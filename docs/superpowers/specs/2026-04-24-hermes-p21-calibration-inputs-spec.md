# P21 Calibration Inputs Spec

Date: 2026-04-24
Status: Draft for engineering handoff
Scope: Hermes `agent/research_v1` P21 calibration-input layer after P20 P&L integrity and factor persistence acceptance

## 1. Purpose

P20 made Hermes factor logs and P&L observations auditable. P21 must now make every major decision knob explicit, versioned, and testable before P22 computes IC, ICIR, decay, and shrinkage-calibrated parameters.

P21 is not the phase where Hermes learns optimal parameters from data. P21 is the phase where Hermes stops hiding priors in code. All scoring thresholds, role weights, exit multiples, sector valuation benchmarks, regime gates, and sizing assumptions must become named calibration inputs with `calibration_status = "prior_only"` unless and until P22 sample-size and HAC/Newey-West gates permit data-driven updates.

## 2. Core Decision

P21 turns Hermes from a system with hardcoded constants into a system with explicit prior contracts.

P21 must preserve current product behavior where possible, but the source of behavior must move from literals inside scoring functions into configuration objects and payload fields that P22 can audit later.

The guiding rule:

> If a parameter changes the thesis classification, ranking, exit plan, valuation score, or position size, it must be visible in config, surfaced in outputs where relevant, and logged or ready to be logged by factor snapshots.

## 3. Non-Goals

P21 does not:

- run shrinkage calibration
- tune parameters from IC/ICIR results
- add autonomous execution
- add short-selling or bearish trade actions
- implement a full portfolio optimizer
- claim stress tests are real historical resimulations
- require institutional datasets
- replace the existing research pipeline
- change P20 persistence contracts except for additive, versioned fields if strictly necessary

## 4. Dependencies

P21 assumes P20 has already delivered:

- corrected peak-to-trough drawdown
- `CostModel` and net-return-aware outcomes
- `ExitPlan` with prior-only stop/target multiples
- quality scoring that penalizes missing dimensions
- bounded LLM overlay behavior
- role-weight zero guards
- threshold config for thesis classification
- sector benchmark valuation support
- factor snapshots and forward-return observations with gross/net/cost fields
- point-in-time universe membership snapshots

## 5. Design Principles

### 5.1 Explicit priors before learned weights

All P21 configuration values are priors. They must be labeled as such.

Allowed `calibration_status` values:

- `prior_only`: default for P21
- `shadow_observed`: observations exist but cannot tune production behavior yet
- `calibrated`: forbidden in P21 unless a later P22 gate explicitly permits it
- `disabled`: parameter family intentionally inactive with a reason

### 5.2 Config ownership, not scattered literals

Decision constants must live in `agent/research_v1/calibration_config.py` or focused config modules imported from it.

Functions may keep backward-compatible public constants only if those constants are derived from config. They must not be independent truth sources.

### 5.3 P22-ready audit payloads

Whenever a config drives output, the output should carry enough metadata for later analysis:

- config class name
- config version or schema version
- calibration status
- raw input values
- transformed output values
- cap/guard reason when applicable

### 5.4 Net-return default

Any P21 diagnostic or fixture that chooses between gross and net returns must default to `net_return_pct`. Gross returns may be available for comparison, never as the default P22 signal-quality metric.

### 5.5 Honest disclosure over cosmetic confidence

If P21 has only priors, outputs should say so. If stress tests are still synthetic labels, boss-facing output remains disabled. If regime gates are not fully operational, they must report `stubbed` or `insufficient_definition`, not pretend to be calibrated.

## 6. Required Configuration Contracts

### 6.1 `CalibrationStatus`

Add a shared representation for calibration status. A simple string literal set is acceptable; an enum is acceptable if it does not create broad import churn.

Required values:

```text
prior_only
shadow_observed
calibrated
disabled
```

P21 default: `prior_only`.

### 6.2 `CalibrationMetadata`

Add a lightweight metadata contract for config-driven outputs.

Required fields:

- `config_name: str`
- `config_version: str`
- `calibration_status: str`
- `source: str`

Default config version should be `p21.0`.

### 6.3 Thesis thresholds

`ThesisThresholdConfig` already exists. P21 must extend or preserve it with:

- no-trade quality threshold
- investable quality threshold
- investable valuation threshold
- investable catalyst threshold
- watchlist sub-state thresholds if implemented
- `config_version`
- `calibration_status`

`ThesisEngine._classify()` must read thresholds only from config.

### 6.4 Role weights

`RoleWeightConfig` already exists. P21 must ensure:

- no role may have exact `0.00` weight without `disabled_with_reason`
- plain weight export validates the zero-weight guard
- `FinalJudge` can receive a role-weight config instance, not only use a module-level constant
- backward-compatible `ROLE_WEIGHTS` remains derived from `RoleWeightConfig`

### 6.5 Grading weights

`GradingWeightConfig` already exists. P21 must ensure:

- weights sum to 1.0 within tolerance
- no negative weights
- `GradingAgent` uses the instance values in `_calculate_composite()`
- dynamic runtime overrides cannot silently break the sum-to-one invariant

