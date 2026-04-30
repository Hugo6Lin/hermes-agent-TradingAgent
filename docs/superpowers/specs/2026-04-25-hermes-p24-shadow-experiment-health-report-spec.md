# P24-E Shadow Experiment Health Report Spec

Date: 2026-04-25
Status: Draft for engineering handoff
Scope: Read-only health reporting for P24 shadow experiments

## 1. Purpose

P24-D persists shadow run records and creates observations.

P24-E turns those records into a read-only health report that a research lead or manager can understand.

The report answers:

- how many shadow experiments exist
- which experiments are healthy
- which experiments require watch
- which experiments have revocation recommended
- which candidate families are producing stable shadow runs
- which blocked reasons occur most often
- whether the no-production-write safety boundary remains intact

P24-E is reporting only. It does not run experiments, train models, promote outputs, revoke experiments, or modify production configuration.

## 2. Core Principle

The health report is a dashboard-like snapshot over P24-B manifests and P24-D run summaries.

It is not an action engine.

Every revocation field is advisory.

No report output may alter registry, runner, factor snapshots, production configs, trade plans, or live trading behavior.

## 3. Non-Goals

P24-E must not:

- train or load advanced models
- import `xgboost`, `torch`, `tensorflow`, `sklearn`, `stable_baselines`, or RL libraries
- run shadow experiments
- save new run records
- revoke experiments
- promote experiments
- write canonical `FactorSnapshot`
- write production configs
- compute IC, ICIR, PnL, or model performance metrics beyond existing run summary counts
- execute live trades

## 4. Inputs

### 4.1 Manifests

Input manifests are `ShadowExperimentManifest` records from P24-B.

The report must tolerate:

- registered manifests with runs
- registered manifests without runs
- revoked manifests
- archived manifests

### 4.2 Run Store

Input run store is `ShadowRunStore` from P24-D.

The report reads:

- `list_run_records(experiment_id=...)`
- `summarize_experiment_runs(experiment_id)`

The report must not write to the store.

## 5. Output Contracts

### 5.1 `ExperimentHealthRow`

Required fields:

- `experiment_id`
- `candidate_id`
- `candidate_name`
- `candidate_family`
- `manifest_status`
- `shadow_namespace`
- `total_runs`
- `completed_count`
- `blocked_count`
- `failed_count`
- `last_run_id`
- `last_run_status`
- `health_status`: `healthy`, `watch`, `revocation_recommended`, or `no_runs`
- `revocation_recommended`
- `revocation_reasons`
- `top_blocked_reasons`
- `latest_completed_at`
- `no_production_write_confirmed`
- `canonical_snapshot_write_blocked`
- `production_config_write_blocked`
- `live_trading_blocked`

### 5.2 `ShadowExperimentHealthReport`

Required fields:

- `schema_version`: `p24_health_report.0`
- `generated_at`
- `total_experiments`
- `registered_count`
- `revoked_count`
- `archived_count`
- `healthy_count`
- `watch_count`
- `no_runs_count`
- `revocation_recommended_count`
- `family_breakdown`
- `top_blocked_reasons`
- `production_safety_summary`
- `experiments`
- `recommended_actions`

### 5.3 `family_breakdown`

For each `candidate_family`, report:

- `total_experiments`
- `registered_count`
- `healthy_count`
- `watch_count`
- `no_runs_count`
- `revocation_recommended_count`
- `completed_runs`
- `blocked_runs`
- `failed_runs`

### 5.4 `production_safety_summary`

Required fields:

- `all_no_production_write_confirmed`
- `any_canonical_snapshot_write_attempt`
- `any_production_config_write_attempt`
- `any_live_trading_attempt`
- `unsafe_experiment_ids`

The summary must be derived from persisted run records and manifest safety flags.

## 6. Health Logic

For each manifest:

1. call `run_store.summarize_experiment_runs(experiment_id)`
2. derive `ExperimentHealthRow` from manifest + summary
3. preserve summary `health_status`
4. preserve summary `revocation_recommended`
5. preserve summary `revocation_reasons`

For manifests with no runs:

```text
health_status = "no_runs"
revocation_recommended = false
```

For non-registered manifests:

```text
manifest_status is preserved
health_status follows run summary if runs exist, otherwise "no_runs"
```

The report must not override P24-D health logic.

## 7. Recommended Actions

`recommended_actions` is advisory only.

Rules:

- If `revocation_recommended_count > 0`, include `"review_revocation_recommended_experiments"`.
- If `no_runs_count > 0`, include `"schedule_shadow_runs_for_no_run_experiments"`.
- If `watch_count > 0`, include `"inspect_watch_experiments"`.
- If production safety summary has any unsafe flag, include `"investigate_production_safety_violation"`.
- If all experiments are healthy and at least one experiment exists, include `"continue_observation"`.

No action may execute code outside report construction.

## 8. Sorting

Experiment rows should be sorted by:

1. `revocation_recommended` first
2. `health_status == "watch"` next
3. `health_status == "no_runs"` next
4. `candidate_family`
5. `experiment_id`

This places risk at the top while keeping stable ordering.

## 9. Safety Rules

P24-E must:

- read manifests
- read run summaries
- return plain JSON-serializable report objects
- preserve production safety flags
- never write to registry
- never write to run store
- never call `revoke_experiment`
- never call `run_shadow_experiment`

## 10. Tests

Acceptance tests must cover:

1. empty manifest list returns empty report
2. registered experiment with completed runs appears healthy
3. experiment with blocked/failed majority appears watch
4. experiment with revocation recommendation appears at top
5. no-run experiment appears as `no_runs`
6. family breakdown counts experiments and run statuses
7. top blocked reasons aggregate across experiments
8. production safety summary detects canonical/production/live-trading attempts
9. recommended actions include no-run/watch/revocation actions
10. report rows sort risk first
11. report is JSON-serializable
12. no model libraries are imported

## 11. Acceptance Checklist

- Health report contract exists.
- Experiment rows include manifest and run summary fields.
- Empty report works.
- Healthy/watch/no-runs/revocation states are represented.
- Family breakdown is computed.
- Top blocked reasons are aggregated.
- Production safety summary is computed.
- Recommended actions are advisory only.
- Rows are risk-sorted.
- Report is JSON-serializable.
- No registry mutation occurs.
- No run store mutation occurs.
- No model libraries are imported.

## 12. Boundary to P25

P24-E ends the P24 advanced-model safety scaffold:

```text
Gate -> Registry -> Runner -> Persistence -> Health Report
```

P25 may introduce the first real shadow candidate implementation, but only if it uses P24-A through P24-E and remains shadow-only.
