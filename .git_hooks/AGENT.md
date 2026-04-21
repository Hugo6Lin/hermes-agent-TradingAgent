# AGENT.md — .git_hooks/

## Responsibilities

Maintain the git pre-commit hooks that enforce documentation standards. This directory
contains tooling, not business logic.

## Boundaries

**Do NOT:**
- Put business logic in this directory
- Modify the hook logic without updating `CONTRIBUTING.md` and the hook tests
- Add new hooks without adding corresponding pytest tests in `test_doc_standards.py`

**Do:**
- Keep hook logic minimal and fast (hook runs before every commit)
- Keep `check_docs.py` as a standalone script (no external dependencies beyond stdlib)

## Key Interfaces

| File | Purpose |
|---|---|
| `check_docs.py` | Python stdlib script — reads git staged files, checks doc-sync compliance |
| `pre-commit-check-docs` | POSIX shell script — invokes `check_docs.py` from git hook context |

## Change Propagation

When you modify hooks:

1. Update `CONTRIBUTING.md` if behavior changes (e.g., new tracked dirs)
2. Update `docs/doc-standards.md` if the schema changes
3. Update `test_doc_standards.py` if the validation logic changes
4. The pytest test `test_doc_standards.py` validates doc coverage independently of the hook

## Upstream / Downstream

- **Upstream**: git staged files — the hook reads `git diff --cached --name-only`
- **Downstream**: `CONTRIBUTING.md`, `docs/doc-standards.md`, `test_doc_standards.py`

## Tests

Doc enforcement tests live in:
```
tests/agent/research_v1/test_doc_standards.py
```

Run them with:
```bash
pytest tests/agent/research_v1/test_doc_standards.py -v
```

## What NOT to Do

- Do NOT make the hook block commits — it must always exit 0
- Do NOT add dependencies to `check_docs.py` beyond Python standard library
- Do NOT add hooks that run slow commands (hook runs before every commit)
- Do NOT modify hook behavior without updating both the hook AND the pytest test
