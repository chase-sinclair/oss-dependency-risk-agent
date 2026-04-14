"""
Project registry — manages additions to the monitoring list in project_list.py.

Reads the current _DISCOVERED list from project_list.py (appended section),
merges new projects in, and rewrites the file preserving the original
curated lists verbatim.

The discovered projects are kept in a separate _DISCOVERED list at the
bottom of project_list.py and merged into PROJECTS at import time.
This keeps the curated lists clean and makes auto-additions auditable.
"""

import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_PROJECT_LIST_PATH = (
    Path(__file__).resolve().parents[1] / "github_archive" / "project_list.py"
)

# Sentinel comment that marks the start of the auto-generated section
_DISCOVERED_HEADER = "# ── Discovered (auto-generated) ──"
_DISCOVERED_VAR = "_DISCOVERED"


def get_current_projects() -> set[str]:
    """
    Return the set of 'org/repo' strings currently in project_list.py.

    Reads the file directly rather than importing to avoid stale module cache.
    """
    text = _PROJECT_LIST_PATH.read_text(encoding="utf-8")
    # Match all {"org": "...", "repo": "..."} patterns
    return {
        f"{m.group(1)}/{m.group(2)}"
        for m in re.finditer(
            r'"org"\s*:\s*"([^"]+)"[^}]*?"repo"\s*:\s*"([^"]+)"', text
        )
    }


def _format_entry(project: dict, indent: str = "    ") -> str:
    """Format a single project dict as a Python dict literal line."""
    org  = project["org"]
    repo = project["repo"]
    cat  = project.get("category", "discovered")
    desc = project.get("description", "")
    # Escape any quotes in description
    desc = desc.replace('"', '\\"')
    return (
        f'{indent}{{"org": "{org}", "repo": "{repo}", '
        f'"category": "{cat}", "description": "{desc}"}}'
    )


def _build_discovered_block(projects: list[dict]) -> str:
    """Build the full _DISCOVERED list block as a Python source string."""
    if not projects:
        entries = "    # No discovered projects yet."
    else:
        entries = ",\n".join(_format_entry(p) for p in projects)

    return (
        f"\n\n{_DISCOVERED_HEADER}\n"
        f"{_DISCOVERED_VAR}: list[Project] = [\n"
        f"{entries}\n"
        f"]\n"
    )


def _read_existing_discovered(text: str) -> list[dict]:
    """
    Parse any projects already in the _DISCOVERED block.

    Returns a list of {org, repo, category, description} dicts.
    """
    projects = []
    # Find the discovered block if it exists
    match = re.search(
        rf"{re.escape(_DISCOVERED_HEADER)}.*?{_DISCOVERED_VAR}\s*[^=]*=\s*\[(.*?)\]",
        text,
        re.DOTALL,
    )
    if not match:
        return []

    block = match.group(1)
    for m in re.finditer(
        r'"org"\s*:\s*"([^"]+)"[^}]*?"repo"\s*:\s*"([^"]+)"'
        r'[^}]*?"category"\s*:\s*"([^"]*)"[^}]*?"description"\s*:\s*"([^"]*)"',
        block,
    ):
        projects.append({
            "org":         m.group(1),
            "repo":        m.group(2),
            "category":    m.group(3),
            "description": m.group(4),
        })
    return projects


def _ensure_projects_merge(text: str) -> str:
    """
    Ensure _DISCOVERED is included in the PROJECTS master list.

    If the PROJECTS concatenation doesn't already include _DISCOVERED,
    append it.
    """
    if "_DISCOVERED" in text and "+ _DISCOVERED" not in text:
        text = text.replace(
            "+ _CICD\n)",
            "+ _CICD\n    + _DISCOVERED\n)",
        )
    return text


def add_projects(
    new_projects: list[dict],
    dry_run: bool = False,
) -> tuple[int, int]:
    """
    Add new projects to the _DISCOVERED block in project_list.py.

    Args:
        new_projects: List of {org, repo, category, description} dicts.
        dry_run:      If True, log what would be added without writing.

    Returns:
        (added_count, already_present_count) tuple.
    """
    if not new_projects:
        logger.info("No new projects to add.")
        return 0, 0

    text = _PROJECT_LIST_PATH.read_text(encoding="utf-8")
    existing_repos = get_current_projects()

    # Merge existing discovered projects with new ones
    existing_discovered = _read_existing_discovered(text)
    existing_discovered_names = {f"{p['org']}/{p['repo']}" for p in existing_discovered}

    to_add = []
    already_present = 0
    for project in new_projects:
        full_name = f"{project['org']}/{project['repo']}"
        if full_name in existing_repos or full_name in existing_discovered_names:
            already_present += 1
        else:
            to_add.append(project)
            existing_discovered_names.add(full_name)

    if dry_run:
        logger.info("[dry-run] Would add %d project(s) to project_list.py:", len(to_add))
        for p in to_add:
            logger.info("  + %s/%s (%s)", p["org"], p["repo"], p["category"])
        return len(to_add), already_present

    if not to_add:
        logger.info("All %d project(s) already present in monitoring list.", already_present)
        return 0, already_present

    all_discovered = existing_discovered + to_add
    new_block = _build_discovered_block(all_discovered)

    # Remove any existing _DISCOVERED block (wherever it is in the file)
    if _DISCOVERED_HEADER in text:
        text = re.sub(
            rf"\n*{re.escape(_DISCOVERED_HEADER)}.*?(?=\n# ──|\nPROJECTS|\Z)",
            "",
            text,
            flags=re.DOTALL,
        )

    # Insert the block immediately before the master list comment
    master_marker = "# ── Master list"
    if master_marker in text:
        text = text.replace(master_marker, new_block.lstrip("\n") + "\n" + master_marker)
    else:
        # Fallback: prepend before PROJECTS definition
        text = text.replace("PROJECTS:", new_block.lstrip("\n") + "\nPROJECTS:")

    text = _ensure_projects_merge(text)
    _PROJECT_LIST_PATH.write_text(text, encoding="utf-8")

    logger.info(
        "Added %d new project(s) to project_list.py (%d already present).",
        len(to_add), already_present,
    )
    for p in to_add:
        logger.info("  + %s/%s", p["org"], p["repo"])

    return len(to_add), already_present


def list_discovered() -> list[dict]:
    """Return all projects currently in the _DISCOVERED block."""
    text = _PROJECT_LIST_PATH.read_text(encoding="utf-8")
    return _read_existing_discovered(text)


def remove_project(org: str, repo: str) -> bool:
    """
    Remove a project from the _DISCOVERED block.

    Does not touch curated lists. Returns True if the project was found
    and removed, False if it was not in the discovered list.
    """
    text = _PROJECT_LIST_PATH.read_text(encoding="utf-8")
    discovered = _read_existing_discovered(text)
    target = f"{org}/{repo}"
    filtered = [p for p in discovered if f"{p['org']}/{p['repo']}" != target]

    if len(filtered) == len(discovered):
        logger.warning("%s not found in discovered projects.", target)
        return False

    new_block = _build_discovered_block(filtered)
    text = re.sub(
        rf"{re.escape(_DISCOVERED_HEADER)}.*",
        new_block.lstrip("\n"),
        text,
        flags=re.DOTALL,
    )
    _PROJECT_LIST_PATH.write_text(text, encoding="utf-8")
    logger.info("Removed %s from discovered projects.", target)
    return True
