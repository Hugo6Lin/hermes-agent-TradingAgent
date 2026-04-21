# tests/agent/research_v1/ — Research v1 Test Suite

## What This Directory Is

Tests for the canonical research pipeline (`agent/research_v1/`). This directory contains
all unit, integration, and acceptance tests for the Hermes research engine.

## Key Test Files

| File | What It Tests |
|---|---|
| `test_market_data_service.py` | Phase 12 Futu-first market data service |
| `test_phase13_acceptance.py` | Phase 13 product acceptance (A-E scope) |
| `test_app_integration.py` | App integration with mock LLM |
| `test_p6_viewer.py` | Web viewer HTML rendering |
| `test_batch_cli.py` | Batch CLI commands |
| `test_database.py` | SQLite database operations |
| `test_futu_provider.py` | Futu OpenD provider integration |
| `test_p3_signal_quality.py` | Phase 3 signal quality and provider fallback |
| `test_task_router.py` | Task router natural language parsing |
| `test_report_pdf.py` | PDF export (legacy) |
| `fixtures/` | JSON fixtures for batch payloads |

## Test Fixtures

- `fixtures/sample_batch_payload.json` — example batch research JSON with NVDA/AMD tickers

## Relationship to Code

Tests mirror the module structure of `agent/research_v1/`:
- `test_market_data_service.py` ↔ `market_data_service.py` + `data/providers.py`
- `test_phase13_acceptance.py` ↔ entire `app.py` pipeline
- `test_app_integration.py` ↔ `app.py` + `subagent_executor.py`

## If You Modify Code Here

When you modify `agent/research_v1/` code, run the corresponding test file:
- `app.py` → `test_app_integration.py` + `test_phase13_acceptance.py`
- `market_data_service.py` → `test_market_data_service.py`
- `data/providers.py` → `test_market_data_service.py` + `test_futu_provider.py`
- `viewer.py` → `test_p6_viewer.py`
- `batch_cli.py` → `test_batch_cli.py`
- `contracts.py` → all tests that construct canonical dataclasses

## Data Flow / How It Fits

Tests in this directory mirror the source modules they test. Unit tests isolate individual
components (e.g., `test_market_data_service.py`) while integration tests
(`test_phase13_acceptance.py`) run the full end-to-end pipeline with mock LLM and
stubbed market data.

## Running Tests

```bash
# Full suite (18+ sec due to Futu initialization)
pytest tests/agent/research_v1/ -v

# Phase 12 market data tests (fast)
pytest tests/agent/research_v1/test_market_data_service.py -v

# Phase 13 acceptance tests
pytest tests/agent/research_v1/test_phase13_acceptance.py -v

# Specific test class
pytest tests/agent/research_v1/test_phase13_acceptance.py::TestStartupAcceptance -v

# App integration
pytest tests/agent/research_v1/test_app_integration.py -v
```

## Mock LLM Client Pattern

For tests that need controlled LLM responses, use the `_MockLLMClient` pattern:

```python
from agent.research_v1.llm_clients import LLMResponse

class _MockLLMClient(Mock):
    def generate(self, messages, temperature=0.7, max_tokens=4096):
        prompt_text = " ".join(m.get("content", "") for m in messages)
        if "fundamentals" in prompt_text.lower():
            json_body = '{"summary": "Strong fundamentals", ...}'
        elif "technical" in prompt_text.lower():
            json_body = '{"trend": "bullish", ...}'
        # ...
        return LLMResponse(content=f'```json\n{json_body}\n```', model="mock", ...)
```

See `test_app_integration.py` and `test_phase13_acceptance.py` for examples.

## Pre-existing Known Failures

| Test | Issue | Should Fix? |
|---|---|---|
| `test_p6_viewer.py::test_build_viewer_snapshot_collects_*` | Windows temp file locked (WinError 32) | No — OS-level sqlite cleanup issue |
| `test_p6_viewer.py::test_build_viewer_snapshot_tolerates_*` | Same Windows issue | No |
