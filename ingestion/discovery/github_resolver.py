"""
GitHub repository resolver for dependency discovery.

Resolution strategy per ecosystem:
    python  — PyPI API first (most accurate); falls back to GitHub Search
    node    — npm registry API first; falls back to GitHub Search
    go      — module path IS the GitHub path (golang.org/x/... remapped)
    java    — GitHub Search on artifactId
    rust    — crates.io API; falls back to GitHub Search

Results are cached in config/resolution_cache.json to avoid repeat API calls.
"""

import json
import logging
import os
import re
import time
from pathlib import Path
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

_CACHE_PATH = Path(__file__).resolve().parents[3] / "config" / "resolution_cache.json"
_GITHUB_API = "https://api.github.com"
_PYPI_API = "https://pypi.org/pypi"
_NPM_API = "https://registry.npmjs.org"
_CRATES_API = "https://crates.io/api/v1/crates"

# Seconds between GitHub Search API calls (unauthenticated: 10/min, authenticated: 30/min)
_SEARCH_RATE_LIMIT_DELAY = 2.5


class ResolvedRepo:
    """Result of a resolution attempt."""
    __slots__ = ("org", "repo", "source", "confidence")

    def __init__(self, org: str, repo: str, source: str, confidence: str = "high"):
        self.org = org
        self.repo = repo
        self.source = source        # pypi | npm | crates | go_module | github_search
        self.confidence = confidence  # high | medium | low

    @property
    def full_name(self) -> str:
        return f"{self.org}/{self.repo}"


# ── Known-correct mappings (take priority over all API resolution) ────────────
#
# Add entries here when the API resolvers misidentify a well-known package.
# Format: "package-name": ("org", "repo")
# Keys are lowercased for case-insensitive lookup.

_KNOWN_MAPPINGS: dict[str, tuple[str, str]] = {
    "pinecone":   ("pinecone-io", "pinecone-python-client"),
    "pandas":     ("pandas-dev",  "pandas"),
    "numpy":      ("numpy",       "numpy"),
    "scipy":      ("scipy",       "scipy"),
    "matplotlib": ("matplotlib",  "matplotlib"),
    "sqlalchemy": ("sqlalchemy",  "sqlalchemy"),
    "fastapi":    ("tiangolo",    "fastapi"),
    "celery":     ("celery",      "celery"),
    "redis":      ("redis",       "redis-py"),
    "httpx":      ("encode",      "httpx"),
    "pytest":     ("pytest-dev",  "pytest"),
    "openai":     ("openai",      "openai-python"),
}


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def _github_headers() -> dict:
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
def _get(url: str, headers: Optional[dict] = None, params: Optional[dict] = None):
    resp = requests.get(url, headers=headers, params=params, timeout=10)
    return resp


def _parse_github_url(url: str) -> Optional[tuple[str, str]]:
    """
    Extract (org, repo) from a GitHub URL string.

    Handles:
        https://github.com/org/repo
        https://github.com/org/repo.git
        git+https://github.com/org/repo.git
        git://github.com/org/repo.git
        github:org/repo
    """
    if not url:
        return None
    # Strip git+, git: prefixes and .git suffix
    url = re.sub(r"^git\+", "", url)
    url = re.sub(r"\.git$", "", url)
    match = re.search(r"github\.com[/:]([^/\s]+)/([^/\s#?]+)", url)
    if match:
        org, repo = match.group(1), match.group(2)
        if org and repo:
            return org, repo
    return None


# ── Cache ─────────────────────────────────────────────────────────────────────

def _load_cache() -> dict:
    if _CACHE_PATH.exists():
        try:
            return json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            logger.warning("Could not read resolution cache — starting fresh")
    return {}


def _save_cache(cache: dict) -> None:
    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CACHE_PATH.write_text(json.dumps(cache, indent=2, sort_keys=True), encoding="utf-8")


# ── Per-ecosystem resolvers ───────────────────────────────────────────────────

