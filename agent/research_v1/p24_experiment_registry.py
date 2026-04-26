"""P24-B shadow experiment registry.

This module registers auditable shadow experiment manifests for candidates
that already passed the P24 entry gate. It does not train models, write
canonical factor snapshots, or mutate production configuration.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from types import MappingProxyType
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
        return {
            "schema_version": self.schema_version,
            "experiment_id": self.experiment_id,
            "candidate_id": self.candidate_id,
            "candidate_name": self.candidate_name,
            "candidate_family": self.candidate_family,
            "candidate_namespace": self.candidate_namespace,
            "source_gate_report_id": self.source_gate_report_id,
            "source_gate_schema_version": self.source_gate_schema_version,
            "status": self.status,
            "owner": self.owner,
            "purpose": self.purpose,
            "input_contract": _thaw(self.input_contract),
            "output_contract": _thaw(self.output_contract),
            "forbidden_outputs": _thaw(self.forbidden_outputs),
            "training_data_window": _thaw(self.training_data_window),
            "point_in_time_policy": _thaw(self.point_in_time_policy),
            "baseline_comparison_plan": _thaw(self.baseline_comparison_plan),
            "out_of_sample_validation_plan": _thaw(self.out_of_sample_validation_plan),
            "observation_plan": _thaw(self.observation_plan),
            "resource_policy": _thaw(self.resource_policy),
            "expected_artifacts": _thaw(self.expected_artifacts),
            "promotion_blocked": self.promotion_blocked,
            "production_write_blocked": self.production_write_blocked,
            "canonical_snapshot_write_blocked": self.canonical_snapshot_write_blocked,
            "shadow_namespace": self.shadow_namespace,
            "gate_warnings": _thaw(self.gate_warnings),
            "blocking_reasons": _thaw(self.blocking_reasons),
            "registered_at": self.registered_at,
            "notes": self.notes,
        }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _freeze(obj):
    """Recursively freeze a dict/list structure into immutable MappingProxyType/tuple."""
    if isinstance(obj, dict):
        return MappingProxyType({k: _freeze(v) for k, v in obj.items()})
    elif isinstance(obj, list):
        return tuple(_freeze(item) for item in obj)
    else:
        return obj


def _thaw(obj):
    """Recursively thaw frozen nested structures back into plain dict/list for serialization."""
    if isinstance(obj, MappingProxyType):
        return {k: _thaw(v) for k, v in obj.items()}
    elif isinstance(obj, tuple) and not isinstance(obj, str):
        return [_thaw(item) for item in obj]
    else:
        return obj


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


def _validate_manifest_contracts(request: ShadowExperimentRequest) -> None:
    _validate_input_contract(request.input_contract)
    _validate_output_contract(request)
    _validate_forbidden_outputs(request.forbidden_outputs)
    _validate_training_data_window(request)
    _validate_baseline_plan(request.baseline_comparison_plan)
    _validate_oos_plan(request.out_of_sample_validation_plan)
    _validate_observation_plan(request.observation_plan)


class ShadowExperimentRegistry:
    def __init__(self) -> None:
        self._manifests: dict[str, ShadowExperimentManifest] = {}
        self._history: dict[str, list[ShadowExperimentManifest]] = {}

    def register_shadow_experiment(
        self,
        request: ShadowExperimentRequest,
        gate_report: ModelAdmissionGateReport,
    ) -> ShadowExperimentManifest:
        if request.experiment_id in self._manifests or request.experiment_id in self._history:
            raise ShadowExperimentRegistrationError(
                f"experiment_id '{request.experiment_id}' is already registered "
                f"(active or in history); use a new experiment_id for re-registration"
            )
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
            input_contract=_freeze(dict(request.input_contract)),
            output_contract=_freeze(dict(request.output_contract)),
            forbidden_outputs=_freeze(list(request.forbidden_outputs)),
            training_data_window=_freeze(dict(request.training_data_window)),
            point_in_time_policy=_freeze(dict(request.point_in_time_policy)),
            baseline_comparison_plan=_freeze(dict(request.baseline_comparison_plan)),
            out_of_sample_validation_plan=_freeze(dict(request.out_of_sample_validation_plan)),
            observation_plan=_freeze(dict(request.observation_plan)),
            resource_policy=_freeze(dict(request.resource_policy)),
            expected_artifacts=_freeze(list(request.expected_artifacts)),
            promotion_blocked=True,
            production_write_blocked=True,
            canonical_snapshot_write_blocked=True,
            shadow_namespace=request.output_contract["output_namespace"],
            gate_warnings=_freeze(list(gate_report.warnings)),
            blocking_reasons=(),
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
