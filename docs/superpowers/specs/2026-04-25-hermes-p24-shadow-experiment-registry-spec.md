# P24-B Shadow Experiment Registry Spec

Date: 2026-04-25
Status: Draft for engineering handoff
Scope: P24 shadow experiment registration for advanced model and factor-plugin candidates

## 1. Purpose

P24-A answered one question: which advanced candidates are allowed to enter shadow development?

P24-B answers the next question: once a candidate is admitted, how do we register it as an auditable shadow experiment without letting it train blindly, write canonical factor outputs, or mutate production configuration?

The Shadow Experiment Registry is an experiment manifest layer. It does not train models, does not compute model predictions, and does not promote anything to production. It records the contract under which a candidate may later run in shadow mode.

## 2. Core Principle

No advanced model may run unless it has both:

1. a passing `ModelAdmissionGateReport` from P24-A
2. a registered `ShadowExperimentManifest` from P24-B

Gate report says: "This candidate may enter the lab."

Manifest says: "This is exactly what it may read, write, compare against, and report."

## 3. Non-Goals

P24-B must not:

- train XGBoost, GNN, LSTM, Transformer, PPO, or LLM models
- import model libraries such as `xgboost`, `torch`, `tensorflow`, `sklearn`, or RL libraries
- persist predictions into canonical `FactorSnapshot`
- write production calibration configs
- change thesis classification, trade plans, exits, sizing, or portfolio behavior
- create live trading or auto-trading hooks
- evaluate financial performance beyond static manifest validation

## 4. Inputs

### 4.1 `ModelAdmissionGateReport`

Registration requires a P24-A gate report with:

```text
passed == true
production_write_blocked == true
schema_version starts with "p24_gate."
candidate_name is non-empty
candidate_family is supported
candidate_namespace is allowed
blocking_reasons is empty
```

Reports with warnings may still register, but the warnings must be copied into the manifest.

### 4.2 `ShadowExperimentRequest`

Required fields:

- `experiment_id`
- `candidate_id`
- `candidate_name`
- `candidate_family`
- `candidate_namespace`
- `source_gate_report_id`
- `owner`
- `purpose`
- `input_contract`
- `output_contract`
- `forbidden_outputs`
- `training_data_window`
- `point_in_time_policy`
- `baseline_comparison_plan`
- `out_of_sample_validation_plan`
- `observation_plan`
- `resource_policy`
- `expected_artifacts`
- `notes`

## 5. Output Contract

### `ShadowExperimentManifest`

Required fields:

- `schema_version`: `p24_manifest.0`
- `experiment_id`
- `candidate_id`
- `candidate_name`
- `candidate_family`
- `candidate_namespace`
- `source_gate_report_id`
- `source_gate_schema_version`
- `status`: `registered`, `rejected`, `revoked`, or `archived`
- `owner`
- `purpose`
- `input_contract`
- `output_contract`
- `forbidden_outputs`
- `training_data_window`
- `point_in_time_policy`
- `baseline_comparison_plan`
- `out_of_sample_validation_plan`
- `observation_plan`
- `resource_policy`
- `expected_artifacts`
- `promotion_blocked`: must be `true`
- `production_write_blocked`: must be `true`
- `canonical_snapshot_write_blocked`: must be `true`
- `shadow_namespace`
- `gate_warnings`
- `blocking_reasons`
- `registered_at`
- `notes`

## 6. Required Manifest Subcontracts

### 6.1 Input contract

`input_contract` must declare:

- `allowed_sources`
- `required_point_in_time_fields`
- `forbidden_sources`
- `max_source_audit_gap_rate`
- `lookahead_policy`

Minimum accepted values:

```text
allowed_sources is non-empty
required_point_in_time_fields is non-empty
max_source_audit_gap_rate <= 0.20
lookahead_policy == "strict_no_future_data"
```

### 6.2 Output contract

`output_contract` must declare:

- `allowed_outputs`
- `output_namespace`
- `writes_canonical_factor_snapshot`
- `writes_production_config`
- `affects_live_trading`
- `return_basis`

Accepted values:

```text
output_namespace starts with candidate_namespace
writes_canonical_factor_snapshot == false
writes_production_config == false
affects_live_trading == false
return_basis == "net"
```

### 6.3 Forbidden outputs

`forbidden_outputs` must include:

- `company_quality_score`
- `valuation_attractiveness_score`
- `timing_market_fit_score`
- `llm_adjustment_total`
- `classification`
- `production_config`
- `canonical_factor_snapshot`
- `live_trade_signal`

### 6.4 Training data window

`training_data_window` must declare:

- `start_date`
- `end_date`
- `minimum_observations`
- `purged_validation_gap_days`
- `embargo_days`
- `point_in_time_membership_required`

