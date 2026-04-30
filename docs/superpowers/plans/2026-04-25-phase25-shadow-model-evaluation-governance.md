# Phase 25 Shadow Model Evaluation and Governance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement consolidated P25-E/F: evaluate P25-D shadow model predictions against baselines and produce advisory promotion-readiness decisions.

**Architecture:** Add one focused module, `agent/research_v1/phase25_model_governance.py`, with request/result contracts, metric helpers, safety gates, and readiness decisions. Add one acceptance test file, `tests/agent/research_v1/test_phase25_model_governance.py`, using in-memory P25-D-like fixtures.

**Tech Stack:** Python 3.11 standard library, dataclasses, pytest. No model libraries and no production persistence.

---

## File Map

- Create: `agent/research_v1/phase25_model_governance.py`
  - Owns Phase 25 contracts.
  - Owns rank IC, directional hit rate, spread return, aggregation, and readiness gates.
- Create: `tests/agent/research_v1/test_phase25_model_governance.py`
  - Owns Phase 25 acceptance tests.
- Do not modify P25-D training behavior.
- Do not modify production configs or persistence.

---

## Required Implementation Shape

Implement these public objects:

```python
Phase25GovernanceError
Phase25EvaluationRequest
WindowEvaluationResult
ShadowModelEvaluationReport
PromotionReadinessDecision
Phase25GovernanceResult
evaluate_shadow_model_governance(training_result, baseline_predictions, request)
```

Use `to_dict()` on all result contracts.

---

### Task 1: Contract and Smoke Tests

- [ ] **Step 1: Create test file with fixtures**

Create `tests/agent/research_v1/test_phase25_model_governance.py`:

```python
"""Phase 25 shadow model evaluation and governance tests."""

import json
from dataclasses import dataclass

import pytest

from agent.research_v1.phase25_model_governance import (
    Phase25EvaluationRequest,
    Phase25GovernanceError,
    evaluate_shadow_model_governance,
)


@dataclass
class TrainingManifest:
    training_run_id: str = "train_run_001"
    experiment_id: str = "exp_xgb_v1"
    candidate_namespace: str = "shadow_meta_model.xgb_v1"
    model_family: str = "linear_baseline"
    target_name: str = "net_return_pct"
    completed_windows: int = 4
    blocked_windows: int = 0
    failed_windows: int = 0
    safety_flags: dict = None
    schema_version: str = "p25_shadow_training.0"

    def __post_init__(self):
        if self.safety_flags is None:
            self.safety_flags = {
                "production_write_blocked": True,
                "canonical_snapshot_write_blocked": True,
                "live_trading_blocked": True,
            }


@dataclass
class TrainingArtifact:
    window_id: str
    predictions: list
    training_status: str = "completed"


@dataclass
class TrainingResult:
    manifest: TrainingManifest
    window_artifacts: list


def _prediction(snapshot_id, value, target, trading_day="2026-01-01"):
    return {
        "snapshot_id": snapshot_id,
        "prediction_value": value,
        "prediction_rank": 1,
        "target_name": "net_return_pct",
        "actual_target_value": target,
        "trading_day": trading_day,
    }


def _training_result(strong=True, windows=4):
    artifacts = []
    for i in range(windows):
        if strong:
            predictions = [
                _prediction(f"w{i}_a", 0.9, 0.05),
                _prediction(f"w{i}_b", 0.5, 0.02),
                _prediction(f"w{i}_c", -0.2, -0.01),
                _prediction(f"w{i}_d", -0.8, -0.04),
                _prediction(f"w{i}_e", 0.7, 0.03),
            ]
        else:
            predictions = [
                _prediction(f"w{i}_a", -0.9, 0.05),
                _prediction(f"w{i}_b", -0.5, 0.02),
                _prediction(f"w{i}_c", 0.2, -0.01),
                _prediction(f"w{i}_d", 0.8, -0.04),
                _prediction(f"w{i}_e", -0.7, 0.03),
            ]
        artifacts.append(TrainingArtifact(window_id=f"w{i}", predictions=predictions))
    return TrainingResult(TrainingManifest(completed_windows=windows), artifacts)


def _request(**overrides):
    values = dict(
        evaluation_id="eval_001",
        training_run_id="train_run_001",
        experiment_id="exp_xgb_v1",
        candidate_namespace="shadow_meta_model.xgb_v1",
        primary_metric="rank_ic",
        min_completed_windows=4,
        min_validation_predictions=20,
        min_rank_ic_improvement=0.10,
        min_hit_rate_improvement=0.05,
        max_allowed_safety_violations=0,
        promotion_review_enabled=True,
        notes="phase25 test",
    )
    values.update(overrides)
    return Phase25EvaluationRequest(**values)


def test_request_rejects_unsafe_values():
    with pytest.raises(Phase25GovernanceError, match="candidate_namespace must start"):
        _request(candidate_namespace="production.bad")
    with pytest.raises(Phase25GovernanceError, match="primary_metric is not allowed"):
        _request(primary_metric="sharpe")
    with pytest.raises(Phase25GovernanceError, match="min_completed_windows must be >= 4"):
        _request(min_completed_windows=1)


def test_strong_model_is_ready_for_phase26_and_serializable():
    result = evaluate_shadow_model_governance(_training_result(strong=True), None, _request())

    assert result.evaluation_report.schema_version == "phase25_model_evaluation.0"
    assert result.evaluation_report.evaluated_windows == 4
    assert result.readiness_decision.decision == "ready_for_phase26_shadow_portfolio"
    assert result.readiness_decision.apply_to_production is False
    assert result.readiness_decision.production_config_changes == {}
    json.dumps(result.to_dict())
```

