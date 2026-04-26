# P25-B Offline Training Dataset Builder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build point-in-time offline training dataset rows for future XGBoost-style meta-model work without training models or reading raw prices.

**Architecture:** Add `p25_training_dataset_builder.py` with request/row/manifest/result dataclasses, validation helpers, snapshot/return normalization, snapshot-id join logic, exclusion accounting, and JSON-serializable output. Tests use simple dictionaries to keep the builder independent from persistence backends.

**Tech Stack:** Python 3.11, dataclasses, stdlib only, pytest.

---

## Source Specs

- `docs/superpowers/specs/2026-04-25-hermes-p25-training-dataset-builder-spec.md`
- `docs/superpowers/specs/2026-04-25-hermes-p25-xgboost-shadow-dry-adapter-spec.md`
- `docs/superpowers/specs/2026-04-25-hermes-p20-p22-factor-calibration-roadmap-spec.md`

## Files

### Create

- `agent/research_v1/p25_training_dataset_builder.py`
- `tests/agent/research_v1/test_p25_training_dataset_builder.py`

### Modify

- None expected.

---

## Task 1: Contracts, Request Validation, and Happy Path

**Files:**
- Create: `agent/research_v1/p25_training_dataset_builder.py`
- Test: `tests/agent/research_v1/test_p25_training_dataset_builder.py`

- [ ] **Step 1: Write failing tests**

Create `tests/agent/research_v1/test_p25_training_dataset_builder.py`:

```python
import json

import pytest

from agent.research_v1.p25_training_dataset_builder import (
    TrainingDatasetBuilderError,
    TrainingDatasetRequest,
    build_training_dataset,
)


FEATURE_NAMES = [
    "company_quality_score",
    "valuation_attractiveness_score",
    "timing_market_fit_score",
    "llm_adjustment_total",
    "coverage_confidence_score",
]


def _request(**overrides):
    values = dict(
        dataset_id="dataset_xgb_meta_21d",
        candidate_namespace="shadow_meta_model.xgb_v1",
        horizon_days=21,
        feature_names=list(FEATURE_NAMES),
        target_name="net_return_pct",
        min_rows=1,
        require_point_in_time=True,
        require_universe_membership=True,
        max_source_audit_gap_rate=0.20,
        notes="test dataset",
    )
    values.update(overrides)
    return TrainingDatasetRequest(**values)


def _snapshot(**overrides):
    values = dict(
        snapshot_id="snap_1",
        ticker="MSFT",
        trading_day="2026-01-05",
        company_quality_score=80,
        valuation_attractiveness_score=60,
        timing_market_fit_score=50,
        llm_adjustment_total=10,
        coverage_confidence_score=0.9,
        data_as_of_date="2026-01-04",
        universe_membership_snapshot_id="sp500_2026_01_05",
        schema_version="p20_factor_snapshot.0",
        lookahead_violation=False,
        source_audit_gap=0.0,
    )
    values.update(overrides)
    return values


def _forward_return(**overrides):
    values = dict(
        snapshot_id="snap_1",
        horizon_days=21,
        net_return_pct=0.05,
        gross_return_pct=0.055,
        transaction_cost_pct=0.005,
        return_basis="net",
        computed_at="2026-02-01T00:00:00Z",
        schema_version="p20_forward_return.0",
    )
    values.update(overrides)
    return values


def test_valid_snapshot_and_net_forward_return_produces_one_row():
    result = build_training_dataset([_snapshot()], [_forward_return()], _request())

    assert result.manifest.schema_version == "p25_training_dataset.0"
    assert result.manifest.included_rows == 1
    assert result.manifest.target_name == "net_return_pct"
    assert result.manifest.return_basis == "net"
    assert result.manifest.point_in_time_confirmed is True
    assert result.rows[0].snapshot_id == "snap_1"
    assert result.rows[0].target_value == 0.05
    assert result.rows[0].features["company_quality_score"] == 80
    json.dumps(result.manifest.to_dict())
    json.dumps([row.to_dict() for row in result.rows])


def test_request_rejects_non_shadow_namespace():
    with pytest.raises(TrainingDatasetBuilderError, match="candidate_namespace must start with shadow_meta_model."):
        _request(candidate_namespace="candidate_event.bad")


def test_request_rejects_non_net_target():
    with pytest.raises(TrainingDatasetBuilderError, match="target_name must be net_return_pct"):
        _request(target_name="gross_return_pct")
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p25_training_dataset_builder.py -q
```

