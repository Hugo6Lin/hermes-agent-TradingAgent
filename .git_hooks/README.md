# .git_hooks/ — Repository Git Hooks

## What This Directory Is

Contains git pre-commit hooks for Hermes. These are local developer tools that run
before each commit to enforce documentation standards.

## If You Modify Code Here

If you modify the hook logic, also update:
- `CONTRIBUTING.md` if behavior changes
- `docs/doc-standards.md` if schema changes affect the validator
- `test_doc_standards.py` if you change validation logic

## Data Flow / How It Fits

The hook runs as a pre-commit check on the developer's local machine. It reads
staged files via `git diff --cached --name-only`, passes them to `check_docs.py`, and
reports violations without blocking the commit. The pytest-based repo-level
enforcement (`test_doc_standards.py`) runs independently in CI and verifies structural
compliance across all tracked directories.

## Contents / Files

| File | Purpose |
|---|---|
| `check_docs.py` | Python script that checks doc-sync compliance |
| `pre-commit-check-docs` | Shell wrapper that invokes `check_docs.py` |

## How to Install the Pre-commit Hook

```bash
# macOS / Linux (from repo root)
ln -sf ../../.git_hooks/pre-commit-check-docs .git/hooks/pre-commit

# Windows (cmd)
mklink .git\hooks\pre-commit ..\.git_hooks\pre-commit-check-docs
```

## What the Hook Does

`pre-commit-check-docs` runs `check_docs.py` before every commit:

1. Reads the list of staged files from git
2. Checks if any are in tracked directories (`agent/`, `tests/`, `docs/`, etc.)
3. If yes, checks whether a `README.md` was also staged in the same directory
4. Prints a **warning** if code changed without a corresponding README update
5. **Does NOT block commits** — the check is advisory only

## Relationship to Repo-Level Enforcement

The pre-commit hook is a **local developer convenience**. The **repo-level**
doc-sync enforcement is `pytest tests/agent/research_v1/test_doc_standards.py`, which
runs in the normal pytest suite and fails if:
- Any tracked directory is missing `README.md` or `AGENT.md`
- Any `README.md` or `AGENT.md` is missing required sections

Both mechanisms must pass for full compliance:
- Pre-commit hook: warns when code changes without README update (local)
- pytest test: enforces structural compliance of all doc files (runs in CI)

## Running the Check Manually

```bash
python .git_hooks/check_docs.py
```

## Notes

- These hooks are not tracked by git (`.git_hooks/` is in `.gitignore`)
- Each developer must install them manually on their machine
- The hook always exits 0 — it never blocks commits
