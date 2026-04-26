# P24-D Shadow Run Persistence and Observation Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist P24 shadow run records and bridge them into observation summaries without promoting outputs, mutating production configs, or training models.

**Architecture:** Add `p24_run_persistence.py` with an in-memory `ShadowRunStore`, validation helpers, `ShadowRunSummary`, `ShadowExperimentObservation`, and bridge functions. The store consumes `ShadowExperimentRunRecord` from P24-C and `ShadowExperimentManifest` from P24-B, storing JSON-serializable dict copies and reconstructing records for queries.

**Tech Stack:** Python 3.11, dataclasses, stdlib only, pytest.

---

## Source Specs

- `docs/superpowers/specs/2026-04-25-hermes-p24-shadow-run-persistence-observation-spec.md`
- `docs/superpowers/specs/2026-04-25-hermes-p24-shadow-experiment-runner-spec.md`
- `docs/superpowers/specs/2026-04-25-hermes-p24-shadow-experiment-registry-spec.md`

## Files

### Create

- `agent/research_v1/p24_run_persistence.py`
- `tests/agent/research_v1/test_p24_run_persistence.py`

### Modify

- None expected.

---

## Task 1: Store Contracts and Basic Persistence

**Files:**
- Create: `agent/research_v1/p24_run_persistence.py`
- Test: `tests/agent/research_v1/test_p24_run_persistence.py`

- [ ] **Step 1: Write failing persistence tests**

Create `tests/agent/research_v1/test_p24_run_persistence.py`:

