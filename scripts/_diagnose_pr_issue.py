import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
load_dotenv()
from agent.tools.databricks_query import query_databricks

REPO = "BurntSushi/ripgrep"

print(f"=== Silver: raw PR and issue events for {REPO} ===")
rows = query_databricks(f"""
SELECT event_type, payload_action, count(*) as cnt, min(event_date) as earliest, max(event_date) as latest
FROM workspace.default.silver_github_events
WHERE repo_full_name = '{REPO}'
  AND event_type IN ('PullRequestEvent', 'IssuesEvent')
GROUP BY event_type, payload_action
ORDER BY event_type, payload_action
""")
if rows:
    print(f"  {'event_type':<22} {'payload_action':<18} {'cnt':>4}  {'earliest':<12} {'latest'}")
    print("  " + "-" * 70)
    for r in rows:
        print(f"  {r['event_type']:<22} {str(r['payload_action']):<18} {r['cnt']:>4}  {r['earliest']:<12} {r['latest']}")
else:
    print("  NO PR or Issue events found in Silver.")

print(f"\n=== int_pr_health for {REPO} ===")
rows = query_databricks(f"""
SELECT * FROM workspace.default.int_pr_health WHERE repo_full_name = '{REPO}'
""")
if rows:
    for r in rows:
        print(f"  prs_opened={r['prs_opened']}  prs_closed={r['prs_closed']}  pr_merge_rate={r['pr_merge_rate']}")
else:
    print("  No row in int_pr_health.")

print(f"\n=== int_issue_health for {REPO} ===")
rows = query_databricks(f"""
SELECT * FROM workspace.default.int_issue_health WHERE repo_full_name = '{REPO}'
""")
if rows:
    for r in rows:
        print(f"  issues_opened={r['issues_opened']}  issues_closed={r['issues_closed']}  issue_resolution_rate={r['issue_resolution_rate']}")
else:
    print("  No row in int_issue_health.")

print(f"\n=== gold_health_scores for {REPO} ===")
rows = query_databricks(f"""
SELECT pr_score, issue_score, pr_merge_rate, issue_resolution_rate,
       prs_opened, prs_closed, issues_opened, issues_closed
FROM workspace.default.gold_project_health
WHERE repo_full_name = '{REPO}'
""")
if rows:
    r = rows[0]
    print(f"  prs_opened={r['prs_opened']}  prs_closed={r['prs_closed']}  pr_merge_rate={r['pr_merge_rate']}  pr_score={r['pr_score']}")
    print(f"  issues_opened={r['issues_opened']}  issues_closed={r['issues_closed']}  issue_resolution_rate={r['issue_resolution_rate']}  issue_score={r['issue_score']}")
else:
    print("  No row in gold_project_health.")

print(f"\n=== Scoring logic check ===")
print("  pr_score   = NULL → 5.0 fallback | 0 prs_opened → NULL | prs_closed/prs_opened * 10")
print("  issue_score= NULL → 5.0 fallback | 0 opened → NULL | 0 closed → 0.0")
print("  A score of 0.00 means closed=0 with opened>0 (no closures in window).")
print("  A score of 5.00 means no PR/Issue events at all (NULL fallback).")
