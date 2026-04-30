# P24 Entry Gate Spec

Date: 2026-04-25
Status: Draft gate spec for post-P23 planning
Scope: Admission gates for P24 advanced factor plugins, model integration, and shadow meta-model work

## 1. Purpose

P24 must not begin by adding advanced models. P24 begins by deciding whether advanced models are allowed to enter Hermes at all.

This spec defines the gates that must be satisfied before any P24 model or factor-expansion implementation starts.

The governing principle:

> Before diagnostic reports prove stable marginal net returns from core factors, every new model is subjective judgment wearing a lab coat.

## 2. Core Decision

P24 implementation is gated.

No XGBoost, GNN, Transformer, LSTM, PPO, macro plugin, event plugin, or sentiment plugin may enter development unless its admission gate is explicitly evaluated and recorded.

All accepted P24 work is shadow-only by default.

## 3. Non-Goals

P24 entry gates do not:

- train models
- add production factor fields
- mutate calibration config
- promote P23 shadow recommendations
- build portfolio optimization
- build live execution
- create autonomous trading

## 4. Universal P24 Admission Gate

Every P24 candidate must pass the universal gate before model-specific gates are considered.

Required:

```text
P20 accepted: true
P21 accepted: true
P22-A+ accepted: true
P23 accepted: true
return_basis_default: net
lookahead_violation_rate: 0.0
source_audit_gap_rate <= 0.20
no production_config_changes pending
candidate_mode: shadow_only
candidate_namespace defined
source audit metadata defined
```

Blocked if:

- candidate writes directly into core production factor fields
- candidate uses raw prices or financial data without point-in-time metadata
- candidate depends on gross returns as primary evidence
- candidate has no simple baseline comparison
- candidate lacks an out-of-sample evaluation plan

## 5. Candidate Namespaces

All P24 candidates must write to namespaced fields.

Allowed namespaces:

```text
candidate_macro.*
candidate_event.*
candidate_relation.*
candidate_timing_sequence.*
shadow_meta_model.*
```

Forbidden:

```text
company_quality_score
valuation_attractiveness_score
timing_market_fit_score
llm_adjustment_total
classification
```

Core fields may be read, but not overwritten.

## 6. XGBoost Meta-Model Gate

Purpose:

- nonlinear combination of already validated factors
- shadow ranking model
- interaction discovery

Required gate:

```text
at least 3 core factors have net ICIR > 0.30
at least 2 factor-horizon pairs are ready_for_shadow_calibration
max absolute cross-factor correlation < 0.70, or residualization plan exists
at least 500 independent cross-sectional observations
P23 shadow recommendations are stable or non-degrading during observation
train/validation/test split is defined before training
simple linear baseline is defined
```

Blocked if:

- XGBoost is proposed as a standalone stock picker
- model output would bypass `FactorSnapshot`
- feature set includes non-point-in-time fields
- sample size is insufficient

Allowed first artifact:

- `XGBoostAdmissionGateReport`

Not allowed as first artifact:

- trained production model

## 7. LLM Event Surprise Factor Gate

Purpose:

- convert agentic event interpretation into structured event factors
- quantify sentiment surprise, narrative risk, and event severity

Required gate:

```text
existing llm_adjustment_total net IC is near zero or positive
event taxonomy is fixed before measurement
event timestamp policy is point-in-time
label consistency exceeds 80% on review sample
event fields are namespaced under candidate_event.*
bounded overlay rules remain intact
```

Blocked if:

- LLM output directly changes base factor scores
- event taxonomy changes during measurement window
- event timestamps cannot be audited

Allowed first artifact:

- `EventTaxonomySpec`
- `EventSurpriseAdmissionGateReport`

## 8. Macro / Regime Factor Gate

Purpose:

- add macro and regime candidate features to timing/regime diagnostics

Candidate examples:

- yield curve slope
- rates level/change
- credit spread
- PMI or growth proxy
- inflation surprise
- liquidity proxy
- market breadth proxy

