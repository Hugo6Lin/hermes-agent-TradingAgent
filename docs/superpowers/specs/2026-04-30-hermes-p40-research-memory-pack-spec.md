# Hermes P40 Research Memory Pack Spec

Date: 2026-04-30
Status: Approved for implementation planning
Scope: Standalone ticker-level research memory packs, append-only persistence, local CLI, and boss-readable artifacts

## 1. Purpose

P40 gives Hermes a memory layer for prior ticker context.

Before P40, Hermes can produce recommendations, track outcomes, score market regime, score fundamental quality, and surface candidates. The boss still has to manually remember what Hermes said before, whether a thesis already appeared, what happened after prior calls, and whether the same ticker was recently a candidate.

P40 answers:

```text
For this ticker and as-of date, what has Hermes already seen, said, tracked, and learned?
```

P40 is not a recommendation engine. It does not change `final_judge`, does not inject context into `JudgeInputPacket`, and does not trigger a new research run. It produces memory evidence only.

## 2. Product Intent

Hermes should protect the boss from repeat work and forgotten context. When the boss revisits a ticker, Hermes should surface:

- prior research calls and visible action vocabulary
- realized outcome history
- candidate-pool appearances
- latest fundamental-quality context
- latest market-regime context
- watchlist state
- stale or missing context warnings

The expected workflow is:

1. Run P36-P39 when those inputs are available.
2. Run P40 for tickers the boss is considering.
3. Read `p40_research_memory_pack.md`.
4. Manually decide whether to launch a normal `HermesResearchApp.run()` request.

## 3. Non-Goals

P40 must not:

- auto-trade
- send broker orders
- approve production adoption
- mutate production calibration config
- train models
- schedule jobs
- send notifications
- add a viewer
- call `HermesResearchApp.run()`
- call `run_research`
- call `final_judge`
- create `CanonicalSignal`
- create `CanonicalReport`
- change `RoleWeightConfig`
- inject memory into `JudgeInputPacket`
- change `_extract_thesis_inputs()`
- change `ThesisEngine`
- change ticker recommendations
- change P35 governance runtime
- mutate P36 outcome rows
- mutate P37 market-regime snapshots
- mutate P38 fundamental-quality reports
- mutate P39 candidate-pool rows
- use LLMs to summarize memory

P40 is deterministic memory evidence only.

## 4. Phase Map

### P40-A: Memory Collector

Create a focused module that gathers read-only ticker history from canonical research tables, P36 outcomes, P37 regime, P38 quality, P39 candidate pools, and watchlist entries.

### P40-B: Memory Pack Builder + Persistence

Build deterministic ticker memory packs, persist append-only pack runs, and write JSON/Markdown artifacts.

### P40-C: CLI

Add a local `memory-pack-run` command that accepts tickers or a JSON input file, builds memory packs, persists them, writes artifacts, and prints a short summary.

### P40-D: Docs + Regression

Update docs and run focused, P36-P39, governance-adjacent, and doc-standard regression tests.

## 5. Input Contract

P40 accepts either CLI tickers or an input JSON file.

CLI example:

```bash
python -m agent.research_v1.batch_cli memory-pack-run \
  --app-root /path/to/app \
  --tickers AAPL,MSFT \
  --as-of-date 2026-04-30 \
  --lookback-days 180 \
  --output-root output/governance
```

JSON input shape:

```json
{
  "as_of_date": "2026-04-30",
  "lookback_days": 180,
  "tickers": ["AAPL", "MSFT"],
  "source": "manual_review"
}
```

Rules:

- CLI `--as-of-date` overrides input `as_of_date`.
- CLI `--lookback-days` overrides input `lookback_days`.
- Tickers must be normalized to uppercase, stripped, deduplicated, and sorted.
- Empty ticker lists are invalid.
- `lookback_days` must be a positive integer.
- Date values must be valid `YYYY-MM-DD`.

## 6. Read-Only Data Sources

P40 may read:

```text
research_tasks
canonical_signals
canonical_reports
canonical_recommendation_outcomes
candidate_pool_runs
candidate_pool_items
market_regime_snapshots
fundamental_quality_reports
watchlist_entries
validation_results
```

P40 must tolerate missing optional tables. Missing tables become `missing_context` warnings; they must not crash the run.

P40 must not write to any source table above.

## 7. Memory Pack Content

Each ticker memory pack must include:

```text
schema_version
pack_id
as_of_date
created_at
ticker
lookback_days
memory_status
latest_research
prior_signals
outcome_summary
candidate_history
quality_context
regime_context
watchlist_context
validation_context
recurring_themes
risk_memory
missing_context
source_refs
source_hash
disclaimer
```

