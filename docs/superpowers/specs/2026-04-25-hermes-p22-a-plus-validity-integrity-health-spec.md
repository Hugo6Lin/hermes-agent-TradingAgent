# P22-A+ Validity, Integrity, and Health Spec

Date: 2026-04-25
Status: Draft for engineering handoff
Scope: Hermes `agent/research_v1` P22-A+ diagnostics layer after P20 factor persistence and P21 calibration-input acceptance

## 1. Purpose

P22-A+ moves Hermes from a calibration-ready system to a validated factor diagnostics system.

The goal is not to improve trading performance directly. The goal is to determine whether Hermes factors, gates, and forward-return observations are reliable enough to support future shadow calibration.

P22-A+ has three responsibilities:

1. Data integrity preflight: detect lookahead risk, source audit gaps, restatement risk, and missing point-in-time classifications before IC is trusted.
2. Factor validity diagnostics: compute gross/net IC, ICIR, IC decay, Newey-West/HAC t-statistics, autocorrelation, orthogonality, and readiness gates.
3. Daily health reporting: detect factor distribution drift, gate pass-rate drift, and forward-return completion issues.

P22-A+ must remain read-only with respect to production calibration. It must not update weights, thresholds, exits, sizing, valuation benchmarks, regime gates, or any production config.

## 2. Core Decision

Hermes will implement P22-A+:

```text
Data Integrity Preflight
    -> Factor Diagnostics Engine
    -> Calibration Readiness Report
    -> Daily Factor Health Check
```

P22-A+ consumes only point-in-time logged data:

- `FactorSnapshot`
- `ForwardReturnObservation`
- `UniverseMembershipSnapshot`
- source metadata already attached to snapshots, source refs, or diagnostic rows

P22-A+ must not read raw price history directly. Forward returns must already exist as persisted observations.

The default return basis is always `net_return_pct`. `gross_return_pct` is reported only for comparison.

## 3. Non-Goals

P22-A+ does not:

- run shrinkage calibration
- set any production config to `calibrated`
- modify `RoleWeightConfig`, `ThesisThresholdConfig`, `ExitPlanConfig`, `PositionSizingConfig`, or `SectorBenchmarkConfig`
- build portfolio optimization
- perform event-driven strategy backtesting
- add real-time market data ingestion
- build a standalone sentiment-monitoring platform
- infer missing forward returns from live or historical prices
- claim profitability from gross returns alone

## 4. P22.0 Data Integrity Preflight

### 4.1 Lookahead bias checker

For each diagnostic row, source metadata must satisfy:

```text
source_as_of_date <= snapshot.data_as_of_date <= snapshot.trading_day
source_fetched_at <= snapshot.as_of_timestamp
```

Rows violating these constraints must be flagged as:

```text
lookahead_violation
```

Default behavior:

- exclude lookahead-violating rows from IC diagnostics
- count them in the preflight report
- fail readiness if violation rate exceeds threshold

### 4.2 Restated data detector

P22-A+ must detect possible restatement risk when multiple versions of the same financial period appear in source metadata.

Minimum supported fields:

- `ticker`
- `fiscal_period`
- `reported_date`
- `source_fetched_at`
- `data_version`
- `restatement_flag`

If full source metadata is unavailable, P22-A+ must emit:

```text
source_version_metadata_missing
```

It must not pretend restatement risk is clean.

### 4.3 Source audit checker

Each factor row should be traceable to source references or source metadata.

Required audit signals:

- `source_refs_present`
- `source_as_of_date_present`
- `source_fetched_at_present`
- `provider_present`

Rows with missing auditability are allowed in v1 diagnostics only if explicitly flagged. Readiness may be blocked if audit gaps exceed threshold.

### 4.4 Sector snapshot checker

P22-A+ should verify that sector or industry classification is point-in-time.

Required fields when available:

- `sector_id`
- `industry_id`
- `classification_source`
- `classification_as_of_date`
- `classification_snapshot_id`

If these are missing, P22-A+ must flag:

```text
sector_snapshot_missing
```

Sector-neutral diagnostics must not run when sector snapshot data is missing.

## 5. P22.1 Factor Diagnostics Engine

### 5.1 Required factors

P22-A+ v1 must support:

- `company_quality_score`
- `valuation_attractiveness_score`
- `timing_market_fit_score`
- `llm_adjustment_total`
- `negative_signal_strength_decile` when present

### 5.2 Required horizons

P22-A+ v1 must support:

- 1 trading day
- 5 trading days
- 21 trading days
- 63 trading days

### 5.3 IC

For each factor and horizon:

```text
IC = corr(factor_score_t, forward_return_t_to_t+h)
```

P22-A+ v1 may use Pearson correlation. Rank IC can be added later.

### 5.4 Gross vs net IC

For each factor and horizon:

- `gross_ic`
- `net_ic`
- `cost_impact_on_ic = gross_ic - net_ic`
- `cost_fragile = true` when gross IC is positive but net IC is weak or negative

Readiness gates must use net IC only.

### 5.5 ICIR

Compute periodic IC by `trading_day` or diagnostic period, then:

```text
ICIR = mean(periodic_ic_series) / std(periodic_ic_series)
```

If fewer than two periodic ICs exist, return `0.0` and flag `insufficient_ic_periods`.

### 5.6 Newey-West/HAC t-stat

P22-A+ should include a dependency-free Newey-West estimator.

Default lag:

```text
floor(sqrt(n_periods))
```

If HAC cannot be computed, readiness must fail with:

```text
hac_status = "insufficient_periods" | "zero_variance" | "not_implemented"
```

### 5.7 IC decay

For each factor, compare net IC across horizons and classify:

- `short_horizon`
- `medium_horizon`
- `long_horizon`
- `unstable`
- `insufficient_data`

### 5.8 Autocorrelation

Compute lag-1 autocorrelation by ticker over time for each factor.

Purpose:

- detect stale factors
- identify slow-moving signals
- inform future rebalance cadence

### 5.9 Orthogonality

Compute cross-factor correlations:

- quality vs valuation
- quality vs timing
- valuation vs timing
- each primary factor vs LLM overlay

If absolute correlation exceeds `0.70`, mark:

```text
highly_correlated = true
```

## 6. P22.2 Calibration Readiness Report

P22-A+ may mark a factor-horizon pair as `ready_for_shadow_calibration`.

This does not mean production calibration.

Default readiness thresholds:

- `min_observations`: 60
- `min_unique_tickers`: 10
- `min_periods_for_icir`: 6
- `max_missing_return_rate`: 0.20
- `max_lookahead_violation_rate`: 0.00
- `max_source_audit_gap_rate`: 0.20
- `min_abs_net_ic_for_ready`: 0.05
- `max_abs_factor_correlation`: 0.70
- `min_newey_west_t_stat_for_ready`: 1.50

Allowed statuses:

- `insufficient_sample`
- `missing_returns_too_high`
- `lookahead_violations_present`
- `source_audit_gap_too_high`
- `weak_net_ic`
- `hac_tstat_too_low`
- `orthogonality_warning`
- `ready_for_shadow_calibration`

## 7. P22.3 Daily Factor Health Check

Daily health checks are end-of-day diagnostics, not real-time monitoring.

### 7.1 Factor distribution drift

For each factor, compute:

- mean
- standard deviation
- min
- max
- p05
- p50
- p95
- z-score versus trailing baseline

If the latest mean deviates by more than 3 standard deviations from baseline, flag:

```text
factor_distribution_drift
```

### 7.2 Gate pass-rate drift

Track classification and gate rates:

- `Investable`
- `Watchlist`
- `Inconclusive`
- `No Trade`
- coverage gate failure rate
- regime gate failure rate

If latest rate deviates materially from baseline, flag:

```text
gate_pass_rate_drift
```

### 7.3 Forward-return completion

For each horizon, compute:

- expected observations
- computed observations
- missing observations
- completion rate
- missing return rate

If missing return rate exceeds readiness threshold, flag:

```text
forward_return_completion_gap
```

## 8. Sentiment Treatment

P22-A+ must not create a standalone sentiment system.

Sentiment should be treated as factor evidence or regime/timing input, such as:

- VIX percentile
- market breadth proxy
- put/call ratio later

If sentiment proxy data exists in rows, diagnostics may evaluate it as an additional factor. If it does not exist, P22-A+ should not invent it.

## 9. Output Contracts

### 9.1 `DataIntegrityReport`

Required fields:

- `sample_size`
- `lookahead_violation_count`
- `lookahead_violation_rate`
- `source_audit_gap_count`
- `source_audit_gap_rate`
- `restatement_risk_count`
- `sector_snapshot_missing_count`
- `excluded_snapshot_ids`
- `diagnostic_flags`

### 9.2 `FactorMetricResult`

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

### 9.3 `CalibrationReadinessReport`

Required fields:

- `ready_count`
- `not_ready_count`
- `ready_factor_horizons`
- `blocked_factor_horizons`
- `blocking_reasons`

### 9.4 `DailyFactorHealthReport`

Required fields:

- `factor_distribution_alerts`
- `gate_rate_alerts`
- `forward_return_completion_alerts`
- `overall_health_status`
- `diagnostic_flags`

### 9.5 `P22ValidityReport`

Required fields:

- `schema_version`: `p22.0`
- `return_basis_default`: `net`
- `data_integrity_report`
- `factor_metrics`
- `orthogonality_results`
- `decay_results`
- `autocorrelation_results`
- `calibration_readiness_report`
- `daily_health_report`
- `overall_readiness`
- `generated_at`

## 10. Implementation Boundaries

Recommended modules:

- `data_integrity.py`
- `newey_west.py`
- `diagnostic_gates.py`
- `factor_diagnostics.py`
- `factor_health_check.py`
- `diagnostic_reports.py`

Existing `p22_return_selector.py` remains the source for gross/net return selection.

## 11. Acceptance Criteria

P22-A+ is accepted only if:

1. Data integrity preflight flags and excludes lookahead violations by default.
2. Source audit gaps and sector snapshot gaps are visible in reports.
3. Diagnostics default to net returns.
4. Gross IC is reported only as comparison.
5. IC, ICIR, IC decay, Newey-West/HAC, autocorrelation, and orthogonality are implemented.
6. Sample gates block small samples.
7. Readiness gates use net IC, not gross IC.
8. Daily health check detects factor distribution drift.
9. Daily health check detects forward-return completion gaps.
10. Report object contains integrity, diagnostics, readiness, and health sections.
11. No production config is changed to `calibrated`.
12. P20/P21 regression tests continue to pass.

## 12. Review Checklist

Reject implementation if:

- any diagnostic reads raw price history
- lookahead-violating rows enter IC by default
- net return is not the default
- gross IC can pass readiness when net IC fails
- production configs are modified
- missing source audit data is silently treated as clean
- sector snapshot absence is silently ignored
- health reports are cosmetic and do not compute drift/completion metrics
- tests only cover happy paths