Required gate:

```text
macro source has point-in-time timestamps
feature frequency matches Hermes holding horizons
forward-fill policy is explicit
existing regime gate shows some return-distribution separation, or candidate is explicitly marked exploratory
candidate fields are namespaced under candidate_macro.*
```

Blocked if:

- macro feature uses revised data without versioning
- daily precision is faked from monthly data without disclosure
- macro narrative bypasses factor diagnostics

Allowed first artifact:

- `MacroFactorAdmissionGateReport`

## 9. Relation / GNN / Transformer Gate

Purpose:

- model sector, peer, supply-chain, or relation effects

Required gate:

```text
point-in-time relation graph exists
more than 15 relation groups or sectors are represented
average group has more than 10 tickers
simple sector correlation or clustering baseline has been tested
advanced relation model must show planned incremental comparison to simple baseline
candidate fields are namespaced under candidate_relation.*
```

Blocked if:

- relation graph is current-only and backfilled into history
- GNN is proposed before simple relation baseline
- model output bypasses diagnostics

Allowed first artifact:

- `RelationBaselineSpec`
- `GNNAdmissionGateReport`

## 10. LSTM / Sequence Timing Gate

Purpose:

- generate timing candidate factors from price/volume sequences

Required gate:

```text
existing timing_market_fit_score has weak or unstable net IC
simple momentum, reversal, volatility, and trend features have been tested
walk-forward validation is defined
enough historical sequence data exists per universe
candidate fields are namespaced under candidate_timing_sequence.*
```

Blocked if:

- LSTM is proposed before simple timing baselines
- sequence model output changes thesis classification directly
- validation split is random instead of time-based

Allowed first artifact:

- `SequenceTimingAdmissionGateReport`

## 11. PPO / Reinforcement Learning Gate

Purpose:

- execution cost reduction only

Required gate:

```text
portfolio construction layer exists
order frequency is higher than weekly, or order size creates measurable market impact
execution simulator or real execution dataset exists
objective is execution cost reduction
PPO output cannot affect stock selection or thesis classification
```

Blocked if:

- PPO is proposed for alpha generation
- portfolio layer does not exist
- execution data is unavailable

Allowed first artifact:

- `ExecutionRLReadinessReport`

## 12. Model Admission Report Contract

Every candidate must produce:

```text
ModelAdmissionGateReport
  candidate_name
  candidate_family
  candidate_namespace
  requested_phase
  universal_gate_status
  model_specific_gate_status
  passed
  blocking_reasons
  required_evidence
  available_evidence
  simple_baseline_defined
  point_in_time_status
  shadow_only_confirmed
  production_write_blocked
  reviewer_notes
```

No candidate may proceed without `passed = true`.

## 13. P24 Work Types

Allowed P24 work after gate approval:

- admission report generation
- candidate factor namespace scaffolding
- shadow-only plugin contract design
- baseline comparison design
- event taxonomy design
- data source audit design

Disallowed P24 work before explicit implementation approval:

- model training
- production inference
- production config mutation
- model-driven trading
- portfolio optimization

## 14. Acceptance Criteria

This entry gate spec is accepted if:

1. Every advanced model family has a gate.
2. Universal gates protect point-in-time data integrity.
3. Shadow-only namespace rules are explicit.
4. Production factor fields are protected.
5. XGBoost is limited to meta-model use.
6. GNN/Transformer is limited to relation factors.
7. LSTM is limited to timing candidates.
8. PPO is limited to execution optimization.
9. LLM event work is factorized and bounded.
10. No implementation is authorized by default.

## 15. Review Checklist

Reject P24 proposals if:

- they skip `ModelAdmissionGateReport`
- they train before gate approval
- they overwrite core factor fields
- they lack point-in-time source policy
- they use gross returns as primary evidence
- they lack a simple baseline
- they claim production readiness from shadow diagnostics

