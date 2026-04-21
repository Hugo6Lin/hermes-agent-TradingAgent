# AGENT.md — Hermes Repository Guide

> This file is for autonomous agents and models working in the Hermes repository.
> It defines responsibilities, boundaries, and change-propagation rules.
> Human developers: see README.md for product overview.

## System Identity

**Hermes** is a boss-specific trading-decision system. It runs a canonical research pipeline
that produces `CanonicalSignal` + `CanonicalReport` + `TradePlan` + optional `CanonicalReview`
for one or more tickers, persists them to SQLite, and exposes them via a web viewer and PDF export.

**Primary branch**: `main` — all Phase 11+ work is on `main`. Do not open PRs to other branches.

---

## Directory Map

```
agent/                    # Python package root
  research_v1/            # ★ PRIMARY — canonical pipeline lives here
    app.py                # HermesResearchApp (canonical pipeline host)
    task_router.py        # natural language → ResearchTask
    orchestrator.py       # ResearchTask → SubagentTask[] / EvidenceBundle
    subagent_executor.py  # SubagentTask[] → EvidenceItem[] (via analysts)
    evidence_store.py     # normalize raw analyst output → EvidenceItem[]
    final_judge.py        # EvidenceBundle → CanonicalSignal + CanonicalReport
    reviewer.py           # CanonicalReview (optional quality gate)
    market_data_service.py # Futu-first market data (snapshot / candles / options)
    contracts.py          # All canonical dataclasses (ResearchTask, SubagentTask, EvidenceItem, CanonicalSignal, CanonicalReport, etc.)
    signal_pipeline.py    # SignalPersistencePipeline
    trade_plan.py         # TradePlanGenerator
    viewer.py             # Web viewer (legacy / canonical / batch modes)
    report_pdf.py         # Canonical PDF export
    report_pdf_legacy.py # Batch PDF export
    batch_cli.py          # batch init/status/viewer/export subcommands
    data/
      database.py         # ResearchDatabase (SQLite persistence)
      providers.py        # MarketDataProvider ABC + Futu/Yahoo/AkShare/Fallback implementations
      futu_opend.py      # FutuQuoteClient wrapper
      quality.py          # DataQualityValidator
    analysts/
      technical.py        # Technical analyst (EMA/SMA/RSI/MACD)
      fundamentals.py      # Fundamental analyst (revenue/earnings/debt)
      news.py             # News analyst
      sentiment.py        # Sentiment analyst
      industry.py         # Industry analyst
      options.py          # Options analyst (put/call ratio, OI)
      risk.py             # Risk analyst
      valuation.py        # Valuation analyst (DCF/DDM/relative)
    researchers/
      bull_researcher.py  # Bull-case researcher (legacy Phase 1-4)
      bear_researcher.py  # Bear-case researcher (legacy Phase 1-4)

tests/
  agent/
    research_v1/
      test_market_data_service.py   # Phase 12 Futu-first market data tests
      test_phase13_acceptance.py    # Phase 13 product acceptance tests
      test_app_integration.py        # App integration tests
      test_p6_viewer.py            # Viewer tests
      test_futu_provider.py         # Futu provider tests

docs/
  system-overview.md    # System capabilities (Chinese)
  boss-manual.md       # Boss user manual (Chinese)
  system-architecture.md  # Canonical pipeline architecture diagram
  product-acceptance.md   # Phase 13 acceptance criteria
  developer-workflow.md   # This repository's development conventions
```

---

## Legacy Boundaries

**Legacy code** = Phase 1-10 work that pre-dates the canonical pipeline.

| Legacy File | Canonical Replacement | Notes |
|---|---|---|
| `signal_pipeline_legacy.py` | `signal_pipeline.py` | Canonical uses `CanonicalSignal` dataclass |
| `reviewer_legacy.py` | `reviewer.py` | Uses `CanonicalReview` dataclass |
| `trade_plan_legacy.py` | `trade_plan.py` | Uses `TradePlan` dataclass |
| `grading.py` | `final_judge.py` | Phase 11 canonical judge |
| `researchers/` | `subagent_executor.py + analysts/` | Phase 11+ uses analyst agents |

**Rule**: legacy code is frozen — do not add features to it. Add features to canonical files only.
If you need to fix a bug in legacy code, migrate to canonical instead.

---

## Main Path vs. Secondary Path

The **main path** is the canonical pipeline:

```
HermesResearchApp.run(request)
  → TaskRouter.route()
  → Orchestrator.decompose()
  → MarketDataService.fetch_context_for_ticker()  [Futu-first]
  → SubagentExecutor.execute()
  → EvidenceStore.normalize()
  → FinalJudge.judge()
  → SignalPersistencePipeline.persist()
  → TradePlanGenerator.generate()
  → Reviewer.review()  [optional]
```

**Secondary paths** (call canonical components directly):
- `batch_cli.py viewer` → `serve_viewer()` → reads from SQLite
- `report_pdf.py export_task_pdf()` → reads canonical signals/reports from DB
- `python -m agent.research_v1.app` CLI → `HermesResearchApp.run()`

---

## Change-Propagation Rules

When you modify a module, you MUST check and possibly update these other files:

### `app.py`
> **What it does**: Hosts the canonical pipeline, wires all components.
> **Affected by**: Any change to pipeline order, new pipeline stages, new result fields.
> **Check after changing**:
- `test_app_integration.py`
- `test_phase13_acceptance.py`
- `viewer.py` (if new result fields need display)
- `report_pdf.py` (if new fields need PDF rendering)

