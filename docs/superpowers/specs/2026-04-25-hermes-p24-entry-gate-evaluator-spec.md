# P24 Entry Gate Evaluator Spec

Date: 2026-04-25
Status: Draft for engineering handoff
Scope: P24 admission evaluator for advanced model and factor-plugin candidates

## 1. Purpose

P24 must begin with a gate evaluator, not model implementation.

The P24 Entry Gate Evaluator decides whether a candidate advanced model or factor plugin is allowed to enter shadow-only P24 development. It does not train models, does not write factor outputs, and does not alter production configuration.

The evaluator produces a `ModelAdmissionGateReport`.

## 2. Core Decision

Every advanced candidate must pass:

1. universal Hermes readiness gates
2. namespace and production-write safety gates
3. point-in-time source gates
4. simple-baseline gates
5. candidate-family-specific gates

No candidate may proceed without `passed = true`.

## 3. Candidate Families

Supported v1 candidate families:

- `xgboost_meta_model`
- `llm_event_surprise_factor`
- `macro_regime_factor`
- `relation_model`
- `sequence_timing_model`
- `ppo_execution_model`

## 4. Inputs

### 4.1 `P24CandidateRequest`

Required fields:

- `candidate_name`
- `candidate_family`
- `candidate_namespace`
- `requested_phase`
- `intended_outputs`
- `uses_point_in_time_sources`
- `source_audit_plan_defined`
- `simple_baseline_defined`
- `out_of_sample_plan_defined`
- `uses_gross_returns_as_primary`
- `writes_production_fields`
- `requires_portfolio_layer`
- `requires_execution_data`
- `notes`

### 4.2 System evidence

Required evidence payload:

- `p20_accepted`
- `p21_accepted`
- `p22_accepted`
- `p23_accepted`
- `return_basis_default`
- `lookahead_violation_rate`
- `source_audit_gap_rate`
- `ready_for_p24_gate`
- `ready_factor_count`
- `core_factors_with_net_icir_gt_030`
- `ready_factor_horizon_count`
- `max_abs_cross_factor_correlation`
- `independent_cross_sectional_observations`
- `regime_gate_has_return_separation`
- `portfolio_layer_exists`
- `execution_dataset_exists`

## 5. Universal Gate

The universal gate passes only if:

```text
p20_accepted == true
p21_accepted == true
p22_accepted == true
p23_accepted == true
return_basis_default == "net"
lookahead_violation_rate == 0.0
source_audit_gap_rate <= 0.20
ready_for_p24_gate == true
candidate_namespace is allowed
writes_production_fields == false
uses_point_in_time_sources == true
source_audit_plan_defined == true
simple_baseline_defined == true
out_of_sample_plan_defined == true
uses_gross_returns_as_primary == false
```

Allowed namespaces:

- `candidate_macro.*`
- `candidate_event.*`
- `candidate_relation.*`
- `candidate_timing_sequence.*`
- `shadow_meta_model.*`

Forbidden production fields:

- `company_quality_score`
- `valuation_attractiveness_score`
- `timing_market_fit_score`
- `llm_adjustment_total`
- `classification`

## 6. Candidate-Specific Gates

### 6.1 XGBoost meta-model

Pass conditions:

```text
core_factors_with_net_icir_gt_030 >= 3
ready_factor_horizon_count >= 2
max_abs_cross_factor_correlation < 0.70 or residualization_plan_defined == true
independent_cross_sectional_observations >= 500
candidate_namespace starts with shadow_meta_model.
```

### 6.2 LLM event surprise factor

Pass conditions:

```text
candidate_namespace starts with candidate_event.
event_taxonomy_defined == true
label_consistency_score >= 0.80
event_timestamp_policy_defined == true
bounded_overlay_preserved == true
```

### 6.3 Macro regime factor

Pass conditions:

```text
candidate_namespace starts with candidate_macro.
macro_source_point_in_time == true
feature_frequency_matches_horizon == true
forward_fill_policy_defined == true
regime_gate_has_return_separation == true or exploratory_mode == true
```

### 6.4 Relation model

Pass conditions:

```text
candidate_namespace starts with candidate_relation.
point_in_time_relation_graph == true
relation_group_count > 15
average_tickers_per_group > 10
simple_relation_baseline_tested == true
```

### 6.5 Sequence timing model

Pass conditions:

```text
candidate_namespace starts with candidate_timing_sequence.
timing_factor_weak_or_unstable == true
simple_timing_baselines_tested == true
walk_forward_validation_defined == true
sequence_history_sufficient == true
```

### 6.6 PPO execution model

Pass conditions:

```text
portfolio_layer_exists == true
execution_dataset_exists == true
candidate_namespace starts with candidate_execution. or candidate_namespace starts with shadow_execution.
ppo_objective == "execution_cost_reduction"
affects_stock_selection == false
```

PPO should almost always fail until Hermes reaches portfolio/execution maturity.

## 7. Output Contract

### `ModelAdmissionGateReport`

Required fields:

- `schema_version`: `p24_gate.0`
- `candidate_name`
- `candidate_family`
- `candidate_namespace`
- `requested_phase`
- `universal_gate_status`
- `model_specific_gate_status`
- `passed`
- `blocking_reasons`
- `warnings`
- `required_evidence`
- `available_evidence`
- `simple_baseline_defined`
- `point_in_time_status`
- `shadow_only_confirmed`
- `production_write_blocked`: must be `true` whenever the evaluator enforces the P24 rule that candidates cannot mutate production configs, canonical factor snapshots, or live trading behavior.
- `reviewer_notes`
- `generated_at`

## 8. Acceptance Criteria

Accepted implementation must:

1. Evaluate all supported candidate families.
2. Block candidates when P23 observation is not ready for P24.
3. Block production field writes.
4. Block missing point-in-time source policy.
5. Block gross-return-primary candidates.
6. Require simple baselines.
7. Require out-of-sample plans.
8. Block PPO when portfolio/execution layer is absent.
9. Produce auditable blocking reasons.
10. Avoid training or importing model libraries.

## 9. Review Checklist

Reject implementation if:

- it trains a model
- it imports XGBoost, torch, tensorflow, or RL libraries
- it writes factor outputs
- it mutates production config
- it permits production field writes
- it passes candidates without `ready_for_p24_gate`
- it has silent default pass behavior
