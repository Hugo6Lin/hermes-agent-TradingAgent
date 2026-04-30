"""Tests for Hermes version readiness governance dossier."""

from __future__ import annotations

import json

import pytest

from agent.research_v1.phase29_production_adoption_review import (
    MonitoringSLA,
    RollbackPlan,
    VersionFreezeProposal,
)
from agent.research_v1.version_readiness import (
    REQUIRED_VERSION_PHASE_IDS,
    EvidenceItem,
    TestEvidence,
    VersionMetadata,
    VersionReadinessDossier,
    VersionReadinessError,
    VersionReadinessRequest,
    build_version_readiness_dossier,
)


def _metadata() -> VersionMetadata:
    return VersionMetadata(
        branch="codex/quant-governance-p20-p30",
        commit="c3abd67",
        dirty=False,
        frozen_version_label="hermes-governance-p30",
    )


def _passing_tests() -> TestEvidence:
    return TestEvidence(
        command="/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_phase30_advanced_model_pack.py -q",
        status="passed",
        passed_count=55,
        failed_count=0,
        raw_summary="55 passed in 0.10s",
    )


def _evidence_bundle() -> tuple[EvidenceItem, ...]:
    return tuple(
        EvidenceItem(phase_id=phase_id, present=True, summary=f"{phase_id} evidence present")
        for phase_id in REQUIRED_VERSION_PHASE_IDS
    )


def _rollback_plan() -> RollbackPlan:
    return RollbackPlan(
        rollback_owner="risk-owner",
        rollback_trigger="governance blocker or production regression",
        description="Freeze adoption and return to prior reviewed version.",
    )


def _monitoring_sla() -> MonitoringSLA:
    return MonitoringSLA(
        monitoring_cadence="daily governance run",
        alert_routing="operator-review",
        description="Review blockers, degradation, and newly ready candidates daily.",
    )


def _version_freeze() -> VersionFreezeProposal:
    return VersionFreezeProposal(
        frozen_version="hermes-governance-p30",
        freeze_scope="P20-P30 governance contracts and tests",
        thaw_conditions="new human-approved governance spec",
    )


def _request(
    *,
    evidence: tuple[EvidenceItem, ...] | None = None,
    tests: tuple[TestEvidence, ...] | None = None,
    rollback_plan: RollbackPlan | None = None,
    monitoring_sla: MonitoringSLA | None = None,
    version_freeze: VersionFreezeProposal | None = None,
) -> VersionReadinessRequest:
    return VersionReadinessRequest(
        metadata=_metadata(),
        evidence_items=evidence if evidence is not None else _evidence_bundle(),
        test_evidence=tests if tests is not None else (_passing_tests(),),
        rollback_plan=rollback_plan if rollback_plan is not None else _rollback_plan(),
        monitoring_sla=monitoring_sla if monitoring_sla is not None else _monitoring_sla(),
        version_freeze_proposal=version_freeze,
    )


class TestVersionReadinessContracts:
    def test_metadata_contract(self):
        d = _metadata().to_dict()
        assert d["branch"] == "codex/quant-governance-p20-p30"
        assert d["commit"] == "c3abd67"
        assert d["dirty"] is False

    def test_test_evidence_contract(self):
        d = _passing_tests().to_dict()
        assert d["status"] == "passed"
        assert d["failed_count"] == 0

    def test_evidence_item_contract(self):
        item = EvidenceItem(phase_id="P20", present=True, summary="factor snapshots present")
        assert item.to_dict() == {
            "phase_id": "P20",
            "present": True,
            "summary": "factor snapshots present",
            "details": {},
        }

    def test_dossier_json_round_trip(self):
        dossier = build_version_readiness_dossier(_request(version_freeze=_version_freeze()))
        parsed = json.loads(json.dumps(dossier.to_dict()))
        assert parsed["status"] == "ready_for_human_review"
        assert parsed["metadata"]["branch"] == "codex/quant-governance-p20-p30"

    def test_invalid_test_status_rejected(self):
        with pytest.raises(VersionReadinessError, match="status must be one of"):
            TestEvidence(command="pytest", status="unknown", passed_count=0, failed_count=0, raw_summary="")


class TestVersionReadinessGates:
    def test_missing_phase_evidence_blocks(self):
        evidence = tuple(
            item for item in _evidence_bundle()
            if item.phase_id != "P25"
        )
        dossier = build_version_readiness_dossier(_request(evidence=evidence))
        assert dossier.status == "blocked_missing_evidence"
        assert "missing_phase_evidence:P25" in dossier.decision_reasons

    def test_failed_test_blocks(self):
        tests = (
            TestEvidence(
                command="pytest failing-suite",
                status="failed",
                passed_count=10,
                failed_count=1,
                raw_summary="1 failed, 10 passed",
            ),
        )
        dossier = build_version_readiness_dossier(_request(tests=tests))
        assert dossier.status == "blocked_test_failures"
        assert "test_failures:pytest failing-suite" in dossier.decision_reasons

    def test_missing_rollback_plan_blocks_controls(self):
        dossier = build_version_readiness_dossier(
            VersionReadinessRequest(
                metadata=_metadata(),
                evidence_items=_evidence_bundle(),
                test_evidence=(_passing_tests(),),
                rollback_plan=None,
                monitoring_sla=_monitoring_sla(),
                version_freeze_proposal=_version_freeze(),
            )
        )
        assert dossier.status == "blocked_risk_controls_incomplete"
        assert "missing_risk_controls:rollback_plan" in dossier.decision_reasons

    def test_missing_monitoring_sla_blocks_controls(self):
        dossier = build_version_readiness_dossier(
            VersionReadinessRequest(
                metadata=_metadata(),
                evidence_items=_evidence_bundle(),
                test_evidence=(_passing_tests(),),
                rollback_plan=_rollback_plan(),
                monitoring_sla=None,
                version_freeze_proposal=_version_freeze(),
            )
        )
        assert dossier.status == "blocked_risk_controls_incomplete"
        assert "missing_risk_controls:monitoring_sla" in dossier.decision_reasons

    def test_missing_version_freeze_warns_but_does_not_block(self):
        dossier = build_version_readiness_dossier(_request(version_freeze=None))
        assert dossier.status == "ready_for_human_review"
        assert "version_freeze_proposal_not_provided" in dossier.warnings

    def test_complete_request_ready_for_human_review(self):
        dossier = build_version_readiness_dossier(_request(version_freeze=_version_freeze()))
        assert dossier.status == "ready_for_human_review"
        assert "all_gates_passed_awaiting_human_signoff" in dossier.decision_reasons

    def test_to_dict_rebuilds_status_from_gate_fields(self):
        dossier = build_version_readiness_dossier(_request(version_freeze=_version_freeze()))
        object.__setattr__(dossier, "status", "blocked_missing_evidence")
        assert dossier.to_dict()["status"] == "ready_for_human_review"