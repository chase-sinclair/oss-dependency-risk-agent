{{ config(materialized='view') }}

/*
  Staging layer: typed view over workspace.default.silver_github_events.

  Passes through all columns unchanged — the Silver schema is already clean.
  The value of this layer is the dbt source abstraction: downstream models
  reference ref('stg_github_events') instead of the raw table name,
  making the lineage graph accurate and the source swappable.
*/

with source as (

    select * from {{ source('silver', 'silver_github_events') }}

),

-- Deduplicate on event_id, keeping the most recently ingested record.
-- The silver table can accumulate duplicates when the bronze->silver pipeline
-- runs multiple times on overlapping date ranges.  Deduplication here means
-- all downstream models see exactly one row per event.
deduped as (

    select *,
        row_number() over (
            partition by event_id
            order by ingested_at desc
        ) as _row_num
    from source

),

staged as (

    select
        event_id,
        event_type,
        actor_login,
        actor_id,
        repo_full_name,
        repo_id,
        created_at,
        event_date,
        payload_action,
        payload_commits,
        org_name,
        repo_name,
        ingested_at
    from deduped
    where _row_num = 1

)

select * from staged
