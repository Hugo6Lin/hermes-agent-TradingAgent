# P24-C Shadow Experiment Runner Scaffold Spec

Date: 2026-04-25
Status: Draft for engineering handoff
Scope: Safe shadow-run scaffold for registered P24 advanced model/factor experiments

## 1. Purpose

P24-A decides whether a candidate may enter shadow development.

P24-B registers that candidate as an auditable `ShadowExperimentManifest`.

P24-C adds the runner scaffold that can execute a registered shadow experiment in a controlled, non-production mode and emit an auditable run record.

The runner is not a model trainer. It is a safety wrapper around future experiment adapters.

## 2. Core Rule

Only registered manifests may run.

Every run must produce a `ShadowExperimentRunRecord`.

No run may write canonical factor snapshots, production configs, live trade signals, or thesis classifications.

## 3. Non-Goals

P24-C must not:

- train XGBoost, GNN, LSTM, Transformer, PPO, or LLM models
- import `xgboost`, `torch`, `tensorflow`, `sklearn`, `stable_baselines`, or RL libraries
- calculate IC, ICIR, PnL, promotion decisions, or shrinkage weights
- modify `FactorSnapshot`
- modify `ThesisThresholdConfig`, `RoleWeightConfig`, `ExitPlanConfig`, or other production configs
- produce live trade signals
- execute portfolio or order-management logic

## 4. Inputs

### 4.1 `ShadowExperimentManifest`

The runner accepts only manifests with:

```text
status == "registered"
promotion_blocked == true
production_write_blocked == true
canonical_snapshot_write_blocked == true
output_contract.writes_canonical_factor_snapshot == false
output_contract.writes_production_config == false
output_contract.affects_live_trading == false
output_contract.return_basis == "net"
```

### 4.2 `ShadowExperimentRunRequest`

Required fields:

- `run_id`
- `experiment_id`
- `run_mode`: `dry_run` or `shadow_stub`
- `input_window`
- `requested_artifacts`
- `operator`
- `reason`
- `notes`

`input_window` must declare:

- `start_date`
- `end_date`
- `data_as_of_policy`
- `point_in_time_required`

Accepted values:

```text
point_in_time_required == true
data_as_of_policy == "manifest_point_in_time_policy"
```

### 4.3 Adapter Interface

The runner accepts an adapter object or callable with:

```python
run(manifest, request) -> ShadowAdapterResult
```

The adapter may return shadow artifacts only. It must not receive production write handles.

## 5. Output Contracts

### 5.1 `ShadowAdapterResult`

Required fields:

- `adapter_name`
- `adapter_version`
- `produced_artifacts`
- `attempted_outputs`
- `metrics`
- `logs`
- `warnings`

`produced_artifacts` and `attempted_outputs` must be namespaced under the manifest `shadow_namespace`.

### 5.2 `ShadowExperimentRunRecord`

Required fields:

- `schema_version`: `p24_run.0`
- `run_id`
- `experiment_id`
- `candidate_id`
- `candidate_family`
- `manifest_schema_version`
- `manifest_status`
- `run_mode`
- `input_window`
- `output_namespace`
- `adapter_name`
- `adapter_version`
- `status`: `completed`, `blocked`, or `failed`
- `produced_artifacts`
- `blocked_artifacts`
- `safety_checks`
- `warnings`
- `error_message`
- `no_production_write_confirmed`
- `canonical_snapshot_write_blocked`
- `production_config_write_blocked`
- `live_trading_blocked`
- `started_at`
- `completed_at`
- `notes`

### 5.3 `ShadowRunnerResult`

Required fields:

- `record`
- `adapter_result`

If the run is blocked before adapter execution, `adapter_result` must be `None`.

## 6. Safety Checks

The runner must evaluate these checks before adapter execution:

- manifest is registered
- manifest promotion is blocked
- manifest production writes are blocked
- manifest canonical snapshot writes are blocked
- manifest output contract is shadow-only
- run request experiment ID matches manifest experiment ID
- run mode is allowed
- input window is point-in-time
- requested artifacts are within namespace

The runner must evaluate these checks after adapter execution:

- adapter artifacts are within namespace
- adapter attempted outputs are within namespace
- adapter did not attempt forbidden outputs
- adapter did not attempt canonical snapshot writes
- adapter did not attempt production config writes
- adapter did not attempt live trading effects

## 7. Artifact Rules

Allowed artifacts:

- any artifact whose name starts with `manifest.shadow_namespace`
- diagnostic logs scoped to the experiment run
- dry-run metadata

Forbidden artifacts:

- `company_quality_score`
- `valuation_attractiveness_score`
- `timing_market_fit_score`
- `llm_adjustment_total`
- `classification`
- `production_config`
- `canonical_factor_snapshot`
- `live_trade_signal`

If forbidden artifacts are attempted, the run record status must be `blocked`.

## 8. Error Handling

The runner must not throw for normal safety blocks. It should return `ShadowRunnerResult` with:

```text
record.status == "blocked"
record.blocked_artifacts includes blocked item or reason
record.error_message explains the block
adapter_result == None if blocked before adapter execution
```

Adapter exceptions should return:

```text
record.status == "failed"
record.error_message contains exception class and message
no_production_write_confirmed == true
```

The runner may raise only for programmer errors such as missing required dataclass fields.

## 9. Tests

Acceptance tests must cover:

1. dry-run registered manifest completes without adapter execution
2. shadow stub registered manifest executes adapter and records artifacts
3. unregistered/revoked manifest is blocked
4. experiment ID mismatch is blocked
5. non-point-in-time input window is blocked
6. requested artifact outside namespace is blocked
7. adapter artifact outside namespace is blocked
8. adapter forbidden output is blocked
9. adapter exception becomes failed run record
10. record confirms no production write, no canonical snapshot write, and no live trading
11. run record `to_dict()` is JSON-serializable
12. no model libraries are imported

## 10. Acceptance Checklist

- Runner accepts only registered manifests.
- Runner produces `ShadowExperimentRunRecord`.
- Dry run works without adapter execution.
- Shadow stub run calls adapter.
- Pre-run safety blocks return `blocked` records.
- Post-run adapter violations return `blocked` records.
- Adapter exceptions return `failed` records.
- Output namespace is enforced.
- Forbidden artifacts are enforced.
- No production write is possible through runner contracts.
- Run records are JSON-serializable.
- No model libraries are imported.

## 11. Boundary to P24-D

P24-C ends at safe runner scaffolding.

P24-D may add experiment-result storage and observation integration, but P24-D still must not train real advanced models or promote outputs to production without a separate gate.
