from __future__ import annotations

import re
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from api.models import ReportMeta

router = APIRouter()

_REPORTS_DIR = _ROOT / "docs" / "reports"
_SAFE_FILENAME = re.compile(r"^risk_report_[\w\-:.]+\.md$")


def _parse_meta(path: Path) -> ReportMeta:
    stem = path.stem.replace("risk_report_", "")
    # stem looks like: 2026-04-12T19-36-29
    # Convert to readable: 2026-04-12 19:36:29
    timestamp = stem
    parts = stem.split("T")
    if len(parts) == 2:
        date_part = parts[0]
        time_part = parts[1].replace("-", ":")
        timestamp = f"{date_part} {time_part}"

    project_count = 0
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
        project_count = len(re.findall(r"^### .+", content, re.MULTILINE))
    except OSError:
        pass

    size_kb = round(path.stat().st_size / 1024, 1)

    return ReportMeta(
        filename=path.name,
        timestamp=timestamp,
        project_count=project_count,
        file_size_kb=size_kb,
    )


@router.get("/reports", response_model=list[ReportMeta])
def list_reports() -> list[ReportMeta]:
    if not _REPORTS_DIR.exists():
        return []

    files = sorted(_REPORTS_DIR.glob("risk_report_*.md"), reverse=True)
    return [_parse_meta(f) for f in files]


@router.get("/reports/{filename}", response_class=PlainTextResponse)
def get_report(filename: str) -> str:
    if not _SAFE_FILENAME.match(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")

    path = (_REPORTS_DIR / filename).resolve()
    if not str(path).startswith(str(_REPORTS_DIR.resolve())):
        raise HTTPException(status_code=400, detail="Invalid path")

    if not path.exists():
        raise HTTPException(status_code=404, detail="Report not found")

    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
