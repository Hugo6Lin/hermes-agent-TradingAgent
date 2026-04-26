# Phase 25 Shadow Model Evaluation and Governance Spec

Date: 2026-04-25
Status: Draft for engineering handoff
Scope: Consolidated P25-E + P25-F: evaluate P25-D shadow training outputs and produce advisory promotion-readiness decisions

## 1. Purpose

Phase 25 closes the shadow meta-model loop.

P25-A through P25-D proved that Hermes can register a shadow model candidate, build point-in-time training data, create purged walk-forward splits, and generate shadow offline predictions.

This consolidated phase replaces separate P25-E and P25-F nodes with one harder node:

```text
P25-E/F = Shadow Model Evaluation Report + Promotion Readiness Gate
```

The result is advisory only. It may say a model is ready for longer observation or production review, but it must not promote, deploy, or modify production configs.

## 2. Core Principle

A trained shadow model is guilty until proven useful out of sample.

Phase 25 must compare shadow model predictions against simple baselines on the same walk-forward validation windows, using net-return targets only. The promotion gate may advance a candidate only if the shadow model beats the baseline after costs, across enough windows, without safety violations.

## 3. Non-Goals

Phase 25 must not:

- train models
- tune hyperparameters
- alter P25-D artifacts
- write production configs
- write canonical factor snapshots
- write live trade signals
- auto-promote a model
- auto-register new experiments
- auto-revoke existing experiments
- read raw price files
- compute forward returns from prices
- import model libraries such as `xgboost`, `sklearn`, `torch`, `tensorflow`, `stable_baselines3`, `numpy`, or `pandas`

## 4. Inputs

### 4.1 `ShadowTrainingRunResult`

Required fields:

- `manifest`
- `window_artifacts`

The manifest must provide:

- `training_run_id`
- `experiment_id`
- `dataset_id`
- `split_id`
- `candidate_namespace`
- `model_family`
- `training_mode`
- `target_name`
- `completed_windows`
- `blocked_windows`
- `failed_windows`
- `safety_flags`
- `schema_version`

Each artifact must provide:

- `window_id`
- `train_snapshot_ids`
- `validation_snapshot_ids`
- `predictions`
- `training_status`

Each prediction must provide:

- `snapshot_id`
- `prediction_value`
- `prediction_rank`
- `target_name`
- `actual_target_value`
- `trading_day`

### 4.2 Baseline predictions

Baseline predictions may be provided as:

- a second `ShadowTrainingRunResult` from a `dry_run` or prior baseline
- a list of baseline prediction rows
- omitted, in which case Phase 25 must build deterministic zero-score and equal-rank baselines from the shadow artifacts

A baseline row must provide:

- `window_id`
- `snapshot_id`
- `baseline_prediction_value`
- `baseline_prediction_rank`

### 4.3 `Phase25EvaluationRequest`

Required fields:

- `evaluation_id`
- `training_run_id`
- `experiment_id`
- `candidate_namespace`
- `primary_metric`
- `min_completed_windows`
- `min_validation_predictions`
- `min_rank_ic_improvement`
- `min_hit_rate_improvement`
- `max_allowed_safety_violations`
- `promotion_review_enabled`
- `notes`

Accepted values:

```text
candidate_namespace starts with "shadow_meta_model."
primary_metric in {"rank_ic", "directional_hit_rate", "spread_return"}
min_completed_windows >= 4
min_validation_predictions >= 20
promotion_review_enabled == true
max_allowed_safety_violations == 0
```

## 5. Outputs

### 5.1 `WindowEvaluationResult`

Required fields:

- `evaluation_id`
- `training_run_id`
- `window_id`
- `candidate_namespace`
- `validation_prediction_count`
- `model_rank_ic`
- `baseline_rank_ic`
- `rank_ic_improvement`
- `model_directional_hit_rate`
- `baseline_directional_hit_rate`
- `hit_rate_improvement`
- `model_spread_return`
- `baseline_spread_return`
- `spread_return_improvement`
- `status`
- `warnings`

### 5.2 `ShadowModelEvaluationReport`

Required fields:

- `schema_version`: `phase25_model_evaluation.0`
- `evaluation_id`
- `training_run_id`
- `experiment_id`
- `candidate_namespace`
- `model_family`
- `total_windows`
- `evaluated_windows`
- `blocked_windows`
- `total_validation_predictions`
- `aggregate_model_rank_ic`
- `aggregate_baseline_rank_ic`
- `aggregate_rank_ic_improvement`
- `aggregate_model_hit_rate`
- `aggregate_baseline_hit_rate`
- `aggregate_hit_rate_improvement`
- `aggregate_model_spread_return`
- `aggregate_baseline_spread_return`
- `aggregate_spread_return_improvement`
- `window_results`
- `safety_violations`
- `warnings`
- `created_at`

### 5.3 `PromotionReadinessDecision`

