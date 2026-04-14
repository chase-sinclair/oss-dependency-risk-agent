"""
Semantic Search page — query across all OSS risk assessments using natural language.

Embeds the user's query with llama-text-embed-v2 and returns the top 5
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

st.set_page_config(page_title="Search | OSS Risk Agent", layout="wide")

_FILTER_OPTIONS = ["All"] + sorted(VALID_FILTERS)


def _action_color(action: str) -> str:
    return {"REPLACE": "#e74c3c", "UPGRADE": "#f39c12", "MONITOR": "#3498db"}.get(action, "#888")


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

    # Index stats
    with st.spinner("Checking index..."):
        stats = index_stats()

    if stats:
        st.caption(
            f"Index: **{stats.get('namespace_vector_count', 0)}** vectors "
            f"({stats.get('total_vector_count', 0)} total)"
        )
    else:
        st.caption("Index stats unavailable")

# ── Main ──────────────────────────────────────────────────────────────────────

st.title("Semantic Search")
st.markdown(
    "Search across all generated risk assessments using natural language. "
    "Powered by Pinecone + llama-text-embed-v2."
)
st.markdown("---")

# Empty index guard
if stats and stats.get("namespace_vector_count", 0) == 0:
    st.warning(
        "The Pinecone index is empty. Run the agent to generate reports, "
        "then index them with:\n\n"
        "```\npython scripts\\run_indexer.py\n```"
    )
    st.stop()

# Query input
query = st.text_input(
    "Search query",
    placeholder="e.g. projects with low contributor diversity and slow PR reviews",
    label_visibility="collapsed",
)

col_search, col_clear = st.columns([1, 5])
with col_search:
    search_clicked = st.button("Search", type="primary", use_container_width=True)

st.markdown("---")

# Run search
if search_clicked or query:
    if not query.strip():
        st.info("Enter a query above to search.")
        st.stop()

    filter_value = None if rec_filter == "All" else rec_filter

    with st.spinner("Searching..."):
        try:
            results = search(query=query, top_k=top_k, recommendation_filter=filter_value)
        except RuntimeError as exc:
            st.error(f"Configuration error: {exc}")
            st.stop()
        except Exception as exc:
            st.error(f"Search failed: {exc}")
            st.stop()

    if not results:
        st.info(
            "No results found. Try a broader query or remove the recommendation filter."
        )
    else:
        st.subheader(f"{len(results)} result{'s' if len(results) != 1 else ''}")

        for i, res in enumerate(results, start=1):
            repo = res["repo_full_name"]
            action = res["recommendation"]
            health = res.get("health_score", 0.0)
            similarity = res.get("similarity_score", 0.0)
            excerpt = res.get("excerpt", "")
            report_date = res.get("report_date", "")

            action_color = _action_color(action)
            action_badge = (
                f"<span style='background:{action_color};color:#fff;"
                f"padding:2px 8px;border-radius:4px;font-weight:bold;"
                f"font-size:0.8em'>{action}</span>"
            )

            with st.container():
                col_rank, col_info = st.columns([1, 11])
                with col_rank:
                    st.markdown(f"### {i}")
                with col_info:
                    st.markdown(f"**{repo}**")
                    col_action, col_score, col_sim, col_date = st.columns([2, 2, 2, 3])
                    with col_action:
                        st.markdown(action_badge, unsafe_allow_html=True)
                    with col_score:
                        st.markdown(score_badge(health), unsafe_allow_html=True)
                    with col_sim:
                        st.caption(f"Similarity: {similarity:.3f}")
                    with col_date:
                        st.caption(f"Report: {report_date}")

                    if excerpt:
                        st.markdown(
                            f"<div style='background:rgba(128,128,128,0.08);"
                            f"border-left:3px solid {action_color};"
                            f"padding:8px 12px;border-radius:0 4px 4px 0;"
                            f"font-size:0.9em;margin-top:6px'>{excerpt}</div>",
                            unsafe_allow_html=True,
                        )

                st.markdown("---")

else:
    # Landing state — show example queries
    st.markdown("### Example queries")
    examples = [
        "projects with high bus factor risk and few contributors",
        "repos that haven't merged any pull requests recently",
        "projects with poor issue resolution and declining health trend",
        "LLM tooling projects at risk of abandonment",
        "infrastructure projects with low commit frequency",
    ]
    for ex in examples:
        if st.button(ex, key=ex):
            st.session_state["_search_query"] = ex
            st.rerun()
