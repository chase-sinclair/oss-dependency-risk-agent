"""
Diagnose Silver coverage for a set of repos.

Answers two questions:
  1. Do boto/boto3 and pytest-dev/pytest have PushEvents in Silver?
     - If yes but still null in Gold: join bug
     - If no: genuine data gap, 5.0 is a fallback not a real score

  2. Across ALL 800 projects, how many are hitting the NULL guard
     (commit_score or contributor_score is exactly 5.0 because the
     column is NULL in gold_project_health) vs. carrying a real score?

Usage:
    python scripts/diagnose_silver_coverage.py
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from agent.tools.databricks_query import query_databricks  # noqa: E402

FOCUS_REPOS = ["boto/boto3", "pytest-dev/pytest"]


# ── helpers ──────────────────────────────────────────────────────────────────

def section(title: str) -> None:
    print(f"\n{'-' * 64}")
    print(f"  {title}")
    print('-' * 64)


def _fmt(rows: list[dict]) -> None:
    if not rows:
        print("  (no rows)")
        return
    cols = list(rows[0].keys())
    widths = {c: max(len(c), max((len(str(r.get(c) or "")) for r in rows), default=0)) for c in cols}
    header = "  " + "  ".join(c.ljust(widths[c]) for c in cols)
    print(header)
    print("  " + "  ".join("-" * widths[c] for c in cols))
    for r in rows:
        print("  " + "  ".join(str(r.get(c) or "NULL").ljust(widths[c]) for c in cols))


# ── SECTION 1: Silver event summary for focus repos ──────────────────────────

section("1. Silver event counts for focus repos")

repo_list = ", ".join(f"'{r}'" for r in FOCUS_REPOS)

silver_summary = query_databricks(f"""
SELECT
    repo_full_name,
    event_type,
    COUNT(*)            AS event_count,
    COUNT(DISTINCT actor_login) AS distinct_actors,
    MIN(event_date)     AS earliest,
    MAX(event_date)     AS latest
FROM workspace.default.silver_github_events
WHERE repo_full_name IN ({repo_list})
GROUP BY repo_full_name, event_type
ORDER BY repo_full_name, event_type
""")
_fmt(silver_summary)

push_repos = {
    r["repo_full_name"]
    for r in silver_summary
    if r["event_type"] == "PushEvent"
}

print()
for repo in FOCUS_REPOS:
    has_push = repo in push_repos
    verdict = "HAS PushEvents in Silver" if has_push else "NO PushEvents in Silver"
    print(f"  {repo}: {verdict}")


# ── SECTION 2: Gold intermediate tables for focus repos ──────────────────────

section("2. Gold intermediate models for focus repos")

print("\n  int_commit_activity:")
commit_int = query_databricks(f"""
SELECT repo_full_name, push_event_count, total_commits,
       active_committers, commits_per_week
FROM workspace.default.int_commit_activity
WHERE repo_full_name IN ({repo_list})
""")
_fmt(commit_int)

print("\n  int_contributor_diversity:")
contrib_int = query_databricks(f"""
SELECT repo_full_name, contributor_count, bus_factor_risk
FROM workspace.default.int_contributor_diversity
WHERE repo_full_name IN ({repo_list})
""")
_fmt(contrib_int)


# ── SECTION 3: Gold health for focus repos ───────────────────────────────────

section("3. gold_project_health + gold_health_scores for focus repos")

gold = query_databricks(f"""
SELECT
    h.repo_full_name,
    h.commits_per_week,
    h.contributor_count,
    h.bus_factor_risk,
    s.commit_score,
    s.contributor_score,
    s.bus_factor_score,
    s.health_score
FROM workspace.default.gold_project_health  h
JOIN workspace.default.gold_health_scores   s USING (repo_full_name)
WHERE h.repo_full_name IN ({repo_list})
""")
_fmt(gold)

print()
for r in gold:
    repo = r["repo_full_name"]
    cpw  = r.get("commits_per_week")
    cc   = r.get("contributor_count")
    cs   = r.get("commit_score")
    cons = r.get("contributor_score")
    notes = []
    if cpw in (None, "NULL"):
        notes.append("commits_per_week=NULL -> 5.0 fallback")
    else:
        notes.append(f"commits_per_week={cpw} (real data)")
    if cc in (None, "NULL"):
        notes.append("contributor_count=NULL -> 5.0 fallback")
    else:
        notes.append(f"contributor_count={cc} (real data)")
    print(f"  {repo}: commit_score={cs}, contributor_score={cons}")
    for n in notes:
        print(f"    -> {n}")


# ── SECTION 4: Portfolio-wide NULL-guard exposure ────────────────────────────

section("4. Portfolio-wide: real scores vs. NULL-guard fallbacks (5.0)")

coverage = query_databricks("""
SELECT
    CASE
        WHEN h.commits_per_week   IS NULL THEN 'no_push_events'
        ELSE 'has_push_events'
    END AS push_coverage,
    CASE
        WHEN h.contributor_count  IS NULL THEN 'no_contributor_data'
        ELSE 'has_contributor_data'
    END AS contrib_coverage,
    COUNT(*)            AS project_count,
    ROUND(AVG(CAST(s.commit_score AS DOUBLE)), 2)      AS avg_commit_score,
    ROUND(AVG(CAST(s.contributor_score AS DOUBLE)), 2) AS avg_contributor_score,
    ROUND(AVG(CAST(s.health_score AS DOUBLE)), 2)      AS avg_health_score
FROM workspace.default.gold_project_health h
JOIN workspace.default.gold_health_scores  s USING (repo_full_name)
GROUP BY push_coverage, contrib_coverage
ORDER BY project_count DESC
""")
_fmt(coverage)

total_rows = query_databricks("""
SELECT COUNT(*) AS total FROM workspace.default.gold_health_scores
""")
total = total_rows[0]["total"] if total_rows else "?"

no_push = next(
    (int(r["project_count"]) for r in coverage if r["push_coverage"] == "no_push_events"),
    0
)
has_push = next(
    (int(r["project_count"]) for r in coverage if r["push_coverage"] == "has_push_events"),
    0
)

print(
    "\n  Portfolio summary\n"
    "  -----------------\n"
    f"  Total scored projects             : {total}\n"
    f"  Has real PushEvent data           : {has_push}\n"
    f"  No PushEvents (NULL guard firing) : {no_push}\n"
)

if no_push > 0:
    pct = round(no_push / int(total) * 100, 1) if total != "?" else "?"
    print(f"  WARNING: {pct}% of the portfolio is scoring commit/contributor on the 5.0 fallback.")
    print("     Consider surfacing a 'data coverage' flag in the UI for these projects.")
else:
    print("  OK: All scored projects have real PushEvent data.")


# ── SECTION 5: Sample of projects hitting the NULL guard ─────────────────────

if no_push > 0:
    section("5. Sample projects hitting the NULL guard (up to 20)")

    sample = query_databricks("""
    SELECT
        h.repo_full_name,
        h.commits_per_week,
        h.contributor_count,
        s.commit_score,
        s.contributor_score,
        s.health_score
    FROM workspace.default.gold_project_health h
    JOIN workspace.default.gold_health_scores  s USING (repo_full_name)
    WHERE h.commits_per_week IS NULL
       OR h.contributor_count IS NULL
    ORDER BY s.health_score DESC
    LIMIT 20
    """)
    _fmt(sample)

print("\n  Done.\n")
