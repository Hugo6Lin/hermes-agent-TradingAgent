# Executor Prompt: P25-C Walk-Forward Split Manifest Builder

You are implementing P25-C for Hermes.

Read these first:

1. `docs/superpowers/specs/2026-04-25-hermes-p25-walk-forward-split-manifest-spec.md`
2. `docs/superpowers/plans/2026-04-25-p25-walk-forward-split-manifest.md`
3. `agent/research_v1/p25_training_dataset_builder.py`
4. `tests/agent/research_v1/test_p25_training_dataset_builder.py`

## Mission

Implement a purged walk-forward train/validation split manifest builder.

This is not model training. It only creates JSON-serializable split manifests from P25-B dataset rows.

## Hard Constraints

Do not:

- import `xgboost`, `sklearn`, `torch`, `tensorflow`, `stable_baselines`, or model-training libraries
- train any model
- tune hyperparameters
- compute IC/ICIR/PnL
- read raw prices
- modify dataset rows
- write canonical `FactorSnapshot`
- write production configs
- promote any output

Use Python 3.11 and stdlib only.

## Files to Create

- `agent/research_v1/p25_split_manifest_builder.py`
- `tests/agent/research_v1/test_p25_split_manifest_builder.py`

## Required Contracts

Create:

- `SplitManifestBuilderError`
- `SplitManifestRequest`
- `SplitWindow`
- `SplitManifest`
- `SplitBuildResult`
- `build_split_manifest(rows, request)`

## Required Behavior

The builder must:

- reject non-shadow namespaces
- require `walk_forward_enabled == True`
- reject zero or negative windows
- reject `purged_gap_days < 1`
- reject `embargo_days < 1`
- sort rows by `trading_day`, then `snapshot_id`
- create train windows before validation windows
- enforce purge gap
- record embargo days
- ensure train/validation snapshot IDs do not overlap
- exclude insufficient train windows
- exclude insufficient validation windows
- report exclusion reasons
- support dict-like and dataclass-like rows
- return JSON-serializable manifests

## Verification Commands

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p25_split_manifest_builder.py -q
```

Run:

```bash
python3.11 -m pytest \
  tests/agent/research_v1/test_p25_xgboost_shadow_adapter.py \
  tests/agent/research_v1/test_p25_training_dataset_builder.py \
  tests/agent/research_v1/test_p25_split_manifest_builder.py \
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
  tests/agent/research_v1/test_p25_training_dataset_builder.py \
  tests/agent/research_v1/test_p25_split_manifest_builder.py \
  -q
```

Run:

```bash
grep -R "import xgboost\|from xgboost\|import torch\|from torch\|import tensorflow\|from tensorflow\|stable_baselines\|import sklearn\|from sklearn" -n \
  agent/research_v1/p25_split_manifest_builder.py \
  tests/agent/research_v1/test_p25_split_manifest_builder.py || true
```

Expected: no output except possible string literals inside the no-model-library test.

## Handoff Report

Return exactly this structure:

```text
P25-C Walk-Forward Split Manifest Builder Handoff

Changed files:
- <path> — <created/modified> — <purpose>

Tests run:
- <command> → <result>

Acceptance checklist:
- split request contract exists: yes/no
- split window contract exists: yes/no
- split manifest contract exists: yes/no
- walk-forward only: yes/no
- train dates precede validation dates: yes/no
- purge gap enforced: yes/no
- embargo days recorded: yes/no
- snapshot IDs do not overlap: yes/no
- insufficient windows excluded: yes/no
- exclusion reasons reported: yes/no
- dataclass-like rows supported: yes/no
- manifest JSON-serializable: yes/no
- no model libraries imported: yes/no
- no training performed: yes/no
- P20-P25 regression green: yes/no

Known issues:
- <issue or None>
```
