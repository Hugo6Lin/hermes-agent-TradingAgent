# Executor Prompt: P25-D Shadow Offline Training Runner

You are implementing P25-D for Hermes.

## Required Reading

Read these files before coding:

1. `docs/superpowers/specs/2026-04-25-hermes-p25-shadow-offline-training-runner-spec.md`
2. `docs/superpowers/plans/2026-04-25-p25-shadow-offline-training-runner.md`
3. Existing P25 modules:
   - `agent/research_v1/p25_xgboost_shadow_adapter.py`
   - `agent/research_v1/p25_training_dataset_builder.py`
   - `agent/research_v1/p25_split_manifest_builder.py`

## Mission

Create P25-D: a shadow-only offline training runner.

This is the first phase where offline training is allowed, but it must remain fully shadow-only and must consume only approved P25-B/P25-C artifacts.

## Files to Create

- `agent/research_v1/p25_shadow_training_runner.py`
- `tests/agent/research_v1/test_p25_shadow_training_runner.py`

## Hard Boundaries

Do not:

- write production configs
- write canonical factor snapshots
- write live trade signals
- persist binary model objects
- read raw prices
- recompute forward returns
- auto-promote any shadow output
- auto-register or auto-revoke experiments
- import `xgboost`, `sklearn`, `torch`, `tensorflow`, `stable_baselines3`, `numpy`, or `pandas`

Use Python standard library only.

## Required Contracts

Implement:

- `ShadowTrainingRequest`
- `WindowTrainingArtifact`
- `ShadowTrainingRunManifest`
- `ShadowTrainingRunResult`
- `ShadowTrainingError`
- `run_shadow_offline_training(dataset_result, split_manifest, experiment_manifest, request)`

All output contracts must expose `to_dict()` returning JSON-serializable plain dict/list/scalar structures.

## Required Safety Blocks

The runner must block the whole run if:

- dataset ID mismatch
- split ID mismatch
- split dataset ID mismatch
- candidate namespace mismatch across dataset/split/experiment/request
- experiment output namespace escapes candidate namespace
- dataset return basis is not net
- dataset point-in-time is not confirmed
- dataset does not meet min rows
- split is not walk-forward enabled
- experiment safety flags are false
- requested target is not `net_return_pct`
- requested features are not a subset of dataset feature names
- any requested feature is missing from dataset rows
- split references snapshot IDs missing from dataset
- train and validation overlap in a window

Blocked run result:

- `completed_windows == 0`
- `blocked_windows == total_windows`
- `failed_windows == 0`
- `window_artifacts == []`
- `warnings` includes machine-readable reasons

## Required Training Behavior

Support two modes:

1. `dry_run`
   - Produces deterministic zero predictions.
   - Still validates all contracts.

2. `shadow_offline` with `linear_baseline`
   - Fits using training rows only.
   - Predicts validation rows using features only.
   - Attaches validation target values only after predictions are generated.
   - Repeated identical inputs produce identical outputs except `created_at`.

The baseline may be simple. Use training-set feature/target covariance direction as signed feature weights.

## Required Tests

Create tests covering:

- request validation
- JSON serialization
- namespace mismatch block
- non-net return basis block
- point-in-time false block
- production safety false block
- missing split snapshot ID block
- train/validation overlap block
- requested feature not in dataset manifest block
- deterministic dry run
- linear baseline prediction
- validation targets do not affect predictions
- repeated runs deterministic
- artifacts stay inside namespace
- no model libraries imported

## Commands to Run

Run P25-D tests:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p25_shadow_training_runner.py -q
```

Run P25 bundle:

```bash
python3.11 -m pytest \
  tests/agent/research_v1/test_p25_xgboost_shadow_adapter.py \
  tests/agent/research_v1/test_p25_training_dataset_builder.py \
  tests/agent/research_v1/test_p25_split_manifest_builder.py \
  tests/agent/research_v1/test_p25_shadow_training_runner.py \
  -q
```

Run P20-P25 regression bundle used in prior handoffs and report the exact command/result.

## Handoff Format

Return:

```text
P25-D Shadow Offline Training Runner Handoff

Changed files:

agent/research_v1/p25_shadow_training_runner.py — created — contracts, safety validation, dry-run and linear baseline training
tests/agent/research_v1/test_p25_shadow_training_runner.py — created — acceptance tests

Tests run:

python3.11 -m pytest tests/agent/research_v1/test_p25_shadow_training_runner.py -q → N passed
python3.11 -m pytest [P25 bundle] -q → N passed
python3.11 -m pytest [P20-P25 regression bundle] -q → N passed

Acceptance checklist:

training request contract exists: yes/no
training result contracts exist: yes/no
consumes P25-B dataset result: yes/no
consumes P25-C split manifest: yes/no
P24 experiment safety enforced: yes/no
candidate namespace matching enforced: yes/no
net return required: yes/no
point-in-time dataset required: yes/no
walk-forward split required: yes/no
missing split rows blocked: yes/no
train/validation overlap blocked: yes/no
deterministic dry run works: yes/no
standard-library linear baseline works: yes/no
validation targets not used in fitting/prediction: yes/no
repeated runs deterministic: yes/no
output JSON-serializable: yes/no
no model libraries imported: yes/no
no production writes: yes/no
P20-P25 regression green: yes/no

Known issues:

None.
```
