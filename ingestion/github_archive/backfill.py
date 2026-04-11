"""
90-day backfill orchestrator for GitHub Archive ingestion.

Iterates over every (date, hour) pair in the requested window, calls
fetch_hour() for each, and accumulates a BackfillSummary. Already-processed
hours are skipped automatically via the S3 sentinel mechanism in fetcher.py.

Public API:
    run_backfill(days, dry_run, ...) -> BackfillSummary
    generate_date_hour_pairs(days, end_date) -> list[tuple[str, int]]
"""
import logging
import os
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

from dotenv import load_dotenv

from ingestion.github_archive.fetcher import FetchResult, fetch_hour
from ingestion.github_archive.project_list import get_project_set
from ingestion.utils.s3_client import S3Client

load_dotenv()

logger = logging.getLogger(__name__)

_HOURS_PER_DAY = 24


# ── Summary dataclass ──────────────────────────────────────────────────────────


@dataclass
class BackfillSummary:
    """Aggregate outcome of a backfill run."""

    days: int
    dry_run: bool
    hours_attempted: int = 0
    hours_succeeded: int = 0
    hours_skipped: int = 0
    hours_failed: int = 0
    total_events_downloaded: int = 0
    total_events_filtered: int = 0
    total_s3_keys_written: int = 0
    failed_hours: list[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        actionable = self.hours_attempted - self.hours_skipped
        if actionable == 0:
            return 1.0
        return self.hours_succeeded / actionable


# ── Date/hour generation ───────────────────────────────────────────────────────


def generate_date_hour_pairs(
    days: int,
    end_date: Optional[date] = None,
) -> list[tuple[str, int]]:
    """
    Generate all (date_str, hour) pairs for the last N days, oldest first.

    Args:
        days:     Number of days to include (e.g. 90).
        end_date: Last date to include. Defaults to yesterday (today - 1 day)
                  because the current day's hourly files are still being written.

    Returns:
        List of ("YYYY-MM-DD", 0..23) tuples in chronological order.
    """
    if end_date is None:
        end_date = date.today() - timedelta(days=1)

    start_date = end_date - timedelta(days=days - 1)
    pairs: list[tuple[str, int]] = []
    current = start_date

    while current <= end_date:
        date_str = current.strftime("%Y-%m-%d")
        for hour in range(_HOURS_PER_DAY):
            pairs.append((date_str, hour))
        current += timedelta(days=1)

    return pairs


# ── Orchestrator ───────────────────────────────────────────────────────────────


def run_backfill(
    days: int = 90,
    dry_run: bool = True,
    skip_existing: bool = True,
    end_date: Optional[date] = None,
) -> BackfillSummary:
    """
    Orchestrate a GitHub Archive backfill for the last N days.

    Downloads, filters, and uploads one hour-file at a time. Failures are
    recorded but do not abort the run — processing continues with the next hour.

    Args:
        days:           Number of days to backfill (default: 90).
        dry_run:        If True, no data is written to S3.
        skip_existing:  If True, hours already in S3 are skipped (idempotent).
        end_date:       Last date to include (defaults to yesterday).

    Returns:
        BackfillSummary with per-hour counters and a list of any failed hours.
    """
    summary = BackfillSummary(days=days, dry_run=dry_run)
    target_repos = get_project_set()
    s3_client = S3Client(dry_run=dry_run)

    pairs = generate_date_hour_pairs(days, end_date)
    total = len(pairs)

    logger.info(
        "Backfill started — days=%d, hours=%d, projects=%d, dry_run=%s",
        days,
        total,
        len(target_repos),
        dry_run,
    )

    for idx, (date_str, hour) in enumerate(pairs, start=1):
        logger.info(
            "Progress [%d/%d] — %s hour %02d",
            idx,
            total,
            date_str,
            hour,
        )

        result: FetchResult = fetch_hour(
            date_str=date_str,
            hour=hour,
            s3_client=s3_client,
            target_repos=target_repos,
            skip_existing=skip_existing,
            dry_run=dry_run,
        )

        summary.hours_attempted += 1

        if result.skipped:
            summary.hours_skipped += 1
        elif result.success:
            summary.hours_succeeded += 1
            summary.total_events_downloaded += result.events_downloaded
            summary.total_events_filtered += result.events_filtered
            summary.total_s3_keys_written += len(result.s3_keys_written)
        else:
            summary.hours_failed += 1
            summary.failed_hours.append(
                f"{date_str}-{hour:02d}: {result.error}"
            )
            logger.warning(
                "Hour %s-%02d failed: %s", date_str, hour, result.error
            )

    _log_summary(summary)
    return summary


def _log_summary(summary: BackfillSummary) -> None:
    """Emit a structured final summary log."""
    logger.info(
        "Backfill complete — "
        "succeeded=%d  skipped=%d  failed=%d  total=%d  "
        "events_filtered=%d  s3_keys=%d  dry_run=%s",
        summary.hours_succeeded,
        summary.hours_skipped,
        summary.hours_failed,
        summary.hours_attempted,
        summary.total_events_filtered,
        summary.total_s3_keys_written,
        summary.dry_run,
    )
    if summary.failed_hours:
        logger.warning(
            "%d hour(s) failed:\n%s",
            len(summary.failed_hours),
            "\n".join(f"  {h}" for h in summary.failed_hours),
        )
