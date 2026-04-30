# Hermes P46 Controlled Evidence Refresh Planner Spec

Date: 2026-04-30
Scope: Dry-run evidence refresh planning from P44 freshness/drift and P45 market-data readiness, append-only plan artifacts, local CLI, and documentation
Branch: `codex/quant-governance-p20-p30`

## 1. Purpose

P44 tells Hermes which evidence is missing, stale, invalid, or high-churn. P45 tells Hermes whether the Futu market-data source is actually usable. P46 answers the next operational question:

```text
Given the current evidence-health and market-data-readiness state, which evidence should a human refresh next, what is safe to refresh, and what is blocked?
```

P46 is a controlled refresh planner. It does not refresh evidence. It produces a deterministic dry-run plan that a human or a future explicitly-approved phase can inspect.

## 2. Product Intent

The boss/reviewer should see:

- which phases need evidence refresh;
- why each refresh is recommended or blocked;
- whether Futu readiness allows market-data-dependent refreshes;
- priority ordering across P36-P43 evidence;
- manual commands the operator could run later;
- clear disclaimers that no refresh was executed.

P46 turns P44/P45 into an execution-aware checklist without crossing into execution.

## 3. Non-Goals And Hard Boundaries

P46 must not:

- call Futu or any market-data provider;
- call P36-P45 runtime functions;
- run `outcome-run`, `market-regime-run`, `fundamental-quality-run`, `candidate-pool-run`, `research-memory-pack-run`, `decision-journal-run`, `boss-copilot-brief-run`, `copilot-console-index-run`, `evidence-monitor-run`, or `market-data-readiness-run`;
- mutate P36-P45 evidence;
- rewrite existing artifacts;
- schedule refresh jobs;
- send notifications;
- start a server/viewer;
- auto-trade;
- send broker orders;
- approve production adoption;
- mutate production config;
- train models;
- call `HermesResearchApp.run()`;
- call `final_judge`;
- create `CanonicalSignal` or `CanonicalReport`;
- mutate `JudgeInputPacket`;
- use LLMs to rank refreshes.

P46 may read persisted P44/P45 reports and existing artifact JSON files.

## 4. Phase Map

### P46-A: Refresh Planner Model

Create `evidence_refresh_planner.py` with deterministic plan item creation, dependency checks, priority scoring, source hashing, and artifact writing.

### P46-B: Persistence Layer

Persist append-only refresh plans in `evidence_refresh_plans`.

### P46-C: CLI

Add `evidence-refresh-plan-run` to `batch_cli.py`.

### P46-D: Docs + Regression

Update docs and run P36-P46, governance-adjacent, CLI, and doc-standard regressions.

## 5. Input Contract

CLI:

```bash
python -m agent.research_v1.batch_cli evidence-refresh-plan-run \
  --as-of-date 2026-04-30 \
  --lookback-days 14 \
  --max-items 12 \
  --governance-root output/governance \
  --output-root output/governance
```

Arguments:

```text
--as-of-date        required YYYY-MM-DD
--lookback-days     optional positive integer, default 14
--max-items         optional positive integer, default 12
--governance-root   optional, default output/governance, relative to --app-root
--output-root       optional, default output/governance, relative to --app-root
```

Runtime:

```python
run_evidence_refresh_planner(
    db: ResearchDatabase,
    governance_root: Path,
    output_root: Path,
    as_of_date: str,
    lookback_days: int = 14,
    max_items: int = 12,
) -> dict
```

Invalid date, non-positive lookback, non-positive max-items, or non-directory governance root returns `blocked_invalid_input`.

## 6. Evidence Inputs

P46 may read:

```text
evidence_freshness_drift_reports
market_data_readiness_reports
output/governance/YYYY-MM-DD/p44_evidence_freshness_drift_monitor.json
output/governance/YYYY-MM-DD/p45_market_data_readiness.json
```

P46 should prefer the latest persisted P44/P45 report at or before `as_of_date`.

If DB rows are absent, P46 may load artifact files from `governance_root` at or before `as_of_date`.

P46 must not call P44/P45 runtimes to create missing reports.

## 7. Planned Refresh Targets

P46 may plan refreshes for these phase outputs:

