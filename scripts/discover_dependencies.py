"""
CLI entry point for dependency discovery.

Parses one or more manifest files, resolves packages to GitHub repositories,
and optionally adds them to the monitoring list in project_list.py.

Usage:
    python scripts/discover_dependencies.py --manifest requirements.txt
    python scripts/discover_dependencies.py --manifest package.json
    python scripts/discover_dependencies.py --manifest requirements.txt --manifest package.json
    python scripts/discover_dependencies.py --manifest requirements.txt --dry-run
    python scripts/discover_dependencies.py --list
    python scripts/discover_dependencies.py --remove pydantic/pydantic
"""

import argparse
import logging
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

_UNRESOLVED_LOG = _PROJECT_ROOT / "docs" / "unresolved.txt"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Discover and onboard OSS dependencies from manifest files.",
    )
    parser.add_argument(
        "--manifest",
        action="append",
        dest="manifests",
        metavar="FILE",
        default=[],
        help="Path to a manifest file (repeatable). Supported: "
             "requirements.txt, package.json, go.mod, pom.xml, Cargo.toml",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Show what would be added without modifying project_list.py.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        dest="list_projects",
        default=False,
        help="List all currently discovered projects and exit.",
    )
    parser.add_argument(
        "--remove",
        metavar="ORG/REPO",
        default=None,
        help="Remove a project from the discovered list (e.g. pydantic/pydantic).",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help="Enable DEBUG logging.",
    )
    return parser.parse_args()


def _write_unresolved(names: list[str], manifest_name: str) -> None:
    """Append unresolved package names to docs/unresolved.txt."""
    if not names:
        return
    _UNRESOLVED_LOG.parent.mkdir(parents=True, exist_ok=True)
    with _UNRESOLVED_LOG.open("a", encoding="utf-8") as f:
        f.write(f"\n# {manifest_name}\n")
        for name in names:
            f.write(f"{name}\n")
    logger.info("Unresolved packages logged to %s", _UNRESOLVED_LOG)


def _cmd_list() -> int:
    from ingestion.discovery.project_registry import list_discovered
    projects = list_discovered()
    if not projects:
        print("No discovered projects in monitoring list.")
        return 0
    print(f"\nDiscovered projects ({len(projects)}):\n")
    for p in projects:
        print(f"  {p['org']}/{p['repo']:<40}  {p['description']}")
    return 0


def _cmd_remove(full_name: str) -> int:
    from ingestion.discovery.project_registry import remove_project
    parts = full_name.split("/", 1)
    if len(parts) != 2:
        logger.error("--remove requires 'org/repo' format, got: %r", full_name)
        return 1
    org, repo = parts
    removed = remove_project(org, repo)
    return 0 if removed else 1


def _cmd_discover(manifest_paths: list[Path], dry_run: bool) -> int:
    from ingestion.discovery.github_resolver import resolve_packages
    from ingestion.discovery.manifest_parser import parse_manifest
    from ingestion.discovery.project_registry import add_projects, get_current_projects

    existing = get_current_projects()
    all_packages: list[dict] = []
    manifest_names: list[str] = []

    for path in manifest_paths:
        if not path.exists():
            logger.error("Manifest file not found: %s", path)
            return 1
        try:
            packages = parse_manifest(path)
        except ValueError as exc:
            logger.error("%s", exc)
            return 1
        logger.info("Parsed %d dependencies from %s", len(packages), path.name)
        all_packages.extend(packages)
        manifest_names.append(path.name)

    if not all_packages:
        logger.warning("No dependencies found in the provided manifest(s).")
        return 0

    print(f"\nParsed {len(all_packages)} total dependencies from "
          f"{len(manifest_paths)} manifest(s).\n")

    resolved, unresolved = resolve_packages(all_packages, existing)

    # Print resolution summary
    pct = len(resolved) / len(all_packages) * 100 if all_packages else 0
    print(f"Resolved {len(resolved)}/{len(all_packages)} to GitHub repositories ({pct:.0f}%)")
    if unresolved:
        print(f"Failed to resolve {len(unresolved)} package(s) — logged to docs/unresolved.txt")

    if resolved:
        action = "Would add" if dry_run else "Adding"
        print(f"\n{action} {len(resolved)} new project(s) to monitoring list:\n")
        for p in resolved:
            print(f"  + {p['org']}/{p['repo']:<40}  {p['description']}")
        print()

    # Write to project_list.py (or preview in dry-run)
    added, already = add_projects(resolved, dry_run=dry_run)

    if already:
        print(f"  ({already} package(s) already in monitoring list — skipped)")

    # Log unresolved packages
    for path in manifest_paths:
        _write_unresolved(unresolved, path.name)

    if dry_run:
        print("\n[dry-run] No changes written to project_list.py.")
    else:
        print(f"\nDone. Added {added} new project(s) to project_list.py.")
        if added:
            print("Run the ingestion pipeline to start collecting events for new projects:")
            print("  python scripts\\run_ingestion.py --backfill --days 30")

    return 0


def main() -> int:
    args = _parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # --list
    if args.list_projects:
        return _cmd_list()

    # --remove
    if args.remove:
        return _cmd_remove(args.remove)

    # --manifest (required for discovery)
    if not args.manifests:
        logger.error(
            "No manifest files specified. Use --manifest FILE or --list / --remove.\n"
            "Run with --help for usage."
        )
        return 1

    manifest_paths = [Path(m) for m in args.manifests]
    return _cmd_discover(manifest_paths, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
