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

# Projects whose health score is below this threshold are flagged for investigation.
_HEALTH_SCORE_THRESHOLD = float(os.environ.get("HEALTH_SCORE_THRESHOLD", "6.0"))

_SQL = """
SELECT
    repo_full_name,
    health_score,
    commit_score,
    issue_score,
    pr_score,
    contributor_score,
    bus_factor_score,
    health_trend,
    event_month
FROM {catalog}.{schema}.gold_health_scores
WHERE
    health_score IS NOT NULL
    AND CAST(health_score AS DOUBLE) < {threshold}
ORDER BY CAST(health_score AS DOUBLE) ASC
"""


def monitor(state: AgentState) -> dict:
    """
    Query gold_health_scores and return projects that fall below the threshold.

    Returns:
        Dict with keys: flagged_projects, run_timestamp.
    """
    run_timestamp = datetime.now(timezone.utc).isoformat()

    catalog = os.environ.get("DATABRICKS_CATALOG", "workspace")
    schema = os.environ.get("DATABRICKS_SCHEMA", "default")

    sql = _SQL.format(
        catalog=catalog,
        schema=schema,
        threshold=_HEALTH_SCORE_THRESHOLD,
    )

    logger.info(
        "monitor: querying gold_health_scores (threshold=%.1f)", _HEALTH_SCORE_THRESHOLD
    )

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
