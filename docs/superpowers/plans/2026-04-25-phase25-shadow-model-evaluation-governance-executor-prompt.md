# Executor Prompt: Phase 25 Shadow Model Evaluation and Governance

You are implementing consolidated Phase 25 for Hermes: P25-E + P25-F in one node.

## Required Reading

1. `docs/superpowers/specs/2026-04-25-hermes-phase25-shadow-model-evaluation-governance-spec.md`
2. `docs/superpowers/plans/2026-04-25-phase25-shadow-model-evaluation-governance.md`
3. `agent/research_v1/p25_shadow_training_runner.py`
4. `tests/agent/research_v1/test_p25_shadow_training_runner.py`

## Mission

Implement advisory evaluation and governance for P25-D shadow training outputs.

This phase must compare trained shadow predictions against a baseline and decide whether the candidate is:

- blocked by safety
- blocked by sample size
- rejected for underperformance
- watch more windows
- ready for Phase 26 shadow portfolio simulation

## Files to Create

- `agent/research_v1/phase25_model_governance.py`
- `tests/agent/research_v1/test_phase25_model_governance.py`

## Hard Boundaries

Do not:

- train models
- tune hyperparameters
- write production configs
- write canonical factor snapshots
- write live trade signals
- auto-promote a model
- read raw prices
- import `xgboost`, `sklearn`, `torch`, `tensorflow`, `stable_baselines3`, `numpy`, or `pandas`

## Required Public API

Implement:

```python
Phase25GovernanceError
Phase25EvaluationRequest
WindowEvaluationResult
ShadowModelEvaluationReport
PromotionReadinessDecision
Phase25GovernanceResult
evaluate_shadow_model_governance(training_result, baseline_predictions, request)
```

All result contracts must have `to_dict()` methods returning JSON-serializable plain structures.

## Required Metrics

Implement:

- per-window rank IC
- per-window directional hit rate
- per-window spread return
- aggregate model metrics
- aggregate baseline metrics
- aggregate improvements

If `baseline_predictions is None`, generate deterministic zero-score baseline from model validation predictions.

## Required Decision Gate

Use this order:

1. safety violation -> `blocked_by_safety`
2. sample too small -> `blocked_by_sample_size`
3. primary metric improvement <= 0 -> `rejected_underperforms_baseline`
4. improvement positive but below thresholds -> `watch_more_windows`
5. thresholds pass -> `ready_for_phase26_shadow_portfolio`

`production_config_changes` must always be `{}`.

`apply_to_production` must always be `False`.

## Required Tests

Cover:

- request validation
- unsafe training blocks readiness
- non-net target blocks readiness
- namespace mismatch blocks readiness
- baseline missing snapshot blocks readiness
- zero baseline generation
- rank IC, hit rate, spread return
- aggregate improvements
- insufficient windows and predictions
- underperformance rejection
- watch-more decision
- ready-for-phase26 decision
- production changes empty
- apply_to_production false
- JSON serialization
- no model libraries imported

## Commands

Run Phase 25 tests:

```bash
python3.11 -m pytest tests/agent/research_v1/test_phase25_model_governance.py -q
```

Run P25 bundle:

```bash
python3.11 -m pytest \
  tests/agent/research_v1/test_p25_xgboost_shadow_adapter.py \
  tests/agent/research_v1/test_p25_training_dataset_builder.py \
  tests/agent/research_v1/test_p25_split_manifest_builder.py \
  tests/agent/research_v1/test_p25_shadow_training_runner.py \
  tests/agent/research_v1/test_phase25_model_governance.py \
  -q
```

Run P20-P25 regression bundle used in the prior handoffs and include exact output.

## Handoff Format

Use the handoff format from the implementation plan.
