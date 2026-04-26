# Phase 26 Shadow Portfolio Layer Spec

Date: 2026-04-25
Status: Draft for engineering handoff
Scope: Consolidated P26-A + P26-B + P26-C: shadow portfolio simulation, risk constraints, and production governance boundary

## 1. Purpose

Phase 26 compresses three planned nodes into one delivery:

```text
P26-A Portfolio Simulation Layer
P26-B Risk Budget / Position Constraint Engine
P26-C Shadow-to-Production Governance Boundary
```

The goal is to test whether a Phase 25-ready shadow model can survive portfolio-level constraints, turnover, concentration, and cost-aware net returns.

This is still shadow-only. Phase 26 does not allocate capital, send orders, or promote a model.

## 2. Core Principle

A good ranking model is not yet a portfolio.

Phase 26 must transform advisory shadow predictions into simulated portfolio weights under explicit constraints, then report portfolio behavior without touching production systems.

## 3. Non-Goals

Phase 26 must not:

- execute trades
- connect to brokers
- write production configs
- write canonical factor snapshots
- write live trade signals
- auto-promote any model
- train models
- tune model parameters
- read raw price files
- compute forward returns from prices
- import portfolio optimization libraries
- import model libraries such as `xgboost`, `sklearn`, `torch`, `tensorflow`, `stable_baselines3`, `numpy`, or `pandas`

Use Python standard library only for the first implementation.

## 4. Inputs

### 4.1 `Phase25GovernanceResult`

Required fields:

- `evaluation_report`
- `readiness_decision`

The readiness decision must provide:

- `decision`
- `training_run_id`
- `experiment_id`
- `candidate_namespace`
- `apply_to_production`
- `production_config_changes`

Accepted values:

```text
decision == "ready_for_phase26_shadow_portfolio"
apply_to_production == false
production_config_changes == {}
```

### 4.2 Shadow prediction artifacts

Phase 26 may consume either:

- the same P25-D `ShadowTrainingRunResult`
- extracted prediction rows grouped by window

Each prediction row must provide:

- `window_id`
- `snapshot_id`
- `ticker`
- `trading_day`
- `prediction_value`
- `actual_target_value`
- `candidate_namespace`

Optional fields:

- `sector`
- `adv_shares_20d`
- `estimated_cost_pct`
- `volatility_estimate`

### 4.3 `PortfolioSimulationRequest`

Required fields:

- `simulation_id`
- `training_run_id`
- `experiment_id`
- `candidate_namespace`
- `portfolio_mode`
- `initial_capital`
- `max_positions`
- `max_single_name_weight`
- `max_sector_weight`
- `gross_exposure_limit`
- `turnover_limit`
- `min_prediction_value`
- `rebalance_frequency`
- `cost_basis`
- `governance_review_enabled`
- `notes`

Accepted values:

```text
candidate_namespace starts with "shadow_meta_model."
portfolio_mode in {"long_only_top_rank", "long_short_rank_shadow"}
initial_capital > 0
max_positions >= 1
0 < max_single_name_weight <= 1
0 < max_sector_weight <= 1
0 < gross_exposure_limit <= 2
0 <= turnover_limit <= 2
rebalance_frequency in {"window", "weekly", "monthly"}
cost_basis in {"net_target", "explicit_cost_field"}
governance_review_enabled == true
```

Hermes remains operationally long-only. `long_short_rank_shadow` is allowed only for analysis and must not create live short instructions.

## 5. Outputs

### 5.1 `PortfolioHolding`

Required fields:

- `window_id`
- `snapshot_id`
- `ticker`
- `sector`
- `target_weight`
- `capped_weight`
- `prediction_value`
- `actual_target_value`
- `constraint_flags`

### 5.2 `PortfolioWindowResult`

Required fields:

- `simulation_id`
- `window_id`
- `candidate_namespace`
- `holding_count`
- `gross_exposure`
- `net_exposure`
- `turnover`
- `portfolio_gross_return`
- `portfolio_net_return`
- `max_single_name_weight`
- `max_sector_weight`
- `constraint_violations`
- `holdings`
- `status`
- `warnings`

### 5.3 `PortfolioRiskSummary`

Required fields:

- `total_windows`
- `evaluated_windows`
- `cumulative_net_return`
- `average_window_net_return`
- `volatility_proxy`
- `max_drawdown`
- `hit_rate`
- `average_turnover`
- `max_observed_single_name_weight`
- `max_observed_sector_weight`
- `constraint_violation_count`
- `warnings`

### 5.4 `Phase26GovernanceDecision`

Required fields:

- `schema_version`: `phase26_portfolio_governance.0`
- `simulation_id`
- `training_run_id`
- `experiment_id`
- `candidate_namespace`
- `decision`
- `decision_reasons`
- `production_config_changes`
- `apply_to_production`
- `next_phase_recommendation`
- `created_at`

Accepted decision values:

```text
blocked_by_phase25
blocked_by_safety
blocked_by_constraints
rejected_portfolio_underperforms
watch_more_shadow_windows
ready_for_manual_production_review
```

`production_config_changes` must always be empty.

`apply_to_production` must always be false.

### 5.5 `ShadowPortfolioSimulationReport`

Required fields:

- `schema_version`: `phase26_shadow_portfolio.0`
- `simulation_id`
- `training_run_id`
- `experiment_id`
- `candidate_namespace`
- `portfolio_mode`
- `request_config`
- `window_results`
- `risk_summary`
- `governance_decision`
- `safety_flags`
- `warnings`
- `created_at`

