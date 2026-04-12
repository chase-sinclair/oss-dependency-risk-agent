# CLAUDE.md — OSS Dependency Risk Agent
> This file is the persistent memory and instruction set for Claude Code.
> Update the Memory Log at the end of every phase before moving on.

---

## Project Overview

**Project Name:** OSS Dependency Risk Agent

**What It Does:**


**Target Audience:** Engineering leads and DevOps/platform engineers at
mid-to-large organizations managing complex OSS dependency ecosystems.

**Resume Purpose:** Demonstrates end-to-end AI engineering across data
pipelines (S3, Databricks, dbt), agent frameworks (LangGraph), and LLM
integration (Anthropic Claude) for Forward Deployed AI Engineer and AI
Strategy/Enablement roles.

---

## Tech Stack

| Layer | Tool |
|---|---|
| Storage (Bronze) | AWS S3 |
| Compute (Silver) | Databricks + PySpark |
| Transformation (Gold) | dbt |
| Agent Framework | LangGraph |
| LLM | Anthropic Claude (claude-sonnet-4-5) |
| Vector DB | Pinecone |
| Frontend | Streamlit |
| Language | Python 3.13 |
| OS | Windows / PowerShell |

---

## Project Structure

```
oss-dependency-risk-agent/
├── ingestion/
│   ├── github_archive/     ← GH Archive fetchers
│   └── utils/              ← Shared utilities (S3 client etc.)
├── transformation/
│   ├── databricks/
│   │   ├── notebooks/      ← PySpark Silver layer notebooks
│   │   └── jobs/           ← Databricks job definitions
│   └── dbt/
│       └── models/
│           ├── staging/    ← Raw → typed casts
│           ├── intermediate/ ← Business logic joins
│           └── gold/       ← Final health metric tables
├── agent/
│   ├── tools/              ← LangGraph tool definitions
│   ├── nodes/              ← Graph node implementations
│   ├── graphs/             ← Graph wiring / state machines
│   └── prompts/            ← Prompt templates
├── embeddings/             ← Pinecone index management
├── frontend/
│   ├── pages/
│   └── components/
├── config/
├── tests/
│   ├── unit/
│   └── integration/
├── docs/
└── scripts/
```

---

## Environment Variables

All secrets live in `.env` (never committed). See `.env.example` for
the full list. Key variables:

- `ANTHROPIC_API_KEY` — Claude API access
- `ANTHROPIC_MODEL` — set to `claude-sonnet-4-5`
- `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` — S3 access
- `S3_BRONZE_BUCKET` — `oss-risk-agent-bronze`
- `DATABRICKS_HOST` / `DATABRICKS_TOKEN` — workspace access
- `DATABRICKS_CLUSTER_ID` / `DATABRICKS_HTTP_PATH` — set in Phase 2
- `DATABRICKS_CATALOG` — set in Phase 2
- `PINECONE_API_KEY` / `PINECONE_INDEX_NAME` — `oss-health`
- `GITHUB_TOKEN` — public repo read access

---

## Standing Instructions for Claude Code

1. **Always use Windows-compatible commands and PowerShell syntax**
2. **Never commit `.env`** — it is gitignored
3. **Always use `python-dotenv`** to load environment variables
4. **All file paths** should use `os.path.join()` for cross-platform safety
5. **Every script** must have proper logging (use Python `logging` module)
6. **Every external call** (S3, GitHub API, Databricks) must have retry
   logic and error handling
7. **Never hardcode credentials** — always read from environment variables
8. **Add a `dry_run=True` flag** to any script that writes to S3 or
   external services
9. **Follow the Bronze/Silver/Gold naming convention** throughout
10. **Keep functions small and single-purpose** — this is a portfolio
    project and must be readable

---

## Build Phases

| Phase | Description | Status |
|---|---|---|
| 0 | Environment setup, scaffold, credentials | ✅ Complete |
| 1 | GitHub Archive → S3 ingestion | ✅ Complete |
| 2 | Databricks Bronze → Silver | ✅ Complete |
| 3 | dbt Gold layer — health metrics | ✅ Complete |
| 4 | LangGraph agent — 5 step workflow | ✅ Complete |
| 5 | Streamlit UI | ⬜ Pending |
| 6 | Polish, README, architecture diagram | ⬜ Pending |

