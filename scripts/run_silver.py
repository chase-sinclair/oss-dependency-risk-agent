"""
Entry point for Bronze -> Silver Databricks pipeline.

Uploads notebooks, creates/updates the job definition, triggers a run,
and optionally waits for it to complete.

Usage (PowerShell from project root):

    # Upload notebooks and create/update job definition only
    python scripts\\run_silver.py --upload --create-job

    # Trigger a full backfill run (all dates) and wait for result
    python scripts\\run_silver.py --trigger --wait

    # Process a specific date range
    python scripts\\run_silver.py --trigger --wait --start-date 2024-03-01 --end-date 2024-03-15

    # Dry-run: see what would happen without touching Databricks
    python scripts\\run_silver.py --upload --create-job --trigger --dry-run

    # Full end-to-end in one command
    python scripts\\run_silver.py --upload --create-job --trigger --wait

Exit codes: 0 = success, 1 = failure or run error.
"""
import argparse
import json
import logging
import os
import sys
from pathlib import Path

# Ensure project root is on sys.path regardless of invocation directory
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from ingestion.utils.databricks_client import DatabricksClient, DatabricksRunError  # noqa: E402

# ── Paths ──────────────────────────────────────────────────────────────────────
_NOTEBOOKS_DIR  = _PROJECT_ROOT / "transformation" / "databricks" / "notebooks"
_JOB_CONFIG     = _PROJECT_ROOT / "transformation" / "databricks" / "jobs" / "silver_job_config.json"
_JOB_NAME       = "oss-risk-agent-bronze-to-silver"


# ── Logging ────────────────────────────────────────────────────────────────────

def _setup_logging(level: str) -> None:
    numeric = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric,
        format="%(asctime)s [%(levelname)-8s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


# ── Argument parsing ───────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_silver",
        description="OSS Dependency Risk Agent - Bronze to Silver Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Log all operations but skip writes to Databricks",
    )
    parser.add_argument(
        "--log-level",
        default=os.environ.get("LOG_LEVEL", "INFO"),
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        metavar="LEVEL",
        help="Logging verbosity (default: INFO)",
    )

    # ── Actions ────────────────────────────────────────────────────────────────
    parser.add_argument(
        "--upload",
        action="store_true",
        default=False,
        help="Upload notebooks from transformation/databricks/notebooks/ to workspace",
    )
    parser.add_argument(
        "--notebook-path",
        default=os.environ.get("DATABRICKS_NOTEBOOK_PATH", "/Shared/oss-risk-agent"),
        metavar="WORKSPACE_PATH",
        help="Workspace destination folder for notebooks (default: /Shared/oss-risk-agent)",
    )
    parser.add_argument(
        "--create-job",
        action="store_true",
        default=False,
        help="Create or update the Databricks job from silver_job_config.json",
    )
    parser.add_argument(
        "--trigger",
        action="store_true",
        default=False,
        help="Trigger a job run",
    )
    parser.add_argument(
        "--wait",
        action="store_true",
        default=False,
        help="Wait for the triggered run to complete (implies --trigger)",
    )

    # ── Run parameters ─────────────────────────────────────────────────────────
    parser.add_argument(
        "--start-date",
        default="",
        metavar="YYYY-MM-DD",
        help="Earliest event date to process (empty = all data)",
    )
    parser.add_argument(
        "--end-date",
        default="",
        metavar="YYYY-MM-DD",
        help="Latest event date to process (empty = all data)",
    )
    parser.add_argument(
        "--job-id",
        type=int,
        default=None,
        metavar="ID",
        help="Use an existing job ID instead of looking up by name",
    )

    return parser


# ── Step handlers ──────────────────────────────────────────────────────────────

def _do_upload(client: DatabricksClient, notebook_path: str, logger: logging.Logger) -> None:
    logger.info("Uploading notebooks to workspace:%s", notebook_path)
    uploaded = client.upload_all_notebooks(
        notebooks_dir=_NOTEBOOKS_DIR,
        remote_base=notebook_path,
    )
    logger.info("Uploaded %d notebook(s): %s", len(uploaded), uploaded)


def _do_create_job(client: DatabricksClient, logger: logging.Logger) -> int:
    logger.info("Creating/updating job from %s", _JOB_CONFIG)
    job_id = client.create_or_update_job(_JOB_CONFIG)
    logger.info("Job ready (id=%s)", job_id)
    return job_id


def _resolve_job_id(
    client: DatabricksClient,
    explicit_id: int | None,
    logger: logging.Logger,
) -> int:
    if explicit_id:
        return explicit_id
    job_id = client.get_job_by_name(_JOB_NAME)
    if job_id is None:
        raise RuntimeError(
            f"Job '{_JOB_NAME}' not found. Run with --create-job first, "
            f"or provide --job-id."
        )
    return job_id


def _do_trigger(
    client: DatabricksClient,
    job_id: int,
    start_date: str,
    end_date: str,
    logger: logging.Logger,
) -> int | None:
    notebook_params = {}
    if start_date:
        notebook_params["start_date"] = start_date
    if end_date:
        notebook_params["end_date"] = end_date

    logger.info(
        "Triggering job_id=%d with params=%s", job_id, notebook_params or "(none)"
    )
    run_id = client.trigger_run(job_id=job_id, notebook_params=notebook_params)
    if run_id:
        logger.info("Run URL: %s", client.get_run_url(run_id))
    return run_id


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    _setup_logging(args.log_level)
    logger = logging.getLogger(__name__)

    if not any([args.upload, args.create_job, args.trigger, args.wait]):
        parser.print_help()
        return 0

    # --wait implies --trigger
    if args.wait and not args.trigger:
        args.trigger = True

    logger.info(
        "run_silver starting  dry_run=%s  upload=%s  create_job=%s  trigger=%s  wait=%s",
        args.dry_run,
        args.upload,
        args.create_job,
        args.trigger,
        args.wait,
    )

    client = DatabricksClient(dry_run=args.dry_run)
    job_id = None
    run_id = None

    try:
        if args.upload:
            _do_upload(client, args.notebook_path, logger)

        if args.create_job:
            job_id = _do_create_job(client, logger)

        if args.trigger:
            if job_id is None:
                job_id = _resolve_job_id(client, args.job_id, logger)
            run_id = _do_trigger(
                client,
                job_id,
                args.start_date,
                args.end_date,
                logger,
            )

        if args.wait and run_id is not None:
            logger.info("Waiting for run_id=%d to complete...", run_id)
            client.wait_for_run(run_id=run_id)
            logger.info("Run completed successfully.")

    except DatabricksRunError as exc:
        logger.error("Databricks run failed: %s", exc)
        return 1
    except (RuntimeError, TimeoutError) as exc:
        logger.error("%s", exc)
        return 1

    logger.info("run_silver finished successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
