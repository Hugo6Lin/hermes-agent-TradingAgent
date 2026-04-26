# P23 Shadow Observation Loop Spec

Date: 2026-04-25
Status: Draft for engineering handoff
Scope: Observation and monitoring layer for P23 shadow calibration recommendations

## 1. Purpose

P23 shadow calibration is not complete when a recommendation is generated. It becomes useful only when Hermes observes whether shadow recommendations remain stable and improve over prior-only behavior over time.

This spec defines the P23 Shadow Observation Loop:

```text
ShadowCalibrationReport
  -> persist recommendations
  -> observe future diagnostics / returns
  -> compare shadow vs prior
  -> monitor stability
  -> revoke, continue, or mark eligible for P24 gate
```

The loop is still non-production. It must not apply recommendations to production configs.

## 2. Core Decision

Hermes will persist and monitor P23 shadow recommendations as first-class observation objects.

The observation loop evaluates:

- recommendation stability
- shadow-vs-prior improvement
- evidence degradation
- health degradation
- reversal frequency
- eligibility for P24 entry gates

It does not change production configuration.

## 3. Non-Goals

The observation loop does not:

- mutate `calibration_config.py`
- apply shadow recommendations to production
- mark production configs as `calibrated`
- run portfolio optimization
- train XGBoost/GNN/LSTM/PPO models
- replace P22 diagnostics
- infer returns from raw prices

## 4. Observation Contract

### 4.1 `ShadowRecommendationObservation`

Required fields:

- `recommendation_id`
- `generated_at`
- `source_p22_report_id`
- `source_p23_report_id`
- `parameter_family`
- `parameter_name`
- `factor_name`
- `horizon_days`
- `prior_value`
- `data_suggested_value`
- `shadow_value`
- `delta`
- `evidence_strength`
- `sample_size`
- `net_ic`
- `newey_west_t_stat`
- `diagnostic_flags`
- `observation_status`
- `created_at`
- `updated_at`

Allowed `observation_status` values:

- `active`
- `watch`
- `revoked`
- `expired`
- `eligible_for_p24_gate`

### 4.2 `ShadowObservationEvaluation`

Required fields:

- `evaluation_id`
- `recommendation_id`
- `evaluation_date`
- `evaluation_window`
- `latest_net_ic`
- `latest_newey_west_t_stat`
- `latest_evidence_strength`
- `prior_reference_value`
- `shadow_reference_value`
- `shadow_vs_prior_delta`
- `shadow_outperformed_prior`
- `health_status`
- `reversal_detected`
- `revocation_triggered`
- `diagnostic_flags`

## 5. Shadow vs Prior Comparison

P23 observation should start with ranking-level comparison, not portfolio backtesting.

For each recommendation:

```text
shadow_vs_prior_delta = shadow_metric - prior_metric
```

Allowed v1 metrics:

- net IC improvement
- evidence strength improvement
- readiness status stability
- rank-score proxy improvement when available

Portfolio-level P&L comparison is explicitly deferred.

## 6. Monitoring Report

### 6.1 `ShadowRecommendationMonitorReport`

Required fields:

- `schema_version`: `p23_observation.0`
- `generated_at`
- `active_recommendation_count`
- `watch_recommendation_count`
- `revoked_recommendation_count`
- `expired_recommendation_count`
- `eligible_for_p24_count`
- `average_evidence_strength`
- `shadow_hit_rate`
- `average_shadow_vs_prior_delta`
- `recommendation_reversal_rate`
- `health_degradation_count`
- `recommendations`
- `global_flags`
- `ready_for_p24_gate`

`ready_for_p24_gate` may be true only when:

- at least one recommendation has enough observation windows
- shadow-vs-prior delta is positive
- reversal rate is acceptable
- no critical health degradation is active
- no data integrity blocker is active

## 7. Revocation Rules

Recommendations must be revoked, not silently deleted.

Default revocation triggers:

```text
latest_net_ic < 0.03
latest_newey_west_t_stat < 1.0
health_status == critical
source audit or lookahead blocker appears
recommendation reverses direction twice
shadow underperforms prior for 3 consecutive evaluation windows
```

Revoked recommendations remain in the observation store.

## 8. P24 Gate Relationship

P24 model or factor expansion may only use P23 recommendations if the observation loop marks at least one recommendation:

```text
observation_status = eligible_for_p24_gate
```

Eligibility does not mean production adoption. It only means P24 design work may reference the recommendation as evidence.

## 9. Persistence

P23 observation may start as an in-memory or SQLite-friendly module, but it must expose stable serialization:

- `to_dict()`
- `from_report()`
- deterministic `recommendation_id` or persisted ID

If database persistence is added, it must be additive and idempotent.

## 10. Acceptance Criteria

P23 observation loop is accepted only if:

1. Shadow recommendations can be converted into observation records.
2. Observations preserve source P22/P23 report IDs.
3. Evaluations compare shadow against prior.
4. Revocation triggers are implemented.
5. Revoked recommendations are retained.
6. Monitor report summarizes active/watch/revoked/eligible states.
7. `ready_for_p24_gate` is false until observation evidence is sufficient.
8. No production config is modified.
9. Tests cover active, watch, revoked, and eligible paths.
10. P20/P21/P22/P23 regression tests continue to pass.

## 11. Review Checklist

Reject implementation if:

- recommendations are only kept in transient reports
- revoked recommendations are deleted
- P24 gate can pass without observation windows
- shadow recommendations are applied to production
- gross returns are used as primary evidence
- health or source-audit degradation is ignored
- blocked observations lack reasons

