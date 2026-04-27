import os, sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
load_dotenv()
import requests

token = os.environ.get("GITHUB_TOKEN", "")
headers = {
    "Accept": "application/vnd.github.v3+json",
    "Authorization": f"Bearer {token}",
}

for org, repo, branch in [
    ("microsoft", "vscode",    "main"),
    ("google",    "guava",     "master"),
    ("psf",       "requests",  "main"),
]:
    # Test 1: branch protection endpoint (requires admin/repo scope)
    url = f"https://api.github.com/repos/{org}/{repo}/branches/{branch}/protection"
    resp = requests.get(url, headers=headers, timeout=15)
    print(f"\n--- {org}/{repo} ---")
    print(f"  /branches/{branch}/protection  →  HTTP {resp.status_code}")
    if resp.status_code != 200:
        print(f"  body: {resp.text[:300]}")

    # Test 2: branch endpoint (readable with public_repo scope)
    url2 = f"https://api.github.com/repos/{org}/{repo}/branches/{branch}"
    resp2 = requests.get(url2, headers=headers, timeout=15)
    print(f"  /branches/{branch}              →  HTTP {resp2.status_code}")
    if resp2.status_code == 200:
        data = resp2.json()
        print(f"  protected field: {data.get('protected')}")
        protection = data.get("protection", {})
        print(f"  protection summary: {json.dumps(protection, indent=4)}")
