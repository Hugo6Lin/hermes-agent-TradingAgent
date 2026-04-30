# Phase 30 Advanced Model Pack Spec

Date: 2026-04-26
Status: Draft for engineering handoff
Scope: Real XGBoost, relation/sequence models, and advanced model admission after governance evidence exists

## 1. Purpose

Phase 30 is the first phase allowed to consider real advanced model training, but only after Phase 25/26/29 evidence supports it.

```text
Phase 30 = Advanced Model Admission + Real Training Sandbox + Model Comparison Report
```

## 2. Core Principle

Advanced models are admitted by evidence, not enthusiasm.

No XGBoost, GNN, LSTM, Transformer, or PPO model may enter production directly from Phase 30.

## 3. Candidate Families

- `real_xgboost_meta_model`
- `sector_relation_gnn_candidate`
- `sequence_timing_model_candidate`
- `llm_event_surprise_model_candidate`
- `ppo_execution_candidate`

## 4. Entry Gates

Each candidate requires:

- passing P24 admission gate
- Phase 25 evaluation evidence where applicable
- Phase 26 portfolio evidence where applicable
- PIT dataset contract
- walk-forward split contract
- baseline comparison plan
- OOS evaluation plan
- no production write path

PPO additionally requires:

- objective `execution_cost_reduction`
- affects_stock_selection false
- Phase 28 execution logs sufficient

## 5. Required Contracts

- `AdvancedModelAdmissionRequest`
- `AdvancedModelSandboxManifest`
- `AdvancedModelComparisonReport`
- `AdvancedModelGovernanceDecision`

Required function:

```python
evaluate_advanced_model_admission(request) -> AdvancedModelGovernanceDecision
```

Note: `request` aggregates all candidate evidence internally (`p24_gate_report`, `p25_evaluation_evidence`, `p26_portfolio_evidence`, and family-specific fields). The two-argument form `(candidate_evidence, request)` is not used; evidence is folded into the request object.

Optional later function, only after admission passes:

```python
build_advanced_model_sandbox_manifest(decision, request) -> AdvancedModelSandboxManifest
```

## 6. Non-Goals

Phase 30 must not:

- promote advanced models to production
- bypass P24/P25/P26 governance
- allow PPO stock selection
- use advanced model outputs as canonical factor fields
- auto-update production configs

## 7. Acceptance Checklist

- advanced model admission contract exists: yes/no
- family-specific gates implemented: yes/no
- XGBoost gate requires prior evidence: yes/no
- GNN/sequence gates require data sufficiency: yes/no
- PPO execution-only enforced: yes/no
- sandbox manifest shadow-only: yes/no
- no production writes: yes/no
