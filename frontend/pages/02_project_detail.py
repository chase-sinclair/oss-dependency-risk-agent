"""
Project Detail — per-project health metrics, score breakdown, and AI risk assessment.
"""

import html as html_lib
import re
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
from frontend.components.metrics_card import render_score_card, score_badge

st.set_page_config(page_title="Project Detail | OSS Risk Agent", layout="wide")

_CATALOG = "workspace"
_SCHEMA  = "default"
_TABLE   = f"{_CATALOG}.{_SCHEMA}.gold_health_scores"
_REPORTS_DIR = _ROOT / "docs" / "reports"

_SQL_ALL_REPOS = f"SELECT DISTINCT repo_full_name FROM {_TABLE} ORDER BY repo_full_name"

_SQL_LATEST = f"""
SELECT *
FROM {_TABLE}
WHERE repo_full_name = '{{repo}}'
LIMIT 1
"""

_SQL_HISTORY = f"""
SELECT *
FROM {_TABLE}
WHERE repo_full_name = '{{repo}}'
ORDER BY last_event_date ASC
"""


@st.cache_data(ttl=300)
def load_repo_list() -> list:
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


def _find_assessment(repo: str) -> tuple:
    """
    Search recent reports for this repo's Claude assessment.

    Returns:
        (assessment_text, report_label) or (None, None)
    """
    if not _REPORTS_DIR.exists():
        return None, None
    reports = sorted(_REPORTS_DIR.glob("risk_report_*.md"), reverse=True)
    for path in reports[:5]:
        text = path.read_text(encoding="utf-8", errors="ignore")
        marker = f"### {repo}"
        if marker in text:
            start = text.index(marker) + len(marker)
            next_sec = text.find("\n### ", start)
            snippet = text[start:next_sec].strip() if next_sec != -1 else text[start:].strip()
            # Parse report timestamp from filename
            stem = path.stem.replace("risk_report_", "")
            date_part = stem[:10]
            time_part = stem[11:16].replace("-", ":") if len(stem) > 10 else ""
            label = f"{date_part} {time_part}".strip()
            return snippet, label
    return None, None


def _fmt(val, decimals: int = 2) -> str:
    if val is None:
        return "N/A"
    try:
        return f"{float(val):.{decimals}f}"
    except (TypeError, ValueError):
        return str(val)


def _safe_float(val) -> float | None:
    try:
        return float(val) if val is not None else None
    except (TypeError, ValueError):
        return None


# ── Pre-select repo from navigation ───────────────────────────────────────────

with st.spinner("Loading project list..."):
    repo_list = load_repo_list()

if not repo_list:
    st.warning("No projects found in gold table.")
    st.stop()

default_idx = 0
if "nav_repo" in st.session_state:
    nav = st.session_state.pop("nav_repo")
    if nav in repo_list:
        default_idx = repo_list.index(nav)

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("OSS Risk Agent")
    st.markdown("---")
    st.subheader("Select Project")
    st.caption("Type to search within the list.")
    selected_repo = st.selectbox(
        "Repository",
        repo_list,
        index=default_idx,
        label_visibility="collapsed",
    )

# ── Main ──────────────────────────────────────────────────────────────────────

st.title("Project Detail")

if not selected_repo:
    st.info("Select a project from the sidebar.")
    st.stop()

with st.spinner(f"Loading {selected_repo}…"):
    latest     = load_latest(selected_repo)
    history_df = load_history(selected_repo)

if not latest:
    st.warning(f"No data found for `{selected_repo}`.")
    st.stop()

health_f = _safe_float(latest.get("health_score"))
trend_f  = _safe_float(latest.get("health_trend"))

# ── Header row ────────────────────────────────────────────────────────────────

github_url  = f"https://github.com/{selected_repo}"
days_avail  = latest.get("data_days_available", "?")
last_date   = latest.get("last_event_date", "N/A")

head_left, head_right = st.columns([6, 3])
with head_left:
    st.subheader(selected_repo)
    st.link_button("View on GitHub", github_url, icon=":material/open_in_new:")
with head_right:
    st.markdown(score_badge(health_f), unsafe_allow_html=True)
    st.caption(f"Data through: **{last_date}**  ({days_avail} days)")
    if trend_f is not None:
        arrow = "▲" if trend_f >= 0 else "▼"
        color = "#27ae60" if trend_f >= 0 else "#c0392b"
        sign  = "+" if trend_f >= 0 else ""
        st.markdown(
            f"<span style='color:{color};font-size:0.9em'>{arrow} Trend: {sign}{trend_f:.2f}</span>",
            unsafe_allow_html=True,
        )

