"""
Investigate node — fetches live GitHub signals for each flagged project.

Calls fetch_project_signals() for every project in flagged_projects and
stores the results in AgentState.investigation_results keyed by repo_full_name.
"""

import logging

from agent.graphs.state import AgentState
from agent.tools.github_fetch import fetch_project_signals

logger = logging.getLogger(__name__)


def investigate(state: AgentState) -> dict:
    """
    Fetch GitHub signals for all flagged projects.

    Returns:
        Dict with key: investigation_results — {repo_full_name: signals_dict}.
    """
    flagged = state.get("flagged_projects", [])

    if not flagged:
        logger.info("investigate: no flagged projects to investigate")
        return {"investigation_results": {}}

    logger.info("investigate: fetching signals for %d projects", len(flagged))

    results: dict = {}
    for project in flagged:
        repo = project.get("repo_full_name", "")
        if not repo:
            logger.warning("investigate: skipping project row with missing repo_full_name")
            continue

        logger.info("investigate: fetching signals for %s", repo)
        try:
            signals = fetch_project_signals(repo)
            results[repo] = signals
        except Exception as exc:
            logger.error("investigate: failed to fetch signals for %s: %s", repo, exc)
            results[repo] = {
                "repo_full_name": repo,
                "error": str(exc),
                "metadata": {},
                "open_issues": [],
                "recent_prs": [],
            }

    logger.info("investigate: completed signals fetch for %d/%d projects", len(results), len(flagged))
    return {"investigation_results": results}
