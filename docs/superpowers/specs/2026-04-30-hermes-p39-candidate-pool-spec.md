# Hermes P39 Candidate Pool Spec

Date: 2026-04-30
Status: Approved for implementation planning
Scope: Standalone candidate discovery evidence, append-only persistence, local CLI, and boss-readable artifacts

## 1. Purpose

P39 gives Hermes its first active idea-generation layer.

Before P39, Hermes can evaluate a named ticker, track recommendation outcomes, describe market regime, and score business quality. The boss still has to decide which tickers deserve attention. P39 creates a deterministic candidate pool that screens a supplied universe and ranks names worth human review.

P39 answers:

```text
Given a point-in-time ticker universe plus existing Hermes evidence, which names deserve attention, why, and which ones are excluded?
```

P39 is not a recommendation engine. It does not produce `Buy Stock`, `Buy Call`, `No Trade`, or any trade action. It produces candidate evidence only.

## 2. Product Intent

Hermes should reduce the boss's time spent scanning markets for ideas. P39 moves Hermes from "research this ticker I already chose" toward "show me the most interesting names to consider today" while preserving the same hard safety boundary: no automatic research, no automatic orders, and no financial call.

The expected boss workflow is:

1. Run P36, P37, and P38 when those inputs are available.
2. Run P39 against a curated universe JSON file.
3. Read `p39_candidate_pool.md`.
4. Manually choose which candidates should enter the normal `HermesResearchApp.run()` research path.

## 3. Non-Goals

P39 must not:

- auto-trade
- send broker orders
- approve production adoption
- mutate production calibration config
- train models
- schedule jobs
- send notifications
- add a viewer
- call `HermesResearchApp.run()`
- call `final_judge`
- create `CanonicalSignal`
- create `CanonicalReport`
- change `RoleWeightConfig`
- inject candidates into `JudgeInputPacket`
- change `_extract_thesis_inputs()`
- change `ThesisEngine`
- change ticker recommendations
- change P35 governance runtime
- mutate P36 outcome rows
- mutate P37 market-regime snapshots
- mutate P38 fundamental-quality reports
- scrape live ticker universes
- use LLMs to score candidates

P39 is deterministic discovery evidence only.

## 4. Phase Map

### P39-A: Candidate Scoring Core

Create a focused module that validates a point-in-time universe, joins optional P37/P38/P36 evidence, computes deterministic component scores, ranks candidates, and explains inclusion or exclusion.

### P39-B: Persistence + Artifacts

Persist append-only candidate-pool runs and candidate items. Write JSON/Markdown artifacts under `output/governance/YYYY-MM-DD/`.

### P39-C: CLI

Add a local `candidate-pool-run` command that reads a universe JSON input file, builds the candidate pool, persists it, writes artifacts, and prints a short summary.

### P39-D: Docs + Regression

Update docs and run focused, P36, P37, P38, governance-adjacent, and doc-standard regression tests.

## 5. Input Contract

P39 consumes an explicit point-in-time universe JSON file. Runtime v1 does not scrape a universe.

Input shape:

```json
{
  "as_of_date": "2026-04-30",
  "source": "manual_screen",
  "universe_id": "us_liquid_growth",
  "tickers": [
    {
      "ticker": "AAPL",
      "sector": "technology",
      "currency": "USD",
      "source_date": "2026-04-30",
      "close": 200.0,
      "close_20d_ago": 190.0,
      "close_60d_ago": 170.0,
      "close_120d_ago": 160.0,
      "high_252d": 215.0,
      "low_252d": 140.0,
      "avg_dollar_volume_20d": 1500000000,
      "realized_vol_20d": 0.24,
      "market_cap": 3000000000000,
      "benchmark_return_60d": 0.05,
      "catalyst_tags": ["earnings_soon", "product_cycle"],
      "outcome_prior": {
        "sample_size": 6,
        "hit_rate_20d": 0.67,
        "median_net_return_20d": 0.04
      }
    }
  ]
}
```

Required ticker fields:

```text
ticker
sector
source_date
close
close_20d_ago
close_60d_ago
close_120d_ago
high_252d
low_252d
avg_dollar_volume_20d
realized_vol_20d
```

Optional ticker fields:

```text
currency
market_cap
benchmark_return_60d
catalyst_tags
outcome_prior
exclude_reasons
```

`exclude_reasons` is a caller-supplied list of reasons to force a ticker out of candidate ranking, for example `"restricted_list"` or `"insufficient_source_rights"`.

## 6. Point-in-Time Integrity

P39 must enforce source-date integrity:

- Reject CLI `--as-of-date` values that are not valid `YYYY-MM-DD`.
- Use CLI `--as-of-date` when provided; otherwise use input `as_of_date`.
- Ignore and exclude ticker rows with `source_date > as_of_date`.
- Mark future rows with `future_source_date_ignored`.
- Mark missing required fields with exact field names.
- Mark non-dict ticker items as invalid input in the CLI.
- Never shift a stale row forward to the as-of date.

## 7. Evidence Inputs

P39 may enrich a universe row with prior Hermes evidence:

### P37 Market Regime

Use the latest persisted market-regime snapshot at or before `as_of_date` when available. If unavailable, use neutral regime context and add `missing_market_regime_context`.

Required fields from P37:

```text
regime_label
confidence
sector_scores_json
source_hash
```

### P38 Fundamental Quality

Use the latest persisted fundamental-quality report for each ticker at or before `as_of_date` when available. If unavailable, use neutral quality and add `missing_fundamental_quality`.

Required fields from P38:

```text
quality_label
overall_quality_score
confidence
red_flags_json
source_hash
```

### P36 Outcome Prior

P39 v1 can consume an inline `outcome_prior` from the universe row. It may also read persisted P36 outcomes if a compact database helper is added. Outcome prior must only affect the `track_record_score`; it must not block or approve candidates.

If no outcome prior is available, use neutral track-record context and add `missing_outcome_prior`.

## 8. Eligibility Rules

Each ticker receives an eligibility status before scoring.

Excluded statuses:

```text
excluded_missing_required_fields
excluded_future_source_date
excluded_low_liquidity
excluded_low_price
excluded_user_rule
```

Minimum thresholds:

```text
close >= 5.0
avg_dollar_volume_20d >= 5000000
```

Rows with caller-provided `exclude_reasons` are `excluded_user_rule`.

Excluded rows must still appear in the JSON artifact under `excluded_items`; they must not appear in `candidates`.

## 9. Candidate Categories

P39 candidate categories:

```text
quality_momentum
regime_aligned
recovery_watchlist
liquidity_leader
outcome_retest
balanced_candidate
```

Assignment rules:

- `quality_momentum`: quality score >= 0.65 and 60-day momentum score >= 0.65.
- `regime_aligned`: regime score >= 0.75 and total score >= 0.60.
- `recovery_watchlist`: 60-day return is positive, 120-day return is negative, and quality score >= 0.55.
- `liquidity_leader`: liquidity score >= 0.90 and total score >= 0.55.
- `outcome_retest`: outcome prior sample size >= 3 and hit rate >= 0.60.
- `balanced_candidate`: fallback for included names that do not match another category.

## 10. Component Scores

All component scores must be deterministic floats from `0.0` to `1.0`.

```text
momentum_score
quality_score
regime_score
liquidity_score
risk_penalty_score
track_record_score
```

### Momentum Score

Inputs:

```text
return_20d = close / close_20d_ago - 1
return_60d = close / close_60d_ago - 1
return_120d = close / close_120d_ago - 1
distance_from_252d_high = close / high_252d - 1
```

Normalize:

- 60-day return: `-20% -> 0.0`, `+30% -> 1.0`.
- 20-day return: `-10% -> 0.0`, `+15% -> 1.0`.
- Distance from 252-day high: `-35% -> 0.0`, `0% -> 1.0`.

Weights:

```text
0.50 * normalized_60d
0.30 * normalized_20d
0.20 * normalized_distance_from_high
```

### Quality Score

Use P38 `overall_quality_score` when available. If unavailable, use `0.50`.

Penalize severe P38 red flags by `0.10` each, capped at `0.30`.

Severe P38 red flags:

```text
negative_revenue
negative_equity
negative_fcf
fcf_conversion_below_zero
debt_to_equity_high
net_debt_to_fcf_high
```

### Regime Score

