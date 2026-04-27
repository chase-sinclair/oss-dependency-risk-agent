{{ config(materialized='view') }}

/*
  Pull-request health metrics per project, aggregated across ALL available data.

  Source events: PullRequestEvent (actions: opened, closed)
  Key metrics:
    - prs_opened          : total PRs opened
    - prs_closed          : total PRs closed (merged OR unmerged)
    - active_days         : distinct event dates with any PR activity
    - prs_closed_per_week : prs_closed / active_days * 7  (throughput rate)
    - pr_merge_rate       : prs_closed / prs_opened (retained for reference)

  pr_score in gold_health_scores uses prs_closed_per_week on a log scale
  (same approach as commit_score) rather than the closed/opened ratio.
  Rationale: the ratio penalises repos where PRs span the Silver window
  boundary — many opens in the window, merges outside it. Throughput rate
  is stable regardless of window edge effects.
*/

with pr_events as (

    select
        repo_full_name,
        org_name,
        repo_name,
        payload_action,
        event_date
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
        count_if(payload_action = 'closed') as prs_closed,
        count(distinct event_date)          as active_days
    from pr_events
    group by
        repo_full_name,
        org_name,
        repo_name

)

select
    *,
    round(
        cast(prs_closed as double) / nullif(active_days, 0) * 7.0,
        2
    ) as prs_closed_per_week,
    case
        when prs_opened = 0 then null
        else round(cast(prs_closed as double) / prs_opened, 4)
    end as pr_merge_rate
from aggregated
