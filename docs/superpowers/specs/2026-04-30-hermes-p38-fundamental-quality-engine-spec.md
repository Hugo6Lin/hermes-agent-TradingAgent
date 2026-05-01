# Hermes P38 Fundamental Quality Engine Spec

Date: 2026-04-30
Status: Approved for implementation planning
Scope: Standalone fundamental-quality scoring, append-only persistence, local CLI, and boss-readable artifacts

## 1. Purpose

P38 replaces Hermes' weakest current fundamentals proxy with an explicit, auditable quality engine.

Today, `_extract_thesis_inputs()` derives fundamental quality from bullish evidence fraction times analyst confidence. That is useful as a fallback, but it is not a real business-quality model. P38 adds a deterministic fundamental-quality score from structured financial data so the boss can spend less time manually checking margins, cash conversion, leverage, dilution, and growth quality.

P38 answers:

```text
Given point-in-time financial rows for a ticker, how strong is the business quality, which dimensions drive the score, and which red flags require human attention?
```

## 2. Product Intent

Hermes is a boss-facing investment research co-pilot. The boss should not need to manually reconstruct multi-quarter fundamental quality from raw statements every time Hermes reviews a name.

P38 provides a standalone evidence artifact. Later phases may feed this quality score into `ThesisEngine`, `JudgeInputPacket`, candidate generation, or governance edge review. P38 itself must not change recommendations.

## 3. Non-Goals

P38 must not:

- auto-trade
- send broker orders
- approve production adoption
- mutate production calibration config
- train models
- schedule jobs
- send notifications
- add a viewer
- call `final_judge`
- change `RoleWeightConfig`
- inject quality scores into `JudgeInputPacket`
- change `_extract_thesis_inputs()`
- change `ThesisEngine` behavior
- change any ticker recommendation
- change P35 runtime
- change P36 outcome tracking
- change P37 market-regime context
- scrape live financial statements
- use LLMs to compute numeric quality scores

P38 is deterministic fundamental-quality evidence only.

## 4. Phase Map

### P38-A: Quality Metrics + Scoring

Create a focused fundamental-quality module that normalizes point-in-time financial rows and computes deterministic dimension scores.

### P38-B: Persistence + Artifacts

Persist append-only fundamental-quality reports and write JSON/Markdown artifacts under `output/governance/YYYY-MM-DD/`.

### P38-C: CLI

Add a local `fundamental-quality-run` command that reads a structured JSON input file, builds reports, persists them, writes artifacts, and prints a short summary.

### P38-D: Docs + Regression

Update docs and run focused, P36, P37, governance-adjacent, and doc-standard regression tests.

## 5. Input Contract

P38 consumes explicit point-in-time financial rows. Tests must use local fixtures. Runtime v1 uses a JSON input file, not live scraping.

Input file shape:

```json
{
  "as_of_date": "2026-04-30",
  "source": "manual_fixture",
  "tickers": [
    {
      "ticker": "AAPL",
      "sector": "technology",
      "currency": "USD",
      "rows": [
        {
          "period_end": "2025-03-31",
          "filing_date": "2025-05-01",
          "source_date": "2025-05-01",
          "revenue": 100000000,
          "gross_profit": 45000000,
          "operating_income": 25000000,
          "net_income": 21000000,
          "cfo": 26000000,
          "capex": -5000000,
          "free_cash_flow": 21000000,
          "total_debt": 30000000,
          "cash_and_equivalents": 18000000,
          "shareholders_equity": 70000000,
          "shares_outstanding": 10000000,
          "eps": 2.10,
          "ebit": 25000000,
          "current_assets": 50000000,
          "current_liabilities": 25000000
        }
      ]
    }
  ]
}
```

Required row fields:

```text
period_end
source_date
revenue
gross_profit
operating_income
net_income
cfo
capex
total_debt
cash_and_equivalents
shareholders_equity
shares_outstanding
```

Optional row fields:

```text
filing_date
free_cash_flow
eps
ebit
current_assets
current_liabilities
```

If `free_cash_flow` is absent, compute:

```text
free_cash_flow = cfo + capex
```

where capex is expected to be negative for cash outflow. If capex is positive, treat it as provided and add `capex_sign_check` warning.

## 6. Point-In-Time Rules

