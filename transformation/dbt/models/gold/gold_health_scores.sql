{{ config(materialized='table', file_format='delta') }}

/*
  Gold layer: composite health score (0–10) per project per month.

  Weights (must sum to 1.0):
    commit_frequency      25%
    issue_resolution_rate 20%
    pr_merge_rate         20%
    contributor_count     20%
    bus_factor_risk       15%

  Normalisation to 0–10:
    commit_score      : min(commits_per_week / 10.0, 1.0) * 10   — cap at 10 commits/week
    issue_score       : min(issue_resolution_rate, 1.0) * 10      — rate > 1.0 is capped
    pr_score          : min(pr_merge_rate, 1.0) * 10
    contributor_score : min(contributor_count / 20.0, 1.0) * 10   — 20+ contributors = max
    bus_factor_score  : (1.0 - bus_factor_risk) * 10              — inverted: lower risk = better

  Null handling: metrics with no data for the month default to 5.0 (neutral)
  so a single absent signal does not collapse the overall score.

  health_trend: month-over-month change in health_score (null for first month seen).
*/

with base as (

    select * from {{ ref('gold_project_health') }}

),

normalised as (

    select
        repo_full_name,
        org_name,
        repo_name,
        event_month,
        computed_at,

        -- Commit frequency: 10 commits/week → score 10
        round(least(commits_per_week / 10.0, 1.0) * 10.0, 2)
            as commit_score,

        -- Issue resolution rate: 1.0 (closed = opened) → score 10
        round(
            case
                when issue_resolution_rate is null then 5.0
                else least(issue_resolution_rate, 1.0) * 10.0
            end,
            2
        ) as issue_score,

        -- PR merge rate: 1.0 → score 10
        round(
            case
                when pr_merge_rate is null then 5.0
                else least(pr_merge_rate, 1.0) * 10.0
            end,
            2
        ) as pr_score,

        -- Contributor diversity: 20+ distinct contributors → score 10
        round(least(cast(contributor_count as double) / 20.0, 1.0) * 10.0, 2)
            as contributor_score,

        -- Bus factor (inverted): 0.0 risk → score 10, 1.0 risk → score 0
        round(
            case
                when bus_factor_risk is null then 5.0
                else (1.0 - bus_factor_risk) * 10.0
            end,
            2
        ) as bus_factor_score

    from base

),

scored as (

    select
        *,
        round(
              commit_score      * 0.25
            + issue_score       * 0.20
            + pr_score          * 0.20
            + contributor_score * 0.20
            + bus_factor_score  * 0.15,
            2
        ) as health_score
    from normalised

),

with_trend as (

    select
        *,
        lag(health_score) over (
            partition by repo_full_name
            order by event_month
        ) as prev_health_score,

        round(
            health_score - lag(health_score) over (
                partition by repo_full_name
                order by event_month
            ),
            2
        ) as health_trend
    from scored

)

select
    repo_full_name,
    org_name,
    repo_name,
    event_month,
    health_score,
    health_trend,
    prev_health_score,
    commit_score,
    issue_score,
    pr_score,
    contributor_score,
    bus_factor_score,
    computed_at
from with_trend