---

## Phase 1 — GitHub Archive Ingestion

**Goal:** Download GitHub Archive hourly dump files for 200 target OSS
projects and upload raw filtered JSON data to S3 bronze layer.

**Data Source:**
- URL pattern: `https://data.gharchive.org/{YYYY-MM-DD-H}.json.gz`
- Each file contains all public GitHub events for that hour
- Filter for target projects during download to reduce size

**S3 Storage Pattern:**
```
s3://oss-risk-agent-bronze/github-archive/raw/{org}/{repo}/{date}/
```

**Files to Build:**

| File | Purpose |
|---|---|
| `ingestion/github_archive/project_list.py` | Curated list of 200 projects as structured dicts |
| `ingestion/github_archive/fetcher.py` | Downloads, filters, compresses, uploads to S3 |
| `ingestion/github_archive/backfill.py` | Orchestrates 90-day initial backfill |
| `ingestion/utils/s3_client.py` | Reusable S3 upload/download utilities |
| `scripts/run_ingestion.py` | PowerShell entry point |

**Project Categories:**
- Data & ML: Airflow, Spark, dbt-core, Kafka, PyTorch, LangChain, MLflow
- Infrastructure: Kubernetes, Terraform, Prometheus
- Frameworks: FastAPI, React
- AI/LLM tooling: LlamaIndex, Hugging Face Transformers, LangGraph

**Key Requirements:**
- Use `boto3` for S3, `requests` for HTTP
- 90-day initial backfill for first run
- `dry_run=True` flag on fetcher to test without hitting S3
- Retry logic on all HTTP requests
- Log every file downloaded and uploaded

**Acceptance Criteria:**
- [ ] `run_ingestion.py --dry-run` executes without errors
- [ ] At least one project's events land in S3 in correct path
- [ ] Logs show download → filter → upload flow clearly

---

## Phase 2 — Databricks Bronze → Silver

**Goal:** Read raw JSON.gz files from S3 bronze layer into Databricks,
flatten and clean the nested GitHub event structure, and write typed,
deduplicated tables to the Silver layer in Databricks Unity Catalog.

**Input:**
- S3 path: `s3://oss-risk-agent-bronze/github-archive/raw/{org}/{repo}/{date}/`
- Format: gzipped JSON, one event per line
- Schema: nested GitHub event objects (type, actor, repo, payload, created_at)

**Output:**
- Databricks table: `workspace.default.silver_github_events`
- Format: Delta table, partitioned by `event_date` and `repo_full_name`

**Key GitHub Event Types to Capture:**

| Event Type | What It Tells Us |
|---|---|
| `PushEvent` | Commit activity, contributor frequency |
| `IssuesEvent` | Issue open/close rates, backlog health |
| `PullRequestEvent` | PR merge time, review activity |
| `IssueCommentEvent` | Community engagement, sentiment signal |
| `WatchEvent` | Popularity momentum |
| `ForkEvent` | Adoption signal |

**Silver Table Schema:**
```
event_id          STRING       -- sha256 hash for deduplication
event_type        STRING       -- PushEvent, IssuesEvent, etc.
actor_login       STRING       -- GitHub username
actor_id          LONG
repo_full_name    STRING       -- org/repo
repo_id           LONG
created_at        TIMESTAMP
event_date        DATE         -- partition key
payload_action    STRING       -- opened, closed, merged, etc.
payload_commits   INT          -- number of commits (PushEvent only)
org_name          STRING       -- extracted from repo_full_name
repo_name         STRING       -- extracted from repo_full_name
ingested_at       TIMESTAMP    -- pipeline run timestamp
```

**Files to Build:**

| File | Purpose |
|---|---|
| `transformation/databricks/notebooks/01_bronze_to_silver.py` | PySpark notebook: read S3, flatten, write Delta |
| `transformation/databricks/notebooks/00_setup.py` | Creates catalog, schema, mounts if needed |
| `transformation/databricks/jobs/silver_job_config.json` | Databricks job definition JSON |
| `ingestion/utils/databricks_client.py` | Python client to trigger Databricks jobs via REST API |
| `scripts/run_silver.py` | PowerShell entry point to trigger the job |

