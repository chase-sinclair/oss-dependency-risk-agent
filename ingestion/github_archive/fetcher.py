"""
GitHub Archive hourly event fetcher.

Downloads a single hour-file from data.gharchive.org, filters it for the
target project list, groups events by repository, and uploads per-project
gzipped NDJSON to the S3 bronze layer.

Public API:
    fetch_hour(date_str, hour, s3_client, ...) -> FetchResult
"""
import gzip
import io
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Optional

import requests
from dotenv import load_dotenv
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ingestion.github_archive.project_list import get_project_set
from ingestion.utils.s3_client import S3Client

load_dotenv()

logger = logging.getLogger(__name__)

_GHARCHIVE_BASE_URL = os.environ.get(
    "GITHUB_ARCHIVE_BASE_URL", "https://data.gharchive.org"
)
_DOWNLOAD_TIMEOUT_SECONDS = 180


# ── Result dataclass ───────────────────────────────────────────────────────────


@dataclass
class FetchResult:
    """Outcome of processing one hour-file."""

    date_str: str
    hour: int
    url: str
    events_downloaded: int = 0
    events_filtered: int = 0
    projects_with_events: int = 0
    s3_keys_written: list[str] = field(default_factory=list)
    skipped: bool = False
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.error is None and not self.skipped


# ── Download ───────────────────────────────────────────────────────────────────


@retry(
    retry=retry_if_exception_type((requests.RequestException, ConnectionError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=60),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def _download_archive(url: str) -> bytes:
    """
    Stream-download a GH Archive .json.gz file and return raw bytes.

    Retries up to 3 times on network errors with exponential back-off.
    Raises requests.HTTPError on 4xx/5xx responses.
    """
    logger.info("Downloading %s", url)
    response = requests.get(url, stream=True, timeout=_DOWNLOAD_TIMEOUT_SECONDS)
    response.raise_for_status()

    chunks: list[bytes] = []
    total = 0
    for chunk in response.iter_content(chunk_size=1024 * 1024):  # 1 MB chunks
        chunks.append(chunk)
        total += len(chunk)

    logger.debug("Downloaded %.1f MB from %s", total / 1_048_576, url)
    return b"".join(chunks)


# ── Parsing ────────────────────────────────────────────────────────────────────


def _parse_events(raw_gz: bytes) -> list[dict]:
    """
    Decompress and parse gzipped NDJSON into a list of event dicts.

    Malformed JSON lines are skipped with a warning rather than crashing.
    """
    events: list[dict] = []
    with gzip.open(io.BytesIO(raw_gz), "rt", encoding="utf-8") as fh:
        for line_number, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError as exc:
                logger.warning("Line %d: malformed JSON — %s", line_number, exc)
    return events


# ── Filtering ──────────────────────────────────────────────────────────────────


def _filter_events(
    events: list[dict], target_repos: set[str]
) -> dict[str, list[dict]]:
    """
    Group events by repository, keeping only those in target_repos.

    Args:
        events:       Parsed event dicts from one hour-file.
        target_repos: Set of 'org/repo' strings (O(1) lookup).

    Returns:
        Dict mapping 'org/repo' -> list of matching events.
    """
    grouped: dict[str, list[dict]] = {}
    for event in events:
        repo_name: str = event.get("repo", {}).get("name", "")
        if repo_name in target_repos:
            grouped.setdefault(repo_name, []).append(event)
    return grouped


# ── Compression ───────────────────────────────────────────────────────────────


def _compress_events(events: list[dict]) -> bytes:
    """Serialize a list of event dicts to gzipped NDJSON bytes."""
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb") as gz:
        for event in events:
            gz.write((json.dumps(event, separators=(",", ":")) + "\n").encode("utf-8"))
    return buf.getvalue()


# ── Public entry point ─────────────────────────────────────────────────────────


def fetch_hour(
    date_str: str,
    hour: int,
    s3_client: S3Client,
    target_repos: Optional[set[str]] = None,
    skip_existing: bool = True,
    dry_run: bool = True,
) -> FetchResult:
    """
    Download, filter, and upload one hour of GitHub Archive data.

    Args:
        date_str:       Date in YYYY-MM-DD format, e.g. "2024-03-15".
        hour:           Hour of day 0–23.
        s3_client:      Configured S3Client instance.
        target_repos:   Set of 'org/repo' strings. Defaults to full project list.
        skip_existing:  If True, skip hours already marked done in S3.
        dry_run:        If True, skip all S3 writes (passed through to S3Client).

    Returns:
        FetchResult with counters and any error message.
    """
    if target_repos is None:
        target_repos = get_project_set()

    url = f"{_GHARCHIVE_BASE_URL}/{date_str}-{hour}.json.gz"
    result = FetchResult(date_str=date_str, hour=hour, url=url)

    # ── Idempotency check ──────────────────────────────────────────────────────
    sentinel_key = S3Client.build_sentinel_key(date_str, hour)
    if skip_existing and not dry_run and s3_client.key_exists(sentinel_key):
        logger.info("Skipping already-processed hour: %s-%02d", date_str, hour)
        result.skipped = True
        return result

    # ── Download -> Parse -> Filter -> Upload ────────────────────────────────────
    try:
        raw_gz = _download_archive(url)
        events = _parse_events(raw_gz)
        result.events_downloaded = len(events)

        grouped = _filter_events(events, target_repos)
        result.events_filtered = sum(len(v) for v in grouped.values())
        result.projects_with_events = len(grouped)

        logger.info(
            "%s-%02d: %d total events -> %d matched across %d projects",
            date_str,
            hour,
            result.events_downloaded,
            result.events_filtered,
            result.projects_with_events,
        )

        for repo_full_name, repo_events in grouped.items():
            org, repo = repo_full_name.split("/", 1)
            key = S3Client.build_key(org, repo, date_str, hour)
            compressed = _compress_events(repo_events)
            s3_client.upload_bytes(key, compressed)
            result.s3_keys_written.append(key)
            logger.debug(
                "Uploaded %d events (%d bytes) -> %s",
                len(repo_events),
                len(compressed),
                key,
            )

        # Write sentinel only after all per-project uploads succeed
        if not dry_run:
            s3_client.upload_bytes(sentinel_key, b"done", content_type="text/plain")
            logger.debug("Sentinel written: %s", sentinel_key)

    except requests.HTTPError as exc:
        # 404 means GH Archive simply has no file for this hour — not an error
        if exc.response is not None and exc.response.status_code == 404:
            logger.info("No archive file for %s-%02d (HTTP 404 — skipping)", date_str, hour)
            result.skipped = True
        else:
            result.error = str(exc)
            logger.error("HTTP error for %s-%02d: %s", date_str, hour, exc)
    except Exception as exc:  # noqa: BLE001
        result.error = str(exc)
        logger.error("Failed to process %s-%02d: %s", date_str, hour, exc, exc_info=True)

    return result
