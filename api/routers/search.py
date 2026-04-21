from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from embeddings.searcher import search
from api.models import SearchRequest, SearchResult

router = APIRouter()

_VALID_FILTERS = {"REPLACE", "UPGRADE", "MONITOR"}


@router.post("/search", response_model=list[SearchResult])
def semantic_search(body: SearchRequest) -> list[SearchResult]:
    if not body.query.strip():
        return []

    rec_filter = body.filter.upper() if body.filter else None
    if rec_filter and rec_filter not in _VALID_FILTERS:
        raise HTTPException(status_code=400, detail=f"filter must be one of {_VALID_FILTERS}")

    try:
        hits = search(
            query=body.query,
            top_k=min(body.top_k, 20),
            recommendation_filter=rec_filter,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    results: list[SearchResult] = []
    for h in hits:
        def _f(v: object) -> float | None:
            try:
                return float(v) if v is not None else None
            except (ValueError, TypeError):
                return None

        results.append(
            SearchResult(
                repo_full_name=h.get("repo_full_name", ""),
                health_score=_f(h.get("health_score")),
                recommendation=h.get("recommendation"),
                similarity_score=float(h.get("similarity_score", 0)),
                excerpt=h.get("excerpt"),
                report_date=h.get("report_date"),
            )
        )

    return results
