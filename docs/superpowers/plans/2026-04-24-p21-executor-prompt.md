# Executor Prompt: P21 Calibration Inputs

You are the execution model for Hermes Trading Agent. Implement P21 exactly according to the spec and plan below.

## Required Skills / Workflow

Use `superpowers:executing-plans` or `superpowers:subagent-driven-development`.
Use test-driven development: write/adjust tests first, run them to see failure, implement minimal code, then rerun.
Do not skip verification.
Do not claim completion without fresh command output.

## Primary Files to Read First

1. `docs/superpowers/specs/2026-04-24-hermes-p21-calibration-inputs-spec.md`
2. `docs/superpowers/plans/2026-04-24-p21-calibration-inputs.md`
3. `docs/superpowers/specs/2026-04-24-hermes-p20-p22-factor-calibration-roadmap-spec.md`
4. Existing implementation files:
   - `agent/research_v1/calibration_config.py`
   - `agent/research_v1/exit_planning.py`
   - `agent/research_v1/final_judge.py`
   - `agent/research_v1/grading.py`
   - `agent/research_v1/valuation_models.py`
   - `agent/research_v1/trade_plan.py`
   - `agent/research_v1/stress_testing.py`

## Implementation Scope

Implement only P21 Calibration Inputs. Do not start P22 shrinkage, IC/ICIR engines, portfolio optimization, autonomous trading, or real historical stress resimulation.

Required deliverables:

1. `calibration_config.py` owns or re-exports all P21 config contracts:
   - `CalibrationMetadata`
   - `ThesisThresholdConfig`
   - `RoleWeight` / `RoleWeightConfig`
   - `GradingWeightConfig`
   - `ExitPlanConfig`
   - `SectorBenchmarkConfig`
   - `PositionSizingConfig`
   - `RegimeGateConfig`

2. Existing modules consume config instead of hidden literals:
   - `exit_planning.py`: canonical `ExitPlanConfig`, output includes `config_version` and `calibration_status`
   - `final_judge.py`: supports injected `RoleWeightConfig`, keeps backward-compatible `ROLE_WEIGHTS`
   - `grading.py`: validates dynamic overrides after merging; no invalid sum allowed
   - `valuation_models.py`: emits sector benchmark metadata and fallback metadata
   - `trade_plan.py`: emits volatility-aware sizing fields while preserving `suggested_position_size`
   - `stress_testing.py`: boss-facing output remains false unless real resimulation is enabled

3. Add new helper modules:
   - `agent/research_v1/regime_gate.py`
   - `agent/research_v1/p22_return_selector.py`

4. Add focused tests:
   - `tests/agent/research_v1/test_p21_calibration_inputs.py`

## Hard Acceptance Rules

The reviewer will reject the work if any of these are true:

- thesis thresholds are hardcoded inside `_classify()`
- role weights can be zero without `disabled_with_reason`
- `FinalJudge` cannot accept injected `RoleWeightConfig`
- `GradingAgent(dynamic_weights=...)` can create weights that do not sum to 1.0
- exit stop/target multiples are not exposed as `prior_only`
- sector valuation silently falls back to default without metadata
- trade sizing remains only an integer with no volatility/cap metadata
- regime gate returns `pass` when required regime inputs are missing
- P22 return selection defaults to gross returns instead of net returns
- stress testing is boss-facing without real resimulation
- production defaults use `calibration_status="calibrated"`

## Verification Commands

Run these before handoff:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p21_calibration_inputs.py -q
```

```bash
python3.11 -m pytest \
  tests/agent/research_v1/test_p20_factor_contracts.py \
  tests/agent/research_v1/test_p20_pnl_integrity.py \
  tests/agent/research_v1/test_backtest.py \
  tests/agent/research_v1/test_final_judge.py \
  tests/agent/research_v1/test_thesis_engine.py \
  tests/agent/research_v1/test_review_grade_monitor.py \
  tests/agent/research_v1/test_p4_valuation_risk.py \
  tests/agent/research_v1/test_p21_calibration_inputs.py \
  -q
```

```bash
python3.11 -m pytest tests/agent/research_v1 -q
```

If the full suite has unrelated pre-existing failures, report the exact failures and still provide the passing P20/P21 regression bundle output.

## Handoff Report Format

Return this exact structure:

```text
P21 Calibration Inputs Handoff

Changed files:
- <path> — <created/modified> — <one-line purpose>

Tests run:
- <command> -> <result>
- <command> -> <result>
- <command> -> <result or exact known failures>

Acceptance checklist:
- config contracts versioned/prior-only: yes/no
- thesis thresholds config-driven: yes/no
- role weights injectable and zero-guarded: yes/no
- grading dynamic overrides validated: yes/no
- exit multiples prior-only and versioned: yes/no
- sector valuation metadata emitted: yes/no
- volatility-aware sizing fields emitted: yes/no
- regime gate missing data does not pass: yes/no
- P22 return selector defaults to net: yes/no
- stress output hidden without resimulation: yes/no

Known issues:
- <none or exact issue>
```

Do not commit unless explicitly asked.
