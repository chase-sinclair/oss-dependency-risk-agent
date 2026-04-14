"""
OSS Dependency Risk Agent — Streamlit Home Page.

Entry point: streamlit run frontend/app.py
"""

import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from agent.tools.databricks_query import query_databricks
from frontend.components.metrics_card import render_metric_card, score_badge

st.set_page_config(
    page_title="OSS Dependency Risk Agent",
    page_icon=":bar_chart:",
    layout="wide",
    initial_sidebar_state="expanded",
)

_CATALOG = "workspace"
_SCHEMA = "default"
_TABLE = f"{_CATALOG}.{_SCHEMA}.gold_health_scores"
_REPORTS_DIR = _ROOT / "docs" / "reports"

_SQL = f"""
SELECT
    repo_full_name,
    health_score,
    data_days_available,
    last_event_date,
    computed_at
FROM {_TABLE}
ORDER BY CAST(health_score AS DOUBLE) ASC
"""


@st.cache_data(ttl=300)
def load_scores() -> pd.DataFrame:
    rows = query_databricks(_SQL)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["health_score"] = pd.to_numeric(df["health_score"], errors="coerce")
    return df


@st.cache_data(ttl=60)
def _assessed_repos() -> set:
    """Set of org/repo strings found in any report file."""
    assessed = set()
    if not _REPORTS_DIR.exists():
        return assessed
    for path in _REPORTS_DIR.glob("risk_report_*.md"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for m in re.finditer(r"^### ([^\n]+)", text, re.MULTILINE):
            assessed.add(m.group(1).strip())
    return assessed


@st.cache_data(ttl=60)
def _latest_report_info() -> tuple:
    """Return (timestamp_str, project_count) for the most recent report."""
    if not _REPORTS_DIR.exists():
        return "N/A", 0
    reports = sorted(_REPORTS_DIR.glob("risk_report_*.md"), reverse=True)
    if not reports:
        return "N/A", 0
    path = reports[0]
    stem = path.stem.replace("risk_report_", "")  # 2026-04-12T19-36-29
    date_part = stem[:10]
    time_part = stem[11:16].replace("-", ":") if len(stem) > 10 else ""
    friendly = f"{date_part} {time_part}".strip()
    text = path.read_text(encoding="utf-8", errors="ignore")
    count = len(re.findall(r"^### ", text, re.MULTILINE))
    return friendly, count


def _go_to_project(repo: str) -> None:
    st.session_state["nav_repo"] = repo
    st.switch_page("pages/02_project_detail.py")


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("OSS Risk Agent")
    st.caption("Dependency health monitoring powered by Claude.")
    st.markdown("---")
    st.page_link("app.py",                         label="Home",               icon=":material/home:")
    st.page_link("pages/01_health_dashboard.py",   label="Health Dashboard",   icon=":material/dashboard:")
    st.page_link("pages/02_project_detail.py",     label="Project Detail",     icon=":material/search:")
    st.page_link("pages/03_run_agent.py",          label="Agent Control Room", icon=":material/play_circle:")
    st.page_link("pages/04_reports.py",            label="Reports",            icon=":material/description:")
    st.page_link("pages/05_search.py",             label="Semantic Search",    icon=":material/manage_search:")

# ── Main ─────────────────────────────────────────────────────────────────────

st.title("OSS Dependency Risk Agent")
st.markdown(
    "Real-time health monitoring for open-source dependencies — "
    "**GitHub Archive** events · **Databricks** analytics · **Claude AI** risk assessments."
)
st.markdown("---")

with st.spinner("Loading health data..."):
    df = load_scores()

if df.empty:
    st.warning("No health score data found. Run the dbt pipeline to generate scores.")
    st.stop()

# ── Summary metrics ───────────────────────────────────────────────────────────

total        = len(df)
critical     = int((df["health_score"] < 5.0).sum())
warning      = int(((df["health_score"] >= 5.0) & (df["health_score"] < 7.0)).sum())
healthy      = int((df["health_score"] >= 7.0).sum())
avg_score    = df["health_score"].mean()

assessed     = _assessed_repos()
ai_count     = int(df["repo_full_name"].isin(assessed).sum())

last_data    = str(df["last_event_date"].max()) if "last_event_date" in df.columns else "N/A"
pipeline_ts  = str(df["computed_at"].max())[:19]  if "computed_at"    in df.columns else "N/A"
agent_ts, _  = _latest_report_info()

st.subheader("Summary")
c1, c2, c3, c4, c5, c6 = st.columns(6)
with c1:
    render_metric_card("Projects Monitored", total)
with c2:
    render_metric_card("Critical", critical, help_text="Health score < 5.0 — immediate action required")
with c3:
    render_metric_card("Warning",  warning,  help_text="Health score 5.0–7.0 — needs attention")
with c4:
    render_metric_card("Healthy",  healthy,  help_text="Health score ≥ 7.0")
with c5:
    render_metric_card("Avg Score", f"{avg_score:.2f}" if pd.notna(avg_score) else "N/A")
with c6:
    render_metric_card("AI Assessed", ai_count, help_text="Projects with a Claude risk assessment")

st.caption(
    f"Data through: **{last_data}**  ·  "
    f"Pipeline run: **{pipeline_ts}**  ·  "
    f"Last agent run: **{agent_ts}**"
)
st.markdown("---")

# ── Top 5 at-risk / healthiest ────────────────────────────────────────────────

col_risk, _spacer, col_best = st.columns([5, 1, 5])

with col_risk:
    st.subheader("🔴 Most At-Risk")
    for _, row in df.nsmallest(5, "health_score").iterrows():
        repo = row["repo_full_name"]
        r1, r2, r3 = st.columns([5, 3, 2])
        with r1:
            st.markdown(f"**{repo}**")
        with r2:
            st.markdown(score_badge(row["health_score"]), unsafe_allow_html=True)
        with r3:
            if st.button("View →", key=f"risk_{repo}", use_container_width=True):
                _go_to_project(repo)

with col_best:
    st.subheader("🟢 Healthiest")
    for _, row in df.nlargest(5, "health_score").iterrows():
        repo = row["repo_full_name"]
        r1, r2, r3 = st.columns([5, 3, 2])
        with r1:
            st.markdown(f"**{repo}**")
        with r2:
            st.markdown(score_badge(row["health_score"]), unsafe_allow_html=True)
        with r3:
            if st.button("View →", key=f"best_{repo}", use_container_width=True):
                _go_to_project(repo)
