{{ config(materialized='view') }}

/*
  Pull-request health metrics per project, aggregated across ALL available data.

  Source events: PullRequestEvent (actions: opened, closed)
  Key metrics:
    - prs_opened    : total PRs opened
    - prs_closed    : total PRs closed (merged OR unmerged)
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
        payload_action
    from {{ ref('stg_github_events') }}
    where event_type = 'PullRequestEvent'
      and payload_action in ('opened', 'closed')

),

aggregated as (

    select
        repo_full_name,
        org_name,
        repo_name,
        count_if(payload_action = 'opened') as prs_opened,
        count_if(payload_action = 'closed') as prs_closed
    from pr_events
    group by
        repo_full_name,
        org_name,
        repo_name

)

select
    *,
    case
        when prs_opened = 0 then null
        else round(cast(prs_closed as double) / prs_opened, 4)
    end as pr_merge_rate
from aggregated
