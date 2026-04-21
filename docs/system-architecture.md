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

## Bullish Decision System (Phase 14)

The bullish decision system is an **additive layer** on top of the canonical pipeline.
It does not replace or modify canonical signal/report outputs.

```
Phase 14: After FinalJudge (step 7) — additive, non-destructive

  ThesisEngine.evaluate(fundamentals, valuation, catalysts)
    → UnderlyingThesis {classification: Investable | Watchlist | No Trade}

  InstrumentSelectionEngine.choose(thesis, option_context, holding_context)
    → InstrumentRecommendation {primary_action, ranked_alternatives, reason}

  PositionDecisionCard(task_id, ticker, primary_action, conviction, thesis_summary, why_now, alternatives)
    → Boss-facing decision artifact
```

## Watchlist & Alert Center (Phase 16)

Phase 16 adds boss-centric monitored watchlists with business-day cadence checks and thesis-state-aware alert levels. All actions are **advisory only** — no auto-execution.

### WatchlistEntry Contract

Every ticker processed by the pipeline may produce a `WatchlistEntry`:

| Field | Type | Description |
|---|---|---|
| `ticker` | `str` | Ticker symbol |
| `status` | `WatchlistStatus` | Held / High Priority Watch / Research In Progress / Passive Watch |
| `thesis_state` | `ThesisState` | Strengthening / Stable / Weakening / Broken |
| `alert_level` | `AlertLevel` | Critical / High / Medium / Low / None |
| `current_action_bias` | `str` | Instrument action (e.g. "Sell Cash-Secured Put") |

Status is derived from `instrument_rec.primary_action`: "No Trade" or "Watchlist" → Passive Watch; everything else → Held.

### WatchlistAlert Contract

Alerts are **advisory only**:

| Field | Type | Description |
|---|---|---|
| `ticker` | `str` | Ticker symbol |
| `alert_level` | `AlertLevel` | Critical / High / Medium / Low |
| `message` | `str` | Human-readable advisory message |

### Cadence Rules

| Status | Cadence |
|---|---|
| Held / High Priority Watch / Research In Progress | Every business day |
| Passive Watch | Weekly |

### Alert Level Mapping (thesis_state → alert_level)

| Thesis State | Alert Level |
|---|---|
| `Broken` | Critical |
| `Weakening` | High |
| `Strengthening` | Medium |
| `Stable` | None |

### Data Storage

`ResearchDatabase` persists watchlist entries in the `watchlist_entries` table. Viewer snapshots and PDF exports include the current watchlist.

### Allowed Instrument Actions

| Action | When preferred |
|---|---|
| `Buy Stock` | Strong thesis, high IV, long/uncertain time window |
| `Buy Call` | Strong thesis, acceptable IV, clear timing |
| `Bull Call Spread` | Positive but bounded upside, expensive long calls |
| `Sell Cash-Secured Put` | Investable, willing to own lower, elevated IV |
| `Covered Call` | Stock held, long thesis intact, limited short-term upside |
| `Watchlist / No Trade` | Underlying not investable |

### Key Constraints (Phase 14)

- **Stock thesis first**: derivative recommendations require positive underlying thesis
- **Bullish-only**: `Short Stock`, `Buy Put`, `Long Put` are not valid primary actions
- **Alert-only**: no auto-trading, no auto-close, no broker-side execution
- **Additive**: canonical signal/report outputs are unchanged; Phase 14 adds `thesis`, `instrument_recommendation`, `decision_card` fields

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
| ThesisEngine | `thesis_engine.py` | Underlying thesis evaluation (Phase 14) |
| InstrumentSelectionEngine | `instrument_selection.py` | Bullish instrument selection (Phase 14) |
| WatchlistAlertCenter | `watchlist_alerts.py` | Watchlist entry registration, cadence, and alert generation (Phase 16) |
| ValidationEngine | `validation_engine.py` | Historical support, environment fit, failure mode, and confidence annotation (Phase 17) |

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

## Phase 11/12/13/14/16/17 Changes

- **Phase 11**: Canonical pipeline established (TaskRouter → Orchestrator → FinalJudge → CanonicalSignal/Report)
- **Phase 12**: Futu-first market data (`MarketDataService`, `MarketDataProvider` ABC, `FallbackMarketDataProvider`)
- **Phase 13**: Product acceptance (viewer, PDF, batch CLI, data stability)
- **Phase 14**: Bullish decision system (`ThesisEngine`, `InstrumentSelectionEngine`, `PositionDecisionCard`) — additive layer, bullish-only instrument selection, stock thesis first
- **Phase 16**: Watchlist & Alert Center (`WatchlistEntry`, `WatchlistAlert`, `WatchlistAlertCenter`) — boss-centric monitored watchlists with business-day cadence, thesis-state-aware alert levels, alert-only (no auto-execution)
- **Phase 17**: Validation Engine (`ValidationResult`, `ValidationEngine`) — lightweight annotation layer providing historical support, environment fit, failure mode, and confidence without overriding thesis or instrument decisions

## Validation Engine (Phase 17)

Phase 17 adds a **lightweight validation annotation layer** — purely advisory, never overrides decisions.

### ValidationResult Contract

| Field | Type | Description |
|---|---|---|
| `ticker` | `str` | Ticker symbol |
| `regime` | `str` | trend_up / range_bound / high_volatility / risk_off / unknown |
| `historical_support` | `str` | strong / moderate / weak |
| `environment_fit` | `str` | good / mixed / poor |
| `main_failure_mode` | `str` | direction / timing / iv / liquidity / none |
| `validation_confidence` | `float` | 0.0–1.0 |
| `notes` | `str \| None` | Human-readable summary |

### Regime Detection

Rule-based detection from candle data and market context:
- **trend_up**: price > 3% above SMA, low realized vol
- **range_bound**: price near SMA, moderate vol
- **high_volatility**: elevated realized vol OR IV percentile ≥ 0.88
- **risk_off**: high vol + price below SMA
- **unknown**: insufficient candle data

### Historical Support

Rule-based (no backtesting): strong when Investable thesis + good regime + clear catalyst + supportive valuation; weak when No Trade, high_vol/risk_off regime, or very high IV.

### Failure Mode Inference

- `Buy Stock` → direction | `Buy Call` (high IV) → iv | `Buy Call` (low IV) → timing
- `Bull Call Spread` → timing | `Sell CSP` → direction | `Covered Call` → timing
- Liquidity problems → liquidity (always, when present)

### Key Constraints (Phase 17)

- **Not a new authority**: validation is annotation only, does not override `decision_card` or `instrument_recommendation`
- **Additive**: no changes to canonical signal, report, or Phase 14–16 outputs
- **Bullish-only**: no bearish instruments introduced

## Legacy vs. Canonical

| Aspect | Legacy (Phase 1-10) | Canonical (Phase 11+) |
|---|---|---|
| Signal class | `signal_pipeline_legacy` | `CanonicalSignal` |
| Report class | ad-hoc dicts | `CanonicalReport` |
| Research flow | `grading.py` | `final_judge.py` |
| Market data | `yahoo_finance.py` direct | `MarketDataService` (Futu-first) |
| Analyst execution | `researchers/` | `subagent_executor.py + analysts/` |
| Instrument selection | N/A | Phase 14: bullish-only (`InstrumentSelectionEngine`) |
| Watchlist & alerts | N/A | Phase 16: boss-centric monitored watchlists (`WatchlistAlertCenter`) |

Legacy and canonical co-exist. Viewer and PDF prefer canonical; legacy is kept for backwards compatibility.