def _resolve_via_pypi(package_name: str) -> Optional[ResolvedRepo]:
    """Query PyPI JSON API for the upstream GitHub repository URL."""
    try:
        resp = _get(f"{_PYPI_API}/{package_name}/json")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.debug("PyPI lookup failed for %r: %s", package_name, exc)
        return None

    info = data.get("info", {})
    # Check project_urls first (most reliable)
    for url_key in ("Source", "Source Code", "Homepage", "Repository", "Code"):
        url = (info.get("project_urls") or {}).get(url_key, "")
        parsed = _parse_github_url(url)
        if parsed:
            return ResolvedRepo(*parsed, source="pypi", confidence="high")
    # Fall back to info.home_page
    parsed = _parse_github_url(info.get("home_page", ""))
    if parsed:
        return ResolvedRepo(*parsed, source="pypi", confidence="medium")
    return None


def _resolve_via_npm(package_name: str) -> Optional[ResolvedRepo]:
    """Query npm registry for the upstream GitHub repository URL."""
    try:
        resp = _get(f"{_NPM_API}/{package_name}/latest")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.debug("npm lookup failed for %r: %s", package_name, exc)
        return None

    repo_field = data.get("repository", {})
    url = repo_field.get("url", "") if isinstance(repo_field, dict) else str(repo_field)
    parsed = _parse_github_url(url)
    if parsed:
        return ResolvedRepo(*parsed, source="npm", confidence="high")
    # Try homepage
    parsed = _parse_github_url(data.get("homepage", ""))
    if parsed:
        return ResolvedRepo(*parsed, source="npm", confidence="medium")
    return None


