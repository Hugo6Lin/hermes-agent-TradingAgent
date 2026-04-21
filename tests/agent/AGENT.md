# AGENT.md — tests/agent/

## Responsibilities

Test namespace for `agent/` package tests. This directory is a thin wrapper — it
exists only to mirror the `agent/` package structure.

## Boundaries

- Tests for `agent/research_v1/*` belong in `tests/agent/research_v1/`
- No business logic here — only test code
- Do not import from `agent/` directly in conftest fixtures without justification

## Key Interfaces

This directory has no code of its own. All test logic lives in `tests/agent/research_v1/`.

## Upstream / Downstream

- **Upstream**: `agent/` — the code being tested
- **Downstream**: `tests/agent/research_v1/` — the actual test implementation

## Change Propagation

No code changes should be made to `tests/agent/` directly. All test code belongs in
`tests/agent/research_v1/`.

## What NOT to Do

- Do NOT add test code at this level — put it in `tests/agent/research_v1/`
- Do NOT add conftest fixtures here — add them to `tests/conftest.py`
