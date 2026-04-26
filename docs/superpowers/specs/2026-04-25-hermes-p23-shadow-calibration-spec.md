# P23 Shadow Calibration Spec

Date: 2026-04-25
Status: Draft for engineering handoff
Scope: Hermes `agent/research_v1` P23 shadow-only calibration recommendation layer after P22-A+ validity diagnostics acceptance

## 1. Purpose

P23 generates shadow calibration recommendations from P22-A+ diagnostics without changing production behavior.

P23 answers:

> If a factor-horizon pair has passed P22-A+ validity gates, what parameter changes would Hermes recommend in shadow mode, and how strongly should those recommendations be trusted?

P23 must remain non-authoritative. It may recommend changes to weights, thresholds, and exit multiples, but it must not apply them to production configs and must not set production `calibration_status` to `calibrated`.

## 2. Core Decision

Hermes will implement shadow-only shrinkage calibration:

```text
shadow_value = delta * prior_value + (1 - delta) * data_suggested_value
```

Where:

- `prior_value` comes from P21 prior-only config
- `data_suggested_value` comes from P22-A+ validated diagnostics
- `delta` is the shrinkage strength toward the prior
- high uncertainty means larger `delta`
- strong validated evidence allows smaller `delta`

P23 output is a `ShadowCalibrationReport`, not a production config patch.

## 3. Non-Goals

P23 does not:

- mutate `calibration_config.py`
- set production defaults to `calibrated`
- automatically update role weights, thesis thresholds, exit multiples, or position sizing
- implement portfolio optimization
- run live trading or auto-trading
- create a full strategy backtest engine
- bypass P22-A+ readiness gates
- use gross IC as a readiness basis
- recommend calibration from lookahead-contaminated or source-audit-failed data

## 4. Inputs

P23 consumes P22-A+ report payloads or equivalent result objects.

Required input sections:

- `data_integrity_report`
- `factor_metrics`
- `orthogonality_results`
- `calibration_readiness_report`
- `daily_health_report`
- `return_basis_default`

Required `factor_metrics` fields:

- `factor_name`
- `horizon_days`
- `sample_size`
- `unique_tickers`
- `net_ic`
- `gross_ic`
- `icir`
- `newey_west_t_stat`
- `missing_return_rate`
- `readiness_status`
- `ready_for_shadow_calibration`
- `diagnostic_flags`

P23 must ignore factor-horizon pairs unless `ready_for_shadow_calibration` is true.

## 5. Output Contracts

### 5.1 `ShadowCalibrationRecommendation`

Required fields:

- `parameter_family`: `role_weight`, `thesis_threshold`, `exit_multiple`, or `ranking_hint`
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
- `readiness_status`
- `calibration_status`: always `shadow_only`
- `apply_to_production`: always `false`
- `diagnostic_flags`
- `human_reason`

### 5.2 `ShadowCalibrationReport`

Required fields:

- `schema_version`: `p23.0`
- `mode`: `shadow_only`
- `generated_at`
- `source_report_schema_version`
- `recommendations`
- `blocked_candidates`
- `global_warnings`
- `production_config_changes`: always empty list
- `overall_status`

Allowed `overall_status` values:

- `no_ready_factors`
- `shadow_recommendations_available`
- `blocked_by_data_integrity`
- `blocked_by_health_check`

## 6. Evidence Strength and Shrinkage

### 6.1 Evidence strength

P23 should compute evidence strength from:

- absolute net IC
- absolute Newey-West t-stat
- sample size
- missing return rate
- orthogonality warning flags
- cost fragility flags

A simple v1 scoring formula is acceptable:

```text
evidence_strength = clamp(
    0.40 * min(abs(net_ic) / 0.10, 1.0)
  + 0.30 * min(abs(newey_west_t_stat) / 3.0, 1.0)
  + 0.20 * min(sample_size / 240, 1.0)
  + 0.10 * (1 - missing_return_rate),
  0.0,
  1.0
)
```

Penalties:

- subtract `0.20` if `cost_fragile`
- subtract `0.20` if `orthogonality_warning`
- subtract `0.30` if daily health status is `critical`

### 6.2 Delta selection

P23 v1 delta rule:

```text
delta = clamp(1.0 - evidence_strength, 0.25, 0.90)
```

This means:

- weak evidence stays close to prior
- strong evidence may move up to 75% toward data suggestion
- no shadow recommendation can fully override prior

## 7. Supported Shadow Recommendation Families

### 7.1 Ranking hints

Ranking hints are safest and should be implemented first.

Example:

```text
factor company_quality_score @ 63d has positive net IC and passes HAC
recommend increasing its ranking influence in shadow ranking model
```

No production ranking model is modified in P23.

### 7.2 Role weight hints

P23 may map factor diagnostics to role-weight hints:

- `company_quality_score` -> `fundamentals`
- `valuation_attractiveness_score` -> `valuation`
- `timing_market_fit_score` -> `technical`
- `llm_adjustment_total` -> `sentiment` or `news` depending on future source mapping

P23 must not directly overwrite `RoleWeightConfig`.

### 7.3 Thesis threshold hints

P23 may recommend threshold movement only as a shadow suggestion.

Rules:

- positive validated quality IC may suggest raising quality importance or tightening low-quality rejection
- weak or negative valuation IC may suggest not loosening valuation threshold
- recommendations must include a conservative max move cap

Default max threshold move:

```text
0.05 absolute threshold units
```

### 7.4 Exit multiple hints

P23 may recommend shadow exit multiple adjustments only when timing factor has validated short-horizon net IC.

Rules:

- timing validated at 1d/5d can suggest tighter or more responsive exits
- quality/valuation long-horizon factors should not drive short-term exit multiples
- max move cap: `0.25` multiple units

## 8. Safety Rules

P23 must enforce:

1. No recommendation from non-ready factor-horizon pairs.
2. No recommendation when P22 `return_basis_default` is not `net`.
3. No recommendation when data integrity report has lookahead violations above threshold.
4. No production config mutation.
5. No `calibrated` production status.
6. All recommendations must be reversible and auditable.
7. Every blocked candidate must include a blocking reason.

## 9. Acceptance Criteria

P23 is accepted only if:

1. Shadow reports are generated from P22-A+ report payloads.
2. Non-ready factors are blocked and recorded.
3. Recommendations use net IC, not gross IC.
4. Shrinkage formula is implemented with bounded delta.
5. Evidence strength includes sample size, HAC t-stat, net IC, missing returns, and penalties.
6. Production config changes list is always empty.
7. `apply_to_production` is always false.
8. No production config is modified.
9. Tests cover ready factor recommendation, blocked non-ready factor, gross-only edge rejection, data-integrity blocking, health-check blocking, and bounded shrinkage.
10. P20/P21/P22 regression tests continue to pass.

## 10. Review Checklist

Reject implementation if:

- production configs are changed
- `calibration_status = "calibrated"` appears in production defaults
- gross IC can drive recommendations when net IC fails
- non-ready factor-horizon pairs produce recommendations
- recommendations lack prior/data/shadow values
- delta can become 0 or 1 without bounds
- blocked candidates are silently dropped
- report omits global warnings for data integrity or health issues
