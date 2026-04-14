"""
LangGraph graph definition for the OSS Dependency Risk Agent.

Wires the five nodes into a linear pipeline:
    monitor -> investigate -> synthesize -> recommend -> deliver

Exports build_graph() and run_agent() for external callers.
"""

import logging
import os

from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph

from agent.graphs.state import AgentState
from agent.nodes.deliver import deliver
from agent.nodes.investigate import investigate
from agent.nodes.monitor import monitor
from agent.nodes.recommend import recommend
from agent.nodes.synthesize import synthesize

load_dotenv()

logger = logging.getLogger(__name__)

_RECURSION_LIMIT = int(os.environ.get("LANGGRAPH_RECURSION_LIMIT", "10"))


def build_graph() -> StateGraph:
    """
    Construct and compile the risk agent StateGraph.

    Returns:
        Compiled LangGraph graph ready for invocation.
    """
    graph = StateGraph(AgentState)

    graph.add_node("monitor", monitor)
    graph.add_node("investigate", investigate)
    graph.add_node("synthesize", synthesize)
    graph.add_node("recommend", recommend)
    graph.add_node("deliver", deliver)

    graph.add_edge(START, "monitor")
    graph.add_edge("monitor", "investigate")
    graph.add_edge("investigate", "synthesize")
    graph.add_edge("synthesize", "recommend")
    graph.add_edge("recommend", "deliver")
    graph.add_edge("deliver", END)

    return graph.compile()


def run_agent(
    dry_run: bool = False,
    project_limit: int | None = None,
    min_score: float | None = None,
    max_score: float | None = None,
) -> AgentState:
    """
    Build and invoke the risk agent graph.

    Args:
        dry_run:       If True, skip writing the report file.
        project_limit: Cap the number of projects investigated (None = no cap).
        min_score:     Only flag projects with health_score >= min_score.
        max_score:     Only flag projects with health_score < max_score.
                       When neither bound is set, defaults to health_score < 6.0.

    Returns:
        Final AgentState after all nodes have run.
    """
    compiled = build_graph()

    initial_state: AgentState = {
        "flagged_projects":      [],
        "investigation_results": {},
        "risk_assessments":      {},
        "recommendations":       {},
        "report":                "",
        "run_timestamp":         "",
        "dry_run":               dry_run,
        "project_limit":         project_limit,
        "min_score":             min_score,
        "max_score":             max_score,
    }

    logger.info(
        "run_agent: starting (dry_run=%s, project_limit=%s)",
        dry_run, project_limit,
    )

    final_state = compiled.invoke(
        initial_state,
        config={"recursion_limit": _RECURSION_LIMIT},
    )

    flagged_count = len(final_state.get("flagged_projects", []))
    assessed_count = len(final_state.get("risk_assessments", {}))
    logger.info(
        "run_agent: complete — flagged=%d assessed=%d",
        flagged_count, assessed_count,
    )

    return final_state
