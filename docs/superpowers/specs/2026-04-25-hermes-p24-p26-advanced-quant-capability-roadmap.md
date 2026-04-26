# P24-P26 Advanced Quant Capability Roadmap

Date: 2026-04-25
Status: Strategic roadmap for post-P23 planning
Scope: Advanced factor expansion, model integration, portfolio construction, and long-range quant-engine evolution after P22-A+ diagnostics and P23 shadow calibration

## 1. Executive Summary

Before P22-A+ diagnostics prove that core Hermes factors have stable marginal net predictive power, every new model is just subjective judgment wearing a lab coat.

Hermes must not add XGBoost, GNNs, LSTMs, PPO, or standalone sentiment systems before the current factor infrastructure is validated. The system has deliberately moved from narrative research toward point-in-time, cost-aware, auditable factor diagnostics. Adding complex models before that diagnostic loop is accepted would create overfit shells, attribution confusion, and factor contamination.

The correct next-level roadmap is conservative:

```text
P22-A+: prove factor validity
P23-A: run shadow calibration without production changes
P24-P26: expand factor/model capability only through gated shadow modules
Level 5: portfolio and execution optimization after factor and calibration evidence exists
```

## 2. Current Boundary Conditions

### 2.1 P22-A+

Role:

- data integrity preflight
- factor diagnostics
- IC / ICIR / HAC / orthogonality
- daily health reporting
- calibration readiness reporting

Outputs:

- `FactorDiagnosticsReport`
- `CalibrationReadinessReport`
- `DailyFactorHealthReport`

Restrictions:

- no production parameter updates
- no new model families
- no new unvalidated factors entering production
- no strategy backtest as substitute for factor diagnostics

### 2.2 P23-A

Role:

- shadow calibration only
- shrinkage recommendations
- factor orthogonalization hints
- blocked-candidate reporting

Outputs:

- `ShadowCalibrationReport`
- `ShadowShrinkageWeights`
- `FactorOrthogonalizationHint`

Restrictions:

- no automatic production config edits
- no production `calibration_status = "calibrated"`
- no new model integration
- no simultaneous factor-source changes

Observation requirement:

- shadow recommendations should be observed for at least one full market cycle or 12 months before any production adoption review, unless the user explicitly accepts a shorter research-only shadow window.

### 2.3 P24-P26

Entry condition:

- P23 shadow calibration shows at least one core factor or factor group improves net predictive quality or decision quality relative to prior-only configuration.

Role:

- advanced factor expansion
- model family admission gates
- shadow-only model/plugin experiments
- portfolio construction design after validated factor evidence exists

## 3. Guiding Principle

Complexity must earn its place.

Every advanced model must enter Hermes through the same sequence:

```text
candidate idea
  -> admission gate
  -> shadow factor/plugin logging
  -> P22-style diagnostics
  -> P23-style shadow calibration
  -> production adoption review
```

No model may bypass:

- point-in-time source audit
- net-return validation
- sample-size gates
- orthogonality checks
- health checks
- shadow-only observation period

## 4. Failure Modes This Roadmap Prevents

### 4.1 Overfit shell

If sample size is weak, an XGBoost or LSTM model can learn noise as nonlinear interaction. It may show excellent backtest IC and then collapse out of sample.

Prevention:

- no model admission without P22 sample gates
- no production use without shadow observation
- net IC and HAC are required

### 4.2 Factor contamination

If a new model writes directly into `FactorSnapshot` without isolation, later diagnostics cannot distinguish original factor signal from model-transformed signal.

Prevention:

- new model outputs must use separate namespaced fields
- original core factor fields remain immutable
- model factors are logged as shadow candidates first

### 4.3 Attribution collapse

If P23 shadow calibration and P24 model expansion happen simultaneously, performance changes cannot be attributed to calibration versus new features.

Prevention:

- P23 calibrates existing validated factors only
- P24 starts only after P23 shadow behavior is understood

### 4.4 Cool-model bias

Models must not be adopted because they sound sophisticated.

Prevention:

- each model family has mandatory admission gates
- blocked model attempts are recorded with reasons

