# Hermes P36 Recommendation Outcome Tracking Spec

Date: 2026-04-30
Status: Approved for implementation planning
Scope: Canonical recommendation outcome tracking, automatic market-data evaluation, standalone P36 audit artifacts

## 1. Purpose

P36 gives Hermes its first measurable recommendation feedback loop.

P20-P35 built the research and governance scaffold. P36 starts answering whether Hermes recommendations actually worked after they were made. The goal is not to trade, backtest, optimize, or promote anything automatically. The goal is to persist forward-looking outcome evidence so future phases can prove whether Hermes is improving.

P36 answers:

```text
For each canonical recommendation Hermes made, what happened after 5/20/60 trading days, under clearly documented evaluation rules?
```

## 2. Product Intent

Hermes is intended to become a boss-facing investment research co-pilot. Outcome tracking is required because later features such as market-regime awareness, candidate generation, emotional guardrails, adversarial review, and calibration governance all need a factual record of past recommendation quality.

Governance remains the audit substrate. P36 adds the evidence that makes the system's improvement falsifiable.

## 3. Non-Goals

P36 must not:

- auto-trade
- send broker orders
- approve production adoption
- mutate production calibration config
- promote shadow outputs into canonical factor fields
- train models
- convert P32-B dry-run into real execution
- schedule recurring jobs
- send notifications
- add a governance viewer
- wire into P35 runtime
- make P33 consume P36 outcomes
- change `RoleWeightConfig`
- inject outcome memory into `JudgeInputPacket`
- perform portfolio attribution
- perform retrospective strategy backtesting
- consolidate multi-leg option outcomes
- evaluate `Bull Call Spread`, `Sell Cash-Secured Put`, or `Covered Call` economics in v1

P36 is forward outcome tracking only.

## 4. Phase Map

### P36-A: Canonical Outcome Schema + Persistence

Add a canonical outcome table linked to `canonical_signals.signal_id`. The table must include schema versioning, action, entry rule, costs, provenance, win semantics, two evaluation timestamps, and idempotent natural-key behavior.

### P36-B: Outcome Computation + Provider Plumbing

Evaluate eligible canonical recommendations using forward market data. The evaluator must be action-aware, calendar-aware, cost-aware, and deterministic under repeated runs.

### P36-C: CLI + Artifact Writer

Add a local `outcome-run` command and write standalone P36 JSON/Markdown artifacts under `output/governance/YYYY-MM-DD/`.

### P36-D: Docs + Regression

Update docs and run focused, governance-adjacent, and doc-standard regression tests.

## 5. Core Semantics

### 5.1 Canonical Source of Truth

P36 must use canonical research outputs.

Primary signal source:

```text
canonical_signals
```

Action source:

```text
canonical_reports.decision_card_json.primary_action
canonical_reports.instrument_rec_json.primary_action
```

Resolution order:

1. latest matching `canonical_reports.decision_card_json.primary_action`
2. latest matching `canonical_reports.instrument_rec_json.primary_action`
3. otherwise `invalid_signal`

Latest report tie-breaker:

1. most recent `created_at`
2. if `created_at` ties, highest `report_id`

When selecting recent canonical signals for a limited run, order deterministically:

```sql
ORDER BY created_at DESC, signal_id
```

### 5.2 Action-Aware Evaluation

P36 must persist the approved boss-facing action on every outcome row.

Allowed action behavior:

| Action | P36 V1 behavior |
|---|---|
| `Buy Stock` | `evaluated` |
| `Buy Call` | `evaluated` using underlying price proxy |
| `Bull Call Spread` | `not_evaluable_in_v1` |
| `Sell Cash-Secured Put` | `not_evaluable_in_v1` |
| `Covered Call` | `not_evaluable_in_v1` |
| `Watchlist` | `not_applicable` |
| `No Trade` | `not_applicable` |
| missing / unknown | `invalid_signal` |

For `Buy Call`, persist:

```text
evaluation_proxy = underlying_price_proxy
```

For `Buy Stock`, persist:

```text
evaluation_proxy = none
```

### 5.3 Entry Rule

Default entry rule:

```text
next_open
```

Meaning:

```text
The recommendation is evaluated as if entered at the next available trading row's open after the signal timestamp.
```

If the next trading row has no open price, mark the affected horizons as:

```text
insufficient_data
```

Do not silently fall back to close.

Persist:

```text
entry_rule
entry_date
entry_price
```

### 5.4 Horizons

Default horizons:

```text
5, 20, 60
```

Horizons are trading-row based, not calendar-day based.

If a required horizon row is missing, mark that horizon as:

```text
insufficient_data
```

Do not shift forward to a later row. If the exchange calendar says a trading day exists but the provider returns no row for that day because of a halt, illiquidity, or vendor outage, the affected horizon is still `insufficient_data`.

### 5.5 Calendar

