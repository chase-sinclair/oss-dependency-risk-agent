{{ config(materialized='view') }}

/*
  Pull-request health metrics per project per calendar month.

  Source events: PullRequestEvent (actions: opened, closed)
  Key metrics:
    - prs_opened    : PRs opened in the month
    - prs_closed    : PRs closed in the month (merged OR unmerged)
    - pr_merge_rate : prs_closed / prs_opened  (proxy for merge rate)

  Limitation: the Silver schema captures payload_action ('opened' / 'closed')
  but not the payload.pull_request.merged boolean.  prs_closed therefore
  counts both merged and abandoned PRs.  This is a known approximation —
  refine by adding payload_merged to the Silver schema if needed.
*/

with pr_events as (

    select
        repo_full_name,
        org_name,
        repo_name,
        trunc(event_date, 'MM') as event_month,
        payload_action
    from {{ ref('stg_github_events') }}
    where event_type = 'PullRequestEvent'
      and payload_action in ('opened', 'closed')

),

monthly as (

    select
        repo_full_name,
        org_name,
        repo_name,
        event_month,
        count_if(payload_action = 'opened') as prs_opened,
        count_if(payload_action = 'closed') as prs_closed
    from pr_events
    group by
        repo_full_name,
        org_name,
        repo_name,
        event_month

)

select
    *,
    case
        when prs_opened = 0 then null
        else round(cast(prs_closed as double) / prs_opened, 4)
    end as pr_merge_rate
from monthly
