# AGENT.md — agent/research_v1/analysts/

## Responsibilities

Each analyst agent produces an `EvidenceItem` scoped to one `AgentRole` and one ticker.
Analysts do NOT persist to DB — they only return structured evidence.

## Boundaries

**Do NOT:**
- Add database writes in analyst files
- Make network calls directly — use `MarketDataService` for market data
- Return anything other than a dict matching the expected JSON schema for that role

**Do:**
- Follow the existing analyst pattern: receive `(ticker, context, llm_client)` and return `EvidenceItem`
- Each analyst should handle missing market data gracefully (don't crash if context is empty)
- Add meaningful confidence scores based on data quality

## Key Interfaces

### Standard Analyst Signature

```python
def research_<role>(ticker: str, context: dict, llm_client) -> EvidenceItem:
    """
    Args:
        ticker: stock symbol
        context: market data from MarketDataService (may be partial/stub)
        llm_client: LLM API client for analyst reasoning

    Returns:
        EvidenceItem with evidence_type='analyst/<role>' and role=AgentRole.<ROLE>
    """
```

## Adding a New Analyst Role

1. Add `AgentRole.NEW_ROLE` to `contracts.py`
2. Create `analysts/new_role.py` with `research_new_role(ticker, context, llm_client)`
3. Add case to `subagent_executor.py::_run_role_handler()`
4. Add mock LLM response in `_MockLLMClient` (test helper)
5. Add test in `test_market_data_service.py` or `test_app_integration.py`
6. Update `agent/research_v1/README.md` (analysts table)
7. Update `AGENT.md` (this file)

## Upstream/Downstream

**Upstream**: `MarketDataService` provides `context` to analysts
**Downstream**: `EvidenceStore.normalize()` consumes `EvidenceItem` from analysts

## Change Propagation

| If you add | You MUST also |
|---|---|
| New analyst role | Add `AgentRole` to `contracts.py`, update `subagent_executor.py` |
| New `EvidenceItem` field | Update `evidence_store.py`, all analyst implementations |
| New market data need | Update `market_data_service.py` |

## Tests / Verification

Run analyst tests:
```bash
pytest tests/agent/research_v1/test_market_data_service.py -v
pytest tests/agent/research_v1/test_app_integration.py -v
```