Calendar resolution:

| Ticker | Calendar |
|---|---|
| `HK.*` | `XHKG` |
| `US.*` | `XNYS` |
| unprefixed ticker | `XNYS` |
| unresolved | `invalid_signal` |

Persist:

```text
calendar
```

### 5.6 Costs

Persist both gross and net return.

Fields:

```text
cost_basis
cost_bps
gross_return_pct
net_return_pct
```

Allowed `cost_basis` values in P36 V1:

```text
none
flat_bps
```

Default:

```text
cost_basis = none
cost_bps = 0
```

If CLI receives `--flat-cost-bps N`, compute:

```text
net_return_pct = gross_return_pct - (2 * N / 10000)
```

Flat-bps round-trip costs apply only to V1 evaluated long-equity and long-call proxy outcomes. P36 V1 spread, cash-secured-put, and covered-call structures are `not_evaluable_in_v1`; they do not enter the cost path.

### 5.7 Provenance

Persist:

```text
data_source
price_adjustment
data_source_hash
path_precision
```

Allowed `price_adjustment` values:

```text
adjusted
unadjusted
unknown
```

Allowed `path_precision` values:

```text
ohlc
close_only
```

`data_source_hash` must be deterministic:

- SHA-256
- over canonical JSON serialization
- exact normalized price rows consumed for that signal and horizon
- sorted by date
- fixed field order: `date`, `open`, `high`, `low`, `close`, `price_adjustment`
- JSON separators `(",", ":")`
- `sort_keys=True`

If the provider does not declare whether prices are adjusted or unadjusted, persist:

```text
price_adjustment = unknown
```

### 5.8 Win Definition

Persist enough fields to recompute win definitions later:

```text
target_reached
stop_breached
target_reached_before_stop
benchmark_return_pct
gross_return_pct
net_return_pct
win
win_definition
```

Canonical `win` definition:

- If both `take_profit` and `stop_loss` exist, `win = target_reached_before_stop`.
- If a target/stop pair is incomplete, `win = net_return_pct > 0`.

Persist:

```text
win_definition = target_reached_before_stop
```

or:

```text
win_definition = net_return_positive
```

### 5.9 Rerun and Idempotence Policy

P36 is append-only with natural-key idempotence.

Natural key:

```text
(signal_id, horizon_days, evaluated_for_date, data_source_hash)
```

Rerun behavior:

- Same signal, horizon, evaluated-for date, and data hash: no duplicate row.
- Same signal, horizon, evaluated-for date, but revised price data hash: append a new row.
- `evaluated_at` is wall-clock audit time and must not participate in the natural key.

This lets reviewers distinguish an identical rerun from a market-data revision.

### 5.10 Evaluation Dates

Persist two dates:

```text
evaluated_for_date
evaluated_at
```

`evaluated_for_date` is the logical as-of date that drives the evaluation pivot. It participates in the natural key.

`evaluated_at` is the UTC wall-clock instant when the computation ran. It does not participate in the natural key.

## 6. Canonical Outcome Table

Create a table equivalent to:

```text
canonical_recommendation_outcomes
```

Required persisted fields:

```text
schema_version
canonical_outcome_id
signal_id
task_id
ticker
action
rating
horizon_days
calendar
entry_rule
entry_price
entry_date
exit_price
exit_date
target_reached
stop_breached
target_reached_before_stop
benchmark_return_pct
gross_return_pct
net_return_pct
max_drawdown_pct
win
win_definition
status
evaluation_proxy
cost_basis
cost_bps
data_source
price_adjustment
data_source_hash
path_precision
evaluated_for_date
evaluated_at
created_at
```

Schema version:

```text
p36_recommendation_outcome.1
```

Allowed statuses:

```text
evaluated
not_evaluable_in_v1
not_applicable
insufficient_data
invalid_signal
```

## 7. Database API

Extend `ResearchDatabase` with:

```text
initialize_canonical_outcome_schema()
save_canonical_outcome(outcome: dict) -> str
list_canonical_outcomes_by_signal(signal_id: str) -> list[dict]
get_recent_outcome_track_record(ticker: str, lookback_days: int) -> list[dict]
summarize_outcomes_by(group_by: str, horizon_days: int | None = None) -> list[dict]
```

Allowed `group_by`:

```text
rating
action
ticker
horizon
```

Persistence rules:

- Do not dual-write into legacy `signal_outcomes`.
- Do not treat legacy `signal_outcomes` as the source of truth.
- Do not delete or mutate existing canonical signal/report rows.

## 8. Market Provider

