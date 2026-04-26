# Phase 28 Execution Realism Pack Spec

Date: 2026-04-26
Status: Draft for engineering handoff
Scope: Slippage, liquidity stress, ADV realism, and execution-only PPO admission boundary

## 1. Purpose

Phase 28 improves execution realism without allowing execution automation.

```text
Phase 28 = richer cost/slippage + liquidity stress + execution-only PPO gate
```

## 2. Core Principle

Alpha that disappears after realistic execution costs is not alpha.

Phase 28 upgrades cost and liquidity modeling used by shadow simulations, but it must not place orders or optimize live execution.

## 3. Non-Goals

Phase 28 must not:

- execute trades
- connect to brokers
- route orders
- train PPO
- import RL libraries
- modify production configs
- override Phase 26 governance
- create live signals

## 4. Required Contracts

- `ExecutionRealismRequest`
- `SlippageEstimate`
- `LiquidityStressScenario`
- `ExecutionRealismReport`
- `PPOExecutionAdmissionDecision`

Required functions:

```python
estimate_execution_costs(trade_intents, market_liquidity, request) -> ExecutionRealismReport
evaluate_ppo_execution_admission(evidence, request) -> PPOExecutionAdmissionDecision
```

## 5. Cost Model Requirements

For each simulated trade intent, compute:

- commission bps
- half-spread bps
- impact bps
- ADV participation
- volatility penalty
- liquidity stress penalty
- total estimated cost bps

Must flag:

- `adv_limit_exceeded`
- `spread_missing`
- `liquidity_data_missing`
- `stress_cost_exceeds_edge`

## 6. PPO Admission Boundary

PPO may be admitted only for execution research if:

- objective is `execution_cost_reduction`
- affects_stock_selection is false
- portfolio layer exists
- sufficient execution logs exist
- no live trading effect exists

The output is advisory and must not start PPO training.

## 7. Acceptance Checklist

- slippage contract exists: yes/no
- liquidity stress contract exists: yes/no
- execution cost estimation implemented: yes/no
- ADV participation implemented: yes/no
- stress penalties implemented: yes/no
- missing liquidity data flagged: yes/no
- cost can exceed alpha edge: yes/no
- PPO execution-only gate implemented: yes/no
- PPO stock-selection role blocked: yes/no
- no broker/live execution: yes/no
- no RL/model libraries imported: yes/no
