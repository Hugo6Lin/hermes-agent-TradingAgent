# System Architecture — Hermes Canonical Pipeline

## Overview

Hermes runs a **canonical research pipeline** that transforms a natural language request
(e.g., "Research AAPL") into a structured `CanonicalSignal`, `CanonicalReport`,
`TradePlan`, and optional `CanonicalReview`, persisted to SQLite and viewable via web or PDF.

## Canonical Pipeline (Phase 11确立，Phase 12/13扩展)

```
Request: "Research AAPL" or "Compare AAPL and MSFT"
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│ 1. TaskRouter.route()                                        │
│    Input: natural language string                            │
│    Output: ResearchTask {request_text, tickers, task_type}   │
└──────────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│ 2. Orchestrator.decompose()                                  │
│    Input: ResearchTask                                       │
│    Output: SubagentTask[] (one per AgentRole × per ticker)   │
│                                                              │
│    SubagentTask = {                                          │
│      task_id, subtask_id, agent_role, ticker,               │
│      objective, required_context                             │
│    }                                                         │
└──────────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│ 3. MarketDataService.fetch_context_for_ticker() (Phase 12)  │
│    Per-ticker pre-fetch of market data (Futu-first)         │
│    Output: {market_data, candles, option_chain,             │
│             _fallback_reasons}                               │
└──────────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│ 4. SubagentExecutor.execute() per SubagentTask              │
│    Injects market context into required_context              │
│    Calls LLM with analyst-specific prompt                    │
│    Output: raw_output dict (JSON from LLM)                   │
└──────────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│ 5. EvidenceStore.normalize()                                │
│    Input: raw_output dict                                    │
│    Output: EvidenceItem[] (one per subagent)                │
│                                                              │
│    EvidenceItem = {                                         │
│      ticker, agent_role, evidence_type, content,             │
│      confidence, source, metadata                           │
│    }                                                         │
└──────────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│ 6. Orchestrator.assemble_bundle()                           │
│    Input: task_id, ticker, EvidenceItem[]                   │
│    Output: EvidenceBundle {task_id, ticker, evidence_items, │
│                            coverage_summary}                 │
└──────────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│ 7. FinalJudge.judge()                                       │
│    Input: JudgeInputPacket (task, bundle, audit)             │
│    Output: (CanonicalSignal, CanonicalReport)               │
│                                                              │
│    CanonicalSignal = {                                       │
│      ticker, rating, confidence, priority_score,            │
│      entry_price, stop_loss, take_profit,                   │
│      holding_horizon, decision_reason                       │
│    }                                                         │
│                                                              │
│    CanonicalReport = {                                       │
│      title, executive_summary, bottom_line, why_now,         │
│      bull_case, bear_case, trade_plan, risk_watch           │
│    }                                                         │
└──────────────────────────────────────────────────────────────┘
    │
    ├──────────────────┐
    ▼                  ▼
┌─────────────┐  ┌──────────────────────────┐
│ 8a. Persist │  │ 9. TradePlanGenerator    │
│ Canonical   │  │    .generate(signal)     │
│ Signal +    │  │    → trade_plan dict     │
│ Report to   │  └──────────────────────────┘
│ SQLite      │           │
└─────────────┘           ▼
                  ┌──────────────────────────┐
                  │ 10. Reviewer.review()   │
                  │    (optional quality     │
                  │    gate)                │
                  │    → CanonicalReview    │
                  └──────────────────────────┘
                           │
                           ▼
                  ┌──────────────────────────┐
                  │ TickerResearchResult:    │
                  │ {signal, report, review, │
                  │  trade_plan, audit}     │
                  └──────────────────────────┘
```

## Component Map

| Component | File | Responsibility |
|---|---|---|
| TaskRouter | `task_router.py` | Parse natural language → ResearchTask |
| Orchestrator | `orchestrator.py` | Decompose + bundle + judge packet |
| SubagentExecutor | `subagent_executor.py` | Execute analysts via LLM |
| MarketDataService | `market_data_service.py` | Futu-first market data |
| EvidenceStore | `evidence_store.py` | Normalize analyst output → EvidenceItem[] |
| FinalJudge | `final_judge.py` | EvidenceBundle → CanonicalSignal + CanonicalReport |
| SignalPersistence | `signal_pipeline.py` | Persist signal/report to SQLite |
| TradePlanGenerator | `trade_plan.py` | Signal → TradePlan |
| Reviewer | `reviewer.py` | Optional quality review |

## Data Layer

```
MarketDataService
  ├─ FutuMarketDataProvider → FutuQuoteClient → Futu OpenD (TCP)
  ├─ YahooMarketDataProvider (fallback #1)
  └─ AkShareMarketDataProvider (fallback #2)

FallbackMarketDataProvider.get_last_fallback_reasons()
  → tracks why each provider was bypassed
  → exposed in audit["fallback_reasons"]

ResearchDatabase (SQLite)
  ├─ research_tasks (FK prerequisite)
  ├─ canonical_signals (Phase 11+)
  ├─ canonical_reports (Phase 11+)
  ├─ research_batches / research_batch_items / company_reports (batch mode)
  └─ legacy tables: research_signals, research_decisions, etc.
```

## Viewer / PDF / Batch Consumers

These components consume canonical outputs from SQLite:

```
HermesResearchApp.run()
  → TickerResearchResult {signal, report, trade_plan, audit}
  → persisted to SQLite by SignalPersistencePipeline

batch_cli viewer
  → serve_viewer() HTTP server
  → reads canonical_signals + canonical_reports + research_batches from DB
  → renders HTML (viewer.py)

export_task_pdf(db, task_id)
  → reads canonical_signals + reports from DB
  → generates PDF via Microsoft Edge headless
```

## Phase 11/12/13 Changes

- **Phase 11**: Canonical pipeline established (TaskRouter → Orchestrator → FinalJudge → CanonicalSignal/Report)
- **Phase 12**: Futu-first market data (`MarketDataService`, `MarketDataProvider` ABC, `FallbackMarketDataProvider`)
- **Phase 13**: Product acceptance (viewer, PDF, batch CLI, data stability)

## Legacy vs. Canonical

| Aspect | Legacy (Phase 1-10) | Canonical (Phase 11+) |
|---|---|---|
| Signal class | `signal_pipeline_legacy` | `CanonicalSignal` |
| Report class | ad-hoc dicts | `CanonicalReport` |
| Research flow | `grading.py` | `final_judge.py` |
| Market data | `yahoo_finance.py` direct | `MarketDataService` (Futu-first) |
| Analyst execution | `researchers/` | `subagent_executor.py + analysts/` |

Legacy and canonical co-exist. Viewer and PDF prefer canonical; legacy is kept for backwards compatibility.
