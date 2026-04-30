# Executor Prompt: P24-C Shadow Experiment Runner Scaffold

You are implementing P24-C for Hermes.

Read these first:

1. `docs/superpowers/specs/2026-04-25-hermes-p24-shadow-experiment-runner-spec.md`
2. `docs/superpowers/plans/2026-04-25-p24-shadow-experiment-runner.md`
3. `agent/research_v1/p24_entry_gate.py`
4. `agent/research_v1/p24_experiment_registry.py`
5. `tests/agent/research_v1/test_p24_entry_gate.py`
6. `tests/agent/research_v1/test_p24_experiment_registry.py`

## Mission

Implement a safe shadow experiment runner scaffold.

The runner executes registered `ShadowExperimentManifest` objects in `dry_run` or `shadow_stub` mode and emits auditable `ShadowExperimentRunRecord` objects.

This is not model training.

## Hard Constraints

Do not:

- train any model
- import `xgboost`, `torch`, `tensorflow`, `sklearn`, `stable_baselines`, or RL libraries
- compute real predictions
- compute IC/ICIR/PnL/promotion decisions
- write canonical `FactorSnapshot`
- modify production configs
- change thesis classification
- generate live trade signals
- add portfolio execution behavior

Use Python 3.11 and stdlib only.

## Files to Create

- `agent/research_v1/p24_shadow_runner.py`
- `tests/agent/research_v1/test_p24_shadow_runner.py`

## Required Contracts

Create:

- `ShadowExperimentRunRequest`
- `ShadowAdapterResult`
- `ShadowExperimentRunRecord`
- `ShadowRunnerResult`
- `run_shadow_experiment(manifest, adapter, run_request)`

## Required Behavior

Pre-run blocks:

- manifest status is not `registered`
- manifest does not block promotion
- manifest does not block production writes
- manifest does not block canonical snapshot writes
- manifest output contract permits canonical snapshot writes
- manifest output contract permits production config writes
- manifest output contract permits live trading
- manifest output contract does not use `net`
- run request experiment ID mismatches manifest
- run mode is not `dry_run` or `shadow_stub`
- input window is not point-in-time
- requested artifact is outside namespace
- requested artifact is forbidden

Post-adapter blocks:

- adapter produced artifact outside namespace
- adapter attempted output outside namespace
- adapter produced forbidden output
- adapter attempted forbidden output

Failure handling:

- adapter exception becomes `record.status == "failed"`
- exception class and message appear in `error_message`
- no production write flags remain true

## Required Flags

Every run record must have:

```python
no_production_write_confirmed = True
canonical_snapshot_write_blocked = True
production_config_write_blocked = True
live_trading_blocked = True
```

## Verification Commands

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p24_shadow_runner.py -q
```

Run:

```bash
python3.11 -m pytest \
  tests/agent/research_v1/test_p24_entry_gate.py \
  tests/agent/research_v1/test_p24_experiment_registry.py \
  tests/agent/research_v1/test_p24_shadow_runner.py \
  -q
```

Run:

```bash
python3.11 -m pytest \
  tests/agent/research_v1/test_p20_factor_contracts.py \
  tests/agent/research_v1/test_p20_pnl_integrity.py \
  tests/agent/research_v1/test_p21_calibration_inputs.py \
  tests/agent/research_v1/test_p22_a_plus_validity_integrity_health.py \
  tests/agent/research_v1/test_p23_shadow_calibration.py \
  tests/agent/research_v1/test_p23_shadow_observation_loop.py \
  tests/agent/research_v1/test_p24_entry_gate.py \
  tests/agent/research_v1/test_p24_experiment_registry.py \
  tests/agent/research_v1/test_p24_shadow_runner.py \
  -q
```

Run:

```bash
grep -R "import xgboost\|from xgboost\|import torch\|from torch\|import tensorflow\|from tensorflow\|stable_baselines\|import sklearn\|from sklearn" -n \
  agent/research_v1/p24_shadow_runner.py \
  tests/agent/research_v1/test_p24_shadow_runner.py || true
```

Expected: no output.

## Handoff Report

Return exactly this structure:

```text
P24-C Shadow Experiment Runner Scaffold Handoff

Changed files:
- <path> — <created/modified> — <purpose>

Tests run:
- <command> → <result>

Acceptance checklist:
- runner accepts only registered manifests: yes/no
- dry run completes without adapter: yes/no
- shadow stub calls adapter: yes/no
- pre-run safety blocks return blocked records: yes/no
- post-adapter violations return blocked records: yes/no
- adapter exceptions return failed records: yes/no
- output namespace enforced: yes/no
- forbidden artifacts enforced: yes/no
- no production write confirmed: yes/no
- run records JSON-serializable: yes/no
- no model libraries imported: yes/no
- P20-P24 regression green: yes/no

Known issues:
- <issue or None>
```