Statuses:

```text
memory_available
limited_memory
no_prior_memory
blocked_invalid_input
```

Status rules:

- `memory_available`: at least one prior signal/report/candidate/outcome exists.
- `limited_memory`: only context evidence exists, such as P37/P38/watchlist, but no prior signal/report/candidate/outcome.
- `no_prior_memory`: no usable context exists for the ticker.
- `blocked_invalid_input`: invalid date, lookback, or ticker shape.

## 8. Latest Research

`latest_research` is derived from the newest canonical report/signal for the ticker at or before `as_of_date`.

Fields:

```text
task_id
signal_id
report_id
created_at
rating
confidence
priority_score
visible_action
title
bottom_line
why_now
risk_flags
decision_reason
```

Visible action resolution:

1. Prefer `decision_card.primary_action` from canonical report.
2. Else prefer `instrument_rec.primary_action`.
3. Else use `trade_plan.action` only as a legacy fallback and mark `legacy_action_fallback`.
4. If no action is available, use `unknown_prior_action`.

P40 must label this as historical context, not an instruction.

## 9. Prior Signals

Include up to `max_items_per_ticker` prior canonical signals within lookback.

Fields:

```text
signal_id
task_id
created_at
rating
confidence
priority_score
entry_price
stop_loss
take_profit
holding_horizon
risk_flags
decision_reason
```

Sort by:

```text
created_at DESC, signal_id ASC
```

## 10. Outcome Summary

Use P36 outcomes for each included signal.

Fields:

```text
total_outcome_rows
evaluated_rows
not_applicable_rows
insufficient_data_rows
win_rate
median_net_return_pct
best_net_return_pct
worst_net_return_pct
latest_outcome_date
status_counts
```

Only rows with numeric `net_return_pct` participate in return statistics.

Win rate uses P36's persisted `win` field when available. If unavailable, derive `net_return_pct > 0`.

## 11. Candidate History

Use P39 candidate-pool rows for the ticker within lookback.

Fields:

```text
appearance_count
latest_candidate_date
latest_category
latest_workflow_action
best_total_score
latest_total_score
recent_inclusion_reasons
recent_missing_context
```

This is candidate history only. `research_candidate` remains a workflow label, not a trade action.

## 12. Quality Context

Use latest P38 report at or before `as_of_date`.

Fields:

```text
as_of_date
quality_label
overall_quality_score
confidence
red_flags
missing_required_fields
source_hash
```

If unavailable, add `missing_fundamental_quality`.

## 13. Regime Context

Use latest P37 snapshot at or before `as_of_date`.

Fields:

```text
as_of_date
regime_label
confidence
source_hash
```

If unavailable, add `missing_market_regime_context`.

## 14. Watchlist + Validation Context

Use watchlist and validation rows when available.

Watchlist fields:

```text
status
thesis_state
alert_level
current_action_bias
updated_at
```

Validation fields:

```text
regime
historical_support
environment_fit
main_failure_mode
validation_confidence
updated_at
```

If unavailable, add `missing_watchlist_context` or `missing_validation_context`.

## 15. Recurring Themes and Risk Memory

P40 must derive deterministic text tokens from stored fields, not LLM summaries.

Recurring themes may include:

```text
repeated_quality_candidate
repeated_momentum_candidate
prior_high_confidence_research
prior_watchlist_state
positive_outcome_history
negative_outcome_history
stale_research_context
```

Risk memory may include:

```text
prior_stop_breached
prior_insufficient_outcome_data
recurring_missing_context
quality_red_flags_present
elevated_candidate_volatility
legacy_action_fallback_used
```

## 16. Source Hash

`source_hash` must be deterministic SHA-256 over canonical JSON containing:

- `schema_version`
- `as_of_date`
- `ticker`
- `lookback_days`
- selected canonical signal IDs and created_at values
- selected canonical report IDs and created_at values
- selected P36 outcome IDs or deterministic outcome row keys
- selected P39 candidate item IDs/source hashes
- selected P38 source hash
- selected P37 source hash
- selected watchlist updated_at
- selected validation updated_at

Any selected source row change must change the memory pack hash.

## 17. Persistence

Add `research_memory_packs`:

```text
pack_id
schema_version
as_of_date
created_at
ticker
lookback_days
memory_status
source_hash
latest_research_json
outcome_summary_json
candidate_history_json
quality_context_json
regime_context_json
watchlist_context_json
validation_context_json
recurring_themes_json
risk_memory_json
missing_context_json
source_refs_json
summary
```

