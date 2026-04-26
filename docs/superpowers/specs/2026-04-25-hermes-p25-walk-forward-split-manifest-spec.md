# P25-C Walk-Forward Split Manifest Builder Spec

Date: 2026-04-25
Status: Draft for engineering handoff
Scope: Purged walk-forward train/validation split manifests for P25 training datasets

## 1. Purpose

P25-B builds clean point-in-time training rows.

P25-C builds the split manifest that future training must use.

This phase does not train models. It only defines safe train/validation windows for future XGBoost-style meta-model training.

## 2. Core Principle

Financial model validation must be time-ordered.

P25-C must not perform random splits.

Every validation window must occur after its training window, with purge and embargo gaps applied to reduce leakage.

## 3. Non-Goals

P25-C must not:

- import `xgboost`, `sklearn`, `torch`, `tensorflow`, `stable_baselines`, or model-training libraries
- train any model
- tune hyperparameters
- compute IC, ICIR, PnL, or feature importance
- read raw prices
- modify dataset rows
- write canonical `FactorSnapshot`
- write production configs
- promote any shadow output

## 4. Inputs

### 4.1 Dataset rows

Input rows are `TrainingDatasetRow` objects or dict-like equivalents from P25-B.

Required fields:

- `snapshot_id`
- `trading_day`
- `features`
- `target_name`
- `target_value`
- `horizon_days`

### 4.2 `SplitManifestRequest`

Required fields:

- `split_id`
- `dataset_id`
- `candidate_namespace`
- `train_window_days`
- `validation_window_days`
- `step_days`
- `purged_gap_days`
- `embargo_days`
- `min_train_rows`
- `min_validation_rows`
- `walk_forward_enabled`
- `notes`

Accepted values:

```text
candidate_namespace starts with "shadow_meta_model."
train_window_days > 0
validation_window_days > 0
step_days > 0
purged_gap_days >= 1
embargo_days >= 1
min_train_rows >= 1
min_validation_rows >= 1
walk_forward_enabled == true
```

## 5. Outputs

### 5.1 `SplitWindow`

Required fields:

- `window_id`
- `train_start`
- `train_end`
- `validation_start`
- `validation_end`
- `purged_gap_days`
- `embargo_days`
- `train_snapshot_ids`
- `validation_snapshot_ids`
- `train_row_count`
- `validation_row_count`

### 5.2 `SplitManifest`

Required fields:

- `schema_version`: `p25_split_manifest.0`
- `split_id`
- `dataset_id`
- `candidate_namespace`
- `walk_forward_enabled`
- `train_window_days`
- `validation_window_days`
- `step_days`
- `purged_gap_days`
- `embargo_days`
- `min_train_rows`
- `min_validation_rows`
- `total_rows`
- `total_windows`
- `included_windows`
- `excluded_windows`
- `exclusion_reasons`
- `windows`
- `created_at`
- `notes`

### 5.3 `SplitBuildResult`

Required fields:

- `manifest`

### 5.4 `build_split_manifest`

Required signature:

```python
build_split_manifest(rows, request) -> SplitBuildResult
```

The function must create split metadata only. It must not train models, mutate rows, compute performance, or write production state.

## 6. Split Rules

Rows must be sorted by `trading_day`, then `snapshot_id`.

For each candidate window:

```text
train_start <= train dates <= train_end
validation_start <= validation dates <= validation_end
validation_start > train_end
validation_start >= train_end + purged_gap_days
```

The embargo period after validation is represented in the manifest and affects the next window's train eligibility.

No `snapshot_id` may appear in both train and validation in the same window.

No validation date may be earlier than or equal to the train end date.

## 7. Window Exclusion Rules

Exclude candidate windows for:

- `insufficient_train_rows`
- `insufficient_validation_rows`
- `train_validation_overlap`
- `validation_not_after_train`
- `purge_gap_violation`

`excluded_windows` is the total number of excluded candidate windows.

`exclusion_reasons` maps reason -> count.

## 8. Safety Rules

P25-C must:

- use time-ordered walk-forward splits only
- reject random split requests
- reject non-shadow namespaces
- reject zero or negative window parameters
- preserve row snapshot IDs without mutation
- return JSON-serializable manifests
- import no model libraries
- train no models

## 9. Tests

Acceptance tests must cover:

1. request rejects non-shadow namespace
2. request rejects `walk_forward_enabled == false`
3. request rejects zero/negative windows
4. sorted rows produce at least one split window
5. train dates are before validation dates
6. purge gap is enforced
7. embargo fields are preserved
8. train/validation snapshot IDs do not overlap
9. insufficient train rows exclude window
10. insufficient validation rows exclude window
11. manifest reports exclusion reasons
12. rows can be dict-like or dataclass-like
13. manifest is JSON-serializable
14. no model libraries are imported

## 10. Acceptance Checklist

- Split request contract exists.
- Split window contract exists.
- Split manifest contract exists.
- Walk-forward only.
- Random split disabled.
- Train dates precede validation dates.
- Purge gap enforced.
- Embargo days recorded.
- Snapshot IDs do not overlap.
- Insufficient windows excluded.
- Exclusion reasons reported.
- Manifest JSON-serializable.
- No model libraries imported.
- No training performed.

## 11. Boundary to P25-D

P25-C ends at split manifest construction.

P25-D may introduce a shadow-only offline training runner, but only after the split manifest is accepted and still under a separate spec.