Accepted values:

```text
minimum_observations >= 500 for xgboost_meta_model
purged_validation_gap_days >= 1
embargo_days >= 1
point_in_time_membership_required == true
```

For non-XGBoost families, `minimum_observations` may be lower only if the gate report admitted the family for exploratory shadow development. The manifest must still record the value explicitly.

### 6.5 Baseline comparison plan

`baseline_comparison_plan` must declare:

- `baseline_name`
- `baseline_type`
- `primary_metric`
- `secondary_metrics`
- `comparison_direction`
- `minimum_evaluation_windows`

Accepted values:

```text
baseline_name is non-empty
primary_metric in ["net_ic", "net_icir", "cost_reduction_bps", "net_return_spread"]
minimum_evaluation_windows >= 4
```

### 6.6 Out-of-sample validation plan

`out_of_sample_validation_plan` must declare:

- `method`
- `walk_forward_enabled`
- `holdout_periods`
- `leakage_checks`
- `promotion_criteria_documented`

Accepted values:

```text
walk_forward_enabled == true
holdout_periods is non-empty
leakage_checks includes "point_in_time"
leakage_checks includes "purged_embargo"
promotion_criteria_documented == true
```

### 6.7 Observation plan

`observation_plan` must declare:

- `observation_frequency`
- `minimum_shadow_windows`
- `required_reports`
- `revocation_triggers`

Accepted values:

```text
minimum_shadow_windows >= 4
required_reports includes "ModelAdmissionGateReport"
required_reports includes "ShadowExperimentManifest"
required_reports includes "ShadowObservationReport"
revocation_triggers is non-empty
```

## 7. Registry Behavior

### 7.1 Register

`register_shadow_experiment(request, gate_report)` must:

1. validate the gate report
2. validate all manifest subcontracts
3. reject unsafe output paths
4. generate `ShadowExperimentManifest`
5. store it in an in-memory registry object
6. return the manifest

The v1 registry may be in-memory only. Persistence can be added after the manifest contract is stable.

### 7.2 Reject

If validation fails, the registry must return a manifest-like rejection record or raise a typed `ShadowExperimentRegistrationError`.

The implementation plan should use a typed exception for invalid registration attempts, because rejection means the experiment must not appear in the active registry.

### 7.3 Query

The registry must support:

- `get_experiment(experiment_id)`
- `list_experiments(status=None, candidate_family=None)`
- `list_active_experiments(candidate_family=None)`
- `get_experiment_history(experiment_id)`
- `revoke_experiment(experiment_id, reason)`
- `archive_experiment(experiment_id, reason)`

`active` means `status == "registered"`.

### 7.4 Immutability

Registered manifests are immutable. Revocation and archival must create a new manifest record with changed `status` and appended note/reason, not mutate fields in place.

The registry must preserve version history. `get_experiment(experiment_id)` returns the latest manifest; `get_experiment_history(experiment_id)` returns every manifest version in registration order.

## 8. Safety Rules

The registry must block:

- failed gate reports
- gate reports with non-empty `blocking_reasons`
- manifests whose `candidate_namespace` differs from the gate report namespace
- manifests whose `source_gate_report_id` is empty
- output namespaces outside the candidate namespace
- canonical factor snapshot writes
- production config writes
- live trading effects
- gross-return-primary output contracts
- missing baseline plans
- missing out-of-sample plans
- missing revocation triggers

## 9. Tests

Acceptance tests must cover:

1. passing gate report registers a manifest
2. failed gate report cannot register
3. namespace mismatch is blocked
4. canonical snapshot writes are blocked
5. production config writes are blocked
6. gross-return-primary output contract is blocked
7. missing baseline plan is blocked
8. missing out-of-sample leakage checks are blocked
9. registered manifests are queryable by family
10. revocation preserves the experiment but removes it from active list
11. revocation preserves manifest history
12. required forbidden outputs are enforced
13. no model libraries are imported

## 10. Acceptance Checklist

- `ShadowExperimentManifest` contract exists.
- Registration requires a passing P24 gate report.
- Failed candidates cannot enter active registry.
- Manifest records source gate identity.
- Input contract enforces point-in-time and source audit rules.
- Output contract blocks canonical snapshots, production configs, and live trading effects.
- Baseline and OOS plans are mandatory.
- Observation plan requires at least four shadow windows.
- Registry supports query by candidate family.
- Revocation preserves audit history through `get_experiment_history`.
- No model training or model-library imports are introduced.

## 11. Boundary to P24-C

P24-B ends at registration.

P24-C may implement shadow experiment execution scaffolding, but only after P24-B makes every candidate auditable. P24-C still must not promote outputs to production.
