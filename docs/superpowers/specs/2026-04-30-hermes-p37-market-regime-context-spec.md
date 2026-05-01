# Hermes P37 Market Regime Context Spec

Date: 2026-04-30
Status: Approved for implementation planning
Scope: Standalone market-regime snapshot, read-only context artifact, local CLI, and persistence hooks for future research-context injection

## 1. Purpose

P37 closes the largest remaining co-pilot gap after P36: Hermes can evaluate individual recommendations, but it still lacks a top-down market context layer.

P37 builds a daily market-regime snapshot that helps the boss answer:

```text
What kind of market am I operating in today, and should individual ticker ideas be interpreted with more risk-on, risk-off, volatile, narrow, or broad-market caution?
```

P37 must not make trades, approve production, change recommendation authority, or silently alter ticker judgments. It creates auditable market context for humans and future phases.

## 2. Product Intent

Hermes is a boss-facing investment research co-pilot. The boss should not need to manually stitch together index trend, volatility, breadth, sector rotation, rates, credit, and dollar context before asking Hermes about a ticker.

P37 provides a first durable market-analysis artifact. Later phases may inject this artifact into `JudgeInputPacket` or candidate generation, but P37 itself remains standalone and read-only.

## 3. Non-Goals

P37 must not:

- auto-trade
- send broker orders
- approve production adoption
- mutate production calibration config
- train models
- schedule recurring jobs
- send notifications
- add a viewer
- change `final_judge`
- change `RoleWeightConfig`
- inject market-regime context into `JudgeInputPacket`
- change any existing ticker recommendation
- change P35 governance runtime
- change P36 outcome tracking
- create candidate pools or screeners
- perform backtesting
- claim macro forecasting ability

P37 is context generation only.

## 4. Phase Map

### P37-A: Market Regime Schema + Metrics

Create a focused market-regime module with deterministic metric computation over normalized market proxy histories.

### P37-B: Persistence + Artifact Writer

Persist market-regime snapshots and write JSON/Markdown artifacts under `output/governance/YYYY-MM-DD/`.

### P37-C: CLI

Add a local `market-regime-run` command that fetches market proxy history, builds the snapshot, persists it, writes artifacts, and prints a short status summary.

### P37-D: Docs + Regression

Update docs and run focused, P36, governance-adjacent, and doc-standard regression tests.

## 5. Inputs

P37 uses market proxy histories. Tests must use fake providers. Local runtime may use existing market-data providers.

Provider interface:

```text
fetch_history(symbol: str, start_date: date, end_date: date) -> list[dict]
```

Expected normalized row fields:

```text
date
open
high
low
close
volume
price_adjustment
```

Minimum required field:

```text
close
```

If a required proxy has no usable close history, mark the snapshot `degraded_missing_inputs`.

## 6. Default Proxy Universe

P37 V1 default symbols:

```text
SPY  -> us_equity_large_cap
QQQ  -> us_growth
IWM  -> us_small_cap
VIX  -> volatility_proxy
TLT  -> duration_rates_proxy
HYG  -> high_yield_credit_proxy
LQD  -> investment_grade_credit_proxy
UUP  -> dollar_proxy
XLK  -> technology
XLF  -> financials
XLY  -> consumer_discretionary
XLP  -> consumer_staples
XLE  -> energy
XLV  -> healthcare
XLI  -> industrials
XLU  -> utilities
XLB  -> materials
XLC  -> communication_services
XLRE -> real_estate
```

If a provider requires market prefixes, the provider adapter may normalize symbols. The artifact must persist both requested symbol and provider symbol when available.

## 7. Metrics

P37 computes deterministic metrics:

```text
return_1d
return_5d
return_20d
realized_vol_20d
drawdown_20d
drawdown_60d
above_sma_20
above_sma_50
```

For sector proxies, compute relative strength versus `SPY`:

```text
sector_relative_strength_20d = sector_return_20d - spy_return_20d
```

For breadth proxy:

```text
breadth_above_sma_20 = count(proxies above SMA20) / count(proxies with enough data)
breadth_above_sma_50 = count(proxies above SMA50) / count(proxies with enough data)
sector_positive_20d_ratio = count(sector proxies with positive 20d return) / count(sector proxies with enough data)
```

For risk appetite proxy:

```text
credit_risk_appetite_20d = HYG_return_20d - LQD_return_20d
growth_vs_defensive_20d = QQQ_return_20d - XLP_return_20d
small_vs_large_20d = IWM_return_20d - SPY_return_20d
duration_pressure_20d = -TLT_return_20d
dollar_pressure_20d = UUP_return_20d
```

## 8. Regime Classification

P37 V1 must be rule-based, deterministic, and explainable. It must not train a model.

Allowed regime labels:

```text
risk_on_broad
risk_on_narrow
risk_off
high_volatility
range_bound
degraded_unknown
```

Recommended classification:

- `degraded_unknown`: required inputs are missing.
- `high_volatility`: volatility proxy is elevated or SPY realized volatility is high and SPY drawdown is material.
- `risk_off`: SPY 20d return is negative, breadth is weak, and credit risk appetite is negative.
- `risk_on_broad`: SPY 20d return is positive, breadth is strong, and sector-positive ratio is broad.
- `risk_on_narrow`: SPY or QQQ is positive but breadth or sector-positive ratio is weak.
- `range_bound`: none of the above dominates.

