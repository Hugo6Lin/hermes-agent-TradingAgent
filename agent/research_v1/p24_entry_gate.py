"""P24 model/factor admission gate evaluator."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone


ALLOWED_NAMESPACES = (
    "candidate_macro.",
    "candidate_event.",
    "candidate_relation.",
    "candidate_timing_sequence.",
    "shadow_meta_model.",
    "candidate_execution.",
    "shadow_execution.",
)


@dataclass(frozen=True)
class P24CandidateRequest:
    candidate_name: str
    candidate_family: str
    candidate_namespace: str
    requested_phase: str
    intended_outputs: list[str]
    uses_point_in_time_sources: bool
    source_audit_plan_defined: bool
    simple_baseline_defined: bool
    out_of_sample_plan_defined: bool
    uses_gross_returns_as_primary: bool
    writes_production_fields: bool
    requires_portfolio_layer: bool
    requires_execution_data: bool
    notes: str = ""
    # XGBoost-specific
    residualization_plan_defined: bool = False
    # LLM event surprise factor
    event_taxonomy_defined: bool = False
    label_consistency_score: float = 0.0
    event_timestamp_policy_defined: bool = False
    bounded_overlay_preserved: bool = False
    # Macro regime factor
    macro_source_point_in_time: bool = False
    feature_frequency_matches_horizon: bool = False
    forward_fill_policy_defined: bool = False
    exploratory_mode: bool = False
    # Relation model
    point_in_time_relation_graph: bool = False
    relation_group_count: int = 0
    average_tickers_per_group: float = 0.0
    simple_relation_baseline_tested: bool = False
    # Sequence timing model
    timing_factor_weak_or_unstable: bool = False
    simple_timing_baselines_tested: bool = False
    walk_forward_validation_defined: bool = False
    sequence_history_sufficient: bool = False
    # PPO execution model
    ppo_objective: str = ""
    affects_stock_selection: bool = False


@dataclass(frozen=True)
class P24SystemEvidence:
    p20_accepted: bool
    p21_accepted: bool
    p22_accepted: bool
    p23_accepted: bool
    return_basis_default: str
    lookahead_violation_rate: float
    source_audit_gap_rate: float
    ready_for_p24_gate: bool
    ready_factor_count: int
    core_factors_with_net_icir_gt_030: int
    ready_factor_horizon_count: int
    max_abs_cross_factor_correlation: float
    independent_cross_sectional_observations: int
    regime_gate_has_return_separation: bool
    portfolio_layer_exists: bool
    execution_dataset_exists: bool


@dataclass(frozen=True)
class ModelAdmissionGateReport:
    schema_version: str
    candidate_name: str
    candidate_family: str
    candidate_namespace: str
    requested_phase: str
    universal_gate_status: str
    model_specific_gate_status: str
    passed: bool
    blocking_reasons: list[str]
    warnings: list[str]
    required_evidence: dict
    available_evidence: dict
    simple_baseline_defined: bool
    point_in_time_status: str
    shadow_only_confirmed: bool
    production_write_blocked: bool
    reviewer_notes: str
    generated_at: str

    def to_dict(self) -> dict:
        return asdict(self)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _namespace_allowed(namespace: str) -> bool:
    return namespace.startswith(ALLOWED_NAMESPACES)


def _evaluate_universal_gate(request: P24CandidateRequest, evidence: P24SystemEvidence) -> list[str]:
    reasons = []
    if not evidence.p20_accepted:
        reasons.append("p20_not_accepted")
    if not evidence.p21_accepted:
        reasons.append("p21_not_accepted")
    if not evidence.p22_accepted:
        reasons.append("p22_not_accepted")
    if not evidence.p23_accepted:
        reasons.append("p23_not_accepted")
    if evidence.return_basis_default != "net":
        reasons.append("return_basis_not_net")
    if evidence.lookahead_violation_rate > 0.0:
        reasons.append("lookahead_violations_present")
    if evidence.source_audit_gap_rate > 0.20:
        reasons.append("source_audit_gap_too_high")
    if not evidence.ready_for_p24_gate:
        reasons.append("ready_for_p24_gate_false")
    if not _namespace_allowed(request.candidate_namespace):
        reasons.append("candidate_namespace_not_allowed")
    if request.writes_production_fields:
        reasons.append("writes_production_fields")
    if not request.uses_point_in_time_sources:
        reasons.append("missing_point_in_time_sources")
    if not request.source_audit_plan_defined:
        reasons.append("source_audit_plan_missing")
    if not request.simple_baseline_defined:
        reasons.append("simple_baseline_missing")
    if not request.out_of_sample_plan_defined:
        reasons.append("out_of_sample_plan_missing")
    if request.uses_gross_returns_as_primary:
        reasons.append("uses_gross_returns_as_primary")
    return reasons


def _evaluate_specific_gate(request: P24CandidateRequest, evidence: P24SystemEvidence) -> tuple[list[str], list[str]]:
    reasons = []
    warnings = []
    family = request.candidate_family
    namespace = request.candidate_namespace

    if family == "xgboost_meta_model":
        if not namespace.startswith("shadow_meta_model."):
            reasons.append("xgboost_namespace_invalid")
        if evidence.core_factors_with_net_icir_gt_030 < 3:
            reasons.append("xgboost_needs_three_core_factors")
        if evidence.ready_factor_horizon_count < 2:
            reasons.append("xgboost_needs_two_ready_factor_horizons")
        if evidence.max_abs_cross_factor_correlation >= 0.70 and not request.residualization_plan_defined:
            reasons.append("xgboost_factor_correlation_too_high")
        if evidence.independent_cross_sectional_observations < 500:
            reasons.append("xgboost_insufficient_observations")
    elif family == "llm_event_surprise_factor":
        if not namespace.startswith("candidate_event."):
            reasons.append("event_namespace_invalid")
        if not request.event_taxonomy_defined:
            reasons.append("event_taxonomy_missing")
        if request.label_consistency_score < 0.80:
            reasons.append("event_label_consistency_too_low")
        if not request.event_timestamp_policy_defined:
            reasons.append("event_timestamp_policy_missing")
        if not request.bounded_overlay_preserved:
            reasons.append("event_bounded_overlay_not_preserved")
    elif family == "macro_regime_factor":
        if not namespace.startswith("candidate_macro."):
            reasons.append("macro_namespace_invalid")
        if not request.macro_source_point_in_time:
            reasons.append("macro_source_not_point_in_time")
        if not request.feature_frequency_matches_horizon:
            reasons.append("macro_feature_frequency_mismatch")
        if not request.forward_fill_policy_defined:
            reasons.append("macro_forward_fill_policy_missing")
        if not evidence.regime_gate_has_return_separation and not request.exploratory_mode:
            reasons.append("macro_needs_return_separation_or_exploratory")
    elif family == "relation_model":
        if not namespace.startswith("candidate_relation."):
            reasons.append("relation_namespace_invalid")
        if not request.point_in_time_relation_graph:
            reasons.append("relation_graph_not_point_in_time")
        if request.relation_group_count <= 15:
            reasons.append("relation_insufficient_groups")
        if request.average_tickers_per_group <= 10.0:
            reasons.append("relation_tickers_per_group_too_low")
        if not request.simple_relation_baseline_tested:
            reasons.append("relation_baseline_not_tested")
    elif family == "sequence_timing_model":
        if not namespace.startswith("candidate_timing_sequence."):
            reasons.append("sequence_namespace_invalid")
        if not request.timing_factor_weak_or_unstable:
            reasons.append("sequence_timing_factor_not_weak")
        if not request.simple_timing_baselines_tested:
            reasons.append("sequence_baselines_not_tested")
        if not request.walk_forward_validation_defined:
            reasons.append("sequence_walk_forward_not_defined")
        if not request.sequence_history_sufficient:
            reasons.append("sequence_history_insufficient")
    elif family == "ppo_execution_model":
        if not (namespace.startswith("candidate_execution.") or namespace.startswith("shadow_execution.")):
            reasons.append("ppo_namespace_invalid")
        if request.ppo_objective != "execution_cost_reduction":
            reasons.append("ppo_objective_must_be_execution_cost_reduction")
        if request.affects_stock_selection:
            reasons.append("ppo_cannot_affect_stock_selection")
        if not evidence.portfolio_layer_exists:
            reasons.append("ppo_portfolio_layer_missing")
        if not evidence.execution_dataset_exists:
            reasons.append("ppo_execution_dataset_missing")
    else:
        reasons.append("unsupported_candidate_family")
    return reasons, warnings


def evaluate_p24_entry_gate(
    request: P24CandidateRequest,
    evidence: P24SystemEvidence,
) -> ModelAdmissionGateReport:
    universal_reasons = _evaluate_universal_gate(request, evidence)
    specific_reasons, warnings = _evaluate_specific_gate(request, evidence)
    blocking_reasons = universal_reasons + specific_reasons
    passed = not blocking_reasons
    return ModelAdmissionGateReport(
        schema_version="p24_gate.0",
        candidate_name=request.candidate_name,
        candidate_family=request.candidate_family,
        candidate_namespace=request.candidate_namespace,
        requested_phase=request.requested_phase,
        universal_gate_status="pass" if not universal_reasons else "fail",
        model_specific_gate_status="pass" if not specific_reasons else "fail",
        passed=passed,
        blocking_reasons=blocking_reasons,
        warnings=warnings,
        required_evidence={
            "return_basis_default": "net",
            "ready_for_p24_gate": True,
            "point_in_time_sources": True,
            "simple_baseline": True,
            "out_of_sample_plan": True,
        },
        available_evidence=evidence.__dict__,
        simple_baseline_defined=request.simple_baseline_defined,
        point_in_time_status="defined" if request.uses_point_in_time_sources else "missing",
        shadow_only_confirmed=not request.writes_production_fields,
        production_write_blocked=True,
        reviewer_notes=request.notes,
        generated_at=_utc_now(),
    )
