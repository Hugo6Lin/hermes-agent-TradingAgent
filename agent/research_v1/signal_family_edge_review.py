"""P33 signal-family edge review based on governance artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agent.research_v1.evidence_artifact_registry import ArtifactRecord, EvidenceArtifactRegistryReport


ALLOWED_EDGE_REVIEW_STATUSES = frozenset({
    "blocked_missing_evidence",
    "blocked_integrity_failure",
    "shadow_observation_only",
    "ready_for_human_review",
    "rejected_for_now",
})

ALLOWED_EDGE_NEXT_STEPS = frozenset({
    "collect_more_evidence",
    "continue_shadow_observation",
    "prepare_human_review",
    "reject_for_now",
})


@dataclass(frozen=True)
class EdgeReviewPolicy:
    minimum_observation_count: int
    require_net_return_basis: bool = True
    require_execution_realism: bool = True


@dataclass(frozen=True)
class SignalFamilyEdgeReviewRequest:
    family_namespace: str
    family_type: str
    registry_report: EvidenceArtifactRegistryReport
    policy: EdgeReviewPolicy
    notes: str = ""


@dataclass(frozen=True)
class SignalFamilyEdgeReviewReport:
    family_namespace: str
    family_type: str
    status: str
    edge_evidence_summary: str
    risk_evidence_summary: str
    integrity_blockers: tuple[str, ...]
    missing_artifacts: tuple[str, ...]
    degradation_warnings: tuple[str, ...]
    execution_cost_warnings: tuple[str, ...]
    allowed_next_step: str
    promotion_forbidden_reasons: tuple[str, ...]
    human_review_questions: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "family_namespace": self.family_namespace,
            "family_type": self.family_type,
            "status": self.status,
            "edge_evidence_summary": self.edge_evidence_summary,
            "risk_evidence_summary": self.risk_evidence_summary,
            "integrity_blockers": list(self.integrity_blockers),
            "missing_artifacts": list(self.missing_artifacts),
            "degradation_warnings": list(self.degradation_warnings),
            "execution_cost_warnings": list(self.execution_cost_warnings),
            "allowed_next_step": self.allowed_next_step,
            "promotion_forbidden_reasons": list(self.promotion_forbidden_reasons),
            "human_review_questions": list(self.human_review_questions),
        }


def _records_for_family(
    registry: EvidenceArtifactRegistryReport,
    family_namespace: str,
) -> dict[str, ArtifactRecord]:
    """Return a dict of artifact_type -> ArtifactRecord for the given family.

    Include records with exact family_namespace match.
    If no exact match for an artifact type, include records with empty family_namespace.
    """
    records: dict[str, ArtifactRecord] = {}
    exact: dict[str, ArtifactRecord] = {}
    fallback: dict[str, ArtifactRecord] = {}

    for rec in registry.artifact_records:
        if rec.family_namespace == family_namespace:
            exact[rec.artifact_type] = rec
        elif not rec.family_namespace:
            fallback[rec.artifact_type] = rec

    # Prefer exact match; fall back to empty-namespace for same type if no exact
    for atype in set(exact.keys()) | set(fallback.keys()):
        if atype in exact:
            records[atype] = exact[atype]
        elif atype in fallback:
            records[atype] = fallback[atype]

    return records


def build_signal_family_edge_review(
    request: SignalFamilyEdgeReviewRequest,
) -> SignalFamilyEdgeReviewReport:
    family_ns = request.family_namespace
    family_type = request.family_type
    records = _records_for_family(request.registry_report, family_ns)
    policy = request.policy

    integrity_blockers: list[str] = []
    missing_artifacts: list[str] = []
    execution_cost_warnings: list[str] = []
    degradation_warnings: list[str] = []
    promotion_forbidden: list[str] = []
    questions: list[str] = []

    # ── P22 validity required for all families ──────────────────────────────────
    p22_rec = records.get("p22_validity_report")
    if p22_rec is None or p22_rec.status != "present":
        missing_artifacts.append("missing_artifact:p22_validity_report")

    # ── P28 execution realism required when policy demands it ──────────────────
    p28_rec = records.get("p28_execution_realism_report")

    # ── P25/P26 required for shadow model families ──────────────────────────────
    if family_type == "shadow_model_family":
        if records.get("p25_shadow_training_result") is None:
            missing_artifacts.append("missing_artifact:p25_shadow_training_result")
        if records.get("p26_shadow_portfolio_report") is None:
            missing_artifacts.append("missing_artifact:p26_shadow_portfolio_report")

    # ── Determine status ────────────────────────────────────────────────────────
    if missing_artifacts:
        status = "blocked_missing_evidence"
        next_step = "collect_more_evidence"
        edge_summary = "insufficient evidence for edge assessment"
        risk_summary = "missing required artifacts"
    else:
        # P22 details analysis
        p22_details = p22_rec.details if p22_rec else {}
        return_basis = p22_details.get("return_basis", "")
        obs_count = p22_details.get("observation_count", 0)
        net_ic_positive = p22_details.get("net_ic_positive", False)
        lookahead_blocker = p22_details.get("lookahead_blocker", False)
        source_audit_blocker = p22_details.get("source_audit_blocker", False)

        # Integrity blockers
        if lookahead_blocker:
            integrity_blockers.append("lookahead_blocker_present")
        if source_audit_blocker:
            integrity_blockers.append("source_audit_blocker_present")

        # Net return requirement
        if policy.require_net_return_basis and return_basis != "net_return_pct":
            integrity_blockers.append("net_return_basis_required")

        # Observation count
        insufficient_samples = obs_count < policy.minimum_observation_count

        # Execution cost
        p28_details = p28_rec.details if p28_rec else {}
        cost_exceeds = p28_details.get("stress_cost_exceeds_edge", False)
        if cost_exceeds:
            execution_cost_warnings.append("execution_cost_exceeds_edge")

        # Determine status from blockers
        if integrity_blockers or (policy.require_execution_realism and cost_exceeds):
            status = "blocked_integrity_failure"
            next_step = "collect_more_evidence"
            edge_summary = "integrity issues block positive edge assessment"
            risk_summary = "integrity blockers present"
        elif insufficient_samples or not net_ic_positive:
            status = "shadow_observation_only"
            next_step = "continue_shadow_observation"
            edge_summary = "evidence present but not mature enough for human review"
            risk_summary = "observation count below threshold or net IC not positive"
            if insufficient_samples:
                degradation_warnings.append(f"observation_count:{obs_count}_below_minimum:{policy.minimum_observation_count}")
            if not net_ic_positive:
                degradation_warnings.append("net_ic_not_positive")
        else:
            status = "ready_for_human_review"
            next_step = "prepare_human_review"
            edge_summary = "net evidence positive and mature"
            risk_summary = "execution cost acceptable"
            questions.append("Does the human reviewer accept the evidence maturity claim?")

    # ── Promotion boundaries ────────────────────────────────────────────────────
    if family_type in {"shadow_model_family", "advanced_model_candidate"}:
        promotion_forbidden.append("shadow_outputs_must_not_promote_to_production")

    if family_type == "advanced_model_candidate":
        promotion_forbidden.append("advanced_model_remains_sandbox_only")

    return SignalFamilyEdgeReviewReport(
        family_namespace=family_ns,
        family_type=family_type,
        status=status,
        edge_evidence_summary=edge_summary,
        risk_evidence_summary=risk_summary,
        integrity_blockers=tuple(integrity_blockers),
        missing_artifacts=tuple(missing_artifacts),
        degradation_warnings=tuple(degradation_warnings),
        execution_cost_warnings=tuple(execution_cost_warnings),
        allowed_next_step=next_step,
        promotion_forbidden_reasons=tuple(dict.fromkeys(promotion_forbidden)),
        human_review_questions=tuple(questions),
    )
