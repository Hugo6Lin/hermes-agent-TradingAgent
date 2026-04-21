# tests/ — Test Suite

## What This Directory Is

All test code for the Hermes project. Tests mirror the `agent/` structure.

## Structure / Contents

```
tests/
  agent/
    research_v1/     # mirrors agent/research_v1/
      fixtures/      # test fixtures (JSON payloads, etc.)
      test_market_data_service.py   # Phase 12 Futu-first market data
      test_phase13_acceptance.py    # Phase 13 product acceptance
      test_app_integration.py        # app integration tests
      test_p6_viewer.py            # viewer tests
      test_batch_cli.py            # batch_cli tests
      test_database.py             # database tests
      test_futu_provider.py         # Futu provider tests
      test_p3_signal_quality.py    # Phase 3 signal quality tests
      test_task_router.py          # task router tests
      test_report_pdf.py           # PDF export tests
```

## If You Modify Code Here

When you add tests for new features, update this README to include the new test file.
See `tests/agent/research_v1/README.md` for the full test suite guide.

## Data Flow

Tests in this directory mirror the `agent/` package structure:
`tests/agent/research_v1/` contains integration and acceptance tests that exercise the full
pipeline. Each test file corresponds to one or more modules in `agent/research_v1/`.

## How Tests Relate to Code

- `tests/agent/research_v1/test_market_data_service.py` ↔ `agent/research_v1/market_data_service.py`
- `tests/agent/research_v1/test_app_integration.py` ↔ `agent/research_v1/app.py`
- `tests/agent/research_v1/test_phase13_acceptance.py` ↔ entire canonical pipeline

## Running Tests

```bash
# All research_v1 tests
pytest tests/agent/research_v1/ -v

# Phase 12 market data
pytest tests/agent/research_v1/test_market_data_service.py -v

# Phase 13 acceptance
pytest tests/agent/research_v1/test_phase13_acceptance.py -v

# Specific test
pytest tests/agent/research_v1/test_phase13_acceptance.py::TestStartupAcceptance -v
```

## Known Pre-existing Failures (Do Not Fix)

- `test_p6_viewer.py::test_build_viewer_snapshot_collects_signals_positions_and_paper_trades` — Windows `WinError 32` (temp file locked during cleanup)
- `test_p6_viewer.py::test_build_viewer_snapshot_tolerates_missing_watchlist_tables` — same Windows issue

These are Windows-specific sqlite temp file locking issues, not product bugs.

## Test Fixtures

Fixtures live in `tests/agent/research_v1/fixtures/` and include:
- `sample_batch_payload.json` — example batch research payload
