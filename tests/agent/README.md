# tests/agent/ — Agent Tests

## What This Directory Is

Mirrors `agent/` structure for test code. All Python tests live here.

## Contents / Core Files

```
tests/agent/
  research_v1/     # mirrors agent/research_v1/
```

## Relationship to Other Directories

- `agent/` — the code being tested
- `tests/conftest.py` — shared pytest fixtures
- `tests/agent/research_v1/fixtures/` — test data files

## If You Modify Code Here

All test code belongs in `tests/agent/research_v1/`, not at this level.
If you add a new test module to `agent/research_v1/`, create the corresponding
test file in `tests/agent/research_v1/`.

## Data Flow / How It Fits

Test files in `tests/agent/research_v1/` are organized to mirror the `agent/research_v1/`
source tree. Each test module corresponds to one or more source modules under
`agent/research_v1/`. The `tests/conftest.py` at the repo level provides shared fixtures
used across all test modules.