- [ ] **Step 2: Run and confirm failure**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_phase25_model_governance.py -q
```

Expected: FAIL because module does not exist.

---

### Task 2: Implement Contracts and Metrics

- [ ] **Step 1: Create implementation module**

Create `agent/research_v1/phase25_model_governance.py` with standard-library-only dataclasses and helpers:

```python
"""Phase 25 shadow model evaluation and advisory governance."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from typing import Any


ALLOWED_PRIMARY_METRICS = {"rank_ic", "directional_hit_rate", "spread_return"}


class Phase25GovernanceError(ValueError):
    """Raised for unsafe Phase 25 evaluation requests."""


@dataclass(frozen=True)
class Phase25EvaluationRequest:
    evaluation_id: str
    training_run_id: str
    experiment_id: str
    candidate_namespace: str
    primary_metric: str
    min_completed_windows: int
    min_validation_predictions: int
    min_rank_ic_improvement: float
    min_hit_rate_improvement: float
    max_allowed_safety_violations: int
    promotion_review_enabled: bool
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.candidate_namespace.startswith("shadow_meta_model."):
            raise Phase25GovernanceError("candidate_namespace must start with shadow_meta_model")
        if self.primary_metric not in ALLOWED_PRIMARY_METRICS:
            raise Phase25GovernanceError("primary_metric is not allowed")
        if self.min_completed_windows < 4:
            raise Phase25GovernanceError("min_completed_windows must be >= 4")
        if self.min_validation_predictions < 1:
            raise Phase25GovernanceError("min_validation_predictions must be >= 1")
        if self.max_allowed_safety_violations != 0:
            raise Phase25GovernanceError("max_allowed_safety_violations must be 0")
        if self.promotion_review_enabled is not True:
            raise Phase25GovernanceError("promotion_review_enabled must be true")


@dataclass(frozen=True)
class WindowEvaluationResult:
    evaluation_id: str
    training_run_id: str
    window_id: str
    candidate_namespace: str
    validation_prediction_count: int
    model_rank_ic: float
    baseline_rank_ic: float
    rank_ic_improvement: float
    model_directional_hit_rate: float
    baseline_directional_hit_rate: float
    hit_rate_improvement: float
    model_spread_return: float
    baseline_spread_return: float
    spread_return_improvement: float
    status: str
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ShadowModelEvaluationReport:
    schema_version: str
    evaluation_id: str
    training_run_id: str
    experiment_id: str
    candidate_namespace: str
    model_family: str
    total_windows: int
    evaluated_windows: int
    blocked_windows: int
    total_validation_predictions: int
    aggregate_model_rank_ic: float
    aggregate_baseline_rank_ic: float
    aggregate_rank_ic_improvement: float
    aggregate_model_hit_rate: float
    aggregate_baseline_hit_rate: float
    aggregate_hit_rate_improvement: float
    aggregate_model_spread_return: float
    aggregate_baseline_spread_return: float
    aggregate_spread_return_improvement: float
    window_results: list[WindowEvaluationResult]
    safety_violations: list[str]
    warnings: list[str]
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["window_results"] = [window.to_dict() for window in self.window_results]
        return data


@dataclass(frozen=True)
class PromotionReadinessDecision:
    schema_version: str
    evaluation_id: str
    training_run_id: str
    experiment_id: str
    candidate_namespace: str
    decision: str
    decision_reasons: list[str]
    required_observation_windows: int
    production_config_changes: dict[str, Any]
    apply_to_production: bool
    next_phase_recommendation: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Phase25GovernanceResult:
    evaluation_report: ShadowModelEvaluationReport
    readiness_decision: PromotionReadinessDecision

    def to_dict(self) -> dict[str, Any]:
        return {
            "evaluation_report": self.evaluation_report.to_dict(),
            "readiness_decision": self.readiness_decision.to_dict(),
        }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "to_dict"):
        return dict(value.to_dict())
    if hasattr(value, "__dict__"):
        return dict(value.__dict__)
    raise Phase25GovernanceError("input must be dict-like")
```

- [ ] **Step 2: Add metric helpers**

Append:

```python
def _rank(values: list[float], reverse: bool = False) -> list[float]:
    indexed = sorted(enumerate(values), key=lambda item: item[1], reverse=reverse)
    ranks = [0.0] * len(values)
    for rank, (index, _value) in enumerate(indexed, start=1):
        ranks[index] = float(rank)
    return ranks


def _pearson(xs: list[float], ys: list[float]) -> float:
    if len(xs) < 2 or len(xs) != len(ys):
        return 0.0
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    denom_x = sum((x - mean_x) ** 2 for x in xs) ** 0.5
    denom_y = sum((y - mean_y) ** 2 for y in ys) ** 0.5
    if denom_x == 0 or denom_y == 0:
        return 0.0
    return numerator / (denom_x * denom_y)


def _rank_ic(predictions: list[dict[str, Any]], value_key: str) -> float:
    scores = [float(pred[value_key]) for pred in predictions]
    targets = [float(pred["actual_target_value"]) for pred in predictions]
    return _pearson(_rank(scores, reverse=True), _rank(targets, reverse=True))


def _sign(value: float) -> int:
    return 1 if value > 0 else -1 if value < 0 else 0


def _hit_rate(predictions: list[dict[str, Any]], value_key: str) -> float:
    if not predictions:
        return 0.0
    hits = 0
    for pred in predictions:
        hits += 1 if _sign(float(pred[value_key])) == _sign(float(pred["actual_target_value"])) else 0
    return hits / len(predictions)


def _spread_return(predictions: list[dict[str, Any]], value_key: str) -> float:
    if len(predictions) < 2:
        return 0.0
    ordered = sorted(predictions, key=lambda pred: float(pred[value_key]), reverse=True)
    half = len(ordered) // 2
    top = ordered[:half]
    bottom = ordered[-half:]
    return sum(float(pred["actual_target_value"]) for pred in top) / len(top) - sum(float(pred["actual_target_value"]) for pred in bottom) / len(bottom)
```

- [ ] **Step 3: Implement governance function**

Append implementation that:

- converts training result manifest/artifacts to dicts
- validates safety
- builds zero baseline if baseline input is `None`
- evaluates each window
- aggregates metric averages
- produces gated decision

Use explicit warning strings from the spec.

- [ ] **Step 4: Run smoke tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_phase25_model_governance.py -q
```

Expected: PASS for initial tests.

---

### Task 3: Add Safety and Decision Tests

- [ ] **Step 1: Add acceptance tests**

Extend `tests/agent/research_v1/test_phase25_model_governance.py` with tests for:

```python
- unsafe training safety flag -> blocked_by_safety
- training target gross -> blocked_by_safety
- namespace mismatch -> blocked_by_safety
- baseline missing snapshot -> blocked_by_safety
- insufficient windows -> blocked_by_sample_size
- insufficient validation predictions -> blocked_by_sample_size
- weak/negative model -> rejected_underperforms_baseline
- marginal model -> watch_more_windows
- strong model -> ready_for_phase26_shadow_portfolio
- no model libraries imported
```

Use exact decision strings from the spec.

- [ ] **Step 2: Make implementation pass all tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_phase25_model_governance.py -q
```

Expected: all Phase 25 tests PASS.

---

### Task 4: Regression and Handoff

- [ ] **Step 1: Run Phase 25 test**

```bash
python3.11 -m pytest tests/agent/research_v1/test_phase25_model_governance.py -q
```

- [ ] **Step 2: Run P25 bundle**

```bash
python3.11 -m pytest \
  tests/agent/research_v1/test_p25_xgboost_shadow_adapter.py \
  tests/agent/research_v1/test_p25_training_dataset_builder.py \
  tests/agent/research_v1/test_p25_split_manifest_builder.py \
  tests/agent/research_v1/test_p25_shadow_training_runner.py \
  tests/agent/research_v1/test_phase25_model_governance.py \
  -q
```

- [ ] **Step 3: Run P20-P25 regression bundle**

Use the existing P20-P25 bundle plus `test_phase25_model_governance.py` and report exact output.

- [ ] **Step 4: Handoff**

```text
Phase 25 Shadow Model Evaluation and Governance Handoff

Changed files:

agent/research_v1/phase25_model_governance.py — created — evaluation metrics and advisory readiness gate
tests/agent/research_v1/test_phase25_model_governance.py — created — acceptance tests

Tests run:

python3.11 -m pytest tests/agent/research_v1/test_phase25_model_governance.py -q → N passed
python3.11 -m pytest [P25 bundle] -q → N passed
python3.11 -m pytest [P20-P25 regression bundle] -q → N passed

Acceptance checklist:

evaluation request contract exists: yes/no
window evaluation contract exists: yes/no
evaluation report contract exists: yes/no
promotion readiness decision contract exists: yes/no
consumes P25-D training result: yes/no
baseline comparison implemented: yes/no
rank IC implemented: yes/no
hit rate implemented: yes/no
spread return implemented: yes/no
safety violations block readiness: yes/no
sample-size gate implemented: yes/no
underperformance rejected: yes/no
ready-for-phase26 decision gated: yes/no
production_config_changes empty: yes/no
apply_to_production false: yes/no
JSON serialization works: yes/no
no model libraries imported: yes/no
P20-P25 regression green: yes/no

Known issues:

None.
```