```text
P36 recommendation_outcomes
P37 market_regime
P38 fundamental_quality
P39 candidate_pool
P40 research_memory
P41 decision_journal
P42 boss_copilot_brief
P43 copilot_console_index
P44 evidence_freshness_drift_monitor
P45 market_data_readiness
```

P46 does not refresh itself in v1.

## 8. Dependency Rules

Market-data-dependent phases:

```text
P36 recommendation_outcomes
P37 market_regime
P39 candidate_pool
P42 boss_copilot_brief
```

These are `blocked_provider_unavailable` unless latest P45 status is:

```text
provider_ready
provider_degraded
```

If P45 is `provider_degraded`, market-data-dependent items may be `refresh_candidate` but must include warning:

```text
market_data_provider_degraded
```

Non-market-data phases:

```text
P38 fundamental_quality
P40 research_memory
P41 decision_journal
P43 copilot_console_index
P44 evidence_freshness_drift_monitor
P45 market_data_readiness
```

These do not require Futu readiness.

P44 refresh depends on stale/missing P44 itself or changed upstream evidence.

P45 refresh depends on stale/missing/degraded/unavailable P45 itself.

## 9. Plan Item Schema

Each plan item:

```text
item_id
phase_id
phase_name
artifact_name
plan_status
priority
priority_score
reason_codes
blocking_reasons
warnings
manual_command
required_inputs
latest_evidence_date
latest_source_hash
source_refs
```

Allowed `plan_status`:

```text
refresh_candidate
blocked_missing_monitor
blocked_provider_unavailable
blocked_invalid_artifact
blocked_missing_inputs
defer_no_action
```

Allowed `priority`:

```text
critical
high
medium
low
none
```

## 10. Reason Codes

Allowed reason codes:

```text
freshness_missing
freshness_stale
freshness_invalid
coverage_missing
coverage_partial
coverage_invalid
churn_high
missing_context_pattern
provider_ready
provider_degraded
provider_unavailable
provider_not_tested_live
monitor_missing
manual_review_required
```

Reason codes must be deterministic and sorted.

## 11. Priority Scoring

Base scores:

```text
freshness_invalid      +100
coverage_invalid       +100
freshness_missing       +90
coverage_missing        +80
freshness_stale         +60
coverage_partial        +45
churn_high              +35
missing_context_pattern +20
provider_degraded       -15
provider_unavailable    blocked
provider_not_tested_live blocked for market-data phases
```

Priority:

```text
critical >= 100
high      70-99
medium    40-69
low       1-39
none      0
```

Sort items by:

```text
plan_status group, priority_score DESC, phase_id ASC
```

Status group order:

```text
refresh_candidate
blocked_invalid_artifact
blocked_provider_unavailable
blocked_missing_monitor
blocked_missing_inputs
defer_no_action
```

## 12. Manual Commands

Plan items should include suggested manual commands. These are strings only and must not be executed.

Examples:

```text
P36: python -m agent.research_v1.batch_cli outcome-run --as-of-date YYYY-MM-DD
P37: python -m agent.research_v1.batch_cli market-regime-run --as-of-date YYYY-MM-DD
P38: python -m agent.research_v1.batch_cli fundamental-quality-run --as-of-date YYYY-MM-DD --input <path>
P39: python -m agent.research_v1.batch_cli candidate-pool-run --as-of-date YYYY-MM-DD --universe <path>
P40: python -m agent.research_v1.batch_cli research-memory-run --as-of-date YYYY-MM-DD --ticker <ticker>
P41: python -m agent.research_v1.batch_cli decision-journal-run --as-of-date YYYY-MM-DD --input <path>
P42: python -m agent.research_v1.batch_cli boss-copilot-brief-run --as-of-date YYYY-MM-DD
P43: python -m agent.research_v1.batch_cli copilot-console-index-run --as-of-date YYYY-MM-DD
P44: python -m agent.research_v1.batch_cli evidence-monitor-run --as-of-date YYYY-MM-DD
P45: python -m agent.research_v1.batch_cli market-data-readiness-run --as-of-date YYYY-MM-DD --live
```

Commands may contain placeholders like `<path>` or `<ticker>` when P46 lacks concrete input. Those placeholders must be explicit and cause `blocked_missing_inputs` if the phase cannot be refreshed from current context.

