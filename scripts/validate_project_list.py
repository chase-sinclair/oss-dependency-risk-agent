"""
Validates ingestion/github_archive/project_list.py for structural integrity.

Checks:
  1. Duplicate org/repo entries across all lists
  2. Malformed dicts — missing any of the 4 required keys
  3. Empty string values for any key
  4. Category value mismatch (entry's category != expected category for its list)
  5. get_all_projects() and get_project_set() return consistent counts
  6. PROJECTS master list includes all sub-lists
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

import ingestion.github_archive.project_list as pl

REQUIRED_KEYS = {"org", "repo", "category", "description"}

# Map each private list name → expected category value
LIST_CATEGORY_MAP = {
    "_DATA_ML":        "data_ml",
    "_AI_LLM":         "ai_llm",
    "_INFRASTRUCTURE": "infrastructure",
    "_WEB_FRAMEWORKS": "web_frameworks",
    "_DATABASES":      "databases",
    "_DEV_TOOLING":    "dev_tooling",
    "_SECURITY":       "security",
    "_OBSERVABILITY":  "observability",
    "_MESSAGING":      "messaging",
    "_CICD":           "cicd",
    "_PYTHON_LIBS":    "python_libs",
    "_JAVASCRIPT_LIBS":"js_libs",
    "_GO_LIBS":        "go_libs",
    "_RUST_LIBS":      "rust_libs",
    "_DISCOVERED":     "discovered",
}

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"
WARN = "\033[33mWARN\033[0m"

failures: list[str] = []
warnings: list[str] = []


def section(title: str) -> None:
    print(f"\n{'-' * 60}")
    print(f"  {title}")
    print('-' * 60)


def check(label: str, passed: bool, detail: str = "") -> None:
    status = PASS if passed else FAIL
    print(f"  [{status}] {label}")
    if detail:
        for line in detail.strip().splitlines():
            print(f"         {line}")
    if not passed:
        failures.append(label)


# ── 1. Duplicate org/repo ──────────────────────────────────────────────────
section("1. Duplicate org/repo entries")

seen: dict[str, str] = {}      # "org/repo" → list_name
dupes: list[str] = []

for list_name in LIST_CATEGORY_MAP:
    sub_list = getattr(pl, list_name)
    for p in sub_list:
        key = f"{p.get('org', '')}/{p.get('repo', '')}"
        if key in seen:
            dupes.append(f"{key}  (in {seen[key]} and {list_name})")
        else:
            seen[key] = list_name

check(
    f"No duplicate org/repo pairs ({len(dupes)} found)",
    len(dupes) == 0,
    "\n".join(dupes) if dupes else "",
)


# ── 2. Malformed dicts ────────────────────────────────────────────────────
section("2. Malformed dicts (missing required keys)")

malformed: list[str] = []

for list_name in LIST_CATEGORY_MAP:
    sub_list = getattr(pl, list_name)
    for i, p in enumerate(sub_list):
        missing = REQUIRED_KEYS - set(p.keys())
        if missing:
            malformed.append(f"{list_name}[{i}] missing keys: {missing}  entry={p}")

check(
    f"All entries have 4 required keys ({len(malformed)} malformed)",
    len(malformed) == 0,
    "\n".join(malformed) if malformed else "",
)


# ── 3. Empty string values ────────────────────────────────────────────────
section("3. Empty string values")

empty_vals: list[str] = []

for list_name in LIST_CATEGORY_MAP:
    sub_list = getattr(pl, list_name)
    for i, p in enumerate(sub_list):
        for key in REQUIRED_KEYS:
            val = p.get(key, None)
            if val is not None and str(val).strip() == "":
                empty_vals.append(f"{list_name}[{i}] key '{key}' is empty  entry={p}")

check(
    f"No empty string values ({len(empty_vals)} found)",
    len(empty_vals) == 0,
    "\n".join(empty_vals) if empty_vals else "",
)


# ── 4. Category mismatch ──────────────────────────────────────────────────
section("4. Category value matches list")

mismatches: list[str] = []

for list_name, expected_cat in LIST_CATEGORY_MAP.items():
    sub_list = getattr(pl, list_name)
    for i, p in enumerate(sub_list):
        actual = p.get("category", "")
        if actual != expected_cat:
            mismatches.append(
                f"{list_name}[{i}] expected category='{expected_cat}' "
                f"got='{actual}'  ({p.get('org')}/{p.get('repo')})"
            )

check(
    f"All category values match their list ({len(mismatches)} mismatches)",
    len(mismatches) == 0,
    "\n".join(mismatches) if mismatches else "",
)


# ── 5. API function counts ────────────────────────────────────────────────
section("5. API function return counts")

all_projects = pl.get_all_projects()
project_set  = pl.get_project_set()
raw_total    = sum(len(getattr(pl, n)) for n in LIST_CATEGORY_MAP)

check(
    f"get_all_projects() length matches raw list total  ({len(all_projects)} == {raw_total})",
    len(all_projects) == raw_total,
)

unique_count = len(project_set)
check(
    f"get_project_set() has no implicit dupes  ({unique_count} unique of {len(all_projects)} total)",
    unique_count == len(all_projects),
    "" if unique_count == len(all_projects) else f"  {len(all_projects) - unique_count} org/repo pairs are duplicated",
)

check(
    f"Total project count >= 800  ({len(all_projects)})",
    len(all_projects) >= 800,
)


# ── 6. Master list completeness ───────────────────────────────────────────
section("6. PROJECTS master list includes all sub-lists")

projects_set = set(id(p) for p in pl.PROJECTS)
missing_lists: list[str] = []

for list_name in LIST_CATEGORY_MAP:
    sub_list = getattr(pl, list_name)
    if not sub_list:
        missing_lists.append(f"{list_name} is empty")
        continue
    sample = sub_list[0]
    if id(sample) not in projects_set:
        missing_lists.append(f"{list_name} not included in PROJECTS")

check(
    f"All 15 sub-lists present in PROJECTS ({len(LIST_CATEGORY_MAP) - len(missing_lists)}/15)",
    len(missing_lists) == 0,
    "\n".join(missing_lists) if missing_lists else "",
)


# ── Summary ───────────────────────────────────────────────────────────────
section("Summary")

print(f"\n  Total projects  : {len(all_projects)}")
print(f"  Unique org/repos: {unique_count}")
print()

# Per-category breakdown
cats: dict[str, int] = {}
for p in all_projects:
    cats[p["category"]] = cats.get(p["category"], 0) + 1
for cat, count in sorted(cats.items()):
    print(f"    {cat:<20} {count}")

print()
if failures:
    print(f"  \033[31m{len(failures)} check(s) FAILED:\033[0m")
    for f in failures:
        print(f"    • {f}")
    sys.exit(1)
else:
    print(f"  \033[32mAll checks passed.\033[0m")
