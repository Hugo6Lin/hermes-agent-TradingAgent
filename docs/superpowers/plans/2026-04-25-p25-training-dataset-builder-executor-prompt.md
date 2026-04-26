# Executor Prompt: P25-B Offline Training Dataset Builder

You are implementing P25-B for Hermes.

Read these first:

1. `docs/superpowers/specs/2026-04-25-hermes-p25-training-dataset-builder-spec.md`
2. `docs/superpowers/plans/2026-04-25-p25-training-dataset-builder.md`
3. `agent/research_v1/p25_xgboost_shadow_adapter.py`
4. `tests/agent/research_v1/test_p25_xgboost_shadow_adapter.py`

## Mission

Implement a point-in-time offline training dataset builder for future XGBoost-style meta-model work.

This is not model training. It only builds auditable rows from factor snapshots and forward-return observations.

## Hard Constraints

Do not:

- import `xgboost`, `sklearn`, `torch`, `tensorflow`, `stable_baselines`, or model-training libraries
- train any model
- tune hyperparameters
- compute IC/ICIR
- read raw prices
- compute forward returns from raw prices
- write canonical `FactorSnapshot`
- write production configs
- promote any score
- generate live trade signals

Use Python 3.11 and stdlib only.

## Files to Create

- `agent/research_v1/p25_training_dataset_builder.py`
- `tests/agent/research_v1/test_p25_training_dataset_builder.py`

## Required Contracts

Create:

- `TrainingDatasetBuilderError`
- `TrainingDatasetRequest`
- `TrainingDatasetRow`
- `TrainingDatasetManifest`
- `TrainingDatasetBuildResult`
- `build_training_dataset(factor_snapshots, forward_returns, request)`

## Required Behavior

The builder must:

- join snapshots and forward returns by `snapshot_id`
- require `target_name == "net_return_pct"`
- require `return_basis == "net"`
- require requested `horizon_days`
- require point-in-time fields
- require universe membership
- exclude lookahead rows
- exclude source audit gap rows
- exclude missing feature rows
- resolve duplicate returns by latest net observation
- report excluded counts
- return JSON-serializable rows and manifest

Exclusion keys:

- `missing_forward_return`
- `non_net_return`
- `lookahead_violation`
- `source_audit_gap`
- `universe_mismatch`
- `missing_required_feature`
- `wrong_horizon`

## Verification Commands

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p25_training_dataset_builder.py -q
```

Run:

```bash
python3.11 -m pytest \
  tests/agent/research_v1/test_p25_xgboost_shadow_adapter.py \
  tests/agent/research_v1/test_p25_training_dataset_builder.py \
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
  tests/agent/research_v1/test_p24_health_report.py \
  tests/agent/research_v1/test_p25_xgboost_shadow_adapter.py \
  tests/agent/research_v1/test_p25_training_dataset_builder.py \
  -q
```

Run:

```bash
grep -R "import xgboost\|from xgboost\|import torch\|from torch\|import tensorflow\|from tensorflow\|stable_baselines\|import sklearn\|from sklearn" -n \
  agent/research_v1/p25_training_dataset_builder.py \
  tests/agent/research_v1/test_p25_training_dataset_builder.py || true
```

Expected: no output except possible string literals inside the no-model-library test.

## Handoff Report

Return exactly this structure:

```text
P25-B Offline Training Dataset Builder Handoff

Changed files:
- <path> — <created/modified> — <purpose>

Tests run:
- <command> → <result>

Acceptance checklist:
- request contract exists: yes/no
- row contract exists: yes/no
- manifest contract exists: yes/no
- join by snapshot_id: yes/no
- net return required: yes/no
- wrong horizon excluded: yes/no
- lookahead excluded: yes/no
- source audit gap excluded: yes/no
- universe membership required: yes/no
- missing features excluded: yes/no
- duplicate returns resolved deterministically: yes/no
- excluded counts reported: yes/no
- output JSON-serializable: yes/no
- no raw prices read: yes/no
- no model libraries imported: yes/no
- no training performed: yes/no
- P20-P25 regression green: yes/no

Known issues:
- <issue or None>
```
