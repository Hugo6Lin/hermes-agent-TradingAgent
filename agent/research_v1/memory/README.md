# agent/research_v1/memory/ — Legacy Memory/Context Storage

## What This Directory Is

Legacy Phase 1-4 memory provider module. Contains `financial_provider.py` which provides
market data context for the legacy researcher agents.

## Status: FROZEN

This directory is **frozen** — no new development. Legacy researchers used this for
context enrichment before the canonical pipeline existed.

## If You Modify Code Here

**Do NOT modify.** This directory is frozen. If you need memory/context features,
add them to the canonical pipeline under `agent/research_v1/`.

## Related Files

- `agent/research_v1/researchers/` — legacy researchers that used this module
- `agent/research_v1/market_data_service.py` — Phase 12+ canonical market data (replacement)
