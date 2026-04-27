import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
load_dotenv()
from agent.tools.databricks_query import query_databricks

REPOS = [
    "99designs/gqlgen",
    "Automattic/mongoose",
    "Bearer/bearer",
    "BerriAI/litellm",
    "BurntSushi/ripgrep",
]

placeholders = ", ".join(f"'{r}'" for r in REPOS)

rows = query_databricks(f"""
SELECT
    repo_full_name,
    health_score,
    commit_score,
    issue_score,
    pr_score,
    contributor_score,
    bus_factor_score,
    governance_score,
    security_score,
    vuln_data_available,
    has_push_data
FROM workspace.default.gold_health_scores
WHERE repo_full_name IN ({placeholders})
ORDER BY repo_full_name
""")

COL_W = 22
def fmt(v):
    if v is None: return "NULL"
    try:
        return f"{float(v):.2f}"
    except (TypeError, ValueError):
        return str(v)

headers = ["repo", "health", "commit", "issue", "pr", "contrib", "bus_fac", "gov", "sec", "vuln_avail", "push_data"]
widths  = [26, 6, 6, 6, 6, 7, 7, 6, 6, 10, 9]

header_row = "  ".join(h.ljust(w) for h, w in zip(headers, widths))
print(header_row)
print("-" * len(header_row))

for r in rows:
    vals = [
        r.get("repo_full_name", ""),
        fmt(r.get("health_score")),
        fmt(r.get("commit_score")),
        fmt(r.get("issue_score")),
        fmt(r.get("pr_score")),
        fmt(r.get("contributor_score")),
        fmt(r.get("bus_factor_score")),
        fmt(r.get("governance_score")),
        fmt(r.get("security_score")),
        str(r.get("vuln_data_available", "NULL")),
        str(r.get("has_push_data", "NULL")),
    ]
    print("  ".join(v.ljust(w) for v, w in zip(vals, widths)))

missing = set(REPOS) - {r["repo_full_name"] for r in rows}
if missing:
    print(f"\nNot found in gold_health_scores: {sorted(missing)}")
