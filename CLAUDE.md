# CLAUDE.md — OSS Dependency Risk Agent

Monitors 800+ OSS projects for health deterioration. Pipeline: GitHub Archive events → AWS S3 (Bronze) → Databricks PySpark (Silver) → dbt (Gold) → 5-node LangGraph agent (Claude Sonnet) → FastAPI + Next.js frontend.

---

## Standing Instructions

- **Windows / PowerShell** — all shell commands must use PowerShell syntax
- **`--dry-run` flag** — any script that writes to S3 or an external service must support it

---

## Running the Project

```powershell
# Start both servers together
.\scripts\run_dev.ps1

# Or individually (venv must be active):
python scripts/run_api.py          # FastAPI on :8000
cd frontend-next && npm run dev    # Next.js on :3000
```

---

## Key Connections

| Resource | Value |
|---|---|
| Databricks workspace | `https://dbc-92208bf2-316f.cloud.databricks.com` |
| SQL Warehouse HTTP path | `/sql/1.0/warehouses/11bd1ba7445b1a22` |
| Catalog / Schema | `workspace` / `default` |
| S3 Bronze bucket | `oss-risk-agent-bronze` (us-east-1) |
| Silver table | `workspace.default.silver_github_events` |
| Gold table | `workspace.default.gold_health_scores` |
| Pinecone index | `oss-health`, namespace `oss-deps` |

---

## Architecture

```
ingestion/github_archive/    GitHub Archive → S3 Bronze ingestion
ingestion/discovery/         Manifest parsing + GitHub package resolver
databricks/                  PySpark Bronze → Silver jobs
dbt/                         Silver → Gold health score models
agent/                       5-node LangGraph workflow (Claude Sonnet)
embeddings/                  Pinecone RAG indexer and searcher
api/                         FastAPI REST backend
  routers/health.py          GET /api/health-scores, /api/summary
  routers/reports.py         GET /api/reports, /api/reports/{filename}
  routers/search.py          POST /api/search
  routers/agent.py           POST /api/agent/run, GET /api/agent/status/{id}
  routers/onboard.py         POST /api/onboard (manifest file upload)
frontend-next/               Next.js 14 App Router frontend
  app/                       Pages: /, /dashboard, /projects/[org]/[repo],
                             /search, /reports, /agent, /onboard
scripts/
  run_api.py                 FastAPI entry point
  run_agent.py               Agent CLI (--dry-run, --limit, --min-score, --max-score)
  run_indexer.py             Pinecone indexer CLI
  daily_run.ps1              Full pipeline: ingest → silver → dbt → agent → index
  discover_dependencies.py   Manifest → GitHub resolver CLI
```

---

## Non-Obvious Gotchas

**Databricks**
- Secret scope key names use **underscores** — `aws_access_key_id`, not `aws-access-key-id`. Hyphens cause silent failures that fall through to anonymous credentials and S3 403 errors.
- Statement Execution `wait_timeout` must be `"0s"` or between `"5s"`–`"50s"`. `"60s"` raises a validation error.
- Do not pass raw dicts to `sdk.jobs.create()`. Use `sdk.api_client.do("POST", "/api/2.1/jobs/create", body=config)`.
- Serverless clusters do not support `.cache()`. Materialise DataFrames to a temp Delta table first.
- Cold-start: warehouse takes 60–90s on first query. The API fires a warmup `SELECT 1` in a background thread at startup.

**dbt**
- Inject `DBT_PROFILES_DIR` as a subprocess env var — `--profiles-dir` is not accepted as a global flag in dbt 1.11+.
- Resolve dbt as `Path(sys.executable).parent / "dbt"` — the venv is not on the subprocess PATH on Windows.
- Never write `{{ ref('...') }}` inside a SQL comment — dbt's ref extractor scans comments and creates phantom dependencies.

**FastAPI / Next.js**
- File uploads (`UploadFile`) require `python-multipart` to be installed.
- `uvicorn --reload` without `--reload-dir api` watches the entire project including `.venv`, which blocks the event loop on Windows.
- `next.config.ts` / `tailwind.config.ts` are not supported in Next.js 14 — use `.js` with `module.exports`.