## 13. Overall Status

Allowed report statuses:

```text
refresh_plan_ready
refresh_plan_blocked
refresh_plan_noop
blocked_invalid_input
```

Rules:

- `blocked_invalid_input` for invalid runtime input.
- `refresh_plan_ready` when at least one item is `refresh_candidate`.
- `refresh_plan_blocked` when no item is refreshable and at least one item is blocked.
- `refresh_plan_noop` when all items are `defer_no_action`.

## 14. Source Hash

`source_hash` must be deterministic SHA-256 over canonical JSON containing:

- schema version;
- as-of date;
- lookback days;
- max items;
- selected P44 report id/source hash/status;
- selected P45 report id/source hash/status;
- plan items with status/reasons/commands;
- missing input warnings.

Same inputs should be idempotent. Revised P44/P45 evidence or changed plan items should append a new P46 report.

## 15. Persistence

Add table:

```text
evidence_refresh_plans
```

Columns:

```text
plan_id TEXT PRIMARY KEY
schema_version TEXT NOT NULL
as_of_date TEXT NOT NULL
created_at TEXT NOT NULL
status TEXT NOT NULL
lookback_days INTEGER NOT NULL
max_items INTEGER NOT NULL
candidate_count INTEGER NOT NULL
blocked_count INTEGER NOT NULL
source_hash TEXT NOT NULL
plan_json TEXT NOT NULL
```

Natural key:

```text
(as_of_date, lookback_days, max_items, source_hash)
```

## 16. Artifact Output

Write:

```text
output/governance/YYYY-MM-DD/p46_evidence_refresh_plan.json
output/governance/YYYY-MM-DD/p46_evidence_refresh_plan.md
```

JSON must include:

```text
schema_version
plan_id
as_of_date
created_at
status
lookback_days
max_items
selected_monitor
selected_provider_readiness
items
summary
source_hash
disclaimer
```

Markdown must include:

- status;
- selected P44/P45 source refs;
- refresh candidate table;
- blocked item table;
- missing input notes;
- disclaimer.

## 17. Disclaimer

Every artifact must include:

```text
P46 is a dry-run evidence refresh planner only. It does not refresh evidence, call market-data providers, submit orders, approve production adoption, train models, schedule jobs, or mutate research decisions.
```

Forbidden rendered terms:

```text
buy this now
sell this now
follow this trade
guaranteed edge
production approved
model promoted
execute trade
place order
unlock_trade
```

Use "submit orders" instead of "place orders" in disclaimers.

## 18. Tests

Focused tests should cover:

1. Missing P44 monitor produces `blocked_missing_monitor`.
2. Missing P45 provider readiness blocks market-data phases.
3. P45 `provider_unavailable` blocks P36/P37/P39/P42.
4. P45 `provider_ready` allows stale P36/P37 refresh candidates.
5. P45 `provider_degraded` allows candidates with warning.
6. Invalid P44 artifact phase produces `blocked_invalid_artifact`.
7. High churn produces `review_source_hash_churn` reason and medium/low priority.
8. Missing context pattern adds reason to affected phase.
9. P38/P40/P41/P43 do not require provider readiness.
10. P44/P45 own refreshes are planned when stale/missing.
11. Source hash changes when selected P44 or P45 hash changes.
12. Persistence is idempotent for identical report.
13. Revised source hash appends.
14. Runtime rejects invalid date.
15. Runtime rejects non-directory governance root.
16. CLI returns 0 for ready/noop/blocked plan, 2 for invalid input.
17. Markdown includes candidate and blocked tables.
18. Markdown rejects forbidden trading language.
19. Hard-boundary test confirms no imports/calls of P36-P45 runtimes, Futu provider, trade contexts, or `HermesResearchApp`.

## 19. Acceptance Criteria

P46 is accepted when:

- focused P46 tests pass;
- CLI tests pass;
- P36-P45 regression passes except known host-specific gaps;
- governance-adjacent regression passes;
- doc standards pass;
- P46 writes append-only JSON/Markdown artifacts;
- P46 persists append-only plan rows;
- P46 does not call any refresh/runtime/provider/trading functions;
- P46 clearly distinguishes refresh candidates from blocked items.

