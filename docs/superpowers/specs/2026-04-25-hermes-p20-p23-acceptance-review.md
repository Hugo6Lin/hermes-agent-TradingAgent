# P20-P23 Acceptance Review

Date: 2026-04-25
Status: Accepted milestone review
Scope: Hermes `agent/research_v1` P20 through P23 factor calibration foundation, diagnostics, and shadow calibration

## 1. Executive Summary

Hermes has completed the transition from a research-assistant style scoring system into a Level 3+ quant research infrastructure:

```text
Level 2.5: calibration-ready factor logging
Level 3: validated factor diagnostics
Level 3+: shadow calibration recommendations
```

P20 through P23 establish the minimum trustworthy foundation for future quant expansion:

- P20 makes factor snapshots and forward returns auditable.
- P21 turns hidden decision constants into explicit prior-only calibration inputs.
- P22-A+ validates factor behavior using point-in-time, cost-aware diagnostics.
- P23 generates shadow-only calibration recommendations without mutating production config.

The system is not yet a production-calibrated quant engine and is not yet a portfolio optimizer. It is now a diagnostics-capable, shadow-calibration-ready research system.

## 2. Phase Acceptance Summary

### 2.1 P20: Factor Contracts, Persistence, and P&L Integrity

Accepted capabilities:

- `FactorSnapshot` contract supports point-in-time factor logging.
- `ForwardReturnObservation` stores gross and net returns, transaction cost, and cost source.
- `UniverseMembershipSnapshot` supports point-in-time universe membership.
- `get_latest_factor_snapshot()` can scope by `universe_membership_snapshot_id`.
- Max drawdown uses true peak-to-trough semantics.
- Cost-aware outcomes distinguish `gross_return_pct` from `net_return_pct`.
- Fixed stop/target logic was replaced by ATR/volatility-driven `ExitPlan`.
- Missing quality data is penalized instead of rewarded.
- LLM verbal verdicts are bounded overlays, not base scores.

Accepted boundary:

- P20 does not prove factor alpha.
- P20 does not calibrate weights.
- P20 does not add portfolio construction.

### 2.2 P21: Calibration Inputs

Accepted capabilities:

- Calibration inputs are explicit, versioned, and `prior_only`.
- `ThesisThresholdConfig` drives thesis thresholds.
- `RoleWeightConfig` rejects zero weights without `disabled_with_reason`.
- `FinalJudge` accepts injected role-weight config.
- `GradingWeightConfig` validates dynamic overrides.
- `ExitPlanConfig` is versioned and prior-only.
- `SectorBenchmarkConfig` is the single source for sector valuation benchmarks.
- `PositionSizingConfig` supports volatility-aware sizing and hard caps.
- `RegimeGateConfig` returns conservative states when inputs are missing.
- P22 return selection defaults to `net_return_pct`.

Accepted boundary:

- P21 does not learn parameters from data.
- P21 does not mark configs as calibrated.
- P21 does not introduce advanced models.

### 2.3 P22-A+: Validity, Integrity, and Health Diagnostics

Accepted capabilities:

- Data integrity preflight flags and excludes lookahead rows by default.
- Source audit gaps, restatement risk, and sector snapshot gaps are visible.
- Diagnostics use net returns by default and gross returns only for comparison.
- IC, ICIR, IC decay, Newey-West/HAC, orthogonality, and autocorrelation are implemented.
- Readiness gates block small samples, weak net IC, excessive missing returns, lookahead violations, source audit failures, and weak HAC evidence.
- Daily health checks detect factor drift, gate-rate drift, and forward-return completion gaps.
- `P22ValidityReport` carries integrity, diagnostics, readiness, and health sections.

Accepted boundary:

- P22-A+ does not update production parameters.
- P22-A+ does not train models.
- P22-A+ does not run strategy or portfolio backtests.

### 2.4 P23: Shadow Calibration

Accepted capabilities:

- P23 consumes P22-A+ reports.
- Non-ready factors are blocked and recorded.
- Net IC drives recommendations; gross-only edge is rejected.
- Evidence strength combines net IC, HAC t-stat, sample size, missing returns, and diagnostic penalties.
- Shrinkage is bounded with `delta` in `[0.25, 0.90]`.
- `production_config_changes` is always empty.
- `apply_to_production` is always false.
- Lookahead, source audit, non-net return basis, and critical health blockers prevent recommendations.
- `ShadowCalibrationReport` is shadow-only.

Accepted boundary:

- P23 does not mutate `calibration_config.py`.
- P23 does not mark production config as `calibrated`.
- P23 does not admit new model families.

## 3. Regression Evidence

Most recent reviewed verification:

```text
P20/P21/P22/P23 regression bundle: 186 passed
P23 focused tests: 14 passed
```

Known full-suite condition:

- Full `tests/agent/research_v1` includes unrelated infrastructure failures involving browser/PDF, Futu API context, viewer server, and local path assumptions.
- These failures are outside the P20-P23 factor calibration scope.

## 4. Current System Level

Hermes is now best described as:

> A point-in-time, cost-aware, research-derived, multi-factor diagnostics and shadow-calibration system.

It is not yet:

- a production-calibrated signal engine
- a portfolio construction engine
- an execution optimizer
- an autonomous trading system
- a deep-learning alpha platform

## 5. What Is Now Allowed

Allowed after P23 acceptance:

- observe shadow calibration recommendations over time
- compare shadow recommendations against prior-only behavior
- prepare P24 model/factor admission gates
- design shadow factor plugin architecture
- define future XGBoost, macro, event, relation, and timing model entry criteria

## 6. What Remains Forbidden

Forbidden until explicit future acceptance:

- setting production configs to `calibrated`
- automatically applying P23 recommendations
- adding XGBoost/GNN/LSTM/PPO directly into production decisions
- letting new model outputs overwrite core factor fields
- using gross returns as calibration evidence
- bypassing P22-A+ data integrity checks
- launching portfolio optimization before validated signal and shadow-calibration evidence exists

## 7. P24 Entry Condition

P24 should not start implementation merely because P23 exists.

Minimum P24 design entry:

- P20-P23 acceptance review is complete.
- P24 entry gates are written and approved.
- P23 shadow recommendations have at least initial observation records.
- Any proposed advanced model has a clear admission gate and shadow-only boundary.

Minimum P24 implementation entry:

- At least one P23 shadow recommendation family demonstrates stable non-degrading behavior during observation, or the user explicitly authorizes research-only plugin scaffolding with no model training.

## 8. Boss-Facing Narrative

Hermes deliberately avoided rushing into complex models.

The professional story is:

```text
We first made the research system auditable.
Then we made returns cost-aware.
Then we made parameters explicit.
Then we validated factors.
Then we generated shadow-only calibration suggestions.
Only after this do we decide whether advanced models deserve admission.
```

This is stronger than presenting a flashy ML backtest without point-in-time controls, cost-awareness, or attribution discipline.

## 9. Reviewer Notes

Future work should be rejected if it:

- contaminates production factor fields
- mutates production config from shadow reports
- trains complex models before admission gates pass
- hides data integrity failures
- treats P23 recommendations as production instructions
- claims profitability from diagnostics alone

