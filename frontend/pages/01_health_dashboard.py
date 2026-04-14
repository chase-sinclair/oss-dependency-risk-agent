"""
Health Dashboard — searchable, filterable, paginated table of all monitored projects.
"""

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
from frontend.components.health_chart import render_health_bar_chart
from frontend.components.metrics_card import score_badge, status_dot

st.set_page_config(page_title="Health Dashboard | OSS Risk Agent", layout="wide")

_CATALOG = "workspace"
_SCHEMA  = "default"
_TABLE   = f"{_CATALOG}.{_SCHEMA}.gold_health_scores"
_REPORTS_DIR = _ROOT / "docs" / "reports"

_SQL = f"""
SELECT
    repo_full_name,
    org_name,
    health_score,
    commit_score,
    issue_score,
    pr_score,
    contributor_score,
    bus_factor_score,
    data_days_available,
    last_event_date
FROM {_TABLE}
ORDER BY CAST(health_score AS DOUBLE) ASC
"""

_SCORE_COLS = [
    "health_score", "commit_score", "issue_score", "pr_score",
    "contributor_score", "bus_factor_score",
]

_PAGE_SIZE = 25


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


@st.cache_data(ttl=60)
def _assessed_repos() -> set:
    assessed = set()
    if not _REPORTS_DIR.exists():
        return assessed
    for path in _REPORTS_DIR.glob("risk_report_*.md"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for m in re.finditer(r"^### ([^\n]+)", text, re.MULTILINE):
            assessed.add(m.group(1).strip())
    return assessed


def _color_score(val):
    if pd.isna(val):
        return ""
    if val >= 7.0:
        return "background-color:#d5f5e3;color:#1a6b3a"
    if val >= 5.0:
        return "background-color:#fef9e7;color:#7d6608"
    return "background-color:#fadbd8;color:#922b21"


# ── Load data ─────────────────────────────────────────────────────────────────

with st.spinner("Loading..."):
    df_all = load_scores()

# ── Sidebar filters ───────────────────────────────────────────────────────────

with st.sidebar:
    st.title("OSS Risk Agent")
    st.markdown("---")
    st.subheader("Filters")

    if not df_all.empty:
        # Category derived from org_name column or first path segment
        if "org_name" in df_all.columns:
            df_all["_org"] = df_all["org_name"].fillna(
                df_all["repo_full_name"].str.split("/").str[0]
            )
        else:
            df_all["_org"] = df_all["repo_full_name"].str.split("/").str[0]

        all_orgs = ["All"] + sorted(df_all["_org"].dropna().unique())
        selected_org = st.selectbox("Category / Org", all_orgs, index=0)

        status_filter = st.selectbox(
            "Status",
            ["All", "Critical (< 5.0)", "Warning (5.0–7.0)", "Healthy (≥ 7.0)"],
            index=0,
        )

        min_score = st.slider("Min health score", 0.0, 10.0, 0.0, 0.5)

    st.markdown("---")
    st.caption("Click a row in the table, then use **View Project** to open Project Detail.")

# ── Main ──────────────────────────────────────────────────────────────────────

st.title("Health Dashboard")

if df_all.empty:
    st.warning("No health score data found. Run the dbt pipeline to generate scores.")
    st.stop()

# ── Top-of-page search ────────────────────────────────────────────────────────

search_term = st.text_input(
    "Search projects",
    placeholder="Filter by project name…",
    label_visibility="collapsed",
)

# ── Apply filters ─────────────────────────────────────────────────────────────

df = df_all.copy()

if search_term.strip():
    df = df[df["repo_full_name"].str.contains(search_term.strip(), case=False, na=False)]

if selected_org != "All":
    df = df[df["_org"] == selected_org]

if status_filter == "Critical (< 5.0)":
    df = df[df["health_score"] < 5.0]
elif status_filter == "Warning (5.0–7.0)":
    df = df[(df["health_score"] >= 5.0) & (df["health_score"] < 7.0)]
elif status_filter == "Healthy (≥ 7.0)":
    df = df[df["health_score"] >= 7.0]

df = df[df["health_score"] >= min_score]

# ── Summary counts ────────────────────────────────────────────────────────────

last_date = df_all["last_event_date"].max() if "last_event_date" in df_all.columns else "N/A"
st.caption(f"Data through: **{last_date}**  ·  Showing **{len(df)}** of **{len(df_all)}** projects")

c1, c2, c3 = st.columns(3)
with c1:
    st.metric("Critical", int((df["health_score"] < 5.0).sum()))
with c2:
    st.metric("Warning", int(((df["health_score"] >= 5.0) & (df["health_score"] < 7.0)).sum()))
with c3:
    st.metric("Healthy", int((df["health_score"] >= 7.0).sum()))

st.markdown("---")

if df.empty:
    st.info("No projects match the current filters.")
    st.stop()

# ── Build display table ───────────────────────────────────────────────────────

assessed = _assessed_repos()

display_df = df[["repo_full_name", "health_score", "commit_score",
                  "issue_score", "pr_score"]].copy()
display_df.insert(0, "Status", df["health_score"].apply(status_dot))
display_df["AI ✓"] = df["repo_full_name"].apply(lambda r: "✓" if r in assessed else "")

display_df = display_df.rename(columns={
    "repo_full_name": "Project",
    "health_score":   "Health",
    "commit_score":   "Commit",
    "issue_score":    "Issue",
    "pr_score":       "PR",
})

# Round numeric cols
for col in ["Health", "Commit", "Issue", "PR"]:
    if col in display_df.columns:
        display_df[col] = display_df[col].round(2)

# ── Pagination ────────────────────────────────────────────────────────────────

total_pages = max(1, (len(display_df) + _PAGE_SIZE - 1) // _PAGE_SIZE)

col_exp, col_page = st.columns([6, 2])
with col_exp:
    csv_data = df[["repo_full_name", "health_score", "commit_score",
                    "issue_score", "pr_score", "contributor_score",
                    "bus_factor_score", "data_days_available"]].to_csv(index=False)
    st.download_button(
        label="Export CSV",
        data=csv_data,
        file_name="health_scores.csv",
        mime="text/csv",
    )
with col_page:
    page_num = st.number_input("Page", min_value=1, max_value=total_pages, value=1, step=1,
                               label_visibility="collapsed")

start = (page_num - 1) * _PAGE_SIZE
page_df = display_df.iloc[start : start + _PAGE_SIZE].reset_index(drop=True)

st.caption(f"Page {page_num} of {total_pages}  ·  {_PAGE_SIZE} rows per page")

# ── Table with row selection ──────────────────────────────────────────────────

# Style health score column
styled = (
    page_df.style
    .applymap(_color_score, subset=["Health"])
    .format(
        {c: "{:.2f}" for c in ["Health", "Commit", "Issue", "PR"] if c in page_df.columns},
        na_rep="N/A",
    )
)

try:
    selection = st.dataframe(
        styled,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key="health_table",
    )
    selected_rows = selection.selection.rows
    if selected_rows:
        selected_repo = page_df.iloc[selected_rows[0]]["Project"]
        col_sel, col_btn = st.columns([6, 2])
        with col_sel:
            st.info(f"Selected: **{selected_repo}**")
        with col_btn:
            if st.button("View Project →", type="primary", use_container_width=True):
                st.session_state["nav_repo"] = selected_repo
                st.switch_page("pages/02_project_detail.py")
except TypeError:
    # Fallback for older Streamlit without on_select
    st.dataframe(styled, use_container_width=True, hide_index=True)

st.markdown("---")

# ── Bar chart (secondary, full distribution) ──────────────────────────────────

with st.expander("Full Score Distribution", expanded=False):
    render_health_bar_chart(df_all, title=f"Health Scores — All {len(df_all)} Projects")
