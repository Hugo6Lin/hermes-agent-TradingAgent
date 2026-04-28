"""Version-level governance readiness dossier for Hermes P20-P30 evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agent.research_v1.phase29_production_adoption_review import (
    MonitoringSLA,
    RollbackPlan,
    VersionFreezeProposal,
)


class VersionReadinessError(ValueError):
    """Raised for unsafe or invalid version readiness inputs."""


REQUIRED_VERSION_PHASE_IDS: tuple[str, ...] = (
    "P20",
    "P21",
    "P22",
    "P23",
    "P24",
    "P25",
    "P26",
    "P28",
    "P29",
    "P30",
)

ALLOWED_TEST_STATUSES: frozenset[str] = frozenset({"passed", "failed", "not_run"})
ALLOWED_VERSION_STATUSES: frozenset[str] = frozenset({
    "blocked_missing_evidence",
    "blocked_test_failures",
    "blocked_risk_controls_incomplete",
    "ready_for_human_review",
})


@dataclass(frozen=True)
class VersionMetadata:
    branch: str
    commit: str
    dirty: bool
    frozen_version_label: str = ""

    def __post_init__(self) -> None:
        if not self.branch.strip():
            raise VersionReadinessError("branch must be non-empty")
        if not self.commit.strip():
            raise VersionReadinessError("commit must be non-empty")

    def to_dict(self) -> dict[str, Any]:
        return {
            "branch": self.branch,
            "commit": self.commit,
            "dirty": self.dirty,
            "frozen_version_label": self.frozen_version_label,
        }


@dataclass(frozen=True)
class EvidenceItem:
    phase_id: str
    present: bool
    summary: str
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.phase_id.strip():
            raise VersionReadinessError("phase_id must be non-empty")

    def to_dict(self) -> dict[str, Any]:
        return {
            "phase_id": self.phase_id,
            "present": self.present,
            "summary": self.summary,
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class TestEvidence:
    command: str
    status: str
    passed_count: int
    failed_count: int
    raw_summary: str

    def __post_init__(self) -> None:
        if not self.command.strip():
            raise VersionReadinessError("command must be non-empty")
        if self.status not in ALLOWED_TEST_STATUSES:
            raise VersionReadinessError(
                f"status must be one of {sorted(ALLOWED_TEST_STATUSES)}, got {self.status!r}"
            )
        if self.passed_count < 0:
            raise VersionReadinessError("passed_count must be >= 0")
        if self.failed_count < 0:
            raise VersionReadinessError("failed_count must be >= 0")

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "status": self.status,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "raw_summary": self.raw_summary,
        }


@dataclass(frozen=True)
class VersionReadinessRequest:
    metadata: VersionMetadata
    evidence_items: tuple[EvidenceItem, ...]
    test_evidence: tuple[TestEvidence, ...]
    rollback_plan: RollbackPlan | None
    monitoring_sla: MonitoringSLA | None
    version_freeze_proposal: VersionFreezeProposal | None = None
    notes: str = ""


@dataclass(frozen=True)
class VersionReadinessDossier:
    status: str
    metadata: VersionMetadata
    evidence_matrix: tuple[EvidenceItem, ...]
    test_summary: tuple[TestEvidence, ...]
    rollback_plan: RollbackPlan | None
    monitoring_sla: MonitoringSLA | None
    version_freeze_candidate: VersionFreezeProposal | None
    human_review_questions: tuple[str, ...]
    next_actions: tuple[str, ...]
    decision_reasons: tuple[str, ...]
    warnings: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.status not in ALLOWED_VERSION_STATUSES:
            raise VersionReadinessError(
                f"status must be one of {sorted(ALLOWED_VERSION_STATUSES)}, got {self.status!r}"
            )

    def to_dict(self) -> dict[str, Any]:
        evidence_missing = [
            item.phase_id for item in self.evidence_matrix
            if item.phase_id in REQUIRED_VERSION_PHASE_IDS and not item.present
        ]
        failed_tests = [
            item.command for item in self.test_summary
            if item.status == "failed" or item.failed_count > 0
        ]
        controls_complete = self.rollback_plan is not None and self.monitoring_sla is not None

        if evidence_missing:
            rebuilt_status = "blocked_missing_evidence"
        elif failed_tests:
            rebuilt_status = "blocked_test_failures"
        elif not controls_complete:
            rebuilt_status = "blocked_risk_controls_incomplete"
        else:
            rebuilt_status = "ready_for_human_review"

        return {
            "status": rebuilt_status,
            "metadata": self.metadata.to_dict(),
            "evidence_matrix": [item.to_dict() for item in self.evidence_matrix],
            "test_summary": [item.to_dict() for item in self.test_summary],
            "risk_control_summary": {
                "rollback_plan": self.rollback_plan.to_dict() if self.rollback_plan else None,
                "monitoring_sla": self.monitoring_sla.to_dict() if self.monitoring_sla else None,
            },
            "version_freeze_candidate": (
                self.version_freeze_candidate.to_dict()
                if self.version_freeze_candidate
                else None
            ),
            "human_review_questions": list(self.human_review_questions),
            "next_actions": list(self.next_actions),
            "decision_reasons": list(self.decision_reasons),
            "warnings": list(self.warnings),
        }


def _normalize_evidence(items: tuple[EvidenceItem, ...]) -> tuple[EvidenceItem, ...]:
    by_phase = {item.phase_id: item for item in items}
    normalized: list[EvidenceItem] = []
    for phase_id in REQUIRED_VERSION_PHASE_IDS:
        normalized.append(
            by_phase.get(
                phase_id,
                EvidenceItem(
                    phase_id=phase_id,
                    present=False,
                    summary=f"{phase_id} evidence missing",
                ),
            )
        )
    for item in items:
        if item.phase_id not in REQUIRED_VERSION_PHASE_IDS:
            normalized.append(item)
    return tuple(normalized)


def build_version_readiness_dossier(
    request: VersionReadinessRequest,
) -> VersionReadinessDossier:
    evidence_matrix = _normalize_evidence(request.evidence_items)
    missing_phase_ids = [
        item.phase_id for item in evidence_matrix
        if item.phase_id in REQUIRED_VERSION_PHASE_IDS and not item.present
    ]
    failed_tests = [
        item.command for item in request.test_evidence
        if item.status == "failed" or item.failed_count > 0
    ]

    decision_reasons: list[str] = []
    warnings: list[str] = []
    next_actions: list[str] = []
    human_review_questions: list[str] = []

    if missing_phase_ids:
        decision_reasons.append(f"missing_phase_evidence:{','.join(missing_phase_ids)}")
        next_actions.append("collect_missing_phase_evidence")

    if failed_tests:
        for command in failed_tests:
            decision_reasons.append(f"test_failures:{command}")
        next_actions.append("fix_or_explain_failed_tests")

    missing_controls: list[str] = []
    if request.rollback_plan is None:
        missing_controls.append("rollback_plan")
    if request.monitoring_sla is None:
        missing_controls.append("monitoring_sla")
    if missing_controls:
        decision_reasons.append(f"missing_risk_controls:{','.join(missing_controls)}")
        next_actions.append("complete_risk_controls")

    if request.version_freeze_proposal is None:
        warnings.append("version_freeze_proposal_not_provided")
        human_review_questions.append("Should this commit be frozen for review?")

    if missing_phase_ids:
        status = "blocked_missing_evidence"
    elif failed_tests:
        status = "blocked_test_failures"
    elif missing_controls:
        status = "blocked_risk_controls_incomplete"
    else:
        status = "ready_for_human_review"
        decision_reasons.append("all_gates_passed_awaiting_human_signoff")
        next_actions.append("prepare_human_review")

    if request.metadata.dirty:
        warnings.append("working_tree_dirty")
        human_review_questions.append("Should dirty local changes be included in the reviewed version?")

    return VersionReadinessDossier(
        status=status,
        metadata=request.metadata,
        evidence_matrix=evidence_matrix,
        test_summary=request.test_evidence,
        rollback_plan=request.rollback_plan,
        monitoring_sla=request.monitoring_sla,
        version_freeze_candidate=request.version_freeze_proposal,
        human_review_questions=tuple(human_review_questions),
        next_actions=tuple(dict.fromkeys(next_actions)),
        decision_reasons=tuple(decision_reasons),
        warnings=tuple(warnings),
    )
