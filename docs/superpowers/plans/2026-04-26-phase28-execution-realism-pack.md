# Phase 28 Execution Realism Pack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add standard-library execution realism estimates and an execution-only PPO admission gate.

**Architecture:** Create `agent/research_v1/phase28_execution_realism.py` and `tests/agent/research_v1/test_phase28_execution_realism.py`.

**Tech Stack:** Python 3.11 standard library, dataclasses, pytest.

---

## Tasks

### Task 1: Contracts
- [ ] Implement `ExecutionRealismRequest`, `SlippageEstimate`, `LiquidityStressScenario`, `ExecutionRealismReport`, `PPOExecutionAdmissionDecision`.
- [ ] Add JSON-safe `to_dict()`.

### Task 2: Slippage and Cost Estimation
- [ ] Compute commission, half-spread, impact, ADV participation, volatility penalty, stress penalty.
- [ ] Tests for each cost component.

### Task 3: Liquidity Stress
- [ ] Add stress scenarios that multiply spread/impact/vol penalties.
- [ ] Flag stress cost exceeding expected edge.

### Task 4: PPO Admission Gate
- [ ] Require `objective == execution_cost_reduction`.
- [ ] Require `affects_stock_selection is False`.
- [ ] Require portfolio and execution logs.
- [ ] Tests for blocked alpha/selection PPO.

### Task 5: Regression
- [ ] Run Phase 28 tests.
- [ ] Run P20-Phase28 regression bundle.