```python
import json

import pytest

from agent.research_v1.p24_entry_gate import (
    P24CandidateRequest,
    P24SystemEvidence,
    evaluate_p24_entry_gate,
)
from agent.research_v1.p24_experiment_registry import ShadowExperimentRegistry, ShadowExperimentRequest
from agent.research_v1.p24_shadow_runner import (
    ShadowAdapterResult,
    ShadowExperimentRunRequest,
    run_shadow_experiment,
)
from agent.research_v1.p24_run_persistence import ShadowRunPersistenceError, ShadowRunStore


def _gate_report(**overrides):
    values = dict(
        candidate_name="xgb_meta_v1",
        candidate_family="xgboost_meta_model",
        candidate_namespace="shadow_meta_model.xgb_v1",
        requested_phase="P24",
        intended_outputs=["shadow_meta_model.xgb_v1.shadow_ranking_score"],
        uses_point_in_time_sources=True,
        source_audit_plan_defined=True,
        simple_baseline_defined=True,
        out_of_sample_plan_defined=True,
        uses_gross_returns_as_primary=False,
        writes_production_fields=False,
        requires_portfolio_layer=False,
        requires_execution_data=False,
        residualization_plan_defined=False,
        notes="persistence test",
    )
    values.update(overrides)
    evidence = P24SystemEvidence(
        p20_accepted=True,
        p21_accepted=True,
        p22_accepted=True,
        p23_accepted=True,
        return_basis_default="net",
        lookahead_violation_rate=0.0,
        source_audit_gap_rate=0.0,
        ready_for_p24_gate=True,
        ready_factor_count=3,
        core_factors_with_net_icir_gt_030=3,
        ready_factor_horizon_count=3,
        max_abs_cross_factor_correlation=0.50,
        independent_cross_sectional_observations=800,
        regime_gate_has_return_separation=True,
        portfolio_layer_exists=False,
        execution_dataset_exists=False,
    )
    return evaluate_p24_entry_gate(P24CandidateRequest(**values), evidence)


def _experiment_request(**overrides):
    values = dict(
        experiment_id="exp_xgb_meta_v1",
        candidate_id="xgb_meta_v1",
        candidate_name="xgb_meta_v1",
        candidate_family="xgboost_meta_model",
        candidate_namespace="shadow_meta_model.xgb_v1",
        source_gate_report_id="gate_xgb_meta_v1",
        owner="research",
        purpose="Persistence bridge test.",
        input_contract={
            "allowed_sources": ["factor_snapshots", "forward_return_observations"],
            "required_point_in_time_fields": ["trading_day", "data_as_of_date", "universe_membership_snapshot_id"],
            "forbidden_sources": ["future_prices"],
            "max_source_audit_gap_rate": 0.20,
            "lookahead_policy": "strict_no_future_data",
        },
        output_contract={
            "allowed_outputs": ["shadow_meta_model.xgb_v1.shadow_ranking_score"],
            "output_namespace": "shadow_meta_model.xgb_v1",
            "writes_canonical_factor_snapshot": False,
            "writes_production_config": False,
            "affects_live_trading": False,
            "return_basis": "net",
        },
        forbidden_outputs=[
            "company_quality_score",
            "valuation_attractiveness_score",
            "timing_market_fit_score",
            "llm_adjustment_total",
            "classification",
            "production_config",
            "canonical_factor_snapshot",
            "live_trade_signal",
        ],
        training_data_window={
            "start_date": "2024-01-01",
            "end_date": "2026-01-01",
            "minimum_observations": 500,
            "purged_validation_gap_days": 5,
            "embargo_days": 5,
            "point_in_time_membership_required": True,
        },
        point_in_time_policy={
            "source_timestamp_required": True,
            "membership_snapshot_required": True,
            "revision_policy": "as_reported_only",
        },
        baseline_comparison_plan={
            "baseline_name": "prior_linear_factor_blend",
            "baseline_type": "current_prior",
            "primary_metric": "net_icir",
            "secondary_metrics": ["net_ic"],
            "comparison_direction": "higher_is_better",
            "minimum_evaluation_windows": 4,
        },
        out_of_sample_validation_plan={
            "method": "walk_forward",
            "walk_forward_enabled": True,
            "holdout_periods": ["2026H1"],
            "leakage_checks": ["point_in_time", "purged_embargo"],
            "promotion_criteria_documented": True,
        },
        observation_plan={
            "observation_frequency": "weekly",
            "minimum_shadow_windows": 4,
            "required_reports": ["ModelAdmissionGateReport", "ShadowExperimentManifest", "ShadowObservationReport"],
            "revocation_triggers": ["lookahead_violation", "net_underperformance"],
        },
        resource_policy={
            "max_runtime_minutes": 30,
            "max_memory_mb": 4096,
            "model_libraries_allowed": False,
        },
        expected_artifacts=["manifest", "shadow_predictions_file", "observation_report"],
        notes="persistence manifest",
    )
    values.update(overrides)
    return ShadowExperimentRequest(**values)


def _manifest():
    registry = ShadowExperimentRegistry()
    return registry.register_shadow_experiment(_experiment_request(), _gate_report())


def _run_request(**overrides):
    values = dict(
        run_id="run_xgb_meta_v1_001",
        experiment_id="exp_xgb_meta_v1",
        run_mode="dry_run",
        input_window={
            "start_date": "2026-01-01",
            "end_date": "2026-03-31",
            "data_as_of_policy": "manifest_point_in_time_policy",
            "point_in_time_required": True,
        },
        requested_artifacts=["shadow_meta_model.xgb_v1.dry_run_metadata"],
        operator="codex",
        reason="verify persistence",
        notes="dry run",
    )
    values.update(overrides)
    return ShadowExperimentRunRequest(**values)


def _run_record(**request_overrides):
    return run_shadow_experiment(_manifest(), adapter=None, run_request=_run_request(**request_overrides)).record


def test_completed_run_is_saved_and_retrieved():
    store = ShadowRunStore()
    record = _run_record()

    saved = store.save_run_record(record)

    assert saved.run_id == "run_xgb_meta_v1_001"
    assert store.get_run_record("run_xgb_meta_v1_001") == saved
    json.dumps(saved.to_dict())


def test_duplicate_run_id_is_rejected():
    store = ShadowRunStore()
    record = _run_record()
    store.save_run_record(record)

    with pytest.raises(ShadowRunPersistenceError, match="duplicate run_id"):
        store.save_run_record(record)
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p24_run_persistence.py::test_completed_run_is_saved_and_retrieved tests/agent/research_v1/test_p24_run_persistence.py::test_duplicate_run_id_is_rejected -q
```

Expected: FAIL because `p24_run_persistence.py` does not exist.

- [ ] **Step 3: Implement store contracts**

Create `agent/research_v1/p24_run_persistence.py`:

