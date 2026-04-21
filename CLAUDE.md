# CLAUDE.md — OSS Dependency Risk Agent

Monitors 200 OSS projects for health deterioration: GitHub Archive events → AWS S3 (Bronze) → Databricks PySpark (Silver) → dbt (Gold) → 5-node LangGraph agent (Claude Sonnet) → Streamlit dashboard. All 6 phases complete.

---

## Standing Instructions

- **Windows / PowerShell** — all shell commands must use PowerShell syntax
- **`--dry-run` flag** — any script that writes to S3 or an external service must support it

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

---

## Phase 8 — Dependency Discovery (Complete)
**Files built:**
- `ingestion/discovery/__init__.py` — Package stub.
- `ingestion/discovery/manifest_parser.py` — Parses 5 ecosystems: `requirements.txt`
  (pip), `package.json` (npm), `go.mod`, `pom.xml` (Maven), `Cargo.toml` (Rust).
  Detection order: exact filename → file extension suffix (`.txt`, `.json`, `.xml`).
  This allows non-standard names like `test_requirements.txt` or `base.txt` to
  resolve correctly via the `.txt` suffix fallback.
- `ingestion/discovery/github_resolver.py` — Three-tier resolution per package:
  (1) hardcoded `_KNOWN_MAPPINGS` dict (highest priority, no API call),
  (2) ecosystem-native registry API (PyPI → `project_urls`, npm → `repository.url`,
  crates.io, Go module path parsing with `golang.org/x/` / `k8s.io/` remaps),
  (3) GitHub Search fallback (confidence: low, rate-limited to 2.5s between calls).
  Results cached in `config/resolution_cache.json`. Lookup is case-insensitive.
- `ingestion/discovery/project_registry.py` — Manages a `_DISCOVERED` block at
  the bottom of `project_list.py`, kept separate from curated lists. Auto-patches
  the `PROJECTS` concatenation to include `_DISCOVERED`. Supports add, list, remove.
  Path fix: uses `parents[1]` (the `ingestion/` directory) not `parents[2]`.
- `scripts/discover_dependencies.py` — CLI with `--manifest FILE` (repeatable),
  `--dry-run`, `--list`, `--remove ORG/REPO`, `--debug`. Prints resolution summary
  matching spec output. Unresolved packages appended to `docs/unresolved.txt`.

**Known-correct mapping dict** (bypasses all API calls):
```
pinecone    -> pinecone-io/pinecone-python-client
pandas      -> pandas-dev/pandas
numpy       -> numpy/numpy
scipy       -> scipy/scipy
matplotlib  -> matplotlib/matplotlib
sqlalchemy  -> sqlalchemy/sqlalchemy
fastapi     -> tiangolo/fastapi
celery      -> celery/celery
redis       -> redis/redis-py
httpx       -> encode/httpx
pytest      -> pytest-dev/pytest
openai      -> openai/openai-python
```

**Bugs fixed during build:**
- `parents[2]` in `project_registry.py` resolved to project root, skipping
  `ingestion/`. Fixed to `parents[1]`.
- `\d` in `discover_dependencies.py` docstring raised `SyntaxWarning` (invalid
  escape sequence in Python 3.12+). Fixed by using forward slashes in usage examples.
- Exact filename match rejected `test_requirements.txt`. Fixed by adding suffix
  fallback (`.txt` → pip parser) after exact match fails.
- Cache must be cleared (`config/resolution_cache.json`) if known-correct mappings
  are added after a bad resolution was already cached.

---

## Phase 7 — Pinecone RAG Layer (Complete)
**Files built:**
- `embeddings/indexer.py` — Parses `docs/reports/risk_report_*.md` by splitting on
  `## Section` then `### org/repo` headers. Extracts health score, risk score,
  recommendation, and assessment text per project. Embeds with Pinecone's hosted
  `llama-text-embed-v2` (input_type: `passage`). Upserts in batches of 50 to the
  `oss-health` index, namespace `oss-deps`. Vector ID is
  `sha256(repo_full_name|report_file)[:40]` for idempotent re-indexing.
  `_get_or_create_index()` auto-creates the index (dim=1024, cosine, serverless
  AWS us-east-1) if it doesn't exist — handles expired trials or fresh setups.
  Empty assessment text falls back to a metadata-based sentence rather than
  skipping the record entirely.
- `embeddings/searcher.py` — Embeds query with `llama-text-embed-v2`
  (input_type: `query`), queries Pinecone with optional `$eq` metadata filter on
  `recommendation`. Returns ranked dicts with similarity_score, excerpt, health_score,
  report_date. `index_stats()` returns namespace vector count for the UI health check.
  Guards against missing index gracefully.
- `scripts/run_indexer.py` — CLI: `--all` indexes every report, default indexes
  latest only, `--dry-run` parses without touching Pinecone, `--debug` sets
  logging to DEBUG to inspect parsed record content.
- `frontend/pages/05_search.py` — Search bar + recommendation filter (All /
  REPLACE / UPGRADE / MONITOR) + top-k slider. Index vector count shown in sidebar.
  "Run agent first" message when index is empty. Results show similarity score,
  health score badge, action badge with color, and excerpt with colored left-border.
  Example query buttons on landing state.
