# AGENT.md — agent/research_v1/data/

## Responsibilities

Manages all market data provider implementations and SQLite persistence.

## Boundaries

**Do NOT:**
- Add SQL queries directly in business logic — put them in `database.py`
- Change `MarketDataProvider` ABC method signatures without updating all implementations
- Use raw `sqlite3.connect()` instead of `ResearchDatabase._get_connection()`

**Do:**
- Add new provider implementations under `providers.py`
- Extend `FallbackMarketDataProvider` for new fallback strategies
- Add new database tables in `database.py` with proper schema

## Adding a New Market Data Provider

1. Add the method signatures to `MarketDataProvider` ABC in `providers.py`
2. Implement in all existing providers (Futu / Yahoo / AkShare)
3. Add `NotImplementedError` stub to providers that don't support it yet
4. Add to `FallbackMarketDataProvider.providers` list
5. Add tests in `test_market_data_service.py`

## Key Interfaces

### ResearchDatabase (database.py)
```python
class ResearchDatabase:
    def save_research_task(task) -> str
    def save_canonical_signal(signal, task_id) -> str
    def save_canonical_report(report, task_id, ticker) -> str
    def list_canonical_signals(limit) -> list[dict]
    def list_canonical_reports(limit) -> list[dict]
    def save_research_batch_payload(payload) -> dict
    def list_research_batch_items(batch_id) -> list[dict]
    def get_research_batch(batch_id) -> dict
```

### MarketDataProvider ABC (providers.py)
```python
class MarketDataProvider(ABC):
    def fetch_history(symbol, start_date, end_date) -> list[dict]: ...
    def fetch_snapshot(symbols) -> list[dict]: ...
    def fetch_option_chain(symbol, start, end) -> list[dict]: ...

class FallbackMarketDataProvider(MarketDataProvider):
    def get_last_fallback_reasons() -> list[str]: ...
```

## Database Schema Notes

- `canonical_signals` and `canonical_reports` are the **canonical** output tables (Phase 11+)
- `research_signals` / `research_decisions` are **legacy** tables (Phase 1-10)
- Both sets co-exist without interfering
- `research_batches` / `research_batch_items` / `company_reports` are for batch-mode viewing

## Change Propagation

| If you change | Check |
|---|---|
| `providers.py` (MarketDataProvider ABC) | All provider implementations + `test_market_data_service.py` |
| `database.py` (schema) | `signal_pipeline.py`, `batch_cli.py`, all DB-using tests |
| `futu_opend.py` | `test_futu_provider.py` |

## Upstream / Downstream

- **Upstream**: `futu`, `yfinance`, `akshare` packages; Python `sqlite3`
- **Downstream**: `subagent_executor.py`, `app.py`, `batch_cli.py`, `viewer.py`
