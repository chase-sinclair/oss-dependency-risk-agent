import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
load_dotenv()
from agent.tools.databricks_query import query_databricks

rows = query_databricks("""
SELECT
    repo_full_name,
    is_maintained,
    has_license,
    is_branch_protected,
    requires_code_review,
    has_security_policy,
    vuln_count,
    vuln_data_available,
    has_dep_update_tool
FROM workspace.default.github_scorecard
ORDER BY repo_full_name
""")

def b(v):
    if v is None: return "NULL"
    if str(v).lower() == "true":  return "Y"
    if str(v).lower() == "false": return "N"
    return str(v)

def governance(r):
    pts = 0
    if str(r.get("is_maintained","")).lower()        == "true": pts += 4
    if str(r.get("has_license","")).lower()           == "true": pts += 2
    if str(r.get("is_branch_protected","")).lower()   == "true": pts += 2
    if str(r.get("requires_code_review","")).lower()  == "true": pts += 2
    if str(r.get("has_security_policy","")).lower()   == "true": pts += 2
    return round(pts / 12 * 10, 2)

def security(r):
    vc    = r.get("vuln_count")
    avail = str(r.get("vuln_data_available","")).lower() == "true"
    dep   = str(r.get("has_dep_update_tool","")).lower() == "true"
    vuln_score = max(0, 10 - int(vc) * 2) if (avail and vc is not None) else 5.0
    dep_score  = 10.0 if dep else 0.0
    return round(vuln_score * 0.6 + dep_score * 0.4, 2)

header = (f"{'repo':<42} {'maint':>5} {'lic':>3} {'prot':>4} {'rev':>3} "
          f"{'sec_pol':>7} {'vulns':>5} {'dep':>3} | {'gov_score':>9} {'sec_score':>9}")
print(header)
print("-" * len(header))
for r in rows:
    print(
        f"{r['repo_full_name']:<42} "
        f"{b(r['is_maintained']):>5} "
        f"{b(r['has_license']):>3} "
        f"{b(r['is_branch_protected']):>4} "
        f"{b(r['requires_code_review']):>3} "
        f"{b(r['has_security_policy']):>7} "
        f"{str(r['vuln_count'] if r['vuln_count'] is not None else 'N/A'):>5} "
        f"{b(r['has_dep_update_tool']):>3} "
        f"| {governance(r):>9} {security(r):>9}"
    )
