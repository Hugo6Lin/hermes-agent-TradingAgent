# P25-D Shadow Offline Training Runner Spec

Date: 2026-04-25
Status: Draft for engineering handoff
Scope: Shadow-only offline training runner using P25-B datasets and P25-C walk-forward split manifests

## 1. Purpose

P25-A introduced a safe XGBoost-style dry adapter.

P25-B built point-in-time training dataset rows.

P25-C built purged walk-forward split manifests.

P25-D is the first phase that may perform offline training, but only inside the shadow experiment system and only from approved P25-B/P25-C artifacts.

The output is not a production model. It is an auditable set of walk-forward out-of-sample prediction artifacts that later P25-E can evaluate.

## 2. Core Principle

Training is allowed only after the data contract and split contract are already clean.

P25-D must never decide what data to use by itself. It consumes:

- P25-B `TrainingDatasetBuildResult`
- P25-C `SplitManifest`
- P24 registered shadow experiment manifest

The runner must train only on each window's `train_snapshot_ids` and predict only on that same window's `validation_snapshot_ids`.

## 3. Non-Goals

P25-D must not:

- write production configs
- write canonical `FactorSnapshot`
- write live trade signals
- promote any shadow score
- auto-register experiments
- auto-revoke experiments
- read raw price files
- recompute forward returns
- perform random train/test splits
- compute PnL attribution or IC/ICIR final reports
- use validation labels during fitting
- tune hyperparameters from validation performance
- persist binary model objects
- require `xgboost`, `torch`, `tensorflow`, `stable_baselines3`, or GPU libraries

P25-D may use Python standard library only. If a lightweight deterministic baseline is needed, implement it directly.

## 4. Inputs

### 4.1 `TrainingDatasetBuildResult`

Required fields:

- `manifest`
- `rows`

The dataset manifest must provide:

- `dataset_id`
- `candidate_namespace`
- `feature_names`
- `target_name`
- `horizon_days`
- `return_basis`
- `point_in_time_confirmed`
- `meets_min_rows`
- `schema_version`

Each row must provide:

- `snapshot_id`
- `ticker`
- `trading_day`
- `features`
- `target_name`
- `target_value`
- `horizon_days`

### 4.2 `SplitManifest`

Required fields:

- `split_id`
- `dataset_id`
- `candidate_namespace`
- `walk_forward_enabled`
- `windows`
- `schema_version`

Each window must provide:

- `window_id`
- `train_snapshot_ids`
- `validation_snapshot_ids`
- `train_row_count`
- `validation_row_count`
- `train_start`
- `train_end`
- `validation_start`
- `validation_end`

### 4.3 P24 registry manifest

P25-D must receive a registered P24 experiment manifest or a manifest-like dict.

Required fields:

- `experiment_id`
- `candidate_namespace`
- `candidate_family`
- `status`
- `output_namespace`
- `production_write_blocked`
- `canonical_snapshot_write_blocked`
- `live_trading_blocked`

Accepted values:

```text
status in {"registered", "running", "active"}
production_write_blocked == true
canonical_snapshot_write_blocked == true
live_trading_blocked == true
```

### 4.4 `ShadowTrainingRequest`

Required fields:

- `training_run_id`
- `experiment_id`
- `dataset_id`
- `split_id`
- `candidate_namespace`
- `model_family`
- `feature_names`
- `target_name`
- `training_mode`
- `hyperparameters`
- `baseline_name`
- `notes`

Accepted values:

```text
candidate_namespace starts with "shadow_meta_model."
model_family in {"linear_baseline", "stump_ensemble_stub", "xgboost_style_stub"}
training_mode in {"shadow_offline", "dry_run"}
target_name == "net_return_pct"
feature_names is non-empty
hyperparameters is JSON-serializable
```

## 5. Outputs

### 5.1 `WindowTrainingArtifact`

Required fields:

- `training_run_id`
- `experiment_id`
- `window_id`
- `candidate_namespace`
- `model_family`
- `feature_names`
- `train_snapshot_ids`
- `validation_snapshot_ids`
- `train_row_count`
- `validation_row_count`
- `fitted_parameters`
- `predictions`
- `training_status`
- `warnings`

`predictions` is a list of dictionaries with:

- `snapshot_id`
- `prediction_value`
- `prediction_rank`
- `target_name`
- `actual_target_value`
- `trading_day`

P25-D may include `actual_target_value` for later evaluation, but model fitting code must not read validation target values before predictions are generated.

### 5.2 `ShadowTrainingRunManifest`

Required fields:

- `schema_version`: `p25_shadow_training.0`
- `training_run_id`
- `experiment_id`
- `dataset_id`
- `split_id`
- `candidate_namespace`
- `model_family`
- `training_mode`
- `feature_names`
- `target_name`
- `total_windows`
- `completed_windows`
- `blocked_windows`
- `failed_windows`
- `hyperparameters`
- `baseline_name`
- `dataset_schema_version`
- `split_schema_version`
- `created_at`
- `safety_flags`
- `warnings`
- `notes`

