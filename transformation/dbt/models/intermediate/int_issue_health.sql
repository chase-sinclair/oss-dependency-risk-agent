{{ config(materialized='view') }}

/*
  Issue resolution health metrics per project, aggregated across ALL available data.

  Source events: IssuesEvent (actions: opened, closed)
  Key metrics:
    - issues_opened         : total issues opened
    - issues_closed         : total issues closed
    - issue_resolution_rate : issues_closed / MIN(issues_opened, issues_closed * 3)

  The denominator is capped at issues_closed * 3 so high-volume projects with
  large structural backlogs (e.g. 5k open, 1k closed) are not unfairly penalised.
  Without the cap, such a project would score 0.2; with it the floor is 1/3 = 0.33.
  Rate > 1.0 means the project is closing backlog faster than new issues arrive.
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
        when issues_closed  = 0 then 0.0
        else round(
            cast(issues_closed as double)
            / least(issues_opened, issues_closed * 3),
            4
        )
    end as issue_resolution_rate
from aggregated
