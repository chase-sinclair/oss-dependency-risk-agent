"""
Pinecone indexer for OSS risk assessment reports.

Parses generated Markdown reports in docs/reports/, extracts per-project
sections, embeds them using Pinecone's hosted llama-text-embed-v2 model,
and upserts vectors to the oss-health index.

Vector ID is a stable hash of (repo_full_name + report_file) so re-indexing
the same report is idempotent.
"""

import hashlib
import logging
import os
import re
import time
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_REPORTS_DIR = Path(__file__).resolve().parents[1] / "docs" / "reports"
_INDEX_NAME = os.environ.get("PINECONE_INDEX_NAME", "oss-health")
_NAMESPACE = "oss-deps"
_EMBED_MODEL = "llama-text-embed-v2"
_BATCH_SIZE = 50  # Pinecone upsert batch limit

# Section heading → recommendation action
_SECTION_MAP = {
    "Critical — Replace": "REPLACE",
    "Warning — Upgrade":  "UPGRADE",
    "Monitor":            "MONITOR",
}


# ── Parsing ───────────────────────────────────────────────────────────────────

def _parse_report(report_path: Path) -> list[dict]:
    """
    Parse a single report file into a list of per-project record dicts.

    Each record contains:
        repo_full_name, recommendation, health_score, risk_score,
        assessment_text, report_date, report_file
    """
    text = report_path.read_text(encoding="utf-8")
    report_date = _date_from_filename(report_path.name)
    records: list[dict] = []

    # Split on level-2 section headers (## ...)
    sections = re.split(r"^## (.+)$", text, flags=re.MULTILINE)
    # sections = [preamble, heading1, body1, heading2, body2, ...]
    # Zip into (heading, body) pairs
    it = iter(sections[1:])
    for heading, body in zip(it, it):
        recommendation = _SECTION_MAP.get(heading.strip())
        if recommendation is None:
            continue

        # Split body on level-3 repo headers (### org/repo)
        repo_sections = re.split(r"^### (.+)$", body, flags=re.MULTILINE)
        it2 = iter(repo_sections[1:])
        for repo_name, repo_body in zip(it2, it2):
            repo_name = repo_name.strip()
            if not repo_name or "/" not in repo_name:
                continue

            health_score = _extract_health_score(repo_body)
            risk_score = _extract_risk_score(repo_body)
            assessment = _extract_assessment(repo_body)

            records.append({
                "repo_full_name": repo_name,
                "recommendation": recommendation,
                "health_score":   health_score,
                "risk_score":     risk_score,
                "assessment_text": assessment,
                "report_date":    report_date,
                "report_file":    report_path.name,
            })

    logger.debug("Parsed %d project records from %s", len(records), report_path.name)
    return records


def _date_from_filename(filename: str) -> str:
    """Extract date string from risk_report_2026-04-12T19-36-29.md -> 2026-04-12."""
    match = re.search(r"(\d{4}-\d{2}-\d{2})", filename)
    return match.group(1) if match else ""


def _extract_health_score(text: str) -> float:
    """Extract health score float from a repo section body."""
    match = re.search(r"\*\*Health score:\*\*\s*([\d.]+)", text)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass
    return 0.0


def _extract_risk_score(text: str) -> float:
    """Extract risk score float from a repo section body."""
    match = re.search(r"\*\*Risk score:\*\*\s*([\d.]+)", text)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass
    return 0.0


def _extract_assessment(text: str) -> str:
    """
    Extract the assessment bullet text from a repo section body.

    Works line-by-line: skips the metadata line (health/risk score),
    horizontal rules, and leading/trailing blank lines.
    """
    lines = text.splitlines()
    kept = []
    for line in lines:
        stripped = line.strip()
        # Skip the metadata line and horizontal rules
        if stripped.startswith("- **Health score") or stripped == "---":
            continue
        kept.append(line)

    return "\n".join(kept).strip()


def _vector_id(repo_full_name: str, report_file: str) -> str:
    """Stable, collision-resistant vector ID for a (repo, report) pair."""
    raw = f"{repo_full_name}|{report_file}"
    return hashlib.sha256(raw.encode()).hexdigest()[:40]


# ── Embedding ─────────────────────────────────────────────────────────────────

def _embed_texts(pc, texts: list[str]) -> list[list[float]]:
    """
    Embed a list of texts using Pinecone's hosted llama-text-embed-v2.

    Args:
        pc:    Pinecone client instance.
        texts: List of strings to embed.

    Returns:
        List of embedding vectors (list of floats).
    """
    response = pc.inference.embed(
        model=_EMBED_MODEL,
        inputs=texts,
        parameters={"input_type": "passage", "truncate": "END"},
    )
    return [item.values for item in response]


# ── Upsert ────────────────────────────────────────────────────────────────────

