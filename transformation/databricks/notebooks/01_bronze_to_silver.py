# Databricks notebook source
# OSS Dependency Risk Agent — 01_bronze_to_silver.py
#
# Reads gzipped GitHub Archive JSON from S3 bronze layer, enforces an
# explicit schema, flattens nested structs, deduplicates on event_id,
# and MERGEs records into workspace.default.silver_github_events (Delta).
#
# Widgets
#   start_date  YYYY-MM-DD  Earliest event date to process (empty = all)
#   end_date    YYYY-MM-DD  Latest event date to process   (empty = all)

# COMMAND ----------

# MAGIC %md
# MAGIC ## OSS Risk Agent — Bronze to Silver Transformation
# MAGIC
# MAGIC | | |
# MAGIC |---|---|
# MAGIC | **Input**  | `s3a://oss-risk-agent-bronze/github-archive/raw/*/*/*/*.json.gz` |
# MAGIC | **Output** | `workspace.default.silver_github_events` (Delta, partitioned by `event_date`) |
# MAGIC | **Key**    | `event_id = sha2(type + actor_login + repo_full_name + created_at, 256)` |

# COMMAND ----------

# ── Widgets ────────────────────────────────────────────────────────────────────
dbutils.widgets.text("start_date", "", "Start date (YYYY-MM-DD, empty = all)")
dbutils.widgets.text("end_date",   "", "End date   (YYYY-MM-DD, empty = all)")

start_date = dbutils.widgets.get("start_date").strip()
end_date   = dbutils.widgets.get("end_date").strip()

# ── Constants ──────────────────────────────────────────────────────────────────
S3_BRONZE_BUCKET  = "oss-risk-agent-bronze"
BRONZE_ROOT       = f"s3a://{S3_BRONZE_BUCKET}/github-archive/raw"
FULL_TABLE_NAME   = "workspace.default.silver_github_events"

TARGET_EVENT_TYPES = {
    "PushEvent",
    "IssuesEvent",
    "PullRequestEvent",
    "IssueCommentEvent",
    "WatchEvent",
    "ForkEvent",
}

