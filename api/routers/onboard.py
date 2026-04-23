from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from api.models import AddedProject, OnboardResponse, ReadyProject, UnresolvedPackage

router = APIRouter()

_TABLE = "workspace.default.gold_health_scores"
_SAFE_REPO = re.compile(r"^[a-zA-Z0-9._\-]+/[a-zA-Z0-9._\-]+$")


def _fetch_health_scores(full_names: list[str]) -> dict[str, Optional[float]]:
    """Return {repo_full_name: health_score} for the given repos. Non-fatal on error."""
    if not full_names:
        return {}
    safe = [n for n in full_names if _SAFE_REPO.match(n)]
    if not safe:
        return {}
    try:
        from agent.tools.databricks_query import query_databricks
        in_clause = ", ".join(f"'{n}'" for n in safe)
        sql = f"""
            SELECT repo_full_name, health_score
            FROM {_TABLE}
            WHERE repo_full_name IN ({in_clause})
        """
        rows = query_databricks(sql)
        result: dict[str, Optional[float]] = {}
        for row in rows:
            try:
                result[row["repo_full_name"]] = float(row["health_score"])
            except (TypeError, ValueError):
                result[row["repo_full_name"]] = None
        return result
    except Exception:
        return {}


@router.post("/onboard", response_model=OnboardResponse)
async def onboard_manifest(file: UploadFile = File(...)) -> OnboardResponse:
    from ingestion.discovery.github_resolver import _load_cache, _save_cache, resolve_package
    from ingestion.discovery.manifest_parser import parse_manifest
    from ingestion.discovery.project_registry import add_projects, get_current_projects

    filename = Path(file.filename or "manifest.txt").name
    content = await file.read()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir) / filename
        tmp_path.write_bytes(content)
        try:
            packages = parse_manifest(tmp_path)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    if not packages:
        return OnboardResponse(
            parsed_count=0,
            ready_projects=[],
            added_projects=[],
            unresolved_packages=[],
        )

    existing = get_current_projects()
    cache = _load_cache()

    # Collect per-category
    already_monitored: list[dict] = []   # {org, repo, package_name, ecosystem}
    to_add: list[dict] = []              # for project_registry
    added_meta: list[tuple] = []        # (org, repo, package_name, ecosystem, confidence)
    unresolved: list[UnresolvedPackage] = []
    seen: set[str] = set()

    for pkg in packages:
        name = pkg["name"]
        ecosystem = pkg["ecosystem"]
        result = resolve_package(name, ecosystem, cache)

        if result is None:
            unresolved.append(UnresolvedPackage(name=name, reason="not found"))
            continue

        full_name = f"{result.org}/{result.repo}"

        if full_name in existing:
            already_monitored.append({
                "org": result.org, "repo": result.repo,
                "package_name": name, "ecosystem": ecosystem,
            })
            continue

        if full_name in seen:
            continue
        seen.add(full_name)

        added_meta.append((result.org, result.repo, name, ecosystem, result.confidence))
        to_add.append({
            "org": result.org, "repo": result.repo,
            "category": "discovered",
            "description": f"Discovered from manifest ({ecosystem} package: {name})",
        })

    _save_cache(cache)
    add_projects(to_add)

    # Fetch health scores for already-monitored repos
    monitored_full_names = [f"{p['org']}/{p['repo']}" for p in already_monitored]
    score_map = _fetch_health_scores(monitored_full_names)

    ready_projects = [
        ReadyProject(
            org=p["org"], repo=p["repo"],
            package_name=p["package_name"], ecosystem=p["ecosystem"],
            health_score=score_map.get(f"{p['org']}/{p['repo']}"),
        )
        for p in already_monitored
    ]

    added_projects = [
        AddedProject(org=org, repo=repo, package_name=pkg_name, ecosystem=eco, confidence=conf)
        for org, repo, pkg_name, eco, conf in added_meta
    ]

    return OnboardResponse(
        parsed_count=len(packages),
        ready_projects=ready_projects,
        added_projects=added_projects,
        unresolved_packages=unresolved,
    )
