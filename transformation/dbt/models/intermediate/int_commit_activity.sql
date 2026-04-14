{{ config(materialized='view') }}

/*
  Commit activity metrics per project, aggregated across ALL available data.

  Source events: PushEvent
  Key metrics:
    - push_event_count   : number of push events
    - total_commits      : sum of commits across all push events
    - active_committers  : distinct actors who pushed
    - active_days        : distinct calendar days with at least one push
    - data_days_available: distinct days with any event for this repo
    - commits_per_week   : total_commits / active_days * 7
                           (uses actual data span, not a hardcoded 30-day window)
*/

with push_events as (

    select
        repo_full_name,
        org_name,
        repo_name,
        actor_login,
        coalesce(payload_commits, 1) as commit_count,
        event_date
    from {{ ref('stg_github_events') }}
    where event_type = 'PushEvent'

),

aggregated as (

    select
        repo_full_name,
        org_name,
        repo_name,
        count(*)                        as push_event_count,
        sum(commit_count)               as total_commits,
        count(distinct actor_login)     as active_committers,
        count(distinct event_date)      as active_days
    from push_events
    group by
        repo_full_name,
        org_name,
        repo_name

)

select
    *,
    round(
        cast(total_commits as double) / nullif(active_days, 0) * 7.0,
        2
    ) as commits_per_week
from aggregated
