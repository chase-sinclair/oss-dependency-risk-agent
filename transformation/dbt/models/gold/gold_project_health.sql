{{ config(materialized='table', file_format='delta') }}

/*
  Gold layer: wide health metrics per project, aggregated across ALL available data.

  Joins all four intermediate models on repo_full_name.
  Left joins ensure every repo with ANY event type appears in the output,
  even if it has no issues or PRs.

  data_days_available: how many distinct event_date values exist for the repo
  (used to calibrate commits_per_week and to show data freshness in the UI).

  Output table: workspace.default.gold_project_health
*/

with all_repos as (

    -- Anchor: every distinct repo seen in any event, with date span metadata
    select
        repo_full_name,
        org_name,
        repo_name,
        count(distinct event_date) as data_days_available,
        min(event_date)            as first_event_date,
        max(event_date)            as last_event_date
    from {{ ref('stg_github_events') }}
    group by
        repo_full_name,
        org_name,
        repo_name

),

commit_activity as (

    select
        repo_full_name,
        push_event_count,
        total_commits,
        active_committers,
        active_days,
        commits_per_week
    from {{ ref('int_commit_activity') }}

),

issue_health as (

    select
        repo_full_name,
        issues_opened,
        issues_closed,
        issue_resolution_rate
    from {{ ref('int_issue_health') }}

),

pr_health as (

    select
        repo_full_name,
        prs_opened,
        prs_closed,
        pr_merge_rate
    from {{ ref('int_pr_health') }}

),

contributor_diversity as (

    select
        repo_full_name,
        contributor_count,
        bus_factor_risk
    from {{ ref('int_contributor_diversity') }}

)

select
    m.repo_full_name,
    m.org_name,
    m.repo_name,
    m.data_days_available,
    m.first_event_date,
    m.last_event_date,

    -- Commit activity (NULL when no PushEvents — preserved so gold_health_scores
    -- can apply the 5.0 neutral fallback instead of scoring 0)
    coalesce(c.push_event_count,  0) as push_event_count,
    coalesce(c.total_commits,     0) as total_commits,
    coalesce(c.active_committers, 0) as active_committers,
    coalesce(c.active_days,       0) as active_days,
    c.commits_per_week,

    -- Issue health (null when no IssuesEvents)
    coalesce(i.issues_opened, 0)       as issues_opened,
    coalesce(i.issues_closed, 0)       as issues_closed,
    i.issue_resolution_rate,

    -- PR health (null when no PullRequestEvents)
    coalesce(p.prs_opened, 0)          as prs_opened,
    coalesce(p.prs_closed, 0)          as prs_closed,
    p.pr_merge_rate,

    -- Contributor diversity (null when no PushEvents)
    d.contributor_count,
    d.bus_factor_risk,

    current_timestamp()                as computed_at

from all_repos m
left join commit_activity      c on m.repo_full_name = c.repo_full_name
left join issue_health         i on m.repo_full_name = i.repo_full_name
left join pr_health            p on m.repo_full_name = p.repo_full_name
left join contributor_diversity d on m.repo_full_name = d.repo_full_name