Expected: FAIL because `p25_training_dataset_builder.py` does not exist.

- [ ] **Step 3: Implement contracts**

Create `agent/research_v1/p25_training_dataset_builder.py`:

```python
"""P25-B point-in-time training dataset builder.

This module constructs offline training rows from factor snapshots and
forward-return observations. It does not train models or read raw prices.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone


EXCLUSION_KEYS = (
    "missing_forward_return",
    "non_net_return",
    "lookahead_violation",
    "source_audit_gap",
    "universe_mismatch",
    "missing_required_feature",
    "wrong_horizon",
)


class TrainingDatasetBuilderError(ValueError):
    """Raised when P25-B dataset request or inputs are unsafe."""


@dataclass(frozen=True)
class TrainingDatasetRequest:
    dataset_id: str
    candidate_namespace: str
    horizon_days: int
    feature_names: list[str]
    target_name: str
    min_rows: int
    require_point_in_time: bool
    require_universe_membership: bool
    max_source_audit_gap_rate: float
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.candidate_namespace.startswith("shadow_meta_model."):
            raise TrainingDatasetBuilderError("candidate_namespace must start with shadow_meta_model.")
        if self.target_name != "net_return_pct":
            raise TrainingDatasetBuilderError("target_name must be net_return_pct")
        if self.horizon_days <= 0:
            raise TrainingDatasetBuilderError("horizon_days must be positive")
        if not self.feature_names:
            raise TrainingDatasetBuilderError("feature_names is required")
        if self.min_rows < 1:
            raise TrainingDatasetBuilderError("min_rows must be >= 1")
        if self.require_point_in_time is not True:
            raise TrainingDatasetBuilderError("require_point_in_time must be true")
        if self.require_universe_membership is not True:
            raise TrainingDatasetBuilderError("require_universe_membership must be true")
        if self.max_source_audit_gap_rate > 0.20:
            raise TrainingDatasetBuilderError("max_source_audit_gap_rate must be <= 0.20")


@dataclass(frozen=True)
class TrainingDatasetRow:
    snapshot_id: str
    ticker: str
    trading_day: str
    features: dict
    target_name: str
    target_value: float
    horizon_days: int
    data_as_of_date: str
    universe_membership_snapshot_id: str
    source_snapshot_schema_version: str
    source_return_schema_version: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class TrainingDatasetManifest:
    schema_version: str
    dataset_id: str
    candidate_namespace: str
    horizon_days: int
    feature_names: list[str]
    target_name: str
    total_snapshots: int
    total_forward_returns: int
    included_rows: int
    excluded_counts: dict[str, int]
    point_in_time_confirmed: bool
    return_basis: str
    min_rows: int
    meets_min_rows: bool
    created_at: str
    notes: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class TrainingDatasetBuildResult:
    manifest: TrainingDatasetManifest
    rows: list[TrainingDatasetRow]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
```

- [ ] **Step 4: Implement builder skeleton**

Append to `agent/research_v1/p25_training_dataset_builder.py`:

