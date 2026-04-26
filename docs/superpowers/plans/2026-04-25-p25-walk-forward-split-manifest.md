# P25-C Walk-Forward Split Manifest Builder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build purged walk-forward train/validation split manifests from P25-B training dataset rows without training models.

**Architecture:** Add `p25_split_manifest_builder.py` with request/window/manifest dataclasses, request validation, dict/dataclass row normalization, time-ordered window generation, exclusion accounting, and JSON-serializable output. Tests use synthetic rows and avoid model libraries.

**Tech Stack:** Python 3.11, dataclasses, stdlib only, pytest.

---

## Source Specs

- `docs/superpowers/specs/2026-04-25-hermes-p25-walk-forward-split-manifest-spec.md`
- `docs/superpowers/specs/2026-04-25-hermes-p25-training-dataset-builder-spec.md`

## Files

### Create

- `agent/research_v1/p25_split_manifest_builder.py`
- `tests/agent/research_v1/test_p25_split_manifest_builder.py`

### Modify

- None expected.

---

## Task 1: Contracts and Request Validation

**Files:**
- Create: `agent/research_v1/p25_split_manifest_builder.py`
- Test: `tests/agent/research_v1/test_p25_split_manifest_builder.py`

- [ ] **Step 1: Write failing request tests**

Create `tests/agent/research_v1/test_p25_split_manifest_builder.py`:

```python
import json

import pytest

from agent.research_v1.p25_split_manifest_builder import (
    SplitManifestBuilderError,
    SplitManifestRequest,
    build_split_manifest,
)


def _request(**overrides):
    values = dict(
        split_id="split_xgb_meta_21d",
        dataset_id="dataset_xgb_meta_21d",
        candidate_namespace="shadow_meta_model.xgb_v1",
        train_window_days=30,
        validation_window_days=10,
        step_days=10,
        purged_gap_days=2,
        embargo_days=2,
        min_train_rows=2,
        min_validation_rows=1,
        walk_forward_enabled=True,
        notes="test split",
    )
    values.update(overrides)
    return SplitManifestRequest(**values)


def _row(snapshot_id, trading_day):
    return {
        "snapshot_id": snapshot_id,
        "trading_day": trading_day,
        "features": {"company_quality_score": 80},
        "target_name": "net_return_pct",
        "target_value": 0.05,
        "horizon_days": 21,
    }


def test_request_rejects_non_shadow_namespace():
    with pytest.raises(SplitManifestBuilderError, match="candidate_namespace must start with shadow_meta_model."):
        _request(candidate_namespace="candidate_event.bad")


def test_request_rejects_walk_forward_disabled():
    with pytest.raises(SplitManifestBuilderError, match="walk_forward_enabled must be true"):
        _request(walk_forward_enabled=False)


def test_request_rejects_zero_or_negative_windows():
    with pytest.raises(SplitManifestBuilderError, match="train_window_days must be positive"):
        _request(train_window_days=0)
    with pytest.raises(SplitManifestBuilderError, match="validation_window_days must be positive"):
        _request(validation_window_days=0)
    with pytest.raises(SplitManifestBuilderError, match="step_days must be positive"):
        _request(step_days=0)
```