### 5.3 `ShadowTrainingRunResult`

Required fields:

- `manifest`
- `window_artifacts`

### 5.4 `run_shadow_offline_training`

Required signature:

```python
run_shadow_offline_training(dataset_result, split_manifest, experiment_manifest, request) -> ShadowTrainingRunResult
```

The function must be pure with respect to production state. It may return result contracts, but must not write files, write databases, alter configs, or trigger live actions.

## 6. Safety Validation Rules

Before training starts, P25-D must block the entire run if any condition is true:

- dataset `dataset_id` does not match request `dataset_id`
- split `split_id` does not match request `split_id`
- split `dataset_id` does not match dataset `dataset_id`
- candidate namespace mismatch across dataset, split, experiment, and request
- dataset manifest `return_basis != "net"`
- dataset manifest `point_in_time_confirmed != true`
- dataset manifest `meets_min_rows != true`
- split manifest `walk_forward_enabled != true`
- experiment manifest has any production safety flag false
- request target is not `net_return_pct`
- request feature names are not a subset of dataset feature names
- any requested feature name is missing in a training row
- any training or validation snapshot ID in the split is absent from dataset rows
- any snapshot ID appears in both train and validation for the same window

Blocked runs return a result with:

```text
completed_windows == 0
blocked_windows == total_windows
failed_windows == 0
window_artifacts == []
warnings includes machine-readable block reasons
```

## 7. Training Rules

P25-D must support at least one deterministic standard-library baseline.

Required baseline: `linear_baseline`.

Minimum acceptable implementation:

1. For each requested feature, compute the training-set mean feature value and target covariance direction.
2. Build a deterministic signed feature weight from the training rows only.
3. Score validation rows using features only.
4. Clamp predictions to a reasonable numeric range, such as `[-1.0, 1.0]`.
5. Rank validation predictions within the window.

The exact math may be simple. The important contract is:

- fitting uses training rows only
- prediction uses validation features only
- validation targets are attached only after predictions are generated
- repeated runs with identical inputs produce identical artifacts

`dry_run` may skip fitting and produce deterministic zero predictions, but must still validate all contracts.

## 8. Artifact Namespace Rules

All artifacts must stay under the request namespace.

Allowed artifact names:

```text
{candidate_namespace}.training_run
{candidate_namespace}.window.{window_id}.predictions
{candidate_namespace}.window.{window_id}.fitted_parameters
```

P25-D must not produce artifacts under:

- `factor_snapshot`
- `production_config`
- `live_signal`
- `trade_order`
- any namespace not equal to the candidate namespace or a dot-delimited child of it

## 9. Serialization Rules

All output contracts must provide `to_dict()` and return JSON-serializable plain dictionaries/lists/scalars.

No output may contain:

- function objects
- class objects
- binary model objects
- numpy arrays
- pandas frames
- non-serializable mapping proxies

## 10. Tests Required

Acceptance tests must cover:

1. request contract validation
2. dataset/split/experiment namespace mismatch blocks run
3. non-net dataset return basis blocks run
4. point-in-time false blocks run
5. production safety flag false blocks run
6. missing split snapshot ID blocks run
7. train/validation overlap blocks run
8. requested feature not in dataset manifest blocks run
9. deterministic dry run produces zero predictions
10. linear baseline trains from train rows and predicts validation rows
11. validation targets do not affect predictions
12. repeated identical inputs produce identical predictions
13. result contracts are JSON-serializable
14. artifact names stay inside namespace
15. no model libraries are imported
16. no production persistence is written

## 11. Acceptance Checklist

A valid P25-D handoff must report:

- training request contract exists: yes/no
- training result contracts exist: yes/no
- consumes P25-B dataset result: yes/no
- consumes P25-C split manifest: yes/no
- P24 experiment safety enforced: yes/no
- candidate namespace matching enforced: yes/no
- net return required: yes/no
- point-in-time dataset required: yes/no
- walk-forward split required: yes/no
- missing split rows blocked: yes/no
- train/validation overlap blocked: yes/no
- deterministic dry run works: yes/no
- standard-library linear baseline works: yes/no
- validation targets not used in fitting/prediction: yes/no
- repeated runs deterministic: yes/no
- output JSON-serializable: yes/no
- no model libraries imported: yes/no
- no production writes: yes/no
- P20-P25 regression green: yes/no

## 12. Boundary to P25-E

P25-D ends at shadow offline training artifacts.

P25-E may evaluate trained shadow predictions against prior/baseline predictions and produce a model evaluation report. P25-E must remain advisory and must not promote any model to production.