```python
def build_training_dataset(
    factor_snapshots: list[dict],
    forward_returns: list[dict],
    request: TrainingDatasetRequest,
) -> TrainingDatasetBuildResult:
    excluded_counts = {key: 0 for key in EXCLUSION_KEYS}
    returns_by_snapshot = _index_forward_returns(forward_returns, request.horizon_days)
    rows: list[TrainingDatasetRow] = []

    for raw_snapshot in factor_snapshots:
        snapshot = _as_dict(raw_snapshot)
        row_exclusions = _snapshot_exclusions(snapshot, request)
        matching_return = returns_by_snapshot.get(snapshot.get("snapshot_id"))
        if matching_return is None:
            row_exclusions.append("missing_forward_return")
        else:
            row_exclusions.extend(_return_exclusions(matching_return, request))
        if row_exclusions:
            for reason in set(row_exclusions):
                excluded_counts[reason] += 1
            continue
        rows.append(_build_row(snapshot, matching_return, request))

    manifest = TrainingDatasetManifest(
        schema_version="p25_training_dataset.0",
        dataset_id=request.dataset_id,
        candidate_namespace=request.candidate_namespace,
        horizon_days=request.horizon_days,
        feature_names=list(request.feature_names),
        target_name=request.target_name,
        total_snapshots=len(factor_snapshots),
        total_forward_returns=len(forward_returns),
        included_rows=len(rows),
        excluded_counts=excluded_counts,
        point_in_time_confirmed=True,
        return_basis="net",
        min_rows=request.min_rows,
        meets_min_rows=len(rows) >= request.min_rows,
        created_at=_utc_now(),
        notes=request.notes,
    )
    return TrainingDatasetBuildResult(manifest=manifest, rows=rows)
```

- [ ] **Step 5: Implement helpers**

Append to `agent/research_v1/p25_training_dataset_builder.py`:

```python
def _as_dict(value) -> dict:
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "to_dict"):
        return dict(value.to_dict())
    if hasattr(value, "__dict__"):
        return dict(value.__dict__)
    raise TrainingDatasetBuilderError("input rows must be dict-like")


def _index_forward_returns(forward_returns: list[dict], horizon_days: int) -> dict[str, dict]:
    indexed: dict[str, dict] = {}
    for raw_return in forward_returns:
        observation = _as_dict(raw_return)
        snapshot_id = observation.get("snapshot_id")
        if not snapshot_id:
            continue
        current = indexed.get(snapshot_id)
        if current is None:
            indexed[snapshot_id] = observation
            continue
        indexed[snapshot_id] = _choose_return(current, observation, horizon_days)
    return indexed


def _choose_return(left: dict, right: dict, horizon_days: int) -> dict:
    left_is_net = left.get("return_basis") == "net" and left.get("horizon_days") == horizon_days
    right_is_net = right.get("return_basis") == "net" and right.get("horizon_days") == horizon_days
    if left_is_net and not right_is_net:
        return left
    if right_is_net and not left_is_net:
        return right
    return right if str(right.get("computed_at", "")) >= str(left.get("computed_at", "")) else left


def _snapshot_exclusions(snapshot: dict, request: TrainingDatasetRequest) -> list[str]:
    exclusions: list[str] = []
    if snapshot.get("lookahead_violation") is True:
        exclusions.append("lookahead_violation")
    if float(snapshot.get("source_audit_gap", 0.0) or 0.0) > request.max_source_audit_gap_rate:
        exclusions.append("source_audit_gap")
    if request.require_universe_membership and not snapshot.get("universe_membership_snapshot_id"):
        exclusions.append("universe_mismatch")
    required_snapshot_fields = [
        "snapshot_id",
        "ticker",
        "trading_day",
        "data_as_of_date",
        "universe_membership_snapshot_id",
        *request.feature_names,
    ]
    if any(field not in snapshot or snapshot.get(field) in (None, "") for field in required_snapshot_fields):
        exclusions.append("missing_required_feature")
    return exclusions


def _return_exclusions(observation: dict, request: TrainingDatasetRequest) -> list[str]:
    exclusions: list[str] = []
    if observation.get("horizon_days") != request.horizon_days:
        exclusions.append("wrong_horizon")
    if observation.get("return_basis") != "net":
        exclusions.append("non_net_return")
    if observation.get("net_return_pct") is None:
        exclusions.append("non_net_return")
    return exclusions


def _build_row(snapshot: dict, observation: dict, request: TrainingDatasetRequest) -> TrainingDatasetRow:
    return TrainingDatasetRow(
        snapshot_id=str(snapshot["snapshot_id"]),
        ticker=str(snapshot["ticker"]),
        trading_day=str(snapshot["trading_day"]),
        features={feature: snapshot[feature] for feature in request.feature_names},
        target_name=request.target_name,
        target_value=float(observation["net_return_pct"]),
        horizon_days=int(observation["horizon_days"]),
        data_as_of_date=str(snapshot["data_as_of_date"]),
        universe_membership_snapshot_id=str(snapshot["universe_membership_snapshot_id"]),
        source_snapshot_schema_version=str(snapshot.get("schema_version", "")),
        source_return_schema_version=str(observation.get("schema_version", "")),
    )
```

