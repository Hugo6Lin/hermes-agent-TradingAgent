# Executor Prompt: P25-A XGBoost Meta-Model Shadow Dry Adapter

You are implementing P25-A for Hermes.

Read these first:

1. `docs/superpowers/specs/2026-04-25-hermes-p25-xgboost-shadow-dry-adapter-spec.md`
2. `docs/superpowers/plans/2026-04-25-p25-xgboost-shadow-dry-adapter.md`
3. `agent/research_v1/p24_entry_gate.py`
4. `agent/research_v1/p24_experiment_registry.py`
5. `agent/research_v1/p24_shadow_runner.py`
6. `agent/research_v1/p24_run_persistence.py`
7. `agent/research_v1/p24_health_report.py`

## Mission

Implement the first real P25 shadow candidate: an XGBoost-style meta-model dry adapter.

This is not real XGBoost training. It is a shadow-only adapter that validates feature contracts, computes deterministic stub scores, and runs through the existing P24 safety pipeline.

## Hard Constraints

Do not:

- import `xgboost`, `sklearn`, `torch`, `tensorflow`, `stable_baselines`, or any model-training library
- train any model
- load or save model objects
- compute fitted predictions
- write canonical `FactorSnapshot`
- modify production configs
- alter thesis classification
- alter trade plans
- promote shadow scores
- generate live trade signals

Use Python 3.11 and stdlib only.

## Files to Create

- `agent/research_v1/p25_xgboost_shadow_adapter.py`
- `tests/agent/research_v1/test_p25_xgboost_shadow_adapter.py`

## Required Contracts

Create:

- `XGBoostShadowAdapterConfigError`
- `XGBoostMetaFeatureContract`
- `XGBoostShadowAdapterConfig`
- `XGBoostDryRunAdapter`

The adapter must return P24-C `ShadowAdapterResult`.

## Required Behavior

Feature contract must:

- require point-in-time fields
- require `target_return_basis == "net"`
- require `point_in_time_required == True`
- forbid future-return and production fields

Adapter config must:

- require namespace under `shadow_meta_model.*`
- require all output names under namespace
- require `calibration_status == "shadow_dry_run"`

Adapter run must:

- exclude rows missing required fields
- exclude rows containing forbidden fields
- warn on missing optional fields
- compute deterministic stub scores
- clamp scores to `0..1`
- produce only:
  - `<namespace>.shadow_predictions`
  - `<namespace>.feature_audit`
  - `<namespace>.dry_run_metadata`

## Verification Commands

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p25_xgboost_shadow_adapter.py -q
```

Run:

```bash
python3.11 -m pytest \
  tests/agent/research_v1/test_p24_entry_gate.py \
  tests/agent/research_v1/test_p24_experiment_registry.py \
  tests/agent/research_v1/test_p24_shadow_runner.py \
  tests/agent/research_v1/test_p24_run_persistence.py \
  tests/agent/research_v1/test_p24_health_report.py \
  tests/agent/research_v1/test_p25_xgboost_shadow_adapter.py \
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
  tests/agent/research_v1/test_p25_xgboost_shadow_adapter.py \
  -q
```

Run:

```bash
grep -R "import xgboost\|from xgboost\|import torch\|from torch\|import tensorflow\|from tensorflow\|stable_baselines\|import sklearn\|from sklearn" -n \
  agent/research_v1/p25_xgboost_shadow_adapter.py \
  tests/agent/research_v1/test_p25_xgboost_shadow_adapter.py || true
```

Expected: no output except possible string literals inside the no-model-library test.

## Handoff Report

Return exactly this structure:

```text
P25-A XGBoost Meta-Model Shadow Dry Adapter Handoff

Changed files:
- <path> — <created/modified> — <purpose>

Tests run:
- <command> → <result>

Acceptance checklist:
- feature contract exists: yes/no
- adapter config exists: yes/no
- namespace validation works: yes/no
- point-in-time fields required: yes/no
- forbidden features blocked: yes/no
- missing required feature rows excluded: yes/no
- optional feature warnings emitted: yes/no
- stub scores deterministic and clamped: yes/no
- outputs stay under shadow_meta_model namespace: yes/no
- P24 runner executes adapter: yes/no
- P24 persistence stores run: yes/no
- P24 health report sees experiment: yes/no
- no model libraries imported: yes/no
- no production outputs written: yes/no
- P20-P25 regression green: yes/no

Known issues:
- <issue or None>
```
