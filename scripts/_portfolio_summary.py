import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
load_dotenv()
from agent.tools.databricks_query import query_databricks

def pct(n, total):
    return f"{float(n)/total*100:.1f}%" if total else "N/A"

def hdr(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)

# ── 1. Score band distribution ────────────────────────────────
hdr("1. Health Score Distribution")
rows = query_databricks("""
SELECT
    COUNT(*)                                            AS total,
    COUNT_IF(health_score < 4.0)                        AS critical,
    COUNT_IF(health_score >= 4.0 AND health_score < 7.0) AS warning,
    COUNT_IF(health_score >= 7.0)                       AS healthy
FROM workspace.default.gold_health_scores
""")
r = rows[0]
total = int(r["total"])
print(f"  Total scored repos : {total}")
print(f"  Critical  (< 4.0)  : {r['critical']:>4}  ({pct(r['critical'], total)})")
print(f"  Warning  (4.0-6.9) : {r['warning']:>4}  ({pct(r['warning'], total)})")
print(f"  Healthy   (7.0+)   : {r['healthy']:>4}  ({pct(r['healthy'], total)})")

# ── 2. Average signal scores ──────────────────────────────────
hdr("2. Average Signal Scores (portfolio-wide)")
rows = query_databricks("""
SELECT
    round(avg(commit_score),      2) AS commit_score,
    round(avg(issue_score),       2) AS issue_score,
    round(avg(pr_score),          2) AS pr_score,
    round(avg(contributor_score), 2) AS contributor_score,
    round(avg(bus_factor_score),  2) AS bus_factor_score,
    round(avg(governance_score),  2) AS governance_score,
    round(avg(security_score),    2) AS security_score,
    round(avg(health_score),      2) AS health_score
FROM workspace.default.gold_health_scores
""")
r = rows[0]
signals = [
    ("commit_score",      r["commit_score"]),
    ("issue_score",       r["issue_score"]),
    ("pr_score",          r["pr_score"]),
    ("contributor_score", r["contributor_score"]),
    ("bus_factor_score",  r["bus_factor_score"]),
    ("governance_score",  r["governance_score"]),
    ("security_score",    r["security_score"]),
    ("── health_score",   r["health_score"]),
]
for name, val in signals:
    bar = "█" * int(float(val or 0))
    print(f"  {name:<20} {float(val or 0):>5.2f}  {bar}")

# ── 3. Governance signal breakdown ───────────────────────────
hdr("3. Governance Signal Coverage (% of scorecard repos)")
rows = query_databricks("""
SELECT
    COUNT_IF(is_maintained        = true) AS maintained,
    COUNT_IF(has_license          = true) AS license,
    COUNT_IF(is_branch_protected  = true) AS branch_protected,
    COUNT_IF(requires_code_review = true) AS code_review,
    COUNT_IF(has_security_policy  = true) AS security_policy,
    COUNT_IF(has_dep_update_tool  = true) AS dep_update_tool,
    COUNT(repo_full_name)                 AS total
FROM workspace.default.github_scorecard
""")
r = rows[0]
sc_total = int(r["total"])
signals = [
    ("is_maintained",        r["maintained"]),
    ("has_license",          r["license"]),
    ("is_branch_protected",  r["branch_protected"]),
    ("requires_code_review", r["code_review"]),
    ("has_security_policy",  r["security_policy"]),
    ("has_dep_update_tool",  r["dep_update_tool"]),
]
for name, val in signals:
    v = int(val or 0)
    print(f"  {name:<24} {v:>4} / {sc_total}  ({pct(v, sc_total)})")

# ── 4. Vulnerability distribution ────────────────────────────
hdr("4. Vulnerability Count Distribution (OSV)")
rows = query_databricks("""
SELECT
    COUNT_IF(vuln_data_available = false OR vuln_count IS NULL) AS ecosystem_unknown,
    COUNT_IF(vuln_data_available = true  AND vuln_count = 0)    AS zero_vulns,
    COUNT_IF(vuln_data_available = true  AND vuln_count BETWEEN 1 AND 5)  AS one_to_five,
    COUNT_IF(vuln_data_available = true  AND vuln_count BETWEEN 6 AND 10) AS six_to_ten,
    COUNT_IF(vuln_data_available = true  AND vuln_count > 10)   AS over_ten,
    COUNT(repo_full_name)                                        AS total
FROM workspace.default.github_scorecard
""")
r = rows[0]
sc_total = int(r["total"])
bands = [
    ("Ecosystem unknown (amber badge)", r["ecosystem_unknown"]),
    ("0 vulns",                         r["zero_vulns"]),
    ("1–5 vulns",                       r["one_to_five"]),
    ("6–10 vulns",                      r["six_to_ten"]),
    ("10+ vulns",                       r["over_ten"]),
]
for name, val in bands:
    v = int(val or 0)
    print(f"  {name:<34} {v:>4} / {sc_total}  ({pct(v, sc_total)})")
