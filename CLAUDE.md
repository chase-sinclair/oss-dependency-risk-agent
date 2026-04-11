# CLAUDE.md — OSS Dependency Risk Agent
> This file is the persistent memory and instruction set for Claude Code.
> Update the Memory Log at the end of every phase before moving on.

---

## Project Overview

**Project Name:** OSS Dependency Risk Agent

**What It Does:**
An autonomous agent system that monitors 200+ open source dependencies by
analyzing GitHub Archive event data through a Databricks/dbt pipeline,
detects health deterioration signals, and automatically generates risk
assessments using a LangGraph agent powered by Claude (Anthropic API).

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
| 2 | Databricks Bronze → Silver | 🔄 In Progress |
| 3 | dbt Gold layer — health metrics | ⬜ Pending |
| 4 | LangGraph agent — 5 step workflow | ⬜ Pending |
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

---
*Last updated: Phase 1 complete*