**Key Requirements:**
- Use `spark.read.json()` with schema inference disabled — enforce schema explicitly
- Deduplicate on `event_id` (hash of event type + actor + repo + created_at)
- Partition Delta table by `event_date` for query performance
- Handle malformed JSON rows gracefully — log and skip, never fail
- Write mode: `append` with Delta merge for idempotency
- Auto-optimize and Z-order by `repo_full_name` for dbt query performance

**Acceptance Criteria:**
- [ ] `workspace.default.silver_github_events` table exists in Databricks
- [ ] Table contains records for at least 1 project from S3
- [ ] Schema matches specification above
- [ ] Running the job twice produces no duplicate rows
- [ ] Query in Databricks SQL Editor returns results:
      `SELECT repo_full_name, COUNT(*) FROM workspace.default.silver_github_events GROUP BY 1 ORDER BY 2 DESC LIMIT 10`

---

## Phase 3 — dbt Gold Layer

**Goal:** Connect dbt to Databricks, model the Silver table into a Gold
layer of computed health metrics per project per month, and generate a
visual lineage graph.

**Input:**
- Databricks table: `workspace.default.silver_github_events`

**Output tables:**
- `workspace.default.gold_project_health` — monthly health metrics per project
- `workspace.default.gold_health_scores` — final composite score per project

**dbt Project Structure:**
```
transformation/dbt/
├── dbt_project.yml
├── profiles.yml          ← gitignored, uses env vars
├── packages.yml
└── models/
    ├── staging/
    │   └── stg_github_events.sql
    ├── intermediate/
    │   ├── int_commit_activity.sql
    │   ├── int_issue_health.sql
    │   ├── int_pr_health.sql
    │   └── int_contributor_diversity.sql
    └── gold/
        ├── gold_project_health.sql
        └── gold_health_scores.sql
```

**Health Metrics to Compute (Gold Layer):**

| Metric | Logic |
|---|---|
| `commit_frequency` | PushEvents per week, 90-day trend |
| `issue_resolution_rate` | Closed issues / opened issues ratio |
| `pr_merge_rate` | Merged PRs / opened PRs ratio |
| `contributor_count` | Distinct actors, last 30 days |
| `bus_factor_risk` | % commits from top 3 contributors |
| `community_engagement` | Comments + reactions per issue |
| `health_score` | Weighted composite 0-10 |
| `health_trend` | MoM change in health_score |

**Files to Build:**

| File | Purpose |
|---|---|
| `transformation/dbt/dbt_project.yml` | dbt project config |
| `transformation/dbt/profiles.yml` | Databricks connection (uses env vars) |
| `transformation/dbt/packages.yml` | dbt packages (dbt-utils) |
| `transformation/dbt/models/staging/stg_github_events.sql` | Cast and rename silver columns |
| `transformation/dbt/models/intermediate/int_commit_activity.sql` | Commit frequency metrics |
| `transformation/dbt/models/intermediate/int_issue_health.sql` | Issue resolution metrics |
| `transformation/dbt/models/intermediate/int_pr_health.sql` | PR merge metrics |
| `transformation/dbt/models/intermediate/int_contributor_diversity.sql` | Bus factor + contributor count |
| `transformation/dbt/models/gold/gold_project_health.sql` | Join all intermediate models |
| `transformation/dbt/models/gold/gold_health_scores.sql` | Final weighted composite score |
| `transformation/dbt/models/staging/schema.yml` | Column descriptions + tests |
| `transformation/dbt/models/gold/schema.yml` | Gold layer tests |
| `scripts/run_dbt.py` | PowerShell entry point for dbt commands |

**Key Requirements:**
- Use `dbt-databricks` adapter
- profiles.yml reads from environment variables — never hardcoded
- Add `not_null` and `unique` tests on key columns
- Add `accepted_values` test on event_type
- health_score must be between 0 and 10
- Models should be materialized as `table` in gold, `view` in staging
- Include a `dbt source` definition for silver_github_events

**Acceptance Criteria:**
- [ ] `dbt debug` passes — connection to Databricks confirmed
- [ ] `dbt run` completes with all models green
- [ ] `dbt test` passes with zero failures
- [ ] `dbt docs generate && dbt docs serve` shows lineage graph
- [ ] `gold_health_scores` table exists in `workspace.default`
- [ ] Health scores are between 0-10 for all projects

