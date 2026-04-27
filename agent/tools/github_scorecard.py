"""
GitHub Scorecard fetcher for the OSS Risk Agent.

Fetches 6 governance and security signals per repository using the GitHub
REST API and the OSV vulnerability database.

Signals returned by fetch_scorecard():
    is_maintained         BOOLEAN   last push within 90 days
    has_license           BOOLEAN   license file detected by GitHub
    is_branch_protected   BOOLEAN   default branch has branch protection enabled
    requires_code_review  BOOLEAN   PRs required before merging (subset of protection)
    has_security_policy   BOOLEAN   SECURITY.md present in the repository
    vuln_count            INT|None  unfixed CVE count from OSV; None when ecosystem unknown
    vuln_data_available   BOOLEAN   False when ecosystem cannot be inferred
    has_dep_update_tool   BOOLEAN   Dependabot or Renovate config file present
    language              STR|None  primary repo language as reported by GitHub

Rate budget: ~4 GitHub API calls + 1 OSV call per repo.
At 5,000 req/hour (authenticated), 700 repos ≈ 2,800 calls ≈ well within budget.
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests
from dotenv import load_dotenv
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

load_dotenv()

logger = logging.getLogger(__name__)

_GITHUB_API = "https://api.github.com"
_OSV_API    = "https://api.osv.dev/v1/query"

_LANGUAGE_TO_ECOSYSTEM: dict[str, str] = {
    "Python":     "PyPI",
    "JavaScript": "npm",
    "TypeScript": "npm",
    "Go":         "Go",
    "Rust":       "crates.io",
    "Java":       "Maven",
    "Ruby":       "RubyGems",
    "PHP":        "Packagist",
    "C#":         "NuGet",
    "Kotlin":     "Maven",
    "Scala":      "Maven",
}

_DEP_UPDATE_PATHS = [
    ".github/dependabot.yml",
    ".github/dependabot.yaml",
    "renovate.json",
    ".renovaterc",
    ".renovaterc.json",
]

_SECURITY_POLICY_PATHS = [
    "SECURITY.md",
    ".github/SECURITY.md",
    "docs/SECURITY.md",
]


def _headers() -> dict:
    token = os.environ.get("GITHUB_TOKEN", "")
    h = {"Accept": "application/vnd.github.v3+json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


@retry(
    retry=retry_if_exception_type(requests.RequestException),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def _get(url: str, params: Optional[dict] = None) -> dict | list:
    resp = requests.get(url, headers=_headers(), params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def _get_or_404(url: str) -> tuple[dict | list | None, int]:
    """GET that returns (body, status_code) without retrying on 4xx."""
    try:
        resp = requests.get(url, headers=_headers(), timeout=15)
        if resp.status_code == 404:
            return None, 404
        resp.raise_for_status()
        return resp.json(), resp.status_code
    except requests.HTTPError as exc:
        return None, exc.response.status_code if exc.response is not None else 0
    except requests.RequestException:
        return None, 0


# ── Signal helpers ────────────────────────────────────────────────────────────

def _is_maintained(pushed_at: Optional[str]) -> Optional[bool]:
    if not pushed_at:
        return None
    try:
        dt = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt) < timedelta(days=90)
    except Exception:
        return None


def _branch_protection(org: str, repo: str, branch: str) -> tuple[bool, bool]:
    """
    Returns (is_protected, requires_code_review).

    Uses GET /repos/{org}/{repo}/branches/{branch} which is readable with
    public_repo scope and returns a `protected` boolean directly.

    The /branches/{branch}/protection endpoint requires admin token scope and
    returns 404 for all repos when the token lacks that scope — do not use it.

    requires_code_review: true when the branch protection summary includes
    required_pull_request_reviews or enforcement_level is non-admins/everyone.
    """
    url = f"{_GITHUB_API}/repos/{org}/{repo}/branches/{branch}"
    data, status = _get_or_404(url)
    if data is None:
        logger.warning("branch fetch returned status=%d for %s/%s", status, org, repo)
        return False, False

    is_protected = bool(data.get("protected", False))
    if not is_protected:
        return False, False

    # protection summary is included inline on the branch object
    protection = data.get("protection", {})
    requires_review = (
        protection.get("required_pull_request_reviews") is not None
        or protection.get("required_status_checks", {}).get("enforcement_level")
           in ("non_admins", "everyone")
    )
    return True, requires_review


def _vuln_count(repo_name: str, language: Optional[str]) -> tuple[Optional[int], bool]:
    """
    Returns (vuln_count, vuln_data_available).

    vuln_count=None and vuln_data_available=False when the ecosystem cannot
    be inferred — surfaced as an amber badge in the UI, not as 0 vulns.
    """
    ecosystem = _LANGUAGE_TO_ECOSYSTEM.get(language or "")
    if not ecosystem:
        return None, False
    try:
        resp = requests.post(
            _OSV_API,
            json={"package": {"name": repo_name, "ecosystem": ecosystem}},
            timeout=15,
        )
        resp.raise_for_status()
        vulns = resp.json().get("vulns", [])
        return len(vulns), True
    except Exception as exc:
        logger.warning("OSV query failed for %s (%s): %s", repo_name, ecosystem, exc)
        return None, False


def _has_dep_update_tool(org: str, repo: str) -> bool:
    """Return True if Dependabot or Renovate config is present."""
    for path in _DEP_UPDATE_PATHS:
        url = f"{_GITHUB_API}/repos/{org}/{repo}/contents/{path}"
        _, status = _get_or_404(url)
        if status == 200:
            return True
    return False


def _has_security_policy(org: str, repo: str) -> bool:
    """Return True if SECURITY.md is present (root, .github/, or docs/)."""
    for path in _SECURITY_POLICY_PATHS:
        url = f"{_GITHUB_API}/repos/{org}/{repo}/contents/{path}"
        _, status = _get_or_404(url)
        if status == 200:
            return True
    return False


# ── Public API ────────────────────────────────────────────────────────────────

def fetch_scorecard(repo_full_name: str) -> dict:
    """
    Fetch all 6 scorecard signals for a repository.

    Args:
        repo_full_name: "org/repo" string.

    Returns:
        Dict with keys: repo_full_name, is_maintained, has_license,
        is_branch_protected, requires_code_review, vuln_count,
        vuln_data_available, has_dep_update_tool, language, fetched_at.
        On fatal error, returns a dict with error key set.
    """
    parts = repo_full_name.split("/", 1)
    if len(parts) != 2:
        logger.error("Invalid repo_full_name (expected org/repo): %s", repo_full_name)
        return {"repo_full_name": repo_full_name, "error": "invalid repo name"}

    org, repo = parts
    logger.debug("Fetching scorecard for %s", repo_full_name)

    try:
        meta = _get(f"{_GITHUB_API}/repos/{org}/{repo}")
    except Exception as exc:
        logger.warning("fetch_scorecard: repo metadata failed for %s: %s", repo_full_name, exc)
        return {"repo_full_name": repo_full_name, "error": str(exc)}

    language    = meta.get("language")
    pushed_at   = meta.get("pushed_at")
    default_br  = meta.get("default_branch") or "main"

    is_protected, requires_review = _branch_protection(org, repo, default_br)
    count, vuln_available         = _vuln_count(repo, language)
    has_dep_tool                  = _has_dep_update_tool(org, repo)
    has_sec_policy                = _has_security_policy(org, repo)

    return {
        "repo_full_name":       repo_full_name,
        "is_maintained":        _is_maintained(pushed_at),
        "has_license":          meta.get("license") is not None,
        "is_branch_protected":  is_protected,
        "requires_code_review": requires_review,
        "has_security_policy":  has_sec_policy,
        "vuln_count":           count,
        "vuln_data_available":  vuln_available,
        "has_dep_update_tool":  has_dep_tool,
        "language":             language,
        "fetched_at":           datetime.now(timezone.utc).isoformat(),
    }