The snapshot must include `classification_reasons`, not only a label.

## 9. Confidence and Data Quality

Persist:

```text
coverage_ratio
missing_symbols
stale_symbols
data_quality_warnings
confidence
```

Confidence is bounded:

```text
0.0 <= confidence <= 1.0
```

Suggested confidence:

```text
confidence = min(1.0, coverage_ratio) - stale_penalty - contradiction_penalty
```

Contradictions include:

- risk-on index trend with weak breadth
- strong sector concentration
- equity strength with credit deterioration
- high volatility with risk-on classification

Do not block artifact writing on contradictions. Record them as warnings and reduce confidence.

## 10. Schema

Create a persisted snapshot table equivalent to:

```text
market_regime_snapshots
```

Required persisted fields:

```text
snapshot_id
schema_version
as_of_date
created_at
regime_label
confidence
coverage_ratio
summary_json
metrics_json
proxy_metrics_json
sector_rotation_json
classification_reasons_json
warnings_json
missing_symbols_json
stale_symbols_json
data_source_hash
```

Schema version:

```text
p37_market_regime_snapshot.1
```

Natural key:

```text
(as_of_date, data_source_hash)
```

Rerun behavior:

- Same as-of date and same source hash: no duplicate row.
- Same as-of date and revised source hash: append a new row.

## 11. Artifact

Write:

```text
output/governance/YYYY-MM-DD/p37_market_regime_snapshot.json
output/governance/YYYY-MM-DD/p37_market_regime_snapshot.md
```

Required JSON fields:

```text
schema_version
as_of_date
created_at
status
regime_label
confidence
coverage_ratio
summary
classification_reasons
warnings
missing_symbols
stale_symbols
breadth
risk_appetite
sector_rotation
proxy_metrics
data_source_hash
disclaimer
```

Markdown must lead with:

1. regime label
2. confidence
3. three to five classification reasons
4. market-context disclaimer
5. breadth and sector-rotation table

Disclaimer:

```text
P37 is market-context evidence only. It does not approve production adoption, change recommendations, instruct trades, place orders, train models, schedule jobs, or mutate production configuration.
```

## 12. CLI

Add:

```bash
python -m agent.research_v1.batch_cli market-regime-run \
  --app-root /path/to/app \
  --as-of-date 2026-04-30 \
  --lookback-days 90 \
  --output-root output/governance
```

Behavior:

- fetch default proxy histories
- compute market-regime snapshot
- persist it
- write JSON/Markdown artifacts
- print status, output dir, regime label, confidence, missing count, and warnings

`--output-root` follows the P35/P36 convention: if relative, resolve it under `--app-root`; if absolute, preserve it.

Exit codes:

- `0` for completed or completed-with-warnings
- `2` for invalid CLI input

## 13. Hard Boundaries

Add an explicit hard-boundary test asserting P37 does not:

- call broker/order APIs
- train models
- schedule jobs
- send notifications
- mutate production config
- call `final_judge`
- call `run_governance_runtime`
- call `run_recommendation_outcome_tracking`

## 14. Required Tests

P37 must add focused tests for:

1. Normalized proxy rows produce expected returns, volatility, drawdown, SMA flags.
2. Breadth metrics compute from available proxies only.
3. Sector rotation ranks sectors by 20d relative strength versus SPY.
4. `risk_on_broad` classification from positive SPY, strong breadth, broad sectors.
5. `risk_on_narrow` classification from positive QQQ/SPY with weak breadth.
6. `risk_off` classification from negative SPY, weak breadth, negative credit appetite.
7. `high_volatility` classification from high volatility and drawdown.
8. Missing required inputs produce `degraded_missing_inputs` or `degraded_unknown`.
9. Confidence is reduced by missing inputs and contradictions.
10. Data source hash is deterministic.
11. Same natural key no-ops on rerun.
12. Revised data hash appends a row.
13. JSON and Markdown artifacts are written.
14. CLI resolves relative output root under `--app-root`.
15. CLI rejects invalid as-of date and negative lookback.
16. Hard-boundary test enforces no trading, model training, scheduling, notifications, production mutation, judge call, P35 call, or P36 call.

## 15. Documentation

Update:

```text
README.md
agent/research_v1/README.md
```

Docs must explain:

- P37 is standalone market-context evidence.
- P37 does not change ticker recommendations in this phase.
- P37 artifacts live under `output/governance/YYYY-MM-DD/`.
- P37 snapshot persistence is append-only and idempotent by `(as_of_date, data_source_hash)`.
- Future phases may inject this context into research, but P37 does not.

## 16. Suggested Commit Split

Use four reviewable commits:

1. `feat: add market regime snapshot metrics`
2. `feat: persist market regime snapshots`
3. `feat: add market regime cli`
4. `docs: document p37 market regime context`

## 17. Acceptance Criteria

P37 is complete when:

- P37 focused tests pass.
- Existing P36 focused tests still pass.
- Governance-adjacent tests still pass.
- Doc standards still pass.
- `market-regime-run` writes JSON and Markdown artifacts.
- Reruns with identical input data do not duplicate persisted snapshots.
- Revised input data appends a distinguishable snapshot.
- P37 does not trade, train, schedule, notify, approve production, mutate production config, change ticker recommendations, call P35 runtime, or call P36 outcome tracking.
