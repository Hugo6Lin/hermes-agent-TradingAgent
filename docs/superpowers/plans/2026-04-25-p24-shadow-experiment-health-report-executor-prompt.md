# Executor Prompt: P24-E Shadow Experiment Health Report

You are implementing P24-E for Hermes.

Read these first:

1. `docs/superpowers/specs/2026-04-25-hermes-p24-shadow-experiment-health-report-spec.md`
2. `docs/superpowers/plans/2026-04-25-p24-shadow-experiment-health-report.md`
3. `agent/research_v1/p24_experiment_registry.py`
4. `agent/research_v1/p24_shadow_runner.py`
5. `agent/research_v1/p24_run_persistence.py`
6. `tests/agent/research_v1/test_p24_experiment_registry.py`
7. `tests/agent/research_v1/test_p24_shadow_runner.py`
8. `tests/agent/research_v1/test_p24_run_persistence.py`

## Mission

Implement a read-only health report for P24 shadow experiments.

The report summarizes manifests and persisted run records. It must be useful for research/management review while remaining strictly advisory.

## Hard Constraints

Do not:

- train any model
- import `xgboost`, `torch`, `tensorflow`, `sklearn`, `stable_baselines`, or RL libraries
- run shadow experiments inside the report builder
- save new run records
- revoke experiments
- promote experiments
- write canonical `FactorSnapshot`
- modify production configs
- generate live trade signals
- compute IC/ICIR/PnL/model performance metrics beyond persisted run status counts

Use Python 3.11 and stdlib only.

## Files to Create

- `agent/research_v1/p24_health_report.py`
- `tests/agent/research_v1/test_p24_health_report.py`

## Required Contracts

Create:

- `ExperimentHealthRow`
- `ShadowExperimentHealthReport`
- `build_shadow_experiment_health_report(manifests, run_store)`

## Required Behavior

The report must compute:

- total experiments
- registered count
- revoked count
- archived count
- healthy count
- watch count
- no-runs count
- revocation-recommended count
- family breakdown
- top blocked reasons
- `production_safety_summary`
- advisory `recommended_actions`
- risk-sorted experiment rows

Experiment rows must include:

- manifest identity
- candidate family
- manifest status
- run counts
- last run status
- health status
- revocation recommendation
- top blocked reasons
- production safety flags

Recommended actions are advisory strings only. Do not call `revoke_experiment`, `run_shadow_experiment`, or any persistence write method.

## Verification Commands

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p24_health_report.py -q
```

Run:

```bash
python3.11 -m pytest \
  tests/agent/research_v1/test_p24_entry_gate.py \
  tests/agent/research_v1/test_p24_experiment_registry.py \
  tests/agent/research_v1/test_p24_shadow_runner.py \
  tests/agent/research_v1/test_p24_run_persistence.py \
  tests/agent/research_v1/test_p24_health_report.py \
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
  tests/agent/research_v1/test_p24_run_persistence.py \
  tests/agent/research_v1/test_p24_health_report.py \
  -q
```

Run:

```bash
grep -R "import xgboost\|from xgboost\|import torch\|from torch\|import tensorflow\|from tensorflow\|stable_baselines\|import sklearn\|from sklearn" -n \
  agent/research_v1/p24_health_report.py \
  tests/agent/research_v1/test_p24_health_report.py || true
```

Expected: no output except possible string literals inside the no-model-library test.

## Handoff Report

Return exactly this structure:

```text
P24-E Shadow Experiment Health Report Handoff

Changed files:
- <path> — <created/modified> — <purpose>

Tests run:
- <command> → <result>

Acceptance checklist:
- health report contract exists: yes/no
- empty report works: yes/no
- healthy experiments reported: yes/no
- watch experiments reported: yes/no
- no-run experiments reported: yes/no
- revocation-recommended experiments reported: yes/no
- risk sorting works: yes/no
- family breakdown computed: yes/no
- top blocked reasons aggregated: yes/no
- production safety summary computed: yes/no
- recommended actions advisory only: yes/no
- JSON serialization works: yes/no
- no model libraries imported: yes/no
- P20-P24 regression green: yes/no

Known issues:
- <issue or None>
```