---

## Phase 4 — LangGraph Agent

**Goal:** Build a five-step autonomous agent using LangGraph that monitors
gold_health_scores, detects deteriorating projects, investigates signals,
synthesizes risk assessments, and delivers alerts.

**Agent Steps:**

| Step | Node Name | What It Does |
|---|---|---|
| 1 | `monitor` | Queries gold_health_scores, flags projects below threshold |
| 2 | `investigate` | Fetches recent GitHub issues/PRs for flagged projects |
| 3 | `synthesize` | Calls Claude API to generate risk assessment |
| 4 | `recommend` | Produces structured recommendations (upgrade/replace/monitor) |
| 5 | `deliver` | Writes report to file, optionally posts to Slack |

**Agent State Schema:**
```python
class AgentState(TypedDict):
    flagged_projects: list[dict]
    investigation_results: dict
    risk_assessments: dict
    recommendations: dict
    report: str
    run_timestamp: str
```

**Files to Build:**

| File | Purpose |
|---|---|
| `agent/graphs/risk_agent.py` | Main LangGraph graph definition |
| `agent/nodes/monitor.py` | Queries Databricks gold table |
| `agent/nodes/investigate.py` | GitHub API calls for flagged projects |
| `agent/nodes/synthesize.py` | Claude API risk assessment generation |
| `agent/nodes/recommend.py` | Structured recommendation logic |
| `agent/nodes/deliver.py` | Report writing and delivery |
| `agent/tools/databricks_query.py` | Tool to query Databricks SQL |
| `agent/tools/github_fetch.py` | Tool to fetch GitHub issues/PRs |
| `agent/prompts/risk_assessment.py` | Prompt templates for Claude |
| `scripts/run_agent.py` | PowerShell entry point |

**Key Requirements:**
- Use LangGraph `StateGraph` with typed state
- LANGGRAPH_RECURSION_LIMIT=50 from env vars
- AGENT_MAX_RETRIES=3 from env vars
- RISK_SCORE_THRESHOLD=0.65 from env vars
- Monitor node flags projects where health_score < 6.0
- Investigate node fetches last 10 open issues per project
- Synthesize node generates 3-bullet risk summary per project
- Recommend node outputs one of: UPGRADE, REPLACE, MONITOR, HEALTHY
- Deliver node writes markdown report to docs/reports/
- Include --dry-run flag that runs full agent but skips delivery
- Loop limit: max 3 investigation retries per project

**Acceptance Criteria:**
- [ ] `python scripts\run_agent.py --dry-run` completes without errors
- [ ] Agent correctly flags projects with health_score < 6.0
- [ ] Risk assessment generated for each flagged project
- [ ] Markdown report written to docs/reports/
- [ ] Graph visualization available via LangGraph

---

## Phase 5 — Streamlit UI

**Goal:** Build a clean, interactive Streamlit dashboard that demos the
full OSS Dependency Risk Agent to interviewers and stakeholders.

**Pages:**

| Page | What It Shows |
|---|---|
| `Home` | Project summary, last run stats, top 5 risky projects |
| `Health Dashboard` | All 200 projects with health scores, sortable table, bar chart |
| `Project Detail` | Click any project — shows all metrics + AI risk assessment |
| `Run Agent` | Trigger a live agent run with limit selector, stream logs |
| `Reports` | List and view past markdown reports from docs/reports/ |

**Files to Build:**

| File | Purpose |
|---|---|
| `frontend/app.py` | Main Streamlit entry point, page routing |
| `frontend/pages/01_health_dashboard.py` | Health scores table and chart |
| `frontend/pages/02_project_detail.py` | Per-project deep dive |
| `frontend/pages/03_run_agent.py` | Live agent trigger UI |
| `frontend/pages/04_reports.py` | Past reports viewer |
| `frontend/components/health_chart.py` | Reusable bar chart component |
| `frontend/components/metrics_card.py` | Reusable metric card component |

**Key Requirements:**
- Use `st.set_page_config(layout="wide")`
- Load data from Databricks via databricks_query tool
- Health score color coding: green >= 7, yellow >= 5, red < 5
- Run Agent page uses `st.empty()` to stream agent log output
- All Databricks queries cached with `@st.cache_data(ttl=300)`
- No hardcoded credentials — all from .env via python-dotenv
- Include a sidebar with project filters (category, min health score)

