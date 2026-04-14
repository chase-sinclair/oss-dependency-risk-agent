"""
Pinecone semantic search for OSS risk assessments.

Embeds a natural language query using llama-text-embed-v2 and returns the
top-k most similar project assessments from the oss-health index.
"""

import logging
import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_INDEX_NAME = os.environ.get("PINECONE_INDEX_NAME", "oss-health")
_NAMESPACE = "oss-deps"
_EMBED_MODEL = "llama-text-embed-v2"

# Valid recommendation filter values
VALID_FILTERS = {"REPLACE", "UPGRADE", "MONITOR"}


def search(
    query: str,
    top_k: int = 5,
    recommendation_filter: Optional[str] = None,
) -> list[dict]:
    """
    Embed a query and return semantically similar project assessments.

    Args:
        query:                  Natural language search query.
        top_k:                  Number of results to return (default 5).
        recommendation_filter:  If set, restrict results to "REPLACE",
                                "UPGRADE", or "MONITOR". None returns all.

    Returns:
        List of result dicts, each containing:
            repo_full_name, recommendation, health_score, risk_score,
            report_date, report_file, excerpt, similarity_score.
        Sorted by similarity_score descending.

    Raises:
        RuntimeError: if PINECONE_API_KEY is not set.
        ValueError:   if recommendation_filter is not a valid value.
    """
    from pinecone import Pinecone

    api_key = os.environ.get("PINECONE_API_KEY")
    if not api_key:
        raise RuntimeError("PINECONE_API_KEY environment variable is not set")

    if recommendation_filter and recommendation_filter not in VALID_FILTERS:
        raise ValueError(
            f"Invalid recommendation_filter '{recommendation_filter}'. "
            f"Must be one of: {', '.join(sorted(VALID_FILTERS))}"
        )

    if not query or not query.strip():
        return []

    pc = Pinecone(api_key=api_key)

    # Guard: return empty list if the index doesn't exist yet
    existing = [idx.name for idx in pc.list_indexes()]
    if _INDEX_NAME not in existing:
        logger.warning(
            "Pinecone index '%s' does not exist. Run `python scripts\\run_indexer.py` first.",
            _INDEX_NAME,
        )
        return []

    index = pc.Index(_INDEX_NAME)

    # Embed the query
    logger.info("Embedding query: %r", query[:80])
    response = pc.inference.embed(
        model=_EMBED_MODEL,
        inputs=[query.strip()],
        parameters={"input_type": "query", "truncate": "END"},
    )
    query_vector = response[0].values

    # Build optional metadata filter
    pinecone_filter = None
    if recommendation_filter:
        pinecone_filter = {"recommendation": {"$eq": recommendation_filter}}

    logger.info(
        "Querying Pinecone (top_k=%d, filter=%s, namespace=%s)",
        top_k, recommendation_filter, _NAMESPACE,
    )
    result = index.query(
        vector=query_vector,
        top_k=top_k,
        namespace=_NAMESPACE,
        include_metadata=True,
        filter=pinecone_filter,
    )

    matches = result.get("matches", [])
    if not matches:
        logger.info("No matches found for query %r", query[:80])
        return []

    results = []
    for match in matches:
        meta = match.get("metadata", {})
        results.append({
            "repo_full_name":  meta.get("repo_full_name", ""),
            "recommendation":  meta.get("recommendation", ""),
            "health_score":    meta.get("health_score", 0.0),
            "risk_score":      meta.get("risk_score", 0.0),
            "report_date":     meta.get("report_date", ""),
            "report_file":     meta.get("report_file", ""),
            "excerpt":         meta.get("excerpt", ""),
            "similarity_score": round(float(match.get("score", 0.0)), 4),
        })

    logger.info("Returning %d results for query %r", len(results), query[:80])
    return results


def index_stats() -> dict:
    """
    Return basic stats about the Pinecone index.

    Returns:
        Dict with total_vector_count and namespace_vector_count,
        or an empty dict if the index is unreachable.
    """
    from pinecone import Pinecone

    api_key = os.environ.get("PINECONE_API_KEY")
    if not api_key:
        return {}

    try:
        pc = Pinecone(api_key=api_key)
        index = pc.Index(_INDEX_NAME)
        stats = index.describe_index_stats()
        ns = stats.get("namespaces", {}).get(_NAMESPACE, {})
        return {
            "total_vector_count": stats.get("total_vector_count", 0),
            "namespace_vector_count": ns.get("vector_count", 0),
        }
    except Exception as exc:
        logger.warning("Could not fetch index stats: %s", exc)
        return {}
