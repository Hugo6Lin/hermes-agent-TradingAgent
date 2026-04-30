# Phase 26 Shadow Portfolio Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement consolidated P26-A/B/C: shadow portfolio simulation, risk constraints, and advisory governance in one standard-library-only module.

**Architecture:** Add `agent/research_v1/phase26_shadow_portfolio.py` with request/result contracts, portfolio construction helpers, risk metrics, and governance decisions. Add `tests/agent/research_v1/test_phase26_shadow_portfolio.py` with in-memory Phase 25-like and prediction fixtures.

**Tech Stack:** Python 3.11 standard library, dataclasses, pytest. No broker, optimizer, model, numpy, or pandas dependencies.

---

## File Map

- Create: `agent/research_v1/phase26_shadow_portfolio.py`
  - Owns contracts, simulation, risk constraints, and governance.
- Create: `tests/agent/research_v1/test_phase26_shadow_portfolio.py`
  - Owns Phase 26 acceptance tests.
- Do not modify production configs.
- Do not modify persistence.
- Do not connect to broker or raw price data.

---

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

All result contracts must have `to_dict()`.

---

### Task 1: Contract and Admission Tests

- [ ] **Step 1: Create test file**

Create `tests/agent/research_v1/test_phase26_shadow_portfolio.py` with fixtures for:

- Phase 25 ready result
- Phase 25 blocked result
- prediction rows across four windows
- request builder

Initial tests:

```python
- request rejects unsafe namespace
- request rejects invalid exposure/cap values
- Phase 25 non-ready blocks simulation
- ready Phase 25 produces JSON-serializable report
```

- [ ] **Step 2: Run and confirm failure**

```bash
python3.11 -m pytest tests/agent/research_v1/test_phase26_shadow_portfolio.py -q
```

Expected: FAIL because module does not exist.

---

### Task 2: Implement Contracts and Admission Gate

- [ ] **Step 1: Create module**

Create `agent/research_v1/phase26_shadow_portfolio.py` using dataclasses and standard library only.

Implement:

- request validation
- `_as_dict`
- `_utc_now`
- safety extraction from Phase 25 result
- block report for non-ready Phase 25

- [ ] **Step 2: Run initial tests**

```bash
python3.11 -m pytest tests/agent/research_v1/test_phase26_shadow_portfolio.py -q
```

Expected: initial tests PASS.

---

### Task 3: Implement Long-Only Portfolio Construction

- [ ] **Step 1: Add tests**

Add tests for:

```python
- top prediction rows become holdings
- max_positions caps holding count
- single-name cap limits capped_weight
- sector cap limits aggregate sector exposure
- net window return is weighted sum of target returns
```

- [ ] **Step 2: Implement long-only simulation**

Implement helper flow:

```text
group by window_id
sort by prediction_value descending
filter prediction_value >= min_prediction_value
select max_positions
assign equal weights
apply single-name cap
apply sector cap
compute gross/net exposure
compute weighted net return
```

- [ ] **Step 3: Run tests**

```bash
python3.11 -m pytest tests/agent/research_v1/test_phase26_shadow_portfolio.py -q
```

Expected: PASS.

---

### Task 4: Implement Turnover and Risk Summary

- [ ] **Step 1: Add tests**

Add tests for:

```python
- turnover computed from prior window weights
- turnover limit creates constraint violation
- cumulative net return computed
- max drawdown computed peak-to-trough
- hit rate computed from positive window returns
```

- [ ] **Step 2: Implement risk helpers**

Implement:

- `_turnover(current, prior)`
- `_max_drawdown(window_returns)`
- `_risk_summary(window_results)`

- [ ] **Step 3: Run tests**

```bash
python3.11 -m pytest tests/agent/research_v1/test_phase26_shadow_portfolio.py -q
```

Expected: PASS.

---

### Task 5: Implement Governance and Safety Blocks

- [ ] **Step 1: Add tests**

Add tests for:

```python
- forbidden live/production fields block simulation
- long_short_rank_shadow emits shadow_only_short_analysis warning
- hard constraint violation -> blocked_by_constraints
- negative cumulative return -> rejected_portfolio_underperforms
- positive stable return -> ready_for_manual_production_review
- production_config_changes == {}
- apply_to_production is False
- no model/optimizer libraries imported
```

- [ ] **Step 2: Implement governance decisions**

Use exact decision order from spec:

```text
blocked_by_phase25
blocked_by_safety
blocked_by_constraints
rejected_portfolio_underperforms
watch_more_shadow_windows
ready_for_manual_production_review
```

- [ ] **Step 3: Run tests**

```bash
python3.11 -m pytest tests/agent/research_v1/test_phase26_shadow_portfolio.py -q
```

Expected: PASS.

---

### Task 6: Regression and Handoff

- [ ] **Step 1: Run Phase 26 test**

```bash
python3.11 -m pytest tests/agent/research_v1/test_phase26_shadow_portfolio.py -q
```

- [ ] **Step 2: Run P25/P26 bundle**

```bash
python3.11 -m pytest \
  tests/agent/research_v1/test_phase25_model_governance.py \
  tests/agent/research_v1/test_phase26_shadow_portfolio.py \
  -q
```

- [ ] **Step 3: Run P20-P26 regression bundle**

Use the existing P20-P25 regression bundle, add Phase 25 and Phase 26 tests, and report exact output.

- [ ] **Step 4: Handoff**

```text
Phase 26 Shadow Portfolio Layer Handoff

Changed files:

agent/research_v1/phase26_shadow_portfolio.py — created — shadow portfolio simulation, risk constraints, governance
tests/agent/research_v1/test_phase26_shadow_portfolio.py — created — acceptance tests

Tests run:

python3.11 -m pytest tests/agent/research_v1/test_phase26_shadow_portfolio.py -q → N passed
python3.11 -m pytest [Phase25/26 bundle] -q → N passed
python3.11 -m pytest [P20-P26 regression bundle] -q → N passed

Acceptance checklist:

simulation request contract exists: yes/no
portfolio holding contract exists: yes/no
window result contract exists: yes/no
risk summary contract exists: yes/no
governance decision contract exists: yes/no
Phase 25 readiness required: yes/no
long-only simulation implemented: yes/no
long-short shadow warning implemented: yes/no
single-name cap implemented: yes/no
sector cap implemented: yes/no
turnover implemented: yes/no
cost basis handled: yes/no
max drawdown implemented: yes/no
forbidden production fields blocked: yes/no
constraints gate governance: yes/no
production_config_changes empty: yes/no
apply_to_production false: yes/no
JSON serialization works: yes/no
no model/optimizer libraries imported: yes/no
P20-P26 regression green: yes/no

Known issues:

None.
```
