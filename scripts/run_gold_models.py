"""
Run all 9 dbt models directly via the Databricks REST API.

Replaces `dbt run` for this warehouse, which only accepts REST connections
(Databricks SDK) and rejects the Thrift connections used by databricks-sql-connector.

Execution order matches the dbt DAG:
  1. stg_github_events          (VIEW  — dedup over silver)
  2. int_commit_activity         (VIEW  — PushEvent aggregates)
  3. int_issue_health            (VIEW  — IssuesEvent aggregates)
  4. int_pr_health               (VIEW  — PullRequestEvent aggregates)
  5. int_contributor_diversity   (VIEW  — bus factor over PushEvents)
  6. int_governance              (VIEW  — governance score from github_scorecard)
  7. int_security                (VIEW  — security score from github_scorecard + OSV)
  8. gold_project_health         (DELTA TABLE — wide metrics per project)
  9. gold_health_scores          (DELTA TABLE — composite 0-10 scores + flags)

Usage:
    python scripts/run_gold_models.py
    python scripts/run_gold_models.py --dry-run
    python scripts/run_gold_models.py --select gold_project_health gold_health_scores
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from agent.tools.databricks_query import query_databricks  # noqa: E402

CATALOG = "workspace"
SCHEMA  = "default"


def fqn(table: str) -> str:
    return f"{CATALOG}.{SCHEMA}.{table}"


# ---------------------------------------------------------------------------
# 1. stg_github_events  (VIEW)
# ---------------------------------------------------------------------------

STG_GITHUB_EVENTS_SQL = f"""
CREATE OR REPLACE VIEW {fqn("stg_github_events")} AS
with source as (
    select * from {fqn("silver_github_events")}
),
deduped as (
    select *,
        row_number() over (
            partition by event_id
            order by ingested_at desc
        ) as _row_num
    from source
),
staged as (
    select
        event_id, event_type, actor_login, actor_id,
        repo_full_name, repo_id, created_at, event_date,
        payload_action, payload_commits,
        org_name, repo_name, ingested_at
    from deduped
    where _row_num = 1
)
select * from staged
"""


# ---------------------------------------------------------------------------
# 2. int_commit_activity  (VIEW)
# ---------------------------------------------------------------------------

INT_COMMIT_ACTIVITY_SQL = f"""
CREATE OR REPLACE VIEW {fqn("int_commit_activity")} AS
with push_events as (
    select
        repo_full_name, org_name, repo_name, actor_login,
        coalesce(payload_commits, 1) as commit_count,
        event_date
    from {fqn("stg_github_events")}
    where event_type = 'PushEvent'
),
aggregated as (
    select
        repo_full_name, org_name, repo_name,
        count(*)                    as push_event_count,
        sum(commit_count)           as total_commits,
        count(distinct actor_login) as active_committers,
        count(distinct event_date)  as active_days
    from push_events
    group by repo_full_name, org_name, repo_name
)
select
    *,
    round(
        cast(total_commits as double) / nullif(active_days, 0) * 7.0,
        2
    ) as commits_per_week