Natural key:

```text
(ticker, as_of_date, lookback_days, source_hash)
```

Same source hash is idempotent. Revised source rows append a distinguishable pack.

## 18. Artifacts

Write:

```text
output/governance/YYYY-MM-DD/p40_research_memory_pack.json
output/governance/YYYY-MM-DD/p40_research_memory_pack.md
```

Markdown sections:

1. run metadata
2. ticker summary table
3. latest research context
4. outcome memory
5. candidate history
6. missing context
7. risk memory
8. disclaimer

Forbidden terms in Markdown:

```text
buy this now
sell this now
follow this trade
guaranteed edge
production approved
model promoted
trade now
```

Allowed workflow phrase:

```text
historical context only
```

## 19. CLI

Command:

```bash
python -m agent.research_v1.batch_cli memory-pack-run \
  --tickers AAPL,MSFT \
  --as-of-date 2026-04-30 \
  --lookback-days 180 \
  --output-root output/governance
```

Arguments:

```text
--tickers             comma-separated ticker list
--input               optional JSON input file
--as-of-date          required unless input contains as_of_date
--lookback-days       optional positive integer, default 180
--output-root         optional, default output/governance, relative to --app-root
--max-items-per-ticker optional positive integer, default 5
```

At least one of `--tickers` or `--input` is required.

Exit codes:

- `0` for memory_available, limited_memory, or no_prior_memory runs.
- `2` for invalid path, invalid JSON, invalid date, invalid lookback, invalid max items, or empty ticker list.

Printed summary:

```text
Research memory status: <status>
Output dir: <path>
Ticker count: <n>
Memory available: <n>
Limited memory: <n>
No prior memory: <n>
Warning count: <n>
```

## 20. Hard Boundary Test

Add an explicit hard-boundary test asserting P40 does not expose or call:

```text
broker
order
train_model
scheduler
notification
HermesResearchApp
run_research
final_judge
JudgeInputPacket
CanonicalSignal
CanonicalReport
run_governance_runtime
run_recommendation_outcome_tracking
run_market_regime_context
run_fundamental_quality
run_candidate_pool
_extract_thesis_inputs
```

The test must assert the disclaimer contains:

```text
P40 is research-memory evidence only.
```

## 21. Required Tests

P40 focused tests must cover:

1. Ticker normalization deduplicates and sorts.
2. Empty ticker list is blocked.
3. Latest research resolves decision-card action before legacy trade plan.
4. Legacy action fallback is marked.
5. Prior signals are sorted deterministically.
6. Outcome summary computes status counts and median net return.
7. Candidate history summarizes P39 appearances.
8. Latest P38 quality context is included.
9. Latest P37 regime context is included.
10. Missing optional tables do not crash the run.
11. Missing contexts are recorded.
12. Recurring themes are deterministic.
13. Risk memory is deterministic.
14. Source hash changes when a selected prior signal changes.
15. Persistence is idempotent for same natural key.
16. Revised source hash appends a new pack.
17. Artifacts write JSON and Markdown.
18. Markdown avoids forbidden trading language.
19. CLI success writes under app root for relative output root.
20. CLI rejects invalid date/lookback/input/tickers.
21. Hard boundaries are explicit.

## 22. Regression Requirements

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_research_memory_pack.py -q
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_batch_cli.py -q -k "memory_pack or memory-pack"
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_recommendation_outcomes.py tests/agent/research_v1/test_market_regime_context.py tests/agent/research_v1/test_fundamental_quality.py tests/agent/research_v1/test_candidate_pool.py -q
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_governance_runtime.py tests/agent/research_v1/test_boss_governance_brief.py tests/agent/research_v1/test_signal_family_edge_review.py -q
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_doc_standards.py -q
```

Full P20-P40 chain should be run after implementation, excluding only known host-specific PDF/Futu gaps when necessary.

## 23. Commit Split

Expected implementation commits:

1. `feat: add research memory collector`
2. `feat: persist research memory packs`
3. `feat: add research memory cli`
4. `docs: document p40 research memory`

## 24. Acceptance Criteria

P40 is complete when:

- Memory packs are deterministic and read-only.
- Prior research, outcomes, candidate history, quality, regime, watchlist, and validation context are included when available.
- Missing optional context is explicit.
- Persistence is append-only and idempotent.
- CLI validates inputs and writes artifacts under the correct app root.
- Hard-boundary tests pass.
- P36-P39 regressions pass.
- Doc standards pass.
- No existing research recommendation behavior changes.