Required fields:

- `schema_version`: `phase25_promotion_readiness.0`
- `evaluation_id`
- `training_run_id`
- `experiment_id`
- `candidate_namespace`
- `decision`
- `decision_reasons`
- `required_observation_windows`
- `production_config_changes`
- `apply_to_production`
- `next_phase_recommendation`
- `created_at`

Accepted decision values:

```text
blocked_by_safety
blocked_by_sample_size
rejected_underperforms_baseline
watch_more_windows
ready_for_phase26_shadow_portfolio
```

`production_config_changes` must always be empty.

`apply_to_production` must always be false.

### 5.4 `Phase25GovernanceResult`

Required fields:

- `evaluation_report`
- `readiness_decision`

### 5.5 Required function

```python
evaluate_shadow_model_governance(training_result, baseline_predictions, request) -> Phase25GovernanceResult
```

The function must be read-only and pure with respect to production state.

## 6. Metric Rules

### 6.1 Rank IC

For each window, compute Spearman-style rank correlation between model prediction ranks and actual target ranks.

If fewer than two validation predictions exist in a window, mark the window blocked with `insufficient_validation_predictions`.

### 6.2 Directional hit rate

For each prediction:

```text
predicted direction = sign(prediction_value)
actual direction = sign(actual_target_value)
```

Zero predictions count as neutral and should not be credited as correct unless actual target is exactly zero.

### 6.3 Spread return

For each window:

```text
spread_return = average target of top half by prediction - average target of bottom half by prediction
```

If the validation count is odd, the middle observation is ignored.

### 6.4 Baseline comparison

Every model metric must have a baseline metric computed on the same window and same validation snapshot IDs.

If a supplied baseline is missing any validation snapshot ID, block evaluation with `baseline_snapshot_missing`.

## 7. Safety Rules

Phase 25 must block readiness if:

- training result has `blocked_windows > 0`
- training result has `failed_windows > 0`
- training manifest safety flags are not all true
- training target is not `net_return_pct`
- candidate namespace mismatch exists between training result and request
- experiment ID mismatch exists between training result and request
- total completed windows is below `min_completed_windows`
- total validation predictions is below `min_validation_predictions`
- baseline predictions do not cover the same validation IDs

## 8. Readiness Gate Rules

Decision logic must be gated, not weighted-sum.

Order:

1. If safety violation exists -> `blocked_by_safety`
2. Else if sample requirements fail -> `blocked_by_sample_size`
3. Else if aggregate improvement is negative or zero on primary metric -> `rejected_underperforms_baseline`
4. Else if improvement is positive but below configured thresholds -> `watch_more_windows`
5. Else -> `ready_for_phase26_shadow_portfolio`

Thresholds:

```text
rank_ic_improvement >= min_rank_ic_improvement
hit_rate_improvement >= min_hit_rate_improvement
```

For `primary_metric == "spread_return"`, spread improvement must be positive and rank/hit-rate improvements must not be materially negative.

## 9. Serialization Rules

All contracts must expose `to_dict()` returning JSON-serializable dictionaries/lists/scalars.

No output may contain binary models, functions, class objects, numpy arrays, pandas frames, or mutable mapping proxies.

## 10. Tests Required

Acceptance tests must cover:

1. request validation
2. evaluation blocks unsafe training result
3. evaluation blocks target not net
4. evaluation blocks namespace mismatch
5. supplied baseline must cover all validation IDs
6. zero baseline is generated when baseline input is omitted
7. per-window rank IC is computed
8. per-window hit rate is computed
9. per-window spread return is computed
10. aggregate improvements are computed
11. sample-size gate blocks insufficient windows
12. underperforming model is rejected
13. marginal positive model returns watch-more decision
14. strong model returns ready-for-phase26 decision
15. production_config_changes always empty
16. apply_to_production always false
17. JSON serialization works
18. no model libraries imported

## 11. Acceptance Checklist

A valid Phase 25 handoff must report:

- evaluation request contract exists: yes/no
- window evaluation contract exists: yes/no
- evaluation report contract exists: yes/no
- promotion readiness decision contract exists: yes/no
- consumes P25-D training result: yes/no
- baseline comparison implemented: yes/no
- rank IC implemented: yes/no
- hit rate implemented: yes/no
- spread return implemented: yes/no
- safety violations block readiness: yes/no
- sample-size gate implemented: yes/no
- underperformance rejected: yes/no
- ready-for-phase26 decision gated: yes/no
- production_config_changes empty: yes/no
- apply_to_production false: yes/no
- JSON serialization works: yes/no
- no model libraries imported: yes/no
- P20-P25 regression green: yes/no

## 12. Boundary to Phase 26

Phase 25 may produce `ready_for_phase26_shadow_portfolio`.

That is not production approval. It only permits Phase 26 to test portfolio-level behavior in shadow simulation.
