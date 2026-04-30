# Executor Prompt: P20-P22 P&L Integrity and Factor Calibration

You are the execution model for Hermes. Implement the P20-P22 P&L integrity plan exactly, using TDD and small verification checkpoints.

## Required reading order

1. `AGENT.md`
2. `agent/research_v1/AGENT.md`
3. `docs/superpowers/specs/2026-04-24-hermes-p20-p22-factor-calibration-roadmap-spec.md`
4. `docs/superpowers/plans/2026-04-24-p20-p22-pnl-integrity-factor-calibration.md`
5. Existing tests near each touched module, especially:
   - `tests/agent/research_v1/test_backtest.py`
   - `tests/agent/research_v1/test_database.py`
   - `tests/agent/research_v1/test_thesis_engine.py`
   - `tests/agent/research_v1/test_final_judge.py`
   - `tests/agent/research_v1/test_review_grade_monitor.py`
   - `tests/agent/research_v1/test_p4_valuation_risk.py`
   - `tests/agent/research_v1/test_p5_service_mode.py`

## Mandatory workflow

Use test-first implementation.

For each task in the implementation plan:

1. Write the failing test first.
2. Run the exact focused test and confirm it fails for the expected reason.
3. Implement the minimal production code.
4. Run the focused test and confirm it passes.
5. Run the adjacent regression tests listed in the task.
6. Commit after the task if git is available. If git is not available, record changed files.

Do not skip red/green verification.

## Scope boundaries

Do not add:

- auto-trading
- bearish execution
- a portfolio optimizer
- a new P19.5 phase
- a new report-delivery architecture
- live market data requirements in tests
- real LLM/API calls in tests

Do not let report/image generation become a decision authority.

## Acceptance requirements

Your work is acceptable only if all of these are true:

- `max_drawdown_pct` uses true peak-to-trough drawdown.
- Backtest/forward outcomes include schema version, gross return, net return, transaction cost, and cost source.
- `CostModel` includes commission, half-spread, ADV-aware impact, position-as-ADV, illiquidity penalty, and liquidity flags.
- Fixed `-7% / +12%` exits are replaced by ATR/realized-vol adaptive `ExitPlan` output.
- Exit multiples are config/prior-only calibration inputs, not silent magic constants.
- Thesis quality penalizes missing expected fields.
- Thesis thresholds load from calibration config.
- LLM verbal verdicts are bounded overlays and cannot set base scores directly.
- Zero role weights require `disabled_with_reason`.
- Valuation supports minimal sector-indexed benchmark multiples before P22 diagnostics.
- Risk metrics include Sortino, Calmar, and Expected Shortfall/CVaR.
- Cosmetic stress testing is disclosed as disabled/hidden until real resimulation exists.
- Existing Phase 19 image-report behavior remains downstream and compatible.

## Final response format

At completion, report:

```text
Changed files:
- ...

Tests run:
- command: result

Acceptance checklist:
- corrected drawdown: yes/no
- cost-aware net returns: yes/no
- adaptive exits prior-only: yes/no
- quality coverage fixed: yes/no
- LLM overlay bounded: yes/no
- zero-weight guard: yes/no
- threshold config: yes/no
- sector valuation: yes/no
- added risk metrics: yes/no
- stress output hidden/flagged: yes/no

Known issues:
- ...
```

If any verification fails, stop and report exact failure output. Do not hand-wave failing tests.
