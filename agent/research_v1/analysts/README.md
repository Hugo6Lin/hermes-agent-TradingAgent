# agent/research_v1/analysts/ — Individual Analyst Agents

## What This Directory Is

Contains individual analyst implementations called by `SubagentExecutor`. Each analyst
produces an `EvidenceItem` from market data and a role-specific LLM prompt.

## Contents

| File | Role | What It Analyzes |
|---|---|---|
| `technical.py` | `AgentRole.TECHNICAL` | EMA/SMA/RSI/MACD from candles |
| `fundamentals.py` | `AgentRole.FUNDAMENTAL` | Revenue, earnings, debt/equity |
| `news.py` | `AgentRole.NEWS` | News items and event impact |
| `sentiment.py` | `AgentRole.SENTIMENT` | Social/news sentiment scoring |
| `industry.py` | `AgentRole.INDUSTRY` | Industry trends and peer comparison |
| `options.py` | `AgentRole.OPTIONS` | Put/call ratio, open interest, IV |
| `risk.py` | `AgentRole.RISK` | Risk rating, sector exposure |
| `valuation.py` | `AgentRole.VALUATION` | DCF, DDM, relative valuation |

## How Analysts Are Called

```
SubagentExecutor.execute(subtask)
  → _run_role_handler(agent_role, ticker, context)
    → analysts/<role>.research_<role>(ticker, context)  # if market_data_service available
    → LLM call with analyst-specific prompt
    → EvidenceItem
```

Each analyst receives:
- `ticker`: stock symbol
- `context`: {market_data, candles, option_chain, ...} from `MarketDataService`

## Relationship to Other Files

- **`subagent_executor.py`** — calls analysts based on `AgentRole`
- **`contracts.py`** — `AgentRole` enum and `EvidenceItem` dataclass
- **`market_data_service.py`** — provides market data context to analysts

## If You Modify Code Here

- `subagent_executor.py` — if you change how analysts are called
- `contracts.py` — if you add a new `AgentRole`
- `test_market_data_service.py` — if you change the analyst interface
- `test_app_integration.py` — if you change analyst output format

## Data Flow / How It Fits

Analysts sit in the middle of the pipeline: `MarketDataService` (upstream) provides
`context` dict containing market data, and each analyst produces an `EvidenceItem` that
flows downstream to `EvidenceStore.normalize()` for deduplication and persistence.
