{{ config(materialized='table', file_format='delta') }}

/*
  Gold layer: composite health score (0-10) per project, derived from
  ALL available data (not a single calendar month).

  Active weights (sum = 1.0):
    commit_score:       0.20
    issue_score:        0.15
    pr_score:           0.15
    contributor_score:  0.15
    bus_factor_score:   0.00  (informational only — window-sensitive, not in composite)
    governance_score:   0.20
    security_score:     0.15

  Normalisation to 0-10:
    commit_score      : log10(1 + cpw*50) / log10(501) * 10  (logarithmic; 1/mo→4, 5/mo→6, 20/mo→9, cap at 10)
    issue_score       : min(rate, 1.0) * 10  where rate = closed / min(opened, closed*3)
    pr_score          : min(pr_merge_rate, 1.0) * 10
    contributor_score : min(contributor_count / 20.0, 1.0) * 10   (20+ contributors = max)
    bus_factor_score  : (1.0 - bus_factor_risk) * 10               (inverted: lower risk = better)
    governance_score  : (pts / 12) * 10  where pts = maintained(4) + license(2) + protected(2) + review(2) + sec_policy(2)
    security_score    : vuln_score(0-10)*0.6 + dep_update_score(0 or 10)*0.4
                        vuln_score = max(0, 10 - vuln_count*2); 5.0 fallback when ecosystem unknown
    pr_score          : log10(1 + prs_closed_per_week*50) / log10(501) * 10  (same log scale as commit_score)
                        NULL prs_closed_per_week → 5.0 fallback; 0 closes in window → 0.0

  Null handling: metrics with no data default to 5.0 (neutral) so a single
  absent signal does not collapse the overall score.

  data_days_available: number of distinct event_date values in the source data
  for this project — tells downstream consumers how much history backed the score.

  health_trend: not computable from a single aggregated period. Reserved as
  NULL for future use when historical score snapshots are available.
*/

with base as (

    select * from {{ ref('gold_project_health') }}

),

normalised as (

    select
        repo_full_name,
        org_name,
        repo_name,
        data_days_available,
        first_event_date,
        last_event_date,
        computed_at,

        -- Data coverage flag: false means commit/contributor scores are 5.0 fallbacks
        (commits_per_week is not null) as has_push_data,

        -- Commit frequency: logarithmic scale — 1/mo≈4, 5/mo≈6, 20/mo≈9, ≥40/mo→10
        round(
            case
                when commits_per_week is null then 5.0
                else least(log10(1.0 + commits_per_week * 50.0) / log10(501.0) * 10.0, 10.0)
            end,
            2
        ) as commit_score,

        -- Issue resolution rate: 1.0 (closed = opened) -> score 10
        round(
            case
                when issue_resolution_rate is null then 5.0
                else least(issue_resolution_rate, 1.0) * 10.0
            end,
            2
        ) as issue_score,

        -- PR throughput: log scale on prs_closed_per_week (window-stable vs closed/opened ratio)
        round(
            case
                when prs_closed_per_week is null then 5.0
                else least(log10(1.0 + prs_closed_per_week * 50.0) / log10(501.0) * 10.0, 10.0)
            end,
            2
        ) as pr_score,

        -- Contributor diversity: 20+ distinct contributors -> score 10
        round(
            case
                when contributor_count is null then 5.0
                else least(cast(contributor_count as double) / 20.0, 1.0) * 10.0
            end,
            2
        ) as contributor_score,

        -- Bus factor (inverted): 0.0 risk -> score 10, 1.0 risk -> score 0
        round(
            case
                when bus_factor_risk is null then 5.0
                else (1.0 - bus_factor_risk) * 10.0
            end,
            2
        ) as bus_factor_score,

        -- Governance score: 5.0 neutral fallback when repo not yet in github_scorecard
        round(
            case when governance_score is null then 5.0
                 else governance_score end,
            2
        ) as governance_score,

        -- Security score: 5.0 neutral fallback when repo not yet in github_scorecard
        round(
            case when security_score is null then 5.0
                 else security_score end,
            2
        ) as security_score,

        -- Propagate vuln_data_available for UI amber badge when ecosystem unknown
        coalesce(vuln_data_available, false) as vuln_data_available

    from base

),

scored as (

    select
        *,
        round(
              commit_score      * 0.20
            + issue_score       * 0.15
            + pr_score          * 0.15
            + contributor_score * 0.15
            + bus_factor_score  * 0.00
            + governance_score  * 0.20
            + security_score    * 0.15,
            2
        ) as health_score
    from normalised

)

select
    repo_full_name,
    org_name,
    repo_name,
    health_score,
    cast(null as double)    as health_trend,   -- reserved; requires historical snapshots
    cast(null as double)    as prev_health_score,
    data_days_available,
    first_event_date,
    last_event_date,
    commit_score,
    issue_score,
    pr_score,
    contributor_score,
    bus_factor_score,
    governance_score,
    security_score,
    vuln_data_available,
    has_push_data,
    computed_at
from scored
