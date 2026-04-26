# P22 Validity Diagnostics Spec

Date: 2026-04-25
Status: Draft for engineering handoff
Scope: Hermes `agent/research_v1` P22 validity-first diagnostics layer after P20 factor persistence and P21 calibration-input acceptance

## 1. Purpose

P22 answers one question:

> Do Hermes factor signals show statistically useful forward-return relationships after costs, using only point-in-time logged observations?

P22 must not tune production parameters. It must not update weights, thresholds, exits, sizing, valuation benchmarks, or thesis gates. Its job is to produce an auditable validity report that says which factors, horizons, and universes are ready for future calibration and which remain `prior_only`.

P22 is therefore a diagnostics phase, not a calibration phase.

## 2. Core Decision

Hermes will implement P22-A: validity-first diagnostics.

P22 consumes only:

- `FactorSnapshot`
- `ForwardReturnObservation`
- `UniverseMembershipSnapshot` where needed for point-in-time universe context

P22 must not read raw price history directly. Forward returns must already exist as persisted observations. The default return basis is `net_return_pct`; `gross_return_pct` is available only for comparison.

## 3. Non-Goals

P22 does not:

- modify production configs
- produce `calibration_status = "calibrated"`
- run shrinkage updates
- create portfolio optimization
- add autonomous trading
- add bearish trade execution
- claim profitability from gross returns alone
- infer missing forward returns from live prices
- backfill historical factor snapshots outside the P20 contract

## 4. Inputs

### 4.1 Factor snapshot rows

Required factor columns:

- `snapshot_id`
- `ticker`
- `trading_day`
- `universe_membership_snapshot_id`
- `company_quality_score`
- `valuation_attractiveness_score`
- `timing_market_fit_score`
- `llm_adjustment_total`
- `negative_signal_strength_decile`
- coverage fields
- classification fields
- `sector_id`
- `size_decile`

P22 v1 factor list:

- `company_quality_score`
- `valuation_attractiveness_score`
- `timing_market_fit_score`
- `llm_adjustment_total`
- `negative_signal_strength_decile` when present

### 4.2 Forward return observations

Required return columns:

- `snapshot_id`
- `ticker`
- `trading_day`
- `horizon_days`
- `gross_return_pct`
- `net_return_pct`
- `transaction_cost_pct`
- `cost_source`
- `observation_status`

P22 must exclude rows where `observation_status` is not `None` or `"computed"` unless a diagnostic explicitly counts missing-return rates.

### 4.3 Return basis

Default basis:

```text
net
```

Allowed bases:

```text
net
gross
```

All primary readiness gates use net returns. Gross metrics are side-by-side diagnostics only.

## 5. Diagnostics

### 5.1 Information coefficient

For each factor and horizon:

```text
IC = corr(factor_score_t, forward_return_t_to_t+h)
```

P22 v1 may use Pearson correlation as the default. Spearman rank IC may be added as a secondary field if inexpensive, but Pearson net IC is required.

### 5.2 ICIR

For each factor and horizon, compute ICIR as:

```text
ICIR = mean(periodic_ic_series) / std(periodic_ic_series)
```

If there is only one period or zero standard deviation, ICIR must return `0.0` and include an insufficient-period flag.

### 5.3 IC decay

For each factor, compare IC across horizons:

- 1 trading day
- 5 trading days
- 21 trading days
- 63 trading days

P22 should report the horizon with strongest absolute net IC and whether the signal appears short-horizon, medium-horizon, long-horizon, or unstable.

### 5.4 Gross vs net comparison

For each factor and horizon, report:

- `gross_ic`
- `net_ic`
- `cost_impact_on_ic = gross_ic - net_ic`

If gross IC is positive but net IC is near zero or negative, mark `cost_fragile = true`.

### 5.5 Autocorrelation

For each factor, compute lag-1 autocorrelation by ticker over time where enough observations exist.

Purpose:

- detect stale factors
- identify signals that barely change
- inform future rebalance cadence

### 5.6 Orthogonality

Compute cross-factor correlation over aligned snapshot rows.

Required pairs:

- quality vs valuation
- quality vs timing
- valuation vs timing
- each primary factor vs LLM overlay