- [ ] **Step 6: Run initial tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p25_training_dataset_builder.py -q
```

Expected: initial tests PASS.

---

## Task 2: Exclusion Rules

**Files:**
- Modify: `tests/agent/research_v1/test_p25_training_dataset_builder.py`

- [ ] **Step 1: Add exclusion tests**

Append to `tests/agent/research_v1/test_p25_training_dataset_builder.py`:

```python
def test_join_uses_snapshot_id_not_ticker_date():
    snapshot = _snapshot(snapshot_id="snap_left", ticker="MSFT", trading_day="2026-01-05")
    wrong_return = _forward_return(snapshot_id="snap_right")

    result = build_training_dataset([snapshot], [wrong_return], _request())

    assert result.rows == []
    assert result.manifest.excluded_counts["missing_forward_return"] == 1


def test_missing_forward_return_excludes_row():
    result = build_training_dataset([_snapshot()], [], _request())

    assert result.manifest.included_rows == 0
    assert result.manifest.excluded_counts["missing_forward_return"] == 1


def test_non_net_return_excludes_row():
    result = build_training_dataset([_snapshot()], [_forward_return(return_basis="gross")], _request())

    assert result.manifest.included_rows == 0
    assert result.manifest.excluded_counts["non_net_return"] == 1


def test_wrong_horizon_excludes_row():
    result = build_training_dataset([_snapshot()], [_forward_return(horizon_days=63)], _request(horizon_days=21))

    assert result.manifest.included_rows == 0
    assert result.manifest.excluded_counts["wrong_horizon"] == 1


def test_lookahead_violation_excludes_row():
    result = build_training_dataset([_snapshot(lookahead_violation=True)], [_forward_return()], _request())

    assert result.manifest.included_rows == 0
    assert result.manifest.excluded_counts["lookahead_violation"] == 1


def test_source_audit_gap_excludes_row():
    result = build_training_dataset([_snapshot(source_audit_gap=0.50)], [_forward_return()], _request())

    assert result.manifest.included_rows == 0
    assert result.manifest.excluded_counts["source_audit_gap"] == 1


def test_missing_universe_membership_excludes_row():
    result = build_training_dataset(
        [_snapshot(universe_membership_snapshot_id="")],
        [_forward_return()],
        _request(),
    )

    assert result.manifest.included_rows == 0
    assert result.manifest.excluded_counts["universe_mismatch"] == 1


def test_missing_requested_feature_excludes_row():
    snapshot = _snapshot()
    del snapshot["company_quality_score"]

    result = build_training_dataset([snapshot], [_forward_return()], _request())

    assert result.manifest.included_rows == 0
    assert result.manifest.excluded_counts["missing_required_feature"] == 1
```

- [ ] **Step 2: Run exclusion tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p25_training_dataset_builder.py -q
```

Expected: PASS.

---

## Task 3: Duplicate Returns, Min Rows, and Serialization

**Files:**
- Modify: `tests/agent/research_v1/test_p25_training_dataset_builder.py`

- [ ] **Step 1: Add duplicate/min-row tests**

