# Executor Prompt: P22-A+ Validity, Integrity, and Health

You are the execution model for Hermes Trading Agent. Implement P22-A+ exactly according to the spec and plan below.

## Required Workflow

Use `superpowers:executing-plans` or `superpowers:subagent-driven-development`.
Use test-driven development: write tests first, verify failure, implement minimal code, then rerun.
Do not modify production calibration parameters.
Do not claim completion without fresh verification output.

## Read First

1. `docs/superpowers/specs/2026-04-25-hermes-p22-a-plus-validity-integrity-health-spec.md`
2. `docs/superpowers/plans/2026-04-25-p22-a-plus-validity-integrity-health.md`
3. `agent/research_v1/p22_return_selector.py`
4. `agent/research_v1/factor_persistence.py`
5. `agent/research_v1/contracts.py`
6. `agent/research_v1/calibration_config.py`

## Scope

Implement only P22-A+:

- data integrity preflight
- lookahead bias checks
- source audit gap checks
- restatement-risk flags
- sector snapshot gap flags
- IC / gross IC / net IC
- ICIR
- IC decay
- Newey-West/HAC t-stat
- orthogonality
- autocorrelation
- calibration readiness report
- daily factor health check
- final report assembly

Do not implement:

- shrinkage calibration
- production parameter updates
- portfolio optimization
- event-driven portfolio backtest
- real-time market data ingestion
- standalone sentiment monitoring system

## Required New Files

- `agent/research_v1/data_integrity.py`
- `agent/research_v1/newey_west.py`
- `agent/research_v1/diagnostic_gates.py`
- `agent/research_v1/factor_diagnostics.py`
- `agent/research_v1/factor_health_check.py`
- `agent/research_v1/diagnostic_reports.py`
- `tests/agent/research_v1/test_p22_a_plus_validity_integrity_health.py`

## Hard Review Rules

The reviewer will reject the work if:

- diagnostics read raw price history
- lookahead-violating rows enter IC by default
- net returns are not the default
- gross IC can pass readiness when net IC fails
- source audit gaps are silently treated as clean
- sector snapshot absence is silently ignored
- small samples can pass readiness
- HAC/Newey-West absence is hidden
- daily health checks are cosmetic and do not compute drift/completion metrics
- any production config is changed to `calibrated`

## Verification Commands

Run before handoff:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p22_a_plus_validity_integrity_health.py -q
```

```bash
python3.11 -m pytest \
  tests/agent/research_v1/test_p20_factor_contracts.py \
  tests/agent/research_v1/test_p20_pnl_integrity.py \
  tests/agent/research_v1/test_p21_calibration_inputs.py \
  tests/agent/research_v1/test_p22_a_plus_validity_integrity_health.py \
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
P22-A+ Validity, Integrity, and Health Handoff

Changed files:
- <path> — <created/modified> — <purpose>

Tests run:
- <command> -> <result>
- <command> -> <result>
- <command> -> <result or known failures>

Acceptance checklist:
- lookahead rows excluded by default: yes/no
- source audit gaps visible: yes/no
- sector snapshot gaps visible: yes/no
- net return default: yes/no
- gross vs net IC comparison: yes/no
- IC/ICIR/decay/HAC implemented: yes/no
- orthogonality implemented: yes/no
- autocorrelation implemented: yes/no
- daily factor health check implemented: yes/no
- forward-return completion gaps detected: yes/no
- no production config changed to calibrated: yes/no
- P20/P21 regression green: yes/no

Known issues:
- <none or exact issue>
```
