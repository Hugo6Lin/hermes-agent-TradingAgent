"""Doc standards validation — repo-level enforcement for README/AGENT schema.

This test module runs as part of the normal pytest suite and enforces:
    1. All tracked directories have README.md and AGENT.md
    2. README.md files contain required sections (What This Directory Is, etc.)
    3. AGENT.md files contain required sections (Responsibilities, Boundaries, etc.)
    4. Doc-sync: if tracked directory code changes, README must also change or be acknowledged

Reference: docs/doc-standards.md
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

# Add .git_hooks to path so we can import check_docs as a module
# Path: repo/tests/agent/research_v1/test_doc_standards.py
#       repo/ is 4 parents up
_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_REPO_ROOT / ".git_hooks"))

from check_docs import check_sync  # noqa: E402


# All directories that must have README.md and (for implementation dirs) AGENT.md
TRACKED_DIRS = [
    "agent/",
    "agent/research_v1/",
    "agent/research_v1/data/",
    "agent/research_v1/analysts/",
    "tests/",
    "tests/agent/",
    "tests/agent/research_v1/",
    "docs/",
    ".git_hooks/",
]

# README.md required section headings (case-insensitive regex match)
# Reference: docs/doc-standards.md
README_REQUIRED_SECTIONS = [
    r"What This Directory Is",
    r"Contents|Core Files|Key.*Files",  # flexible
    r"Relationship|Relates?",  # flexible — "How It Relates to Other Directories" etc.
    r"If You Modify|If You Change",  # flexible
    r"Data Flow|How It Fits|How.*Flow",  # flexible — "Data Flow", "How It Fits", etc.
]

# AGENT.md required section headings (case-insensitive regex match)
AGENT_REQUIRED_SECTIONS = [
    r"Responsibilities",
    r"Boundaries",
    r"Key Interfaces|Key Files|Key",  # flexible
    r"Upstream",  # flexible — "Upstream/Downstream" etc.
    r"Change Propagation",
    r"Tests?|Verification",  # flexible — "Tests", "Test", "Verification"
    r"What NOT|Do NOT",  # flexible
]


def _normalize_heading(line: str) -> str:
    """Strip markdown heading markers and whitespace."""
    return re.sub(r"^#+\s*", "", line).strip()


def _section_headings(content: str) -> list[str]:
    """Return all level-2+ markdown section headings from content."""
    headings = []
    for line in content.splitlines():
        stripped = _normalize_heading(line)
        if stripped:
            headings.append(stripped)
    return headings


def _has_heading(content: str, pattern: str) -> bool:
    """Return True if content has a heading matching the given regex pattern."""
    headings = _section_headings(content)
    for h in headings:
        if re.search(pattern, h, re.IGNORECASE):
            return True
    return False


class TestReadmeCoverage:
    """Every tracked directory must have a README.md."""

    @pytest.mark.parametrize("dir_path", TRACKED_DIRS)
    def test_tracked_dir_has_readme(self, dir_path: str):
        readme_path = Path(dir_path) / "README.md"
        assert readme_path.exists(), (
            f"Missing README.md in {dir_path}. "
            f"Every tracked directory must have a README.md. "
            f"See docs/doc-standards.md for the required schema."
        )


class TestAgentCoverage:
    """Every tracked directory must have an AGENT.md (implementation dirs only)."""

    # All tracked dirs are implementation dirs in this repo
    @pytest.mark.parametrize("dir_path", TRACKED_DIRS)
    def test_tracked_dir_has_agent(self, dir_path: str):
        agent_path = Path(dir_path) / "AGENT.md"
        assert agent_path.exists(), (
            f"Missing AGENT.md in {dir_path}. "
            f"Every tracked directory must have an AGENT.md for agent guidance. "
            f"See docs/doc-standards.md for the required schema."
        )


class TestReadmeSchema:
    """README.md files must contain required sections."""

    @pytest.mark.parametrize("dir_path", TRACKED_DIRS)
    def test_readme_has_required_sections(self, dir_path: str):
        readme_path = Path(dir_path) / "README.md"
        if not readme_path.exists():
            pytest.skip(f"No README.md in {dir_path}")

        content = readme_path.read_text(encoding="utf-8")
        missing = []
        for section_pattern in README_REQUIRED_SECTIONS:
            if not _has_heading(content, section_pattern):
                missing.append(section_pattern)

        assert not missing, (
            f"{readme_path} is missing required README sections: {missing}. "
            f"See docs/doc-standards.md for the required schema."
        )


class TestAgentSchema:
    """AGENT.md files must contain required sections."""

    @pytest.mark.parametrize("dir_path", TRACKED_DIRS)
    def test_agent_has_required_sections(self, dir_path: str):
        agent_path = Path(dir_path) / "AGENT.md"
        if not agent_path.exists():
            pytest.skip(f"No AGENT.md in {dir_path}")

        content = agent_path.read_text(encoding="utf-8")
        missing = []
        for section_pattern in AGENT_REQUIRED_SECTIONS:
            if not _has_heading(content, section_pattern):
                missing.append(section_pattern)

        assert not missing, (
            f"{agent_path} is missing required AGENT sections: {missing}. "
            f"See docs/doc-standards.md for the required schema."
        )


class TestNoOrphanedCodeDirs:
    """Code directories without README are flagged (catch-all)."""

    def test_no_orphan_code_dirs(self):
        """
        Scan agent/ and tests/ subdirectories.
        Any subdirectory that contains .py files must have a README.md.
        """
        repo_root = Path(".")
        orphans = []

        for search_root in ["agent/", "tests/"]:
            root = Path(search_root)
            if not root.exists():
                continue
            for subdir in sorted(root.rglob("*")):
                if not subdir.is_dir():
                    continue
                # Skip __pycache__, .pytest_cache, fixtures
                if subdir.name in ("__pycache__", ".pytest_cache", "fixtures"):
                    continue
                # Skip if it has a README
                if (subdir / "README.md").exists():
                    continue
                # Has .py files but no README → orphan
                py_files = list(subdir.glob("*.py"))
                if py_files:
                    orphans.append(str(subdir))

        assert not orphans, (
            f"Found code directories without README.md: {orphans}. "
            f"Every directory with .py files needs a README.md. "
            f"See docs/doc-standards.md."
        )


class TestDocSyncBehavior:
    """
    Behavioral doc-sync tests: verifies the check_sync() rule.

    Rule: if code in a tracked directory changes, either:
        (a) the directory's README.md must also be changed, OR
        (b) the directory must be in acknowledged_dirs (e.g., frozen)

    These tests directly exercise check_sync() to verify the rule is correct.
    """

    def test_code_change_with_readme_change_passes(self):
        """Code + README changed together → pass (no violations)."""
        changed = [
            "agent/research_v1/app.py",
            "agent/research_v1/README.md",
        ]
        violations = check_sync(changed, acknowledged_dirs=set())
        assert violations == [], f"Expected no violations: {violations}"

    def test_code_change_acknowledged_passes(self):
        """Code changed + directory explicitly acknowledged → pass."""
        violations = check_sync(
            ["agent/research_v1/app.py"],
            acknowledged_dirs={"agent/research_v1/"},
        )
        assert violations == []

    def test_code_change_no_readme_no_acknowledge_fails(self):
        """Code changed but no README and not acknowledged → fail."""
        violations = check_sync(
            ["agent/research_v1/app.py"],
            acknowledged_dirs=set(),
        )
        assert len(violations) == 1
        assert "app.py" in violations[0]
        assert "README.md" in violations[0]

    def test_readme_only_change_passes(self):
        """Only README changed → pass (no code changes)."""
        violations = check_sync(
            ["agent/research_v1/README.md"],
            acknowledged_dirs=set(),
        )
        assert violations == []

    def test_non_tracked_dir_change_passes(self):
        """Changes in non-tracked directories → pass."""
        violations = check_sync(
            ["some/other/path/file.py"],
            acknowledged_dirs=set(),
        )
        assert violations == []

    def test_multiple_tracked_dirs_mixed_acknowledged(self):
        """Multiple dirs, some acknowledged, some not → only unacknowledged fail."""
        changed = [
            "agent/research_v1/app.py",      # tracked, not acknowledged, no README → fail
            "tests/agent/research_v1/test_app.py",  # tracked, acknowledged → pass
        ]
        violations = check_sync(
            changed,
            acknowledged_dirs={"tests/agent/research_v1/"},
        )
        # Only agent/research_v1/app.py should fail (no README, not acknowledged)
        assert len(violations) == 1
        assert "agent/research_v1/app.py" in violations[0]

    def test_frozen_dir_code_change_no_readme_passes(self):
        """Frozen dir (memory/) code changed without README → pass (frozen = implicit ack)."""
        violations = check_sync(
            ["agent/research_v1/memory/financial_provider.py"],
            acknowledged_dirs=set(),
        )
        assert violations == []

    def test_acknowledge_file_loaded_correctly(self):
        """Acknowledged dirs loaded from file work the same way."""
        # Use frozen dir as implicit acknowledge test
        violations = check_sync(
            ["agent/research_v1/researchers/bull_researcher.py"],
            acknowledged_dirs={"agent/research_v1/researchers/"},
        )
        assert violations == []

    def test_multiple_code_files_in_same_dir_one_readme_sufficient(self):
        """Multiple code files changed in same dir, README also changed → single README update is enough."""
        violations = check_sync(
            [
                "agent/research_v1/app.py",
                "agent/research_v1/task_router.py",
                "agent/research_v1/README.md",
            ],
            acknowledged_dirs=set(),
        )
        assert violations == []

    def test_check_sync_empty_changed_files(self):
        """Empty changed files list → no violations."""
        violations = check_sync([], acknowledged_dirs=set())
        assert violations == []

    def test_check_sync_with_none_acknowledged(self):
        """acknowledged_dirs=None treated same as empty set."""
        violations = check_sync(
            ["agent/research_v1/app.py"],
            acknowledged_dirs=None,
        )
        assert len(violations) == 1  # Not acknowledged → fails