P36 must run with a fake provider in tests and may use the existing Futu provider in local runtime.

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
price_adjustment
```

Minimum provider data is `date` and `close`, but `next_open` evaluation requires `open`. If `open` is absent for the required entry row, return `insufficient_data`.

P36 should extend Futu history normalization to include `open`, `high`, and `low` when available. Existing callers that only consume `date` and `close` must keep working.

## 9. CLI

Add:

```bash
python -m agent.research_v1.batch_cli outcome-run \
  --app-root /path/to/app \
  --as-of-date 2026-04-30 \
  --output-root output/governance \
  --limit 50 \
  --flat-cost-bps 0
```

Behavior:

- read recent canonical signals ordered by `created_at DESC, signal_id`
- resolve action from latest matching canonical report
- fetch forward history
- persist canonical outcome rows
- write P36 artifacts
- print status, output paths, evaluated row count, skipped duplicate count, and warnings

`--output-root` follows the P35 convention: if relative, resolve it under `--app-root`; if absolute, preserve it.

Exit codes:

- `0` for completed or completed-with-warnings
- `2` for invalid CLI/config input

The CLI must not start a server, schedule work, send notifications, call a broker, mutate production config, train models, or invoke P35 runtime.

## 10. Artifacts

Write:

```text
output/governance/YYYY-MM-DD/p36_recommendation_outcomes.json
output/governance/YYYY-MM-DD/p36_recommendation_outcomes.md
```

Required JSON fields:

```text
run_date
evaluated_for_date
schema_version
status
signals_considered
outcome_rows_written
duplicate_rows_skipped
evaluated_count
not_applicable_count
not_evaluable_count
insufficient_data_count
invalid_signal_count
warnings
distribution_summary
extreme_examples
disclaimer
```

Distribution summaries must lead the artifact. Extremes are secondary context.

Distribution groups:

```text
action
rating
horizon
```

Required metrics:

```text
sample_size
hit_rate
median_net_return
p25_net_return
p75_net_return
mean_win
mean_loss
average_drawdown
```

Extreme examples:

- largest positive evaluated net returns
- largest negative evaluated net returns

Artifact disclaimer must state:

```text
P36 is recommendation outcome tracking only. It does not approve production adoption, instruct trades, place orders, train models, schedule jobs, or mutate production configuration.
```

## 11. Hard Boundaries

Add an explicit hard-boundary regression test that asserts P36 does not:

- call broker/order APIs
- create scheduler or notification artifacts
- mutate production config files
- invoke model-training modules
- invoke P35 runtime
- write outside `output/governance/YYYY-MM-DD/` except the canonical outcome table

## 12. Required Tests

P36 must add focused tests for:

1. `Buy Stock` evaluates 5/20/60 outcomes with fake OHLC data.
2. `Buy Call` evaluates with `evaluation_proxy = underlying_price_proxy`.
3. `Bull Call Spread`, `Sell Cash-Secured Put`, and `Covered Call` produce `not_evaluable_in_v1`.
4. `Watchlist` and `No Trade` produce `not_applicable`.
5. Missing/unknown action produces `invalid_signal`.
6. Missing signal entry price produces `invalid_signal`.
7. Missing next-open price produces `insufficient_data`.
8. Missing horizon row produces `insufficient_data` without shifting forward.
9. Unresolved calendar produces `invalid_signal`.
10. Provider with no adjustment metadata persists `price_adjustment = unknown`.
11. `data_source_hash` is deterministic for identical normalized rows.
12. Same natural key no-ops on rerun.
13. Revised data hash appends a new row.
14. Flat-bps cost changes net return.
15. Target-before-stop controls win when both target and stop exist.
16. Close-only provider data persists `path_precision = close_only`.
17. Database summaries work by action, rating, ticker, and horizon.
18. CLI writes JSON and Markdown artifacts.
19. Hard-boundary test asserts no broker, scheduler, notification, production config mutation, model training, or P35 runtime invocation.

## 13. Documentation

Update:

```text
README.md
agent/research_v1/README.md
```

Docs must explain:

- P36 is standalone outcome tracking.
- P36 is not a trading engine, backtester, scheduler, or production approver.
- Canonical outcomes are append-only and idempotent by natural key.
- P36 artifacts live under `output/governance/YYYY-MM-DD/`.
- P36 does not wire into P35 runtime in this phase.

If any new directory with Python files is added, add a README for that directory to satisfy doc standards.

## 14. Suggested Commit Split

Use four reviewable commits:

1. `feat: add canonical recommendation outcome persistence`
2. `feat: compute recommendation outcomes`
3. `feat: add recommendation outcome cli`
4. `docs: document p36 recommendation outcomes`

## 15. Acceptance Criteria

P36 is complete when:

- All required P36 focused tests pass.
- Existing P31-P35 governance tests still pass.
- Doc standards still pass.
- The CLI can run against a fake or seeded local database and write both P36 artifacts.
- Re-running the same as-of date with the same market data does not duplicate rows.
- Re-running with revised market data appends distinguishable rows.
- No P36 code path trades, schedules, trains, sends notifications, promotes models, mutates production config, or changes P35 runtime.
