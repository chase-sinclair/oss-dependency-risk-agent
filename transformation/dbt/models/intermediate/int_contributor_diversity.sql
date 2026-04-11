{{ config(materialized='view') }}

/*
  Contributor diversity metrics per project per calendar month.

  Source events: PushEvent
  Key metrics:
    - contributor_count : distinct committers in the month
    - top3_commits      : commits attributed to the top-3 contributors
    - bus_factor_risk   : top3_commits / total_commits  (0.0 – 1.0)
                          higher = more concentrated = higher risk

  A bus_factor_risk of 1.0 means one person made all commits.
  The gold scoring layer inverts this: score = (1 - bus_factor_risk) * 10.
*/

with push_events as (

    select
        repo_full_name,
        org_name,
        repo_name,
        trunc(event_date, 'MM')         as event_month,
        actor_login,
        coalesce(payload_commits, 1)    as commit_count
    from {{ ref('stg_github_events') }}
    where event_type = 'PushEvent'

),

-- Commits per actor per project per month
actor_monthly as (

    select
        repo_full_name,
        org_name,
        repo_name,
        event_month,
        actor_login,
        sum(commit_count) as actor_commits
    from push_events
    group by
        repo_full_name,
        org_name,
        repo_name,
        event_month,
        actor_login

),

-- Totals per project per month
monthly_totals as (

    select
        repo_full_name,
        org_name,
        repo_name,
        event_month,
        sum(actor_commits)          as total_commits,
        count(distinct actor_login) as contributor_count
    from actor_monthly
    group by
        repo_full_name,
        org_name,
        repo_name,
        event_month

),

-- Top-3 contributors' combined commits per project per month
top3 as (

    select
        repo_full_name,
        event_month,
        sum(actor_commits) as top3_commits
    from (
        select
            repo_full_name,
            event_month,
            actor_commits,
            row_number() over (
                partition by repo_full_name, event_month
                order by actor_commits desc
            ) as rnk
        from actor_monthly
    ) ranked
    where rnk <= 3
    group by repo_full_name, event_month

)

select
    t.repo_full_name,
    t.org_name,
    t.repo_name,
    t.event_month,
    t.total_commits,
    t.contributor_count,
    top3.top3_commits,
    round(
        cast(top3.top3_commits as double) / nullif(t.total_commits, 0),
        4
    ) as bus_factor_risk
from monthly_totals t
left join top3
    on t.repo_full_name = top3.repo_full_name
    and t.event_month   = top3.event_month
