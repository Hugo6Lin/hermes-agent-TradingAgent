# Hermes P42 Boss Co-Pilot Daily Brief Spec

Date: 2026-04-30
Status: Approved for implementation planning
Scope: Standalone boss-facing daily co-pilot brief, read-only aggregation of P36-P41 evidence, append-only artifacts, local CLI, and optional persistence

## 1. Purpose

P42 turns the evidence created by P36-P41 into one daily boss-facing research brief.

P36-P41 now cover realized recommendation outcomes, market regime, fundamental quality, candidate discovery, research memory, and decision-journal guardrails. Those artifacts are useful, but they are still scattered. P42 gives the boss one daily artifact that answers:

```text
What should I review today, what context matters, and where should I slow down?
```

P42 is a research prioritization layer. It is not a trading layer.

## 2. Product Intent

The boss should be able to read one daily brief and quickly see:

- market-regime context
- top research candidates
- ticker-level memory and outcome context
- fundamental-quality concerns
- decision-journal guardrails
- missing or stale evidence
- research priorities for the day
- explicit no-trade-instruction disclaimer

The brief must make the boss faster without making Hermes more autonomous. It may say "review AAPL first because candidate score is high and memory is fresh." It must not say "buy AAPL," "sell AAPL," "follow this trade," or equivalent instructions.

## 3. Non-Goals

P42 must not:

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
- mutate P41 decision-journal entries
- invoke any P36-P41 runtime command
- use LLMs to rank priorities

P42 is deterministic daily co-pilot evidence only.

## 4. Phase Map

### P42-A: Brief Builder

Create `boss_copilot_daily_brief.py` with deterministic aggregation, scoring, status classification, forbidden-language checks, JSON/Markdown artifact writing, and focused tests.

### P42-B: Database Helpers + Optional Persistence

Extend `ResearchDatabase` with latest-as-of read helpers and a `boss_copilot_daily_briefs` table. Persistence must be append-only and idempotent by natural key.

### P42-C: CLI

Add `boss-copilot-brief-run` to `batch_cli.py`. The command reads only existing database evidence, writes artifacts, persists the brief, and prints a summary.

### P42-D: Docs + Regression

Update root and research README files, run P36-P42 focused/adjoining regressions, governance-adjacent regressions, and doc standards.

## 5. Input Contract

P42 CLI arguments:

```bash
python -m agent.research_v1.batch_cli boss-copilot-brief-run \
  --as-of-date 2026-04-30 \
  --output-root output/governance \
  --max-priorities 8
```

Arguments:

```text
--as-of-date       required YYYY-MM-DD
--output-root      optional, default output/governance, relative to --app-root
--max-priorities   optional positive integer, default 8
```

Runtime function:

```python
run_boss_copilot_daily_brief(
    db: ResearchDatabase,
    as_of_date: str,
    output_root: Path,
    max_priorities: int = 8,
) -> dict
```

Invalid date or non-positive `max_priorities` returns CLI exit code `2`.

## 6. Context Inputs

P42 may read these persisted evidence sources:

```text
P36 canonical_recommendation_outcomes
P37 market_regime_snapshots
P38 fundamental_quality_reports
P39 candidate_pool_runs and candidate_pool_items
P40 research_memory_packs
P41 decision_journal_entries
```

Every lookup must be as-of safe:

- only evidence with `as_of_date <= requested as_of_date`
- if multiple same-date rows exist, use latest `created_at DESC`
- add a stable tie-breaker such as ID/hash ascending
- never use future P36 `evaluated_for_date` rows in summaries

P42 must continue when any evidence source is missing. Missing context must be explicit in the brief.

## 7. Brief Status

Statuses:

```text
brief_ready
brief_limited_context
brief_no_candidates
blocked_invalid_input
```

Rules:

- `blocked_invalid_input` for invalid date or invalid `max_priorities`.
- `brief_no_candidates` when no candidate-pool items are found at or before `as_of_date`.
- `brief_limited_context` when candidates exist but any of P37/P38/P40/P41 context is missing for the selected priorities.
- `brief_ready` when candidates exist and required context coverage is present for selected priorities.

The status is about evidence coverage, not trading readiness.

## 8. Research Priority Object

Each priority must include:

```text
rank
ticker
sector
priority_score
priority_band
research_reason
candidate_ref
market_regime_ref
fundamental_quality_ref
memory_ref
decision_guardrail_ref
outcome_snapshot
quality_snapshot
regime_snapshot
memory_snapshot
guardrail_snapshot
missing_context
risk_notes
suggested_research_action
disclaimer
```

Allowed `suggested_research_action` values:

```text
review_research_pack
refresh_missing_context
compare_with_watchlist
defer_until_context_improves
manual_review_before_any_action
```

These are research workflow actions, not trading actions.

## 9. Priority Scoring

Priority scoring must be deterministic and explainable.

Base inputs:

- P39 candidate `total_score`
- P38 fundamental quality
- P40 memory freshness and outcome history
- P41 guardrail severity
- missing context penalty

Suggested score formula:

```text
priority_score =
  0.50 * candidate_total_score
  + 0.20 * fundamental_quality_score
  + 0.15 * memory_score
  + 0.10 * regime_fit_score
  + 0.05 * outcome_score
  - missing_context_penalty
  - guardrail_penalty
```

All components must be clamped to `[0.0, 1.0]`.

Penalties:

```text
missing_context_penalty = min(0.30, 0.05 * missing_context_count)
guardrail_penalty:
  info: 0.00
  caution: 0.03
  slow_down: 0.08
  manual_review: 0.15
```

Bands:

```text
high_priority       score >= 0.75
medium_priority     score >= 0.55 and < 0.75
low_priority        score >= 0.35 and < 0.55
context_blocked     score < 0.35 or manual_review guardrail
```

Sorting:

```text
priority_score DESC, candidate_rank ASC, ticker ASC
```

Manual-review guardrails must not hide a ticker. They must lower score, set band `context_blocked`, and set `suggested_research_action = manual_review_before_any_action`.

## 10. Summary Object

Top-level summary fields:

```text
priority_count
high_priority_count
medium_priority_count
low_priority_count
context_blocked_count
manual_review_count
missing_context_counts
regime_label
regime_confidence
candidate_run_ref
latest_evidence_dates
```

`missing_context_counts` is a deterministic mapping from missing-context key to count.

## 11. Source Hash

`source_hash` must be deterministic SHA-256 over canonical JSON containing:

- `schema_version`
- `as_of_date`
- `max_priorities`
- selected candidate run ID and source hash
- selected market-regime snapshot ID/hash
- selected priority candidate item IDs and source hashes
- selected P38 report IDs/source hashes
- selected P40 pack IDs/source hashes
- selected P41 journal IDs/source hashes

Changing any selected upstream evidence must change the P42 source hash.

## 12. Persistence

Add `boss_copilot_daily_briefs`:

```text
brief_id
schema_version
as_of_date
created_at
status
priority_count
manual_review_count
source_hash
brief_json
```

Natural key:

```text
(as_of_date, source_hash)
```

Same source hash is idempotent. Revised upstream evidence appends a distinguishable row.

## 13. Artifacts

Write:

```text
output/governance/YYYY-MM-DD/p42_boss_copilot_daily_brief.json
output/governance/YYYY-MM-DD/p42_boss_copilot_daily_brief.md
```

Markdown sections:

1. Run metadata
2. Market context
3. Research priorities
4. Guardrails and slow-down notes
5. Evidence coverage and missing context
6. Suggested research workflow
7. Disclaimer

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
place order
execute trade
```

Allowed phrase:

```text
research priority
```

## 14. CLI Output

Successful CLI output:

```text
Boss co-pilot brief status: <status>
Output dir: <path>
Priority count: <n>
High priority count: <n>
Manual review count: <n>
Missing context count: <n>
```

Exit codes:

- `0` for `brief_ready`, `brief_limited_context`, or `brief_no_candidates`.
- `2` for `blocked_invalid_input`.

## 15. Hard Boundary Test

Add an explicit test asserting P42 does not expose or call:

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
run_decision_journal_guardrails
_extract_thesis_inputs
```

The disclaimer must contain:

```text
P42 is daily research-priority evidence only.
```

## 16. Required Tests

Focused P42 tests must cover:

1. Empty candidate context returns `brief_no_candidates`.
2. Candidate plus complete context returns `brief_ready`.
3. Missing P37 context returns `brief_limited_context`.
4. Missing P38/P40/P41 context is surfaced in `missing_context`.
5. Manual-review P41 guardrail forces `context_blocked`.
6. Slow-down P41 guardrail lowers score but keeps candidate visible.
7. Priority sorting is deterministic.
8. Source hash changes when selected candidate source hash changes.
9. Source hash changes when selected memory source hash changes.
10. Source hash is stable for identical input.
11. Markdown writer rejects forbidden trading language.
12. Persistence is idempotent for same natural key.
13. Revised source hash appends a new brief row.
14. CLI success writes under app root for relative output root.
15. CLI rejects invalid date.
16. CLI rejects non-positive max priorities.
17. Hard boundaries are explicit.

## 17. Regression Requirements

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_boss_copilot_daily_brief.py -q
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_batch_cli.py -q -k "boss_copilot or boss-copilot"
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_recommendation_outcomes.py tests/agent/research_v1/test_market_regime_context.py tests/agent/research_v1/test_fundamental_quality.py tests/agent/research_v1/test_candidate_pool.py tests/agent/research_v1/test_research_memory_pack.py tests/agent/research_v1/test_decision_journal_guardrails.py -q
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_governance_runtime.py tests/agent/research_v1/test_boss_governance_brief.py tests/agent/research_v1/test_signal_family_edge_review.py -q
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_doc_standards.py -q
```

Run the full P20-P42 chain after implementation. Host-specific PDF/Futu gaps may be reported separately if unrelated.

## 18. Commit Split

Expected implementation commits:

1. `feat: add boss copilot daily brief`
2. `feat: persist boss copilot briefs`
3. `feat: add boss copilot brief cli`
4. `docs: document p42 boss copilot brief`

## 19. Acceptance Criteria

P42 is complete when:

- It produces deterministic daily research-priority briefs from existing P36-P41 evidence.
- It never creates or changes trading recommendations.
- It handles missing upstream evidence explicitly.
- It is as-of safe and never uses future evidence.
- Source hash changes when selected upstream evidence changes.
- Persistence is append-only and idempotent.
- CLI validates inputs and writes artifacts under the correct app root.
- Forbidden trading language is blocked.
- P36-P41 regressions pass.
- Governance-adjacent and doc standards pass.
