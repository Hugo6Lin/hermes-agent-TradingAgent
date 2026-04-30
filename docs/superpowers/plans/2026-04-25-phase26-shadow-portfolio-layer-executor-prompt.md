# Executor Prompt: Phase 26 Shadow Portfolio Layer

You are implementing consolidated Phase 26 for Hermes: P26-A + P26-B + P26-C in one node.

## Required Reading

1. `docs/superpowers/specs/2026-04-25-hermes-phase26-shadow-portfolio-layer-spec.md`
2. `docs/superpowers/plans/2026-04-25-phase26-shadow-portfolio-layer.md`
3. `agent/research_v1/phase25_model_governance.py` if it exists after Phase 25 implementation

## Mission

Implement shadow portfolio simulation, risk constraints, and advisory governance.

This phase tests whether a Phase 25-ready shadow model can survive portfolio-level constraints. It is not production approval.

## Files to Create

- `agent/research_v1/phase26_shadow_portfolio.py`
- `tests/agent/research_v1/test_phase26_shadow_portfolio.py`

## Hard Boundaries

Do not:

- execute trades
- connect to brokers
- write production configs
- write canonical factor snapshots
- write live trade signals
- auto-promote a model
- train models
- read raw prices
- import `xgboost`, `sklearn`, `torch`, `tensorflow`, `stable_baselines3`, `numpy`, `pandas`, or optimizer libraries

## Required Public API

Implement:

```python
PortfolioSimulationError
PortfolioSimulationRequest
PortfolioHolding
PortfolioWindowResult
PortfolioRiskSummary
Phase26GovernanceDecision
ShadowPortfolioSimulationReport
run_shadow_portfolio_simulation(phase25_result, prediction_rows, request)
```

## Required Behavior

- Require Phase 25 decision `ready_for_phase26_shadow_portfolio`
- Build long-only top-rank portfolio
- Support long-short shadow analysis only with warning
- Apply max positions
- Apply single-name cap
- Apply sector cap
- Compute turnover
- Compute window net return
- Compute cumulative net return
- Compute max drawdown
- Block forbidden live/production fields
- Keep `production_config_changes == {}`
- Keep `apply_to_production is False`

## Required Tests

Cover all acceptance tests listed in the Phase 26 spec, including constraints, governance, serialization, and no forbidden imports.

## Commands

Run Phase 26 tests:

```bash
python3.11 -m pytest tests/agent/research_v1/test_phase26_shadow_portfolio.py -q
```

Run Phase 25/26 bundle:

```bash
python3.11 -m pytest \
  tests/agent/research_v1/test_phase25_model_governance.py \
  tests/agent/research_v1/test_phase26_shadow_portfolio.py \
  -q
```

Run P20-P26 regression bundle used by prior handoffs plus Phase 25/26 tests and report exact output.

## Handoff Format

Use the handoff format from the implementation plan.
