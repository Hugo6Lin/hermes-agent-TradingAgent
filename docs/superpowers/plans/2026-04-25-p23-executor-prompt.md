# Executor Prompt: P23 Shadow Calibration

You are the execution model for Hermes Trading Agent. Implement P23 shadow-only calibration recommendations exactly according to the spec and plan below.

## Required Workflow

Use `superpowers:executing-plans` or `superpowers:subagent-driven-development`.
Use test-driven development: write tests first, verify failure, implement minimal code, then rerun.
Do not modify production calibration parameters.
Do not claim completion without fresh verification output.

## Read First

1. `docs/superpowers/specs/2026-04-25-hermes-p23-shadow-calibration-spec.md`
2. `docs/superpowers/plans/2026-04-25-p23-shadow-calibration.md`
3. `agent/research_v1/diagnostic_reports.py`
4. `agent/research_v1/factor_diagnostics.py`
5. `agent/research_v1/calibration_config.py`

## Scope

Implement only shadow recommendations:

- evidence strength
- bounded shrinkage
- factor-to-parameter mappings
- shadow recommendation contracts
- shadow report generation
- blocked candidate reporting
- safety blockers for data integrity and health issues

Do not implement:

- production config mutation
- automatic calibration application
- portfolio optimization
- live trading
- strategy backtest

## Required New Files

- `agent/research_v1/shadow_calibration.py`
- `agent/research_v1/shadow_calibration_mappings.py`
- `tests/agent/research_v1/test_p23_shadow_calibration.py`

## Hard Review Rules

The reviewer will reject the work if:

- production configs are changed
- `calibration_status="calibrated"` appears in production defaults
- gross IC can create recommendations when net IC fails
- non-ready factors produce recommendations
- `apply_to_production` can be true
- `production_config_changes` is non-empty
- delta is unbounded
- blocked candidates are silently dropped

## Verification Commands

```bash
python3.11 -m pytest tests/agent/research_v1/test_p23_shadow_calibration.py -q
```

```bash
python3.11 -m pytest \
  tests/agent/research_v1/test_p20_factor_contracts.py \
  tests/agent/research_v1/test_p20_pnl_integrity.py \
  tests/agent/research_v1/test_p21_calibration_inputs.py \
  tests/agent/research_v1/test_p22_a_plus_validity_integrity_health.py \
  tests/agent/research_v1/test_p23_shadow_calibration.py \
  tests/agent/research_v1/test_backtest.py \
  tests/agent/research_v1/test_final_judge.py \
  tests/agent/research_v1/test_thesis_engine.py \
  tests/agent/research_v1/test_review_grade_monitor.py \
  tests/agent/research_v1/test_p4_valuation_risk.py \
  -q
```

```bash
python3.11 -m pytest tests/agent/research_v1 -q
```

If full suite has unrelated pre-existing failures, report exact failures and still provide passing P20/P21/P22/P23 regression output.

## Handoff Format

```text
P23 Shadow Calibration Handoff

Changed files:
- <path> — <created/modified> — <purpose>

Tests run:
- <command> -> <result>
- <command> -> <result>
- <command> -> <result or known failures>

Acceptance checklist:
- consumes P22-A+ reports only: yes/no
- non-ready factors blocked: yes/no
- net IC drives recommendations: yes/no
- gross-only edge rejected: yes/no
- shrinkage formula implemented: yes/no
- delta bounded: yes/no
- production_config_changes empty: yes/no
- apply_to_production always false: yes/no
- lookahead/health blockers enforced: yes/no
- no production config changed to calibrated: yes/no
- P20/P21/P22 regression green: yes/no

Known issues:
- <none or exact issue>
```
