# Executor Prompt: P23 Shadow Observation Loop

You are the execution model for Hermes Trading Agent. Implement the P23 Shadow Observation Loop exactly according to the spec and plan below.

## Required Workflow

Use `superpowers:executing-plans` or `superpowers:subagent-driven-development`.
Use test-driven development: write tests first, verify failure, implement minimal code, then rerun.
Do not modify production calibration parameters.
Do not claim completion without fresh verification output.

## Read First

1. `docs/superpowers/specs/2026-04-25-hermes-p23-shadow-observation-loop-spec.md`
2. `docs/superpowers/plans/2026-04-25-p23-shadow-observation-loop.md`
3. `agent/research_v1/shadow_calibration.py`
4. `agent/research_v1/diagnostic_reports.py`

## Scope

Implement only observation and monitoring:

- convert shadow recommendations to observation records
- preserve source P22/P23 report IDs
- evaluate shadow vs prior
- trigger revocation
- retain revoked recommendations
- generate monitor report
- determine P24 gate eligibility after enough observation windows

Do not implement:

- production config mutation
- automatic application of recommendations
- portfolio backtest
- advanced model integration
- database migration unless explicitly requested

## Required New Files

- `agent/research_v1/shadow_observation.py`
- `tests/agent/research_v1/test_p23_shadow_observation_loop.py`

## Hard Review Rules

The reviewer will reject the work if:

- recommendations are only kept in transient reports
- revoked recommendations are deleted
- P24 gate can pass without enough observation windows
- shadow recommendations are applied to production
- gross returns are used as primary evidence
- source or health degradation is ignored

## Verification Commands

```bash
python3.11 -m pytest tests/agent/research_v1/test_p23_shadow_observation_loop.py -q
```

```bash
python3.11 -m pytest \
  tests/agent/research_v1/test_p20_factor_contracts.py \
  tests/agent/research_v1/test_p20_pnl_integrity.py \
  tests/agent/research_v1/test_p21_calibration_inputs.py \
  tests/agent/research_v1/test_p22_a_plus_validity_integrity_health.py \
  tests/agent/research_v1/test_p23_shadow_calibration.py \
  tests/agent/research_v1/test_p23_shadow_observation_loop.py \
  tests/agent/research_v1/test_backtest.py \
  tests/agent/research_v1/test_final_judge.py \
  tests/agent/research_v1/test_thesis_engine.py \
  tests/agent/research_v1/test_review_grade_monitor.py \
  tests/agent/research_v1/test_p4_valuation_risk.py \
  -q
```

## Handoff Format

```text
P23 Shadow Observation Loop Handoff

Changed files:
- <path> — <created/modified> — <purpose>

Tests run:
- <command> -> <result>
- <command> -> <result>

Acceptance checklist:
- shadow recommendations converted to observations: yes/no
- source P22/P23 IDs preserved: yes/no
- shadow vs prior evaluation implemented: yes/no
- revocation triggers implemented: yes/no
- revoked recommendations retained: yes/no
- monitor report summarizes states: yes/no
- P24 gate requires enough observation windows: yes/no
- no production config modified: yes/no
- P20-P23 regression green: yes/no

Known issues:
- <none or exact issue>
```
