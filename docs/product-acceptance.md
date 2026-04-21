# Product Acceptance Criteria — Phase 13 + Phase 16

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

## Phase 16 Acceptance — Watchlist & Alert Center

**Goal**: Boss-centric monitored watchlists with alert-only advisory, business-day cadence, and thesis-state-aware alert levels.

### F: Watchlist Contract Acceptance

| Test | Criterion | File |
|---|---|---|
| `test_watchlist_entry_validates_status` | WatchlistEntry rejects invalid status | `test_watchlist_alerts.py` |
| `test_watchlist_entry_validates_thesis_state` | WatchlistEntry rejects invalid thesis_state | `test_watchlist_alerts.py` |
| `test_watchlist_entry_validates_alert_level` | WatchlistEntry rejects invalid alert_level | `test_watchlist_alerts.py` |
| `test_watchlist_alert_validates_fields` | WatchlistAlert rejects invalid alert_level or missing fields | `test_watchlist_alerts.py` |

### G: Watchlist Persistence Acceptance

| Test | Criterion | File |
|---|---|---|
| `test_save_and_list_watchlist_entry` | WatchlistEntry round-trips through SQLite | `test_watchlist_alerts.py` |
| `test_save_watchlist_entry_replace` | INSERT OR REPLACE updates existing entry | `test_watchlist_alerts.py` |

### H: Watchlist Cadence Acceptance

| Test | Criterion | File |
|---|---|---|
| `test_business_day_cadence_for_active_statuses` | Held/HighPriority/ResearchInProgress → business_day | `test_watchlist_alerts.py` |
| `test_weekly_cadence_for_passive_watch` | PassiveWatch → weekly | `test_watchlist_alerts.py` |
| `test_tomorrow_is_business_day` | Business day helper excludes weekends | `test_watchlist_alerts.py` |
| `test_next_cadence_respects_business_day_gap` | Weekly cadence skips weekends | `test_watchlist_alerts.py` |

### I: Thesis State → Alert Level Acceptance

| Test | Criterion | File |
|---|---|---|
| `test_broken_triggers_critical_alert` | Broken → AlertLevel.CRITICAL | `test_watchlist_alerts.py` |
| `test_weakening_triggers_high_alert` | Weakening → AlertLevel.HIGH | `test_watchlist_alerts.py` |
| `test_strengthening_triggers_medium_alert` | Strengthening → AlertLevel.MEDIUM | `test_watchlist_alerts.py` |
| `test_stable_triggers_no_alert` | Stable → AlertLevel.NONE | `test_watchlist_alerts.py` |

### J: Alert Generation and Summary Acceptance

| Test | Criterion | File |
|---|---|---|
| `test_build_alert_produces_watchlist_alert` | build_alert() returns WatchlistAlert with correct level | `test_watchlist_alerts.py` |
| `test_summarize_reports_correct_counts` | summarize() counts by status and alert_level | `test_watchlist_alerts.py` |
| `test_update_thesis_state_changes_state` | update_thesis_state() changes thesis_state | `test_watchlist_alerts.py` |

## Running the Phase 16 Acceptance Suite

```bash
pytest tests/agent/research_v1/test_watchlist_alerts.py tests/agent/research_v1/test_bullish_decision_integration.py -v
```

Expected: **56 passed** (34 bullish + 22 watchlist) + pre-existing Phase 13 failures (Windows temp file locks — unrelated to Phase 16).

Phase 16 wiring is verified by the bullish integration tests (`test_bullish_decision_integration.py`) and by `test_database.py` (watchlist persistence) and `test_report_pdf.py` (PDF watchlist table).

## Phase 17 Acceptance — Validation Engine

**Goal**: Lightweight validation annotation layer without overriding thesis or instrument decisions.

### L: Validation Contract Acceptance

| Test | Criterion | File |
|---|---|---|
| `test_valid_construction` | ValidationResult accepts all valid field values | `test_validation_engine.py` |
| `test_rejects_invalid_regime` | Invalid regime raises ValueError | `test_validation_engine.py` |
| `test_rejects_invalid_historical_support` | Invalid historical_support raises ValueError | `test_validation_engine.py` |
| `test_rejects_invalid_environment_fit` | Invalid environment_fit raises ValueError | `test_validation_engine.py` |
| `test_rejects_invalid_failure_mode` | Invalid main_failure_mode raises ValueError | `test_validation_engine.py` |
| `test_rejects_confidence_below_0` | Confidence < 0 raises ValueError | `test_validation_engine.py` |
| `test_rejects_confidence_above_1` | Confidence > 1 raises ValueError | `test_validation_engine.py` |