print(f"[bronze->silver] start_date : '{start_date or 'ALL'}'")
print(f"[bronze->silver] end_date   : '{end_date   or 'ALL'}'")
print(f"[bronze->silver] target     : {FULL_TABLE_NAME}")

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
        f"[bronze->silver] Could not read AWS credentials from secret scope '{_SECRET_SCOPE}'. "
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
print("[bronze->silver] S3 credentials configured from secret scope 'oss-risk-agent'.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Step 2 — Define Bronze Schema

# COMMAND ----------

from pyspark.sql.types import (
    ArrayType, BooleanType, IntegerType, LongType,
    StringType, StructField, StructType,
)

# Minimal commits sub-schema — we only need the count, not full detail
_commits_schema = ArrayType(
    StructType([
        StructField("sha",      StringType(),  True),
        StructField("message",  StringType(),  True),
        StructField("distinct", BooleanType(), True),
    ])
)

# Explicit bronze schema — fields not listed here are silently dropped by Spark.
# created_at is kept as StringType for deterministic sha2 hashing before cast.
bronze_schema = StructType([
    StructField("id",      StringType(),  True),
    StructField("type",    StringType(),  True),
    StructField("actor", StructType([
        StructField("id",            LongType(),   True),
        StructField("login",         StringType(), True),
        StructField("display_login", StringType(), True),
        StructField("gravatar_id",   StringType(), True),
        StructField("url",           StringType(), True),
        StructField("avatar_url",    StringType(), True),
    ]), True),
    StructField("repo", StructType([
        StructField("id",   LongType(),   True),
        StructField("name", StringType(), True),
        StructField("url",  StringType(), True),
    ]), True),
    StructField("payload", StructType([
        StructField("action",        StringType(),   True),
        StructField("ref",           StringType(),   True),
        StructField("ref_type",      StringType(),   True),
        StructField("push_id",       LongType(),     True),
        StructField("size",          IntegerType(),  True),
        StructField("distinct_size", IntegerType(),  True),
        StructField("commits",       _commits_schema, True),
        StructField("number",        IntegerType(),  True),
    ]), True),
    StructField("public",     BooleanType(), True),
    StructField("created_at", StringType(),  True),   # ISO-8601 string
    StructField("org", StructType([
        StructField("id",    LongType(),   True),
        StructField("login", StringType(), True),
    ]), True),
    # Catches rows that don't conform to the schema (PERMISSIVE mode)
    StructField("_corrupt_record", StringType(), True),
])

print(f"[bronze->silver] Bronze schema defined ({len(bronze_schema.fields)} top-level fields).")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Step 3 — Build S3 Read Paths

# COMMAND ----------

import datetime

def _build_s3_paths(bronze_root: str, start_date: str, end_date: str) -> list:
    """
    Return a list of S3 glob patterns to read.

    When both dates are provided, builds one pattern per calendar day
    so Spark only opens relevant partitions.
    When dates are empty, returns a single recursive wildcard.
    """
    if start_date and end_date:
        paths = []
        current = datetime.date.fromisoformat(start_date)
        end     = datetime.date.fromisoformat(end_date)
        while current <= end:
            day_str = current.strftime("%Y-%m-%d")
            # Pattern: raw/{org}/{repo}/{date}/*.json.gz
            paths.append(f"{bronze_root}/*/*/*{day_str}*/*.json.gz")
            current += datetime.timedelta(days=1)
        return paths
    # No filter — read everything
    return [f"{bronze_root}/*/*/*/*.json.gz"]


s3_paths = _build_s3_paths(BRONZE_ROOT, start_date, end_date)
print(f"[bronze->silver] Reading from {len(s3_paths)} S3 glob pattern(s).")
for p in s3_paths[:3]:
    print(f"        {p}")
if len(s3_paths) > 3:
    print(f"        ... and {len(s3_paths) - 3} more")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Step 4 — Read Bronze Layer

# COMMAND ----------

df_raw = (
    spark.read
    .schema(bronze_schema)
    .option("mode",                   "PERMISSIVE")
    .option("columnNameOfCorruptRecord", "_corrupt_record")
    .option("compression",            "gzip")
    .json(s3_paths)
)

total_raw = df_raw.count()
corrupt   = df_raw.filter("_corrupt_record IS NOT NULL").count()
print(f"[bronze->silver] Raw rows read    : {total_raw:,}")
print(f"[bronze->silver] Corrupt rows     : {corrupt:,}")

if corrupt > 0:
    print("[bronze->silver] Sample corrupt records (up to 5):")
    df_raw.filter("_corrupt_record IS NOT NULL").select("_corrupt_record").show(5, truncate=120)

# Drop corrupt rows before transformation
df_clean = df_raw.filter("_corrupt_record IS NULL").drop("_corrupt_record")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Step 5 — Filter to Target Event Types

# COMMAND ----------

from pyspark.sql import functions as F

df_filtered = df_clean.filter(F.col("type").isin(list(TARGET_EVENT_TYPES)))

filtered_count = df_filtered.count()
print(f"[bronze->silver] After event-type filter: {filtered_count:,} rows")
print(f"[bronze->silver] Event type distribution:")
(
    df_filtered
    .groupBy("type")
    .count()
    .orderBy(F.col("count").desc())
    .show(truncate=False)
)

# COMMAND ----------

# MAGIC %md
# MAGIC ### Step 6 — Transform to Silver Schema

# COMMAND ----------

from pyspark.sql import functions as F

df_silver = (
    df_filtered
    # ── Deduplication key ───────────────────────────────────────────────────
    # sha2 of the four most-identifying fields, separated by | to prevent
    # accidental collisions across field boundaries.
    .withColumn(
        "event_id",
        F.sha2(
            F.concat_ws(
                "|",
                F.col("type"),
                F.col("actor.login"),
                F.col("repo.name"),
                F.col("created_at"),   # raw ISO string — consistent across runs
            ),
            256,
        ),
    )
    # ── Scalar fields ───────────────────────────────────────────────────────
    .withColumn("event_type",     F.col("type"))
    .withColumn("actor_login",    F.col("actor.login"))
    .withColumn("actor_id",       F.col("actor.id").cast("long"))
    .withColumn("repo_full_name", F.col("repo.name"))
    .withColumn("repo_id",        F.col("repo.id").cast("long"))
    # ── Timestamps ──────────────────────────────────────────────────────────
    .withColumn(
        "created_at",
        F.to_timestamp(F.col("created_at"), "yyyy-MM-dd'T'HH:mm:ss'Z'"),
    )
    .withColumn("event_date", F.to_date(F.col("created_at")))
    # ── Payload flattening ──────────────────────────────────────────────────
    .withColumn("payload_action",  F.col("payload.action"))
    .withColumn(
        "payload_commits",
        F.when(
            F.col("payload.commits").isNotNull(),
            F.size(F.col("payload.commits")),
        ).otherwise(F.lit(None).cast("int")),
    )
    # ── Derived fields ───────────────────────────────────────────────────────
    .withColumn(
        "org_name",
        F.split(F.col("repo.name"), "/").getItem(0),
    )
    .withColumn(
        "repo_name",
        F.split(F.col("repo.name"), "/").getItem(1),
    )
    # ── Pipeline metadata ────────────────────────────────────────────────────
    .withColumn("ingested_at", F.current_timestamp())
    # ── Select only Silver columns (drop bronze structs) ─────────────────────
    .select(
        "event_id",
        "event_type",
        "actor_login",
        "actor_id",
        "repo_full_name",
        "repo_id",
        "created_at",
        "event_date",
        "payload_action",
        "payload_commits",
        "org_name",
        "repo_name",
        "ingested_at",
    )
    # Drop rows where the deduplication key fields are null
    .filter(
        F.col("event_id").isNotNull()
        & F.col("repo_full_name").isNotNull()
        & F.col("event_date").isNotNull()
    )
)

# ── Materialise to temp Delta table (serverless compatibility) ─────────────
# .cache() is not supported on serverless compute.  Writing to a temp Delta
# table forces the full S3 -> transform plan to execute exactly once; the
# reassigned df_silver is then a cheap table scan for both the row count
# below and the MERGE in Step 8.  Overwrite mode keeps the table fresh each
# run — no DROP TABLE needed (and dropping would trigger lazy re-evaluation).
_TEMP_TABLE = "workspace.default._silver_incoming_temp"

(
    df_silver
    .write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(_TEMP_TABLE)
)

df_silver = spark.table(_TEMP_TABLE)

silver_incoming = df_silver.count()
print(f"[bronze->silver] Transformed rows ready for MERGE: {silver_incoming:,}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Step 7 — Ensure Silver Table Exists

# COMMAND ----------

# The table is created by 00_setup.py.  This guard prevents a hard failure
# if this notebook is run standalone without setup.
spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {FULL_TABLE_NAME} (
        event_id          STRING     NOT NULL,
        event_type        STRING,
        actor_login       STRING,
        actor_id          LONG,
        repo_full_name    STRING,
        repo_id           LONG,
        created_at        TIMESTAMP,
        event_date        DATE,
        payload_action    STRING,
        payload_commits   INT,
        org_name          STRING,
        repo_name         STRING,
        ingested_at       TIMESTAMP
    )
    USING DELTA
    PARTITIONED BY (event_date)
    TBLPROPERTIES (
        'delta.autoOptimize.optimizeWrite' = 'true',
        'delta.autoOptimize.autoCompact'   = 'true'
    )
""")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Step 8 — MERGE into Silver Table (idempotent)

# COMMAND ----------

# Pre-MERGE row count for validation
before_count = spark.sql(f"SELECT COUNT(*) AS n FROM {FULL_TABLE_NAME}").first()["n"]
print(f"[bronze->silver] Rows in target before MERGE : {before_count:,}")

# Register incoming data as a temp view for the SQL MERGE statement
df_silver.createOrReplaceTempView("_incoming_silver")

merge_sql = f"""
MERGE INTO {FULL_TABLE_NAME} AS target
USING _incoming_silver AS source
ON target.event_id = source.event_id
WHEN NOT MATCHED THEN INSERT *
"""

spark.sql(merge_sql)

# Post-MERGE validation
after_count  = spark.sql(f"SELECT COUNT(*) AS n FROM {FULL_TABLE_NAME}").first()["n"]
rows_added   = after_count - before_count
dupe_count   = silver_incoming - rows_added

print(f"[bronze->silver] Rows in target after MERGE  : {after_count:,}")
print(f"[bronze->silver] New rows inserted            : {rows_added:,}")
print(f"[bronze->silver] Duplicates skipped           : {dupe_count:,}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Step 9 — Row Count Summary by Repository

# COMMAND ----------

print("[bronze->silver] ===== Top 20 repos by event count (all-time) =====")
spark.sql(f"""
    SELECT
        repo_full_name,
        COUNT(*)            AS total_events,
        COUNT(DISTINCT event_type) AS event_types,
        MIN(event_date)     AS earliest_date,
        MAX(event_date)     AS latest_date
    FROM {FULL_TABLE_NAME}
    GROUP BY repo_full_name
    ORDER BY total_events DESC
    LIMIT 20
""").show(truncate=False)

# COMMAND ----------

print(f"\n[bronze->silver] ===== Pipeline Run Summary =====")
print(f"  S3 paths read       : {len(s3_paths)}")
print(f"  Raw rows read       : {total_raw:,}")
print(f"  Corrupt rows        : {corrupt:,}")
print(f"  After type filter   : {filtered_count:,}")
print(f"  Sent to MERGE       : {silver_incoming:,}")
print(f"  Rows inserted       : {rows_added:,}")
print(f"  Duplicates skipped  : {dupe_count:,}")
print(f"  Table total (after) : {after_count:,}")
print(f"  Target table        : {FULL_TABLE_NAME}")
