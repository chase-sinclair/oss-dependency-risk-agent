{{ config(materialized='view') }}

/*
  Issue resolution health metrics per project, aggregated across ALL available data.

  Source events: IssuesEvent (actions: opened, closed)
  Key metrics:
    - issues_opened         : total issues opened
    - issues_closed         : total issues closed
    - issue_resolution_rate : issues_closed / issues_opened  (0.0 – ∞, ideally >= 1.0)

  Note: resolution rate > 1.0 means the project is closing backlog issues
  faster than new ones arrive, which is healthy.  The gold scoring layer
  caps the normalised score at 10.
*/

with issue_events as (

    select
        repo_full_name,
        org_name,
        repo_name,
        payload_action
    from {{ ref('stg_github_events') }}
    where event_type = 'IssuesEvent'
      and payload_action in ('opened', 'closed')

),

aggregated as (

    select
        repo_full_name,
        org_name,
        repo_name,
        count_if(payload_action = 'opened') as issues_opened,
        count_if(payload_action = 'closed') as issues_closed
    from issue_events
    group by
        repo_full_name,
        org_name,
        repo_name

)

select
    *,
    case
        when issues_opened = 0 then null
        else round(cast(issues_closed as double) / issues_opened, 4)
    end as issue_resolution_rate
from aggregated
