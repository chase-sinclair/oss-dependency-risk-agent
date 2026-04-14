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

---

## Phase 8 — Dependency Discovery

**Goal:** Allow any company to onboard their actual dependency stack
by parsing standard package manifest files and automatically resolving
dependencies to GitHub repositories for monitoring.

**How It Works:**
1. User provides one or more manifest files (requirements.txt, 
   package.json, etc.)
2. Parser extracts package names and versions
3. Resolver calls GitHub Search API to find the canonical org/repo
4. Resolved projects are added to project_list.py monitoring list
5. Next pipeline run automatically includes new projects

**Files to Build:**

| File | Purpose |
|---|---|
| `ingestion/discovery/manifest_parser.py` | Parses requirements.txt, package.json, go.mod, pom.xml, Cargo.toml |
| `ingestion/discovery/github_resolver.py` | Resolves package names to GitHub org/repo via GitHub Search API |
| `ingestion/discovery/project_registry.py` | Manages adding/removing projects from monitoring list |
| `scripts/discover_dependencies.py` | CLI entry point |

**CLI Usage:**
```
# Onboard a Python project
python scripts\discover_dependencies.py --manifest requirements.txt

# Onboard a Node project  
python scripts\discover_dependencies.py --manifest package.json

# Onboard multiple manifests
python scripts\discover_dependencies.py --manifest requirements.txt --manifest package.json

# Preview without adding to monitoring list
python scripts\discover_dependencies.py --manifest requirements.txt --dry-run

# Show current monitoring list
python scripts\discover_dependencies.py --list
```

**Output Example:**
```
Parsed 45 dependencies from requirements.txt
Resolved 38/45 to GitHub repositories
Added 12 new projects to monitoring list (26 already monitored)
Failed to resolve 7 packages (logged to docs/unresolved.txt)

New projects added:
  + pydantic/pydantic        (python/validation)
  + tiangolo/fastapi         (python/framework) 
  + celery/celery            (python/task-queue)
  ...
```

**Key Requirements:**
- GitHub Search API for resolution (GITHUB_TOKEN already in .env)
- Cache resolved packages to avoid repeat API calls
- Dry run flag shows what would be added without modifying project_list.py
- Handle packages with no GitHub repo gracefully (log to unresolved.txt)
- Preserve existing project_list.py structure and categories
- Add discovered projects under a "discovered" category
- Deduplication — never add a project already being monitored

**Acceptance Criteria:**
- [ ] `discover_dependencies.py --manifest requirements.txt --dry-run` works
- [ ] At least 80% of packages in a standard requirements.txt resolve correctly
- [ ] project_list.py updated correctly after non-dry-run
- [ ] Duplicates handled gracefully
- [ ] Unresolved packages logged to docs/unresolved.txt

---