### 5.6 Required function

```python
run_shadow_portfolio_simulation(phase25_result, prediction_rows, request) -> ShadowPortfolioSimulationReport
```

The function must be read-only and pure with respect to production state.

## 6. Simulation Rules

### 6.1 Candidate admission

Block the simulation unless Phase 25 decision is exactly:

```text
ready_for_phase26_shadow_portfolio
```

### 6.2 Long-only rank portfolio

For `portfolio_mode == "long_only_top_rank"`:

1. group predictions by `window_id`
2. sort descending by `prediction_value`
3. keep rows with `prediction_value >= min_prediction_value`
4. keep top `max_positions`
5. assign equal raw weights
6. apply single-name cap
7. apply sector cap
8. re-normalize only if doing so does not break caps
9. compute window return as sum of capped weights times target returns

### 6.3 Long-short shadow portfolio

For `portfolio_mode == "long_short_rank_shadow"`:

- top half receives positive weights
- bottom half receives negative weights
- gross exposure must stay within `gross_exposure_limit`
- output must include `shadow_only_short_analysis` warning
- no live short instructions may be generated

### 6.4 Turnover

Turnover is computed against prior window holdings:

```text
turnover = sum(abs(current_weight[ticker] - prior_weight[ticker]))
```

If turnover exceeds `turnover_limit`, mark the window with `turnover_limit_exceeded` and cap the governance decision at `blocked_by_constraints` or `watch_more_shadow_windows`.

### 6.5 Cost handling

If `cost_basis == "net_target"`, use `actual_target_value` as already net of costs.

If `cost_basis == "explicit_cost_field"`, subtract `estimated_cost_pct` from gross target if both fields exist. If required fields are absent, block with `cost_field_missing`.

## 7. Risk Constraint Rules

A window violates constraints if:

- any capped weight exceeds `max_single_name_weight`
- any sector exposure exceeds `max_sector_weight`
- gross exposure exceeds `gross_exposure_limit`
- turnover exceeds `turnover_limit`
- holding count exceeds `max_positions`
- live trade or production output fields appear in predictions

Prediction rows must not contain these fields:

- `live_trade_signal`
- `order_id`
- `broker_instruction`
- `production_config_update`

## 8. Governance Rules

Decision order:

1. Phase 25 not ready -> `blocked_by_phase25`
2. Safety flag violation -> `blocked_by_safety`
3. Any hard constraint violation -> `blocked_by_constraints`
4. Cumulative net return <= 0 -> `rejected_portfolio_underperforms`
5. Positive but low/unstable portfolio behavior -> `watch_more_shadow_windows`
6. Strong stable behavior -> `ready_for_manual_production_review`

`ready_for_manual_production_review` is still not production approval.

It only means a human may review whether a separate production adoption spec should be written.

## 9. Serialization Rules

All contracts must expose `to_dict()` returning JSON-serializable dictionaries/lists/scalars.

No output may contain binary objects, functions, class objects, numpy arrays, pandas frames, or mapping proxies.

## 10. Tests Required

Acceptance tests must cover:

1. request validation
2. Phase 25 non-ready blocks simulation
3. production/adoption fields in Phase 25 remain false/empty
4. long-only top-rank portfolio construction
5. max positions cap
6. single-name cap
7. sector cap
8. turnover computation
9. turnover limit violation
10. net return computation
11. max drawdown computation
12. long-short mode emits shadow-only warning
13. forbidden live/production fields block simulation
14. blocked_by_constraints decision
15. rejected underperformance decision
16. ready_for_manual_production_review decision remains advisory
17. production_config_changes always empty
18. apply_to_production always false
19. JSON serialization works
20. no model or optimization libraries imported

## 11. Acceptance Checklist

A valid Phase 26 handoff must report:

- simulation request contract exists: yes/no
- portfolio holding contract exists: yes/no
- window result contract exists: yes/no
- risk summary contract exists: yes/no
- governance decision contract exists: yes/no
- Phase 25 readiness required: yes/no
- long-only simulation implemented: yes/no
- long-short shadow warning implemented: yes/no
- single-name cap implemented: yes/no
- sector cap implemented: yes/no
- turnover implemented: yes/no
- cost basis handled: yes/no
- max drawdown implemented: yes/no
- forbidden production fields blocked: yes/no
- constraints gate governance: yes/no
- production_config_changes empty: yes/no
- apply_to_production false: yes/no
- JSON serialization works: yes/no
- no model/optimizer libraries imported: yes/no
- P20-P26 regression green: yes/no

## 12. Compressed Roadmap After Phase 26

After Phase 26, later work should be compressed into larger multi-optimization nodes:

```text
Phase 27: Factor Expansion Pack
  - macro factor candidates
  - event surprise candidates
  - sector relation baseline
  - P22-style diagnostics for all candidates

Phase 28: Execution Realism Pack
  - richer slippage model
  - liquidity and ADV stress
  - execution-only PPO admission gate, no alpha role

Phase 29: Production Adoption Review Pack
  - manual production review artifacts
  - rollback plan
  - monitoring SLA
  - version freeze

Phase 30: Advanced Model Pack
  - real XGBoost training if Phase 25/26 evidence supports it
  - GNN/sequence models only through P24 admission and shadow-only diagnostics
```

Each future phase may contain several internal optimizations, but must keep a single entry gate, single acceptance report, and single review boundary.
