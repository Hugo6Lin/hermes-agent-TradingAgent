# AGENT.md — tests/agent/research_v1/

## Responsibilities

Unit, integration, and acceptance tests for the canonical research pipeline.

## Boundaries

**Do NOT:**
- Write tests that hit real LLM APIs — always mock
- Write tests that require a live Futu OpenD connection — mock it
- Add long-running integration tests to the fast test suite
- Write tests that assume specific tickers or dates

**Do:**
- Use `tempfile.TemporaryDirectory()` for all DB paths
- Use `_FakeQuoteContext` / `_FakeProvider` patterns for market data mocking
- Add a test for every new feature in the same PR
- Add a regression test for every bug fix

## Test Categories

| Category | Files | Run time |
|---|---|---|
| Unit tests | `test_market_data_service.py`, `test_database.py`, `test_task_router.py` | Fast (<5s) |
| Integration tests | `test_app_integration.py`, `test_futu_provider.py` | Medium (<15s) |
| Acceptance tests | `test_phase13_acceptance.py` | Medium (<10s) |
| Viewer tests | `test_p6_viewer.py` | Fast |

## Mock Patterns

### Market Data Provider Mock
```python
class _FakeMarketDataProvider(MarketDataProvider):
    def fetch_history(self, symbol, start_date, end_date):
        return [{"day": 0, "date": "2026-04-18", "close": 185.0}]
    def fetch_snapshot(self, symbols):
        return [{"code": "US.AAPL", "last_price": 186.5}]
    def fetch_option_chain(self, symbol, start=None, end=None):
        return []
```

### FakeQuoteContext (for Futu)
See `test_market_data_service.py` and `test_futu_provider.py` for `_FakeQuoteContext` pattern.

## Important Test Invariants

- Tests must be independent — no test depends on another test's DB state
- Use a fresh `ResearchDatabase` per test with `tempfile.TemporaryDirectory()`
- Always call `db.initialize()` and `db.initialize_research_core()` before using DB

## Change Propagation

| If you modify in `agent/research_v1/` | Add/update test in |
|---|---|
| `market_data_service.py` | `test_market_data_service.py` |
| `app.py` | `test_app_integration.py`, `test_phase13_acceptance.py` |
| `data/providers.py` | `test_market_data_service.py`, `test_futu_provider.py` |
| `viewer.py` | `test_p6_viewer.py` |
| `batch_cli.py` | `test_batch_cli.py` |
| `contracts.py` | All tests that construct dataclasses |

## What NOT to Do

- Do NOT write tests that require a live Futu OpenD connection — mock it
- Do NOT write tests that hit real LLM APIs — always mock with `_MockLLMClient`
- Do NOT add tests to the slow suite unless they are truly integration tests
- Do NOT hardcode tickers or dates in tests

## Key Interfaces

- `pytest` — test runner
- `_MockLLMClient` — mock LLM client for app integration tests
- `_FakeMarketDataProvider` — mock provider for market data tests
- `_FakeQuoteContext` — mock Futu quote context for provider tests

## Upstream / Downstream

- **Upstream**: `agent/research_v1/` — all code under test lives here
- **Downstream**: None — tests are leaf nodes