from aggregated
"""


# ---------------------------------------------------------------------------
# 3. int_issue_health  (VIEW)
# ---------------------------------------------------------------------------

INT_ISSUE_HEALTH_SQL = f"""
CREATE OR REPLACE VIEW {fqn("int_issue_health")} AS
with issue_events as (
    select repo_full_name, org_name, repo_name, payload_action
    from {fqn("stg_github_events")}
    where event_type = 'IssuesEvent'
      and payload_action in ('opened', 'closed')
),
aggregated as (
    select
        repo_full_name, org_name, repo_name,
        count_if(payload_action = 'opened') as issues_opened,
        count_if(payload_action = 'closed') as issues_closed
    from issue_events
    group by repo_full_name, org_name, repo_name
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
"""


# ---------------------------------------------------------------------------
# 4. int_pr_health  (VIEW)
# ---------------------------------------------------------------------------

INT_PR_HEALTH_SQL = f"""
CREATE OR REPLACE VIEW {fqn("int_pr_health")} AS
with pr_events as (
    select repo_full_name, org_name, repo_name, payload_action, event_date
    from {fqn("stg_github_events")}
    where event_type = 'PullRequestEvent'
      and payload_action in ('opened', 'closed')
),
aggregated as (
    select
        repo_full_name, org_name, repo_name,
        count_if(payload_action = 'opened') as prs_opened,
        count_if(payload_action = 'closed') as prs_closed,
        count(distinct event_date)          as active_days
    from pr_events
    group by repo_full_name, org_name, repo_name
)
select
    *,
    round(cast(prs_closed as double) / nullif(active_days, 0) * 7.0, 2) as prs_closed_per_week,
    case
        when prs_opened = 0 then null
        else round(cast(prs_closed as double) / prs_opened, 4)
    end as pr_merge_rate
from aggregated
"""


# ---------------------------------------------------------------------------
# 5. int_contributor_diversity  (VIEW)
# ---------------------------------------------------------------------------

INT_CONTRIBUTOR_DIVERSITY_SQL = f"""
CREATE OR REPLACE VIEW {fqn("int_contributor_diversity")} AS
with push_events as (
    select
        repo_full_name, org_name, repo_name, actor_login,
        coalesce(payload_commits, 1) as commit_count
    from {fqn("stg_github_events")}
    where event_type = 'PushEvent'
),
actor_totals as (
    select
        repo_full_name, org_name, repo_name, actor_login,
        sum(commit_count) as actor_commits
    from push_events
    group by repo_full_name, org_name, repo_name, actor_login
),
repo_totals as (
    select
        repo_full_name, org_name, repo_name,
        sum(actor_commits)          as total_commits,
        count(distinct actor_login) as contributor_count
    from actor_totals
    group by repo_full_name, org_name, repo_name
),
top3 as (
    select repo_full_name, sum(actor_commits) as top3_commits
    from (
        select
            repo_full_name, actor_commits,
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
    t.repo_full_name, t.org_name, t.repo_name,
    t.total_commits, t.contributor_count, top3.top3_commits,
    round(
        cast(top3.top3_commits as double) / nullif(t.total_commits, 0),
        4
    ) as bus_factor_risk
from repo_totals t
left join top3 on t.repo_full_name = top3.repo_full_name
"""


# ---------------------------------------------------------------------------
# 6. int_governance  (VIEW)
# ---------------------------------------------------------------------------

INT_GOVERNANCE_SQL = f"""
CREATE OR REPLACE VIEW {fqn("int_governance")} AS
with scorecard as (
    select * from {fqn("github_scorecard")}
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
"""


# ---------------------------------------------------------------------------
# 7. int_security  (VIEW)
# ---------------------------------------------------------------------------

INT_SECURITY_SQL = f"""
CREATE OR REPLACE VIEW {fqn("int_security")} AS
with scorecard as (
    select * from {fqn("github_scorecard")}
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
            end, 2
        ) as vuln_score,
        round(
            case when has_dep_update_tool = true then 10.0 else 0.0 end, 2
        ) as dep_update_score
    from scorecard
),
final as (
    select *,
        round(vuln_score * 0.6 + dep_update_score * 0.4, 2) as security_score
    from scored
)
select * from final
"""


# ---------------------------------------------------------------------------
# 8. gold_project_health  (DELTA TABLE)
# ---------------------------------------------------------------------------

GOLD_PROJECT_HEALTH_SQL = f"""
CREATE OR REPLACE TABLE {fqn("gold_project_health")}
USING DELTA
AS
with all_repos as (
    select
        repo_full_name, org_name, repo_name,
        count(distinct event_date) as data_days_available,
        min(event_date)            as first_event_date,
        max(event_date)            as last_event_date
    from {fqn("stg_github_events")}
    group by repo_full_name, org_name, repo_name
),
commit_activity as (
    select repo_full_name, push_event_count, total_commits,
           active_committers, active_days, commits_per_week
    from {fqn("int_commit_activity")}
),
issue_health as (
    select repo_full_name, issues_opened, issues_closed, issue_resolution_rate
    from {fqn("int_issue_health")}
),
pr_health as (
    select repo_full_name, prs_opened, prs_closed, prs_closed_per_week, pr_merge_rate
    from {fqn("int_pr_health")}
),
contributor_diversity as (
    select repo_full_name, contributor_count, bus_factor_risk
    from {fqn("int_contributor_diversity")}
),
governance as (
    select repo_full_name, governance_score,
           is_maintained, has_license, is_branch_protected,
           requires_code_review, has_security_policy
    from {fqn("int_governance")}
),
security as (
    select repo_full_name, security_score,
           vuln_count, vuln_data_available, has_dep_update_tool
    from {fqn("int_security")}
)
select
    m.repo_full_name, m.org_name, m.repo_name,
    m.data_days_available, m.first_event_date, m.last_event_date,

    coalesce(c.push_event_count,  0) as push_event_count,
    coalesce(c.total_commits,     0) as total_commits,
    coalesce(c.active_committers, 0) as active_committers,
    coalesce(c.active_days,       0) as active_days,
    c.commits_per_week,

    coalesce(i.issues_opened, 0)     as issues_opened,
    coalesce(i.issues_closed, 0)     as issues_closed,
    i.issue_resolution_rate,

    coalesce(p.prs_opened, 0)        as prs_opened,
    coalesce(p.prs_closed, 0)        as prs_closed,
    p.prs_closed_per_week,
    p.pr_merge_rate,

    d.contributor_count,
    d.bus_factor_risk,

    g.governance_score,
    g.is_maintained,
    g.has_license,
    g.is_branch_protected,
    g.requires_code_review,
    g.has_security_policy,

    s.security_score,
    s.vuln_count,
    s.vuln_data_available,
    s.has_dep_update_tool,

    current_timestamp()              as computed_at

from all_repos m
left join commit_activity       c on m.repo_full_name = c.repo_full_name
left join issue_health          i on m.repo_full_name = i.repo_full_name
left join pr_health             p on m.repo_full_name = p.repo_full_name
left join contributor_diversity d on m.repo_full_name = d.repo_full_name
left join governance            g on m.repo_full_name = g.repo_full_name
left join security              s on m.repo_full_name = s.repo_full_name
"""


# ---------------------------------------------------------------------------
# 9. gold_health_scores  (DELTA TABLE)
# ---------------------------------------------------------------------------

GOLD_HEALTH_SCORES_SQL = f"""
CREATE OR REPLACE TABLE {fqn("gold_health_scores")}
USING DELTA
AS
with base as (
    select * from {fqn("gold_project_health")}
),
normalised as (
    select
        repo_full_name, org_name, repo_name,
        data_days_available, first_event_date, last_event_date, computed_at,

        (commits_per_week is not null) as has_push_data,

        round(
            case when commits_per_week is null then 5.0
                 else least(log10(1.0 + commits_per_week * 50.0) / log10(501.0) * 10.0, 10.0)
            end, 2
        ) as commit_score,

        round(
            case when issue_resolution_rate is null then 5.0
                 else least(issue_resolution_rate, 1.0) * 10.0 end, 2
        ) as issue_score,

        round(
            case when prs_closed_per_week is null then 5.0
                 else least(log10(1.0 + prs_closed_per_week * 50.0) / log10(501.0) * 10.0, 10.0)
            end, 2
        ) as pr_score,

        round(
            case when contributor_count is null then 5.0
                 else least(cast(contributor_count as double) / 20.0, 1.0) * 10.0 end, 2
        ) as contributor_score,

        round(
            case when bus_factor_risk is null then 5.0
                 else (1.0 - bus_factor_risk) * 10.0 end, 2
        ) as bus_factor_score,

        round(
            case when governance_score is null then 5.0
                 else governance_score end, 2
        ) as governance_score,

        round(
            case when security_score is null then 5.0
                 else security_score end, 2
        ) as security_score,

        coalesce(vuln_data_available, false) as vuln_data_available

    from base
),
scored as (
    select *,
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
    repo_full_name, org_name, repo_name,
    health_score,
    cast(null as double) as health_trend,
    cast(null as double) as prev_health_score,
    data_days_available, first_event_date, last_event_date,
    commit_score, issue_score, pr_score, contributor_score, bus_factor_score,
    governance_score, security_score,
    vuln_data_available,
    has_push_data,
    computed_at
from scored
"""


# ---------------------------------------------------------------------------
# Model registry — ordered by DAG dependency
# ---------------------------------------------------------------------------

ALL_MODELS: list[tuple[str, str]] = [
    ("stg_github_events",        STG_GITHUB_EVENTS_SQL),
    ("int_commit_activity",      INT_COMMIT_ACTIVITY_SQL),
    ("int_issue_health",         INT_ISSUE_HEALTH_SQL),
    ("int_pr_health",            INT_PR_HEALTH_SQL),
    ("int_contributor_diversity",INT_CONTRIBUTOR_DIVERSITY_SQL),
    ("int_governance",           INT_GOVERNANCE_SQL),
    ("int_security",             INT_SECURITY_SQL),
    ("gold_project_health",      GOLD_PROJECT_HEALTH_SQL),
    ("gold_health_scores",       GOLD_HEALTH_SCORES_SQL),
]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run(select: list[str] | None, dry_run: bool) -> None:
    models = (
        [(n, s) for n, s in ALL_MODELS if n in select]
        if select else ALL_MODELS
    )

    if not models:
        print(f"No models matched --select {select}. Available: {[n for n,_ in ALL_MODELS]}")
        sys.exit(1)

    for name, sql in models:
        kind = "VIEW" if name.startswith(("stg_", "int_")) else "DELTA TABLE"
        prefix = f"[{name}] ({kind})"
        if dry_run:
            print(f"{prefix} DRY RUN — skipping")
            continue
        print(f"{prefix} Running...", end=" ", flush=True)
        try:
            query_databricks(sql)
            print("OK")
        except RuntimeError as exc:
            print(f"FAILED\n  {exc}")
            sys.exit(1)

    if dry_run:
        print("\nDry run complete — no objects were modified.")
        return

    print("\nAll models complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run dbt models via the Databricks REST API (bypasses Thrift).",
    )
    parser.add_argument(
        "--select", nargs="+", metavar="MODEL",
        help="Run only the named models (space-separated). Runs all 7 if omitted.",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(select=args.select, dry_run=args.dry_run)
