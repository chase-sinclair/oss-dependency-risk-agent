{{ config(materialized='table', file_format='delta') }}

/*
  Gold layer: wide monthly health metrics per project.

  Joins all four intermediate models on (repo_full_name, event_month).
  Left joins ensure every repo/month with ANY event type appears in the
  output, even if it has no issues or PRs in that month.

  Output table: workspace.default.gold_project_health
*/

with all_months as (

    -- Anchor: every distinct repo/month pair seen in any event
    select distinct
        repo_full_name,
        org_name,
        repo_name,
        trunc(event_date, 'MM') as event_month
    from {{ ref('stg_github_events') }}

),

commit_activity as (

    select
        repo_full_name,
        event_month,
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
        event_month,
        issues_opened,
        issues_closed,
        issue_resolution_rate
    from {{ ref('int_issue_health') }}

),

pr_health as (

    select
        repo_full_name,
        event_month,
        prs_opened,
        prs_closed,
        pr_merge_rate
    from {{ ref('int_pr_health') }}

),

contributor_diversity as (

    select
        repo_full_name,
        event_month,
        contributor_count,
        bus_factor_risk
    from {{ ref('int_contributor_diversity') }}

)

select
    m.repo_full_name,
    m.org_name,
    m.repo_name,
    m.event_month,

    -- Commit activity (0 when no PushEvents in month)
    coalesce(c.push_event_count,  0)    as push_event_count,
    coalesce(c.total_commits,     0)    as total_commits,
    coalesce(c.active_committers, 0)    as active_committers,
    coalesce(c.active_days,       0)    as active_days,
    coalesce(c.commits_per_week,  0.0)  as commits_per_week,

    -- Issue health (null when no IssuesEvents in month)
    coalesce(i.issues_opened, 0)        as issues_opened,
    coalesce(i.issues_closed, 0)        as issues_closed,
    i.issue_resolution_rate,

    -- PR health (null when no PullRequestEvents in month)
    coalesce(p.prs_opened, 0)           as prs_opened,
    coalesce(p.prs_closed, 0)           as prs_closed,
    p.pr_merge_rate,

    -- Contributor diversity (null when no PushEvents in month)
    coalesce(d.contributor_count, 0)    as contributor_count,
    d.bus_factor_risk,

    current_timestamp()                 as computed_at

from all_months m
left join commit_activity     c on m.repo_full_name = c.repo_full_name and m.event_month = c.event_month
left join issue_health        i on m.repo_full_name = i.repo_full_name and m.event_month = i.event_month
left join pr_health           p on m.repo_full_name = p.repo_full_name and m.event_month = p.event_month
left join contributor_diversity d on m.repo_full_name = d.repo_full_name and m.event_month = d.event_month