```python
"""P24-D shadow run persistence and observation bridge."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone

from agent.research_v1.p24_experiment_registry import ShadowExperimentManifest
from agent.research_v1.p24_shadow_runner import ShadowExperimentRunRecord


class ShadowRunPersistenceError(ValueError):
    """Raised when a shadow run record cannot be persisted or observed safely."""


@dataclass(frozen=True)
class ShadowRunSummary:
    schema_version: str
    experiment_id: str
    total_runs: int
    completed_count: int
    blocked_count: int
    failed_count: int
    last_run_id: str
    last_run_status: str
    blocked_reason_frequency: dict[str, int]
    failed_error_frequency: dict[str, int]
    latest_completed_at: str
    health_status: str
    revocation_recommended: bool
    revocation_reasons: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ShadowExperimentObservation:
    schema_version: str
    experiment_id: str
    run_id: str
    candidate_id: str
    candidate_family: str
    run_status: str
    health_status: str
    produced_artifacts: list[str]
    blocked_artifacts: list[str]
    warnings: list[str]
    revocation_recommended: bool
    revocation_reasons: list[str]
    source_manifest_schema_version: str
    source_run_schema_version: str
    no_production_write_confirmed: bool
    created_at: str

    def to_dict(self) -> dict:
        return asdict(self)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ShadowRunStore:
    def __init__(self) -> None:
        self._records: dict[str, ShadowExperimentRunRecord] = {}
        self._order: list[str] = []

    def save_run_record(self, record: ShadowExperimentRunRecord) -> ShadowExperimentRunRecord:
        _validate_record_for_persistence(record)
        if record.run_id in self._records:
            raise ShadowRunPersistenceError(f"duplicate run_id: {record.run_id}")
        json.loads(json.dumps(record.to_dict()))
        self._records[record.run_id] = record
        self._order.append(record.run_id)
        return record

    def get_run_record(self, run_id: str) -> ShadowExperimentRunRecord | None:
        return self._records.get(run_id)

    def list_run_records(
        self,
        experiment_id: str | None = None,
        status: str | None = None,
    ) -> list[ShadowExperimentRunRecord]:
        records = [self._records[run_id] for run_id in self._order]
        if experiment_id is not None:
            records = [record for record in records if record.experiment_id == experiment_id]
        if status is not None:
            records = [record for record in records if record.status == status]
        return records

    def summarize_experiment_runs(self, experiment_id: str) -> ShadowRunSummary:
        records = self.list_run_records(experiment_id=experiment_id)
        return summarize_run_records(experiment_id, records)
```

- [ ] **Step 4: Add persistence validators and summary skeleton**

Append to `agent/research_v1/p24_run_persistence.py`:

```python
def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ShadowRunPersistenceError(message)


def _validate_record_for_persistence(record: ShadowExperimentRunRecord) -> None:
    _require(record.schema_version.startswith("p24_run."), "run schema_version must start with p24_run.")
    _require(bool(record.run_id), "run_id is required")
    _require(record.no_production_write_confirmed is True, "no_production_write_confirmed must be true")
    _require(record.canonical_snapshot_write_blocked is True, "canonical_snapshot_write_blocked must be true")
    _require(record.production_config_write_blocked is True, "production_config_write_blocked must be true")
    _require(record.live_trading_blocked is True, "live_trading_blocked must be true")


def summarize_run_records(experiment_id: str, records: list[ShadowExperimentRunRecord]) -> ShadowRunSummary:
    if not records:
        return ShadowRunSummary(
            schema_version="p24_run_summary.0",
            experiment_id=experiment_id,
            total_runs=0,
            completed_count=0,
            blocked_count=0,
            failed_count=0,
            last_run_id="",
            last_run_status="",
            blocked_reason_frequency={},
            failed_error_frequency={},
            latest_completed_at="",
            health_status="no_runs",
            revocation_recommended=False,
            revocation_reasons=[],
        )
    completed_count = sum(1 for record in records if record.status == "completed")
    blocked_count = sum(1 for record in records if record.status == "blocked")
    failed_count = sum(1 for record in records if record.status == "failed")
    blocked_reason_frequency = Counter(reason for record in records for reason in record.blocked_artifacts)
    failed_error_frequency = Counter(record.error_message for record in records if record.status == "failed" and record.error_message)
    latest_completed_at = max((record.completed_at for record in records), default="")
    health_status, revocation_reasons = _summary_health(records, completed_count, blocked_count, failed_count)
    return ShadowRunSummary(
        schema_version="p24_run_summary.0",
        experiment_id=experiment_id,
        total_runs=len(records),
        completed_count=completed_count,
        blocked_count=blocked_count,
        failed_count=failed_count,
        last_run_id=records[-1].run_id,
        last_run_status=records[-1].status,
        blocked_reason_frequency=dict(blocked_reason_frequency),
        failed_error_frequency=dict(failed_error_frequency),
        latest_completed_at=latest_completed_at,
        health_status=health_status,
        revocation_recommended=health_status == "revocation_recommended",
        revocation_reasons=revocation_reasons,
    )
```