If absolute correlation exceeds `0.70`, mark pair as `highly_correlated`.

### 5.7 Missing-return rate

For each horizon:

```text
missing_return_rate = missing_or_noncomputed_observations / expected_observations
```

If missing return rate is too high, readiness must fail regardless of IC magnitude.

## 6. Readiness Gates

P22 readiness is data-gated. It must not infer readiness from small samples.

Default P22 v1 gate thresholds:

- `min_observations`: 60
- `min_unique_tickers`: 10
- `min_periods_for_icir`: 6
- `max_missing_return_rate`: 0.20
- `min_abs_net_ic_for_watch`: 0.03
- `min_abs_net_ic_for_ready`: 0.05
- `max_abs_factor_correlation`: 0.70
- `min_newey_west_t_stat_for_ready`: 1.50

P22 v1 may implement Newey-West/HAC t-stat as a simple helper with lag selection `floor(sqrt(n_periods))`. If HAC is not implemented in v1, readiness must remain `false` and report `hac_status = "not_implemented"`. The preferred implementation is to include a small dependency-free Newey-West estimator.

Readiness statuses:

- `insufficient_sample`
- `missing_returns_too_high`
- `weak_net_ic`
- `hac_tstat_too_low`
- `orthogonality_warning`
- `ready_for_shadow_calibration`

Important: `ready_for_shadow_calibration` does not mean production calibration. It means P23 may generate shadow shrinkage recommendations.

## 7. Output Contracts

### 7.1 `FactorMetricResult`

Required fields:

- `factor_name`
- `horizon_days`
- `sample_size`
- `unique_tickers`
- `gross_ic`
- `net_ic`
- `cost_impact_on_ic`
- `icir`
- `newey_west_t_stat`
- `missing_return_rate`
- `readiness_status`
- `ready_for_shadow_calibration`
- `diagnostic_flags`

### 7.2 `OrthogonalityResult`

Required fields:

- `factor_a`
- `factor_b`
- `correlation`
- `sample_size`
- `highly_correlated`

### 7.3 `FactorDecayResult`

Required fields:

- `factor_name`
- `ic_by_horizon`
- `best_horizon_days`
- `decay_profile`

Allowed decay profiles:

- `short_horizon`
- `medium_horizon`
- `long_horizon`
- `unstable`
- `insufficient_data`

### 7.4 `P22ValidityReport`

Required fields:

- `schema_version`: `p22.0`
- `return_basis_default`: `net`
- `factor_metrics`
- `orthogonality_results`
- `decay_results`
- `sample_gate_summary`
- `overall_readiness`
- `generated_at`

`overall_readiness` may be true only if at least one factor-horizon pair is `ready_for_shadow_calibration` and no blocking data-quality issue exists.

## 8. Implementation Boundaries

P22 should be implemented in focused modules:

- `factor_diagnostics.py`: correlation, IC, ICIR, decay, orthogonality, report assembly
- `diagnostic_gates.py`: sample gates and readiness logic
- `newey_west.py`: dependency-free HAC/Newey-West t-stat helper

Existing `p22_return_selector.py` should remain the single source for net/gross return selection.

## 9. Acceptance Criteria

P22 is accepted only if:

1. Diagnostics consume factor snapshots and forward return observations, not raw prices.
2. Net returns are the default return basis.
3. Gross IC is reported only as comparison.
4. IC, ICIR, decay, orthogonality, autocorrelation, and missing-return diagnostics exist.
5. Sample-size gates prevent readiness on small samples.
6. HAC/Newey-West t-stat is implemented or readiness remains blocked with explicit `hac_status`.
7. No production calibration configs are modified.
8. No default `calibration_status` changes to `calibrated`.
9. Tests cover positive IC, negative IC, insufficient sample, cost-fragile signal, high factor correlation, and net-default behavior.
10. P20/P21 regression tests continue to pass.

## 10. Review Checklist

Reject the implementation if:

- any diagnostic reads raw price history
- net returns are not the default
- small samples can pass readiness
- gross IC can make a factor ready when net IC fails
- high factor correlation is ignored
- production weights, thresholds, exits, or sizing configs are changed
- HAC/Newey-West absence is hidden
- tests use only happy-path synthetic data
