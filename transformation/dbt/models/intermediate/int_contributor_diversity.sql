{{ config(materialized='view') }}

/*
  Contributor diversity metrics per project, aggregated across ALL available data.

  Source events: PushEvent
  Key metrics:
    - contributor_count : distinct committers across all data
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
        actor_login,
        coalesce(payload_commits, 1) as commit_count
    from {{ ref('stg_github_events') }}
    where event_type = 'PushEvent'

),

-- Commits per actor per project (across all data)
actor_totals as (

    select
        repo_full_name,
        org_name,
        repo_name,
        actor_login,
        sum(commit_count) as actor_commits
    from push_events
    group by
        repo_full_name,
        org_name,
        repo_name,
        actor_login

),

-- Totals per project
repo_totals as (

    select
        repo_full_name,
        org_name,
        repo_name,
        sum(actor_commits)          as total_commits,
        count(distinct actor_login) as contributor_count
    from actor_totals
    group by
        repo_full_name,
        org_name,
        repo_name

),

-- Top-3 contributors' combined commits per project
top3 as (

    select
        repo_full_name,
        sum(actor_commits) as top3_commits
    from (
        select
            repo_full_name,
            actor_commits,
            row_number() over (
                partition by repo_full_name
                order by actor_commits desc
            ) as rnk
        from actor_totals
    ) ranked
    where rnk <= 3
    group by repo_full_name

)

select
    t.repo_full_name,
    t.org_name,
    t.repo_name,
    t.total_commits,
    t.contributor_count,
    top3.top3_commits,
    round(
        cast(top3.top3_commits as double) / nullif(t.total_commits, 0),
        4
    ) as bus_factor_risk
from repo_totals t
left join top3
    on t.repo_full_name = top3.repo_full_name