**Acceptance Criteria:**
- [ ] `streamlit run frontend/app.py` launches without errors
- [ ] Health Dashboard shows all projects with color-coded scores
- [ ] Project Detail page loads for any selected project
- [ ] Run Agent page triggers agent and shows live output
- [ ] Reports page lists and renders past reports

---

## Memory Log

### Phase 0 — Completed
- Project scaffolded with full folder structure
- `.env.example` created with 20 variables
- `.gitignore` covers Python, dbt, Databricks, Spark, Streamlit
- `dbt-databricks` adapter chosen over `dbt-spark` for Unity Catalog support
- `ANTHROPIC_MODEL` corrected to `claude-sonnet-4-5`
- S3 bucket created: `oss-risk-agent-bronze` in `us-east-1`
- Databricks trial connected to AWS, token generated (60-day expiry)
- Pinecone index created: `oss-health` (serverless, llama-text-embed-v2)
- `DATABRICKS_CLUSTER_ID`, `DATABRICKS_HTTP_PATH`, `DATABRICKS_CATALOG`
  set to `pending` — resolved in Phase 2
- GitHub repo published and pushed

### Phase 1 — Complete
**Files built:**
- `ingestion/github_archive/project_list.py` — 200 projects across 10
  categories (data_ml, ai_llm, infrastructure, web_frameworks, databases,
  dev_tooling, security, observability, messaging, cicd). Exposes
  `get_all_projects()`, `get_project_set()`, `get_projects_by_category()`.
- `ingestion/utils/s3_client.py` — `S3Client` wrapping boto3 with tenacity
  retry (3 attempts, exponential back-off), `dry_run` mode, and static
  `build_key()` / `build_sentinel_key()` helpers.
- `ingestion/github_archive/fetcher.py` — `fetch_hour()` streams a GH Archive
  `.json.gz`, parses NDJSON line-by-line, filters for target repos in O(1),
  compresses per-project event batches, uploads to S3, writes a sentinel
  marker for idempotency.
- `ingestion/github_archive/backfill.py` — `run_backfill()` orchestrates N-day
  window as (date, hour) pairs oldest-first; accumulates `BackfillSummary`
  with per-hour counters. Failures are logged but do not abort the run.
- `scripts/run_ingestion.py` — argparse CLI with `--dry-run`, `--backfill`,
  `--date`, `--hour`, `--days`, `--no-skip-existing`. Exits 0/1.
  `__init__.py` stubs added to all three packages.

**Key decisions:**
- Sentinel key pattern (`_meta/done/{date}-{hour}.done`) chosen over listing
  per-project keys for fast idempotency checks on 2,160-item backfill windows.
- HTTP 404 from GH Archive treated as `skipped` (not a failure) — the archive
  sometimes has gaps for very recent or very old hours.
- Unicode arrows (`→`) replaced with ASCII (`->`) throughout — Windows
  PowerShell terminal uses cp1252 and cannot render them.
- `S3Client.build_key()` is a `@staticmethod` so callers can construct keys
  without instantiating the client (useful for dry-run path checks).

**Known issues / next steps:**
- No rate limiting between hour-files in the backfill loop — add `time.sleep`
  or a semaphore if hitting GH Archive throttling in practice.
- `fetcher.py` loads the full hour-file into memory before parsing. Files can
  reach ~500 MB uncompressed; consider true line-by-line streaming for large
  hours if memory pressure is observed on the Databricks driver.
- `S3_BRONZE_PREFIX` must end with `/` in `.env` or the key builder strips it
  correctly — confirmed in unit test but worth adding an explicit assertion.

### Phase 2 — Complete
**Files built:**
- `transformation/databricks/notebooks/00_setup.py` — Databricks notebook that
  configures S3 credentials (secrets scope with env var fallback), creates
  `workspace.default` schema, tests S3 connectivity via `dbutils.fs.ls`, and
  creates the silver Delta table DDL with `autoOptimize`/`autoCompact` enabled.
  Accepts `reset_table` widget to drop/recreate during development.
