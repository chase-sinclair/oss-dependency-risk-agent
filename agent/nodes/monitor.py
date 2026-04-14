"""
Monitor node — queries gold_health_scores for projects below the health threshold.

Populates AgentState.flagged_projects with a list of row dicts from the gold layer.
Applies project_limit if set in state.
"""

import logging
import os
from datetime import datetime, timezone

from dotenv import load_dotenv

from agent.graphs.state import AgentState
from agent.tools.databricks_query import query_databricks

load_dotenv()

logger = logging.getLogger(__name__)

# Default upper bound when no score flags are provided.
_DEFAULT_MAX_SCORE = float(os.environ.get("HEALTH_SCORE_THRESHOLD", "6.0"))

_SQL_BASE = """
SELECT
    repo_full_name,
    health_score,
    commit_score,
    issue_score,
    pr_score,
    contributor_score,
    bus_factor_score,
    health_trend,
    data_days_available,
    first_event_date,
    last_event_date
FROM {catalog}.{schema}.gold_health_scores
WHERE
    health_score IS NOT NULL
    {filters}
ORDER BY CAST(health_score AS DOUBLE) ASC
"""


def _build_sql(catalog: str, schema: str, min_score: float | None, max_score: float | None) -> tuple[str, str]:
    """
    Build the SQL query and a human-readable description of the active filters.

    Returns:
        (sql, description) tuple.
    """
    clauses = []

    if min_score is not None:
        clauses.append(f"AND CAST(health_score AS DOUBLE) >= {min_score}")
    if max_score is not None:
        clauses.append(f"AND CAST(health_score AS DOUBLE) < {max_score}")

    # Default: flag projects below the standard threshold
    if not clauses:
        clauses.append(f"AND CAST(health_score AS DOUBLE) < {_DEFAULT_MAX_SCORE}")

    filters = "\n    ".join(clauses)
    sql = _SQL_BASE.format(catalog=catalog, schema=schema, filters=filters)

    parts = []
    if min_score is not None:
        parts.append(f"min={min_score}")
    if max_score is not None:
        parts.append(f"max={max_score}")
    if not parts:
        parts.append(f"default threshold < {_DEFAULT_MAX_SCORE}")
    description = ", ".join(parts)

    return sql, description


def monitor(state: AgentState) -> dict:
    """
    Query gold_health_scores and return projects matching the score range.

    Score range is controlled by state fields min_score and max_score.
    When neither is set, falls back to the default threshold (health_score < 6.0).

    Returns:
        Dict with keys: flagged_projects, run_timestamp.
    """
    run_timestamp = datetime.now(timezone.utc).isoformat()

    catalog = os.environ.get("DATABRICKS_CATALOG", "workspace")
    schema = os.environ.get("DATABRICKS_SCHEMA", "default")

    min_score: float | None = state.get("min_score")
    max_score: float | None = state.get("max_score")

    sql, description = _build_sql(catalog, schema, min_score, max_score)

    logger.info("monitor: querying gold_health_scores (%s)", description)

    try:
        rows = query_databricks(sql)
    except Exception as exc:
        logger.error("monitor: failed to query Databricks: %s", exc)
        rows = []

    project_limit = state.get("project_limit")
    if project_limit is not None and project_limit > 0:
        rows = rows[:project_limit]
        logger.info("monitor: applied project_limit=%d", project_limit)

    logger.info("monitor: flagged %d projects for investigation", len(rows))
    for row in rows:
        logger.debug(
            "  flagged: %s (health_score=%s)", row.get("repo_full_name"), row.get("health_score")
        )

    return {
        "flagged_projects": rows,
        "run_timestamp": run_timestamp,
    }
