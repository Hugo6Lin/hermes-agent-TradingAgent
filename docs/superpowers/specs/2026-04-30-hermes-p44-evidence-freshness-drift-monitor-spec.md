# Hermes P44 Evidence Freshness & Drift Monitor Spec

Date: 2026-04-30
Status: Approved for implementation planning
Scope: Standalone read-only freshness/drift monitor for P36-P43 evidence, append-only monitor artifacts, local CLI, and documentation

## 1. Purpose

P44 monitors whether Hermes' co-pilot evidence is fresh, complete, and stable enough to trust for daily review.

P36-P43 produce many useful artifacts. P43 makes them navigable. P44 answers the next operational question:

```text
Which evidence is stale, missing, unstable, or changing too often, and what should a human refresh or inspect next?
```

P44 is a monitor. It does not refresh evidence, schedule jobs, notify anyone, or approve decisions.

## 2. Product Intent

The boss and reviewer should see:

- latest evidence date for each phase
- phase-level freshness status
- missing required daily evidence
- source-hash churn across recent runs
- repeated missing-context patterns
- invalid artifact warnings from P43
- suggested manual follow-up actions

The output is an evidence health report, not a trade report.

## 3. Non-Goals

P44 must not:

- auto-trade
- send broker orders
- approve production adoption
- mutate production calibration config
- train models
- schedule jobs
- send notifications
- start a server
- call `HermesResearchApp.run()`
- call `run_research`
- call `final_judge`
- create `CanonicalSignal`
- create `CanonicalReport`
- mutate `JudgeInputPacket`
- invoke P36-P43 runtime commands
- mutate P36-P43 evidence
- rewrite existing P36-P43 artifact files
- use LLMs to classify drift

P44 is deterministic read-only evidence monitoring only.

## 4. Phase Map

### P44-A: Freshness + Drift Model

Create `evidence_freshness_drift_monitor.py` with deterministic phase coverage, freshness, churn, and missing-context calculations.

### P44-B: Artifact + Persistence Layer

Write JSON/Markdown artifacts and persist append-only monitor reports.

### P44-C: CLI

Add `evidence-monitor-run` to `batch_cli.py`.

### P44-D: Docs + Regression

Update docs and run P36-P44, governance-adjacent, CLI, and doc-standard regressions.

## 5. Input Contract

CLI:

```bash
python -m agent.research_v1.batch_cli evidence-monitor-run \
  --as-of-date 2026-04-30 \
  --lookback-days 14 \
  --freshness-days 3 \
  --governance-root output/governance \
  --output-root output/governance
```

Arguments:

```text
--as-of-date        required YYYY-MM-DD
--lookback-days     optional positive integer, default 14
--freshness-days    optional positive integer, default 3
--governance-root   optional, default output/governance, relative to --app-root
--output-root       optional, default output/governance, relative to --app-root
```

Runtime:

```python
run_evidence_freshness_drift_monitor(
    db: ResearchDatabase,
    governance_root: Path,
    output_root: Path,
    as_of_date: str,
    lookback_days: int = 14,
    freshness_days: int = 3,
) -> dict
```

Invalid date, non-positive lookback, non-positive freshness, or non-directory governance root returns `blocked_invalid_input`.

## 6. Evidence Sources

P44 may read:

```text
canonical_recommendation_outcomes
market_regime_snapshots
fundamental_quality_reports
candidate_pool_runs
candidate_pool_items
research_memory_packs
decision_journal_entries
boss_copilot_daily_briefs
copilot_console_indexes
output/governance/YYYY-MM-DD artifacts
```

P44 must not call any P36-P43 runtime command.

## 7. Phase Monitor Set

P44 monitors these phases:

```text
P36 recommendation_outcomes
P37 market_regime
P38 fundamental_quality
P39 candidate_pool
P40 research_memory
P41 decision_journal
P42 boss_copilot_brief
P43 copilot_console_index
```

For each phase, produce:

```text
phase_id
phase_name
latest_evidence_date
latest_created_at
latest_source_hash
row_count
artifact_count
freshness_status
churn_status
coverage_status
warnings
recommended_action
```

## 8. Freshness Status

Freshness statuses:

```text
fresh
stale
missing
invalid
```

Rules:

- `missing` if no DB rows and no known artifact found in the lookback window.
- `invalid` if any known artifact for the latest day has invalid JSON.
- `fresh` if latest evidence date is within `freshness_days` calendar days of `as_of_date`.
- `stale` otherwise.

Freshness uses calendar days, not trading days.

## 9. Churn Status

Churn detects frequent source-hash changes in the lookback window.

Statuses:

```text
stable
changed
high_churn
unknown
```

Rules:

- `unknown` if fewer than two source hashes are available.
- `stable` if exactly one unique source hash appears.
- `changed` if two unique source hashes appear.
- `high_churn` if three or more unique source hashes appear.

P44 does not decide whether churn is good or bad. It only makes it visible.

## 10. Coverage Status

Coverage statuses:

```text
complete
partial
missing
invalid
```

Rules:

- `missing` if phase has no rows/artifacts in lookback.
- `invalid` if latest known artifact has invalid JSON.
- `complete` if latest day includes the phase's expected JSON artifact.
- `partial` otherwise.

Expected JSON artifacts:

```text
P36 p36_recommendation_outcomes.json
P37 p37_market_regime_snapshot.json
P38 p38_fundamental_quality.json
P39 p39_candidate_pool.json
P40 p40_research_memory_pack.json
P41 p41_decision_journal.json
P42 p42_boss_copilot_daily_brief.json
P43 p43_copilot_console_index.json
```

## 11. Overall Status

Statuses:

```text
monitor_green
monitor_yellow
monitor_red
blocked_invalid_input
```

Rules:

- `blocked_invalid_input` for invalid input.
- `monitor_red` if any phase is `missing` or `invalid`.
- `monitor_yellow` if any phase is `stale` or `high_churn`.
- `monitor_green` otherwise.

Status is evidence-health only; it does not approve trading or production adoption.

## 12. Recommended Actions

Allowed recommended actions:

```text
none
inspect_invalid_artifact
collect_missing_evidence
refresh_stale_evidence
review_source_hash_churn
review_missing_context_pattern
```

Actions are manual review suggestions only. They must never schedule, notify, place orders, or call phase runtimes.

## 13. Missing Context Patterns

P44 should aggregate missing-context keys from:

- P40 `missing_context_json`
- P41 `entry_json.missing_context`
- P42 `brief_json.summary.missing_context_counts`
- P43 `index_json.days[].missing_artifacts`

Output:

```text
missing_context_patterns: [
  {"key": "missing_fundamental_quality", "count": 3, "sources": ["P40", "P42"]}
]
```

The list must be sorted by count descending, then key ascending.

## 14. Source Hash

`source_hash` must be deterministic SHA-256 over canonical JSON containing:

- `schema_version`
- `as_of_date`
- `lookback_days`
- `freshness_days`
- phase monitor summaries
- missing context patterns
- latest selected upstream source hashes

Changing upstream evidence selected by P44 must change P44 source hash.

## 15. Persistence

Add `evidence_freshness_drift_reports`:

```text
report_id
schema_version
as_of_date
created_at
status
lookback_days
freshness_days
phase_count
red_count
yellow_count
source_hash
report_json
```

Natural key:

```text
(as_of_date, lookback_days, freshness_days, source_hash)
```

Same source hash is idempotent. Revised upstream evidence appends a distinguishable report row.

## 16. Artifacts

Write:

```text
output/governance/YYYY-MM-DD/p44_evidence_freshness_drift_monitor.json
output/governance/YYYY-MM-DD/p44_evidence_freshness_drift_monitor.md
```

Markdown sections:

1. Monitor metadata
2. Overall status
3. Phase freshness table
4. Churn table
5. Missing context patterns
6. Recommended manual follow-up actions
7. Disclaimer

Forbidden rendered terms:

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

Required disclaimer:

```text
P44 is evidence freshness and drift monitoring only. It does not refresh evidence, schedule jobs, send notifications, recommend trades, place orders, or mutate research decisions.
```

If needed to avoid forbidden-term checks, use `submit orders` instead of `place orders` while preserving the same meaning.

## 17. CLI Output

Successful CLI output:

```text
Evidence monitor status: <status>
Output dir: <path>
Phase count: <n>
Red count: <n>
Yellow count: <n>
Missing context pattern count: <n>
```

Exit codes:

- `0` for `monitor_green`, `monitor_yellow`, or `monitor_red`.
- `2` for `blocked_invalid_input`.

## 18. Hard Boundary Test

Add a hard-boundary test asserting P44 does not expose or call:

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
run_boss_copilot_daily_brief
run_copilot_console_index
_extract_thesis_inputs
```

## 19. Required Tests

Focused P44 tests must cover:

1. Empty DB/artifact window returns `monitor_red` with missing phases.
2. Complete fresh evidence returns `monitor_green`.
3. Stale evidence returns `monitor_yellow`.
4. Invalid artifact JSON returns `monitor_red`.
5. Three unique source hashes produce `high_churn`.
6. Missing context patterns aggregate from P40/P42/P43 payloads.
7. Source hash changes when upstream latest source hash changes.
8. Source hash is stable for identical input.
9. Persistence is idempotent for same natural key.
10. Revised source hash appends a new row.
11. Writer emits JSON and Markdown.
12. Markdown rejects forbidden trading language.
13. Runtime rejects invalid date.
14. Runtime rejects non-positive lookback/freshness.
15. CLI success writes under app root for relative output root.
16. CLI rejects invalid date.
17. CLI rejects non-positive lookback/freshness.
18. Hard boundaries are explicit.

## 20. Regression Requirements

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_evidence_freshness_drift_monitor.py -q
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_batch_cli.py -q -k "evidence_monitor or evidence-monitor"
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_recommendation_outcomes.py tests/agent/research_v1/test_market_regime_context.py tests/agent/research_v1/test_fundamental_quality.py tests/agent/research_v1/test_candidate_pool.py tests/agent/research_v1/test_research_memory_pack.py tests/agent/research_v1/test_decision_journal_guardrails.py tests/agent/research_v1/test_boss_copilot_daily_brief.py tests/agent/research_v1/test_copilot_console_index.py -q
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_governance_runtime.py tests/agent/research_v1/test_boss_governance_brief.py tests/agent/research_v1/test_signal_family_edge_review.py -q
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_doc_standards.py -q
```

Run the full P20-P44 chain after implementation. Host-specific PDF/Futu gaps may be reported separately if unrelated.

## 21. Commit Split

Expected implementation commits:

1. `feat: add evidence freshness drift monitor`
2. `feat: persist evidence freshness drift reports`
3. `feat: add evidence monitor cli`
4. `docs: document p44 evidence monitor`

## 22. Acceptance Criteria

P44 is complete when:

- It monitors P36-P43 freshness, coverage, churn, and missing context.
- It never invokes prior phase runtimes.
- It never mutates prior phase evidence.
- It validates runtime and CLI inputs.
- It writes append-only JSON/Markdown monitor artifacts.
- It persists idempotent monitor reports.
- It blocks forbidden trading language.
- P36-P43 regressions pass.
- Governance-adjacent and doc standards pass.