- [ ] **Step 5: Run initial tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p24_run_persistence.py::test_completed_run_is_saved_and_retrieved tests/agent/research_v1/test_p24_run_persistence.py::test_duplicate_run_id_is_rejected -q
```

Expected: FAIL because `_summary_health` is not implemented or PASS if not invoked. Continue to Task 2 either way.

---

## Task 2: Query, Status Counts, and Safety Validation

**Files:**
- Modify: `agent/research_v1/p24_run_persistence.py`
- Modify: `tests/agent/research_v1/test_p24_run_persistence.py`

- [ ] **Step 1: Add blocked/failed records and query tests**

Append to `tests/agent/research_v1/test_p24_run_persistence.py`:

```python
class GoodAdapter:
    adapter_name = "good"
    adapter_version = "0.1"

    def run(self, manifest, request):
        return ShadowAdapterResult(
            adapter_name=self.adapter_name,
            adapter_version=self.adapter_version,
            produced_artifacts=["shadow_meta_model.xgb_v1.predictions"],
            attempted_outputs=["shadow_meta_model.xgb_v1.predictions"],
            metrics={},
            logs=[],
            warnings=[],
        )


class ExplodingAdapter:
    adapter_name = "boom"
    adapter_version = "0.1"

    def run(self, manifest, request):
        raise RuntimeError("boom")


def _blocked_record(run_id="run_blocked_001"):
    return run_shadow_experiment(
        _manifest(),
        adapter=None,
        run_request=_run_request(run_id=run_id, requested_artifacts=["production_config"]),
    ).record


def _failed_record(run_id="run_failed_001"):
    return run_shadow_experiment(
        _manifest(),
        adapter=ExplodingAdapter(),
        run_request=_run_request(run_id=run_id, run_mode="shadow_stub"),
    ).record


def test_blocked_and_failed_runs_are_saved_and_retrieved():
    store = ShadowRunStore()
    blocked = store.save_run_record(_blocked_record())
    failed = store.save_run_record(_failed_record())

    assert store.get_run_record(blocked.run_id).status == "blocked"
    assert store.get_run_record(failed.run_id).status == "failed"


def test_records_query_by_experiment_and_status():
    store = ShadowRunStore()
    completed = store.save_run_record(_run_record(run_id="run_completed_001"))
    blocked = store.save_run_record(_blocked_record())
    store.save_run_record(_failed_record())

    assert store.list_run_records(experiment_id="exp_xgb_meta_v1")[0] == completed
    assert store.list_run_records(status="blocked") == [blocked]


def test_false_production_safety_flag_is_rejected():
    store = ShadowRunStore()
    record = replace(_run_record(), no_production_write_confirmed=False)

    with pytest.raises(ShadowRunPersistenceError, match="no_production_write_confirmed must be true"):
        store.save_run_record(record)
```

- [ ] **Step 2: Import `replace`**

At the top of `tests/agent/research_v1/test_p24_run_persistence.py`, add:

```python
from dataclasses import replace
```

- [ ] **Step 3: Run query tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p24_run_persistence.py -q
```

Expected: FAIL only if `_summary_health` import-time reference breaks. Implement Task 3 next.

---

## Task 3: Summary Health Rules

**Files:**
- Modify: `agent/research_v1/p24_run_persistence.py`
- Modify: `tests/agent/research_v1/test_p24_run_persistence.py`

- [ ] **Step 1: Add summary tests**

Append to `tests/agent/research_v1/test_p24_run_persistence.py`:

```python
def test_summary_counts_statuses_and_blocked_reason_frequency():
    store = ShadowRunStore()
    store.save_run_record(_run_record(run_id="run_completed_001"))
    store.save_run_record(_blocked_record(run_id="run_blocked_001"))
    store.save_run_record(_failed_record(run_id="run_failed_001"))

    summary = store.summarize_experiment_runs("exp_xgb_meta_v1")

    assert summary.total_runs == 3
    assert summary.completed_count == 1
    assert summary.blocked_count == 1
    assert summary.failed_count == 1
    assert summary.blocked_reason_frequency["requested_forbidden_artifact:production_config"] == 1
    assert summary.last_run_status == "failed"
    assert summary.health_status == "watch"


def test_three_consecutive_blocked_or_failed_runs_recommend_revocation():
    store = ShadowRunStore()
    store.save_run_record(_blocked_record(run_id="run_blocked_001"))
    store.save_run_record(_failed_record(run_id="run_failed_001"))
    store.save_run_record(_blocked_record(run_id="run_blocked_002"))

    summary = store.summarize_experiment_runs("exp_xgb_meta_v1")

    assert summary.health_status == "revocation_recommended"
    assert summary.revocation_recommended is True
    assert "three_consecutive_blocked_or_failed_runs" in summary.revocation_reasons
```

- [ ] **Step 2: Implement summary health**

Append to `agent/research_v1/p24_run_persistence.py`:

```python
def _is_production_path_reason(reason: str) -> bool:
    return any(
        token in reason
        for token in (
            "production",
            "canonical",
            "live_trading",
            "live_trade_signal",
        )
    )


def _summary_health(
    records: list[ShadowExperimentRunRecord],
    completed_count: int,
    blocked_count: int,
    failed_count: int,
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if any(_is_production_path_reason(reason) for record in records for reason in record.blocked_artifacts):
        reasons.append("production_or_canonical_path_blocked")
    if len(records) >= 3 and all(record.status in {"blocked", "failed"} for record in records[-3:]):
        reasons.append("three_consecutive_blocked_or_failed_runs")
    if reasons:
        return "revocation_recommended", reasons
    if records[-1].status == "completed" and blocked_count == 0 and failed_count == 0:
        return "healthy", []
    if blocked_count + failed_count > completed_count:
        return "watch", []
    return "watch", []
```

- [ ] **Step 3: Run summary tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p24_run_persistence.py -q
```

Expected: current tests PASS.

---

## Task 4: Observation Bridge

**Files:**
- Modify: `agent/research_v1/p24_run_persistence.py`
- Modify: `tests/agent/research_v1/test_p24_run_persistence.py`

- [ ] **Step 1: Add observation bridge tests**

Append to `tests/agent/research_v1/test_p24_run_persistence.py`:

```python
from agent.research_v1.p24_run_persistence import build_shadow_experiment_observation


def test_observation_bridge_creates_healthy_observation_for_completed_run():
    manifest = _manifest()
    record = _run_record()

    observation = build_shadow_experiment_observation(record, manifest)

    assert observation.schema_version == "p24_observation.0"
    assert observation.experiment_id == "exp_xgb_meta_v1"
    assert observation.run_id == record.run_id
    assert observation.run_status == "completed"
    assert observation.health_status == "healthy"
    assert observation.revocation_recommended is False
    assert observation.no_production_write_confirmed is True
    json.dumps(observation.to_dict())


def test_observation_bridge_recommends_revocation_for_production_block():
    manifest = _manifest()
    record = _blocked_record()

    observation = build_shadow_experiment_observation(record, manifest)

    assert observation.health_status == "revocation_recommended"
    assert observation.revocation_recommended is True
    assert "production_or_canonical_path_blocked" in observation.revocation_reasons


def test_observation_bridge_blocks_manifest_run_mismatch():
    manifest = _manifest()
    record = replace(_run_record(), experiment_id="other_experiment")

    with pytest.raises(ShadowRunPersistenceError, match="experiment_id mismatch"):
        build_shadow_experiment_observation(record, manifest)
```

- [ ] **Step 2: Implement observation bridge**

Append to `agent/research_v1/p24_run_persistence.py`:

```python
def _observation_health(record: ShadowExperimentRunRecord) -> tuple[str, list[str]]:
    if record.status == "completed":
        return "healthy", []
    if record.status == "blocked" and any(_is_production_path_reason(reason) for reason in record.blocked_artifacts):
        return "revocation_recommended", ["production_or_canonical_path_blocked"]
    if record.status in {"blocked", "failed"}:
        return "watch", []
    return "watch", []


