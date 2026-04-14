"""
CLI entry point for the OSS Dependency Risk Agent.

Usage:
    python scripts/run_agent.py [--dry-run] [--limit N]

Flags:
    --dry-run   Build the report but do not write it to disk.
    --limit N   Cap the number of flagged projects processed (default: no cap).
"""

import argparse
import logging
import os
import sys
from pathlib import Path

# Ensure the project root is on sys.path so agent.* imports resolve.
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

_REQUIRED_ENV_VARS = [
    "ANTHROPIC_API_KEY",
    "DATABRICKS_HOST",
    "DATABRICKS_TOKEN",
]


def _check_env() -> bool:
    """Validate required environment variables. Return True if all present."""
    missing = [v for v in _REQUIRED_ENV_VARS if not os.environ.get(v)]
    if missing:
        logger.error("Missing required environment variables: %s", ", ".join(missing))
        return False
    return True


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the OSS Dependency Risk Agent.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Build the report but skip writing it to disk.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Cap the number of flagged projects processed.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    if not _check_env():
        return 1

    logger.info(
        "Starting OSS Risk Agent (dry_run=%s, limit=%s)",
        args.dry_run, args.limit,
    )

    from agent.graphs.risk_agent import run_agent

    try:
        final_state = run_agent(
            dry_run=args.dry_run,
            project_limit=args.limit,
        )
    except Exception as exc:
        logger.exception("Agent run failed: %s", exc)
        return 1

    report = final_state.get("report", "")
    if report:
        print("\n" + "=" * 72)
        print(report[:2000])
        if len(report) > 2000:
            print(f"\n... ({len(report) - 2000} chars truncated — see docs/reports/)")
        print("=" * 72)
    else:
        logger.warning("Agent produced no report output.")

    # Auto-index into Pinecone after a successful non-dry-run
    if not args.dry_run and report and os.environ.get("PINECONE_API_KEY"):
        logger.info("Auto-indexing latest report into Pinecone...")
        try:
            from embeddings.indexer import index_latest_report
            count = index_latest_report()
            logger.info("Pinecone: indexed %d vectors.", count)
        except Exception as exc:
            logger.warning("Pinecone indexing failed (non-fatal): %s", exc)

    return 0


if __name__ == "__main__":
    sys.exit(main())
