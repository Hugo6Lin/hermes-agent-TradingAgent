# P25-B Offline Training Dataset Builder Spec

Date: 2026-04-25
Status: Draft for engineering handoff
Scope: Point-in-time offline dataset construction for future XGBoost-style meta-model training

## 1. Purpose

P25-A introduced a shadow-only XGBoost-style dry adapter.

P25-B prepares the next prerequisite: a clean, auditable offline training dataset.

This phase builds feature/target rows from existing persisted factor snapshots and forward-return observations. It does not train a model.

## 2. Core Principle

Training data is a contract, not a convenience file.

Every row must prove:

- features came from a point-in-time factor snapshot
- target came from a matching forward-return observation
- target return basis is net
- universe membership is consistent
- no lookahead violation is present
- no required feature is missing

## 3. Non-Goals

P25-B must not:

- import `xgboost`, `sklearn`, `torch`, `tensorflow`, `stable_baselines`, or model-training libraries
- train any model
- tune hyperparameters
- select features by performance
- compute IC/ICIR
- read raw price files
- compute forward returns from prices
- write canonical `FactorSnapshot`
- write production configs
- promote any shadow score
- execute live trades

## 4. Inputs

### 4.1 Factor snapshot input

The builder accepts factor snapshot-like objects or dictionaries.

Required fields:

- `snapshot_id`
- `ticker`
- `trading_day`
- `company_quality_score`
- `valuation_attractiveness_score`
- `timing_market_fit_score`
- `llm_adjustment_total`
- `coverage_confidence_score`
- `data_as_of_date`
- `universe_membership_snapshot_id`

Optional fields:

- `sector`
- `market_cap_bucket`
- `regime_label`
- `negative_signal_strength_decile`
- `schema_version`
- `lookahead_violation`
- `source_audit_gap`

### 4.2 Forward return input

The builder accepts forward-return observation-like objects or dictionaries.

Required fields:

- `snapshot_id`
- `horizon_days`
- `net_return_pct`
- `gross_return_pct`
- `transaction_cost_pct`
- `return_basis`
- `computed_at`

Accepted target:

```text
return_basis == "net"
net_return_pct is not None
horizon_days == request.horizon_days
```

### 4.3 `TrainingDatasetRequest`

Required fields:

- `dataset_id`
- `candidate_namespace`
- `horizon_days`
- `feature_names`
- `target_name`
- `min_rows`
- `require_point_in_time`
- `require_universe_membership`
- `max_source_audit_gap_rate`
- `notes`

Accepted values:

```text
candidate_namespace starts with "shadow_meta_model."
target_name == "net_return_pct"
require_point_in_time == true
require_universe_membership == true
max_source_audit_gap_rate <= 0.20
```

## 5. Outputs

### 5.1 `TrainingDatasetRow`

Required fields:

- `snapshot_id`
- `ticker`
- `trading_day`
- `features`
- `target_name`
- `target_value`
- `horizon_days`
- `data_as_of_date`
- `universe_membership_snapshot_id`
- `source_snapshot_schema_version`
- `source_return_schema_version`

### 5.2 `TrainingDatasetManifest`

Required fields:

- `schema_version`: `p25_training_dataset.0`
- `dataset_id`
- `candidate_namespace`
- `horizon_days`
- `feature_names`
- `target_name`
- `total_snapshots`
- `total_forward_returns`
- `included_rows`
- `excluded_counts`
- `point_in_time_confirmed`
- `return_basis`
- `min_rows`
- `meets_min_rows`
- `created_at`
- `notes`

### 5.3 `TrainingDatasetBuildResult`

Required fields:

- `manifest`
- `rows`

### 5.4 `build_training_dataset`

Required signature:

```python
build_training_dataset(factor_snapshots, forward_returns, request) -> TrainingDatasetBuildResult
```

The function must be pure with respect to production state: it may inspect provided snapshot/return inputs and return dataset objects, but it must not read raw prices, write persistence tables, or mutate production configs.

## 6. Exclusion Rules

The builder must count and exclude rows for:

- `missing_forward_return`
- `non_net_return`
- `lookahead_violation`
- `source_audit_gap`
- `universe_mismatch`
- `missing_required_feature`
- `wrong_horizon`

Rules:

```text
no matching forward return -> missing_forward_return
return_basis != "net" -> non_net_return
horizon_days != request.horizon_days -> wrong_horizon
snapshot.lookahead_violation == true -> lookahead_violation
snapshot.source_audit_gap > max_source_audit_gap_rate -> source_audit_gap
missing universe_membership_snapshot_id when required -> universe_mismatch
missing any requested feature -> missing_required_feature
```

If multiple exclusion reasons apply, the row may increment multiple counts but must not appear in output rows.

## 7. Join Semantics

Snapshots and returns must join by `snapshot_id`.

The builder must not join by ticker/date alone.

If multiple forward returns exist for the same `(snapshot_id, horizon_days)`, prefer:

1. return observation with `return_basis == "net"`
2. latest `computed_at`

The manifest must still report `total_forward_returns`.

## 8. Safety Rules

P25-B must:

- use net returns by default
- reject request target names other than `net_return_pct`
- reject non-shadow namespaces
- never read raw prices
- never compute returns directly
- never write production configs
- return JSON-serializable manifest and rows

## 9. Tests

Acceptance tests must cover:

1. valid snapshot + net forward return produces one row
2. join uses `snapshot_id`, not ticker/date
3. missing forward return excludes row
4. non-net return excludes row
5. wrong horizon excludes row
6. lookahead violation excludes row
7. source audit gap excludes row
8. missing universe membership excludes row
9. missing requested feature excludes row
10. duplicate forward returns choose latest net observation
11. manifest excluded counts are correct
12. manifest `meets_min_rows` reflects row count
13. request rejects non-shadow namespace
14. request rejects non-net target
15. output is JSON-serializable
16. no model libraries are imported

## 10. Acceptance Checklist

- Training dataset request contract exists.
- Training dataset row contract exists.
- Training dataset manifest exists.
- Join is by `snapshot_id`.
- Net return is default and required.
- Wrong horizon rows are excluded.
- Lookahead rows are excluded.
- Source audit gap rows are excluded.
- Universe membership is required.
- Missing features are excluded.
- Duplicate returns are resolved deterministically.
- Excluded counts are reported.
- Manifest is JSON-serializable.
- No raw prices are read.
- No model libraries are imported.
- No training is performed.

## 11. Boundary to P25-C

P25-B ends at dataset construction.

P25-C may introduce offline train/validation split manifests, but still must not train XGBoost until a separate training spec is approved.
