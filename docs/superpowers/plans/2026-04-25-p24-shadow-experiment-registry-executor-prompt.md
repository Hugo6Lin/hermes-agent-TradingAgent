# Executor Prompt: P24-B Shadow Experiment Registry

You are implementing P24-B for Hermes.

Read these first:

1. `docs/superpowers/specs/2026-04-25-hermes-p24-shadow-experiment-registry-spec.md`
2. `docs/superpowers/plans/2026-04-25-p24-shadow-experiment-registry.md`
3. `docs/superpowers/specs/2026-04-25-hermes-p24-entry-gate-evaluator-spec.md`
4. `agent/research_v1/p24_entry_gate.py`
5. `tests/agent/research_v1/test_p24_entry_gate.py`

## Mission

Implement the P24-B Shadow Experiment Registry.

The registry converts passing P24-A `ModelAdmissionGateReport` objects into immutable `ShadowExperimentManifest` records. This is an audit and safety layer only.

## Hard Constraints

Do not:

- train any model
- import `xgboost`, `torch`, `tensorflow`, `sklearn`, `stable_baselines`, or RL libraries
- create model prediction code
- write canonical `FactorSnapshot`
- modify production configs
- affect thesis classification
- affect trade plans
- affect live trading
- add portfolio optimizer behavior

Use Python 3.11 and stdlib only.

## Files to Create

- `agent/research_v1/p24_experiment_registry.py`
- `tests/agent/research_v1/test_p24_experiment_registry.py`

## Required Contracts

Create:

- `ShadowExperimentRegistrationError`
- `ShadowExperimentRequest`
- `ShadowExperimentManifest`
- `ShadowExperimentRegistry`

`ShadowExperimentRegistry` must support:

- `register_shadow_experiment(request, gate_report)`
- `get_experiment(experiment_id)`
- `list_experiments(status=None, candidate_family=None)`
- `list_active_experiments(candidate_family=None)`
- `get_experiment_history(experiment_id)`
- `revoke_experiment(experiment_id, reason)`
- `archive_experiment(experiment_id, reason)`

## Required Safety Behavior

Registration must reject:

- failed P24 gate reports
- gate reports with blocking reasons
- gate reports whose `production_write_blocked` is not true
- request/gate candidate name mismatch
- request/gate candidate family mismatch
- request/gate candidate namespace mismatch
- missing `source_gate_report_id`
- output namespace outside candidate namespace
- canonical factor snapshot writes
- production config writes
- live trading effects
- non-net return basis
- missing required forbidden outputs
- missing baseline plan
- missing OOS plan
- missing point-in-time and purged-embargo leakage checks
- observation plans with fewer than four shadow windows

## Required Manifest Flags

Every registered manifest must have:

```python
promotion_blocked = True
production_write_blocked = True
canonical_snapshot_write_blocked = True
status = "registered"
schema_version = "p24_manifest.0"
```

## Testing Requirements

Use TDD from the implementation plan.

Minimum tests:

1. passing gate report registers a manifest
2. failed gate report cannot register
3. namespace mismatch is blocked
4. canonical snapshot writes are blocked
5. production config writes are blocked
6. gross-return-primary output contract is blocked
7. missing baseline plan is blocked
8. missing OOS leakage checks are blocked
9. observation plan requires at least four windows
10. required forbidden outputs are enforced
11. registered manifests are queryable by family
12. revocation preserves audit record and removes experiment from active list
13. manifest history is preserved after revocation or archival
14. archival preserves audit record
15. registry module does not import model libraries

## Verification Commands

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p24_experiment_registry.py -q
```

Run:

```bash
python3.11 -m pytest \
  tests/agent/research_v1/test_p24_entry_gate.py \
  tests/agent/research_v1/test_p24_experiment_registry.py \
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
  -q
```

Run:

```bash
grep -R "import xgboost\|from xgboost\|import torch\|from torch\|import tensorflow\|from tensorflow\|stable_baselines\|import sklearn\|from sklearn" -n \
  agent/research_v1/p24_experiment_registry.py \
  tests/agent/research_v1/test_p24_experiment_registry.py || true
```

Expected: no output.

## Handoff Report

Return exactly this structure:

```text
P24-B Shadow Experiment Registry Handoff

Changed files:
- <path> — <created/modified> — <purpose>

Tests run:
- <command> → <result>

Acceptance checklist:
- manifest contract exists: yes/no
- registration requires passing P24 gate: yes/no
- failed candidates blocked: yes/no
- source gate identity preserved: yes/no
- canonical snapshot writes blocked: yes/no
- production config writes blocked: yes/no
- live trading effects blocked: yes/no
- gross-return-primary blocked: yes/no
- baseline and OOS plans mandatory: yes/no
- observation plan requires four windows: yes/no
- query by candidate family works: yes/no
- revocation preserves audit record: yes/no
- manifest history preserved: yes/no
- no model libraries imported: yes/no
- P20-P24 regression green: yes/no

Known issues:
- <issue or None>
```
