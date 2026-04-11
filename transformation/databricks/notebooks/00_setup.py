# Databricks notebook source
# OSS Dependency Risk Agent — 00_setup.py
# Run this once before the bronze -> silver pipeline to:
#   1. Configure S3 credentials via Databricks secrets (or spark.conf fallback)
#   2. Create the workspace.default schema if it does not exist
#   3. Verify read access to the S3 bronze bucket
#   4. Optionally reset the silver table (useful during development)

# COMMAND ----------

# MAGIC %md
# MAGIC ## OSS Risk Agent — Workspace Setup
# MAGIC
# MAGIC **Run order:** Execute this notebook once before `01_bronze_to_silver`.
# MAGIC
# MAGIC ### S3 Credential Options (pick one)
# MAGIC
# MAGIC **Option A — Databricks Secret Scope (recommended):**
# MAGIC ```
# MAGIC databricks secrets create-scope oss-risk-agent
# MAGIC databricks secrets put-secret oss-risk-agent aws-access-key-id     --string-value <key>
# MAGIC databricks secrets put-secret oss-risk-agent aws-secret-access-key --string-value <secret>
# MAGIC databricks secrets put-secret oss-risk-agent aws-region             --string-value us-east-1
# MAGIC databricks secrets put-secret oss-risk-agent s3-bronze-bucket       --string-value oss-risk-agent-bronze
# MAGIC ```
# MAGIC
# MAGIC **Option B — Unity Catalog External Location (zero-credential):**
# MAGIC Create an External Location in the Databricks UI pointing to `s3://oss-risk-agent-bronze/`.
# MAGIC No spark.conf configuration needed.

# COMMAND ----------

# Widget: set to "true" to DROP and recreate the silver table (dev only).
dbutils.widgets.dropdown("reset_table", "false", ["true", "false"])
reset_table = dbutils.widgets.get("reset_table") == "true"

CATALOG = "workspace"
SCHEMA  = "default"
TABLE   = "silver_github_events"
FULL_TABLE_NAME = f"{CATALOG}.{SCHEMA}.{TABLE}"
S3_BRONZE_BUCKET = "oss-risk-agent-bronze"

# COMMAND ----------

# MAGIC %md
# MAGIC ### Step 1 — Configure S3 Credentials

# COMMAND ----------

_SECRET_SCOPE = "oss-risk-agent"

try:
    _aws_access_key = dbutils.secrets.get(scope=_SECRET_SCOPE, key="aws_access_key_id")
    _aws_secret_key = dbutils.secrets.get(scope=_SECRET_SCOPE, key="aws_secret_access_key")
except Exception as _exc:
    raise RuntimeError(
        f"[setup] Could not read AWS credentials from secret scope '{_SECRET_SCOPE}'. "
        "Ensure the scope exists and contains keys 'aws_access_key_id' and "
        f"'aws_secret_access_key'. Original error: {_exc}"
    ) from _exc

spark.conf.set("fs.s3a.access.key",      _aws_access_key)
spark.conf.set("fs.s3a.secret.key",      _aws_secret_key)
spark.conf.set("fs.s3a.endpoint.region", "us-east-1")
spark.conf.set(
    "fs.s3a.aws.credentials.provider",
    "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider",
)
print("[setup] S3 credentials configured from secret scope 'oss-risk-agent'.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Step 2 — Create Catalog Schema

# COMMAND ----------

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}")
print(f"[setup] Schema {CATALOG}.{SCHEMA} is ready.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Step 3 — Verify S3 Connectivity

# COMMAND ----------

bronze_root = f"s3a://{S3_BRONZE_BUCKET}/github-archive/raw/"

try:
    entries = dbutils.fs.ls(bronze_root)
    print(f"[setup] S3 connectivity OK. Found {len(entries)} top-level entries under {bronze_root}")
    for e in entries[:5]:
        print(f"        {e.path}")
except Exception as exc:
    print(f"[setup] WARNING: Could not list {bronze_root}")
    print(f"        Error: {exc}")
    print("        Check S3 credentials / External Location configuration.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Step 4 — Silver Table DDL

# COMMAND ----------

CREATE_TABLE_DDL = f"""
CREATE TABLE IF NOT EXISTS {FULL_TABLE_NAME} (
    event_id          STRING        NOT NULL  COMMENT 'sha256(type|actor_login|repo_full_name|created_at)',
    event_type        STRING                  COMMENT 'PushEvent, IssuesEvent, PullRequestEvent, etc.',
    actor_login       STRING                  COMMENT 'GitHub username of the actor',
    actor_id          LONG                    COMMENT 'Numeric GitHub actor ID',
    repo_full_name    STRING                  COMMENT 'org/repo slug',
    repo_id           LONG                    COMMENT 'Numeric GitHub repo ID',
    created_at        TIMESTAMP               COMMENT 'Event timestamp (UTC)',
    event_date        DATE                    COMMENT 'Partition key — date portion of created_at',
    payload_action    STRING                  COMMENT 'opened, closed, merged, synchronize, etc.',
    payload_commits   INT                     COMMENT 'Commit count for PushEvents; NULL otherwise',
    org_name          STRING                  COMMENT 'Organisation extracted from repo_full_name',
    repo_name         STRING                  COMMENT 'Repository name extracted from repo_full_name',
    ingested_at       TIMESTAMP               COMMENT 'Pipeline run timestamp (UTC)'
)
USING DELTA
PARTITIONED BY (event_date)
TBLPROPERTIES (
    'delta.autoOptimize.optimizeWrite' = 'true',
    'delta.autoOptimize.autoCompact'   = 'true',
    'delta.enableChangeDataFeed'       = 'true'
)
COMMENT 'Silver layer: flattened and deduplicated GitHub Archive events for OSS health monitoring'
"""

if reset_table:
    print(f"[setup] reset_table=true — dropping {FULL_TABLE_NAME}")
    spark.sql(f"DROP TABLE IF EXISTS {FULL_TABLE_NAME}")

spark.sql(CREATE_TABLE_DDL)
print(f"[setup] Table {FULL_TABLE_NAME} is ready.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Step 5 — Z-Order Index Hint (run after first data load)
# MAGIC
# MAGIC After the initial backfill, run this in a separate cell to improve query performance:
# MAGIC ```sql
# MAGIC OPTIMIZE workspace.default.silver_github_events
# MAGIC ZORDER BY (repo_full_name, event_type);
# MAGIC ```

# COMMAND ----------

# Print summary
print("\n[setup] ========== Setup Complete ==========")
print(f"  Catalog   : {CATALOG}")
print(f"  Schema    : {SCHEMA}")
print(f"  Table     : {FULL_TABLE_NAME}")
print(f"  S3 bucket : s3a://{S3_BRONZE_BUCKET}/")
print(f"  Reset     : {reset_table}")
print("[setup] Ready to run 01_bronze_to_silver.")
