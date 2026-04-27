{{ config(materialized='view') }}

/*
  Security score (0-10) per project, sourced from github_scorecard
  (populated by scripts/run_scorecard.py via GitHub REST API + OSV).

  Components:
    vuln_score      (0-10) — 10 - vuln_count*2, floored at 0
                             Falls back to 5.0 when vuln_data_available=false
                             (ecosystem unknown → amber badge in UI, not 0)
    dep_update_score (0 or 10) — 10 if Dependabot/Renovate present, else 0

  Composite: vuln_score * 0.6 + dep_update_score * 0.4

  Repos not yet in github_scorecard produce no row; gold_project_health
  left-joins this view so those repos receive NULL security_score, which
  gold_health_scores coalesces to 5.0 (neutral fallback).
*/

with scorecard as (

    -- External table populated by scripts/run_scorecard.py
    select * from workspace.default.github_scorecard

),

scored as (

    select
        repo_full_name,
        vuln_count,
        vuln_data_available,
        has_dep_update_tool,

        round(
            case
                when not vuln_data_available or vuln_count is null then 5.0
                else greatest(0.0, 10.0 - cast(vuln_count as double) * 2.0)
            end,
            2
        ) as vuln_score,

        round(
            case when has_dep_update_tool = true then 10.0 else 0.0 end,
            2
        ) as dep_update_score

    from scorecard

),

final as (

    select
        *,
        round(vuln_score * 0.6 + dep_update_score * 0.4, 2) as security_score
    from scored

)

select * from final
