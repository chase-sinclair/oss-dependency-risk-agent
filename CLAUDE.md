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

## Phase 7 — Pinecone RAG Layer

**Goal:** Embed generated risk assessment reports into Pinecone and add
semantic search to the Streamlit UI so users can query across all
project assessments using natural language.

**How It Works:**
1. After agent generates a report, indexer embeds each project's
   risk assessment text using Pinecone's hosted llama-text-embed-v2
2. Each vector stored with metadata: repo_full_name, health_score,
   recommendation, report_timestamp
3. Streamlit search page accepts natural language queries, embeds
   them, and returns top 5 semantically similar projects

**Files to Build:**

| File | Purpose |
|---|---|
| `embeddings/indexer.py` | Parse report markdown, embed per-project sections, upsert to Pinecone |
| `embeddings/searcher.py` | Query Pinecone, return ranked results with excerpts |
| `scripts/run_indexer.py` | CLI entry point: indexes latest or all reports |
| `frontend/pages/05_search.py` | Streamlit semantic search page |

**Pinecone Configuration:**
- Index: `oss-health`
- Namespace: `oss-deps`
- Embedding model: `llama-text-embed-v2` (hosted, no separate API needed)
- Metadata fields: repo_full_name, health_score, recommendation,
  report_date, report_file

**Key Requirements:**
- Parse docs/reports/*.md to extract per-project sections
- Each project's full assessment text becomes one Pinecone vector
- Metadata enables filtered search (e.g. only REPLACE recommendations)
- Searcher returns: project name, health score, recommendation,
  relevant excerpt, similarity score
- Search page has optional filter: All / REPLACE / UPGRADE / MONITOR
- Index on every agent run automatically
- Handle empty index gracefully (show "Run agent first" message)

**Acceptance Criteria:**
- [ ] `python scripts\run_indexer.py` indexes all existing reports
- [ ] Pinecone console shows vectors in oss-health index
- [ ] Search page returns relevant results for natural language queries
- [ ] Filtering by recommendation type works correctly
- [ ] Results show similarity score and excerpt