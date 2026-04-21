#!/usr/bin/env python3
"""
Single-source doc-sync checker for Hermes.

This module is the canonical source of truth for the doc-sync rule:
    "If code in a tracked directory changes, the directory's README.md must also change,
     OR the directory must be explicitly acknowledged as not needing a README update."

Two interfaces:
    1. CLI: python check_docs.py [--acknowledge FILE] [FILE ...]
       - Reads changed file paths from FILE arguments (one per line) or stdin
       - Exits 0 if in sync, 1 if violations found
    2. Python API: check_sync(changed_files, acknowledged_dirs) -> list[str]
       - Returns list of violation messages (empty = pass)

Usage as pre-commit hook:
    python .git_hooks/check_docs.py  (reads from git staged files via git diff --cached)

Usage in tests / CI:
    from .git_hooks.check_docs import check_sync
    violations = check_sync(["agent/research_v1/app.py"], acknowledged_dirs=set())
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Iterable

# ---------------------------------------------------------------------------
# Configuration — single source of truth for tracked directories
# ---------------------------------------------------------------------------

# Directories where code changes require README to also change
TRACKED_CODE_DIRS = {
    "agent/",
    "agent/research_v1/",
    "agent/research_v1/analysts/",
    "agent/research_v1/data/",
    "agent/research_v1/memory/",          # legacy frozen
    "agent/research_v1/researchers/",     # legacy frozen
    "tests/",
    "tests/agent/",
    "tests/agent/research_v1/",
    "docs/",
}

# File extensions that count as "code" (not documentation or config)
CODE_EXTENSIONS = {".py", ".js", ".ts", ".jsx", ".tsx", ".sh", ".sql"}

# Directories that are fully frozen — code changes there are not violations
# even without a README update (because they are explicitly acknowledged frozen)
FROZEN_DIRS = {
    "agent/research_v1/memory/",
    "agent/research_v1/researchers/",
}

# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def _code_file_extensions() -> set[str]:
    return CODE_EXTENSIONS


def _is_code_file(path: str) -> bool:
    """Return True if this is a code file (not markdown/docs/shell)."""
    return Path(path).suffix in CODE_EXTENSIONS


def _tracked_dir_for(file_path: str) -> str | None:
    """Return the deepest matching tracked directory for a file path."""
    # Longest prefix match wins
    for tracked in sorted(TRACKED_CODE_DIRS, key=len, reverse=True):
        prefix = tracked.rstrip("/")
        if file_path == prefix or file_path.startswith(prefix + "/"):
            return tracked
    return None


def _readmes_for_tracked_dirs(changed_files: Iterable[str]) -> dict[str, bool]:
    """
    Return a dict: tracked_dir -> True if README.md is in changed_files.
    """
    readme_status = {}
    for tracked in TRACKED_CODE_DIRS:
        prefix = tracked.rstrip("/")
        readme = f"{prefix}/README.md" if prefix else "README.md"
        readme_status[tracked] = any(
            f == readme or f"./{f}" == f"./{readme}"
            for f in changed_files
        )
    return readme_status


def check_sync(
    changed_files: Iterable[str],
    acknowledged_dirs: set[str] | None = None,
) -> list[str]:
    """
    Check doc-sync compliance for a list of changed files.

    Rule: if code in a tracked directory changes, either:
      (a) the directory's README.md is also in changed_files, OR
      (b) the directory is in acknowledged_dirs (explicit freeze/no-op)

    Args:
        changed_files: iterable of file paths that changed
        acknowledged_dirs: set of tracked directory paths (with trailing /) that are
                        explicitly acknowledged as not needing a README update

    Returns:
        list of violation message strings (empty = compliant)
    """
    if acknowledged_dirs is None:
        acknowledged_dirs = set()

    violations = []
    file_list = list(changed_files)

    # Build: tracked_dir -> README changed?
    readme_status = _readmes_for_tracked_dirs(file_list)

    # Check each changed code file
    for file_path in file_list:
        if not _is_code_file(file_path):
            continue

        tracked = _tracked_dir_for(file_path)
        if tracked is None:
            continue  # Not in a tracked directory

        # Frozen dirs don't require README updates for code changes
        if tracked.rstrip("/") in {d.rstrip("/") for d in FROZEN_DIRS}:
            continue

        # Acknowledged dirs don't require README updates
        if tracked.rstrip("/") in {d.rstrip("/") for d in acknowledged_dirs}:
            continue

        # Check if README was also changed
        if readme_status.get(tracked, False):
            continue  # README was updated — compliant

        violations.append(
            f"code file '{file_path}' changed in tracked directory '{tracked}' "
            f"but {tracked}README.md was NOT updated. "
            f"Either update the README or acknowledge the directory "
            f"(add '{tracked}' to the acknowledged_dirs set)."
        )

    return violations


# ---------------------------------------------------------------------------
# CLI interface
# ---------------------------------------------------------------------------

def _read_acknowledged(path: str) -> set[str]:
    """Read acknowledged directories from a file (one per line, # = comment)."""
    acknowledged = set()
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                acknowledged.add(line.rstrip("/") + "/")
    except FileNotFoundError:
        pass
    return acknowledged


def _read_files_from_argv(argv: list[str]) -> list[str]:
    """Read file paths from remaining positional arguments or stdin."""
    paths = []
    for arg in argv:
        if arg == "-":
            # Read from stdin
            paths.extend(sys.stdin.read().splitlines())
        elif Path(arg).exists():
            # Read from file (one path per line)
            with open(arg, encoding="utf-8") as f:
                paths.extend(f.read().splitlines())
        else:
            # Direct path argument
            paths.append(arg)
    return [p.strip() for p in paths if p.strip()]


def _git_staged_files() -> list[str]:
    """Return list of staged file paths from git."""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            check=True,
        )
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check doc-sync compliance for Hermes. "
                   "Rule: if code in a tracked directory changes, README.md must also change.",
    )
    parser.add_argument(
        "--acknowledge",
        metavar="FILE",
        help="File listing acknowledged directories (one per line, # = comment)",
    )
    parser.add_argument(
        "files",
        nargs="*",
        metavar="FILE",
        help="Changed file paths. If omitted, reads from git staged files. "
             "Use '-' to read from stdin.",
    )
    args = parser.parse_args(argv)

    # Determine changed files
    if args.files:
        changed = _read_files_from_argv(args.files)
    else:
        changed = _git_staged_files()

    if not changed:
        print("(doc-sync check: no changed files, skipping)")
        return 0

    # Determine acknowledged dirs
    acknowledged = _read_acknowledged(args.acknowledge) if args.acknowledge else set()

    # Run check
    violations = check_sync(changed, acknowledged)

    if not violations:
        print("(doc-sync check: READMEs are in sync)")
        return 0

    # Report violations
    print("=" * 60)
    print("DOC-SYNC VIOLATIONS — README must be updated when code changes")
    print("=" * 60)
    for v in violations:
        print(f"  • {v}")
    print("-" * 60)
    print("To acknowledge a directory (e.g., frozen code), add it to the")
    print("--acknowledge FILE or to FROZEN_DIRS in check_docs.py.")
    print()
    return 1  # Exit code 1 = violations found


if __name__ == "__main__":
    sys.exit(main())