If P37 sector scores are available, use the current ticker sector score.

If P37 sector scores are unavailable, derive a coarse score from regime label:

- `risk_on_broad`: cyclicals, technology, communication_services, consumer_discretionary score `0.75`; defensive sectors score `0.45`; all others `0.55`.
- `risk_on_narrow`: technology and communication_services score `0.70`; all others `0.45`.
- `neutral`: all sectors `0.50`.
- `risk_off`: utilities, staples, healthcare, cash_proxy score `0.70`; cyclicals and technology score `0.40`; all others `0.50`.
- `high_volatility`: all sectors `0.35`.

Multiply by P37 confidence when available. If P37 is missing, use `0.50`.

### Liquidity Score

Normalize `avg_dollar_volume_20d`:

- `< 5M`: excluded
- `5M -> 0.25`
- `50M -> 0.60`
- `250M -> 0.85`
- `1B+ -> 1.00`

Use piecewise linear interpolation.

### Risk Penalty Score

Start at `1.0` and subtract:

- `0.20` when `realized_vol_20d > 0.60`.
- `0.10` when `realized_vol_20d > 0.40`.
- `0.10` when 20-day return is below `-10%`.
- `0.10` when `close` is more than 30% below 252-day high.

Clamp to `[0.0, 1.0]`.

### Track Record Score

If outcome prior exists:

```text
0.60 * hit_rate_20d + 0.40 * normalized_median_net_return_20d
```

Normalize median net return:

- `-10% -> 0.0`
- `+10% -> 1.0`

If sample size is below 3, cap track-record score at `0.55`.

If outcome prior is missing, use `0.50`.

## 11. Total Score

Total score:

```text
0.30 * momentum_score
0.25 * quality_score
0.20 * regime_score
0.10 * liquidity_score
0.10 * risk_penalty_score
0.05 * track_record_score
```

Round component and total scores to four decimals.

Sort candidates by:

1. `total_score DESC`
2. `momentum_score DESC`
3. `quality_score DESC`
4. `ticker ASC`

## 12. Recommendation Language Boundary

P39 must not use these terms in candidate action fields or Markdown callouts:

```text
buy this
sell this
follow this trade
guaranteed edge
production approved
model promoted
trade now
```

Allowed candidate call-to-action:

```text
research_candidate
monitor_candidate
defer_candidate
```

These are research workflow labels only.

## 13. Output Object

Candidate item fields:

```text
schema_version
run_id
as_of_date
universe_id
ticker
sector
currency
source_date
candidate_status
candidate_category
workflow_action
total_score
component_scores
feature_snapshot
evidence_refs
inclusion_reasons
risk_notes
missing_context
source_hash
created_at
```

Excluded item fields:

```text
ticker
sector
candidate_status
exclusion_reasons
missing_required_fields
source_date
created_at
```

Top-level candidate pool fields:

```text
schema_version
run_id
as_of_date
created_at
universe_id
source
status
candidates
excluded_items
summary
warnings
disclaimer
```

Statuses:

```text
completed
completed_with_warnings
no_candidates
blocked_invalid_input
```

## 14. Persistence

Add two tables.

`candidate_pool_runs`:

```text
run_id
schema_version
as_of_date
created_at
universe_id
source
status
candidate_count
excluded_count
source_hash
warnings_json
summary_json
```

Natural key:

```text
(as_of_date, universe_id, source_hash)
```

`candidate_pool_items`:

```text
item_id
run_id
schema_version
as_of_date
created_at
universe_id
ticker
sector
currency
source_date
candidate_status
candidate_category
workflow_action
rank
total_score
component_scores_json
feature_snapshot_json
evidence_refs_json
inclusion_reasons_json
risk_notes_json
missing_context_json
source_hash
```

Natural key:

```text
(run_id, ticker, source_hash)
```

Persistence must be idempotent:

- Same `(as_of_date, universe_id, source_hash)`: no duplicate run.
- Same ticker and as-of with revised universe data: append a distinguishable run and item rows.

## 15. Source Hash

`source_hash` must be deterministic SHA-256 over canonical JSON containing:

- `schema_version`
- `as_of_date`
- `universe_id`
- `source`
- every ticker row consumed, sorted by ticker
- P37 market-regime source hash when used
- P38 fundamental-quality source hash per ticker when used
- inline outcome prior when used

