"""
Health Dashboard page — all projects with health scores, sortable table, bar chart.
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
from frontend.components.health_chart import render_health_bar_chart

st.set_page_config(page_title="Health Dashboard | OSS Risk Agent", layout="wide")

_CATALOG = "workspace"
_SCHEMA = "default"
_TABLE = f"{_CATALOG}.{_SCHEMA}.gold_health_scores"

_SQL = f"""
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

_SCORE_COLS = [
    "health_score", "commit_score", "issue_score", "pr_score",
    "contributor_score", "bus_factor_score", "health_trend",
]


@st.cache_data(ttl=300)
def load_scores() -> pd.DataFrame:
    rows = query_databricks(_SQL)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    for col in _SCORE_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _color_score(val):
    """Pandas Styler function — returns CSS for a health score cell."""
    if pd.isna(val):
        return ""
    if val >= 7.0:
        return "background-color: #d5f5e3; color: #1e8449"
    if val >= 5.0:
        return "background-color: #fef9e7; color: #9a7d0a"
    return "background-color: #fadbd8; color: #922b21"


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("OSS Risk Agent")
    st.markdown("---")
    st.subheader("Filters")

    with st.spinner("Loading..."):
        df_all = load_scores()

    if not df_all.empty:
        # Category filter derived from org (first segment of repo_full_name)
        df_all["org"] = df_all["repo_full_name"].str.split("/").str[0]
        all_orgs = sorted(df_all["org"].unique())
        selected_orgs = st.multiselect("Organisation", all_orgs, default=[])

        min_score = st.slider(
            "Min health score",
            min_value=0.0,
            max_value=10.0,
            value=0.0,
            step=0.5,
        )
        show_critical_only = st.checkbox("Critical only (< 5.0)", value=False)

# ── Main ──────────────────────────────────────────────────────────────────────

st.title("Health Dashboard")
st.markdown("All monitored projects with their latest health scores.")

if df_all.empty:
    st.warning("No health score data found.")
    st.stop()

# Apply filters
df = df_all.copy()
if selected_orgs:
    df = df[df["org"].isin(selected_orgs)]
if show_critical_only:
    df = df[df["health_score"] < 5.0]
else:
    df = df[df["health_score"] >= min_score]

event_month = df["event_month"].iloc[0] if not df.empty and "event_month" in df.columns else "N/A"
st.caption(f"Data period: {event_month}  |  Showing {len(df)} of {len(df_all)} projects")

if df.empty:
    st.info("No projects match the current filters.")
    st.stop()

# ── Summary counts ────────────────────────────────────────────────────────────

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Critical (< 5.0)", int((df["health_score"] < 5.0).sum()))
with col2:
    st.metric("Warning (5.0-7.0)", int(((df["health_score"] >= 5.0) & (df["health_score"] < 7.0)).sum()))
with col3:
    st.metric("Healthy (>= 7.0)", int((df["health_score"] >= 7.0).sum()))

st.markdown("---")

# ── Chart ─────────────────────────────────────────────────────────────────────

with st.expander("Bar Chart", expanded=True):
    render_health_bar_chart(df, title=f"Health Scores ({len(df)} projects)")

# ── Table ─────────────────────────────────────────────────────────────────────

st.subheader("Project Table")

display_cols = [
    "repo_full_name", "health_score", "commit_score", "issue_score",
    "pr_score", "contributor_score", "bus_factor_score", "health_trend",
]
display_cols = [c for c in display_cols if c in df.columns]
display_df = df[display_cols].copy()

# Round numeric columns for readability
for col in _SCORE_COLS:
    if col in display_df.columns:
        display_df[col] = display_df[col].round(2)

# Apply conditional colouring to health_score only
styled = (
    display_df.style
    .applymap(_color_score, subset=["health_score"])
    .format(
        {c: "{:.2f}" for c in _SCORE_COLS if c in display_df.columns},
        na_rep="N/A",
    )
)

st.dataframe(styled, use_container_width=True, hide_index=True)
