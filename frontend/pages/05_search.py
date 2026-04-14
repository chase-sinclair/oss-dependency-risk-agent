"""
Semantic Search — natural language queries across all AI risk assessments.

Embeds the query with llama-text-embed-v2 and retrieves the top-k
most similar project assessments from the Pinecone oss-health index.
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from embeddings.searcher import VALID_FILTERS, index_stats, search
from frontend.components.metrics_card import score_badge

st.set_page_config(page_title="Semantic Search | OSS Risk Agent", layout="wide")

_FILTER_OPTIONS = ["All"] + sorted(VALID_FILTERS)

_EXAMPLE_QUERIES = [
    "projects with high bus factor risk and few contributors",
    "repos that haven't merged any pull requests recently",
    "LLM tooling projects at risk of abandonment",
    "infrastructure projects with low commit frequency",
    "projects closing issues slower than they open them",
]


def _action_color(action: str) -> str:
    return {"REPLACE": "#c0392b", "UPGRADE": "#e67e22", "MONITOR": "#2980b9"}.get(action, "#555")


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("OSS Risk Agent")
    st.markdown("---")
    st.subheader("Search Options")

    rec_filter = st.selectbox(
        "Filter by recommendation",
        _FILTER_OPTIONS,
        index=0,
        help="Restrict results to a specific action tier.",
    )
    top_k = st.slider("Max results", min_value=1, max_value=10, value=5)

    st.markdown("---")

    with st.spinner("Checking index…"):
        stats = index_stats()

    vector_count = stats.get("namespace_vector_count", 0) if stats else 0
    if stats:
        st.caption(f"Projects indexed: **{vector_count}**")
    else:
        st.caption("Index unavailable")

# ── Main ──────────────────────────────────────────────────────────────────────

st.title("Semantic Search")
st.markdown(
    "Search across all generated risk assessments using natural language. "
    "Powered by **Pinecone** + **llama-text-embed-v2**."
)
st.markdown("---")

# Empty index guard
if stats and vector_count == 0:
    st.warning(
        "The Pinecone index is empty. Run the agent to generate reports, "
        "then index them:\n\n```\npython scripts/run_indexer.py\n```"
    )
    st.stop()

# ── Auto-submit state (from pill clicks) ──────────────────────────────────────

auto_search = st.session_state.pop("_auto_search", False)

# ── Search bar (centered) ─────────────────────────────────────────────────────

_, search_col, _ = st.columns([1, 6, 1])
with search_col:
    query = st.text_input(
        "Search",
        key="search_input",
        placeholder="e.g. projects with low contributor diversity and slow PR reviews",
        label_visibility="collapsed",
    )
    search_clicked = st.button(
        "Search",
        type="primary",
        use_container_width=True,
    )

st.markdown("---")

# ── Run search ────────────────────────────────────────────────────────────────

run_search  = search_clicked or auto_search
show_pills  = not query.strip() and not run_search

if run_search or query.strip():
    if not query.strip():
        st.info("Enter a query above to search.")
        st.stop()

    filter_value = None if rec_filter == "All" else rec_filter

    with st.spinner("Searching…"):
        try:
            results = search(query=query, top_k=top_k, recommendation_filter=filter_value)
        except RuntimeError as exc:
            st.error(f"Configuration error: {exc}")
            st.stop()
        except Exception as exc:
            st.error(f"Search failed: {exc}")
            st.stop()

    if not results:
        st.info("No results found. Try a broader query or remove the recommendation filter.")
    else:
        st.subheader(f"{len(results)} result{'s' if len(results) != 1 else ''}")

        for i, res in enumerate(results, start=1):
            repo        = res["repo_full_name"]
            action      = res.get("recommendation", "")
            health      = res.get("health_score", 0.0)
            similarity  = res.get("similarity_score", 0.0)
            excerpt     = res.get("excerpt", "")
            report_date = res.get("report_date", "")

            action_color = _action_color(action)
            action_badge = (
                f"<span style='background:{action_color};color:#fff;"
                f"padding:3px 10px;border-radius:4px;font-weight:bold;"
                f"font-size:0.82em'>{action}</span>"
            ) if action else ""

            with st.container():
                col_num, col_body = st.columns([1, 11])
                with col_num:
                    st.markdown(f"### {i}")
                with col_body:
                    # Project name + badges
                    st.markdown(f"**{repo}**")
                    badge_row = st.columns([2, 2, 2, 3, 2])
                    with badge_row[0]:
                        st.markdown(action_badge, unsafe_allow_html=True)
                    with badge_row[1]:
                        st.markdown(score_badge(health), unsafe_allow_html=True)
                    with badge_row[2]:
                        st.caption(f"Similarity: {similarity:.3f}")
                    with badge_row[3]:
                        st.caption(f"Report: {report_date}")
                    with badge_row[4]:
                        if st.button("View Detail →", key=f"detail_{i}_{repo}"):
                            st.session_state["nav_repo"] = repo
                            st.switch_page("pages/02_project_detail.py")

                    # Excerpt
                    if excerpt:
                        st.markdown(
                            f"<div style='"
                            f"background:rgba(128,128,128,0.06);"
                            f"border-left:3px solid {action_color};"
                            f"padding:10px 14px;"
                            f"border-radius:0 4px 4px 0;"
                            f"font-size:0.9em;"
                            f"margin-top:8px;"
                            f"color:inherit"
                            f"'>{excerpt}</div>",
                            unsafe_allow_html=True,
                        )

                    # View Full Report link
                    if report_date:
                        st.caption(
                            f"[View full report on the Reports page →]"
                            f"(pages/04_reports.py)"
                        )

                st.markdown("---")

elif show_pills:
    # ── Landing state: example prompt pills ──────────────────────────────────

    st.markdown("### Try an example query")
    st.markdown("Click a pill to auto-submit the search.")
    st.markdown("")

    # Render pills in rows of 2-3
    for i in range(0, len(_EXAMPLE_QUERIES), 2):
        pill_cols = st.columns(2)
        for j, col in enumerate(pill_cols):
            idx = i + j
            if idx < len(_EXAMPLE_QUERIES):
                ex = _EXAMPLE_QUERIES[idx]
                with col:
                    if st.button(
                        ex,
                        key=f"pill_{idx}",
                        use_container_width=True,
                    ):
                        st.session_state["search_input"] = ex
                        st.session_state["_auto_search"]  = True
                        st.rerun()