- [ ] **Step 2: Run failing request tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p25_split_manifest_builder.py -q
```

Expected: FAIL because `p25_split_manifest_builder.py` does not exist.

- [ ] **Step 3: Implement contracts**

Create `agent/research_v1/p25_split_manifest_builder.py`:

```python
"""P25-C purged walk-forward split manifest builder.

This module creates train/validation split manifests. It does not train models.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone


EXCLUSION_REASONS = (
    "insufficient_train_rows",
    "insufficient_validation_rows",
    "train_validation_overlap",
    "validation_not_after_train",
    "purge_gap_violation",
)


class SplitManifestBuilderError(ValueError):
    """Raised when split manifest request or rows are unsafe."""


@dataclass(frozen=True)
class SplitManifestRequest:
    split_id: str
    dataset_id: str
    candidate_namespace: str
    train_window_days: int
    validation_window_days: int
    step_days: int
    purged_gap_days: int
    embargo_days: int
    min_train_rows: int
    min_validation_rows: int
    walk_forward_enabled: bool
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.candidate_namespace.startswith("shadow_meta_model."):
            raise SplitManifestBuilderError("candidate_namespace must start with shadow_meta_model.")
        if self.walk_forward_enabled is not True:
            raise SplitManifestBuilderError("walk_forward_enabled must be true")
        if self.train_window_days <= 0:
            raise SplitManifestBuilderError("train_window_days must be positive")
        if self.validation_window_days <= 0:
            raise SplitManifestBuilderError("validation_window_days must be positive")
        if self.step_days <= 0:
            raise SplitManifestBuilderError("step_days must be positive")
        if self.purged_gap_days < 1:
            raise SplitManifestBuilderError("purged_gap_days must be >= 1")
        if self.embargo_days < 1:
            raise SplitManifestBuilderError("embargo_days must be >= 1")
        if self.min_train_rows < 1:
            raise SplitManifestBuilderError("min_train_rows must be >= 1")
        if self.min_validation_rows < 1:
            raise SplitManifestBuilderError("min_validation_rows must be >= 1")


@dataclass(frozen=True)
class SplitWindow:
    window_id: str
    train_start: str
    train_end: str
    validation_start: str
    validation_end: str
    purged_gap_days: int
    embargo_days: int
    train_snapshot_ids: list[str]
    validation_snapshot_ids: list[str]
    train_row_count: int
    validation_row_count: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class SplitManifest:
    schema_version: str
    split_id: str
    dataset_id: str
    candidate_namespace: str
    walk_forward_enabled: bool
    train_window_days: int
    validation_window_days: int
    step_days: int
    purged_gap_days: int
    embargo_days: int
    min_train_rows: int
    min_validation_rows: int
    total_rows: int
    total_windows: int
    included_windows: int
    excluded_windows: int
    exclusion_reasons: dict[str, int]
    windows: list[SplitWindow]
    created_at: str
    notes: str

    def to_dict(self) -> dict:
        data = asdict(self)
        data["windows"] = [window.to_dict() for window in self.windows]
        return data


@dataclass(frozen=True)
class SplitBuildResult:
    manifest: SplitManifest


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
```

- [ ] **Step 4: Run request tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p25_split_manifest_builder.py -q
```

Expected: PASS for request tests once `build_split_manifest` import exists. Continue to Task 2 if import still fails.

---

## Task 2: Window Generation

**Files:**
- Modify: `agent/research_v1/p25_split_manifest_builder.py`
- Modify: `tests/agent/research_v1/test_p25_split_manifest_builder.py`

- [ ] **Step 1: Add split generation tests**

Append to `tests/agent/research_v1/test_p25_split_manifest_builder.py`:

```python
def _rows():
    return [
        _row("snap_01", "2026-01-01"),
        _row("snap_02", "2026-01-05"),
        _row("snap_03", "2026-01-10"),
        _row("snap_04", "2026-01-15"),
        _row("snap_05", "2026-01-20"),
        _row("snap_06", "2026-01-25"),
        _row("snap_07", "2026-02-01"),
        _row("snap_08", "2026-02-05"),
        _row("snap_09", "2026-02-10"),
    ]


def test_sorted_rows_produce_at_least_one_split_window():
    result = build_split_manifest(list(reversed(_rows())), _request())

    assert result.manifest.schema_version == "p25_split_manifest.0"
    assert result.manifest.included_windows >= 1
    assert result.manifest.windows[0].train_row_count >= 2
    assert result.manifest.windows[0].validation_row_count >= 1
    json.dumps(result.manifest.to_dict())


def test_train_dates_are_before_validation_dates_and_purge_gap_enforced():
    result = build_split_manifest(_rows(), _request(purged_gap_days=2))
    window = result.manifest.windows[0]

    assert window.train_end < window.validation_start
    assert window.purged_gap_days == 2


def test_embargo_fields_are_preserved():
    result = build_split_manifest(_rows(), _request(embargo_days=5))

    assert result.manifest.embargo_days == 5
    assert result.manifest.windows[0].embargo_days == 5


def test_train_validation_snapshot_ids_do_not_overlap():
    result = build_split_manifest(_rows(), _request())
    window = result.manifest.windows[0]

    assert set(window.train_snapshot_ids).isdisjoint(set(window.validation_snapshot_ids))
```

- [ ] **Step 2: Implement row helpers and builder**

Append to `agent/research_v1/p25_split_manifest_builder.py`:

```python
def _as_dict(value) -> dict:
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "to_dict"):
        return dict(value.to_dict())
    if hasattr(value, "__dict__"):
        return dict(value.__dict__)
    raise SplitManifestBuilderError("rows must be dict-like")


def _parse_day(value: str) -> date:
    return date.fromisoformat(str(value))


def _sorted_rows(rows: list) -> list[dict]:
    normalized = [_as_dict(row) for row in rows]
    for row in normalized:
        if not row.get("snapshot_id"):
            raise SplitManifestBuilderError("snapshot_id is required")
        if not row.get("trading_day"):
            raise SplitManifestBuilderError("trading_day is required")
    return sorted(normalized, key=lambda row: (str(row["trading_day"]), str(row["snapshot_id"])))


def build_split_manifest(rows: list, request: SplitManifestRequest) -> SplitBuildResult:
    sorted_rows = _sorted_rows(rows)
    exclusion_reasons = {reason: 0 for reason in EXCLUSION_REASONS}
    windows: list[SplitWindow] = []
    total_windows = 0

    if not sorted_rows:
        manifest = _manifest(request, 0, 0, 0, exclusion_reasons, [])
        return SplitBuildResult(manifest=manifest)

    first_day = _parse_day(sorted_rows[0]["trading_day"])
    last_day = _parse_day(sorted_rows[-1]["trading_day"])
    cursor = first_day
    window_index = 1

    while cursor + timedelta(days=request.train_window_days + request.purged_gap_days + request.validation_window_days) <= last_day + timedelta(days=1):
        total_windows += 1
        train_start = cursor
        train_end = train_start + timedelta(days=request.train_window_days - 1)
        validation_start = train_end + timedelta(days=request.purged_gap_days)
        validation_end = validation_start + timedelta(days=request.validation_window_days - 1)
        train_rows = [row for row in sorted_rows if train_start <= _parse_day(row["trading_day"]) <= train_end]
        validation_rows = [row for row in sorted_rows if validation_start <= _parse_day(row["trading_day"]) <= validation_end]
        reasons = _window_exclusions(train_rows, validation_rows, train_end, validation_start, request)
        if reasons:
            for reason in reasons:
                exclusion_reasons[reason] += 1
        else:
            windows.append(
                SplitWindow(
                    window_id=f"{request.split_id}_w{window_index:03d}",
                    train_start=train_start.isoformat(),
                    train_end=train_end.isoformat(),
                    validation_start=validation_start.isoformat(),
                    validation_end=validation_end.isoformat(),
                    purged_gap_days=request.purged_gap_days,
                    embargo_days=request.embargo_days,
                    train_snapshot_ids=[str(row["snapshot_id"]) for row in train_rows],
                    validation_snapshot_ids=[str(row["snapshot_id"]) for row in validation_rows],
                    train_row_count=len(train_rows),
                    validation_row_count=len(validation_rows),
                )
            )
            window_index += 1
        cursor = cursor + timedelta(days=request.step_days + request.embargo_days)

    manifest = _manifest(
        request=request,
        total_rows=len(sorted_rows),
        total_windows=total_windows,
        excluded_windows=sum(exclusion_reasons.values()),
        exclusion_reasons=exclusion_reasons,
        windows=windows,
    )
    return SplitBuildResult(manifest=manifest)
```

- [ ] **Step 3: Implement exclusion and manifest helpers**

Append to `agent/research_v1/p25_split_manifest_builder.py`:

```python
def _window_exclusions(
    train_rows: list[dict],
    validation_rows: list[dict],
    train_end: date,
    validation_start: date,
    request: SplitManifestRequest,
) -> list[str]:
    reasons: list[str] = []
    if len(train_rows) < request.min_train_rows:
        reasons.append("insufficient_train_rows")
    if len(validation_rows) < request.min_validation_rows:
        reasons.append("insufficient_validation_rows")
    train_ids = {row["snapshot_id"] for row in train_rows}
    validation_ids = {row["snapshot_id"] for row in validation_rows}
    if train_ids.intersection(validation_ids):
        reasons.append("train_validation_overlap")
    if validation_start <= train_end:
        reasons.append("validation_not_after_train")
    if (validation_start - train_end).days < request.purged_gap_days:
        reasons.append("purge_gap_violation")
    return reasons


def _manifest(
    request: SplitManifestRequest,
    total_rows: int,
    total_windows: int,
    excluded_windows: int,
    exclusion_reasons: dict[str, int],
    windows: list[SplitWindow],
) -> SplitManifest:
    return SplitManifest(
        schema_version="p25_split_manifest.0",
        split_id=request.split_id,
        dataset_id=request.dataset_id,
        candidate_namespace=request.candidate_namespace,
        walk_forward_enabled=True,
        train_window_days=request.train_window_days,
        validation_window_days=request.validation_window_days,
        step_days=request.step_days,
        purged_gap_days=request.purged_gap_days,
        embargo_days=request.embargo_days,
        min_train_rows=request.min_train_rows,
        min_validation_rows=request.min_validation_rows,
        total_rows=total_rows,
        total_windows=total_windows,
        included_windows=len(windows),
        excluded_windows=excluded_windows,
        exclusion_reasons=dict(exclusion_reasons),
        windows=windows,
        created_at=_utc_now(),
        notes=request.notes,
    )
```

- [ ] **Step 4: Run split generation tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p25_split_manifest_builder.py -q
```

Expected: PASS.

---

## Task 3: Excluded Windows and Dataclass-Like Rows

**Files:**
- Modify: `tests/agent/research_v1/test_p25_split_manifest_builder.py`

- [ ] **Step 1: Add exclusion/dataclass tests**

Append to `tests/agent/research_v1/test_p25_split_manifest_builder.py`:

```python
from dataclasses import dataclass


def test_insufficient_train_rows_exclude_window():
    result = build_split_manifest(_rows(), _request(min_train_rows=99))

    assert result.manifest.included_windows == 0
    assert result.manifest.exclusion_reasons["insufficient_train_rows"] >= 1


def test_insufficient_validation_rows_exclude_window():
    result = build_split_manifest(_rows(), _request(min_validation_rows=99))

    assert result.manifest.included_windows == 0
    assert result.manifest.exclusion_reasons["insufficient_validation_rows"] >= 1


@dataclass
class RowObject:
    snapshot_id: str
    trading_day: str
    features: dict
    target_name: str
    target_value: float
    horizon_days: int


def test_rows_can_be_dataclass_like():
    rows = [
        RowObject("snap_01", "2026-01-01", {}, "net_return_pct", 0.01, 21),
        RowObject("snap_02", "2026-01-05", {}, "net_return_pct", 0.02, 21),
        RowObject("snap_03", "2026-01-20", {}, "net_return_pct", 0.03, 21),
    ]

    result = build_split_manifest(rows, _request(train_window_days=10, validation_window_days=5, step_days=5))

    assert result.manifest.total_rows == 3
```

- [ ] **Step 2: Run exclusion/dataclass tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p25_split_manifest_builder.py -q
```

Expected: PASS.

---

## Task 4: Serialization, No Model Libraries, and Regression

**Files:**
- Modify: `tests/agent/research_v1/test_p25_split_manifest_builder.py`

- [ ] **Step 1: Add final safety tests**

Append to `tests/agent/research_v1/test_p25_split_manifest_builder.py`:

```python
def test_manifest_is_json_serializable():
    result = build_split_manifest(_rows(), _request())

    json.dumps(result.manifest.to_dict())


def test_split_manifest_builder_does_not_import_model_libraries():
    import agent.research_v1.p25_split_manifest_builder as builder_module

    module_names = set(builder_module.__dict__)
    forbidden_names = {"xgboost", "torch", "tensorflow", "sklearn", "stable_baselines3"}

    assert module_names.isdisjoint(forbidden_names)
```

- [ ] **Step 2: Run P25-C tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p25_split_manifest_builder.py -q
```

Expected: all P25-C tests PASS.

- [ ] **Step 3: Run P25 tests**

Run:

```bash
python3.11 -m pytest \
  tests/agent/research_v1/test_p25_xgboost_shadow_adapter.py \
  tests/agent/research_v1/test_p25_training_dataset_builder.py \
  tests/agent/research_v1/test_p25_split_manifest_builder.py \
  -q
```

Expected: all P25 tests PASS.

- [ ] **Step 4: Run P20-P25 regression bundle**

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

Expected: all selected tests PASS.

- [ ] **Step 5: Scan for forbidden model imports**

Run:

```bash
grep -R "import xgboost\|from xgboost\|import torch\|from torch\|import tensorflow\|from tensorflow\|stable_baselines\|import sklearn\|from sklearn" -n \
  agent/research_v1/p25_split_manifest_builder.py \
  tests/agent/research_v1/test_p25_split_manifest_builder.py || true
```

Expected: no output except possible string literals inside the no-model-library test.

---

## Final Handoff Format

Return:

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
