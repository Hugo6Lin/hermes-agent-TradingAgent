# Developer Workflow

## Branch Strategy

- **Primary branch**: `main` — all Phase 11+ work is on `main`
- Feature work is done directly on `main` in this project (no long-lived feature branches)
- If multiple concurrent experiments are needed, use `git worktree` for isolation

## Pre-commit Workflow

1. Make your changes to the relevant `agent/research_v1/` files
2. **Check if README needs updating**: the doc-sync hook (`.git_hooks/pre-commit-check-docs`)
   will warn if you modified code in a tracked directory without updating the README
3. Run tests to verify your changes don't break anything:
   ```bash
   pytest tests/agent/research_v1/test_market_data_service.py -v   # Phase 12 tests
   pytest tests/agent/research_v1/test_phase13_acceptance.py -v     # Phase 13 tests
   pytest tests/agent/research_v1/ -v                               # Full suite
   ```
4. Commit with a clear message describing what changed and why

## Doc-Sync Rule

When you modify code in these directories, check whether the README needs updating:
- `agent/`
- `agent/research_v1/`
- `agent/research_v1/analysts/`
- `agent/research_v1/data/`
- `tests/`
- `tests/agent/`
- `tests/agent/research_v1/`
- `docs/`

To install the pre-commit hook:
```bash
# macOS/Linux
ln -sf ../../.git_hooks/pre-commit-check-docs .git/hooks/pre-commit

# Windows (cmd)
mklink .git\hooks\pre-commit ..\.git_hooks\pre-commit-check-docs
```

## Running Tests

```bash
# Phase 12 market data tests (fast)
pytest tests/agent/research_v1/test_market_data_service.py -v

# Phase 13 acceptance suite
pytest tests/agent/research_v1/test_phase13_acceptance.py -v

# App integration
pytest tests/agent/research_v1/test_app_integration.py -v

# Viewer tests
pytest tests/agent/research_v1/test_p6_viewer.py -v

# All research_v1 tests
pytest tests/agent/research_v1/ -v
```

## Adding a New Feature

1. **Write the code** in the appropriate module under `agent/research_v1/`
2. **Add tests** in `tests/agent/research_v1/` (same commit)
3. **Update the README** for the directory if the public interface changed
4. **Run the full suite** to verify no regressions
5. **Update `AGENT.md`** if the change affects module responsibilities or change propagation rules

## Modifying Canonical Dataclasses (contracts.py)

Canonical dataclass changes are high-risk — they break all consumers:

1. Check ALL files that use the dataclass
2. Check ALL tests that construct the dataclass
3. If adding a field: ensure all existing consumers handle the new field gracefully
4. If removing a field: ensure no consumers still reference it

## Adding a New Analyst Role

1. Add `AgentRole.NEW_ROLE` to `contracts.py`
2. Create `analysts/new_role.py` with `research_new_role(ticker, context, llm_client)`
3. Add case to `subagent_executor.py::_run_role_handler()`
4. Add test in `test_market_data_service.py` or `test_app_integration.py`
5. Update `agent/research_v1/README.md` (analysts table)
6. Update `AGENT.md` (agent/research_v1/)

## Modifying the Database Schema

Database changes require careful migration handling:

1. **Adding a table**: add to `database.py` with proper `CREATE TABLE IF NOT EXISTS`
2. **Adding a column**: requires `ALTER TABLE` — consider if existing DBs need migration
3. **Never drop columns** — just stop using them (backwards compatibility)
4. **Test with an existing DB**: verify that existing data still works after schema changes

## Reporting Bugs

When you find a bug, add a test that reproduces it. The test becomes the regression guard.

## Code Review Checklist

Before submitting (or before asking for review):

- [ ] Tests pass for the modified module
- [ ] Phase 13 acceptance suite passes
- [ ] No new `print()` statements in business logic
- [ ] No hardcoded tickers or credentials
- [ ] If public interface changed, README was checked and updated
- [ ] If `contracts.py` changed, all consumers were verified
- [ ] If database schema changed, migration path is clear

## Legacy Code Policy

Legacy files (`*_legacy.py`, `researchers/`, `grading.py`) are **frozen**.
Do not add features to them. If you need functionality that exists in legacy code,
migrate it to canonical first, then use the canonical version.