st.markdown("---")

# ── Score breakdown — 3-column grid ──────────────────────────────────────────

st.subheader("Health Score Breakdown")

g1, g2, g3 = st.columns(3)
with g1:
    render_score_card(
        "Commit Frequency",
        _safe_float(latest.get("commit_score")),
        help_text="Normalised push activity. 10 commits/week = score 10.",
    )
with g2:
    render_score_card(
        "Issue Resolution",
        _safe_float(latest.get("issue_score")),
        help_text="Ratio of issues closed to issues opened.",
    )
with g3:
    render_score_card(
        "PR Merge Rate",
        _safe_float(latest.get("pr_score")),
        help_text="Ratio of PRs closed to PRs opened.",
    )

g4, g5, g6 = st.columns(3)
with g4:
    render_score_card(
        "Contributor Diversity",
        _safe_float(latest.get("contributor_score")),
        help_text="Distinct active committers. 20+ contributors = score 10.",
    )
with g5:
    render_score_card(
        "Bus Factor (inverted)",
        _safe_float(latest.get("bus_factor_score")),
        help_text="Lower concentration of commits = higher score.",
    )
with g6:
    render_score_card(
        "Overall Health",
        health_f,
        help_text="Weighted composite: commit 25%, issue 20%, PR 20%, diversity 20%, bus factor 15%.",
    )

st.markdown("---")

# ── Trend chart (only when multiple data points exist) ────────────────────────

if not history_df.empty and len(history_df) > 1:
    st.subheader("Health Score Over Time")
    render_trend_chart(
        history_df,
        month_col="last_event_date",
        score_col="health_score",
        repo_col="repo_full_name",
        title=f"Health Trend — {selected_repo}",
    )
    st.markdown("---")

# ── AI Risk Assessment ────────────────────────────────────────────────────────

st.subheader("AI Risk Assessment")

assessment, assessed_at = _find_assessment(selected_repo)

if assessment:
    # Header bar
    st.markdown(
        f"<div style='display:flex;align-items:center;gap:12px;margin-bottom:4px'>"
        f"<span style='font-size:0.8em;color:#8b949e'>Last assessed: <strong>{assessed_at}</strong></span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # Terminal-style window chrome
    st.markdown(
        "<div style='"
        "background:#161b22;"
        "border-radius:8px 8px 0 0;"
        "border:1px solid #30363d;"
        "border-bottom:0;"
        "padding:8px 14px;"
        "display:flex;align-items:center;gap:6px"
        "'>"
        "<span style='width:12px;height:12px;border-radius:50%;background:#ff5f57;display:inline-block'></span>"
        "<span style='width:12px;height:12px;border-radius:50%;background:#febc2e;display:inline-block'></span>"
        "<span style='width:12px;height:12px;border-radius:50%;background:#28c840;display:inline-block'></span>"
        "<span style='color:#8b949e;font-family:monospace;font-size:0.8em;margin-left:8px'>"
        f"claude — risk assessment: {selected_repo}"
        "</span>"
        "</div>",
        unsafe_allow_html=True,
    )

    # Strip any leading markdown heading that repeats the repo name
    clean = re.sub(r"^\s*#+\s+.*\n?", "", assessment, count=1).strip()
    escaped = html_lib.escape(clean)

    st.markdown(
        f"<div style='"
        f"background:#0d1117;"
        f"color:#c9d1d9;"
        f"font-family:'Courier New',Courier,monospace;"
        f"padding:20px 24px;"
        f"border-radius:0 0 8px 8px;"
        f"border:1px solid #30363d;"
        f"border-top:0;"
        f"font-size:0.875em;"
        f"line-height:1.75;"
        f"white-space:pre-wrap;"
        f"word-wrap:break-word;"
        f"max-height:480px;"
        f"overflow-y:auto"
        f"'>{escaped}</div>",
        unsafe_allow_html=True,
    )

else:
    st.markdown("---")
    st.warning(
        f"No AI assessment found for **{selected_repo}** in any recent report."
    )
    st.markdown(
        "To generate an assessment, run the agent from the **Agent Control Room**. "
        "Projects are assessed in order of lowest health score."
    )
    col_btn, _ = st.columns([2, 5])
    with col_btn:
        if st.button("Open Agent Control Room", type="primary", use_container_width=True):
            st.switch_page("pages/03_run_agent.py")
