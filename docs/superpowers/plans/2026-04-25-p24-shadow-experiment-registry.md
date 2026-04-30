# P24-B Shadow Experiment Registry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a shadow experiment registry that turns passing P24 gate reports into immutable, auditable experiment manifests without training models or modifying production behavior.

**Architecture:** Add `p24_experiment_registry.py` with dataclass contracts, typed registration errors, validation helpers, and an in-memory registry. The module depends on `p24_entry_gate.py` reports but remains stdlib-only. Tests validate registration, rejection, query, revocation, archival, and safety boundaries.

**Tech Stack:** Python 3.11, dataclasses, stdlib only, pytest.

---

## Source Specs

- `docs/superpowers/specs/2026-04-25-hermes-p24-shadow-experiment-registry-spec.md`
- `docs/superpowers/specs/2026-04-25-hermes-p24-entry-gate-evaluator-spec.md`
- `docs/superpowers/specs/2026-04-25-hermes-p24-p26-advanced-quant-capability-roadmap.md`

## Files

### Create

- `agent/research_v1/p24_experiment_registry.py`
- `tests/agent/research_v1/test_p24_experiment_registry.py`

### Modify

- None expected.

---

## Task 1: Registry Contracts and Happy Path

**Files:**
- Create: `agent/research_v1/p24_experiment_registry.py`
- Test: `tests/agent/research_v1/test_p24_experiment_registry.py`

- [ ] **Step 1: Write failing happy-path test**

Create `tests/agent/research_v1/test_p24_experiment_registry.py`:

```python
from agent.research_v1.p24_entry_gate import (
    P24CandidateRequest,
    P24SystemEvidence,
    evaluate_p24_entry_gate,
)
from agent.research_v1.p24_experiment_registry import (
    ShadowExperimentRegistry,
    ShadowExperimentRequest,
)


def _gate_report(**request_overrides):
    request_values = dict(
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
        notes="registry test",
    )
    request_values.update(request_overrides)
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
    return evaluate_p24_entry_gate(P24CandidateRequest(**request_values), evidence)


def _experiment_request(**overrides):
    values = dict(
        experiment_id="exp_xgb_meta_v1",
        candidate_id="xgb_meta_v1",
        candidate_name="xgb_meta_v1",
        candidate_family="xgboost_meta_model",
        candidate_namespace="shadow_meta_model.xgb_v1",
        source_gate_report_id="gate_xgb_meta_v1",
        owner="research",
        purpose="Shadow-test nonlinear combination of validated factors.",
        input_contract={
            "allowed_sources": ["factor_snapshots", "forward_return_observations"],
            "required_point_in_time_fields": ["trading_day", "data_as_of_date", "universe_membership_snapshot_id"],
            "forbidden_sources": ["future_prices", "restated_fundamentals_without_asof"],
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
            "secondary_metrics": ["net_ic", "net_return_spread"],
            "comparison_direction": "higher_is_better",
            "minimum_evaluation_windows": 4,
        },
        out_of_sample_validation_plan={
            "method": "walk_forward",
            "walk_forward_enabled": True,
            "holdout_periods": ["2025H2", "2026H1"],
            "leakage_checks": ["point_in_time", "purged_embargo"],
            "promotion_criteria_documented": True,
        },
        observation_plan={
            "observation_frequency": "weekly",
            "minimum_shadow_windows": 4,
            "required_reports": ["ModelAdmissionGateReport", "ShadowExperimentManifest", "ShadowObservationReport"],
            "revocation_triggers": ["lookahead_violation", "source_audit_gap_too_high", "net_underperformance"],
        },
        resource_policy={
            "max_runtime_minutes": 30,
            "max_memory_mb": 4096,
            "model_libraries_allowed": False,
        },
        expected_artifacts=["manifest", "shadow_predictions_file", "observation_report"],
        notes="happy path",
    )
    values.update(overrides)
    return ShadowExperimentRequest(**values)


def test_register_passing_gate_report_creates_manifest():
    registry = ShadowExperimentRegistry()
    manifest = registry.register_shadow_experiment(_experiment_request(), _gate_report())

    assert manifest.status == "registered"
    assert manifest.schema_version == "p24_manifest.0"
    assert manifest.source_gate_report_id == "gate_xgb_meta_v1"
    assert manifest.source_gate_schema_version == "p24_gate.0"
    assert manifest.promotion_blocked is True
    assert manifest.production_write_blocked is True
    assert manifest.canonical_snapshot_write_blocked is True
    assert manifest.shadow_namespace == "shadow_meta_model.xgb_v1"
    assert registry.get_experiment("exp_xgb_meta_v1") == manifest
```

