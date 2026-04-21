# AGENT.md — tests/

## Responsibilities

All test code for Hermes. Tests verify that code works correctly, not that code exists.

## Boundaries

**Do NOT:**
- Put test code in `agent/` — tests belong in `tests/`
- Add new dependencies to tests without updating `requirements.txt`
- Write tests that only test "the function runs" without verifying behavior

**Do:**
- Follow the existing test structure (mirror `agent/` directory layout)
- Use `pytest` as the test runner
- Use `tempfile.TemporaryDirectory()` for DB path tests
- Mock LLM clients with `_MockLLMClient` pattern (see `test_app_integration.py`)
- Add tests for new features in the same PR as the feature

## Adding Tests for New Features

1. Add test to the appropriate file in `tests/agent/research_v1/`
2. If no suitable file exists, create one following the naming convention
3. Use the `conftest.py` at `tests/conftest.py` for shared fixtures
4. Mock the LLM client rather than calling real APIs
5. Use in-memory SQLite DBs via `tempfile.TemporaryDirectory()`

## Test File Naming

| Code under test | Test file |
|---|---|
| `market_data_service.py` | `test_market_data_service.py` |
| `app.py` | `test_app_integration.py` |
| `batch_cli.py` | `test_batch_cli.py` |
| `viewer.py` | `test_p6_viewer.py` |
| `database.py` | `test_database.py` |
| Full pipeline acceptance | `test_phase13_acceptance.py` |
| Doc standards | `test_doc_standards.py` |

## Key Interfaces

- `pytest` — test runner (configured in `pytest.ini` or `pyproject.toml`)
- `_MockLLMClient` — mock LLM client pattern for integration tests
- `tempfile.TemporaryDirectory()` — DB path isolation per test

## Upstream / Downstream

- **Upstream**: `agent/` — all code being tested lives here
- **Downstream**: None — tests are leaf nodes

## Change Propagation

When code in `agent/` changes, the corresponding test file must be verified.
When a new module is added to `agent/`, a corresponding test file should be created in `tests/agent/research_v1/`.

## What NOT to Do

- Do NOT import business logic directly from `agent/` into test fixtures without justification
- Do NOT write tests that hit real LLM APIs or live market data connections
- Do NOT make tests order-dependent (each test must be independently runnable)
