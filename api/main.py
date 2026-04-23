from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv

load_dotenv()

import logging
import threading

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import agent, health, onboard, reports, search

logger = logging.getLogger(__name__)

app = FastAPI(title="OSS Risk Agent API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(reports.router, prefix="/api", tags=["reports"])
app.include_router(search.router, prefix="/api", tags=["search"])
app.include_router(agent.router, prefix="/api", tags=["agent"])
app.include_router(onboard.router, prefix="/api", tags=["onboard"])


def _warmup_databricks() -> None:
    try:
        from agent.tools.databricks_query import query_databricks
        query_databricks("SELECT 1")
        logger.info("Databricks warmup query succeeded.")
    except Exception as exc:
        logger.warning("Databricks warmup failed (non-fatal): %s", exc)


@app.on_event("startup")
def startup_event() -> None:
    threading.Thread(target=_warmup_databricks, daemon=True).start()


@app.get("/api/ping")
def ping() -> dict[str, str]:
    return {"status": "ok"}