P38 must enforce source-date integrity:

- Ignore rows with `source_date > as_of_date`.
- Mark ignored rows in warnings as `future_source_date_ignored`.
- Sort usable rows by `period_end`.
- Require at least 4 usable rows for a complete report.
- With 2-3 usable rows, emit `degraded_insufficient_history`.
- With fewer than 2 usable rows, emit `blocked_missing_fundamentals`.

No restated future rows may be silently used.

## 7. Metrics

P38 computes:

```text
gross_margin
operating_margin
net_margin
roe
roic
fcf_margin
fcf_conversion
revenue_growth_yoy
eps_growth_yoy
fcf_growth_yoy
debt_to_equity
net_debt_to_fcf
current_ratio
share_count_growth_yoy
margin_stability
fcf_stability
```

YoY metrics require at least 5 quarterly rows or at least 2 annual rows with comparable period cadence. If unavailable, persist `null` and add a coverage warning.

## 8. Dimension Scores

All dimension scores are bounded:

```text
0.0 <= score <= 1.0
```

Dimensions:

```text
profitability_score
growth_quality_score
cash_conversion_score
balance_sheet_score
dilution_score
stability_score
```

Suggested v1 scoring:

- `profitability_score`: weighted ROIC, operating margin, gross margin.
- `growth_quality_score`: weighted revenue growth, EPS growth, FCF growth.
- `cash_conversion_score`: weighted FCF margin and FCF conversion.
- `balance_sheet_score`: penalize high debt/equity, high net debt/FCF, weak current ratio.
- `dilution_score`: penalize positive share count growth; reward stable or declining shares.
- `stability_score`: penalize high margin volatility and FCF volatility.

Overall score:

```text
overall_quality_score =
  0.25 * profitability_score +
  0.20 * growth_quality_score +
  0.20 * cash_conversion_score +
  0.15 * balance_sheet_score +
  0.10 * dilution_score +
  0.10 * stability_score
```

Do not make these weights configurable in P38. They are code constants for deterministic review.

## 9. Labels and Red Flags

Allowed quality labels:

```text
compounder_quality
solid_quality
watchlist_quality
low_quality
blocked_missing_fundamentals
```

Label guidance:

- `compounder_quality`: overall >= 0.80 and no severe red flags.
- `solid_quality`: overall >= 0.65 and no severe red flags.
- `watchlist_quality`: overall >= 0.45 or degraded history.
- `low_quality`: overall < 0.45.
- `blocked_missing_fundamentals`: fewer than 2 usable rows.

Red flags:

```text
negative_revenue
negative_equity
negative_fcf
fcf_conversion_below_zero
debt_to_equity_high
net_debt_to_fcf_high
share_dilution_high
margin_compression
source_date_after_as_of_ignored
insufficient_history
missing_required_fields
capex_sign_check
```

Red flags lower confidence. Severe red flags prevent `compounder_quality`.

## 10. Confidence and Coverage

Persist:

```text
coverage_ratio
usable_row_count
ignored_future_row_count
missing_required_fields
confidence
```

Suggested confidence:

```text
confidence = coverage_ratio
confidence -= 0.15 if usable_row_count < 4
confidence -= 0.10 for each severe red flag, capped at 0.30
confidence = clamp(confidence, 0.0, 1.0)
```

## 11. Schema

Create a persisted table equivalent to:

```text
fundamental_quality_reports
```

Required persisted fields:

```text
report_id
schema_version
as_of_date
created_at
ticker
sector
currency
status
quality_label
overall_quality_score
confidence
coverage_ratio
usable_row_count
ignored_future_row_count
dimension_scores_json
latest_metrics_json
trend_metrics_json
red_flags_json
warnings_json
source_hash
summary
```

Schema version:

```text
p38_fundamental_quality.1
```

Natural key:

```text
(ticker, as_of_date, source_hash)
```

Rerun behavior:

- Same ticker, as-of date, and source hash: no duplicate row.
- Same ticker and as-of date with revised source hash: append a new row.

## 12. Source Hash

`source_hash` must be deterministic:

- SHA-256
- canonical JSON serialization
- sorted tickers
- sorted usable and ignored rows by `period_end`, `source_date`
- fixed field order for every financial input consumed
- include `as_of_date`, `ticker`, `sector`, and `currency`

