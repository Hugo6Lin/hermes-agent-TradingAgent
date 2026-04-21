# agent/research_v1/data/ — Data Providers and Persistence

## What This Directory Is

Contains all data-layer code: market data provider implementations and SQLite persistence.

## Core Files

| File | Purpose |
|---|---|
| `database.py` | `ResearchDatabase` — all SQLite tables and CRUD operations |
| `providers.py` | `MarketDataProvider` ABC + `FutuMarketDataProvider` / `YahooMarketDataProvider` / `AkShareMarketDataProvider` / `FallbackMarketDataProvider` |
| `futu_opend.py` | `FutuOpenDConfig` + `FutuQuoteClient` — Futu OpenD gateway wrapper |
| `quality.py` | `DataQualityValidator` — field validation and staleness checking |
| `yahoo_finance.py` | Yahoo Finance provider (legacy, Phase 1-10) |

## Data Flow

```
MarketDataService.fetch_context_for_ticker()
  ├─ FutuMarketDataProvider
  │    └─ FutuQuoteClient → Futu OpenD (TCP)
  ├─ YahooMarketDataProvider  (fallback if Futu unavailable)
  ├─ AkShareMarketDataProvider (fallback if Yahoo unavailable)
  └─ FallbackMarketDataProvider (chains providers, tracks fallback reasons)

ResearchDatabase (SQLite)
  ├─ research_tasks
  ├─ canonical_signals
  ├─ canonical_reports
  ├─ research_batches
  ├─ research_batch_items
  └─ company_reports
```

## MarketDataProvider ABC

```python
class MarketDataProvider(ABC):
    def fetch_history(self, symbol, start_date, end_date) -> list[dict]: ...
    def fetch_snapshot(self, symbols) -> list[dict]: ...   # Phase 12
    def fetch_option_chain(self, symbol, start, end) -> list[dict]: ...  # Phase 12
```

## If You Modify Code Here

- `providers.py` → check `test_market_data_service.py`, `test_futu_provider.py`, `test_p3_signal_quality.py`
- `database.py` → check all tests using DB, `signal_pipeline.py`, `batch_cli.py`
- `futu_opend.py` → check `test_futu_provider.py`

## Relationship to Other Directories

- `agent/research_v1/market_data_service.py` — uses providers
- `agent/research_v1/subagent_executor.py` — uses MarketDataService
- `tests/agent/research_v1/test_market_data_service.py` — provider tests
- `tests/agent/research_v1/test_futu_provider.py` — Futu-specific tests

## Related Files

- `agent/research_v1/market_data_service.py` — uses providers
- `agent/research_v1/subagent_executor.py` — uses MarketDataService
- `tests/agent/research_v1/test_market_data_service.py` — provider tests
- `tests/agent/research_v1/test_futu_provider.py` — Futu-specific tests
