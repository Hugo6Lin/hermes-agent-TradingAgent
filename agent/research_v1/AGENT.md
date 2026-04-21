# AGENT.md — agent/research_v1/

## Responsibilities

This directory owns the canonical research pipeline. Every piece of business logic for
Hermes research lives here. The pipeline runs:

```
TaskRouter → Orchestrator → SubagentExecutor → EvidenceStore → FinalJudge → TradePlan → Reviewer
```

## Boundaries

**Do NOT:**
- Add new features to legacy files (`researchers/`, `grading.py`, `*_legacy.py`)
- Bypass the canonical pipeline for new features — extend it instead
- Add fields to canonical dataclasses in `contracts.py` without checking all consumers
- Change `MarketDataProvider` ABC methods without updating all provider implementations
- Modify database schema without a migration strategy

**Do:**
- Add new modules to `analysts/` for new analyst roles
- Add new `AgentRole` enum values in `contracts.py`
- Extend `FallbackMarketDataProvider` with new fallback strategies
- Add new viewer routes in `viewer.py` and corresponding tests in `test_p6_viewer.py`
- Add Phase 14 decision engines as new modules (not in existing canonical files)

## Key Interfaces

### HermesResearchApp (app.py)
```python
class HermesResearchApp:
    def __init__(self, llm_client=None, database=None, market_data_service=None)
    def run(self, request: str) -> ResearchResult
    def execute_subagent(self, subtask) -> list[EvidenceItem]
```

### SubagentExecutor (subagent_executor.py)
```python
class SubagentExecutor:
    def __init__(self, llm_client, market_data_service=None)
    def execute(self, subtask: SubagentTask) -> dict  # returns raw_output dict
```

### MarketDataService (market_data_service.py)
```python
class MarketDataService:
    def fetch_context_for_ticker(self, ticker) -> dict
    # Returns: {market_data, candles, option_chain, _fallback_reasons}
```

### FallbackMarketDataProvider (data/providers.py)
```python
class FallbackMarketDataProvider:
    def get_last_fallback_reasons(self) -> list[str]
```

## Upstream/Downstream

**Upstream dependencies** (modules that this directory depends on):
- `futu`, `yfinance`, `akshare` — market data providers
- `sqlite3` — persistence (stdlib)
- LLM API clients (configured via environment)

**Downstream consumers** (modules that depend on this directory):
- `tests/agent/research_v1/` — all tests
- `docs/` — documentation references pipeline components
- Viewer/PDF/batch_cli all read from this directory's DB outputs

## Change Propagation

| If you change | You MUST also check |
|---|---|
| `contracts.py` | All consumers — dataclass fields are used everywhere |
| `app.py` | `test_app_integration.py`, `test_phase13_acceptance.py`, `test_bullish_decision_integration.py` |
| `subagent_executor.py` | `test_market_data_service.py`, analyst files |
| `market_data_service.py` | `test_market_data_service.py`, `subagent_executor.py` |
| `data/providers.py` | `test_market_data_service.py`, `test_futu_provider.py` |
| `data/database.py` | All tests using DB, `signal_pipeline.py` |
| `final_judge.py` | `test_app_integration.py` |
| `viewer.py` | `test_p6_viewer.py`, `test_phase13_acceptance.py` |
| `report_pdf.py` | `test_phase13_acceptance.py` |
| `batch_cli.py` | `test_batch_cli.py`, `test_phase13_acceptance.py` |
| `thesis_engine.py` | `test_thesis_engine.py`, `test_bullish_decision_integration.py` |
| `instrument_selection.py` | `test_instrument_selection.py`, `test_bullish_decision_integration.py` |

## Legacy Files (Frozen)

These files exist for backwards compatibility but no new development should happen here:

- `grading.py` — Phase 1-10 grading. Use `final_judge.py`
- `signal_pipeline_legacy.py` — legacy persistence. Use `signal_pipeline.py`
- `reviewer_legacy.py` — legacy review. Use `reviewer.py`
- `trade_plan_legacy.py` — legacy trade plan. Use `trade_plan.py`
- `researchers/` — Phase 1-4 researchers. Use `subagent_executor.py + analysts/`

## Test Entry Points

```bash
# Market data service tests (Phase 12)
pytest tests/agent/research_v1/test_market_data_service.py -v

# Phase 13 acceptance
pytest tests/agent/research_v1/test_phase13_acceptance.py -v

# All research_v1 tests
pytest tests/agent/research_v1/ -v
```
