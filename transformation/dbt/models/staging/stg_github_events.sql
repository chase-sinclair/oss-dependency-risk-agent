{{ config(materialized='view') }}

/*
  Staging layer: typed view over workspace.default.silver_github_events.

  Passes through all columns unchanged — the Silver schema is already clean.
  The value of this layer is the dbt source abstraction: downstream models
  reference {{ ref('stg_github_events') }} instead of the raw table name,
  making the lineage graph accurate and the source swappable.
*/

with source as (

    select * from {{ source('silver', 'silver_github_events') }}

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
    from source

)

select * from staged
