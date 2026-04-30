"""Phase 29 production adoption review pack: human-review-only adoption dossier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# ─── Errors ───────────────────────────────────────────────────────────────────

class ProductionAdoptionError(ValueError):
    """Raised for unsafe Phase 29 adoption review requests."""


# ─── Constants ────────────────────────────────────────────────────────────────

REQUIRED_PHASE_IDS: tuple[str, ...] = (
    "P20",
    "P21",
    "P22",
    "P23",
    "P24",
    "P25",
    "P26",
    "P28",
)

ALLOWED_STATUSES: frozenset[str] = frozenset({
    "blocked_missing_evidence",
    "blocked_risk_controls_incomplete",
    "ready_for_human_review",
})


# ─── Contracts ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class RollbackPlan:
    rollback_owner: str
    rollback_trigger: str
    description: str

    def __post_init__(self) -> None:
        if not self.rollback_owner.strip():
            raise ProductionAdoptionError("rollback_owner must be non-empty (whitespace-only rejected)")
        if not self.rollback_trigger.strip():
            raise ProductionAdoptionError("rollback_trigger must be non-empty (whitespace-only rejected)")
        if not self.description.strip():
            raise ProductionAdoptionError("description must be non-empty (whitespace-only rejected)")

    def to_dict(self) -> dict[str, Any]:
        return {
            "rollback_owner": self.rollback_owner,
            "rollback_trigger": self.rollback_trigger,
            "description": self.description,
        }


@dataclass(frozen=True)
class MonitoringSLA:
    monitoring_cadence: str
    alert_routing: str
    description: str

    def __post_init__(self) -> None:
        if not self.monitoring_cadence.strip():
            raise ProductionAdoptionError("monitoring_cadence must be non-empty (whitespace-only rejected)")
        if not self.alert_routing.strip():
            raise ProductionAdoptionError("alert_routing must be non-empty (whitespace-only rejected)")
        if not self.description.strip():
            raise ProductionAdoptionError("description must be non-empty (whitespace-only rejected)")

    def to_dict(self) -> dict[str, Any]:
        return {
            "monitoring_cadence": self.monitoring_cadence,
            "alert_routing": self.alert_routing,
            "description": self.description,
        }


@dataclass(frozen=True)
class VersionFreezeProposal:
    frozen_version: str
    freeze_scope: str
    thaw_conditions: str

    def __post_init__(self) -> None:
        if not self.frozen_version.strip():
            raise ProductionAdoptionError("frozen_version must be non-empty (whitespace-only rejected)")
        if not self.freeze_scope.strip():
            raise ProductionAdoptionError("freeze_scope must be non-empty (whitespace-only rejected)")

    def to_dict(self) -> dict[str, Any]:
        return {
            "frozen_version": self.frozen_version,
            "freeze_scope": self.freeze_scope,
            "thaw_conditions": self.thaw_conditions,
        }


@dataclass(frozen=True)
class EvidenceChecklist:
    evidence_present_by_phase: tuple[tuple[str, bool], ...]
    missing_phase_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_present_by_phase": dict(self.evidence_present_by_phase),
            "missing_phase_ids": list(self.missing_phase_ids),
        }


@dataclass(frozen=True)
class ProductionAdoptionDossier:
    status: str
    evidence_checklist: EvidenceChecklist
    rollback_plan: RollbackPlan | None
    monitoring_sla: MonitoringSLA | None
    version_freeze_proposal: VersionFreezeProposal | None
    decision_reasons: tuple[str, ...]
    warnings: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.status not in ALLOWED_STATUSES:
            raise ProductionAdoptionError(
                f"status must be one of {sorted(ALLOWED_STATUSES)}, got {self.status!r}"
            )

    def to_dict(self) -> dict[str, Any]:
        # P29-4: Defensive rebuild — recompute status from gate fields so that
        # object.__setattr__ bypass on self.status cannot forge a value through
        # the audit surface.  Human reviewers reading the JSON must see the
        # truth derived from evidence + controls, not a potentially-tampered field.
        evidence_complete = len(self.evidence_checklist.missing_phase_ids) == 0
        controls_complete = (
            self.rollback_plan is not None
            and self.monitoring_sla is not None
        )
        if not evidence_complete:
            rebuilt_status = "blocked_missing_evidence"
        elif not controls_complete:
            rebuilt_status = "blocked_risk_controls_incomplete"
        else:
            rebuilt_status = "ready_for_human_review"

        return {
            "status": rebuilt_status,
            "evidence_checklist": self.evidence_checklist.to_dict(),
            "rollback_plan": self.rollback_plan.to_dict() if self.rollback_plan else None,
            "monitoring_sla": self.monitoring_sla.to_dict() if self.monitoring_sla else None,
            "version_freeze_proposal": self.version_freeze_proposal.to_dict() if self.version_freeze_proposal else None,
            "decision_reasons": list(self.decision_reasons),
            "warnings": list(self.warnings),
        }


# P29-2: evidence_bundle is a function-parameter concern only.
# ProductionAdoptionReviewRequest carries the plan metadata but NOT evidence,
# which is passed as a separate argument to build_production_adoption_dossier.
@dataclass(frozen=True)
class ProductionAdoptionReviewRequest:
    rollback_plan: RollbackPlan | None = None
    monitoring_sla: MonitoringSLA | None = None
    version_freeze_proposal: VersionFreezeProposal | None = None
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "rollback_plan": self.rollback_plan.to_dict() if self.rollback_plan else None,
            "monitoring_sla": self.monitoring_sla.to_dict() if self.monitoring_sla else None,
            "version_freeze_proposal": self.version_freeze_proposal.to_dict() if self.version_freeze_proposal else None,
            "notes": self.notes,
        }


# ─── Core Logic ───────────────────────────────────────────────────────────────

def build_production_adoption_dossier(
    evidence_bundle: tuple[tuple[str, dict[str, Any]], ...],
    request: ProductionAdoptionReviewRequest,
) -> ProductionAdoptionDossier:
    """
    Assemble a human-review production adoption dossier.

    Does NOT approve production. Output is for human review only (spec §3).
    No production state is written by this function.
    """
    evidence_map = dict(evidence_bundle)
    decision_reasons: list[str] = []
    warnings: list[str] = []

    # ── Evidence Gate ─────────────────────────────────────────────────────────
    # P29-1: require non-empty evidence dict per phase
    evidence_present: list[tuple[str, bool]] = []
    missing_phase_ids: list[str] = []

    for phase_id in REQUIRED_PHASE_IDS:
        evidence = evidence_map.get(phase_id)
        present = evidence is not None and bool(evidence)
        evidence_present.append((phase_id, present))
        if not present:
            missing_phase_ids.append(phase_id)

    checklist = EvidenceChecklist(
        evidence_present_by_phase=tuple(evidence_present),
        missing_phase_ids=tuple(missing_phase_ids),
    )

    evidence_complete = len(missing_phase_ids) == 0
    if not evidence_complete:
        decision_reasons.append(f"blocked_missing_evidence:{','.join(missing_phase_ids)}")

    # ── Risk Controls Gate ─────────────────────────────────────────────────────
    risk_controls_complete = (
        request.rollback_plan is not None
        and request.monitoring_sla is not None
    )
    if not risk_controls_complete:
        missing_controls: list[str] = []
        if request.rollback_plan is None:
            missing_controls.append("rollback_plan")
        if request.monitoring_sla is None:
            missing_controls.append("monitoring_sla")
        decision_reasons.append(f"blocked_risk_controls_incomplete:{','.join(missing_controls)}")

    # ── Determine Status ───────────────────────────────────────────────────────
    # P29-4: status is recomputed from gate outcomes in to_dict(); the
    # self.status field is stored for audit traceability but is rebuilt
    # at serialization time.
    if not evidence_complete:
        status = "blocked_missing_evidence"
        warnings.append("dossier_incomplete_requires_human_review")
    elif not risk_controls_complete:
        status = "blocked_risk_controls_incomplete"
        warnings.append("risk_controls_incomplete_requires_human_review")
    else:
        status = "ready_for_human_review"
        decision_reasons.append("all_gates_passed_awaiting_human_signoff")
        if request.version_freeze_proposal is None:
            warnings.append("version_freeze_proposal_not_provided")

    return ProductionAdoptionDossier(
        status=status,
        evidence_checklist=checklist,
        rollback_plan=request.rollback_plan,
        monitoring_sla=request.monitoring_sla,
        version_freeze_proposal=request.version_freeze_proposal,
        decision_reasons=tuple(decision_reasons),
        warnings=tuple(warnings),
    )