def build_shadow_experiment_observation(
    record: ShadowExperimentRunRecord,
    manifest: ShadowExperimentManifest,
) -> ShadowExperimentObservation:
    _require(record.experiment_id == manifest.experiment_id, "experiment_id mismatch")
    _require(record.candidate_id == manifest.candidate_id, "candidate_id mismatch")
    _require(record.output_namespace == manifest.shadow_namespace, "output namespace mismatch")
    health_status, revocation_reasons = _observation_health(record)
    return ShadowExperimentObservation(
        schema_version="p24_observation.0",
        experiment_id=record.experiment_id,
        run_id=record.run_id,
        candidate_id=record.candidate_id,
        candidate_family=record.candidate_family,
        run_status=record.status,
        health_status=health_status,
        produced_artifacts=list(record.produced_artifacts),
        blocked_artifacts=list(record.blocked_artifacts),
        warnings=list(record.warnings),
        revocation_recommended=health_status == "revocation_recommended",
        revocation_reasons=revocation_reasons,
        source_manifest_schema_version=manifest.schema_version,
        source_run_schema_version=record.schema_version,
        no_production_write_confirmed=record.no_production_write_confirmed,
        created_at=_utc_now(),
    )
```

- [ ] **Step 3: Run observation tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p24_run_persistence.py -q
```

Expected: all current P24-D tests PASS.

---

## Task 5: Serialization, No Model Libraries, and Regression

**Files:**
- Modify: `tests/agent/research_v1/test_p24_run_persistence.py`

- [ ] **Step 1: Add final safety tests**

Append to `tests/agent/research_v1/test_p24_run_persistence.py`:

```python
def test_store_returns_json_serializable_records():
    store = ShadowRunStore()
    saved = store.save_run_record(_run_record())

    json.dumps(saved.to_dict())
    json.dumps(store.summarize_experiment_runs("exp_xgb_meta_v1").to_dict())


def test_persistence_module_does_not_import_model_libraries():
    import agent.research_v1.p24_run_persistence as persistence_module

    module_names = set(persistence_module.__dict__)
    forbidden_names = {"xgboost", "torch", "tensorflow", "sklearn", "stable_baselines3"}

    assert module_names.isdisjoint(forbidden_names)
```

- [ ] **Step 2: Run P24-D tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p24_run_persistence.py -q
```

Expected: all P24-D tests PASS.

- [ ] **Step 3: Run P24-A/B/C/D tests together**

Run:

```bash
python3.11 -m pytest \
  tests/agent/research_v1/test_p24_entry_gate.py \
  tests/agent/research_v1/test_p24_experiment_registry.py \
  tests/agent/research_v1/test_p24_shadow_runner.py \
  tests/agent/research_v1/test_p24_run_persistence.py \
  -q
```

Expected: all P24 tests PASS.

- [ ] **Step 4: Run P20-P24 regression bundle**

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
  -q
```

Expected: all selected tests PASS.

- [ ] **Step 5: Scan for forbidden model imports**

Run:

```bash
grep -R "import xgboost\|from xgboost\|import torch\|from torch\|import tensorflow\|from tensorflow\|stable_baselines\|import sklearn\|from sklearn" -n \
  agent/research_v1/p24_run_persistence.py \
  tests/agent/research_v1/test_p24_run_persistence.py || true
```

Expected: no output except possible string literals inside the no-model-library test.

---

## Final Handoff Format

Return:

```text
P24-D Shadow Run Persistence + Observation Bridge Handoff

Changed files:
- <path> — <created/modified> — <purpose>

Tests run:
- <command> → <result>

Acceptance checklist:
- completed/blocked/failed runs persist: yes/no
- duplicate run IDs rejected: yes/no
- production safety flags enforced: yes/no
- query by experiment ID works: yes/no
- query by status works: yes/no
- summary counts statuses: yes/no
- blocked reason frequency computed: yes/no
- observation bridge validates manifest/run identity: yes/no
- revocation recommendation only, no auto revoke: yes/no
- JSON serialization works: yes/no
- no model libraries imported: yes/no
- P20-P24 regression green: yes/no

Known issues:
- <issue or None>
```
