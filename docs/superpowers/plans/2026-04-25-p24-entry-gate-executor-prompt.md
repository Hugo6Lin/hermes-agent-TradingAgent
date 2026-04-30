# Executor Prompt: P24 Entry Gate Evaluator

You are the execution model for Hermes Trading Agent. Implement the P24 Entry Gate Evaluator exactly according to the spec and plan below.

## Required Workflow

Use `superpowers:executing-plans` or `superpowers:subagent-driven-development`.
Use test-driven development: write tests first, verify failure, implement minimal code, then rerun.
Do not train models.
Do not import model libraries.
Do not modify production calibration parameters.

## Read First

1. `docs/superpowers/specs/2026-04-25-hermes-p24-entry-gate-evaluator-spec.md`
2. `docs/superpowers/specs/2026-04-25-hermes-p24-entry-gate-spec.md`
3. `docs/superpowers/plans/2026-04-25-p24-entry-gate-evaluator.md`
4. `docs/superpowers/specs/2026-04-25-hermes-p24-p26-advanced-quant-capability-roadmap.md`

## Scope

Implement only admission gate evaluation:

- candidate request contract
- system evidence contract
- universal gate
- candidate-specific gates
- model admission report

Do not implement:

- XGBoost training
- LLM event extraction
- macro data ingestion
- GNN/Transformer/LSTM/PPO
- portfolio optimization
- production config mutation

## Required New Files

- `agent/research_v1/p24_entry_gate.py`
- `tests/agent/research_v1/test_p24_entry_gate.py`

## Hard Review Rules

The reviewer will reject the work if:

- it imports `xgboost`, `torch`, `tensorflow`, or RL libraries
- it trains or scores a model
- it writes factor outputs
- it mutates production config
- it permits production field writes
- it passes candidates without `ready_for_p24_gate`
- it silently passes unsupported candidate families

## Verification Commands

```bash
python3.11 -m pytest tests/agent/research_v1/test_p24_entry_gate.py -q
```

```bash
python3.11 -m pytest \
  tests/agent/research_v1/test_p20_factor_contracts.py \
  tests/agent/research_v1/test_p20_pnl_integrity.py \
  tests/agent/research_v1/test_p21_calibration_inputs.py \
  tests/agent/research_v1/test_p22_a_plus_validity_integrity_health.py \
  tests/agent/research_v1/test_p23_shadow_calibration.py \
  tests/agent/research_v1/test_p23_shadow_observation_loop.py \
  tests/agent/research_v1/test_p24_entry_gate.py \
  tests/agent/research_v1/test_backtest.py \
  tests/agent/research_v1/test_final_judge.py \
  tests/agent/research_v1/test_thesis_engine.py \
  tests/agent/research_v1/test_review_grade_monitor.py \
  tests/agent/research_v1/test_p4_valuation_risk.py \
  -q
```

## Handoff Format

```text
P24 Entry Gate Evaluator Handoff

Changed files:
- <path> — <created/modified> — <purpose>

Tests run:
- <command> -> <result>
- <command> -> <result>

Acceptance checklist:
- all supported candidate families evaluated: yes/no
- P23 observation readiness required: yes/no
- production field writes blocked: yes/no
- point-in-time source policy required: yes/no
- gross-return-primary candidates blocked: yes/no
- simple baseline required: yes/no
- out-of-sample plan required: yes/no
- PPO blocked without portfolio/execution layers: yes/no
- no model libraries imported: yes/no
- no production config modified: yes/no
- P20-P23 regression green: yes/no

Known issues:
- <none or exact issue>
```
