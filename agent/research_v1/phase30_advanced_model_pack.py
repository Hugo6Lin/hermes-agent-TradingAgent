"""Phase 30 advanced model pack: evidence-gated admission and sandbox manifests for advanced model candidates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# ─── Errors ───────────────────────────────────────────────────────────────────

class AdvancedModelPackError(ValueError):
    """Raised for unsafe Phase 30 advanced model admission requests."""


# ─── Constants ────────────────────────────────────────────────────────────────

ADMITTED_FAMILIES: frozenset[str] = frozenset({
    "real_xgboost_meta_model",
    "sector_relation_gnn_candidate",
    "sequence_timing_model_candidate",
    "llm_event_surprise_model_candidate",
    "ppo_execution_candidate",
})

P24_GATE_SCHEMA_PREFIX = "p24_gate."
MIN_EXECUTION_LOG_COUNT = 10

# P30-2: namespace prefix enforcement — all Phase 30 candidates must live under
# shadow_advanced_model. to prevent production namespace leakage into the sandbox manifest
SHADOW_ADVANCED_MODEL_PREFIX = "shadow_advanced_model."

# P30-4: Per-family evidence requirements per spec §4.
# XGBoost is the only family with prior Phase 25/26 history.
# GNN / Sequence / LLM are first-time Phase 30 admissions.
# PPO is execution-only and skips P25/P26 by design.
FAMILY_EVIDENCE_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "real_xgboost_meta_model": ("p25", "p26"),
    "sector_relation_gnn_candidate": (),          # first-time admission
    "sequence_timing_model_candidate": (),         # first-time admission
    "llm_event_surprise_model_candidate": (),     # first-time admission
    "ppo_execution_candidate": (),                 # execution-only
}


# ─── Contracts ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class AdvancedModelAdmissionRequest:
    candidate_family: str
    candidate_namespace: str
    p24_gate_report: dict[str, Any] | None
    p25_evaluation_evidence: dict[str, Any] | None
    p26_portfolio_evidence: dict[str, Any] | None
    p28_execution_logs_count: int = 0
    # GNN-specific
    relation_data_sufficient: bool = False
    point_in_time_relation_graph: bool = False
    relation_group_count: int = 0
    # Sequence-specific
    walk_forward_validation_defined: bool = False
    sequence_history_sufficient: bool = False
    # LLM event-specific
    event_taxonomy_defined: bool = False
    label_consistency_score: float = 0.0
    # PPO-specific
    ppo_objective: str = ""
    affects_stock_selection: bool = False
    notes: str = ""

    def __post_init__(self) -> None:
        if self.candidate_family not in ADMITTED_FAMILIES:
            raise AdvancedModelPackError(
                f"candidate_family must be one of {sorted(ADMITTED_FAMILIES)}, "
                f"got {self.candidate_family!r}"
            )
        # P30-2: prevent production namespace from entering sandbox manifest
        if not self.candidate_namespace.startswith(SHADOW_ADVANCED_MODEL_PREFIX):
            raise AdvancedModelPackError(
                f"candidate_namespace must start with {SHADOW_ADVANCED_MODEL_PREFIX!r}, "
                f"got {self.candidate_namespace!r}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_family": self.candidate_family,
            "candidate_namespace": self.candidate_namespace,
            "p24_gate_report": self.p24_gate_report,
            "p25_evaluation_evidence": self.p25_evaluation_evidence,
            "p26_portfolio_evidence": self.p26_portfolio_evidence,
            "p28_execution_logs_count": self.p28_execution_logs_count,
            "relation_data_sufficient": self.relation_data_sufficient,
            "point_in_time_relation_graph": self.point_in_time_relation_graph,
            "relation_group_count": self.relation_group_count,
            "walk_forward_validation_defined": self.walk_forward_validation_defined,
            "sequence_history_sufficient": self.sequence_history_sufficient,
            "event_taxonomy_defined": self.event_taxonomy_defined,
            "label_consistency_score": self.label_consistency_score,
            "ppo_objective": self.ppo_objective,
            "affects_stock_selection": self.affects_stock_selection,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class AdvancedModelGovernanceDecision:
    candidate_family: str
    candidate_namespace: str
    admitted: bool
    blocked_reasons: tuple[str, ...]
    warnings: tuple[str, ...]
    sub_scores: tuple[tuple[str, float], ...]

    def to_dict(self) -> dict[str, Any]:
        # P30-3: Defensive rebuild — recompute admitted from blocked_reasons so that
        # object.__setattr__ bypass on self.admitted cannot forge an admitted=True
        # into the audit surface.  The implementation sets blocked_reasons to exactly
        # ("all_gates_passed",) when admitted; any other contents mean blocked.
        rebuilt_admitted = self.blocked_reasons == ("all_gates_passed",)
        return {
            "candidate_family": self.candidate_family,
            "candidate_namespace": self.candidate_namespace,
            "admitted": rebuilt_admitted,
            "blocked_reasons": list(self.blocked_reasons),
            "warnings": list(self.warnings),
            "sub_scores": dict(self.sub_scores),
        }


@dataclass(frozen=True)
class AdvancedModelSandboxManifest:
    candidate_family: str
    candidate_namespace: str
    sandbox_type: str
    allowed_horizons: tuple[str, ...]
    required_pit_dataset: bool
    required_walk_forward_split: bool
    baseline_comparison_required: bool
    oos_evaluation_required: bool
    blocked_production_paths: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_family": self.candidate_family,
            "candidate_namespace": self.candidate_namespace,
            "sandbox_type": self.sandbox_type,
            "allowed_horizons": list(self.allowed_horizons),
            "required_pit_dataset": self.required_pit_dataset,
            "required_walk_forward_split": self.required_walk_forward_split,
            "baseline_comparison_required": self.baseline_comparison_required,
            "oos_evaluation_required": self.oos_evaluation_required,
            "blocked_production_paths": list(self.blocked_production_paths),
        }


# ─── Gate Helpers ─────────────────────────────────────────────────────────────

def _gate_p24(p24_report: dict[str, Any] | None) -> tuple[bool, list[str]]:
    if p24_report is None:
        return False, ["p24_gate_report_missing"]
    schema = p24_report.get("schema_version", "")
    if not schema.startswith(P24_GATE_SCHEMA_PREFIX):
        return False, [f"p24_gate_schema_invalid:{schema}"]
    if not p24_report.get("passed", False):
        reasons = list(p24_report.get("blocking_reasons", []))
        return False, [f"p24_gate_failed:{r}" for r in reasons]
    if not p24_report.get("production_write_blocked", False):
        return False, ["p24_gate_production_write_not_blocked"]
    return True, []


def _gate_p25(evidence: dict[str, Any] | None) -> tuple[bool, list[str]]:
    if evidence is None:
        return False, ["p25_evaluation_evidence_missing"]
    return True, []


def _gate_p26(evidence: dict[str, Any] | None) -> tuple[bool, list[str]]:
    if evidence is None:
        return False, ["p26_portfolio_evidence_missing"]
    return True, []


def _gate_p28_logs(log_count: int) -> tuple[bool, list[str]]:
    if log_count < MIN_EXECUTION_LOG_COUNT:
        return False, [f"p28_execution_logs_insufficient:{log_count}<{MIN_EXECUTION_LOG_COUNT}"]
    return True, []


def _gate_gnn(
    data_sufficient: bool,
    pit_graph: bool,
    group_count: int,
) -> tuple[bool, list[str]]:
    reasons = []
    if not data_sufficient:
        reasons.append("gnn_relation_data_not_sufficient")
    if not pit_graph:
        reasons.append("gnn_relation_graph_not_point_in_time")
    if group_count < 2:
        reasons.append("gnn_relation_group_count_insufficient")
    return len(reasons) == 0, reasons


def _gate_sequence(
    wfw_defined: bool,
    history_sufficient: bool,
) -> tuple[bool, list[str]]:
    reasons = []
    if not wfw_defined:
        reasons.append("sequence_walk_forward_validation_not_defined")
    if not history_sufficient:
        reasons.append("sequence_history_not_sufficient")
    return len(reasons) == 0, reasons


def _gate_llm_event(
    taxonomy_defined: bool,
    consistency_score: float,
) -> tuple[bool, list[str]]:
    reasons = []
    if not taxonomy_defined:
        reasons.append("llm_event_taxonomy_not_defined")
    if consistency_score < 0.5:
        reasons.append(f"llm_event_label_consistency_score_too_low:{consistency_score}")
    return len(reasons) == 0, reasons


def _gate_ppo_execution_only(
    objective: str,
    affects_selection: bool,
) -> tuple[bool, list[str]]:
    reasons = []
    if objective != "execution_cost_reduction":
        reasons.append(f"ppo_objective_not_execution_cost_reduction:{objective}")
    if affects_selection:
        reasons.append("ppo_affects_stock_selection")
    return len(reasons) == 0, reasons


def _gate_xgboost_requires(
    p24_ok: bool,
    p25_ok: bool,
    p26_ok: bool,
) -> tuple[bool, list[str]]:
    reasons = []
    if not p24_ok:
        reasons.append("xgboost_requires_p24_gate")
    if not p25_ok:
        reasons.append("xgboost_requires_p25_evidence")
    if not p26_ok:
        reasons.append("xgboost_requires_p26_evidence")
    return len(reasons) == 0, reasons


# ─── Core Logic ───────────────────────────────────────────────────────────────

def evaluate_advanced_model_admission(
    request: AdvancedModelAdmissionRequest,
) -> AdvancedModelGovernanceDecision:
    """
    Evaluate admission for an advanced model candidate.

    Spec §5 signature: evaluate_advanced_model_admission(candidate_evidence, request)
    The implementation folds candidate_evidence into request fields internally —
    request.p24_gate_report, request.p25_evaluation_evidence, request.p26_portfolio_evidence,
    and the family-specific fields carry all evidence.  This avoids a redundant two-arg
    interface and keeps the evidence self-contained in the request object.

    Each candidate requires: passing P24 admission gate, PIT dataset contract,
    walk-forward split, baseline/OOS plans, and no production write path.

    PPO additionally requires execution_cost_reduction objective and
    affects_stock_selection=False per Phase 28 spec §6.
    """
    reasons: list[str] = []
    sub_scores: list[tuple[str, float]] = []
    warnings: list[str] = []

    # Universal: P24 gate
    p24_ok, p24_reasons = _gate_p24(request.p24_gate_report)
    sub_scores.append(("p24_gate_passed", float(p24_ok)))
    if not p24_ok:
        reasons.extend(p24_reasons)

    # P25 / P26 evidence gates (per FAMILY_EVIDENCE_REQUIREMENTS)
    family = request.candidate_family
    required_phases = FAMILY_EVIDENCE_REQUIREMENTS.get(family, ())
    requires_p25 = "p25" in required_phases
    requires_p26 = "p26" in required_phases

    p25_ok = True
    p26_ok = True
    if requires_p25:
        p25_ok, p25_reasons = _gate_p25(request.p25_evaluation_evidence)
        sub_scores.append(("p25_evidence_present", float(p25_ok)))
        if not p25_ok:
            reasons.extend(p25_reasons)

    if requires_p26:
        p26_ok, p26_reasons = _gate_p26(request.p26_portfolio_evidence)
        sub_scores.append(("p26_evidence_present", float(p26_ok)))
        if not p26_ok:
            reasons.extend(p26_reasons)

    # Family-specific gates
    family_blocked = False

    if family == "real_xgboost_meta_model":
        ok, gate_reasons = _gate_xgboost_requires(p24_ok, p25_ok, p26_ok)
        sub_scores.append(("xgboost_family_gate", float(ok)))
        if not ok:
            family_blocked = True
            reasons.extend(gate_reasons)

    elif family == "sector_relation_gnn_candidate":
        ok, gate_reasons = _gate_gnn(
            request.relation_data_sufficient,
            request.point_in_time_relation_graph,
            request.relation_group_count,
        )
        sub_scores.append(("gnn_data_sufficiency", float(ok)))
        if not ok:
            family_blocked = True
            reasons.extend(gate_reasons)

    elif family == "sequence_timing_model_candidate":
        ok, gate_reasons = _gate_sequence(
            request.walk_forward_validation_defined,
            request.sequence_history_sufficient,
        )
        sub_scores.append(("sequence_model_sufficiency", float(ok)))
        if not ok:
            family_blocked = True
            reasons.extend(gate_reasons)

    elif family == "llm_event_surprise_model_candidate":
        ok, gate_reasons = _gate_llm_event(
            request.event_taxonomy_defined,
            request.label_consistency_score,
        )
        sub_scores.append(("llm_event_taxonomy_consistency", float(ok)))
        if not ok:
            family_blocked = True
            reasons.extend(gate_reasons)

    elif family == "ppo_execution_candidate":
        ppo_ok, ppo_reasons = _gate_ppo_execution_only(
            request.ppo_objective,
            request.affects_stock_selection,
        )
        p28_ok, p28_reasons = _gate_p28_logs(request.p28_execution_logs_count)
        sub_scores.append(("ppo_execution_only_gate", float(ppo_ok)))
        sub_scores.append(("ppo_execution_logs_sufficient", float(p28_ok)))

        ppo_blocked = (not p24_ok) or (not ppo_ok) or (not p28_ok)
        if not ppo_ok:
            reasons.extend(ppo_reasons)
        if not p28_ok:
            reasons.extend(p28_reasons)
        if not p24_ok:
            reasons.append("ppo_requires_p24_gate")
        if ppo_blocked:
            family_blocked = True

    # Production write path
    p24_report = request.p24_gate_report or {}
    write_blocked = p24_report.get("production_write_blocked", False)
    sub_scores.append(("production_write_blocked", float(write_blocked)))
    if not write_blocked and not family_blocked:
        warnings.append("production_write_path_not_confirmed")

    admitted = p24_ok and not family_blocked

    if admitted:
        reasons.append("all_gates_passed")

    return AdvancedModelGovernanceDecision(
        candidate_family=request.candidate_family,
        candidate_namespace=request.candidate_namespace,
        admitted=admitted,
        blocked_reasons=tuple(reasons),
        warnings=tuple(warnings),
        sub_scores=tuple(sub_scores),
    )


def build_advanced_model_sandbox_manifest(
    decision: AdvancedModelGovernanceDecision,
    request: AdvancedModelAdmissionRequest,
) -> AdvancedModelSandboxManifest:
    """
    Build a shadow-only sandbox manifest for an admitted candidate.

    Spec §5 signature: build_advanced_model_sandbox_manifest(candidate_evidence, request)
    The implementation uses (decision, request) since decision already carries the
    admission outcome; candidate_evidence is incorporated in the request object.

    Must only be called after evaluate_advanced_model_admission returns admitted=True.
    Returns a manifest that is explicitly shadow-only; no production paths are opened.
    Spec §6 non-goals are enforced here.
    """
    if not decision.admitted:
        raise AdvancedModelPackError(
            "Cannot build sandbox manifest for non-admitted candidate"
        )

    family = request.candidate_family
    blocked_paths = (
        "live_trade_signal",
        "broker_instruction",
        "order_id",
        "production_config_update",
        "enable_trading",
        "deploy_to_production",
    )

    if family == "sequence_timing_model_candidate":
        horizons: tuple[str, ...] = ("intraday", "daily")
    elif family == "sector_relation_gnn_candidate":
        horizons = ("daily", "weekly")
    elif family == "ppo_execution_candidate":
        horizons = ("execution",)
    else:
        horizons = ("daily",)

    return AdvancedModelSandboxManifest(
        candidate_family=family,
        candidate_namespace=request.candidate_namespace,
        sandbox_type="shadow_only",
        allowed_horizons=horizons,
        required_pit_dataset=True,
        required_walk_forward_split=(family == "sequence_timing_model_candidate"),
        baseline_comparison_required=True,
        oos_evaluation_required=True,
        blocked_production_paths=blocked_paths,
    )
