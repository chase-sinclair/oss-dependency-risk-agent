"""
Batch GitHub Scorecard fetcher.

Fetches 6 governance + security signals for every repo currently in
gold_health_scores and writes the results to workspace.default.github_scorecard
(Delta table) via the Databricks REST API.

Usage:
    python scripts/run_scorecard.py
    python scripts/run_scorecard.py --dry-run
    python scripts/run_scorecard.py --dry-run --limit 5
    python scripts/run_scorecard.py --limit 50
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-8s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

from agent.tools.databricks_query import query_databricks  # noqa: E402
from agent.tools.github_scorecard import fetch_scorecard   # noqa: E402

CATALOG = "workspace"
SCHEMA  = "default"
TABLE   = f"{CATALOG}.{SCHEMA}.github_scorecard"

_INTER_REPO_SLEEP = 0.15  # seconds between repos — stays well under 5k req/hr


# ── DDL ───────────────────────────────────────────────────────────────────────

CREATE_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS {TABLE} (
    repo_full_name       STRING        NOT NULL,
    is_maintained        BOOLEAN,
    has_license          BOOLEAN,
    is_branch_protected  BOOLEAN,
    requires_code_review BOOLEAN,
    has_security_policy  BOOLEAN,
    vuln_count           INT,
    vuln_data_available  BOOLEAN,
    has_dep_update_tool  BOOLEAN,
    language             STRING,
    fetched_at           TIMESTAMP
)
USING DELTA
"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _sql_bool(v: bool | None) -> str:
    if v is None:
        return "NULL"
    return "true" if v else "false"


def _sql_int(v: int | None) -> str:
    return "NULL" if v is None else str(int(v))


def _sql_str(v: str | None) -> str:
    if v is None:
        return "NULL"
    escaped = v.replace("'", "''")
    return f"'{escaped}'"


def _sql_ts(v: str | None) -> str:
    if v is None:
        return "NULL"
    escaped = v.replace("'", "''")
    return f"CAST('{escaped}' AS TIMESTAMP)"


def _row_to_values(r: dict) -> str:
    return (
        f"({_sql_str(r['repo_full_name'])}, "
        f"{_sql_bool(r.get('is_maintained'))}, "
        f"{_sql_bool(r.get('has_license'))}, "
        f"{_sql_bool(r.get('is_branch_protected'))}, "
        f"{_sql_bool(r.get('requires_code_review'))}, "
        f"{_sql_bool(r.get('has_security_policy'))}, "
        f"{_sql_int(r.get('vuln_count'))}, "
        f"{_sql_bool(r.get('vuln_data_available'))}, "
        f"{_sql_bool(r.get('has_dep_update_tool'))}, "
        f"{_sql_str(r.get('language'))}, "
        f"{_sql_ts(r.get('fetched_at'))})"
    )


# ── Core logic ────────────────────────────────────────────────────────────────

def fetch_repos() -> list[str]:
    rows = query_databricks(
        f"SELECT DISTINCT repo_full_name FROM {CATALOG}.{SCHEMA}.gold_health_scores"
        " ORDER BY repo_full_name"
    )
    return [r["repo_full_name"] for r in rows if r.get("repo_full_name")]


def run(limit: int | None, dry_run: bool) -> None:
    logger.info("run_scorecard  dry_run=%s  limit=%s", dry_run, limit)

    repos = fetch_repos()
    logger.info("Found %d repos in gold_health_scores", len(repos))

    if limit:
        repos = repos[:limit]
        logger.info("Capped to first %d repos (--limit)", len(repos))

    results: list[dict] = []
    errors:  list[str]  = []

    for i, repo in enumerate(repos, 1):
        logger.info("[%d/%d] %s", i, len(repos), repo)
        if dry_run:
            logger.info("  DRY RUN — skipping API calls")
            results.append({
                "repo_full_name":       repo,
                "is_maintained":        None,
                "has_license":          None,
                "is_branch_protected":  None,
                "requires_code_review": None,
                "has_security_policy":  None,
                "vuln_count":           None,
                "vuln_data_available":  False,
                "has_dep_update_tool":  None,
                "language":             None,
                "fetched_at":           None,
            })
            continue

        card = fetch_scorecard(repo)
        if "error" in card:
            logger.warning("  FAILED: %s", card["error"])
            errors.append(repo)
        else:
            logger.info(
                "  maintained=%s  license=%s  protected=%s  review=%s"
                "  sec_policy=%s  vulns=%s(%s)  dep_tool=%s  lang=%s",
                card["is_maintained"],
                card["has_license"],
                card["is_branch_protected"],
                card["requires_code_review"],
                card["has_security_policy"],
                card["vuln_count"],
                "avail" if card["vuln_data_available"] else "N/A",
                card["has_dep_update_tool"],
                card["language"],
            )
            results.append(card)

        time.sleep(_INTER_REPO_SLEEP)

    if dry_run:
        print(f"\nDry run complete — would write {len(results)} rows to {TABLE}.")
        return

    if not results:
        logger.error("No results to write — aborting.")
        sys.exit(1)

    # Create table if it doesn't exist
    logger.info("Ensuring %s exists...", TABLE)
    query_databricks(CREATE_TABLE_SQL)

    # Overwrite table with fresh results
    values_sql = ",\n    ".join(_row_to_values(r) for r in results)
    insert_sql = f"""
INSERT OVERWRITE {TABLE}
SELECT
    col1  AS repo_full_name,
    col2  AS is_maintained,
    col3  AS has_license,
    col4  AS is_branch_protected,
    col5  AS requires_code_review,
    col6  AS has_security_policy,
    col7  AS vuln_count,
    col8  AS vuln_data_available,
    col9  AS has_dep_update_tool,
    col10 AS language,
    col11 AS fetched_at
FROM (VALUES
    {values_sql}
) AS t(col1, col2, col3, col4, col5, col6, col7, col8, col9, col10, col11)
"""
    logger.info("Writing %d rows to %s...", len(results), TABLE)
    query_databricks(insert_sql)
    logger.info("Done.")

    if errors:
        logger.warning("%d repos failed and were skipped: %s", len(errors), errors)

    print(f"\nScorecard complete — {len(results)} rows written to {TABLE}.")
    if errors:
        print(f"  {len(errors)} repos skipped due to errors (see logs).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Batch-fetch GitHub scorecard signals and write to Databricks.",
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Fetch nothing; log what would happen.")
    parser.add_argument("--limit", type=int, default=None, metavar="N",
                        help="Process only the first N repos.")
    args = parser.parse_args()
    run(limit=args.limit, dry_run=args.dry_run)
