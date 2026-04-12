"""
LangGraph state schema for the OSS Dependency Risk Agent.

Imported by every node and the graph builder — kept in its own module
to avoid circular imports.
"""

from typing import NotRequired, TypedDict


class AgentState(TypedDict):
    # Core pipeline outputs, populated step-by-step
    flagged_projects: list[dict]          # set by monitor
    investigation_results: dict           # set by investigate  {repo: signals}
    risk_assessments: dict                # set by synthesize   {repo: assessment}
    recommendations: dict                 # set by recommend    {repo: rec_dict}
    report: str                           # set by deliver

    # Runtime metadata
    run_timestamp: str                    # ISO-8601 UTC, set by monitor

    # CLI / invocation options (not part of the CLAUDE.md spec but needed at runtime)
    dry_run: NotRequired[bool]            # skip file write in deliver
    project_limit: NotRequired[int | None]  # cap flagged list in monitor
