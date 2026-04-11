"""
Entry point for GitHub Archive -> S3 ingestion.

Usage (PowerShell from project root):

    # Smoke-test with no S3 writes (default: fetches yesterday)
    python scripts\\run_ingestion.py --dry-run

    # Full 90-day backfill (writes to S3)
    python scripts\\run_ingestion.py --backfill

    # Backfill a custom window
    python scripts\\run_ingestion.py --backfill --days 30

    # Fetch one specific date (all 24 hours)
    python scripts\\run_ingestion.py --date 2024-03-15

    # Fetch one specific hour
    python scripts\\run_ingestion.py --date 2024-03-15 --hour 9

    # Re-process hours already in S3
    python scripts\\run_ingestion.py --date 2024-03-15 --no-skip-existing

Exit codes: 0 = success, 1 = one or more hours failed.
"""
import argparse
import logging
import os
import sys
from datetime import date, timedelta

# Ensure the project root is on sys.path regardless of where the script is
# invoked from (e.g., `python scripts\\run_ingestion.py` from project root,
# or `python run_ingestion.py` from within the scripts/ directory).
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from dotenv import load_dotenv  # noqa: E402 — must come after sys.path fix

load_dotenv()

from ingestion.github_archive.backfill import run_backfill  # noqa: E402
from ingestion.github_archive.fetcher import fetch_hour  # noqa: E402
from ingestion.utils.s3_client import S3Client  # noqa: E402


# ── Logging ────────────────────────────────────────────────────────────────────


def _setup_logging(level: str) -> None:
    numeric = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric,
        format="%(asctime)s [%(levelname)-8s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


# ── CLI argument parsing ───────────────────────────────────────────────────────


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_ingestion",
        description="OSS Dependency Risk Agent - GitHub Archive Ingestion",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Log all operations but skip S3 writes (safe for testing)",
    )
    parser.add_argument(
        "--log-level",
        default=os.environ.get("LOG_LEVEL", "INFO"),
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        metavar="LEVEL",
        help="Logging verbosity (default: INFO)",
    )
    parser.add_argument(
        "--no-skip-existing",
        action="store_true",
        default=False,
        help="Re-process hours already present in S3 (overwrite mode)",
    )

    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--backfill",
        action="store_true",
        help="Run a multi-day backfill (use --days to set the window)",
    )
    mode_group.add_argument(
        "--date",
        type=str,
        metavar="YYYY-MM-DD",
        help="Fetch a specific date (all 24 hours unless --hour is given)",
    )

    parser.add_argument(
        "--days",
        type=int,
        default=90,
        metavar="N",
        help="Number of days to backfill (default: 90, used with --backfill)",
    )
    parser.add_argument(
        "--hour",
        type=int,
        default=None,
        metavar="0-23",
        help="Specific hour to fetch (0–23, used with --date)",
    )

    return parser


# ── Mode handlers ──────────────────────────────────────────────────────────────


def _run_backfill_mode(args: argparse.Namespace, logger: logging.Logger) -> int:
    summary = run_backfill(
        days=args.days,
        dry_run=args.dry_run,
        skip_existing=not args.no_skip_existing,
    )
    return 0 if summary.hours_failed == 0 else 1


def _run_date_mode(args: argparse.Namespace, logger: logging.Logger) -> int:
    s3_client = S3Client(dry_run=args.dry_run)
    skip_existing = not args.no_skip_existing

    if args.hour is not None:
        # Single hour
        result = fetch_hour(
            date_str=args.date,
            hour=args.hour,
            s3_client=s3_client,
            skip_existing=skip_existing,
            dry_run=args.dry_run,
        )
        return 0 if (result.success or result.skipped) else 1

    # All 24 hours for the given date
    failed = 0
    for h in range(24):
        result = fetch_hour(
            date_str=args.date,
            hour=h,
            s3_client=s3_client,
            skip_existing=skip_existing,
            dry_run=args.dry_run,
        )
        if not result.success and not result.skipped:
            failed += 1
    return 0 if failed == 0 else 1


def _run_default_mode(args: argparse.Namespace, logger: logging.Logger) -> int:
    """Default: fetch yesterday as a single-day smoke-test."""
    yesterday = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
    logger.info(
        "No mode specified — defaulting to yesterday (%s), dry_run=%s",
        yesterday,
        args.dry_run,
    )
    summary = run_backfill(
        days=1,
        dry_run=args.dry_run,
        skip_existing=not args.no_skip_existing,
    )
    return 0 if summary.hours_failed == 0 else 1


# ── Main ───────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    _setup_logging(args.log_level)
    logger = logging.getLogger(__name__)

    logger.info(
        "run_ingestion starting — mode=%s  dry_run=%s",
        "backfill" if args.backfill else (f"date={args.date}" if args.date else "default"),
        args.dry_run,
    )

    if args.backfill:
        return _run_backfill_mode(args, logger)
    if args.date:
        return _run_date_mode(args, logger)
    return _run_default_mode(args, logger)


if __name__ == "__main__":
    sys.exit(main())