Append to `tests/agent/research_v1/test_p25_training_dataset_builder.py`:

```python
def test_duplicate_forward_returns_choose_latest_net_observation():
    older = _forward_return(net_return_pct=0.01, computed_at="2026-01-20T00:00:00Z")
    newer = _forward_return(net_return_pct=0.07, computed_at="2026-01-21T00:00:00Z")

    result = build_training_dataset([_snapshot()], [older, newer], _request())

    assert result.manifest.included_rows == 1
    assert result.rows[0].target_value == 0.07
    assert result.manifest.total_forward_returns == 2


def test_manifest_meets_min_rows_reflects_row_count():
    result = build_training_dataset([_snapshot()], [_forward_return()], _request(min_rows=2))

    assert result.manifest.included_rows == 1
    assert result.manifest.meets_min_rows is False


def test_manifest_excluded_counts_include_all_keys():
    result = build_training_dataset([_snapshot()], [_forward_return()], _request())

    assert set(result.manifest.excluded_counts) == {
        "missing_forward_return",
        "non_net_return",
        "lookahead_violation",
        "source_audit_gap",
        "universe_mismatch",
        "missing_required_feature",
        "wrong_horizon",
    }


def test_output_is_json_serializable():
    result = build_training_dataset([_snapshot()], [_forward_return()], _request())

    json.dumps(result.manifest.to_dict())
    json.dumps([row.to_dict() for row in result.rows])
```

- [ ] **Step 2: Run dataset tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p25_training_dataset_builder.py -q
```

Expected: PASS.

---

## Task 4: No Model Libraries and Regression

**Files:**
- Modify: `tests/agent/research_v1/test_p25_training_dataset_builder.py`

- [ ] **Step 1: Add no-model-library test**

Append to `tests/agent/research_v1/test_p25_training_dataset_builder.py`:

```python
def test_training_dataset_builder_does_not_import_model_libraries():
    import agent.research_v1.p25_training_dataset_builder as builder_module

    module_names = set(builder_module.__dict__)
    forbidden_names = {"xgboost", "torch", "tensorflow", "sklearn", "stable_baselines3"}

    assert module_names.isdisjoint(forbidden_names)
```

- [ ] **Step 2: Run P25-B tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p25_training_dataset_builder.py -q
```

Expected: all P25-B tests PASS.

- [ ] **Step 3: Run P25 tests**

Run:

```bash
python3.11 -m pytest \
  tests/agent/research_v1/test_p25_xgboost_shadow_adapter.py \
  tests/agent/research_v1/test_p25_training_dataset_builder.py \
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
  -q
```

Expected: all selected tests PASS.

- [ ] **Step 5: Scan for forbidden model imports**

Run:

```bash
grep -R "import xgboost\|from xgboost\|import torch\|from torch\|import tensorflow\|from tensorflow\|stable_baselines\|import sklearn\|from sklearn" -n \
  agent/research_v1/p25_training_dataset_builder.py \
  tests/agent/research_v1/test_p25_training_dataset_builder.py || true
```

Expected: no output except possible string literals inside the no-model-library test.

---

## Final Handoff Format

Return:

```text
P25-B Offline Training Dataset Builder Handoff

Changed files:
- <path> — <created/modified> — <purpose>

Tests run:
- <command> → <result>

Acceptance checklist:
- request contract exists: yes/no
- row contract exists: yes/no
- manifest contract exists: yes/no
- join by snapshot_id: yes/no
- net return required: yes/no
- wrong horizon excluded: yes/no
- lookahead excluded: yes/no
- source audit gap excluded: yes/no
- universe membership required: yes/no
- missing features excluded: yes/no
- duplicate returns resolved deterministically: yes/no
- excluded counts reported: yes/no
- output JSON-serializable: yes/no
- no raw prices read: yes/no
- no model libraries imported: yes/no
- no training performed: yes/no
- P20-P25 regression green: yes/no

Known issues:
- <issue or None>
```