def _resolve_via_crates(package_name: str) -> Optional[ResolvedRepo]:
    """Query crates.io for the upstream GitHub repository URL."""
    try:
        resp = _get(
            f"{_CRATES_API}/{package_name}",
            headers={"User-Agent": "oss-risk-agent/1.0"},
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.debug("crates.io lookup failed for %r: %s", package_name, exc)
        return None

    krate = data.get("crate", {})
    for url_key in ("repository", "homepage"):
        parsed = _parse_github_url(krate.get(url_key, ""))
        if parsed:
            return ResolvedRepo(*parsed, source="crates", confidence="high")
    return None


def _resolve_go_module(module_path: str) -> Optional[ResolvedRepo]:
    """
    Resolve a Go module path directly — the module path IS the import path.

    golang.org/x/... -> golang/... (mirrored on GitHub)
    k8s.io/...       -> kubernetes/...
    sigs.k8s.io/...  -> kubernetes-sigs/...
    Everything else starting with github.com/ is direct.
    """
    remaps = {
        "golang.org/x/":  ("golang", None),
        "k8s.io/":        ("kubernetes", None),
        "sigs.k8s.io/":   ("kubernetes-sigs", None),
    }
    for prefix, (org, _) in remaps.items():
        if module_path.startswith(prefix):
            repo = module_path[len(prefix):].split("/")[0]
            return ResolvedRepo(org, repo, source="go_module", confidence="high")

    parsed = _parse_github_url(module_path)
    if parsed:
        return ResolvedRepo(*parsed, source="go_module", confidence="high")
    return None


def _resolve_via_github_search(
    package_name: str,
    ecosystem: str,
) -> Optional[ResolvedRepo]:
    """
    Fall back to GitHub repository search.

    Adds an ecosystem-specific qualifier to improve result quality.
    Rate-limited by a short sleep between calls.
    """
    qualifiers = {
        "python": f"{package_name} language:Python",
        "node":   f"{package_name} language:JavaScript",
        "java":   package_name.split(":")[-1],  # use artifactId only
        "rust":   f"{package_name} language:Rust",
        "go":     f"{package_name} language:Go",
    }
    query = qualifiers.get(ecosystem, package_name)

    try:
        time.sleep(_SEARCH_RATE_LIMIT_DELAY)
        resp = _get(
            f"{_GITHUB_API}/search/repositories",
            headers=_github_headers(),
            params={"q": query, "per_page": 1, "sort": "stars", "order": "desc"},
        )
        if resp.status_code in (403, 429):
            logger.warning("GitHub Search rate limit hit for %r — skipping", package_name)
            return None
        resp.raise_for_status()
        items = resp.json().get("items", [])
    except Exception as exc:
        logger.debug("GitHub Search failed for %r: %s", package_name, exc)
        return None

    if not items:
        return None

    top = items[0]
    full_name = top.get("full_name", "")
    parts = full_name.split("/", 1)
    if len(parts) == 2:
        return ResolvedRepo(parts[0], parts[1], source="github_search", confidence="low")
    return None


# ── Public API ────────────────────────────────────────────────────────────────

def resolve_package(
    name: str,
    ecosystem: str,
    cache: dict,
) -> Optional[ResolvedRepo]:
    """
    Resolve a package name to a GitHub org/repo.

    Checks the in-memory cache first, then tries ecosystem-specific APIs,
    then falls back to GitHub Search.

    Args:
        name:      Package name as it appears in the manifest.
        ecosystem: One of: python, node, go, java, rust.
        cache:     Mutable dict for caching results (caller manages persistence).

    Returns:
        ResolvedRepo or None if the package could not be resolved.
    """
    cache_key = f"{ecosystem}:{name}"
    if cache_key in cache:
        entry = cache[cache_key]
        if entry is None:
            return None
        return ResolvedRepo(entry["org"], entry["repo"], entry["source"], entry["confidence"])

    # Check hardcoded known-correct mappings before any API call
    known = _KNOWN_MAPPINGS.get(name.lower())
    if known:
        logger.debug("Known mapping: %r -> %s/%s", name, known[0], known[1])
        result = ResolvedRepo(known[0], known[1], source="known_mapping", confidence="high")
        cache[cache_key] = {
            "org": result.org,
            "repo": result.repo,
            "source": result.source,
            "confidence": result.confidence,
        }
        return result

    result: Optional[ResolvedRepo] = None

    if ecosystem == "python":
        result = _resolve_via_pypi(name) or _resolve_via_github_search(name, ecosystem)
    elif ecosystem == "node":
        result = _resolve_via_npm(name) or _resolve_via_github_search(name, ecosystem)
    elif ecosystem == "go":
        result = _resolve_go_module(name) or _resolve_via_github_search(name, ecosystem)
    elif ecosystem == "rust":
        result = _resolve_via_crates(name) or _resolve_via_github_search(name, ecosystem)
    elif ecosystem == "java":
        result = _resolve_via_github_search(name, ecosystem)
    else:
        logger.warning("Unknown ecosystem %r for package %r", ecosystem, name)

    # Cache the result (None = unresolvable)
    if result:
        cache[cache_key] = {
            "org": result.org,
            "repo": result.repo,
            "source": result.source,
            "confidence": result.confidence,
        }
    else:
        cache[cache_key] = None

    return result


def resolve_packages(
    packages: list[dict],
    existing_repos: set[str],
) -> tuple[list[dict], list[str]]:
    """
    Resolve a list of PackageDependency dicts to GitHub repos.

    Skips packages already in the monitoring list.
    Persists the resolution cache after completion.

    Args:
        packages:       List of PackageDependency dicts from the manifest parser.
        existing_repos: Set of 'org/repo' strings already being monitored.

    Returns:
        (resolved, unresolved) where:
            resolved   — list of dicts ready for project_list.py
                         {org, repo, category, description}
            unresolved — list of package names that could not be resolved
    """
    cache = _load_cache()
    resolved: list[dict] = []
    unresolved: list[str] = []
    seen: set[str] = set()

    for pkg in packages:
        name = pkg["name"]
        ecosystem = pkg["ecosystem"]

        result = resolve_package(name, ecosystem, cache)

        if result is None:
            logger.info("Could not resolve: %s (%s)", name, ecosystem)
            unresolved.append(name)
            continue

        full_name = result.full_name
        if full_name in existing_repos or full_name in seen:
            logger.debug("Already monitored — skipping: %s", full_name)
            continue

        seen.add(full_name)
        resolved.append({
            "org":         result.org,
            "repo":        result.repo,
            "category":    "discovered",
            "description": f"Discovered from manifest ({ecosystem} package: {name})",
        })
        logger.info(
            "Resolved %r -> %s [via %s, confidence=%s]",
            name, full_name, result.source, result.confidence,
        )

    _save_cache(cache)
    logger.info(
        "Resolution complete: %d resolved, %d unresolved, %d already monitored",
        len(resolved), len(unresolved), len(packages) - len(resolved) - len(unresolved),
    )
    return resolved, unresolved
