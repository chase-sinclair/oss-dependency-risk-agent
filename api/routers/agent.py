from __future__ import annotations

import re
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from api.models import AgentRunRequest, AgentRunResponse, AgentRunSummary, AgentStatus

router = APIRouter()

_REPORTS_DIR = _ROOT / "docs" / "reports"

_runs: dict[str, dict] = {}
_lock = threading.Lock()


def _report_files() -> set[str]:
    if not _REPORTS_DIR.exists():
        return set()
    return {p.name for p in _REPORTS_DIR.glob("risk_report_*.md")}


def _parse_summary(filename: str) -> AgentRunSummary:
    path = _REPORTS_DIR / filename
    assessed = replace_count = upgrade_count = monitor_count = 0
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
        assessed = len(re.findall(r"^### .+", content, re.MULTILINE))
        replace_count = content.upper().count("REPLACE")
        upgrade_count = content.upper().count("UPGRADE")
        monitor_count = content.upper().count("MONITOR")
    except OSError:
        pass
    return AgentRunSummary(
        assessed=assessed,
        replace_count=replace_count,
        upgrade_count=upgrade_count,
        monitor_count=monitor_count,
    )


@router.post("/agent/run", response_model=AgentRunResponse)
def run_agent(body: AgentRunRequest) -> AgentRunResponse:
    run_id = str(uuid.uuid4())

    cmd: list[str] = [sys.executable, str(_ROOT / "scripts" / "run_agent.py")]
    if body.dry_run:
        cmd.append("--dry-run")
    if body.limit is not None:
        cmd.extend(["--limit", str(body.limit)])
    if body.min_score is not None:
        cmd.extend(["--min-score", str(body.min_score)])
    if body.max_score is not None:
        cmd.extend(["--max-score", str(body.max_score)])

    reports_before = _report_files()

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to start agent: {exc}")

    with _lock:
        _runs[run_id] = {
            "process": proc,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "reports_before": reports_before,
        }

    return AgentRunResponse(status="started", run_id=run_id)


@router.get("/agent/status/{run_id}", response_model=AgentStatus)
def agent_status(run_id: str) -> AgentStatus:
    with _lock:
        run = _runs.get(run_id)

    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    proc: subprocess.Popen = run["process"]
    exit_code: Optional[int] = proc.poll()

    if exit_code is None:
        return AgentStatus(status="running")

    if exit_code != 0:
        return AgentStatus(status="failed")

    # Find any new report file created during this run
    new_files = _report_files() - run["reports_before"]
    report_filename: Optional[str] = None
    if new_files:
        report_filename = sorted(new_files)[-1]

    summary = _parse_summary(report_filename) if report_filename else None

    return AgentStatus(
        status="complete",
        summary=summary,
        report_filename=report_filename,
    )
