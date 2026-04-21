# agent/research_v1/ — Canonical Research Pipeline

## What This Directory Is

The primary implementation directory for Hermes. It contains the full canonical research
pipeline from natural language request to canonical signal, report, review, and trade plan.

## Core Files

### Pipeline Host
- **`app.py`** — `HermesResearchApp` — wires the entire canonical pipeline.
  Entry point: `app.run("Research AAPL")` → `ResearchResult`

### Pipeline Components
- **`task_router.py`** — parses natural language → `ResearchTask` (extracts tickers, intent)
- **`orchestrator.py`** — decomposes `ResearchTask` → `SubagentTask[]`, assembles `EvidenceBundle`
- **`subagent_executor.py`** — executes `SubagentTask[]` via analyst agents, uses `MarketDataService`
- **`evidence_store.py`** — normalizes analyst outputs → `EvidenceItem[]`
- **`final_judge.py`** — `judge()` → `CanonicalSignal` + `CanonicalReport` from `EvidenceBundle`
- **`reviewer.py`** — optional `CanonicalReview` quality gate
- **`signal_pipeline.py`** — `SignalPersistencePipeline` for DB persistence

### Market Data (Phase 12)
- **`market_data_service.py`** — `MarketDataService` fetches Futu-first market context
- **`data/providers.py`** — `MarketDataProvider` ABC + `FutuMarketDataProvider` / `YahooMarketDataProvider` / `FallbackMarketDataProvider`
- **`data/futu_opend.py`** — `FutuOpenDConfig` + `FutuQuoteClient` wrapper

### Output/Viewing
- **`trade_plan.py`** — `TradePlanGenerator` → `TradePlan` from `CanonicalSignal`
- **`viewer.py`** — web viewer: `/` (dashboard) / `/batches/latest` / `/ticker/<item_id>`
- **`report_pdf.py`** — canonical task PDF export via Microsoft Edge headless
- **`report_pdf_legacy.py`** — batch PDF export

### CLI / Batch
- **`batch_cli.py`** — `batch_cli` commands: `init` / `status` / `viewer` / `export-pdf`
- **`research_batch_service.py`** — `save_batch_research()` for structured batch payloads

### Data & Contracts
- **`contracts.py`** — ALL canonical dataclasses: `ResearchTask`, `SubagentTask`, `EvidenceItem`,
  `CanonicalSignal`, `CanonicalReport`, `CanonicalReview`, `EvidenceBundle`
- **`data/database.py`** — `ResearchDatabase` with all SQLite tables
- **`data/quality.py`** — `DataQualityValidator` for price history validation

### Analysts
- **`analysts/technical.py`** — EMA/SMA/RSI/MACD signals from candles
- **`analysts/fundamentals.py`** — revenue/earnings/debt equity analysis
- **`analysts/news.py`** — news sentiment scoring
- **`analysts/sentiment.py`** — social sentiment analysis
- **`analysts/industry.py`** — industry trend analysis
- **`analysts/options.py`** — put/call ratio, open interest analysis
- **`analysts/risk.py`** — risk rating and exposure analysis
- **`analysts/valuation.py`** — DCF/DDM/relative valuation

### Legacy (Frozen)
- **`researchers/bull_researcher.py`** — Phase 1-4 bull case researcher
- **`researchers/bear_researcher.py`** — Phase 1-4 bear case researcher
- **`grading.py`** — Phase 1-10 grading (replaced by `final_judge.py`)
- **`signal_pipeline_legacy.py`** — legacy signal persistence
- **`reviewer_legacy.py`** — legacy reviewer
- **`trade_plan_legacy.py`** — legacy trade plan

## Data Flow

```
HermesResearchApp.run(request)
  ├─ TaskRouter.route() → ResearchTask
  ├─ Orchestrator.decompose() → SubagentTask[]
  │    └─ Each SubagentTask: {agent_role, ticker, objective, required_context}
  ├─ MarketDataService.fetch_context_for_ticker() [Futu-first, per ticker]
  │    └─ market_data + candles + option_chain + _fallback_reasons
  ├─ SubagentExecutor.execute(subtask)
  │    ├─ injects market data into required_context
  │    └─ calls LLM with analyst prompt → raw JSON
  ├─ EvidenceStore.normalize() → EvidenceItem[]
  ├─ Orchestrator.assemble_bundle() → EvidenceBundle
  ├─ Orchestrator.assemble_judge_packet() → JudgeInputPacket
  ├─ FinalJudge.judge() → CanonicalSignal + CanonicalReport
  ├─ SignalPersistencePipeline.persist_canonical_signal() + .persist_canonical_report()
  ├─ TradePlanGenerator.generate() → trade_plan dict
  ├─ Reviewer.review() [optional] → CanonicalReview
  └─ _run_ticker_pipeline() → TickerResearchResult {signal, report, review, trade_plan, audit}
```

## How It Relates to Other Directories

- **`tests/agent/research_v1/`** — mirrors this directory for testing
- **`docs/`** — system docs reference this directory's modules
- **`agent/research_v1/data/`** — data providers and SQLite persistence
- **`agent/research_v1/analysts/`** — called by `subagent_executor.py`

## If You Modify Code Here

- `app.py` → check `test_app_integration.py`, `test_phase13_acceptance.py`
- `contracts.py` → check ALL files that use canonical dataclasses
- `market_data_service.py` → check `test_market_data_service.py`
- `subagent_executor.py` → check analyst files and `test_market_data_service.py`
- `final_judge.py` → check `test_app_integration.py`
- `data/database.py` → check all DB-using tests
- `viewer.py` / `report_pdf.py` → check `test_p6_viewer.py`, `test_phase13_acceptance.py`
- `batch_cli.py` → check `test_batch_cli.py`

## Entry Points

```bash
# Primary: canonical research
python -m agent.research_v1.app "Research AAPL"

# Batch viewer server
python -m agent.research_v1.batch_cli --app-root .hermes viewer --host 127.0.0.1 --port 8008

# Batch PDF export
python -m agent.research_v1.batch_cli --app-root .hermes export-pdf --batch-id 1

# Standalone viewer
python -m agent.research_v1.viewer
```