Middle-row or middle-field changes must produce a different hash.

## 16. Artifacts

Write:

```text
output/governance/YYYY-MM-DD/p39_candidate_pool.json
output/governance/YYYY-MM-DD/p39_candidate_pool.md
```

Markdown must lead with:

1. status and run metadata
2. top candidates table
3. category counts
4. missing-context warnings
5. excluded-item summary
6. disclaimer

Markdown must not contain forbidden trading instructions.

## 17. CLI

Command:

```bash
python -m agent.research_v1.batch_cli candidate-pool-run \
  --app-root /path/to/app \
  --input /path/to/universe.json \
  --as-of-date 2026-04-30 \
  --output-root output/governance \
  --max-candidates 20
```

Arguments:

```text
--input             required JSON universe path
--as-of-date        optional override date YYYY-MM-DD
--output-root       optional, default output/governance, relative to --app-root
--max-candidates    optional positive integer, default 20
```

Exit codes:

- `0` for completed, completed-with-warnings, or no-candidates.
- `2` for invalid path, invalid JSON, invalid date, invalid max-candidates, or invalid input shape.

Printed summary:

```text
Candidate pool status: <status>
Output dir: <path>
Candidate count: <n>
Excluded count: <n>
Top candidate: <ticker or none>
Warning count: <n>
```

## 18. Hard Boundary Test

Add an explicit hard-boundary test asserting P39 does not expose or call:

```text
broker
order
train_model
scheduler
notification
HermesResearchApp
run_research
final_judge
run_governance_runtime
run_recommendation_outcome_tracking
run_market_regime_context
run_fundamental_quality
_extract_thesis_inputs
```

The test must also assert the artifact disclaimer contains:

```text
P39 is candidate-discovery evidence only.
```

## 19. Required Tests

P39 focused tests must cover:

1. Valid universe row computes momentum, liquidity, risk, and total scores.
2. P38 quality report improves quality score and stores evidence refs.
3. Missing P38 quality uses neutral quality and records `missing_fundamental_quality`.
4. P37 regime context affects regime score and stores evidence refs.
5. Missing P37 regime uses neutral regime and records `missing_market_regime_context`.
6. Inline outcome prior affects track-record score.
7. Low liquidity row is excluded and appears under `excluded_items`.
8. Low price row is excluded.
9. Future source-date row is excluded.
10. Missing required fields are surfaced exactly.
11. Candidate category assignment follows deterministic rules.
12. Sorting tie-breakers are deterministic.
13. Source hash changes when a middle universe field changes.
14. Persistence is idempotent for same run natural key.
15. Revised source hash appends a distinguishable run.
16. Artifacts write JSON and Markdown.
17. Markdown does not contain forbidden trading terms.
18. CLI success writes artifacts under `--app-root` when output root is relative.
19. CLI rejects invalid JSON/input shape/date/max-candidates.
20. Hard boundaries are explicit.

## 20. Regression Requirements

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_candidate_pool.py -q
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_batch_cli.py -q -k candidate_pool
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_recommendation_outcomes.py tests/agent/research_v1/test_market_regime_context.py tests/agent/research_v1/test_fundamental_quality.py -q
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_governance_runtime.py tests/agent/research_v1/test_boss_governance_brief.py tests/agent/research_v1/test_signal_family_edge_review.py -q
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_doc_standards.py -q
```

Full P20-P39 chain should be run after implementation, excluding only known host-specific PDF/Futu gaps when necessary.

## 21. Commit Split

Expected implementation commits:

1. `feat: add candidate pool scoring`
2. `feat: persist candidate pool reports`
3. `feat: add candidate pool cli`
4. `docs: document p39 candidate pool`

## 22. Acceptance Criteria

P39 is complete when:

- Candidate scoring is deterministic and action-language safe.
- Excluded rows are preserved in artifacts.
- P37/P38/P36 context is consumed only as read-only evidence.
- Persistence is append-only and idempotent.
- CLI validates inputs and writes artifacts under the correct app root.
- Hard-boundary tests pass.
- P36/P37/P38 regressions pass.
- Doc standards pass.
- No existing research recommendation behavior changes.
