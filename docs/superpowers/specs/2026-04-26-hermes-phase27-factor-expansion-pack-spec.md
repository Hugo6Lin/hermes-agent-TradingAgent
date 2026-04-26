# Phase 27 Factor Expansion Pack Spec

Date: 2026-04-26
Status: Draft for engineering handoff
Scope: Macro, event-surprise, and sector-relation factor candidates under the existing shadow-only diagnostics framework

## 1. Purpose

Phase 27 compresses the next factor-expansion work into one node:

```text
Phase 27 = Macro Factor Candidates + Event Surprise Candidates + Sector Relation Baseline + P22-style diagnostics handoff
```

The goal is to add new candidate factor families without polluting canonical factor snapshots or production scores.

## 2. Core Principle

New data is not alpha until it survives the same point-in-time, net-return, out-of-sample diagnostics as the core factors.

Phase 27 produces shadow candidate factor outputs only. It must not change ranking, thesis classification, trading, or production calibration.

## 3. Non-Goals

Phase 27 must not:

- write canonical `FactorSnapshot` fields
- modify production configs
- change P20/P21/P22/P23 calibrated configs
- train advanced models
- promote any candidate factor
- execute trades
- read future data
- use raw unsourced event text without timestamp policy
- import model libraries such as `xgboost`, `sklearn`, `torch`, `tensorflow`, `stable_baselines3`, `numpy`, or `pandas`

## 4. Candidate Families

### 4.1 Macro candidates

Required inputs:

- `macro_series_id`
- `observation_date`
- `release_timestamp`
- `value`
- `source_name`
- `source_as_of_date`
- `frequency`
- `fill_policy`

Required output fields:

- `candidate_factor_name`
- `candidate_namespace`
- `trading_day`
- `macro_regime_score`
- `macro_momentum_score`
- `point_in_time_confirmed`
- `source_audit_complete`
- `warnings`

### 4.2 Event surprise candidates

Required inputs:

- `event_id`
- `ticker`
- `event_timestamp`
- `event_type`
- `expected_direction`
- `observed_direction`
- `confidence_score`
- `source_refs`

Required output fields:

- `event_surprise_score`
- `event_sentiment_score`
- `event_novelty_score`
- `taxonomy_version`
- `label_consistency_score`
- `point_in_time_confirmed`
- `source_audit_complete`

### 4.3 Sector relation baseline candidates

Required inputs:

- `ticker`
- `sector`
- `peer_group_id`
- `trading_day`
- `sector_return_proxy`
- `peer_return_proxy`
- `source_as_of_date`

Required output fields:

- `sector_relative_strength_score`
- `peer_relation_score`
- `sector_dispersion_score`
- `relation_baseline_version`
- `point_in_time_confirmed`
- `source_audit_complete`

## 5. Required Contracts

Implement or extend shadow-only contracts:

- `FactorExpansionRequest`
- `CandidateFactorObservation`
- `CandidateFactorSet`
- `CandidateFactorDiagnosticsInput`
- `FactorExpansionReport`

Required function:

```python
build_factor_expansion_candidates(macro_inputs, event_inputs, relation_inputs, request) -> FactorExpansionReport
```

## 6. Safety Rules

Phase 27 must block candidate observations when:

- `source_as_of_date > trading_day`
- `release_timestamp` is missing for macro data
- event timestamp is missing
- source refs are missing
- taxonomy version is missing for event candidates
- sector/peer group is missing for relation candidates
- candidate namespace does not start with `shadow_candidate_factor.`

Blocked rows must be counted by reason.

## 7. Diagnostics Handoff

Phase 27 does not compute final IC/ICIR itself unless reusing existing P22 helpers without changing their semantics.

It must produce diagnostics-ready rows with:

- `candidate_factor_name`
- `candidate_family`
- `trading_day`
- `ticker` when applicable
- `score_value`
- `point_in_time_confirmed`
- `source_audit_complete`
- `schema_version`

These rows are intended for P22-style diagnostics and P23-style shadow observation later.

## 8. Acceptance Checklist

A valid Phase 27 handoff must report:

- macro candidate contract exists: yes/no
- event candidate contract exists: yes/no
- relation candidate contract exists: yes/no
- PIT checks implemented: yes/no
- source audit checks implemented: yes/no
- taxonomy checks implemented: yes/no
- candidate namespace enforced: yes/no
- blocked counts reported: yes/no
- diagnostics-ready rows emitted: yes/no
- no canonical factor writes: yes/no
- no production config writes: yes/no
- no model libraries imported: yes/no
- P20-Phase27 regression green: yes/no

## 9. Boundary to Phase 28

Phase 27 outputs candidate factors only. Phase 28 may improve execution realism and cost modeling, but must not assume Phase 27 factors are production-ready.