## 5. Model Family Positioning

### 5.1 XGBoost

Correct role:

- nonlinear factor-combination meta-model
- shadow ranking model
- interaction detector across already validated factors

Incorrect role:

- standalone stock picker
- replacement for factor diagnostics
- direct production signal generator

Reasonable inputs:

- `company_quality_score`
- `valuation_attractiveness_score`
- `timing_market_fit_score`
- `llm_adjustment_total`
- regime features
- sector and size features
- P23 shadow-calibrated hints

Admission gate:

```text
- at least 3 core factors have net ICIR > 0.30
- at least 2 factors pass ready_for_shadow_calibration
- max absolute cross-factor correlation < 0.70, or residualization plan exists
- at least 500 independent cross-sectional observations
- no unresolved lookahead or source audit blockers
- out-of-sample split plan is defined before training
```

P24 status:

- eligible only as `shadow_meta_model`
- no production config mutation

### 5.2 LLM Event Surprise Factor

Correct role:

- structured event surprise factor
- qualitative shock quantification
- narrative-risk and event-severity scoring

Incorrect role:

- direct BUY/SELL oracle
- unbounded thesis override
- replacement for hard-data factors

Reasonable outputs:

- `event_surprise_score`
- `sentiment_delta_score`
- `narrative_risk_score`
- `event_severity_score`
- `management_tone_change_score`

Admission gate:

```text
- existing llm_adjustment_total net IC is near zero or positive, not strongly negative
- event taxonomy is fixed before measurement
- labeling consistency exceeds 80% on a review sample
- all event timestamps are point-in-time audited
- event factors are logged separately from existing llm_adjustment_total
```

P24/P25 status:

- strong candidate because it matches Hermes' research-agent advantage
- must be factorized before diagnostics

### 5.3 Macro / Regime Factors

Correct role:

- regime support
- timing support
- factor performance conditioning

Incorrect role:

- broad macro narrative injected into thesis without validation
- discretionary override of factor readiness

Candidate factors:

- rates level and rates change
- yield-curve slope
- credit spread
- PMI or growth proxy
- inflation surprise
- dollar strength proxy
- liquidity proxy
- market breadth proxy

Admission gate:

```text
- macro data source has point-in-time timestamps
- regime gate shows at least some return-distribution separation
- macro feature frequency aligns with Hermes holding horizons
- no daily forward-fill creates false precision
```

P24/P25 status:

- high-priority factor expansion area
- should begin as shadow regime/timing factor candidates

### 5.4 GNN / Transformer Relation Models

Correct role:

- relation factor
- supply-chain or peer-contagion modeling
- sector heatmap or linkage-strength feature

Incorrect role:

- direct return predictor without interpretable relation fields
- replacement for sector and industry snapshots

Admission gate:

```text
- more than 15 sectors or relation groups are represented
- average group has more than 10 tickers
- relation graph is point-in-time versioned
- simple sector correlation or clustering has been tested first
- advanced relation model shows incremental value over simple correlation baselines
```

P25/P26 status:

- later-stage candidate
- start with GNN-lite or correlation-clustering baseline first

### 5.5 LSTM / Time-Series Foundation Model

Correct role:

- timing factor candidate
- price/volume sequence pattern extraction
- volatility or trend-persistence feature generation

Incorrect role:

- company-quality substitute
- thesis classifier
- direct trade authority

Admission gate:

```text
- existing timing_market_fit_score has weak or unstable net IC
- simple momentum, reversal, volatility, and trend features have been tested
- walk-forward validation is defined before model work
- enough historical sequence data exists per universe
- model output is logged as a separate timing candidate factor
```

P26+ status:

- use only if simpler timing factors fail or plateau

### 5.6 PPO / Reinforcement Learning

Correct role:

- execution-layer optimization
- order slicing
- participation-rate control
- market-impact reduction

Incorrect role:

- stock selection
- thesis classification
- factor weighting
- portfolio allocation before portfolio layer exists

Admission gate:

```text
- portfolio construction layer exists
- order frequency is higher than weekly or order size creates measurable impact
- execution simulator or real execution dataset exists
- objective is execution cost reduction, not alpha generation
```

Level 5 status:

- not a P24-P26 priority unless Hermes reaches portfolio/execution scale

## 6. Factor Plugin Architecture Direction

P24 should introduce a plugin contract only after P23 confirms calibration stability.

Required plugin contract:

```text
FactorPlugin
  plugin_name
  plugin_version
  input_contract
  output_fields
  source_refs
  source_as_of_date
  source_fetched_at
  coverage_score
  point_in_time_status
  diagnostic_tags
  factor_snapshot_namespace
```

Rules:

- plugins write to namespaced candidate fields
- plugins do not overwrite core factor fields
- plugins default to `shadow_only`
- plugins must produce source audit metadata
- plugins must be diagnosable by P22-style diagnostics

Candidate namespaces:

```text
candidate_macro.*
candidate_event.*
candidate_relation.*
candidate_timing_sequence.*
shadow_meta_model.*
```

## 7. P24-P26 Phase Roadmap

### 7.1 P24: Shadow Factor Plugin Framework and XGBoost Readiness

Goals:

- define `FactorPlugin` contract
- support shadow-only candidate factor logging
- create model admission gate evaluator
- prepare XGBoost meta-model only if gates pass
- standardize LLM event taxonomy if LLM gate passes

Deliverables:

- `FactorPluginSpec`
- `ModelAdmissionGateReport`
- `ShadowFactorCandidateSnapshot`
- optional `XGBoostMetaModelDesign`, no production training unless gates pass

Acceptance:

- no plugin can write production factor fields
- no model can run without admission gate report
- blocked model candidates are reported

### 7.2 P25: Macro, Event, and Relation Factor Expansion

Goals:

- add point-in-time macro factor candidates
- add event surprise factor candidates
- add simple sector relation baseline before GNN
- evaluate all new candidates through P22-style diagnostics

Deliverables:

- `MacroFactorCandidateSet`
- `EventSurpriseFactorCandidateSet`
- `SectorRelationBaselineReport`
- `CandidateFactorDiagnosticsReport`

Acceptance:

- all candidate factors have source audit metadata
- all candidates are shadow-only
- no candidate enters production without P22/P23 gates

### 7.3 P26: Portfolio Construction and Advanced Model Evaluation

Goals:

- design portfolio construction after validated factors exist
- run rank-based portfolio simulations
- evaluate turnover, cost, concentration, and drawdown
- consider GNN/LSTM only if admission gates pass

Deliverables:

- `PortfolioConstructionSpec`
- `PortfolioBacktestEngineDesign`
- `AdvancedModelEvaluationReport`
- `ExecutionLayerReadinessReport`

Acceptance:

- portfolio simulation consumes validated/shadow-calibrated signals only
- no PPO until execution data and portfolio layer exist
- advanced models must beat simple baselines out of sample

## 8. Production Adoption Rule

Any new model or factor must pass all stages:

```text
admission gate
  -> shadow logging
  -> P22-style diagnostics
  -> P23-style shadow calibration
  -> observation window
  -> production adoption review
```

Minimum production review evidence:

- net IC or portfolio net performance survives costs
- HAC/Newey-West evidence is acceptable
- no unresolved lookahead risk
- no source audit blocker
- orthogonality or residualization plan exists
- shadow period does not degrade health metrics
- human reviewer signs off

## 9. Boss-Facing Narrative

Hermes is deliberately not rushing into complex models.

The professional story is:

> We first built auditable factor infrastructure, then validated whether the factors have net predictive power, then ran shadow calibration, and only then admitted advanced models through explicit gates.

This is stronger than presenting a flashy GNN or XGBoost backtest without attribution control.

## 10. Review Checklist

Reject future advanced-model work if:

- it bypasses P22 diagnostics
- it writes directly into production factor fields
- it lacks source audit metadata
- it uses gross returns as primary evidence
- it trains before sample gates pass
- it cannot be compared to a simple baseline
- it changes P23 shadow calibration inputs during observation
- it claims production readiness without a shadow observation window