**Dependency Discovery**
- Resolution cache lives at `config/resolution_cache.json`. Clear it if `_KNOWN_MAPPINGS` in `github_resolver.py` are updated after a bad resolution was cached.
- Manifest parser falls back to file extension (`.txt` → pip) when the exact filename doesn't match, so `test_requirements.txt` resolves correctly.

**Windows**
- Use `-` not `:` in timestamps written to filenames — colons are invalid on Windows.

---

## Project Registry

`ingestion/github_archive/project_list.py` — 800+ monitored projects across 15 categories. Curated lists are prefixed `_CATEGORY`; auto-discovered projects append to `_DISCOVERED` at the bottom. The `PROJECTS` master list concatenates all of them.

To add projects manually, edit the appropriate category list. To add via manifest:
```powershell
python scripts/discover_dependencies.py --manifest path/to/requirements.txt
```

---

## Changelog

### 2026-04-23
- Expanded `project_list.py` from ~200 to 800 unique projects across 15 categories: added `_PYTHON_LIBS` (110), `_JAVASCRIPT_LIBS` (120), `_GO_LIBS` (93), `_RUST_LIBS` (73), and extended all existing categories.
- Fixed API startup crash: `python-multipart` was missing; required by FastAPI for `UploadFile` routes.
- Added `scripts/validate_project_list.py` — runs 6 structural checks on `project_list.py`: duplicate org/repo pairs, malformed dicts, empty values, category mismatches, API function count consistency, and master list completeness. Fixed 6 cross-category duplicates (`pytorch-lightning`, `biome`, `bubbletea`, `nats.go`, `goprocmgr`, `nickel`) found during validation. All checks pass.

### 2026-04-23 (continued)
- Added `has_push_data` boolean column to `gold_health_scores` — `true` only when the repo has at least one PushEvent in Silver. Repos with only Issues/PR events score commit and contributor metrics at the 5.0 neutral fallback; this flag surfaces that distinction.
- Surfaced `has_push_data` in the Project Detail page as an amber "No push data" badge on the Commit Frequency and Contributor Diversity metric cards only (muted, not red — data gap not a failure).
- Passed `has_push_data` into the LangGraph synthesis prompt — Claude now emits a data coverage notice and annotates the two affected metric rows when the flag is false, preventing it from treating 5.0 fallbacks as real activity signals.
- Fixed `.env` inline-comment bug: values like `DATABRICKS_HOST=https://... # comment` caused the comment text to be included in the env var value, producing an `HTTPSConnectionPool(host='dbc-...   ', ...)` foreign-host error. Stripped all inline comments from `.env` — comments must be on their own line.
- Added `scripts/run_gold_models.py` — runs all 7 dbt models (stg + 4 int views + 2 gold tables) directly via the Databricks SDK REST API, bypassing `dbt run` which uses `databricks-sql-connector` (Thrift) and cannot open a session against this warehouse. Supports `--select model1 model2` and `--dry-run`. Updated `daily_run.ps1` to call this script instead of `run_dbt.py --run --test`.
- Diagnosed Silver coverage gap: boto/boto3 has no PushEvents in Silver (only IssuesEvent), confirming `has_push_data=false` and `commit_score/contributor_score=5.0` are correct fallbacks, not bugs. pytest-dev/pytest has real PushEvent data; its health_score=3.7 is accurate (bus_factor_risk=1.0).

### 2026-04-22
- Added `/onboard` page (`frontend-next/app/onboard/page.tsx`) — drag-and-drop manifest upload, POST to `/api/onboard`, results in three categories: READY (already monitored), ADDED (newly registered), UNRESOLVED.
- Added `api/routers/onboard.py` — parses manifest, resolves packages to GitHub repos, fetches health scores from Databricks, registers new projects.
- Fixed Home page KPI sub-labels (Critical Risks now shows % of portfolio; Avg Health shows "N of M AI analyzed").
- Fixed AI Risk Assessment rendering raw markdown on project detail page — now renders bold, bullets, code, and dividers.
- Fixed Intel Reports refresh: split loading state so the refresh button no longer triggers the full-page spinner.
- Fixed ISO timestamp display — dates now render as "Apr 14, 2026 18:07" throughout.
- Redesigned Semantic Search page with two-mode layout: centered hero on landing, full results view post-search.
