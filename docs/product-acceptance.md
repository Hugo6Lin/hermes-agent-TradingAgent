# Product Acceptance Criteria — Phase 13

## What This Document Is

Documents the Phase 13 acceptance criteria for the Hermes product. These are the
checkpoints that verify Hermes forms a closed product loop for boss use today.

## Acceptance Scope (A–E)

### A: Startup Acceptance

**Goal**: Hermes can be started without crashing.

| Test | Criterion | File |
|---|---|---|
| `test_app_cli_single_ticker_runs_without_crash` | `python -m agent.research_v1.app Research AAPL` exits 0 | `test_phase13_acceptance.py` |
| `test_batch_cli_status_runs_without_crash` | `batch_cli --app-root <dir> status` exits 0 | `test_phase13_acceptance.py` |
| `test_batch_cli_viewer_server_starts_without_crash` | `serve_viewer()` binds to port and responds to HTTP | `test_phase13_acceptance.py` |

### B: Research Acceptance

**Goal**: Core research pipeline produces signal + report + DB persistence.

| Test | Criterion | File |
|---|---|---|
| `test_single_ticker_run_produces_readable_result` | Single-ticker request produces CanonicalSignal + CanonicalReport | `test_phase13_acceptance.py` |
| `test_multi_ticker_run_produces_separate_results` | Multi-ticker request produces one result per ticker | `test_phase13_acceptance.py` |
| `test_db_backed_run_persists_canonical_signal_and_report` | Signal and report are persisted to SQLite | `test_phase13_acceptance.py` |
| `test_subagent_failure_does_not_crash_pipeline` | Subagent failure is recorded but pipeline continues | `test_phase13_acceptance.py` |

### C: Viewer Acceptance

**Goal**: Web viewer renders correctly in all modes.

| Test | Criterion | File |
|---|---|---|
| `test_legacy_mode_dashboard_renders_with_all_sections` | Legacy dashboard shows signals, positions, canonical panels | `test_phase13_acceptance.py` |
| `test_batch_mode_dashboard_renders_ticker_cards` | Batch mode shows ticker cards with ratings | `test_phase13_acceptance.py` |
| `test_end_of_day_summary_works_in_batch_mode` | `build_end_of_day_summary()` works in batch mode | `test_phase13_acceptance.py` |
| `test_end_of_day_summary_works_in_legacy_mode` | `build_end_of_day_summary()` works in legacy mode | `test_phase13_acceptance.py` |

### D: PDF Acceptance

**Goal**: PDF export works for canonical tasks and batch, handles non-ASCII correctly.

| Test | Criterion | File |
|---|---|---|
| `test_canonical_task_pdf_export_produces_valid_pdf` | `export_task_pdf()` produces valid PDF stub from DB | `test_phase13_acceptance.py` |
| `test_export_task_pdf_raises_key_error_when_no_data` | `KeyError` raised when no signals/reports exist | `test_phase13_acceptance.py` |
| `test_batch_pdf_export_with_non_ascii_content` | Chinese text survives save/load round-trip in batch DB | `test_phase13_acceptance.py` |

### E: Data and Stability Acceptance

**Goal**: DB persistence works, fallback is observable, no lock errors.

| Test | Criterion | File |
|---|---|---|
| `test_research_tasks_table_accepts_task_row` | `research_tasks` table is writable and readable | `test_phase13_acceptance.py` |
| `test_canonical_signals_and_reports_persist_and_are_listable` | canonical_signals/reports are listable after persist | `test_phase13_acceptance.py` |
| `test_fallback_reasons_visible_in_ticker_audit` | `tr.audit["fallback_reasons"]` is populated when Futu unavailable | `test_phase13_acceptance.py` |
| `test_app_run_does_not_produce_database_lock_errors` | No "locked" errors in result | `test_phase13_acceptance.py` |
| `test_windows_temp_permission_error_does_not_mask_real_failures` | No PermissionError in business logic | `test_phase13_acceptance.py` |

## Running the Acceptance Suite

```bash
pytest tests/agent/research_v1/test_phase13_acceptance.py -v
```

Expected: **19 passed** (with 1 warning about Futu deprecation).

## Pre-existing Known Failures (Not in Acceptance Scope)

| Test | Issue | Bug Tracker |
|---|---|---|
| `test_p6_viewer.py::test_build_viewer_snapshot_collects_*` | Windows `WinError 32` during temp file cleanup | Pre-existing |
| `test_p6_viewer.py::test_build_viewer_snapshot_tolerates_*` | Same Windows temp file issue | Pre-existing |

These are Windows OS-level sqlite temp file locking issues, not product logic bugs.

## What Is NOT in Current Product Scope

These are planned future enhancements, not current commitments:

- Autonomous LLM research loop (system does not self-trigger research)
- Real-time market data streaming (Futu polling is收盘后idle)
- Mobile app or notifications
- Multi-user / team collaboration
- Broker integration for live trading
- Options chain real-time updates beyond snapshot

## Current Product Commitment

Hermes TODAY provides:
- Canonical pipeline: natural language → signal + report + trade plan
- Futu OpenD market data (with Yahoo fallback)
- SQLite persistence of all research outputs
- Web viewer for signal/report review
- PDF export for batch reports
- Batch mode for structured multi-ticker research

## Acceptance Gate

All Phase 13 acceptance tests must pass before a Phase 14 feature branch is opened.