Middle-row changes must produce a different hash.

## 13. Artifact

Write:

```text
output/governance/YYYY-MM-DD/p38_fundamental_quality.json
output/governance/YYYY-MM-DD/p38_fundamental_quality.md
```

Required JSON fields:

```text
schema_version
as_of_date
created_at
status
reports
summary
warnings
disclaimer
```

Each report must include:

```text
ticker
quality_label
overall_quality_score
confidence
coverage_ratio
dimension_scores
latest_metrics
trend_metrics
red_flags
warnings
source_hash
summary
```

Markdown must lead with:

1. ticker summary table
2. quality labels and overall scores
3. red flags
4. dimension-score table
5. disclaimer

Disclaimer:

```text
P38 is fundamental-quality evidence only. It does not approve production adoption, change recommendations, instruct trades, place orders, train models, schedule jobs, or mutate production configuration.
```

## 14. CLI

Add:

```bash
python -m agent.research_v1.batch_cli fundamental-quality-run \
  --app-root /path/to/app \
  --input /path/to/fundamentals.json \
  --as-of-date 2026-04-30 \
  --output-root output/governance
```

Behavior:

- load JSON input file
- validate shape
- override input `as_of_date` with CLI `--as-of-date` if provided
- build reports for every ticker
- persist reports
- write JSON/Markdown artifacts
- print status, output dir, report count, blocked count, warning count

Exit codes:

- `0` for completed or completed-with-warnings
- `2` for invalid input path, invalid date, invalid JSON, or invalid input shape

## 15. Hard Boundaries

Add an explicit hard-boundary test asserting P38 does not:

- call broker/order APIs
- train models
- schedule jobs
- send notifications
- mutate production config
- call `final_judge`
- call `run_governance_runtime`
- call `run_recommendation_outcome_tracking`
- call `run_market_regime_context`
- mutate `_extract_thesis_inputs()`

## 16. Required Tests

P38 must add focused tests for:

1. Normalized rows compute latest margins, ROE, ROIC, leverage, FCF metrics.
2. YoY growth metrics compute when enough comparable rows exist.
3. Missing optional `free_cash_flow` is computed from CFO + capex.
4. Future `source_date` rows are ignored and warned.
5. Fewer than 2 usable rows produces `blocked_missing_fundamentals`.
6. 2-3 usable rows produces `degraded_insufficient_history`.
7. Strong quality company classifies as `compounder_quality`.
8. High dilution triggers `share_dilution_high` and lowers score.
9. High leverage triggers balance-sheet red flags.
10. Negative FCF triggers cash-conversion red flags.
11. Source hash changes on middle-row revision.
12. Persistence is idempotent for same natural key.
13. Revised source hash appends a new report.
14. JSON and Markdown artifacts are written.
15. CLI resolves relative output root under `--app-root`.
16. CLI rejects invalid JSON/input shape.
17. Hard-boundary test enforces no trading, model training, scheduling, notifications, production mutation, judge call, P35 call, P36 call, P37 call, or thesis-input mutation.

## 17. Documentation

Update:

```text
README.md
agent/research_v1/README.md
```

Docs must explain:

- P38 is standalone fundamental-quality evidence.
- P38 replaces the old confidence-proxy gap with auditable financial dimensions.
- P38 does not change ticker recommendations in this phase.
- P38 artifacts live under `output/governance/YYYY-MM-DD/`.
- P38 persistence is append-only and idempotent by `(ticker, as_of_date, source_hash)`.

## 18. Suggested Commit Split

Use four reviewable commits:

1. `feat: add fundamental quality scoring`
2. `feat: persist fundamental quality reports`
3. `feat: add fundamental quality cli`
4. `docs: document p38 fundamental quality`

## 19. Acceptance Criteria

P38 is complete when:

- P38 focused tests pass.
- P36 and P37 focused tests still pass.
- Governance-adjacent tests still pass.
- Doc standards still pass.
- `fundamental-quality-run` writes JSON and Markdown artifacts.
- Reruns with identical `(ticker, as_of_date, source_hash)` do not duplicate rows.
- Revised input rows append distinguishable reports.
- P38 does not trade, train, schedule, notify, approve production, mutate production config, call judge, call P35, call P36, call P37, or change ticker recommendations.