- `scripts/daily_run.ps1` — One-command daily pipeline: ingestion → silver →
  dbt run+test → agent (limit 10) → indexer.
- `scripts/run_agent.py` (updated) — Auto-calls `index_latest_report()` after
  every non-dry-run when `PINECONE_API_KEY` is set. Failure is non-fatal (warning).

**Key decisions:**
- Index auto-creation uses dim=1024 to match `llama-text-embed-v2` default output.
  Metric is cosine (standard for semantic similarity on normalised embeddings).
- Markdown parser switched from regex substitution to line-by-line filtering to
  avoid Windows CRLF edge case: `^---$` regex doesn't match `---\r`, but
  `stripped == "---"` does.
- Empty assessment text uses a metadata fallback sentence rather than skipping —
  keeps every assessed project searchable by name and recommendation even when
  Claude's response was not captured in the report.
- Vector IDs are deterministic hashes so re-indexing the same report is a
  no-op upsert, not a duplicate insert.

**Bugs fixed:**
- Pinecone index not found (404) on first run — fixed by `_get_or_create_index()`.
- Empty string embed rejected (400) — fixed by fallback text + line-by-line parser.

**Index status:** `oss-health` index, namespace `oss-deps`, 2+ vectors from
`risk_report_2026-04-12T19-36-29.md`.

---



---

## Non-Obvious Gotchas

These caused real bugs and will again if forgotten:

**Databricks**
- Secret scope key names use **underscores** — `aws_access_key_id`, not `aws-access-key-id`. Hyphens cause silent `dbutils.secrets.get()` failures that fall through to `AnonymousAWSCredentials` and produce S3 403 errors with no obvious cause.
- Statement Execution `wait_timeout` must be `"0s"` or between `"5s"`–`"50s"`. `"60s"` raises a validation error.
- Job creation via SDK — do not pass raw dicts to `sdk.jobs.create()`. Use `sdk.api_client.do("POST", "/api/2.1/jobs/create", body=config)` to avoid `AttributeError: 'dict' has no attribute 'as_dict'`.
- Serverless clusters do not support `.cache()`. Materialise DataFrames to a temp Delta table before counting or merging.

