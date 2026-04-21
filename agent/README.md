# agent/ — Python Package Root

## What This Directory Is

The Python package root for Hermes. `agent/` is added to `sys.path` and all first-party
modules live under `agent/research_v1/`.

## Contents

```
agent/
  __init__.py          # Package marker (may expose top-level imports)
  research_v1/         # ★ Primary implementation — canonical pipeline
  research_v1/analysts/   # Individual analyst agents
  research_v1/data/       # Data providers and persistence
  research_v1/researchers/ # Legacy bull/bear researchers (frozen)
```

## Relationship to Other Directories

- `tests/agent/research_v1/` — mirrors `agent/research_v1/` for unit/integration tests
- `docs/` — system documentation, boss manual, developer guides
- `skills/` — Futu OpenD setup/install skills

## How Code Flows Through Here

1. User runs `python -m agent.research_v1.app "Research AAPL"`
2. Python's import system resolves `agent.research_v1.app`
3. `app.py` imports from `agent.research_v1.task_router`, `orchestrator`, `subagent_executor`, etc.
4. Subagents import from `agent.research_v1.analysts.*`, `agent.research_v1.data.*`
5. Data persists through `agent.research_v1.data.database`

## If You Modify Code Here

- `agent/research_v1/app.py` — check `tests/agent/research_v1/test_app_integration.py`
- `agent/research_v1/contracts.py` — check ALL tests that construct canonical dataclasses
- `agent/research_v1/data/` — check `tests/agent/research_v1/test_database.py`
- Any new top-level module must be added to `requirements.txt` if it adds dependencies