### 6.6 Exit multiples

`ExitPlanConfig` exists in `exit_planning.py`. P21 must either move it into `calibration_config.py` or re-export it there as the canonical config source.

Required fields:

- `stop_multiple`
- `target_multiple`
- `calibration_status`
- `config_version`
- optional `horizon_bucket`, default `default`

Stop and target multiples must remain `prior_only` in P21.

### 6.7 Sector valuation benchmarks

Sector benchmark multiples must become config-driven rather than a bare module-level valuation literal.

Required fields:

- sector key
- `pe`
- `pb`
- `ps`
- `calibration_status`
- `config_version`
- fallback/default sector behavior

`calculate_relative_valuation()` must consume the configured sector benchmark when `benchmark_multiples` provides a sector but not explicit multiples.

### 6.8 Position sizing

P21 must replace integer-only position sizing with volatility-aware sizing while preserving backward-compatible output fields.

Required config fields:

- `target_position_volatility`
- `max_single_name_weight`
- `max_position_as_pct_adv`
- `min_position_units`
- `calibration_status`
- `config_version`

Required output fields:

- `suggested_position_size` for backward compatibility
- `suggested_position_weight`
- `target_position_volatility`
- `input_signal_volatility`
- `adv_cap_applied`
- `single_name_cap_applied`
- `calibration_status`

If volatility or portfolio context is missing, use a conservative fallback and include a sizing flag such as `missing_signal_volatility` or `missing_portfolio_equity`.

### 6.9 Regime gate v1

P21 must define an operational regime feature contract even if data availability is partial.

Recommended fields:

- `vix_percentile`
- `realized_vol_percentile`
- `market_breadth_percentile`
- `cross_sectional_dispersion_percentile`
- `major_index_trend_state`

Required output fields:

- `regime_gate_status`: `pass`, `warn`, `fail`, `stubbed`, or `insufficient_definition`
- `failing_features`
- `missing_features`
- `calibration_status`
- `config_version`

If no real regime inputs are available, return `insufficient_definition` or `stubbed`; do not return `pass` by default.

## 7. Required Behavioral Changes

### 7.1 No untracked literals in gate logic

Tests must fail if thesis thresholds are hardcoded inside `_classify()` instead of loaded from `ThesisThresholdConfig`.

### 7.2 No silent zero weights

Tests must fail if any role weight is `0.00` without `disabled_with_reason`.

### 7.3 No unbounded dynamic grading weights

If `GradingAgent(dynamic_weights=...)` is still supported, overrides must be validated after merge with the base config. Invalid overrides must raise `ValueError`.

### 7.4 Exit plans remain priors

ATR/volatility adaptive exits are acceptable, but their multiples are not calibrated. Outputs must expose `calibration_status = "prior_only"`.

### 7.5 Sector valuation must be config-auditable

Relative valuation must report which sector benchmark was used, whether fallback/default was used, and the benchmark config version.

### 7.6 Stress tests remain hidden until real resimulation

Boss-facing stress output must remain disabled unless a real resimulation flag is true. P21 may improve metadata, but must not imply historical stress tests are complete.

### 7.7 P22 diagnostics default to net returns

Add a minimal diagnostics helper or fixture-level consumer proving that return selection defaults to `net_return_pct` and can explicitly choose `gross_return_pct` for comparison.

## 8. Acceptance Criteria

P21 is accepted only if all items below are true:

1. All P20 tests continue to pass.
2. `calibration_config.py` owns or re-exports all P21 calibration contracts.
3. Thesis thresholds are config-driven and covered by tests.
4. Role weights reject zero weights without reasons.
5. `FinalJudge` accepts injected `RoleWeightConfig` while preserving existing public behavior.
6. Grading weights reject invalid sums and invalid dynamic overrides.
7. Exit multiples are config-driven and surfaced as `prior_only`.
8. Sector valuation uses config-driven benchmarks and reports benchmark metadata.
9. Trade plans include volatility-aware sizing fields and cap flags while preserving `suggested_position_size`.
10. Regime gate v1 returns explicit `stubbed` or `insufficient_definition` when inputs are missing.
11. P22 return selector defaults to `net_return_pct` and can select gross returns for comparison.
12. Cosmetic stress test output remains hidden from boss-facing surfaces unless real resimulation is enabled.
13. New tests cover all changed behavior.
14. The final verification command over `tests/agent/research_v1/` passes under Python 3.11.

## 9. Review Checklist for the Review Model

The reviewer should reject the implementation if any of these occur:

- a new hardcoded threshold or weight is introduced inside scoring logic
- `calibration_status = "calibrated"` appears without P22 sample gates
- gross returns become the default for P22 diagnostics
- zero weights appear without `disabled_with_reason`
- trade sizing still only returns integer units with no volatility/cap metadata
- regime gate defaults to `pass` when data is absent
- sector valuation silently falls back to generic multiples without reporting fallback metadata
- tests only check object construction but not behavioral consumption
