# Executor Prompt: P24-D Shadow Run Persistence + Observation Bridge

You are implementing P24-D for Hermes.

Read these first:

1. `docs/superpowers/specs/2026-04-25-hermes-p24-shadow-run-persistence-observation-spec.md`
2. `docs/superpowers/plans/2026-04-25-p24-shadow-run-persistence-observation.md`
3. `agent/research_v1/p24_entry_gate.py`
4. `agent/research_v1/p24_experiment_registry.py`
5. `agent/research_v1/p24_shadow_runner.py`
6. `tests/agent/research_v1/test_p24_entry_gate.py`
7. `tests/agent/research_v1/test_p24_experiment_registry.py`
8. `tests/agent/research_v1/test_p24_shadow_runner.py`

## Mission

Implement shadow run persistence and observation bridge.

P24-D persists `ShadowExperimentRunRecord` objects and creates observation summaries. It does not train models, promote outputs, revoke experiments, or modify production configuration.

## Hard Constraints

Do not:

- train any model
- import `xgboost`, `torch`, `tensorflow`, `sklearn`, `stable_baselines`, or RL libraries
- compute IC/ICIR/PnL/promotion decisions
- write canonical `FactorSnapshot`
- modify production configs
- auto-revoke experiments
- generate live trade signals
- add portfolio execution behavior

Use Python 3.11 and stdlib only.

## Files to Create

- `agent/research_v1/p24_run_persistence.py`
- `tests/agent/research_v1/test_p24_run_persistence.py`

## Required Contracts

Create:

- `ShadowRunPersistenceError`
- `ShadowRunSummary`
- `ShadowExperimentObservation`
- `ShadowRunStore`
- `summarize_run_records(experiment_id, records)`
- `build_shadow_experiment_observation(record, manifest)`

`ShadowRunStore` must support:

- `save_run_record(record)`
- `get_run_record(run_id)`
- `list_run_records(experiment_id=None, status=None)`
- `summarize_experiment_runs(experiment_id)`

## Required Behavior

Persistence must:

- save completed, blocked, and failed run records
- reject duplicate `run_id`
- reject records whose schema does not start with `p24_run.`
- reject records with false production safety flags
- preserve insertion order
- support query by `experiment_id`
- support query by `status`
- return JSON-serializable records

Summary must report:

- total runs
- completed count
- blocked count
- failed count
- last run ID
- last run status
- blocked reason frequency
- failed error frequency
- latest completed timestamp
- health status
- `revocation_recommended`
- revocation reasons

Observation bridge must:

- validate record/manifest experiment ID
- validate record/manifest candidate ID
- validate record output namespace equals manifest shadow namespace
- create healthy observation for completed run
- create watch observation for normal blocked/failed run
- recommend revocation for production/canonical/live-trading path block
- preserve `no_production_write_confirmed`
- never call registry `revoke_experiment`

## Verification Commands

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p24_run_persistence.py -q
```

Run:

```bash
python3.11 -m pytest \
  tests/agent/research_v1/test_p24_entry_gate.py \
  tests/agent/research_v1/test_p24_experiment_registry.py \
  tests/agent/research_v1/test_p24_shadow_runner.py \
  tests/agent/research_v1/test_p24_run_persistence.py \
  -q
```

Run:

```bash
python3.11 -m pytest \
  tests/agent/research_v1/test_p20_factor_contracts.py \
  tests/agent/research_v1/test_p20_pnl_integrity.py \
  tests/agent/research_v1/test_p21_calibration_inputs.py \
  tests/agent/research_v1/test_p22_a_plus_validity_integrity_health.py \
  tests/agent/research_v1/test_p23_shadow_calibration.py \
  tests/agent/research_v1/test_p23_shadow_observation_loop.py \
  tests/agent/research_v1/test_p24_entry_gate.py \
  tests/agent/research_v1/test_p24_experiment_registry.py \
  tests/agent/research_v1/test_p24_shadow_runner.py \
  tests/agent/research_v1/test_p24_run_persistence.py \
  -q
```

Run:

```bash
grep -R "import xgboost\|from xgboost\|import torch\|from torch\|import tensorflow\|from tensorflow\|stable_baselines\|import sklearn\|from sklearn" -n \
  agent/research_v1/p24_run_persistence.py \
  tests/agent/research_v1/test_p24_run_persistence.py || true
```

Expected: no output except possible string literals inside the no-model-library test.

## Handoff Report

Return exactly this structure:

```text
P24-D Shadow Run Persistence + Observation Bridge Handoff

Changed files:
- <path> — <created/modified> — <purpose>

Tests run:
- <command> → <result>

Acceptance checklist:
- completed/blocked/failed runs persist: yes/no
- duplicate run IDs rejected: yes/no
- production safety flags enforced: yes/no
- query by experiment ID works: yes/no
- query by status works: yes/no
- summary counts statuses: yes/no
- blocked reason frequency computed: yes/no
- observation bridge validates manifest/run identity: yes/no
- revocation recommendation only, no auto revoke: yes/no
- JSON serialization works: yes/no
- no model libraries imported: yes/no
- P20-P24 regression green: yes/no

Known issues:
- <issue or None>
```
