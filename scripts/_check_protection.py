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

url = "https://api.github.com/repos/BurntSushi/ripgrep/branches/master/protection"
resp = requests.get(url, headers=headers, timeout=15)
print(f"Status: {resp.status_code}")
print(json.dumps(resp.json(), indent=2))
