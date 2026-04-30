"""Signal-family governance readiness dossier for Hermes candidates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class SignalFamilyReadinessError(ValueError):
    """Raised for unsafe or invalid signal-family readiness inputs."""


ALLOWED_FAMILY_TYPES: frozenset[str] = frozenset({
    "factor_family",
    "signal_family",
    "shadow_model_family",
    "advanced_model_candidate",
})

ALLOWED_PARENT_READY_STATUSES: frozenset[str] = frozenset({"ready_for_human_review"})

ALLOWED_FAMILY_STATUSES: frozenset[str] = frozenset({
    "blocked_system_not_ready",
    "blocked_missing_family_evidence",
    "shadow_observation_only",
    "ready_for_human_review",
})

ALLOWED_NEXT_STEPS: frozenset[str] = frozenset({
    "collect_more_evidence",
    "continue_shadow_observation",
    "prepare_human_review",
    "reject_for_now",
})


@dataclass(frozen=True)
class FamilyEvidence:
    p20_p23_present: bool
    p24_p26_present: bool = False
    p28_present: bool = False
    p30_present: bool = False
    maturity: bool = False
    edge_summary: str = ""
    risk_summary: str = ""
    degradation_warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "p20_p23_present": self.p20_p23_present,
            "p24_p26_present": self.p24_p26_present,
            "p28_present": self.p28_present,
            "p30_present": self.p30_present,
            "maturity": self.maturity,
            "edge_summary": self.edge_summary,
            "risk_summary": self.risk_summary,
            "degradation_warnings": list(self.degradation_warnings),
        }


@dataclass(frozen=True)
class SignalFamilyReadinessRequest:
    parent_version_status: str
    family_type: str
    family_namespace: str
    evidence: FamilyEvidence
    notes: str = ""

    def __post_init__(self) -> None:
        if self.family_type not in ALLOWED_FAMILY_TYPES:
            raise SignalFamilyReadinessError(
                f"family_type must be one of {sorted(ALLOWED_FAMILY_TYPES)}, got {self.family_type!r}"
            )
        if not self.family_namespace.strip():
            raise SignalFamilyReadinessError("family_namespace must be non-empty")


@dataclass(frozen=True)
class SignalFamilyReadinessDossier:
    family_status: str
    parent_version_status: str
    family_type: str
    family_namespace: str
    edge_evidence_summary: str
    risk_evidence_summary: str
    degradation_warnings: tuple[str, ...]
    promotion_forbidden_reasons: tuple[str, ...]
    allowed_next_step: str
    human_review_questions: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.family_status not in ALLOWED_FAMILY_STATUSES:
            raise SignalFamilyReadinessError(
                f"family_status must be one of {sorted(ALLOWED_FAMILY_STATUSES)}, got {self.family_status!r}"
            )
        if self.allowed_next_step not in ALLOWED_NEXT_STEPS:
            raise SignalFamilyReadinessError(
                f"allowed_next_step must be one of {sorted(ALLOWED_NEXT_STEPS)}, got {self.allowed_next_step!r}"
            )

    def to_dict(self) -> dict[str, Any]:
        if self.parent_version_status not in ALLOWED_PARENT_READY_STATUSES:
            rebuilt_status = "blocked_system_not_ready"
        elif any(r.endswith("_missing") for r in self.promotion_forbidden_reasons):
            rebuilt_status = "blocked_missing_family_evidence"
        elif self.allowed_next_step == "continue_shadow_observation":
            rebuilt_status = "shadow_observation_only"
        else:
            rebuilt_status = "ready_for_human_review"

        return {
            "family_status": rebuilt_status,
            "parent_version_status": self.parent_version_status,
            "family_type": self.family_type,
            "family_namespace": self.family_namespace,
            "edge_evidence_summary": self.edge_evidence_summary,
            "risk_evidence_summary": self.risk_evidence_summary,
            "degradation_warnings": list(self.degradation_warnings),
            "promotion_forbidden_reasons": list(self.promotion_forbidden_reasons),
            "allowed_next_step": self.allowed_next_step,
            "human_review_questions": list(self.human_review_questions),
        }


def build_signal_family_readiness_dossier(
    request: SignalFamilyReadinessRequest,
) -> SignalFamilyReadinessDossier:
    forbidden: list[str] = []
    questions: list[str] = []

    if request.parent_version_status not in ALLOWED_PARENT_READY_STATUSES:
        forbidden.append(f"parent_version_not_ready:{request.parent_version_status}")
        return SignalFamilyReadinessDossier(
            family_status="blocked_system_not_ready",
            parent_version_status=request.parent_version_status,
            family_type=request.family_type,
            family_namespace=request.family_namespace,
            edge_evidence_summary=request.evidence.edge_summary,
            risk_evidence_summary=request.evidence.risk_summary,
            degradation_warnings=request.evidence.degradation_warnings,
            promotion_forbidden_reasons=tuple(forbidden),
            allowed_next_step="reject_for_now",
            human_review_questions=("Review system version blockers before family review.",),
        )

    if not request.evidence.p20_p23_present:
        forbidden.append("p20_p23_family_evidence_missing")

    if request.family_type == "shadow_model_family" and not request.evidence.p24_p26_present:
        forbidden.append("p24_p26_shadow_model_evidence_missing")

    if request.family_type == "advanced_model_candidate":
        if not request.evidence.p30_present:
            forbidden.append("p30_advanced_model_admission_missing")
        forbidden.append("advanced_model_remains_sandbox_only")

    blocking_missing = [reason for reason in forbidden if reason.endswith("_missing")]
    if blocking_missing:
        status = "blocked_missing_family_evidence"
        next_step = "collect_more_evidence"
    elif not request.evidence.maturity:
        status = "shadow_observation_only"
        next_step = "continue_shadow_observation"
    else:
        status = "ready_for_human_review"
        next_step = "prepare_human_review"
        questions.append("Does the human reviewer accept the evidence maturity claim?")

    if request.family_type in {"shadow_model_family", "advanced_model_candidate"}:
        if "shadow_outputs_must_not_promote_to_production" not in forbidden:
            forbidden.append("shadow_outputs_must_not_promote_to_production")

    return SignalFamilyReadinessDossier(
        family_status=status,
        parent_version_status=request.parent_version_status,
        family_type=request.family_type,
        family_namespace=request.family_namespace,
        edge_evidence_summary=request.evidence.edge_summary,
        risk_evidence_summary=request.evidence.risk_summary,
        degradation_warnings=request.evidence.degradation_warnings,
        promotion_forbidden_reasons=tuple(forbidden),
        allowed_next_step=next_step,
        human_review_questions=tuple(questions),
    )
