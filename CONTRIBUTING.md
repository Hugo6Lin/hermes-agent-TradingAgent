# Contributing to Hermes

## Doc-Sync Rule

When you modify code in a directory that has a `README.md`, you MUST check whether the
README needs updating. If it does, update it in the same commit.

**Tracked directories** (must have README when modified):
- `agent/`
- `agent/research_v1/`
- `agent/research_v1/analysts/`
- `agent/research_v1/data/`
- `tests/`
- `tests/agent/`
- `tests/agent/research_v1/`
- `docs/`

## Pre-commit Check

A lightweight pre-commit hook verifies the doc-sync rule. To install it:

```bash
# Install the pre-commit hook (one-time)
ln -sf ../../.git_hooks/pre-commit-check-docs .git/hooks/pre-commit
# Or on Windows:
# cmd /c "mklink .git\hooks\pre-commit ..\.git_hooks\pre-commit-check-docs"
```

The hook runs `python .git_hooks/check_docs.py` before each commit. If it detects
code changes in a tracked directory without a corresponding README update, it prints
a warning (non-blocking) and suggests what to check.

**Important**: The hook warns but does NOT block commits. Updating the README is a
professional judgment call — if the change is purely cosmetic (e.g., fixing a typo
in an unrelated function), the hook's suggestion can be ignored with a comment.

## What Counts as "Updating the README"

- Adding a new exported function or class
- Changing the signature of an existing function
- Adding a new dependency
- Adding a new data file or schema
- Changing the data flow through a module
- Adding a new subdirectory

## What Does NOT Need README Updates

- Fixing a bug without changing the public interface
- Updating tests without changing the code's behavior
- Refactoring internal implementation without changing the interface
- Adding comments or docstrings
- Cosmetic formatting changes

## Running Checks Manually

```bash
python .git_hooks/check_docs.py
```

## Adding a New Tracked Directory

Add the directory to the `TRACKED_DIRS` list in `.git_hooks/check_docs.py`.

## Code Style

- Python: follow existing style (4-space indent, `snake_case` for functions/variables)
- No new `print()` statements in business logic — use structured logging
- All new functions/classes must have docstrings
- Dataclass fields: use type annotations
- No hardcoded credentials or tickers
