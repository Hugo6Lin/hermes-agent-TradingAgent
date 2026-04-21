# agent/research_v1/researchers/ — Legacy Bull/Bear Researchers

## What This Directory Is

Legacy Phase 1-4 researcher agents. Contains `bull_researcher.py` and `bear_researcher.py`
which produce bull-case and bear-case research for individual tickers.

## Status: FROZEN

This directory is **frozen** — no new development. It was replaced by the canonical
`subagent_executor.py` + `analysts/` pipeline (Phase 11).

## Core Files

| File | Purpose |
|---|---|
| `bull_researcher.py` | Bull-case researcher (legacy) |
| `bear_researcher.py` | Bear-case researcher (legacy) |
| `research_manager.py` | Legacy research orchestration |

## Relationship to Other Directories

- **Replaced by**: `agent/research_v1/subagent_executor.py` + `agent/research_v1/analysts/`
- **Used by**: legacy pipeline only (frozen)

## If You Modify Code Here

**Do NOT modify.** This directory is frozen. If you need new analyst functionality,
add it to `agent/research_v1/analysts/` and wire it into `subagent_executor.py`.