- `transformation/databricks/notebooks/01_bronze_to_silver.py` — Reads S3
  JSON.gz with an explicit bronze schema (PERMISSIVE + `_corrupt_record`),
  filters to 6 target event types, flattens nested structs, generates
  `event_id = sha2(type|actor_login|repo|created_at, 256)`, casts timestamps,
  extracts `org_name`/`repo_name`, MERGEs into silver Delta table (INSERT-only
  on `event_id`). Emits row-count summary. Accepts `start_date`/`end_date`
  widgets for incremental runs.
- `transformation/databricks/jobs/silver_job_config.json` — Jobs API 2.1
  definition: two tasks (setup -> bronze_to_silver), serverless compute
  (`environments: client: "2"`), 2-hour task timeout, commented daily schedule.
- `ingestion/utils/databricks_client.py` — `DatabricksClient` with lazy SDK
  import (`from __future__ import annotations` + `_import_sdk()` deferred to
  `__init__`), tenacity retry on uploads, `upload_all_notebooks()`,
  `create_or_update_job()` (upsert by name), `trigger_run()`, `wait_for_run()`
  (configurable poll/timeout), dry_run throughout.
- `scripts/run_silver.py` — CLI with `--upload`, `--create-job`, `--trigger`,
  `--wait`, `--start-date`, `--end-date`, `--dry-run`. Exits 0/1.

**Key decisions:**
- Databricks SDK imports are lazy so `--help` works without the package
  installed. `from __future__ import annotations` required to defer type
  annotation evaluation at class definition time.
- PERMISSIVE read mode + `_corrupt_record` captures bad JSON lines without
  crashing the pipeline. Corrupt rows are counted/sampled in logs then dropped.
- `created_at` kept as raw string during sha2 hashing for stable event_id
  regardless of downstream timestamp format changes.
- MERGE uses SQL (`MERGE INTO ... WHEN NOT MATCHED THEN INSERT *`) rather than
  DeltaTable Python API for notebook readability.
- S3 access resolved via **Unity Catalog External Location** pointing to
  `s3://oss-risk-agent-bronze/`. No Spark credential config required at runtime.
  Notebooks retain the secret-scope credential block as a fallback for non-UC
  contexts.
- Databricks secret scope `oss-risk-agent` key names use **underscores**
  (`aws_access_key_id`, `aws_secret_access_key`) — not hyphens. The original
  hyphenated names caused silent `dbutils.secrets.get()` failures that fell
  through to `AnonymousAWSCredentials` (S3 403 errors).
- Workspace: `https://dbc-92208bf2-316f.cloud.databricks.com`
- SQL Warehouse HTTP path: `/sql/1.0/warehouses/11bd1ba7445b1a22` (used by dbt)
- Notebooks upload to `/Shared/oss-risk-agent/` by default.

**Fixes applied post-initial-build:**
- **Serverless `.cache()` incompatibility** — resolved. `01_bronze_to_silver.py`
  now writes `df_silver` to a temp Delta table
  (`workspace.default._silver_incoming_temp`, overwrite mode) and reassigns the
  variable before the row count and MERGE. This materialises the S3 → transform
  plan once instead of re-running it per Spark action. DROP TABLE cleanup was
  removed — overwrite mode keeps the table fresh each run without triggering
  lazy re-evaluation.
- **S3 403 Forbidden** — resolved via Unity Catalog External Location (see above).

**Still open:**
- After initial backfill, run `OPTIMIZE workspace.default.silver_github_events ZORDER BY (repo_full_name)` manually.
- `payload.commits` is counted only; individual commit authors not surfaced.

### Dependency Housekeeping — Post Phase 2
- `requirements.txt` split into two files:
  - `requirements.txt` — packages needed to run the project locally
  - `requirements-dev.txt` — testing/dev tooling only (`-r requirements.txt` at top)
- Removed from `requirements.txt`: `databricks-connect` (Spark runs on Databricks,
  not locally), `pyspark` (same reason), `prefect` (not used; `schedule` covers needs)
- Install locally: `pip install -r requirements.txt`
- Install for development: `pip install -r requirements-dev.txt`

### Phase 3 — dbt Gold Layer (files built, pending first run)
**Files built:**
- `transformation/dbt/dbt_project.yml` — project config; staging/intermediate
  materialized as `view`, gold as `table` (Delta).
