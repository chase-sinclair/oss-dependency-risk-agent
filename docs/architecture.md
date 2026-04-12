# Technical Architecture

This document describes the internal design decisions, data flows, and
component interactions of the OSS Dependency Risk Agent.

---

## System Overview

```
GitHub Archive (public dataset)
        │
        ▼  HTTP streaming, gzip, NDJSON line filtering
┌───────────────────┐
│   AWS S3 Bronze   │  Raw gzipped JSON events per org/repo/date
└───────────────────┘
        │
        ▼  Databricks PySpark notebook (MERGE-based dedup)
┌───────────────────┐
│  Databricks       │  workspace.default.silver_github_events
│  Silver (Delta)   │  Partitioned by event_date, repo_full_name
└───────────────────┘
        │
        ▼  dbt (7 models, 21 tests)
┌───────────────────┐
│  Gold Layer       │  workspace.default.gold_health_scores
│  (Delta tables)   │  Composite health score 0-10 per project/month
└───────────────────┘
        │
        ├──────────────────────────────────┐
        ▼                                  ▼
┌───────────────────┐           ┌──────────────────────┐
│  LangGraph Agent  │           │   Streamlit UI        │
│  5-node pipeline  │──────────▶│   frontend/app.py     │
└───────────────────┘  reports  └──────────────────────┘
        │
        ├── GitHub API (live signals)
        └── Anthropic Claude (risk synthesis)
```

---

## Layer 1 — Bronze (AWS S3)

### Data Source

GitHub Archive (`data.gharchive.org`) publishes one `.json.gz` file per
hour, containing every public GitHub event globally. Each file is 20-200 MB
compressed; ~500 MB uncompressed at peak hours.

### Ingestion Design

`ingestion/github_archive/fetcher.py` streams each hour-file line-by-line,
filtering in O(1) using a pre-built set of 200 `org/repo` strings. Matching
events are collected per project, re-compressed with `gzip`, and uploaded
to S3 under:

```
s3://oss-risk-agent-bronze/github-archive/raw/{org}/{repo}/{YYYY-MM-DD}/
```

A sentinel key (`_meta/done/{date}-{hour}.done`) is written after each
successful hour, enabling the backfill loop to skip already-processed hours
without listing per-project keys.

### Key Decision: In-memory vs. Streaming

The fetcher reads the entire GH Archive hour-file into memory before parsing.
This is acceptable for the current data volume but is flagged in the code as
a potential memory pressure point for very large hours (>500 MB uncompressed).
True line-by-line streaming would require a chunked HTTP response reader.

---

## Layer 2 — Silver (Databricks Delta Lake)

### Schema Enforcement

The Bronze NDJSON schema is deeply nested (actor, repo, payload sub-objects
vary by event type). The Silver notebook uses `PERMISSIVE` read mode with
`_corrupt_record` capture — malformed JSON rows are counted and dropped
without aborting the pipeline.

Six event types are retained: `PushEvent`, `IssuesEvent`, `PullRequestEvent`,
`IssueCommentEvent`, `WatchEvent`, `ForkEvent`.

### Deduplication

Event identity is computed as:

```python
sha2(concat_ws('|', type, actor_login, repo_full_name, created_at), 256)
```

Using `created_at` as a raw string (before timestamp casting) ensures the
hash is stable regardless of downstream timezone handling. The MERGE
statement uses `INSERT WHEN NOT MATCHED` only — there is no UPDATE path,
since GitHub events are immutable once created.

### Serverless Compatibility

Databricks Serverless disallows `.cache()` (no persistent in-memory storage
tier). The Silver notebook materialises the transformed DataFrame to a temp
Delta table (`workspace.default._silver_incoming_temp`) before running the
row count and MERGE. This ensures Spark evaluates the full S3 → transform
plan exactly once.

### S3 Access

Access is granted via Unity Catalog External Location pointing to
`s3://oss-risk-agent-bronze/`. No Spark credential configuration is needed
in the notebook at runtime. A fallback secret-scope block is retained for
non-Unity Catalog contexts.

---

## Layer 3 — Gold (dbt)

### Model Lineage

```
Source: workspace.default.silver_github_events
    │
    └── stg_github_events (view)
            │   ROW_NUMBER() dedup on event_id
            │
            ├── int_commit_activity       (view)
            │   push_event_count, total_commits, commits_per_week
            │
            ├── int_issue_health          (view)
            │   issues_opened, issues_closed, issue_resolution_rate
            │
            ├── int_pr_health             (view)
            │   prs_opened, prs_closed, pr_merge_rate
            │
            └── int_contributor_diversity (view)
                contributor_count, bus_factor_risk
                        │
                        └── gold_project_health (table)
                                    │  wide join of all 4 intermediates
                                    │
                                    └── gold_health_scores (table)
                                        normalised 0-10 scores + health_trend
```

### Scoring Weights

| Signal | Weight | Rationale |
|---|---|---|
| Commit frequency | 25% | Most direct indicator of active maintenance |
| Issue resolution rate | 20% | Signals maintainer responsiveness |
| PR merge rate | 20% | Signals code review health |
| Contributor diversity | 20% | Reduces single-point-of-failure risk |
| Bus factor (inverted) | 15% | Concentration risk; high concentration = high risk |

