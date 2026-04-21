from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from agent.tools.databricks_query import query_databricks
from api.models import HealthScore, Summary

router = APIRouter()

_TABLE = "workspace.default.gold_health_scores"
_REPORTS_DIR = _ROOT / "docs" / "reports"

_SAFE_NAME = re.compile(r"^[a-zA-Z0-9_.\-]+$")


def _cast(row: dict) -> HealthScore:
    def _f(v: object) -> Optional[float]:
        try:
            return float(v) if v is not None else None
        except (ValueError, TypeError):
            return None

    def _i(v: object) -> Optional[int]:
        try:
            return int(float(v)) if v is not None else None
        except (ValueError, TypeError):
            return None

    return HealthScore(
        repo_full_name=row.get("repo_full_name") or "",
        org_name=row.get("org_name"),
        health_score=_f(row.get("health_score")) or 0.0,
        health_trend=_f(row.get("health_trend")),
        commit_score=_f(row.get("commit_score")),
        issue_score=_f(row.get("issue_score")),
        pr_score=_f(row.get("pr_score")),
        contributor_score=_f(row.get("contributor_score")),
        bus_factor_score=_f(row.get("bus_factor_score")),
        data_days_available=_i(row.get("data_days_available")),
        computed_at=row.get("computed_at"),
    )


@router.get("/health-scores", response_model=list[HealthScore])
def get_health_scores(
    min_score: Optional[float] = Query(None),
    max_score: Optional[float] = Query(None),
    limit: Optional[int] = Query(None, ge=1, le=500),
    order: str = Query("asc", pattern="^(asc|desc)$"),
) -> list[HealthScore]:
    conditions: list[str] = []
    if min_score is not None:
        conditions.append(f"CAST(health_score AS DOUBLE) >= {min_score}")
    if max_score is not None:
        conditions.append(f"CAST(health_score AS DOUBLE) <= {max_score}")

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    direction = "ASC" if order == "asc" else "DESC"
    limit_clause = f"LIMIT {limit}" if limit else ""

    sql = f"""
        SELECT
            repo_full_name, org_name, health_score,
            commit_score, issue_score, pr_score,
            contributor_score, bus_factor_score,
            data_days_available, computed_at
        FROM {_TABLE}
        {where}
        ORDER BY CAST(health_score AS DOUBLE) {direction}
        {limit_clause}
    """
    try:
        rows = query_databricks(sql)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return [_cast(r) for r in rows]


@router.get("/health-scores/{org}/{repo}", response_model=HealthScore)
def get_project(org: str, repo: str) -> HealthScore:
    if not _SAFE_NAME.match(org) or not _SAFE_NAME.match(repo):
        raise HTTPException(status_code=400, detail="Invalid org or repo name")

    repo_full_name = f"{org}/{repo}"
    sql = f"""
        SELECT
            repo_full_name, org_name, health_score,
            commit_score, issue_score, pr_score,
            contributor_score, bus_factor_score,
            data_days_available, computed_at
        FROM {_TABLE}
        WHERE repo_full_name = '{repo_full_name}'
        LIMIT 1
    """
    try:
        rows = query_databricks(sql)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    if not rows:
        raise HTTPException(status_code=404, detail=f"{repo_full_name} not found")

    return _cast(rows[0])


@router.get("/summary", response_model=Summary)
def get_summary() -> Summary:
    sql = f"""
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN CAST(health_score AS DOUBLE) < 5.0 THEN 1 ELSE 0 END) AS critical,
            SUM(CASE WHEN CAST(health_score AS DOUBLE) >= 5.0
                      AND CAST(health_score AS DOUBLE) < 7.0 THEN 1 ELSE 0 END) AS warning,
            SUM(CASE WHEN CAST(health_score AS DOUBLE) >= 7.0 THEN 1 ELSE 0 END) AS healthy,
            AVG(CAST(health_score AS DOUBLE)) AS avg_score,
            MAX(computed_at) AS last_pipeline_run
        FROM {_TABLE}
    """
    try:
        rows = query_databricks(sql)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    row = rows[0] if rows else {}

    def _i(v: object) -> int:
        try:
            return int(float(v)) if v is not None else 0
        except (ValueError, TypeError):
            return 0

    def _f(v: object) -> float:
        try:
            return round(float(v), 2) if v is not None else 0.0
        except (ValueError, TypeError):
            return 0.0

    last_agent_run: Optional[str] = None
    assessed_repos: list[str] = []
    projects_assessed = 0

    if _REPORTS_DIR.exists():
        reports = sorted(_REPORTS_DIR.glob("risk_report_*.md"), reverse=True)
        if reports:
            latest = reports[0]
            # Parse timestamp from filename: risk_report_2026-04-12T19-36-29.md
            stem = latest.stem.replace("risk_report_", "")
            last_agent_run = stem.replace("T", " ").replace("-", ":", 2)
            try:
                content = latest.read_text(encoding="utf-8", errors="replace")
                assessed_repos = re.findall(r"^### (.+)$", content, re.MULTILINE)
                projects_assessed = len(assessed_repos)
            except OSError:
                pass

    return Summary(
        total_projects=_i(row.get("total")),
        critical_count=_i(row.get("critical")),
        warning_count=_i(row.get("warning")),
        healthy_count=_i(row.get("healthy")),
        avg_health_score=_f(row.get("avg_score")),
        last_pipeline_run=row.get("last_pipeline_run"),
        last_agent_run=last_agent_run,
        projects_assessed_count=projects_assessed,
        assessed_repos=assessed_repos,
    )