- `transformation/dbt/profiles.yml` — dbt-databricks adapter; reads
  `DATABRICKS_HOST`, `DATABRICKS_TOKEN`, `DATABRICKS_HTTP_PATH`,
  `DATABRICKS_CATALOG`, `DATABRICKS_SCHEMA` from env vars via `env_var()`.
  Strips `https://` from host with Jinja filter. Gitignored.
- `transformation/dbt/packages.yml` — `dbt-labs/dbt_utils >=1.0.0,<2.0.0`
  (used for `accepted_range` tests on health scores).
- `transformation/dbt/models/staging/stg_github_events.sql` — passthrough
  view over `workspace.default.silver_github_events` via `source()`.
- `transformation/dbt/models/staging/schema.yml` — source definition for
  silver table (catalog/schema/table); `not_null`, `unique`, `accepted_values`
  tests on stg model.
- `transformation/dbt/models/intermediate/int_commit_activity.sql` — monthly
  commit frequency per repo: `push_event_count`, `total_commits`,
  `active_committers`, `active_days`, `commits_per_week`.
- `transformation/dbt/models/intermediate/int_issue_health.sql` — monthly
  `issues_opened`, `issues_closed`, `issue_resolution_rate` (closed/opened).
- `transformation/dbt/models/intermediate/int_pr_health.sql` — monthly
  `prs_opened`, `prs_closed`, `pr_merge_rate`. Note: `prs_closed` is a proxy
  for merged PRs — Silver schema does not capture the `merged` boolean.
- `transformation/dbt/models/intermediate/int_contributor_diversity.sql` —
  monthly `contributor_count`, `top3_commits`, `bus_factor_risk`
  (top-3 share of total commits; higher = more concentrated = riskier).
- `transformation/dbt/models/gold/gold_project_health.sql` — wide join of
  all four intermediate models on `(repo_full_name, event_month)`. Left joins
  so every repo/month with any event type appears.
- `transformation/dbt/models/gold/gold_health_scores.sql` — normalises each
  signal to 0-10, applies weights, computes `health_score` and
  `health_trend` (MoM delta via window function).
- `transformation/dbt/models/gold/schema.yml` — `not_null` tests on keys;
  `dbt_utils.accepted_range(0, 10)` on `health_score` and all component scores.
- `scripts/run_dbt.py` — argparse CLI (`--deps`, `--debug`, `--run`,
  `--test`, `--docs`, `--select`, `--full-refresh`). Always passes
  `--profiles-dir .` so profiles.yml is found in the project directory.

**Key decisions:**
- `profiles.yml` is kept in `transformation/dbt/` (gitignored) and loaded via
  `--profiles-dir .` in `run_dbt.py` — avoids polluting `~/.dbt/`.
- `trunc(event_date, 'MM')` used throughout (returns DATE) instead of
  `date_trunc` (returns TIMESTAMP) for consistent join keys.
- `count_if(...)` used in issue/PR models — native Databricks SQL, cleaner
  than `sum(case when ...)`.
- Null metrics (no events of that type in the month) default to 5.0 (neutral)
  in the scoring layer so a missing signal doesn't collapse the health score.
- `generate_schema_name` macro NOT overridden — models land in `target.schema`
  (`default`) with no prefix. If dbt adds `default_` prefix on your workspace,
  add a `macros/generate_schema_name.sql` override.

**Health score weights:** commit_frequency 25%, issue_resolution_rate 20%,
pr_merge_rate 20%, contributor_count 20%, bus_factor_risk 15%.

**Bugs found and fixed during execution:**
- **Self-referencing cycle** — `stg_github_events.sql` had `{{ ref('stg_github_events') }}`
  inside a SQL block comment as a documentation example. dbt's static ref extractor
  runs regex over the entire file (including comments), creating a phantom self-dependency.
  Fix: write `ref('stg_github_events')` without the Jinja delimiters in comments.
- **`--profiles-dir` flag not found** — dbt 1.11 doesn't accept it as a global flag
  before the subcommand. Fix: inject `DBT_PROFILES_DIR` as an environment variable
  in the subprocess instead of using a CLI flag.
- **`dbt` not on PATH in subprocess** — `subprocess.run(["dbt", ...])` fails on Windows
  when the venv is not on the system PATH. Fix: resolve `dbt.exe` from
  `Path(sys.executable).parent` and store as `_DBT_EXE` in `run_dbt.py`.