### M: Regime Detection Acceptance

| Test | Criterion | File |
|---|---|---|
| `test_trend_up_when_price_above_sma_and_low_vol` | Price > SMA + low vol → trend_up | `test_validation_engine.py` |
| `test_range_bound_when_price_near_sma` | Price oscillating → range_bound | `test_validation_engine.py` |
| `test_high_volatility_when_realized_vol_high` | High daily ranges → high_volatility | `test_validation_engine.py` |
| `test_risk_off_when_price_down_and_high_vol` | Price down + high vol → risk_off | `test_validation_engine.py` |
| `test_unknown_when_insufficient_candles` | < 5 candles → unknown | `test_validation_engine.py` |
| `test_high_iv_very_high_leads_to_high_volatility_regime` | IV ≥ 0.88 → high_volatility | `test_validation_engine.py` |

### N: Historical Support Acceptance

| Test | Criterion | File |
|---|---|---|
| `test_investable_plus_good_regime_plus_catalyst_yields_strong` | Investable + trend_up + catalyst → strong | `test_validation_engine.py` |
| `test_watchlist_classification_yields_moderate` | Watchlist classification → moderate | `test_validation_engine.py` |
| `test_no_trade_yields_weak` | No Trade classification → weak | `test_validation_engine.py` |
| `test_high_volatility_regime_yields_weak_even_for_investable` | high_volatility regime → weak regardless | `test_validation_engine.py` |
| `test_risk_off_regime_yields_weak` | risk_off regime → weak | `test_validation_engine.py` |
| `test_low_quality_yields_weak` | quality < 0.45 → weak | `test_validation_engine.py` |

### O: Failure Mode Acceptance

| Test | Criterion | File |
|---|---|---|
| `test_buy_stock_yields_direction` | Buy Stock → direction | `test_validation_engine.py` |
| `test_buy_call_with_high_iv_yields_iv` | Buy Call + high IV → iv | `test_validation_engine.py` |
| `test_buy_call_with_low_iv_yields_timing` | Buy Call + low IV → timing | `test_validation_engine.py` |
| `test_bull_call_spread_yields_timing` | Bull Call Spread → timing | `test_validation_engine.py` |
| `test_sell_csp_yields_direction` | Sell CSP → direction | `test_validation_engine.py` |
| `test_covered_call_yields_timing` | Covered Call → timing | `test_validation_engine.py` |
| `test_liquidity_problem_yields_liquidity_first` | illiquid → liquidity (always) | `test_validation_engine.py` |

### P: Validation Confidence Acceptance

| Test | Criterion | File |
|---|---|---|
| `test_confidence_in_valid_range` | Confidence stays within [0.3, 0.95] | `test_validation_engine.py` |
| `test_strong_thesis_investable_in_trend_up_gives_high_confidence` | Strong setup → confidence > 0.70 | `test_validation_engine.py` |
| `test_risk_off_high_iv_gives_lower_confidence` | risk_off + high IV → lower confidence | `test_validation_engine.py` |
| `test_illiquid_reduces_confidence` | illiquid < liquid confidence | `test_validation_engine.py` |

### Q: App Integration Acceptance

| Test | Criterion | File |
|---|---|---|
| `test_app_result_includes_validation_field` | TickerResearchResult has `validation` field | `test_validation_engine.py` |
| `test_validation_engine_is_instantiated_in_app` | HermesResearchApp creates ValidationEngine | `test_validation_engine.py` |
| `test_viewer_snapshot_includes_validation_results` | build_viewer_snapshot returns validation_results key | `test_validation_engine.py` |

## Running the Phase 17 Acceptance Suite

```bash
pytest tests/agent/research_v1/test_validation_engine.py tests/agent/research_v1/test_bullish_decision_integration.py tests/agent/research_v1/test_watchlist_alerts.py tests/agent/research_v1/test_database.py tests/agent/research_v1/test_report_pdf.py -v
```

Expected: **112 passed** (36 validation + 36 bullish + 22 watchlist + 18 database/pdf) + pre-existing Windows temp file lock failures (unrelated to Phase 17).

Phase 17 wiring is verified by `test_validation_engine.py` (app integration + viewer surface) and by the bullish integration tests confirming no regression in Phase 14–16 behavior.
