"""
CLI wrapper for running dbt commands against the Databricks gold layer.

All dbt commands run from the transformation/dbt/ project directory.
Environment variables are loaded from .env before invoking dbt so that
profiles.yml env_var() calls resolve correctly.

Usage examples:
    python scripts\\run_dbt.py --debug
    python scripts\\run_dbt.py --deps
    python scripts\\run_dbt.py --run
    python scripts\\run_dbt.py --run --test
    python scripts\\run_dbt.py --run --test --full-refresh
    python scripts\\run_dbt.py --run --select gold_health_scores
    python scripts\\run_dbt.py --docs
"""

import argparse
import logging
import os
import subprocess
import sys
from pathlib import Path

# Resolve dbt.exe from the same Scripts/ directory as the active Python
# interpreter so the correct venv installation is used regardless of PATH.
_DBT_EXE = str(Path(sys.executable).parent / "dbt")
_DBT_CMD = [_DBT_EXE]

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-8s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

_DBT_PROJECT_DIR = Path(__file__).resolve().parent.parent / "transformation" / "dbt"


def _run_dbt(args: list[str]) -> int:
    """
    Execute a dbt sub-command from the dbt project directory.

    Streams stdout/stderr directly to the terminal so dbt's colour output
    and progress indicators are preserved.  Returns the process exit code.

    DBT_PROFILES_DIR is injected via the subprocess environment rather than
    the --profiles-dir CLI flag, which has moved between dbt versions and
    behaves differently as a global vs. per-subcommand option.
    """
    cmd = _DBT_CMD + args
    env = {**os.environ, "DBT_PROFILES_DIR": str(_DBT_PROJECT_DIR)}
    logger.info(
        "Running: python -m dbt %s  (cwd=%s)", " ".join(args), _DBT_PROJECT_DIR
    )
    result = subprocess.run(cmd, cwd=str(_DBT_PROJECT_DIR), env=env)
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run dbt commands for the OSS Risk Agent gold layer.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Run `dbt debug` to verify the Databricks connection",
    )
    parser.add_argument(
        "--deps",
        action="store_true",
        help="Run `dbt deps` to install packages from packages.yml",
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Run `dbt run` to build all models",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run `dbt test` after building models",
    )
    parser.add_argument(
        "--docs",
        action="store_true",
        help="Generate and serve dbt docs (opens browser)",
    )
    parser.add_argument(
        "--select",
        type=str,
        default=None,
        metavar="MODEL",
        help="Limit `dbt run` and `dbt test` to a specific model or selector",
    )
    parser.add_argument(
        "--full-refresh",
        action="store_true",
        help="Pass --full-refresh to `dbt run` (rebuilds tables from scratch)",
    )

    args = parser.parse_args()

    if not any([args.debug, args.deps, args.run, args.test, args.docs]):
        parser.print_help()
        return 0

    # Validate required env vars before handing off to dbt
    missing = [
        v for v in ("DATABRICKS_HOST", "DATABRICKS_TOKEN", "DATABRICKS_HTTP_PATH")
        if not os.environ.get(v)
    ]
    if missing:
        logger.error(
            "Missing required environment variables: %s  "
            "Ensure they are set in your .env file.",
            ", ".join(missing),
        )
        return 1

    rc = 0

    if args.debug:
        rc = _run_dbt(["debug"])
        if rc != 0:
            logger.error("dbt debug failed — check profiles.yml and environment variables.")
            return rc

    if args.deps:
        rc = _run_dbt(["deps"])
        if rc != 0:
            logger.error("dbt deps failed.")
            return rc

    if args.run:
        cmd = ["run"]
        if args.full_refresh:
            cmd.append("--full-refresh")
        if args.select:
            cmd += ["--select", args.select]
        rc = _run_dbt(cmd)
        if rc != 0:
            logger.error("dbt run failed.")
            return rc

    if args.test:
        cmd = ["test"]
        if args.select:
            cmd += ["--select", args.select]
        rc = _run_dbt(cmd)
        if rc != 0:
            logger.error("dbt test failed.")
            return rc

    if args.docs:
        rc = _run_dbt(["docs", "generate"])
        if rc != 0:
            return rc
        rc = _run_dbt(["docs", "serve"])

    return rc


if __name__ == "__main__":
    sys.exit(main())
