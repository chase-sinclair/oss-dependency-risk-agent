{{ config(materialized='view') }}

/*
  Commit activity metrics per project per calendar month.

  Source events: PushEvent
  Key metrics:
    - push_event_count   : number of push events
    - total_commits      : sum of commits across all push events
    - active_committers  : distinct actors who pushed
    - active_days        : distinct calendar days with at least one push
    - commits_per_week   : estimated weekly commit cadence (total / 30 * 7)
*/

with push_events as (

    select
        repo_full_name,
        org_name,
        repo_name,
        trunc(event_date, 'MM')         as event_month,
        actor_login,
        coalesce(payload_commits, 1)    as commit_count,
        event_date
    from {{ ref('stg_github_events') }}
    where event_type = 'PushEvent'

),

monthly as (

    select
        repo_full_name,
        org_name,
        repo_name,
        event_month,
        count(*)                            as push_event_count,
        sum(commit_count)                   as total_commits,
        count(distinct actor_login)         as active_committers,
        count(distinct event_date)          as active_days
    from push_events
    group by
        repo_full_name,
        org_name,
        repo_name,
        event_month

)

select
    *,
    round(cast(total_commits as double) / 30.0 * 7.0, 2) as commits_per_week
from monthly
