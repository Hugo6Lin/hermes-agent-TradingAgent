# P24-D Shadow Run Persistence and Observation Bridge Spec

Date: 2026-04-25
Status: Draft for engineering handoff
Scope: Persist P24 shadow run records and convert them into observation summaries

## 1. Purpose

P24-C produces `ShadowExperimentRunRecord` objects.

P24-D makes those run records durable and observable.

The goal is to close the P24 loop:

```text
P24-A Entry Gate
  -> P24-B Shadow Experiment Registry
  -> P24-C Shadow Runner
  -> P24-D Run Persistence + Observation Bridge
```

P24-D does not train models, does not calculate promotion decisions, and does not modify production configuration. It records what happened and summarizes whether an experiment is healthy enough to keep observing.

## 2. Core Principle

Every shadow run must be remembered, including blocked and failed runs.

Completed runs are useful evidence.

Blocked and failed runs are safety evidence.

No run record may be overwritten.

## 3. Non-Goals

P24-D must not:

- train or load advanced models
- import `xgboost`, `torch`, `tensorflow`, `sklearn`, `stable_baselines`, or RL libraries
- compute IC, ICIR, PnL, or promotion decisions
- write canonical `FactorSnapshot`
- write production configs
- revoke experiments automatically
- promote any shadow output
- execute live trades

## 4. Inputs

### 4.1 `ShadowExperimentRunRecord`

The store accepts run records emitted by P24-C.

Required run record fields include:

- `schema_version`
- `run_id`
- `experiment_id`
- `candidate_id`
- `candidate_family`
- `manifest_schema_version`
- `manifest_status`
- `run_mode`
- `input_window`
- `output_namespace`
- `adapter_name`
- `adapter_version`
- `status`
- `produced_artifacts`
- `blocked_artifacts`
- `safety_checks`
- `warnings`
- `error_message`
- `no_production_write_confirmed`
- `canonical_snapshot_write_blocked`
- `production_config_write_blocked`
- `live_trading_blocked`
- `started_at`
- `completed_at`
- `notes`

### 4.2 `ShadowExperimentManifest`

The observation bridge accepts the manifest associated with a run record.

The bridge must verify:

```text
record.experiment_id == manifest.experiment_id
record.candidate_id == manifest.candidate_id
record.output_namespace == manifest.shadow_namespace
```

## 5. Output Contracts

### 5.1 `ShadowRunStore`

Required methods:

- `save_run_record(record)`
- `get_run_record(run_id)`
- `list_run_records(experiment_id=None, status=None)`
- `summarize_experiment_runs(experiment_id)`

The v1 store may be in-memory only. It must still enforce duplicate prevention, safety flag validation, insertion-order listing, and JSON-serializable storage.

### 5.2 `ShadowRunSummary`

Required fields:

- `schema_version`: `p24_run_summary.0`
- `experiment_id`
- `total_runs`
- `completed_count`
- `blocked_count`
- `failed_count`
- `last_run_id`
- `last_run_status`
- `blocked_reason_frequency`
- `failed_error_frequency`
- `latest_completed_at`
- `health_status`: `healthy`, `watch`, `revocation_recommended`, or `no_runs`
- `revocation_recommended`
- `revocation_reasons`

### 5.3 `ShadowExperimentObservation`

Required fields:

- `schema_version`: `p24_observation.0`
- `experiment_id`
- `run_id`
- `candidate_id`
- `candidate_family`
- `run_status`
- `health_status`
- `produced_artifacts`
- `blocked_artifacts`
- `warnings`
- `revocation_recommended`
- `revocation_reasons`
- `source_manifest_schema_version`
- `source_run_schema_version`
- `no_production_write_confirmed`
- `created_at`

## 6. Store Behavior

### 6.1 Save

`save_run_record(record)` must:

1. validate schema version starts with `p24_run.`
2. validate `run_id` is non-empty
3. reject duplicate `run_id`
4. validate safety flags are all true
5. store a JSON-serializable plain dict copy
6. return the saved record

Safety flags:

```text
no_production_write_confirmed == true
canonical_snapshot_write_blocked == true
production_config_write_blocked == true
live_trading_blocked == true
```

### 6.2 Query

The store must support:

- `get_run_record(run_id)`
- `list_run_records(experiment_id=None, status=None)`
- `summarize_experiment_runs(experiment_id)`

`list_run_records()` should return records in insertion order.

### 6.3 Duplicate Policy

`run_id` is immutable and globally unique inside the store.

Duplicate saves must raise `ShadowRunPersistenceError`.

No overwrite mode is allowed in P24-D.

## 7. Observation Bridge Behavior

`build_shadow_experiment_observation(record, manifest)` must:

1. validate run/manifest identity alignment
2. derive health status from run status and blocked artifacts
3. recommend revocation only as a recommendation, never as action
4. include run and manifest schema versions
5. preserve production-write safety confirmation

### 7.1 Health Rules

Single-run observation health:

```text
completed -> healthy
blocked with safety/config reason -> watch
failed -> watch
blocked with production/canonical/live-trading reason -> revocation_recommended
```

Summary health:

```text
no runs -> no_runs
latest run completed and failed_count == 0 and blocked_count == 0 -> healthy
blocked_count + failed_count > completed_count -> watch
any production/canonical/live-trading blocked reason -> revocation_recommended
three consecutive blocked_or_failed statuses -> revocation_recommended
```

P24-D must never call `revoke_experiment()`. It may only set `revocation_recommended = true` with reasons.

## 8. Safety Rules

P24-D must block persistence if:

- run schema version is not `p24_run.*`
- `run_id` is empty
- `run_id` already exists
- any production safety flag is false
- record is not JSON-serializable

P24-D must block observation bridge if:

- record/manifest `experiment_id` mismatch
- record/manifest `candidate_id` mismatch
- record output namespace differs from manifest shadow namespace

## 9. Tests

Acceptance tests must cover:

1. completed run is saved and retrieved
2. blocked run is saved and retrieved
3. failed run is saved and retrieved
4. duplicate `run_id` is rejected
5. false production safety flag is rejected
6. records query by experiment ID
7. records query by status
8. summary counts completed/blocked/failed
9. summary computes blocked reason frequency
10. observation bridge creates healthy observation for completed run
11. observation bridge recommends revocation for production/canonical/live-trading block
12. observation bridge blocks manifest/run mismatch
13. three consecutive blocked/failed runs recommend revocation in summary
14. store returns JSON-serializable records
15. no model libraries are imported

## 10. Acceptance Checklist

- Completed, blocked, and failed runs persist.
- Duplicate run IDs are rejected.
- Production safety flags are enforced.
- Query by experiment ID works.
- Query by status works.
- Summary counts run statuses.
- Summary tracks blocked reason frequency.
- Observation bridge preserves manifest/run identity.
- Observation bridge recommends revocation without executing it.
- JSON serialization works.
- No model libraries are imported.
- No production configs or factor snapshots are written.

## 11. Boundary to P24-E

P24-D ends at persistence and observation records.

P24-E may add a dashboard/report aggregator for shadow experiment health, but it still must not train advanced models or promote shadow outputs.