def _upsert_records(index, records: list[dict], embeddings: list[list[float]]) -> int:
    """Upsert (record, embedding) pairs into Pinecone in batches."""
    vectors = []
    for rec, emb in zip(records, embeddings):
        vectors.append({
            "id":     _vector_id(rec["repo_full_name"], rec["report_file"]),
            "values": emb,
            "metadata": {
                "repo_full_name": rec["repo_full_name"],
                "recommendation": rec["recommendation"],
                "health_score":   rec["health_score"],
                "risk_score":     rec["risk_score"],
                "report_date":    rec["report_date"],
                "report_file":    rec["report_file"],
                # Store a short excerpt for display (first 300 chars of assessment)
                "excerpt":        rec["assessment_text"][:300],
            },
        })

    upserted = 0
    for i in range(0, len(vectors), _BATCH_SIZE):
        batch = vectors[i : i + _BATCH_SIZE]
        index.upsert(vectors=batch, namespace=_NAMESPACE)
        upserted += len(batch)
        logger.debug("Upserted batch of %d vectors", len(batch))

    return upserted


# ── Public API ────────────────────────────────────────────────────────────────

def _get_or_create_index(pc):
    """
    Return the Pinecone index, creating it first if it does not exist.

    llama-text-embed-v2 produces 1024-dimensional vectors by default.
    The index is created as a serverless index on AWS us-east-1.
    """
    from pinecone import ServerlessSpec

    existing = [idx.name for idx in pc.list_indexes()]
    if _INDEX_NAME not in existing:
        logger.info(
            "Index '%s' not found — creating serverless index (dim=1024, metric=cosine)...",
            _INDEX_NAME,
        )
        pc.create_index(
            name=_INDEX_NAME,
            dimension=1024,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
        # Poll until the index is ready (typically 10-30 seconds)
        for attempt in range(30):
            status = pc.describe_index(_INDEX_NAME).status
            if status.get("ready"):
                break
            logger.debug("Waiting for index to be ready (attempt %d)...", attempt + 1)
            time.sleep(2)
        else:
            raise RuntimeError(f"Pinecone index '{_INDEX_NAME}' did not become ready in time.")
        logger.info("Index '%s' created and ready.", _INDEX_NAME)
    else:
        logger.debug("Index '%s' already exists.", _INDEX_NAME)

    return pc.Index(_INDEX_NAME)


def index_report(report_path: Path) -> int:
    """
    Parse a single report file and upsert its vectors to Pinecone.

    Args:
        report_path: Path to a risk_report_*.md file.

    Returns:
        Number of vectors upserted.

    Raises:
        RuntimeError: if PINECONE_API_KEY is not set.
    """
    from pinecone import Pinecone

    api_key = os.environ.get("PINECONE_API_KEY")
    if not api_key:
        raise RuntimeError("PINECONE_API_KEY environment variable is not set")

    records = _parse_report(report_path)
    if not records:
        logger.warning("No project records found in %s — skipping", report_path.name)
        return 0

    # Pinecone rejects empty strings — substitute a metadata-based fallback so the
    # record still lands in the index and is searchable by repo name / recommendation.
    for rec in records:
        if not rec["assessment_text"].strip():
            rec["assessment_text"] = (
                f"{rec['repo_full_name']} — health score {rec['health_score']:.1f}/10, "
                f"recommendation: {rec['recommendation']}. "
                "No detailed assessment text was captured for this project in this report."
            )
            logger.warning(
                "Empty assessment for %s — using metadata fallback text.",
                rec["repo_full_name"],
            )

    if not records:
        logger.warning("No records found in %s — skipping", report_path.name)
        return 0

    logger.info("Embedding %d records from %s", len(records), report_path.name)
    for rec in records:
        logger.debug(
            "  record: %s | %s | assessment[:80]=%r",
            rec["repo_full_name"], rec["recommendation"],
            rec["assessment_text"][:80],
        )

    pc = Pinecone(api_key=api_key)
    index = _get_or_create_index(pc)

    texts = [rec["assessment_text"] for rec in records]
    embeddings = _embed_texts(pc, texts)

    count = _upsert_records(index, records, embeddings)
    logger.info("Indexed %d vectors from %s into namespace '%s'", count, report_path.name, _NAMESPACE)
    return count


def index_all_reports(reports_dir: Optional[Path] = None) -> int:
    """
    Index all risk_report_*.md files in the reports directory.

    Args:
        reports_dir: Directory to scan. Defaults to docs/reports/.

    Returns:
        Total number of vectors upserted across all reports.
    """
    reports_dir = reports_dir or _REPORTS_DIR
    report_files = sorted(reports_dir.glob("risk_report_*.md"))

    if not report_files:
        logger.warning("No report files found in %s", reports_dir)
        return 0

    total = 0
    for path in report_files:
        try:
            total += index_report(path)
        except Exception as exc:
            logger.error("Failed to index %s: %s", path.name, exc)

    logger.info("Indexed %d total vectors from %d reports", total, len(report_files))
    return total


def index_latest_report(reports_dir: Optional[Path] = None) -> int:
    """
    Index only the most recently generated report.

    Returns:
        Number of vectors upserted, or 0 if no reports exist.
    """
    reports_dir = reports_dir or _REPORTS_DIR
    report_files = sorted(reports_dir.glob("risk_report_*.md"), reverse=True)

    if not report_files:
        logger.warning("No report files found in %s", reports_dir)
        return 0

    return index_report(report_files[0])