Missing signals (no events of a given type in the month) default to 5.0
(neutral) rather than 0.0. This prevents a quiet month from appearing as
critical when the project may simply have low event volume.

### Health Trend

`health_trend` is computed as:
```sql
health_score - LAG(health_score) OVER (PARTITION BY repo_full_name ORDER BY event_month)
```

Positive = improving, negative = deteriorating, NULL = first month of data.

### Test Coverage

21 dbt tests enforced on every run:
- `not_null` on all key columns
- `unique` on `event_id` in the staging model (post-dedup)
- `accepted_values` on `event_type`
- `dbt_utils.accepted_range(0, 10)` on all score columns

---

## Layer 4 — LangGraph Agent

### State Machine

```python
class AgentState(TypedDict):
    flagged_projects:      list[dict]   # set by monitor
    investigation_results: dict         # set by investigate
    risk_assessments:      dict         # set by synthesize
    recommendations:       dict         # set by recommend
    report:                str          # set by deliver
    run_timestamp:         str
    dry_run:               NotRequired[bool]
    project_limit:         NotRequired[int | None]
```

Nodes return dicts of updated fields only. LangGraph merges the return
value into the running state — nodes never receive a stale copy of state
they did not intend to modify.

### Node Design

**monitor** — Queries `gold_health_scores` via the Databricks Statement
Execution API (`wait_timeout="50s"`). Flags projects where
`health_score < HEALTH_SCORE_THRESHOLD` (default 6.0). Applies
`project_limit` to cap API costs during development.

**investigate** — Calls `fetch_project_signals()` per flagged repo.
GitHub's `/issues` endpoint returns PRs too; the tool filters them out
before returning. On failure, stores an error dict in state rather than
aborting the pipeline — downstream nodes skip repos with error dicts.

**synthesize** — Sends a formatted prompt to Claude Sonnet with:
- A metric table (6 signals on 0-10 scale)
- Repository metadata (stars, forks, open issues, language, last push)
- Up to 5 recent open issues and 3 recent open PRs

The system prompt instructs Claude to produce exactly 3 bullets:
primary risk signal, mitigating factors, recommended action. Retry
logic (up to 3 attempts) handles rate limits and transient API errors.

**recommend** — Computes `risk_score = (10 - health_score) / 10` and
maps to actions:
- `>= 0.65` → REPLACE (health_score ≤ 3.5)
- `>= 0.50` → UPGRADE (health_score ≤ 5.0)
- `< 0.50`  → MONITOR

**deliver** — Groups recommendations by action tier and renders a
structured Markdown report. In `dry_run=True` mode, the report string
is stored in state and printed to stdout but not written to disk.
The full report string is always available in `state["report"]` for
Streamlit to consume directly.

### Why LangGraph over Direct API Calls?

1. **Inspectability** — the graph is a first-class object; edges and nodes
   can be visualised and tested in isolation
2. **Typed state** — `AgentState` TypedDict makes it impossible to silently
   drop fields or pass wrong types between nodes
3. **Extensibility** — adding a retry loop (e.g. re-investigate if Claude
   confidence is low) requires adding a conditional edge, not refactoring
   function call chains

---

## Layer 5 — Streamlit UI

### Data Loading Pattern

Every page uses `@st.cache_data(ttl=300)` on Databricks query functions.
All queries select `WHERE event_month = MAX(event_month)` so the UI works
correctly with any amount of historical data — including a single day.

### Run Agent Page — Subprocess Streaming

Spawning the agent as a subprocess (rather than calling `run_agent()` inline)
isolates the agent's logging output from Streamlit's own log stream, and
prevents LangGraph's internal threading from conflicting with Streamlit's
script reruns. A daemon thread reads stdout line-by-line into a `Queue`;
the main thread drains the queue and updates a `st.empty()` container.

### Project Detail — Assessment Retrieval

The Project Detail page retrieves Claude's assessment by scanning the most
recent 5 report files for the repo's Markdown section header
(`### org/repo`). This avoids needing a separate database for assessments
and keeps the architecture simple — the report file is the system of record.

---

## Security and Credentials

- All credentials are loaded from `.env` via `python-dotenv`. No values are
  hardcoded anywhere in the codebase.
- `.env` is gitignored. `.env.example` documents all required variables with
  placeholder values.
- Databricks secret scope `oss-risk-agent` stores AWS credentials for
  notebook access. Key names use underscores (`aws_access_key_id`) — the
  Databricks SDK is case-sensitive on hyphens vs. underscores.
- GitHub API degrades gracefully to unauthenticated (60 req/hr) if
  `GITHUB_TOKEN` is absent, rather than failing hard.

---

## Known Limitations

| Limitation | Impact | Mitigation |
|---|---|---|
| `prs_closed` used as proxy for merged PRs | PR merge rate slightly inflated | Silver schema does not capture the `merged` boolean from GH Archive payloads |
| Single-month scoring | Health trend null for first month of data | Acceptable for initial build; grows accurate over time |
| No rate limiting in backfill loop | Potential GH Archive throttling on large backfills | Add `time.sleep` or semaphore if observed in practice |
| Agent processes projects serially | Slow for large flagged lists | Parallelise `investigate` and `synthesize` with `asyncio` or `ThreadPoolExecutor` in V2 |
| In-memory hour-file loading | Memory pressure on files >500 MB | Switch to chunked HTTP streaming if Databricks driver shows OOM |