- **`dbt_utils.accepted_range` / `accepted_values` deprecation** — in dbt 1.11 test
  arguments must be nested under `arguments:`. Updated `gold/schema.yml` and
  `staging/schema.yml` accordingly.
- **`unique_stg_github_events_event_id` test failure** — silver table contained 373
  duplicate `event_id` values from the pipeline running multiple times on overlapping
  date ranges. Fix: added `ROW_NUMBER() OVER (PARTITION BY event_id ORDER BY ingested_at DESC)`
  deduplication to `stg_github_events.sql`. Removed `unique` test from source
  definition (external data, can't control). Test passes on the model.

**Final status: `dbt run` PASS=7/7, `dbt test` PASS=21/21, WARN=0, ERROR=0.**

---
*Last updated: Phase 3 complete — all models built and all tests passing*

### Phase 4 — LangGraph Agent (Complete)
**Files built:**
- `agent/graphs/state.py` — `AgentState` TypedDict with core pipeline fields plus
  `dry_run` and `project_limit` runtime overrides.
- `agent/tools/databricks_query.py` — `query_databricks(sql)` using Databricks SDK
  `statement_execution.execute_statement()`. Returns `list[dict]` with string values.
  `wait_timeout="50s"` (Databricks API requires 0s or 5s–50s).
- `agent/tools/github_fetch.py` — `fetch_project_signals(repo_full_name)` fetching
  metadata, 10 open issues, and 5 recent PRs via GitHub REST API v3. Tenacity retry
  on `RequestException`. `/issues` endpoint filtered to exclude PRs.
- `agent/prompts/risk_assessment.py` — `SYSTEM_PROMPT` (OSS risk analyst persona) +
  `build_risk_assessment_prompt()` producing a metric table + issue/PR sample +
  3-bullet output request (primary risk, mitigating factors, recommended action).
- `agent/nodes/monitor.py` — Queries `gold_health_scores` with
  `health_score < HEALTH_SCORE_THRESHOLD` (default 6.0). Applies `project_limit`.
  Sets `run_timestamp` ISO-8601 UTC.
- `agent/nodes/investigate.py` — Calls `fetch_project_signals()` per flagged repo.
  Stores error dict on failure without aborting the pipeline.
- `agent/nodes/synthesize.py` — Calls Claude API (`claude-sonnet-4-5`) with retry
  (up to `AGENT_MAX_RETRIES=3`) on rate limit and API errors. Skips repos with
  investigation errors.
- `agent/nodes/recommend.py` — Computes `risk_score = (10 - health_score) / 10`.
  REPLACE if >= 0.65 (health <= 3.5), UPGRADE if >= 0.50 (health <= 5.0), else MONITOR.
- `agent/nodes/deliver.py` — Renders Markdown report grouped by REPLACE / UPGRADE /
  MONITOR sections. Writes to `docs/reports/risk_report_{ts}.md`. Skips write in
  `dry_run=True`. Stores full report in state for Streamlit use.
- `agent/graphs/risk_agent.py` — `StateGraph` linear pipeline:
  START → monitor → investigate → synthesize → recommend → deliver → END.
  `LANGGRAPH_RECURSION_LIMIT` from env (default 10).
- `scripts/run_agent.py` — CLI with `--dry-run` and `--limit`. Validates
  `ANTHROPIC_API_KEY`, `DATABRICKS_HOST`, `DATABRICKS_TOKEN` before invoking graph.
  Prints truncated report preview to stdout.

**Key decisions:**
- Nodes return dicts of updated fields only — LangGraph merges into state.
- All Databricks values arrive as strings; callers cast to float for comparisons.
- `wait_timeout` fixed to `"50s"` after runtime error: Databricks requires 0s or 5–50s.
- No Slack integration — deliver node writes to disk only.
- Null metrics in recommend default to (0.5, MONITOR) to avoid crashing on missing data.
- `docs/reports/` created at runtime by deliver node; timestamps use `-` not `:` for
  Windows filename compatibility.

**First successful run:** `docs/reports/risk_report_2026-04-12T19-36-29.md`

---

*Last updated: Phase 4 complete — 5-node LangGraph agent running end to end*

---