**dbt**
- Inject `DBT_PROFILES_DIR` as a subprocess env var — do not use `--profiles-dir` as a CLI flag (dbt 1.11 doesn't accept it as a global flag before the subcommand).
- Resolve the dbt executable as `Path(sys.executable).parent / "dbt"`, not the string `"dbt"` — the venv is not on the subprocess PATH on Windows.
- Never write `{{ ref('...') }}` inside a SQL comment. dbt's ref extractor runs regex over the entire file including comments and will create phantom dependencies.
- Generic test arguments must be nested under `arguments:` in dbt 1.11+.

**Windows / Streamlit**
- Use `-` not `:` in any timestamp written to a filename — colons are invalid on Windows.
- Run the agent as a subprocess from the Run Agent page, not inline. LangGraph's internal threading conflicts with Streamlit's rerun model when called directly.

---

## Build Phase Status

| Phase | Description | Status |
|---|---|---|
| 0 | Environment setup, scaffold, credentials | ✅ Complete |
| 1 | GitHub Archive → S3 ingestion | ✅ Complete |
| 2 | Databricks Bronze → Silver | ✅ Complete |
| 3 | dbt Gold layer — health metrics | ✅ Complete |
| 4 | LangGraph agent — 5-node workflow | ✅ Complete |
| 5 | Streamlit UI | ✅ Complete |
| 6 | Polish, README, architecture diagram | ✅ Complete |
| 7 | Pinecone RAG layer + daily pipeline | ✅ Complete |
| 8 | Dependency discovery from manifests | ✅ Complete |
| 9 | UI/UX overhaul + feature additions  | ✅ Complete |
| 10 | Next.js + FastAPI frontend | ✅ Complete |


---

## Phase 9 — UI/UX Overhaul (Complete)

**Files updated:** `frontend/app.py`, `frontend/pages/01_health_dashboard.py`,
`frontend/pages/02_project_detail.py`, `frontend/pages/03_run_agent.py`,
`frontend/pages/04_reports.py`, `frontend/pages/05_search.py`,
`frontend/components/health_chart.py`, `frontend/components/metrics_card.py`

**Key changes per page:**

- **Home** — Two-column top-5 layout (at-risk left, healthiest right); 6 summary
  cards including AI Assessed count; pipeline + agent run timestamps from real
  sources (`computed_at` column + report filename); "View →" buttons navigate to
  Project Detail via `st.session_state["nav_repo"]` + `st.switch_page`.

- **Health Dashboard** — Top-of-page project search box; Status (🔴/🟡/🟢) dot
  column; AI Assessed (✓) column built by scanning all report files; paginated
  25 rows/page with page number input; org/category + status + min-score sidebar
  filters; Export CSV; row selection via `st.dataframe(on_select="rerun")` with
  "View Project →" button; full distribution bar chart collapsed in expander.

- **Project Detail** — Reads `nav_repo` from session state for cross-page
  navigation; health badge + GitHub link button in header; 2×3 metric grid using
  new `render_score_card`; terminal-style AI assessment box (dark `#0d1117` bg,
  mac window chrome, `Courier New` monospace, `html.escape` safe); last-assessed
  timestamp from report filename; "Open Agent Control Room" button when no
  assessment found.

- **Agent Control Room** — Renamed from "Run Agent"; `--min-score` / `--max-score`
  sliders in sidebar, passed to `scripts/run_agent.py`; pipeline steps fixed to
  Monitor → Investigate → Synthesize → Recommend → Deliver (5 distinct, no
  duplicate); last-run summary parsed from most recent report (counts REPLACE /
  UPGRADE / MONITOR); post-run "View Report →" link.

- **Reports** — Sidebar labels formatted `YYYY-MM-DD HH:MM (N projects)` by
  counting `### ` headers; Print button via `streamlit.components.v1.html` +
  `window.parent.print()`; Export HTML button; recommendation-type jump filter
  (REPLACE / UPGRADE / MONITOR) that extracts matching sections; report comparison
  — select two reports, parse recommendations per project, show diff table with
  ⚠ changed marker; `compare_idx` defaulted to `None` to avoid scoping bugs.

- **Semantic Search** — Centered search bar in a 1:6:1 column layout; 5 example
  prompt pills auto-submit via `st.session_state["_auto_search"] = True` + rerun;
  "View Detail →" per result navigates to Project Detail; "Projects indexed: N"
  label; dead pill_html string removed.

- **Components** — Added `status_dot()` to `metrics_card.py` and `render_score_card()`
  for grid layout on Project Detail; consistent colour palette
  (`#27ae60` / `#e67e22` / `#c0392b`) across all components; `health_chart.py`
  updated colour palette and default `month_col`.

**Navigation pattern:** Pages set `st.session_state["nav_repo"] = repo` then call
`st.switch_page("pages/02_project_detail.py")`. Project Detail reads and pops
`nav_repo` before rendering the selectbox to pre-select the right project.

---

## Phase 10 — Next.js + FastAPI Frontend (Complete)

Streamlit replaced with a FastAPI REST API (`api/`) + Next.js 14 App Router frontend
(`frontend-next/`). Streamlit files kept but deprecated.

**Files built:**
- `api/__init__.py`, `api/main.py` — FastAPI app with CORS for `localhost:3000`;
  fires a `SELECT 1` warmup query in a background thread on startup to pre-warm
  the Databricks warehouse before the first user request.
- `api/models.py` — Pydantic models for all request/response shapes.
- `api/routers/health.py` — `GET /api/health-scores`, `GET /api/health-scores/{org}/{repo}`,
  `GET /api/summary`. Summary reads report files for `last_agent_run` and
  `assessed_repos`; all Databricks values cast from strings at the API layer.
- `api/routers/reports.py` — `GET /api/reports`, `GET /api/reports/{filename}`.
  Filename validated against `^risk_report_[\w\-:.]+\.md$`; path traversal
  blocked by resolving and comparing to reports dir.
- `api/routers/search.py` — `POST /api/search` proxies to `embeddings/searcher.py`.
- `api/routers/agent.py` — `POST /api/agent/run` launches `scripts/run_agent.py`
  as a subprocess; `GET /api/agent/status/{run_id}` polls `process.poll()` and
  diffs report file lists to find the new report on completion.
- `scripts/run_api.py` — entry point; uses `--reload-dir api` to scope watchfiles
  to `api/` only (watching `.venv` blocks the event loop on Windows).
- `scripts/run_dev.ps1` — starts both servers in separate PowerShell windows.
- `frontend-next/` — Next.js 14 App Router, TypeScript, Tailwind only (no UI libs).
  Pages: `/` (home), `/dashboard`, `/projects/[org]/[repo]`, `/search`,
  `/reports`, `/agent`. Shared: `Sidebar`, `HealthBadge`, `LoadingSpinner`.
  All API calls in `lib/api.ts` with 120s timeout and human-readable error messages.

**Run both servers:**
```powershell
# Backend (from project root, venv active)
python scripts/run_api.py

# Frontend (in a second terminal)
cd frontend-next
npm run dev
```

Or together: `.\scripts\run_dev.ps1`

**Non-obvious gotchas fixed during build:**
- `next.config.ts` / `tailwind.config.ts` are not supported in Next.js 14 — must
  use `.js` with `module.exports`.
- `uvicorn --reload` without `--reload-dir` watches the entire project root
  including `.venv`. On Windows this blocks the event loop entirely: the server
  accepts TCP connections but never sends HTTP responses. Fix: `--reload-dir api`.
- `frontend-next/node_modules` must be in `.gitignore`. If accidentally committed,
  rewrite history with `git reset --soft <last-clean-commit>` + force push — a
  `git rm --cached` commit alone still leaves the blob in history and GitHub rejects
  the push.
- Databricks cold-start: the warehouse shows "Running" in the console but the first
  query still takes 60–90 s. The startup warmup thread handles this. Frontend
  timeout is 120 s; spinner shows a hint after 6 s.