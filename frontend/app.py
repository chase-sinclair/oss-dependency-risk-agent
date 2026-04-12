"""
OSS Dependency Risk Agent — Streamlit Home Page.

Entry point: streamlit run frontend/app.py
"""

import sys
from pathlib import Path

# Ensure project root is importable from any working directory.
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from agent.tools.databricks_query import query_databricks
from frontend.components.health_chart import render_health_bar_chart
from frontend.components.metrics_card import render_metric_card, score_badge

st.set_page_config(
    page_title="OSS Risk Agent",
    page_icon=":bar_chart:",
    layout="wide",
    initial_sidebar_state="expanded",
)

_CATALOG = "workspace"
_SCHEMA = "default"
_TABLE = f"{_CATALOG}.{_SCHEMA}.gold_health_scores"

_SQL_LATEST = f"""
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
FROM {_TABLE}
WHERE event_month = (SELECT MAX(event_month) FROM {_TABLE})
ORDER BY CAST(health_score AS DOUBLE) ASC
"""


@st.cache_data(ttl=300)
def load_latest_scores() -> pd.DataFrame:
    rows = query_databricks(_SQL_LATEST)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    for col in ["health_score", "commit_score", "issue_score", "pr_score",
                "contributor_score", "bus_factor_score", "health_trend"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


# ── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("OSS Risk Agent")
    st.caption("Dependency health monitoring powered by Claude.")
    st.markdown("---")
    st.page_link("app.py", label="Home", icon=":material/home:")
    st.page_link("pages/01_health_dashboard.py", label="Health Dashboard", icon=":material/dashboard:")
    st.page_link("pages/02_project_detail.py", label="Project Detail", icon=":material/search:")
    st.page_link("pages/03_run_agent.py", label="Run Agent", icon=":material/play_circle:")
    st.page_link("pages/04_reports.py", label="Reports", icon=":material/description:")

# ── Main ─────────────────────────────────────────────────────────────────────

st.title("OSS Dependency Risk Agent")
st.markdown(
    "Monitors the health of open-source dependencies using GitHub event data, "
    "Databricks analytics, and Claude AI risk assessments."
)
st.markdown("---")

with st.spinner("Loading health data..."):
    df = load_latest_scores()

if df.empty:
    st.warning("No health score data found. Run the dbt pipeline to generate scores.")
    st.stop()

# ── Summary stats ─────────────────────────────────────────────────────────────

total = len(df)
critical = int((df["health_score"] < 5.0).sum())
warning = int(((df["health_score"] >= 5.0) & (df["health_score"] < 7.0)).sum())
healthy = int((df["health_score"] >= 7.0).sum())
avg_score = df["health_score"].mean()
event_month = df["event_month"].iloc[0] if "event_month" in df.columns else "N/A"

st.subheader("Summary")
col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    render_metric_card("Projects Monitored", total)
with col2:
    render_metric_card("Critical (< 5.0)", critical, help_text="Immediate action required")
with col3:
    render_metric_card("Warning (5.0-7.0)", warning, help_text="Needs attention")
with col4:
    render_metric_card("Healthy (>= 7.0)", healthy)
with col5:
    render_metric_card("Avg Health Score", f"{avg_score:.2f}" if pd.notna(avg_score) else "N/A")

st.caption(f"Data period: {event_month}")
st.markdown("---")

# ── Top 5 most at-risk projects ───────────────────────────────────────────────

st.subheader("Top 5 Most At-Risk Projects")
top5 = df.nsmallest(5, "health_score")

for _, row in top5.iterrows():
    col_name, col_score, col_trend = st.columns([3, 1, 1])
    with col_name:
        st.markdown(f"**{row['repo_full_name']}**")
    with col_score:
        st.markdown(score_badge(row["health_score"]), unsafe_allow_html=True)
    with col_trend:
        trend = row.get("health_trend")
        if pd.notna(trend):
            arrow = "+" if trend >= 0 else ""
            color = "#2ecc71" if trend >= 0 else "#e74c3c"
            st.markdown(
                f"<span style='color:{color}'>trend: {arrow}{trend:.2f}</span>",
                unsafe_allow_html=True,
            )

st.markdown("---")

# ── Overview chart ────────────────────────────────────────────────────────────

st.subheader("Health Score Overview")
render_health_bar_chart(
    df.nsmallest(20, "health_score"),
    title="20 Lowest Health Scores",
    height=600,
)
