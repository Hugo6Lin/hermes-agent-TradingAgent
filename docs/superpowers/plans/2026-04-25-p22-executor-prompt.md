# Executor Prompt: P22 Validity Diagnostics

You are the execution model for Hermes Trading Agent. Implement P22-A validity-first diagnostics exactly according to the spec and plan below.

## Required Workflow

Use `superpowers:executing-plans` or `superpowers:subagent-driven-development`.
Use test-driven development. Write tests first, verify failure, implement minimal code, then rerun.
Do not modify production calibration parameters.
Do not claim completion without fresh verification output.

## Read First

1. `docs/superpowers/specs/2026-04-25-hermes-p22-validity-diagnostics-spec.md`
2. `docs/superpowers/plans/2026-04-25-p22-validity-diagnostics.md`
3. `agent/research_v1/p22_return_selector.py`
4. `agent/research_v1/factor_persistence.py`
5. `agent/research_v1/contracts.py`

## Scope

Implement only P22-A validity diagnostics:

- IC
- ICIR
- IC decay
- gross vs net IC comparison
- autocorrelation
- orthogonality
- missing-return rate
- sample/readiness gates
- Newey-West/HAC t-stat helper
- validity report object

Do not implement shrinkage updates. Do not update `RoleWeightConfig`, `ThesisThresholdConfig`, `ExitPlanConfig`, `PositionSizingConfig`, or any production config to `calibrated`.

## Required New Files

- `agent/research_v1/newey_west.py`
- `agent/research_v1/diagnostic_gates.py`
- `agent/research_v1/factor_diagnostics.py`
- `tests/agent/research_v1/test_p22_validity_diagnostics.py`

## Hard Review Rules

The reviewer will reject the work if:

- diagnostics read raw price history
- net returns are not the default
- gross IC can make a factor ready when net IC is weak
- small samples can pass readiness
- high cross-factor correlation is ignored
- HAC/Newey-West absence is hidden
- production configs are changed to `calibrated`
- tests cover only happy paths

## Verification Commands

Run these before handoff:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p22_validity_diagnostics.py -q
```

```bash
python3.11 -m pytest \
  tests/agent/research_v1/test_p20_factor_contracts.py \
  tests/agent/research_v1/test_p20_pnl_integrity.py \
  tests/agent/research_v1/test_p21_calibration_inputs.py \
  tests/agent/research_v1/test_p22_validity_diagnostics.py \
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

If full suite has unrelated pre-existing failures, report exact failures and still provide passing P20/P21/P22 regression output.

## Handoff Format

```text
P22 Validity Diagnostics Handoff

Changed files:
- <path> — <created/modified> — <purpose>

Tests run:
- <command> -> <result>
- <command> -> <result>
- <command> -> <result or exact known failures>

Acceptance checklist:
- consumes FactorSnapshot/ForwardReturnObservation rows only: yes/no
- net return default: yes/no
- gross vs net IC comparison: yes/no
- IC/ICIR/decay implemented: yes/no
- orthogonality implemented: yes/no
- autocorrelation implemented: yes/no
- sample gates block small samples: yes/no
- Newey-West/HAC implemented or explicitly blocks readiness: yes/no
- no production configs modified to calibrated: yes/no
- P20/P21 regression green: yes/no

Known issues:
- <none or exact issue>
```
