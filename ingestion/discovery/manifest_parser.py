"""
Manifest parser for dependency discovery.

Supports:
    requirements.txt  — Python pip format
    package.json      — Node.js npm/yarn
    go.mod            — Go modules
    pom.xml           — Maven (Java)
    Cargo.toml        — Rust

Returns a list of PackageDependency dicts: {name, version, ecosystem}.
Version is the raw constraint string or None if unpinned.
"""

import logging
import re
from pathlib import Path
from typing import Optional
from typing import TypedDict

logger = logging.getLogger(__name__)


class PackageDependency(TypedDict):
    name: str
    version: Optional[str]
    ecosystem: str   # python | node | go | java | rust


# ── Python — requirements.txt ────────────────────────────────────────────────

def _parse_requirements_txt(text: str) -> list[PackageDependency]:
    """
    Parse pip requirements.txt format.

    Handles: pinned (==), ranges (>=, <=, ~=, !=), extras (pkg[extra]),
    environment markers, comments, -r includes (skipped), -e editable (skipped).
    """
    deps: list[PackageDependency] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        # Skip blanks, comments, options (-r, -e, --index-url, etc.)
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        # Strip inline comments
        line = line.split("#")[0].strip()
        # Strip environment markers (e.g. ; python_version >= "3.8")
        line = line.split(";")[0].strip()
        if not line:
            continue
        # Extract name and version constraint
        match = re.match(r"^([A-Za-z0-9_.\-]+)(\[.*?\])?\s*([><=!~,\s\d.*]+)?$", line)
        if match:
            name = match.group(1).strip()
            version = match.group(3).strip() if match.group(3) else None
            deps.append({"name": name, "version": version, "ecosystem": "python"})
        else:
            logger.debug("requirements.txt: could not parse line %r — skipping", line)
    return deps


# ── Node.js — package.json ────────────────────────────────────────────────────

def _parse_package_json(text: str) -> list[PackageDependency]:
    """Parse npm package.json — extracts dependencies and devDependencies."""
    import json

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        logger.error("package.json: JSON parse error: %s", exc)
        return []

    deps: list[PackageDependency] = []
    for section in ("dependencies", "devDependencies", "peerDependencies"):
        for name, version in data.get(section, {}).items():
            deps.append({"name": name, "version": str(version), "ecosystem": "node"})
    return deps


# ── Go — go.mod ──────────────────────────────────────────────────────────────

def _parse_go_mod(text: str) -> list[PackageDependency]:
    """Parse Go modules go.mod — extracts require directives."""
    deps: list[PackageDependency] = []
    in_require_block = False

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("//"):
            continue
        if line == "require (":
            in_require_block = True
            continue
        if in_require_block and line == ")":
            in_require_block = False
            continue
        # Single-line require
        single = re.match(r"^require\s+(\S+)\s+(\S+)", line)
        if single:
            deps.append({"name": single.group(1), "version": single.group(2), "ecosystem": "go"})
            continue
        # Inside require block
        if in_require_block and line:
            parts = line.split()
            if len(parts) >= 2:
                name, version = parts[0], parts[1]
                # Skip indirect-only deps (// indirect comment)
                deps.append({"name": name, "version": version, "ecosystem": "go"})

    return deps


# ── Java — pom.xml ────────────────────────────────────────────────────────────

def _parse_pom_xml(text: str) -> list[PackageDependency]:
    """Parse Maven pom.xml — extracts <dependency> blocks."""
    import xml.etree.ElementTree as ET

    deps: list[PackageDependency] = []
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        logger.error("pom.xml: XML parse error: %s", exc)
        return []

    # Maven uses namespaces; strip them for simple parsing
    ns_pattern = re.compile(r"\{.*?\}")

    def tag(el) -> str:
        return ns_pattern.sub("", el.tag)

    def find_text(parent, child_tag: str) -> Optional[str]:
        for child in parent:
            if tag(child) == child_tag:
                return (child.text or "").strip() or None
        return None

    for dep_el in root.iter():
        if tag(dep_el) != "dependency":
            continue
        group_id = find_text(dep_el, "groupId")
        artifact_id = find_text(dep_el, "artifactId")
        version = find_text(dep_el, "version")
        if group_id and artifact_id:
            name = f"{group_id}:{artifact_id}"
            deps.append({"name": name, "version": version, "ecosystem": "java"})

    return deps


# ── Rust — Cargo.toml ────────────────────────────────────────────────────────

def _parse_cargo_toml(text: str) -> list[PackageDependency]:
    """Parse Cargo.toml — extracts [dependencies] and [dev-dependencies]."""
    deps: list[PackageDependency] = []
    in_dep_section = False

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("#"):
            continue
        # Section headers
        if line.startswith("["):
            in_dep_section = line in ("[dependencies]", "[dev-dependencies]", "[build-dependencies]")
            continue
        if not in_dep_section or not line:
            continue
        # Simple: name = "version"
        simple = re.match(r'^([A-Za-z0-9_\-]+)\s*=\s*"([^"]*)"', line)
        if simple:
            deps.append({"name": simple.group(1), "version": simple.group(2), "ecosystem": "rust"})
            continue
        # Inline table: name = { version = "...", ... }
        inline = re.match(r'^([A-Za-z0-9_\-]+)\s*=\s*\{.*?version\s*=\s*"([^"]*)"', line)
        if inline:
            deps.append({"name": inline.group(1), "version": inline.group(2), "ecosystem": "rust"})

    return deps


# ── Public API ────────────────────────────────────────────────────────────────

# Exact filename matches
_PARSERS: dict[str, any] = {
    "requirements.txt": _parse_requirements_txt,
    "package.json":     _parse_package_json,
    "go.mod":           _parse_go_mod,
    "pom.xml":          _parse_pom_xml,
    "Cargo.toml":       _parse_cargo_toml,
}

# Suffix fallbacks — any file ending in these extensions uses the paired parser
_SUFFIX_PARSERS: dict[str, any] = {
    ".txt":  _parse_requirements_txt,  # e.g. test_requirements.txt, base.txt
    ".json": _parse_package_json,
    ".xml":  _parse_pom_xml,
}


def _detect_parser(manifest_path: Path):
    """
    Return the appropriate parser for a manifest file.

    Checks exact filename first, then falls back to file extension.
    """
    parser = _PARSERS.get(manifest_path.name)
    if parser:
        return parser
    return _SUFFIX_PARSERS.get(manifest_path.suffix.lower())


def parse_manifest(manifest_path: Path) -> list[PackageDependency]:
    """
    Parse a dependency manifest file and return a list of packages.

    Matches on exact filename first (requirements.txt, package.json, etc.),
    then falls back to file extension (.txt -> pip, .json -> npm, .xml -> maven).

    Args:
        manifest_path: Path to the manifest file.

    Returns:
        List of PackageDependency dicts.

    Raises:
        ValueError: if the file type cannot be determined.
    """
    parser = _detect_parser(manifest_path)
    if parser is None:
        supported = ", ".join(sorted(_PARSERS))
        raise ValueError(
            f"Unsupported manifest file '{manifest_path.name}'. "
            f"Supported filenames: {supported}. "
            f"Supported extensions: {', '.join(sorted(_SUFFIX_PARSERS))}."
        )

    text = manifest_path.read_text(encoding="utf-8")
    deps = parser(text)
    logger.info("Parsed %d dependencies from %s", len(deps), manifest_path.name)
    return deps


def supported_manifests() -> list[str]:
    """Return the list of supported manifest filenames."""
    return list(_PARSERS.keys())
