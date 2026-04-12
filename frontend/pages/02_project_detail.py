"""
Project Detail page — per-project deep dive with health metrics and AI risk assessment.
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from agent.tools.databricks_query import query_databricks
from frontend.components.health_chart import render_trend_chart
from frontend.components.metrics_card import render_metric_card, render_score_row, score_badge

st.set_page_config(page_title="Project Detail | OSS Risk Agent", layout="wide")

_CATALOG = "workspace"
_SCHEMA = "default"
_TABLE = f"{_CATALOG}.{_SCHEMA}.gold_health_scores"

_SQL_ALL_REPOS = f"""
SELECT DISTINCT repo_full_name
FROM {_TABLE}
ORDER BY repo_full_name
"""

_SQL_LATEST = f"""
SELECT *
FROM {_TABLE}
WHERE repo_full_name = '{{repo}}'
  AND event_month = (SELECT MAX(event_month) FROM {_TABLE} WHERE repo_full_name = '{{repo}}')
LIMIT 1
"""

_SQL_HISTORY = f"""
SELECT *
FROM {_TABLE}
WHERE repo_full_name = '{{repo}}'
ORDER BY event_month ASC
"""

_REPORTS_DIR = _ROOT / "docs" / "reports"


@st.cache_data(ttl=300)
def load_repo_list() -> list[str]:
    rows = query_databricks(_SQL_ALL_REPOS)
    return [r["repo_full_name"] for r in rows]


@st.cache_data(ttl=300)
def load_latest(repo: str) -> dict:
    rows = query_databricks(_SQL_LATEST.format(repo=repo.replace("'", "''")))
    return rows[0] if rows else {}


@st.cache_data(ttl=300)
def load_history(repo: str) -> pd.DataFrame:
    rows = query_databricks(_SQL_HISTORY.format(repo=repo.replace("'", "''")))
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    for col in ["health_score", "commit_score", "issue_score", "pr_score",
                "contributor_score", "bus_factor_score", "health_trend"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _find_latest_assessment(repo: str) -> str | None:
    """Search the most recent report file for this repo's Claude assessment."""
    if not _REPORTS_DIR.exists():
        return None
    reports = sorted(_REPORTS_DIR.glob("risk_report_*.md"), reverse=True)
    for report_path in reports[:5]:  # check most recent 5 reports
        text = report_path.read_text(encoding="utf-8")
        # Look for the repo section header
        marker = f"### {repo}"
        if marker in text:
            start = text.index(marker) + len(marker)
            # Find next section header or end of file
            next_section = text.find("\n### ", start)
            snippet = text[start:next_section].strip() if next_section != -1 else text[start:].strip()
            return snippet
    return None


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("OSS Risk Agent")
    st.markdown("---")
    st.subheader("Select Project")
    with st.spinner("Loading project list..."):
        repo_list = load_repo_list()

    if not repo_list:
        st.warning("No projects found in gold table.")
        st.stop()

    selected_repo = st.selectbox("Repository", repo_list)

# ── Main ──────────────────────────────────────────────────────────────────────

st.title("Project Detail")

if not selected_repo:
    st.info("Select a project from the sidebar.")
    st.stop()

with st.spinner(f"Loading data for {selected_repo}..."):
    latest = load_latest(selected_repo)
    history_df = load_history(selected_repo)

if not latest:
    st.warning(f"No data found for `{selected_repo}`.")
    st.stop()

# ── Header ────────────────────────────────────────────────────────────────────

def _fmt(val, decimals: int = 2) -> str:
    if val is None:
        return "N/A"
    try:
        return f"{float(val):.{decimals}f}"
    except (TypeError, ValueError):
        return str(val)

health = latest.get("health_score")
health_f = float(health) if health is not None else None
trend = latest.get("health_trend")
trend_f = float(trend) if trend is not None else None

st.subheader(selected_repo)
col_badge, col_trend, col_month = st.columns([2, 2, 3])
with col_badge:
    st.markdown(score_badge(health_f), unsafe_allow_html=True)
with col_trend:
    if trend_f is not None:
        arrow = "+" if trend_f >= 0 else ""
        color = "#2ecc71" if trend_f >= 0 else "#e74c3c"
        st.markdown(
            f"<span style='color:{color}'>MoM trend: {arrow}{trend_f:.2f}</span>",
            unsafe_allow_html=True,
        )
with col_month:
    st.caption(f"Data period: {latest.get('event_month', 'N/A')}")

st.markdown("---")

# ── Score breakdown ───────────────────────────────────────────────────────────

st.subheader("Health Score Breakdown")

_SIGNAL_HELP = {
    "Commit Frequency":     "Normalized push activity over the last month.",
    "Issue Resolution":     "Ratio of issues closed to issues opened.",
    "PR Merge Rate":        "Ratio of PRs closed to PRs opened.",
    "Contributor Diversity":"Distinct active contributors in the month.",
    "Bus Factor (inverted)":"Concentration risk — higher means less concentrated.",
    "Overall Health":       "Weighted composite of the above signals.",
}

render_score_row("Overall Health",       health_f,                                          help_text=_SIGNAL_HELP["Overall Health"])
st.markdown("")
render_score_row("Commit Frequency",     _fmt(latest.get("commit_score")) and float(_fmt(latest.get("commit_score"))) if latest.get("commit_score") else None,      help_text=_SIGNAL_HELP["Commit Frequency"])
render_score_row("Issue Resolution",     float(latest["issue_score"])    if latest.get("issue_score")    else None, help_text=_SIGNAL_HELP["Issue Resolution"])
render_score_row("PR Merge Rate",        float(latest["pr_score"])       if latest.get("pr_score")       else None, help_text=_SIGNAL_HELP["PR Merge Rate"])
render_score_row("Contributor Diversity",float(latest["contributor_score"]) if latest.get("contributor_score") else None, help_text=_SIGNAL_HELP["Contributor Diversity"])
render_score_row("Bus Factor (inverted)",float(latest["bus_factor_score"]) if latest.get("bus_factor_score") else None, help_text=_SIGNAL_HELP["Bus Factor (inverted)"])

st.markdown("---")

# ── Trend chart ───────────────────────────────────────────────────────────────

if not history_df.empty and len(history_df) > 1:
    st.subheader("Health Score Over Time")
    render_trend_chart(
        history_df,
        month_col="event_month",
        score_col="health_score",
        repo_col="repo_full_name",
        title=f"Health Trend — {selected_repo}",
    )
    st.markdown("---")

# ── AI Risk Assessment ────────────────────────────────────────────────────────

st.subheader("AI Risk Assessment")
assessment = _find_latest_assessment(selected_repo)
if assessment:
    st.markdown(assessment)
else:
    st.info(
        "No risk assessment found for this project. "
        "Run the agent on the **Run Agent** page to generate one."
    )
