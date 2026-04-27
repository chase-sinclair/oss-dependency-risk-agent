{{ config(materialized='view') }}

/*
  Governance score (0-10) per project, sourced from github_scorecard
  (populated by scripts/run_scorecard.py via GitHub REST API).

  Point allocation (total = 12, normalised to 0-10):
    is_maintained        4 pts  — any push/commit within last 90 days
    has_license          2 pts  — license file detected by GitHub
    is_branch_protected  2 pts  — default branch has protection rules
    requires_code_review 2 pts  — PRs required before merging
    has_security_policy  2 pts  — SECURITY.md present

  Repos not yet in github_scorecard produce no row here; gold_project_health
  left-joins this view so those repos receive NULL governance_score, which
  gold_health_scores coalesces to 5.0 (neutral fallback).
*/

with scorecard as (

    -- External table populated by scripts/run_scorecard.py
    select * from workspace.default.github_scorecard

),

scored as (

    select
        repo_full_name,
        is_maintained,
        has_license,
        is_branch_protected,
        requires_code_review,
        has_security_policy,

        round(
            (
                  (case when is_maintained        = true then 4 else 0 end)
                + (case when has_license           = true then 2 else 0 end)
                + (case when is_branch_protected   = true then 2 else 0 end)
                + (case when requires_code_review  = true then 2 else 0 end)
                + (case when has_security_policy   = true then 2 else 0 end)
            ) / 12.0 * 10.0,
            2
        ) as governance_score

    from scorecard

)

select * from scored
