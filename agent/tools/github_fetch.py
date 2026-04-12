"""
GitHub API fetching tool for the OSS Risk Agent.

Fetches recent open issues, pull requests, and repository metadata
for a given org/repo using the GitHub REST API v3.

Retries up to 3 times on transient network errors with exponential back-off.
A missing or invalid GITHUB_TOKEN degrades gracefully to unauthenticated
requests (60 req/hour rate limit instead of 5,000).
"""

import logging
import os
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


# ── Public helpers ──────────────────────────────────────────────────────────

def fetch_repo_metadata(org: str, repo: str) -> dict:
    """Fetch basic repository metadata (stars, forks, open issue count, etc.)."""
    try:
        data = _get(f"{_GITHUB_API}/repos/{org}/{repo}")
        return {
            "full_name":   data.get("full_name"),
            "description": data.get("description"),
            "stars":       data.get("stargazers_count", 0),
            "forks":       data.get("forks_count", 0),
            "open_issues": data.get("open_issues_count", 0),
            "language":    data.get("language"),
            "archived":    data.get("archived", False),
            "pushed_at":   data.get("pushed_at"),
            "created_at":  data.get("created_at"),
        }
    except Exception as exc:
        logger.warning("fetch_repo_metadata failed for %s/%s: %s", org, repo, exc)
        return {}


def fetch_open_issues(org: str, repo: str, limit: int = 10) -> list[dict]:
    """
    Fetch the most recently updated open issues (pull requests excluded).

    Args:
        org, repo: GitHub org and repository name.
        limit:     Maximum number of issues to return.

    Returns:
        List of issue summary dicts.
    """
    try:
        items = _get(
            f"{_GITHUB_API}/repos/{org}/{repo}/issues",
            params={
                "state":     "open",
                "per_page":  min(limit * 2, 100),  # fetch extra to filter PRs
                "sort":      "updated",
                "direction": "desc",
            },
        )
        # GitHub /issues endpoint returns PRs too; filter them out
        issues = [i for i in items if "pull_request" not in i][:limit]
        return [
            {
                "number":     issue.get("number"),
                "title":      issue.get("title"),
                "state":      issue.get("state"),
                "created_at": issue.get("created_at"),
                "updated_at": issue.get("updated_at"),
                "comments":   issue.get("comments", 0),
                "labels":     [lb["name"] for lb in issue.get("labels", [])],
                "url":        issue.get("html_url"),
            }
            for issue in issues
        ]
    except Exception as exc:
        logger.warning("fetch_open_issues failed for %s/%s: %s", org, repo, exc)
        return []


def fetch_recent_prs(org: str, repo: str, limit: int = 5) -> list[dict]:
    """Fetch the most recently updated open pull requests."""
    try:
        items = _get(
            f"{_GITHUB_API}/repos/{org}/{repo}/pulls",
            params={
                "state":     "open",
                "per_page":  limit,
                "sort":      "updated",
                "direction": "desc",
            },
        )
        return [
            {
                "number":     pr.get("number"),
                "title":      pr.get("title"),
                "state":      pr.get("state"),
                "created_at": pr.get("created_at"),
                "updated_at": pr.get("updated_at"),
                "draft":      pr.get("draft", False),
                "url":        pr.get("html_url"),
            }
            for pr in items[:limit]
        ]
    except Exception as exc:
        logger.warning("fetch_recent_prs failed for %s/%s: %s", org, repo, exc)
        return []


def fetch_project_signals(repo_full_name: str) -> dict:
    """
    Fetch all GitHub signals for a project in one call.

    Args:
        repo_full_name: "org/repo" string.

    Returns:
        Dict with keys: repo_full_name, metadata, open_issues, recent_prs.
    """
    parts = repo_full_name.split("/", 1)
    if len(parts) != 2:
        logger.error("Invalid repo_full_name (expected org/repo): %s", repo_full_name)
        return {"repo_full_name": repo_full_name, "error": "invalid repo name"}

    org, repo = parts
    logger.info("Fetching GitHub signals for %s", repo_full_name)

    return {
        "repo_full_name": repo_full_name,
        "metadata":       fetch_repo_metadata(org, repo),
        "open_issues":    fetch_open_issues(org, repo, limit=10),
        "recent_prs":     fetch_recent_prs(org, repo, limit=5),
    }