- [ ] **Step 2: Run failing test**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p24_experiment_registry.py::test_register_passing_gate_report_creates_manifest -q
```

Expected: FAIL because `p24_experiment_registry.py` does not exist.

- [ ] **Step 3: Implement contracts and happy path**

Create `agent/research_v1/p24_experiment_registry.py`:

```python
"""P24-B shadow experiment registry.

This module registers auditable shadow experiment manifests for candidates
that already passed the P24 entry gate. It does not train models, write
canonical factor snapshots, or mutate production configuration.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from typing import Iterable

from agent.research_v1.p24_entry_gate import ModelAdmissionGateReport


REQUIRED_FORBIDDEN_OUTPUTS = frozenset(
    {
        "company_quality_score",
        "valuation_attractiveness_score",
        "timing_market_fit_score",
        "llm_adjustment_total",
        "classification",
        "production_config",
        "canonical_factor_snapshot",
        "live_trade_signal",
    }
)

ALLOWED_PRIMARY_METRICS = frozenset({"net_ic", "net_icir", "cost_reduction_bps", "net_return_spread"})


class ShadowExperimentRegistrationError(ValueError):
    """Raised when a shadow experiment request violates P24-B registry rules."""


@dataclass(frozen=True)
class ShadowExperimentRequest:
    experiment_id: str
    candidate_id: str
    candidate_name: str
    candidate_family: str
    candidate_namespace: str
    source_gate_report_id: str
    owner: str
    purpose: str
    input_contract: dict
    output_contract: dict
    forbidden_outputs: list[str]
    training_data_window: dict
    point_in_time_policy: dict
    baseline_comparison_plan: dict
    out_of_sample_validation_plan: dict
    observation_plan: dict
    resource_policy: dict
    expected_artifacts: list[str]
    notes: str = ""


@dataclass(frozen=True)
class ShadowExperimentManifest:
    schema_version: str
    experiment_id: str
    candidate_id: str
    candidate_name: str
    candidate_family: str
    candidate_namespace: str
    source_gate_report_id: str
    source_gate_schema_version: str
    status: str
    owner: str
    purpose: str
    input_contract: dict
    output_contract: dict
    forbidden_outputs: list[str]
    training_data_window: dict
    point_in_time_policy: dict
    baseline_comparison_plan: dict
    out_of_sample_validation_plan: dict
    observation_plan: dict
    resource_policy: dict
    expected_artifacts: list[str]
    promotion_blocked: bool
    production_write_blocked: bool
    canonical_snapshot_write_blocked: bool
    shadow_namespace: str
    gate_warnings: list[str]
    blocking_reasons: list[str]
    registered_at: str
    notes: str

    def to_dict(self) -> dict:
        return asdict(self)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ShadowExperimentRegistry:
    def __init__(self) -> None:
        self._manifests: dict[str, ShadowExperimentManifest] = {}
        self._history: dict[str, list[ShadowExperimentManifest]] = {}

    def register_shadow_experiment(
        self,
        request: ShadowExperimentRequest,
        gate_report: ModelAdmissionGateReport,
    ) -> ShadowExperimentManifest:
        _validate_gate_report(gate_report)
        _validate_request_matches_gate(request, gate_report)
        _validate_manifest_contracts(request)
        manifest = ShadowExperimentManifest(
            schema_version="p24_manifest.0",
            experiment_id=request.experiment_id,
            candidate_id=request.candidate_id,
            candidate_name=request.candidate_name,
            candidate_family=request.candidate_family,
            candidate_namespace=request.candidate_namespace,
            source_gate_report_id=request.source_gate_report_id,
            source_gate_schema_version=gate_report.schema_version,
            status="registered",
            owner=request.owner,
            purpose=request.purpose,
            input_contract=dict(request.input_contract),
            output_contract=dict(request.output_contract),
            forbidden_outputs=list(request.forbidden_outputs),
            training_data_window=dict(request.training_data_window),
            point_in_time_policy=dict(request.point_in_time_policy),
            baseline_comparison_plan=dict(request.baseline_comparison_plan),
            out_of_sample_validation_plan=dict(request.out_of_sample_validation_plan),
            observation_plan=dict(request.observation_plan),
            resource_policy=dict(request.resource_policy),
            expected_artifacts=list(request.expected_artifacts),
            promotion_blocked=True,
            production_write_blocked=True,
            canonical_snapshot_write_blocked=True,
            shadow_namespace=request.output_contract["output_namespace"],
            gate_warnings=list(gate_report.warnings),
            blocking_reasons=[],
            registered_at=_utc_now(),
            notes=request.notes,
        )
        self._manifests[manifest.experiment_id] = manifest
        self._history.setdefault(manifest.experiment_id, []).append(manifest)
        return manifest

    def get_experiment(self, experiment_id: str) -> ShadowExperimentManifest | None:
        return self._manifests.get(experiment_id)

    def get_experiment_history(self, experiment_id: str) -> list[ShadowExperimentManifest]:
        return list(self._history.get(experiment_id, []))

    def list_experiments(
        self,
        status: str | None = None,
        candidate_family: str | None = None,
    ) -> list[ShadowExperimentManifest]:
        manifests = list(self._manifests.values())
        if status is not None:
            manifests = [manifest for manifest in manifests if manifest.status == status]
        if candidate_family is not None:
            manifests = [manifest for manifest in manifests if manifest.candidate_family == candidate_family]
        return manifests

    def list_active_experiments(self, candidate_family: str | None = None) -> list[ShadowExperimentManifest]:
        return self.list_experiments(status="registered", candidate_family=candidate_family)

    def revoke_experiment(self, experiment_id: str, reason: str) -> ShadowExperimentManifest:
        return self._change_status(experiment_id, "revoked", reason)

    def archive_experiment(self, experiment_id: str, reason: str) -> ShadowExperimentManifest:
        return self._change_status(experiment_id, "archived", reason)

    def _change_status(self, experiment_id: str, status: str, reason: str) -> ShadowExperimentManifest:
        current = self._manifests.get(experiment_id)
        if current is None:
            raise ShadowExperimentRegistrationError(f"unknown experiment_id: {experiment_id}")
        updated = replace(current, status=status, notes=f"{current.notes}; {status}: {reason}")
        self._manifests[experiment_id] = updated
        self._history.setdefault(experiment_id, []).append(updated)
        return updated
```

- [ ] **Step 4: Run happy-path test**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p24_experiment_registry.py::test_register_passing_gate_report_creates_manifest -q
```

Expected: FAIL because validation helpers are not implemented yet.

---

## Task 2: Validation Helpers and Safety Blocks

**Files:**
- Modify: `agent/research_v1/p24_experiment_registry.py`
- Test: `tests/agent/research_v1/test_p24_experiment_registry.py`

- [ ] **Step 1: Add failing safety tests**

Append to `tests/agent/research_v1/test_p24_experiment_registry.py`:

```python
import pytest

from agent.research_v1.p24_experiment_registry import ShadowExperimentRegistrationError


def test_failed_gate_report_cannot_register():
    failed_report = _gate_report(writes_production_fields=True)
    registry = ShadowExperimentRegistry()

    with pytest.raises(ShadowExperimentRegistrationError, match="gate report did not pass"):
        registry.register_shadow_experiment(_experiment_request(), failed_report)


def test_namespace_mismatch_is_blocked():
    registry = ShadowExperimentRegistry()
    request = _experiment_request(candidate_namespace="shadow_meta_model.other")

    with pytest.raises(ShadowExperimentRegistrationError, match="candidate namespace mismatch"):
        registry.register_shadow_experiment(request, _gate_report())


def test_canonical_snapshot_write_is_blocked():
    registry = ShadowExperimentRegistry()
    request = _experiment_request(
        output_contract={
            **_experiment_request().output_contract,
            "writes_canonical_factor_snapshot": True,
        }
    )

    with pytest.raises(ShadowExperimentRegistrationError, match="canonical factor snapshot writes are forbidden"):
        registry.register_shadow_experiment(request, _gate_report())


def test_production_config_write_is_blocked():
    registry = ShadowExperimentRegistry()
    request = _experiment_request(
        output_contract={
            **_experiment_request().output_contract,
            "writes_production_config": True,
        }
    )

    with pytest.raises(ShadowExperimentRegistrationError, match="production config writes are forbidden"):
        registry.register_shadow_experiment(request, _gate_report())


def test_gross_return_primary_output_is_blocked():
    registry = ShadowExperimentRegistry()
    request = _experiment_request(
        output_contract={
            **_experiment_request().output_contract,
            "return_basis": "gross",
        }
    )

    with pytest.raises(ShadowExperimentRegistrationError, match="return_basis must be net"):
        registry.register_shadow_experiment(request, _gate_report())
```

- [ ] **Step 2: Run safety tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p24_experiment_registry.py -q
```

Expected: FAIL because helper functions are still missing.

- [ ] **Step 3: Implement validation helpers**

Append to `agent/research_v1/p24_experiment_registry.py`:

```python
def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ShadowExperimentRegistrationError(message)


def _validate_gate_report(gate_report: ModelAdmissionGateReport) -> None:
    _require(gate_report.schema_version.startswith("p24_gate."), "gate report schema_version must start with p24_gate.")
    _require(gate_report.passed is True, "gate report did not pass")
    _require(gate_report.production_write_blocked is True, "gate report must block production writes")
    _require(not gate_report.blocking_reasons, "gate report has blocking reasons")
    _require(bool(gate_report.candidate_name), "gate report candidate_name is required")
    _require(bool(gate_report.candidate_family), "gate report candidate_family is required")
    _require(bool(gate_report.candidate_namespace), "gate report candidate_namespace is required")


def _validate_request_matches_gate(request: ShadowExperimentRequest, gate_report: ModelAdmissionGateReport) -> None:
    _require(bool(request.experiment_id), "experiment_id is required")
    _require(bool(request.source_gate_report_id), "source_gate_report_id is required")
    _require(request.candidate_name == gate_report.candidate_name, "candidate name mismatch")
    _require(request.candidate_family == gate_report.candidate_family, "candidate family mismatch")
    _require(request.candidate_namespace == gate_report.candidate_namespace, "candidate namespace mismatch")


def _validate_manifest_contracts(request: ShadowExperimentRequest) -> None:
    _validate_input_contract(request.input_contract)
    _validate_output_contract(request)
    _validate_forbidden_outputs(request.forbidden_outputs)
    _validate_training_data_window(request)
    _validate_baseline_plan(request.baseline_comparison_plan)
    _validate_oos_plan(request.out_of_sample_validation_plan)
    _validate_observation_plan(request.observation_plan)
```

- [ ] **Step 4: Implement input/output/forbidden validation**

Append to `agent/research_v1/p24_experiment_registry.py`:

```python
def _validate_input_contract(input_contract: dict) -> None:
    _require(bool(input_contract.get("allowed_sources")), "allowed_sources is required")
    _require(bool(input_contract.get("required_point_in_time_fields")), "required_point_in_time_fields is required")
    _require(input_contract.get("max_source_audit_gap_rate", 1.0) <= 0.20, "max_source_audit_gap_rate must be <= 0.20")
    _require(input_contract.get("lookahead_policy") == "strict_no_future_data", "lookahead_policy must be strict_no_future_data")


def _validate_output_contract(request: ShadowExperimentRequest) -> None:
    output_contract = request.output_contract
    output_namespace = output_contract.get("output_namespace", "")
    _require(output_namespace.startswith(request.candidate_namespace), "output namespace must stay within candidate namespace")
    _require(output_contract.get("writes_canonical_factor_snapshot") is False, "canonical factor snapshot writes are forbidden")
    _require(output_contract.get("writes_production_config") is False, "production config writes are forbidden")
    _require(output_contract.get("affects_live_trading") is False, "live trading effects are forbidden")
    _require(output_contract.get("return_basis") == "net", "return_basis must be net")
    for output in output_contract.get("allowed_outputs", []):
        _require(str(output).startswith(request.candidate_namespace), "allowed outputs must stay within candidate namespace")


def _validate_forbidden_outputs(forbidden_outputs: Iterable[str]) -> None:
    missing = REQUIRED_FORBIDDEN_OUTPUTS.difference(set(forbidden_outputs))
    _require(not missing, f"missing required forbidden outputs: {sorted(missing)}")
```

- [ ] **Step 5: Run safety tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p24_experiment_registry.py -q
```

Expected: FAIL because training/baseline/OOS/observation validators are not implemented.

---

## Task 3: Data Window, Baseline, OOS, and Observation Validation

**Files:**
- Modify: `agent/research_v1/p24_experiment_registry.py`
- Test: `tests/agent/research_v1/test_p24_experiment_registry.py`

- [ ] **Step 1: Add failing contract tests**

Append to `tests/agent/research_v1/test_p24_experiment_registry.py`:

```python
def test_missing_baseline_plan_is_blocked():
    registry = ShadowExperimentRegistry()
    request = _experiment_request(baseline_comparison_plan={})

    with pytest.raises(ShadowExperimentRegistrationError, match="baseline_name is required"):
        registry.register_shadow_experiment(request, _gate_report())


def test_oos_plan_requires_point_in_time_and_embargo_checks():
    registry = ShadowExperimentRegistry()
    request = _experiment_request(
        out_of_sample_validation_plan={
            "method": "walk_forward",
            "walk_forward_enabled": True,
            "holdout_periods": ["2026H1"],
            "leakage_checks": ["point_in_time"],
            "promotion_criteria_documented": True,
        }
    )

    with pytest.raises(ShadowExperimentRegistrationError, match="purged_embargo leakage check is required"):
        registry.register_shadow_experiment(request, _gate_report())


def test_observation_plan_requires_four_windows():
    registry = ShadowExperimentRegistry()
    request = _experiment_request(
        observation_plan={
            "observation_frequency": "weekly",
            "minimum_shadow_windows": 2,
            "required_reports": ["ModelAdmissionGateReport", "ShadowExperimentManifest", "ShadowObservationReport"],
            "revocation_triggers": ["net_underperformance"],
        }
    )

    with pytest.raises(ShadowExperimentRegistrationError, match="minimum_shadow_windows must be >= 4"):
        registry.register_shadow_experiment(request, _gate_report())


def test_required_forbidden_outputs_are_enforced():
    registry = ShadowExperimentRegistry()
    request = _experiment_request(forbidden_outputs=["production_config"])

    with pytest.raises(ShadowExperimentRegistrationError, match="missing required forbidden outputs"):
        registry.register_shadow_experiment(request, _gate_report())
```

- [ ] **Step 2: Run contract tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p24_experiment_registry.py -q
```

Expected: FAIL because validators are missing.

- [ ] **Step 3: Implement remaining validators**

Append to `agent/research_v1/p24_experiment_registry.py`:

```python
def _validate_training_data_window(request: ShadowExperimentRequest) -> None:
    window = request.training_data_window
    _require(bool(window.get("start_date")), "training_data_window.start_date is required")
    _require(bool(window.get("end_date")), "training_data_window.end_date is required")
    minimum_observations = int(window.get("minimum_observations", 0))
    if request.candidate_family == "xgboost_meta_model":
        _require(minimum_observations >= 500, "xgboost minimum_observations must be >= 500")
    else:
        _require(minimum_observations > 0, "minimum_observations must be positive")
    _require(int(window.get("purged_validation_gap_days", 0)) >= 1, "purged_validation_gap_days must be >= 1")
    _require(int(window.get("embargo_days", 0)) >= 1, "embargo_days must be >= 1")
    _require(window.get("point_in_time_membership_required") is True, "point_in_time_membership_required must be true")


def _validate_baseline_plan(plan: dict) -> None:
    _require(bool(plan.get("baseline_name")), "baseline_name is required")
    _require(bool(plan.get("baseline_type")), "baseline_type is required")
    _require(plan.get("primary_metric") in ALLOWED_PRIMARY_METRICS, "primary_metric is not allowed")
    _require(bool(plan.get("secondary_metrics")), "secondary_metrics is required")
    _require(plan.get("comparison_direction") in {"higher_is_better", "lower_is_better"}, "comparison_direction is invalid")
    _require(int(plan.get("minimum_evaluation_windows", 0)) >= 4, "minimum_evaluation_windows must be >= 4")


def _validate_oos_plan(plan: dict) -> None:
    _require(bool(plan.get("method")), "oos method is required")
    _require(plan.get("walk_forward_enabled") is True, "walk_forward_enabled must be true")
    _require(bool(plan.get("holdout_periods")), "holdout_periods is required")
    leakage_checks = set(plan.get("leakage_checks", []))
    _require("point_in_time" in leakage_checks, "point_in_time leakage check is required")
    _require("purged_embargo" in leakage_checks, "purged_embargo leakage check is required")
    _require(plan.get("promotion_criteria_documented") is True, "promotion_criteria_documented must be true")


def _validate_observation_plan(plan: dict) -> None:
    _require(bool(plan.get("observation_frequency")), "observation_frequency is required")
    _require(int(plan.get("minimum_shadow_windows", 0)) >= 4, "minimum_shadow_windows must be >= 4")
    required_reports = set(plan.get("required_reports", []))
    _require("ModelAdmissionGateReport" in required_reports, "ModelAdmissionGateReport is required")
    _require("ShadowExperimentManifest" in required_reports, "ShadowExperimentManifest is required")
    _require("ShadowObservationReport" in required_reports, "ShadowObservationReport is required")
    _require(bool(plan.get("revocation_triggers")), "revocation_triggers is required")
```

- [ ] **Step 4: Run registry tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p24_experiment_registry.py -q
```

Expected: all current tests PASS.

---

## Task 4: Query, Revocation, Archival, and Immutability

**Files:**
- Modify: `agent/research_v1/p24_experiment_registry.py`
- Test: `tests/agent/research_v1/test_p24_experiment_registry.py`

- [ ] **Step 1: Add query and lifecycle tests**

Append to `tests/agent/research_v1/test_p24_experiment_registry.py`:

```python
def test_registered_manifests_are_queryable_by_family():
    registry = ShadowExperimentRegistry()
    xgb_manifest = registry.register_shadow_experiment(_experiment_request(), _gate_report())

    event_report = _gate_report(
        candidate_name="event_surprise_v1",
        candidate_family="llm_event_surprise_factor",
        candidate_namespace="candidate_event.surprise_v1",
        intended_outputs=["candidate_event.surprise_v1.event_surprise_score"],
        event_taxonomy_defined=True,
        label_consistency_score=0.90,
        event_timestamp_policy_defined=True,
        bounded_overlay_preserved=True,
    )
    event_request = _experiment_request(
        experiment_id="exp_event_surprise_v1",
        candidate_id="event_surprise_v1",
        candidate_name="event_surprise_v1",
        candidate_family="llm_event_surprise_factor",
        candidate_namespace="candidate_event.surprise_v1",
        source_gate_report_id="gate_event_surprise_v1",
        output_contract={
            **_experiment_request().output_contract,
            "allowed_outputs": ["candidate_event.surprise_v1.event_surprise_score"],
            "output_namespace": "candidate_event.surprise_v1",
        },
        training_data_window={
            **_experiment_request().training_data_window,
            "minimum_observations": 100,
        },
    )
    event_manifest = registry.register_shadow_experiment(event_request, event_report)

    assert registry.list_active_experiments(candidate_family="xgboost_meta_model") == [xgb_manifest]
    assert registry.list_active_experiments(candidate_family="llm_event_surprise_factor") == [event_manifest]


def test_revocation_preserves_manifest_but_removes_from_active_list():
    registry = ShadowExperimentRegistry()
    original = registry.register_shadow_experiment(_experiment_request(), _gate_report())

    revoked = registry.revoke_experiment("exp_xgb_meta_v1", "source audit gap too high")

    assert original.status == "registered"
    assert revoked.status == "revoked"
    assert "source audit gap too high" in revoked.notes
    assert registry.get_experiment("exp_xgb_meta_v1") == revoked
    assert registry.get_experiment_history("exp_xgb_meta_v1") == [original, revoked]
    assert registry.list_active_experiments() == []


def test_archive_preserves_audit_record():
    registry = ShadowExperimentRegistry()
    registry.register_shadow_experiment(_experiment_request(), _gate_report())

    archived = registry.archive_experiment("exp_xgb_meta_v1", "experiment superseded")

    assert archived.status == "archived"
    assert "experiment superseded" in archived.notes
    assert registry.list_experiments(status="archived") == [archived]
    assert len(registry.get_experiment_history("exp_xgb_meta_v1")) == 2
```

- [ ] **Step 2: Run lifecycle tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p24_experiment_registry.py -q
```

Expected: PASS if Task 1 implementation included query, history, and lifecycle methods. If any test fails, adjust only the registry lifecycle methods; do not weaken validation.

---

## Task 5: No Model Libraries and Regression Bundle

**Files:**
- Test: `tests/agent/research_v1/test_p24_experiment_registry.py`

- [ ] **Step 1: Add no-model-library test**

Append to `tests/agent/research_v1/test_p24_experiment_registry.py`:

```python
def test_registry_module_does_not_import_model_libraries():
    import agent.research_v1.p24_experiment_registry as registry_module

    module_names = set(registry_module.__dict__)
    forbidden_names = {"xgboost", "torch", "tensorflow", "sklearn", "stable_baselines3"}

    assert module_names.isdisjoint(forbidden_names)
```

- [ ] **Step 2: Run P24-B tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p24_experiment_registry.py -q
```

Expected: all P24-B tests PASS.

- [ ] **Step 3: Run P24-A and P24-B tests together**

Run:

```bash
python3.11 -m pytest \
  tests/agent/research_v1/test_p24_entry_gate.py \
  tests/agent/research_v1/test_p24_experiment_registry.py \
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
  -q
```

Expected: all selected tests PASS.

- [ ] **Step 5: Scan for forbidden model imports**

Run:

```bash
grep -R "import xgboost\|from xgboost\|import torch\|from torch\|import tensorflow\|from tensorflow\|stable_baselines\|import sklearn\|from sklearn" -n \
  agent/research_v1/p24_experiment_registry.py \
  tests/agent/research_v1/test_p24_experiment_registry.py || true
```

Expected: no output.

---

## Final Handoff Format

Return:

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
