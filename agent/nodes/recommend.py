"""
Recommend node — converts risk assessments into structured action recommendations.

Computes a numeric risk score from the health score, maps it to an action
(REPLACE / UPGRADE / MONITOR), and bundles the Claude assessment with metadata
into a recommendation dict.

Risk score = (10 - health_score) / 10  (0 = perfectly healthy, 1 = critical)
Thresholds:
  >= 0.65  -> REPLACE  (health_score <= 3.5)
  >= 0.50  -> UPGRADE  (health_score <= 5.0)
  <  0.50  -> MONITOR
"""

import logging

from agent.graphs.state import AgentState

logger = logging.getLogger(__name__)

_RISK_SCORE_THRESHOLD_REPLACE = 0.65
_RISK_SCORE_THRESHOLD_UPGRADE = 0.50

_ACTION_REPLACE = "REPLACE"
_ACTION_UPGRADE = "UPGRADE"
_ACTION_MONITOR = "MONITOR"


def _compute_action(health_score_str) -> tuple[float, str]:
    """
    Convert a health score string to (risk_score, action).

    Args:
        health_score_str: String or None value from gold_health_scores.

    Returns:
        (risk_score, action) tuple. Defaults to (0.5, MONITOR) if score unavailable.
    """
    if health_score_str is None:
        return 0.5, _ACTION_MONITOR
    try:
        health = float(health_score_str)
    except (TypeError, ValueError):
        return 0.5, _ACTION_MONITOR

    # Clamp to [0, 10]
    health = max(0.0, min(10.0, health))
    risk_score = (10.0 - health) / 10.0

    if risk_score >= _RISK_SCORE_THRESHOLD_REPLACE:
        action = _ACTION_REPLACE
    elif risk_score >= _RISK_SCORE_THRESHOLD_UPGRADE:
        action = _ACTION_UPGRADE
    else:
        action = _ACTION_MONITOR

    return risk_score, action


def recommend(state: AgentState) -> dict:
    """
    Build structured recommendations for each assessed project.

    Returns:
        Dict with key: recommendations — {repo_full_name: rec_dict}.

        Each rec_dict contains:
            repo_full_name: str
            health_score:   str | None   (raw value from gold layer)
            risk_score:     float        (0-1 scale)
            action:         str          (REPLACE | UPGRADE | MONITOR)
            assessment:     str          (Claude's risk assessment text)
            health_trend:   str | None
    """
    flagged = state.get("flagged_projects", [])
    assessments = state.get("risk_assessments", {})

    if not flagged:
        logger.info("recommend: no flagged projects")
        return {"recommendations": {}}

    # Build health score lookup
    health_lookup: dict[str, dict] = {
        row["repo_full_name"]: row
        for row in flagged
        if row.get("repo_full_name")
    }

    recommendations: dict = {}

    for repo, assessment_text in assessments.items():
        health_row = health_lookup.get(repo, {})
        health_score_str = health_row.get("health_score")
        risk_score, action = _compute_action(health_score_str)

        rec = {
            "repo_full_name": repo,
            "health_score":   health_score_str,
            "risk_score":     round(risk_score, 4),
            "action":         action,
            "assessment":     assessment_text,
            "health_trend":   health_row.get("health_trend"),
        }
        recommendations[repo] = rec

        logger.info(
            "recommend: %s -> action=%s risk_score=%.2f health_score=%s",
            repo, action, risk_score, health_score_str,
        )

    replace_count = sum(1 for r in recommendations.values() if r["action"] == _ACTION_REPLACE)
    upgrade_count = sum(1 for r in recommendations.values() if r["action"] == _ACTION_UPGRADE)
    monitor_count = sum(1 for r in recommendations.values() if r["action"] == _ACTION_MONITOR)

    logger.info(
        "recommend: summary — REPLACE=%d  UPGRADE=%d  MONITOR=%d",
        replace_count, upgrade_count, monitor_count,
    )

    return {"recommendations": recommendations}
