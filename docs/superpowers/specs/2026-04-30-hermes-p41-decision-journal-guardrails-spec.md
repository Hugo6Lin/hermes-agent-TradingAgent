# Hermes P41 Decision Journal Guardrails Spec

Date: 2026-04-30
Status: Approved for implementation planning
Scope: Standalone boss decision journal entries, behavioral guardrail reports, append-only persistence, local CLI, and boss-readable artifacts

## 1. Purpose

P41 gives Hermes an explicit emotional-decision-control layer.

P36-P40 help Hermes remember outcomes, regime, fundamentals, candidates, and prior ticker context. P41 turns that context into a deterministic decision journal and behavioral guardrail report so the boss can see when a contemplated action may be affected by recency bias, overtrading, concentration, stale thesis, duplicate thesis, or missing evidence.

P41 answers:

```text
Before the boss acts on an idea, what context should be recorded, and what behavioral guardrails should be visible?
```

P41 is not a trading control system. It does not block the boss, approve action, place orders, or alter Hermes recommendations. It records and surfaces guardrails only.

## 2. Product Intent

Hermes should help the boss spend less time fighting impulsive decision patterns. The system should make prior context visible at the moment of consideration:

- what the boss is considering
- why the boss says they are considering it
- current urgency and confidence
- recent PnL or emotional state if supplied
- prior Hermes memory for the same ticker
- candidate/research/outcome context
- deterministic guardrail flags
- cooling-off suggestion when risk is high

The output is a journal entry and guardrail report, not an order ticket.

## 3. Non-Goals

P41 must not:

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
- mutate `JudgeInputPacket`
- change `RoleWeightConfig`
- change `_extract_thesis_inputs()`
- change `ThesisEngine`
- mutate P36 outcome rows
- mutate P37 market-regime snapshots
- mutate P38 quality reports
- mutate P39 candidate pools
- mutate P40 memory packs
- use LLMs to decide guardrail severity

P41 is deterministic behavioral evidence only.

## 4. Phase Map

### P41-A: Journal Entry + Guardrail Engine

Create a focused module that validates a contemplated decision, normalizes context, reads optional P40 memory, and produces deterministic guardrail flags.

### P41-B: Persistence + Artifacts

Persist append-only journal entries and write JSON/Markdown artifacts under `output/governance/YYYY-MM-DD/`.

### P41-C: CLI

Add a local `decision-journal-run` command that reads a JSON input file, builds entries, persists them, writes artifacts, and prints a summary.

### P41-D: Docs + Regression

Update docs and run focused, P36-P40, governance-adjacent, and doc-standard regression tests.

## 5. Input Contract

P41 consumes an explicit JSON file. Runtime v1 does not prompt interactively.

Input shape:

```json
{
  "as_of_date": "2026-04-30",
  "source": "manual_boss_check",
  "decisions": [
    {
      "ticker": "AAPL",
      "contemplated_action": "research_candidate",
      "decision_intent": "review_before_action",
      "stated_reason": "Strong candidate score and product-cycle thesis",
      "boss_confidence": 0.82,
      "urgency": "high",
      "time_pressure": "same_day",
      "recent_pnl_state": "drawdown",
      "position_context": {
        "current_position_pct": 0.08,
        "sector_exposure_pct": 0.32,
        "cash_available_pct": 0.18
      },
      "manual_notes": ["Need to verify concentration risk before acting"]
    }
  ]
}
```

Required decision fields:

```text
ticker
contemplated_action
decision_intent
stated_reason
boss_confidence
urgency
```

Optional fields:

```text
time_pressure
recent_pnl_state
position_context
manual_notes
```

Allowed `contemplated_action` values:

```text
research_candidate
monitor_candidate
defer_candidate
review_existing_signal
journal_only
```

Allowed `decision_intent` values:

```text
review_before_action
postpone_decision
compare_with_prior
journal_only
```

P41 must reject trade verbs as contemplated actions, including `buy`, `sell`, `short`, `call`, `put`, and `trade_now`.

## 6. Context Inputs

P41 may read P40 memory packs at or before `as_of_date` for each ticker. If no P40 pack exists, P41 must continue with `missing_memory_pack`.

Required P40 fields when available:

```text
memory_status
latest_research
outcome_summary
candidate_history
quality_context
regime_context
watchlist_context
risk_memory
missing_context
source_hash
```

P41 must not mutate P40 memory packs.

## 7. Guardrail Flags

P41 guardrails are deterministic flags.

Flag IDs:

```text
high_urgency_high_confidence
time_pressure_same_day
recent_drawdown_context
position_concentration_high
sector_concentration_high
cash_constraint_visible
duplicate_recent_thesis
negative_outcome_memory
insufficient_outcome_memory
quality_red_flags_present
stale_research_memory
missing_memory_pack
missing_fundamental_quality
missing_market_regime_context
manual_review_required
```

Severity:

```text
info
caution
slow_down
manual_review
```

Severity rules:

- `manual_review` if any of:
  - position concentration >= 0.15
  - sector exposure >= 0.40
  - P40 risk memory includes `quality_red_flags_present`
  - contemplated action is invalid
- `slow_down` if any of:
  - urgency is `high` and boss confidence >= 0.80
  - time pressure is `same_day`
  - recent PnL state is `drawdown`
  - P40 risk memory includes `negative_outcome_history` or `stale_research_context`
- `caution` if any missing context exists.
- `info` otherwise.

The entry-level severity is the maximum severity among all flags.

## 8. Cooling-Off Suggestion

P41 may emit a cooling-off suggestion, but it must not block action.

Values:

```text
none
recheck_after_30_minutes
recheck_next_session
manual_review_before_action
```

Rules:

- `manual_review_before_action` for `manual_review` severity.
- `recheck_next_session` for `slow_down` with `recent_drawdown_context` or `time_pressure_same_day`.
- `recheck_after_30_minutes` for other `slow_down`.
- `none` for `info` or `caution`.

Artifact wording must say suggestion only, never instruction.

## 9. Output Object

Journal entry fields:

```text
schema_version
journal_id
as_of_date
created_at
ticker
contemplated_action
decision_intent
stated_reason
boss_confidence
urgency
time_pressure
recent_pnl_state
position_context
manual_notes
memory_ref
guardrail_flags
severity
cooling_off_suggestion
missing_context
source_hash
disclaimer
```

Top-level run fields:

```text
schema_version
as_of_date
created_at
source
status
entries
summary
warnings
disclaimer
```

Statuses:

```text
completed
completed_with_warnings
blocked_invalid_input
```

## 10. Source Hash

`source_hash` must be deterministic SHA-256 over canonical JSON containing:

- `schema_version`
- `as_of_date`
- normalized decision input
- selected P40 memory pack source hash
- selected P40 pack ID

Changing the boss journal input or selected P40 memory source must change the hash.

## 11. Persistence

Add `decision_journal_entries`:

```text
journal_id
schema_version
as_of_date
created_at
ticker
contemplated_action
decision_intent
boss_confidence
urgency
severity
cooling_off_suggestion
memory_pack_id
source_hash
entry_json
```

Natural key:

```text
(ticker, as_of_date, contemplated_action, source_hash)
```

Same source hash is idempotent. Revised boss input or revised memory source appends a distinguishable entry.

## 12. Artifacts

Write:

```text
output/governance/YYYY-MM-DD/p41_decision_journal.json
output/governance/YYYY-MM-DD/p41_decision_journal.md
```

Markdown sections:

1. run metadata
2. journal summary table
3. guardrail flags
4. cooling-off suggestions
5. missing context
6. disclaimer

Forbidden terms in Markdown:

```text
buy this now
sell this now
follow this trade
guaranteed edge
production approved
model promoted
trade now
order ticket
```

Allowed phrase:

```text
behavioral guardrail only
```

## 13. CLI

Command:

```bash
python -m agent.research_v1.batch_cli decision-journal-run \
  --input /path/to/decision_journal.json \
  --as-of-date 2026-04-30 \
  --output-root output/governance
```

Arguments:

```text
--input        required JSON decision file
--as-of-date   optional override date YYYY-MM-DD
--output-root  optional, default output/governance, relative to --app-root
```

Exit codes:

- `0` for completed or completed-with-warnings.
- `2` for invalid path, invalid JSON, invalid date, empty decisions, invalid decision item, or forbidden contemplated action.

Printed summary:

```text
Decision journal status: <status>
Output dir: <path>
Entry count: <n>
Manual review count: <n>
Slow down count: <n>
Warning count: <n>
```

## 14. Hard Boundary Test

Add an explicit hard-boundary test asserting P41 does not expose or call:

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
run_research_memory_pack
_extract_thesis_inputs
```

The disclaimer must contain:

```text
P41 is behavioral guardrail evidence only.
```

## 15. Required Tests

Focused P41 tests must cover:

1. Valid decision builds a journal entry.
2. Ticker normalization uppercases and trims.
3. Forbidden trade action is blocked.
4. High urgency plus high confidence emits `high_urgency_high_confidence`.
5. Same-day time pressure emits `time_pressure_same_day`.
6. Drawdown state emits `recent_drawdown_context`.
7. High position concentration produces `manual_review`.
8. High sector exposure produces `manual_review`.
9. Missing P40 memory emits `missing_memory_pack`.
10. P40 risk memory propagates stale/quality/outcome guardrails.
11. Cooling-off suggestion follows severity.
12. Source hash changes when boss input changes.
13. Source hash changes when memory source hash changes.
14. Persistence is idempotent for same natural key.
15. Revised source hash appends a new entry.
16. Artifacts write JSON and Markdown.
17. Markdown avoids forbidden trading language.
18. CLI success writes under app root for relative output root.
19. CLI rejects invalid date/JSON/empty decisions/forbidden action.
20. Hard boundaries are explicit.

## 16. Regression Requirements

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_decision_journal_guardrails.py -q
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_batch_cli.py -q -k "decision_journal or decision-journal"
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_recommendation_outcomes.py tests/agent/research_v1/test_market_regime_context.py tests/agent/research_v1/test_fundamental_quality.py tests/agent/research_v1/test_candidate_pool.py tests/agent/research_v1/test_research_memory_pack.py -q
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_governance_runtime.py tests/agent/research_v1/test_boss_governance_brief.py tests/agent/research_v1/test_signal_family_edge_review.py -q
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_doc_standards.py -q
```

Full P20-P41 chain should be run after implementation, excluding only known host-specific PDF/Futu gaps when necessary.

## 17. Commit Split

Expected implementation commits:

1. `feat: add decision journal guardrails`
2. `feat: persist decision journal entries`
3. `feat: add decision journal cli`
4. `docs: document p41 decision journal`

## 18. Acceptance Criteria

P41 is complete when:

- Journal entries are deterministic and read-only with respect to all prior phases.
- Guardrails are deterministic and explainable.
- Missing memory context is explicit.
- Persistence is append-only and idempotent.
- CLI validates inputs and writes artifacts under the correct app root.
- Hard-boundary tests pass.
- P36-P40 regressions pass.
- Doc standards pass.
- No existing research recommendation behavior changes.
