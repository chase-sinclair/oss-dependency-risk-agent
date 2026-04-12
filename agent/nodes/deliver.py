"""
Deliver node — renders the final Markdown report and writes it to docs/reports/.

In dry_run mode the report is built and logged but not written to disk.
The report is also stored in AgentState.report for downstream use (e.g. Streamlit).
"""

import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from agent.graphs.state import AgentState

logger = logging.getLogger(__name__)

_REPORTS_DIR = Path(__file__).resolve().parents[2] / "docs" / "reports"

_ACTION_EMOJI = {
    "REPLACE": "[CRITICAL]",
    "UPGRADE": "[WARNING]",
    "MONITOR": "[INFO]",
}


def _render_report(
    recommendations: dict,
    run_timestamp: str,
) -> str:
    """Build the full Markdown report string."""
    now_str = run_timestamp or datetime.now(timezone.utc).isoformat()

    replace_repos = [r for r in recommendations.values() if r["action"] == "REPLACE"]
    upgrade_repos = [r for r in recommendations.values() if r["action"] == "UPGRADE"]
    monitor_repos = [r for r in recommendations.values() if r["action"] == "MONITOR"]

    lines = [
        "# OSS Dependency Risk Report",
        "",
        f"**Generated:** {now_str}",
        f"**Projects assessed:** {len(recommendations)}",
        (
            f"**Summary:** "
            f"{len(replace_repos)} REPLACE  |  "
            f"{len(upgrade_repos)} UPGRADE  |  "
            f"{len(monitor_repos)} MONITOR"
        ),
        "",
        "---",
        "",
    ]

    def _section(repos: list[dict], heading: str) -> None:
        if not repos:
            return
        lines.append(f"## {heading}")
        lines.append("")
        for rec in sorted(repos, key=lambda r: r.get("risk_score", 0), reverse=True):
            repo = rec["repo_full_name"]
            health = rec.get("health_score", "N/A")
            risk = rec.get("risk_score", 0.0)
            trend = rec.get("health_trend")
            trend_str = f"  (trend: {float(trend):+.2f})" if trend is not None else ""

            lines.append(f"### {repo}")
            lines.append("")
            lines.append(
                f"- **Health score:** {health}/10  |  "
                f"**Risk score:** {risk:.2f}{trend_str}"
            )
            lines.append("")
            assessment = rec.get("assessment", "No assessment available.")
            lines.append(assessment)
            lines.append("")
            lines.append("---")
            lines.append("")

    _section(replace_repos, "Critical — Replace")
    _section(upgrade_repos, "Warning — Upgrade")
    _section(monitor_repos, "Monitor")

    return "\n".join(lines)


def deliver(state: AgentState) -> dict:
    """
    Build the final Markdown report and optionally write it to disk.

    Returns:
        Dict with key: report — the rendered Markdown string.
    """
    recommendations = state.get("recommendations", {})
    run_timestamp = state.get("run_timestamp", "")
    dry_run = state.get("dry_run", False)

    report = _render_report(recommendations, run_timestamp)

    if dry_run:
        logger.info("deliver: dry_run=True — skipping file write")
        logger.debug("deliver: report preview (first 500 chars):\n%s", report[:500])
    else:
        _REPORTS_DIR.mkdir(parents=True, exist_ok=True)

        # Use ISO timestamp without colons for filename compatibility on Windows
        safe_ts = run_timestamp.replace(":", "-").replace("+", "Z")[:19]
        report_path = _REPORTS_DIR / f"risk_report_{safe_ts}.md"

        report_path.write_text(report, encoding="utf-8")
        logger.info("deliver: report written to %s", report_path)

    return {"report": report}