### `contracts.py`
> **What it does**: All canonical dataclasses. Changing a dataclass field breaks every consumer.
> **Check after changing**:
- All `data/database.py` INSERT/SELECT statements
- `final_judge.py`
- `signal_pipeline.py`
- `viewer.py` HTML rendering
- All test files that construct these dataclasses

### `market_data_service.py`
> **What it does**: Futu-first market data aggregation for subagent context.
> **Check after changing**:
- `test_market_data_service.py`
- `subagent_executor.py` (uses `_fetch_via_service`)
- `app.py` (passes market data into required_context)

### `data/providers.py`
> **What it does**: `MarketDataProvider` ABC + implementations (Futu / Yahoo / AkShare / Fallback).
> **Adding a new provider method**: Add to ABC first, then implement in all providers.
> **Check after changing**:
- `test_market_data_service.py`
- `test_futu_provider.py`
- `test_p3_signal_quality.py`

### `data/database.py`
> **What it does**: All SQLite persistence. Schema changes require migration strategy.
> **Check after changing**:
- Any test that uses a database
- `signal_pipeline.py`
- `batch_cli.py`
- `viewer.py`

### `subagent_executor.py`
> **What it does**: Routes SubagentTask to correct analyst based on AgentRole.
> **Check after changing**:
- `test_market_data_service.py`
- `test_app_integration.py`
- Individual analyst files (`analysts/*.py`)

### `final_judge.py`
> **What it does**: Produces CanonicalSignal + CanonicalReport from EvidenceBundle.
> **Check after changing**:
- `test_app_integration.py`
- `test_phase13_acceptance.py`
- `contracts.py` (signal/report field changes)

### `viewer.py` / `report_pdf.py`
> **What they do**: Consume canonical outputs from DB for display/export.
> **Check after changing**:
- `test_p6_viewer.py`
- `test_phase13_acceptance.py` (PDF tests)
- `batch_cli.py` (if viewer routes change)

### `batch_cli.py`
> **What it does**: batch init/status/viewer/export commands + HTTP viewer server.
> **Check after changing**:
- `test_batch_cli.py`
- `test_phase13_acceptance.py`

---

## What NOT to Do

1. **Do not** add new columns to canonical tables without a schema migration strategy.
2. **Do not** modify legacy files with new features — migrate to canonical instead.
3. **Do not** remove fields from canonical dataclasses without checking all consumers.
4. **Do not** bypass the canonical pipeline when adding new features — extend it.
5. **Do not** add new dependencies without updating `requirements.txt` and `README.md`.
6. **Do not** write business logic that raises raw `PermissionError` — wrap in descriptive strings.
7. **Do not** hardcode tickers or date ranges — all data must be parametric.

---

## Key Interfaces

### Canonical dataclasses (`contracts.py`)
```python
ResearchTask(request_text, tickers, task_type, output_mode, ...)
SubagentTask(task_id, agent_role, ticker, objective, required_context, ...)
EvidenceItem(ticker, agent_role, evidence_type, content, confidence, ...)
CanonicalSignal(ticker, rating, confidence, priority_score, entry_price,
               stop_loss, take_profit, holding_horizon, decision_reason, ...)
CanonicalReport(title, executive_summary, bottom_line, why_now,
                bull_case, bear_case, trade_plan, risk_watch, ...)
CanonicalReview(verdict, quality_score, flags, notes, ...)
EvidenceBundle(task_id, ticker, evidence_items, coverage_summary, ...)
```

### MarketDataProvider ABC (`data/providers.py`)
```python
class MarketDataProvider(ABC):
    def fetch_history(self, symbol, start_date, end_date) -> list[dict]: ...
    def fetch_snapshot(self, symbols) -> list[dict]: ...
    def fetch_option_chain(self, symbol, start, end) -> list[dict]: ...

class FallbackMarketDataProvider:
    def get_last_fallback_reasons(self) -> list[str]: ...
```

### MarketDataService (`market_data_service.py`)
```python
MarketDataService(provider=...)  # defaults to Futu-first
ctx = service.fetch_context_for_ticker(ticker)
# ctx = {market_data, candles, option_chain, _fallback_reasons}
```

---

## Test Runbook

```bash
# Canonical pipeline + market data tests
pytest tests/agent/research_v1/test_market_data_service.py -v

# Phase 13 acceptance (full product loop)
pytest tests/agent/research_v1/test_phase13_acceptance.py -v

# App integration
pytest tests/agent/research_v1/test_app_integration.py -v

# All research_v1 tests (fast)
pytest tests/agent/research_v1/ -v --ignore=tests/agent/research_v1/fixtures

# Full suite
pytest tests/agent/research_v1/ -v
```

**Known pre-existing failures** (do not fix as part of normal development):
- `test_p6_viewer.py::test_build_viewer_snapshot_collects_signals_positions_and_paper_trades` — Windows temp cleanup PermissionError (WinError 32)
- `test_p6_viewer.py::test_build_viewer_snapshot_tolerates_missing_watchlist_tables` — same Windows issue

---

## Doc-Sync Rule

> When you modify code in a directory that has a `README.md`, you MUST check whether the
> README needs updating. If it does, update it in the same commit.
>
> See `CONTRIBUTING.md` for the lightweight pre-commit check that enforces this.

---

## Adding New Analyst Roles

To add a new analyst role (e.g., `macro`):

1. Add `AgentRole.MACRO` to `contracts.py`
2. Create `analysts/macro.py` with `def research_macro(ticker, context) -> EvidenceItem`
3. Add case to `subagent_executor.py::_run_role_handler()`
4. Add mock LLM response in `_MockLLMClient` in tests that use it
5. Add test in `test_app_integration.py`
6. Update `agent/research_v1/README.md` (analysts section)
7. Update `AGENT.md` (main path / change propagation)
