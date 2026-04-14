"""
CLI entry point for the Pinecone indexer.

Parses generated risk reports and upserts per-project assessment vectors
to the oss-health Pinecone index.

Usage:
    python scripts/run_indexer.py              # index latest report only
    python scripts/run_indexer.py --all        # index all reports
    python scripts/run_indexer.py --dry-run    # parse reports, skip Pinecone upsert
"""

import argparse
import logging
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

_REPORTS_DIR = _PROJECT_ROOT / "docs" / "reports"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Index OSS risk assessment reports into Pinecone."
    )
    parser.add_argument(
        "--all",
        action="store_true",
        default=False,
        help="Index all reports in docs/reports/ (default: latest only).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Parse reports and log records but skip Pinecone upsert.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help="Enable DEBUG logging to inspect parsed record content.",
    )
    return parser.parse_args()


def _dry_run_index(index_all: bool) -> int:
    """Parse and log records without calling Pinecone."""
    from embeddings.indexer import _parse_report

    report_files = sorted(_REPORTS_DIR.glob("risk_report_*.md"), reverse=True)
    if not report_files:
        logger.warning("No report files found in %s", _REPORTS_DIR)
        return 0

    targets = report_files if index_all else [report_files[0]]
    total = 0
    for path in targets:
        records = _parse_report(path)
        logger.info("[dry-run] %s -> %d records would be indexed", path.name, len(records))
        for rec in records:
            logger.debug(
                "  [dry-run] %s | %s | health=%.2f | excerpt=%r",
                rec["repo_full_name"],
                rec["recommendation"],
                rec["health_score"],
                rec["assessment_text"][:80],
            )
        total += len(records)
    logger.info("[dry-run] Total: %d records across %d report(s)", total, len(targets))
    return total


def main() -> int:
    args = _parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    if not _REPORTS_DIR.exists() or not any(_REPORTS_DIR.glob("risk_report_*.md")):
        logger.error(
            "No report files found in %s. Run the agent first: "
            "python scripts\\run_agent.py",
            _REPORTS_DIR,
        )
        return 1

    if args.dry_run:
        _dry_run_index(args.all)
        return 0

    from embeddings.indexer import index_all_reports, index_latest_report

    try:
        if args.all:
            logger.info("Indexing all reports in %s", _REPORTS_DIR)
            count = index_all_reports(_REPORTS_DIR)
        else:
            logger.info("Indexing latest report in %s", _REPORTS_DIR)
            count = index_latest_report(_REPORTS_DIR)
    except RuntimeError as exc:
        logger.error("%s", exc)
        return 1
    except Exception as exc:
        logger.exception("Indexer failed: %s", exc)
        return 1

    logger.info("Done. %d vectors upserted to Pinecone.", count)
    return 0


if __name__ == "__main__":
    sys.exit(main())
