"""Tests for Phase 29 production adoption review pack."""

from __future__ import annotations

import json

import pytest

from agent.research_v1.phase29_production_adoption_review import (
    ALLOWED_STATUSES,
    REQUIRED_PHASE_IDS,
    EvidenceChecklist,
    MonitoringSLA,
    ProductionAdoptionDossier,
    ProductionAdoptionError,
    ProductionAdoptionReviewRequest,
    RollbackPlan,
    VersionFreezeProposal,
    build_production_adoption_dossier,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

def _minimal_bundle() -> tuple[tuple[str, dict[str, object]], ...]:
    return (
        ("P20", {"data_integrity": True}),
        ("P21", {"calibration_inputs": True}),
        ("P22", {"diagnostics": True}),
        ("P23", {"shadow_calibration": True}),
        ("P24", {"experiment_governance": True}),
        ("P25", {"model_evaluation": True}),
        ("P26", {"portfolio_simulation": True}),
        ("P28", {"execution_realism": True}),
    )


def _rollback_plan() -> RollbackPlan:
    return RollbackPlan(
        rollback_owner="sre-team",
        rollback_trigger="error_rate > 1% over 5min",
        description="Revert to previous model version.",
    )


def _monitoring_sla() -> MonitoringSLA:
    return MonitoringSLA(
        monitoring_cadence="every 1min",
        alert_routing="pagerduty:oncall-sre",
        description="Monitor prediction drift and error rates.",
    )


def _version_freeze() -> VersionFreezeProposal:
    return VersionFreezeProposal(
        frozen_version="v2.4.1",
        freeze_scope="model_weights + feature_pipeline",
        thaw_conditions="sign-off from both risk-committee and SRE",
    )


# ─── Contract tests ────────────────────────────────────────────────────────────

class TestContracts:
    def test_rollback_plan_contract(self):
        rp = RollbackPlan(
            rollback_owner="sre-team",
            rollback_trigger="error_rate > 1%",
            description="Revert.",
        )
        d = rp.to_dict()
        assert d["rollback_owner"] == "sre-team"
        assert d["rollback_trigger"] == "error_rate > 1%"

    def test_monitoring_sla_contract(self):
        ms = MonitoringSLA(
            monitoring_cadence="every 1min",
            alert_routing="pagerduty:oncall",
            description="Monitor drift.",
        )
        d = ms.to_dict()
        assert d["monitoring_cadence"] == "every 1min"
        assert d["alert_routing"] == "pagerduty:oncall"

    def test_version_freeze_proposal_contract(self):
        vfp = VersionFreezeProposal(
            frozen_version="v2.4.1",
            freeze_scope="model_weights",
            thaw_conditions="risk-committee sign-off",
        )
        d = vfp.to_dict()
        assert d["frozen_version"] == "v2.4.1"
        assert d["freeze_scope"] == "model_weights"

    def test_evidence_checklist_contract(self):
        ec = EvidenceChecklist(
            evidence_present_by_phase=(
                ("P20", True),
                ("P28", False),
            ),
            missing_phase_ids=("P28",),
        )
        d = ec.to_dict()
        assert d["evidence_present_by_phase"]["P20"] is True
        assert d["evidence_present_by_phase"]["P28"] is False
        assert "P28" in d["missing_phase_ids"]

    def test_dossier_contract(self):
        dossier = ProductionAdoptionDossier(
            status="ready_for_human_review",
            evidence_checklist=EvidenceChecklist(
                evidence_present_by_phase=tuple((p, True) for p in REQUIRED_PHASE_IDS),
                missing_phase_ids=(),
            ),
            rollback_plan=_rollback_plan(),
            monitoring_sla=_monitoring_sla(),
            version_freeze_proposal=_version_freeze(),
            decision_reasons=("all_gates_passed_awaiting_human_signoff",),
            warnings=(),
        )
        d = dossier.to_dict()
        assert d["status"] == "ready_for_human_review"
        assert d["rollback_plan"]["rollback_owner"] == "sre-team"
        assert d["monitoring_sla"]["alert_routing"] == "pagerduty:oncall-sre"
        assert d["version_freeze_proposal"]["frozen_version"] == "v2.4.1"

    def test_to_dict_json_round_trip(self):
        dossier = ProductionAdoptionDossier(
            status="blocked_missing_evidence",
            evidence_checklist=EvidenceChecklist(
                evidence_present_by_phase=(("P20", True),),
                missing_phase_ids=("P28",),
            ),
            rollback_plan=None,
            monitoring_sla=None,
            version_freeze_proposal=None,
            decision_reasons=("blocked_missing_evidence:P28",),
            warnings=("dossier_incomplete_requires_human_review",),
        )
        d = dossier.to_dict()
        parsed = json.loads(json.dumps(d))
        assert parsed["status"] == "blocked_missing_evidence"
        assert parsed["rollback_plan"] is None

    def test_required_phase_ids(self):
        assert REQUIRED_PHASE_IDS == ("P20", "P21", "P22", "P23", "P24", "P25", "P26", "P28")

    def test_allowed_statuses(self):
        assert ALLOWED_STATUSES == frozenset({
            "blocked_missing_evidence",
            "blocked_risk_controls_incomplete",
            "ready_for_human_review",
        })


# ─── Contract validation ───────────────────────────────────────────────────────

class TestContractValidation:
    # P29-5: whitespace-only strings rejected
    def test_rollback_plan_rejects_empty_owner(self):
        with pytest.raises(ProductionAdoptionError, match="rollback_owner"):
            RollbackPlan(rollback_owner="", rollback_trigger="trigger", description=".")

    def test_rollback_plan_rejects_whitespace_only_owner(self):
        with pytest.raises(ProductionAdoptionError, match="rollback_owner"):
            RollbackPlan(rollback_owner="   ", rollback_trigger="trigger", description=".")

    def test_rollback_plan_rejects_empty_trigger(self):
        with pytest.raises(ProductionAdoptionError, match="rollback_trigger"):
            RollbackPlan(rollback_owner="team", rollback_trigger="", description=".")

    def test_rollback_plan_rejects_whitespace_trigger(self):
        with pytest.raises(ProductionAdoptionError, match="rollback_trigger"):
            RollbackPlan(rollback_owner="team", rollback_trigger="   ", description=".")

    def test_rollback_plan_rejects_empty_description(self):
        with pytest.raises(ProductionAdoptionError, match="description"):
            RollbackPlan(rollback_owner="team", rollback_trigger="trigger", description="")

    def test_monitoring_sla_rejects_empty_cadence(self):
        with pytest.raises(ProductionAdoptionError, match="monitoring_cadence"):
            MonitoringSLA(monitoring_cadence="", alert_routing="pd", description=".")

    def test_monitoring_sla_rejects_whitespace_cadence(self):
        with pytest.raises(ProductionAdoptionError, match="monitoring_cadence"):
            MonitoringSLA(monitoring_cadence="  ", alert_routing="pd", description=".")

    def test_monitoring_sla_rejects_empty_routing(self):
        with pytest.raises(ProductionAdoptionError, match="alert_routing"):
            MonitoringSLA(monitoring_cadence="1min", alert_routing="", description=".")

    def test_monitoring_sla_rejects_empty_description(self):
        with pytest.raises(ProductionAdoptionError, match="description"):
            MonitoringSLA(monitoring_cadence="1min", alert_routing="pd", description="")

    def test_version_freeze_rejects_empty_version(self):
        with pytest.raises(ProductionAdoptionError, match="frozen_version"):
            VersionFreezeProposal(frozen_version="", freeze_scope=".", thaw_conditions=".")

    def test_version_freeze_rejects_whitespace_version(self):
        with pytest.raises(ProductionAdoptionError, match="frozen_version"):
            VersionFreezeProposal(frozen_version="  ", freeze_scope=".", thaw_conditions=".")

    def test_version_freeze_rejects_empty_scope(self):
        with pytest.raises(ProductionAdoptionError, match="freeze_scope"):
            VersionFreezeProposal(frozen_version="v1", freeze_scope="", thaw_conditions=".")

    # P29-3: invalid status raises
    def test_dossier_rejects_unknown_status(self):
        with pytest.raises(ProductionAdoptionError, match="status must be one of"):
            ProductionAdoptionDossier(
                status="approved_production_immediate",
                evidence_checklist=EvidenceChecklist(
                    evidence_present_by_phase=tuple((p, True) for p in REQUIRED_PHASE_IDS),
                    missing_phase_ids=(),
                ),
                rollback_plan=None,
                monitoring_sla=None,
                version_freeze_proposal=None,
                decision_reasons=(),
                warnings=(),
            )


# ─── Evidence gate tests ─────────────────────────────────────────────────────--

class TestEvidenceGate:
    def test_all_phases_present_no_block(self):
        bundle = _minimal_bundle()
        req = ProductionAdoptionReviewRequest(
            rollback_plan=_rollback_plan(),
            monitoring_sla=_monitoring_sla(),
        )
        dossier = build_production_adoption_dossier(bundle, req)
        assert dossier.status == "ready_for_human_review"
        assert "all_gates_passed_awaiting_human_signoff" in dossier.decision_reasons

    def test_missing_single_phase_blocks(self):
        bundle = tuple(p for p in _minimal_bundle() if p[0] != "P25")
        req = ProductionAdoptionReviewRequest(
            rollback_plan=_rollback_plan(),
            monitoring_sla=_monitoring_sla(),
        )
        dossier = build_production_adoption_dossier(bundle, req)
        assert dossier.status == "blocked_missing_evidence"
        assert "P25" in dossier.evidence_checklist.missing_phase_ids

    def test_missing_multiple_phases_blocks(self):
        bundle = (("P20", {"summary": "x"}), ("P28", {"summary": "y"}))
        req = ProductionAdoptionReviewRequest(
            rollback_plan=_rollback_plan(),
            monitoring_sla=_monitoring_sla(),
        )
        dossier = build_production_adoption_dossier(bundle, req)
        assert dossier.status == "blocked_missing_evidence"
        assert "P21" in dossier.evidence_checklist.missing_phase_ids
        assert "P26" in dossier.evidence_checklist.missing_phase_ids

    def test_evidence_checklist_has_all_phases(self):
        bundle = _minimal_bundle()
        req = ProductionAdoptionReviewRequest(
            rollback_plan=_rollback_plan(),
            monitoring_sla=_monitoring_sla(),
        )
        dossier = build_production_adoption_dossier(bundle, req)
        present = dict(dossier.evidence_checklist.evidence_present_by_phase)
        for phase_id in REQUIRED_PHASE_IDS:
            assert phase_id in present, f"{phase_id} missing from checklist"


# ─── P29-1 Regression: empty dict = missing ────────────────────────────────────

class TestEmptyDictEvidence:
    def test_empty_dict_phase_is_missing(self):
        # P29-1: an empty evidence dict {} is absence of evidence, not presence
        bundle = _minimal_bundle()
        # Replace P22 with empty dict — must still be counted as missing
        bundle = tuple(("P22", {}) if p[0] == "P22" else p for p in bundle)
        req = ProductionAdoptionReviewRequest(
            rollback_plan=_rollback_plan(),
            monitoring_sla=_monitoring_sla(),
        )
        dossier = build_production_adoption_dossier(bundle, req)
        assert dossier.status == "blocked_missing_evidence"
        assert "P22" in dossier.evidence_checklist.missing_phase_ids

    def test_any_phase_empty_dict_blocks_ready(self):
        # Single empty dict for any phase blocks ready status
        bundle = (
            ("P20", {"data_integrity": True}),
            ("P21", {}),  # empty — blocks
            ("P22", {"diagnostics": True}),
            ("P23", {"shadow_calibration": True}),
            ("P24", {"experiment_governance": True}),
            ("P25", {"model_evaluation": True}),
            ("P26", {"portfolio_simulation": True}),
            ("P28", {"execution_realism": True}),
        )
        req = ProductionAdoptionReviewRequest(
            rollback_plan=_rollback_plan(),
            monitoring_sla=_monitoring_sla(),
        )
        dossier = build_production_adoption_dossier(bundle, req)
        assert dossier.status == "blocked_missing_evidence"
        assert "P21" in dossier.evidence_checklist.missing_phase_ids


# ─── Risk controls gate tests ─────────────────────────────────────────────────

class TestRiskControlsGate:
    def test_missing_rollback_plan_blocks(self):
        bundle = _minimal_bundle()
        req = ProductionAdoptionReviewRequest(
            rollback_plan=None,
            monitoring_sla=_monitoring_sla(),
        )
        dossier = build_production_adoption_dossier(bundle, req)
        assert dossier.status == "blocked_risk_controls_incomplete"
        assert "rollback_plan" in str(dossier.decision_reasons)

    def test_missing_monitoring_sla_blocks(self):
        bundle = _minimal_bundle()
        req = ProductionAdoptionReviewRequest(
            rollback_plan=_rollback_plan(),
            monitoring_sla=None,
        )
        dossier = build_production_adoption_dossier(bundle, req)
        assert dossier.status == "blocked_risk_controls_incomplete"
        assert "monitoring_sla" in str(dossier.decision_reasons)

    def test_both_missing_is_blocked(self):
        bundle = _minimal_bundle()
        req = ProductionAdoptionReviewRequest(
            rollback_plan=None,
            monitoring_sla=None,
        )
        dossier = build_production_adoption_dossier(bundle, req)
        assert dossier.status == "blocked_risk_controls_incomplete"

    def test_rollback_plan_alone_not_enough_without_monitoring(self):
        bundle = _minimal_bundle()
        req = ProductionAdoptionReviewRequest(
            rollback_plan=_rollback_plan(),
            monitoring_sla=None,
        )
        dossier = build_production_adoption_dossier(bundle, req)
        assert dossier.status == "blocked_risk_controls_incomplete"

    def test_monitoring_sla_alone_not_enough_without_rollback(self):
        bundle = _minimal_bundle()
        req = ProductionAdoptionReviewRequest(
            rollback_plan=None,
            monitoring_sla=_monitoring_sla(),
        )
        dossier = build_production_adoption_dossier(bundle, req)
        assert dossier.status == "blocked_risk_controls_incomplete"


# ─── Human review output tests ─────────────────────────────────────────────────

class TestHumanReviewOutput:
    def test_ready_status_with_all_phases_and_controls(self):
        bundle = _minimal_bundle()
        req = ProductionAdoptionReviewRequest(
            rollback_plan=_rollback_plan(),
            monitoring_sla=_monitoring_sla(),
            version_freeze_proposal=_version_freeze(),
        )
        dossier = build_production_adoption_dossier(bundle, req)
        assert dossier.status == "ready_for_human_review"
        assert dossier.rollback_plan is not None
        assert dossier.monitoring_sla is not None
        assert dossier.version_freeze_proposal is not None

    def test_version_freeze_optional_for_ready(self):
        bundle = _minimal_bundle()
        req = ProductionAdoptionReviewRequest(
            rollback_plan=_rollback_plan(),
            monitoring_sla=_monitoring_sla(),
            version_freeze_proposal=None,
        )
        dossier = build_production_adoption_dossier(bundle, req)
        assert dossier.status == "ready_for_human_review"
        assert "version_freeze_proposal_not_provided" in dossier.warnings

    def test_no_production_write_fields_in_dossier(self):
        bundle = _minimal_bundle()
        req = ProductionAdoptionReviewRequest(
            rollback_plan=_rollback_plan(),
            monitoring_sla=_monitoring_sla(),
        )
        dossier = build_production_adoption_dossier(bundle, req)
        d = dossier.to_dict()
        production_write_fields = {
            "deploy", "enable_trading", "write_config", "production_config_update",
            "live_trade_signal", "broker_instruction", "order_id",
        }
        flat_keys: set[str] = set()
        def _flatten(obj: object, prefix: str = "") -> None:
            if isinstance(obj, dict):
                for k, v in obj.items():
                    _flatten(v, f"{prefix}.{k}" if prefix else k)
            elif isinstance(obj, (list, tuple)):
                for v in obj:
                    _flatten(v, prefix)
            else:
                flat_keys.add(prefix)
        _flatten(d)
        overlap = production_write_fields & flat_keys
        assert not overlap, f"Production write fields found in dossier: {overlap}"

    def test_dossier_warns_on_missing_evidence(self):
        bundle = (
            ("P20", {"data_integrity": True}),
            ("P21", {}),  # empty → missing
        )
        req = ProductionAdoptionReviewRequest(
            rollback_plan=_rollback_plan(),
            monitoring_sla=_monitoring_sla(),
        )
        dossier = build_production_adoption_dossier(bundle, req)
        assert "dossier_incomplete_requires_human_review" in dossier.warnings

    def test_dossier_warns_on_incomplete_risk_controls(self):
        bundle = _minimal_bundle()
        req = ProductionAdoptionReviewRequest(
            rollback_plan=None,
            monitoring_sla=None,
        )
        dossier = build_production_adoption_dossier(bundle, req)
        assert "risk_controls_incomplete_requires_human_review" in dossier.warnings


# ─── Request contract ─────────────────────────────────────────────────────────

class TestRequestContract:
    def test_request_to_dict(self):
        req = ProductionAdoptionReviewRequest(
            rollback_plan=_rollback_plan(),
            monitoring_sla=_monitoring_sla(),
            version_freeze_proposal=_version_freeze(),
            notes="Phase 29 review",
        )
        d = req.to_dict()
        assert d["rollback_plan"]["rollback_owner"] == "sre-team"
        assert d["monitoring_sla"]["alert_routing"] == "pagerduty:oncall-sre"
        assert d["version_freeze_proposal"]["frozen_version"] == "v2.4.1"
        assert d["notes"] == "Phase 29 review"

    def test_request_to_dict_with_none_plans(self):
        req = ProductionAdoptionReviewRequest(notes="no plans")
        d = req.to_dict()
        assert d["rollback_plan"] is None
        assert d["monitoring_sla"] is None
        assert d["notes"] == "no plans"


# ─── P29-4 Regression: __setattr__ bypass ─────────────────────────────────────

class TestStatusBypass:
    def test_setattr_forge_status_to_dict_rebuilds(self):
        # P29-4: forging status via __setattr__ must not survive to_dict()
        dossier = ProductionAdoptionDossier(
            status="ready_for_human_review",
            evidence_checklist=EvidenceChecklist(
                evidence_present_by_phase=tuple((p, True) for p in REQUIRED_PHASE_IDS),
                missing_phase_ids=(),
            ),
            rollback_plan=_rollback_plan(),
            monitoring_sla=_monitoring_sla(),
            version_freeze_proposal=None,
            decision_reasons=("all_gates_passed_awaiting_human_signoff",),
            warnings=("version_freeze_proposal_not_provided",),
        )
        # Forge status to a forbidden value
        object.__setattr__(dossier, "status", "approved_production_immediate")
        d = dossier.to_dict()
        # to_dict() must rebuild from gate fields, not use the forged self.status
        assert d["status"] == "ready_for_human_review"

    def test_setattr_blocked_risk_to_ready_rebuilds(self):
        # Forging blocked → ready also gets rebuilt
        dossier = ProductionAdoptionDossier(
            status="blocked_risk_controls_incomplete",
            evidence_checklist=EvidenceChecklist(
                evidence_present_by_phase=tuple((p, True) for p in REQUIRED_PHASE_IDS),
                missing_phase_ids=(),
            ),
            rollback_plan=None,  # incomplete controls
            monitoring_sla=None,
            version_freeze_proposal=None,
            decision_reasons=("blocked_risk_controls_incomplete:rollback_plan,monitoring_sla",),
            warnings=("risk_controls_incomplete_requires_human_review",),
        )
        object.__setattr__(dossier, "status", "ready_for_human_review")
        d = dossier.to_dict()
        assert d["status"] == "blocked_risk_controls_incomplete"


# ─── Status enumeration ───────────────────────────────────────────────────────

class TestStatusValues:
    def test_blocked_missing_evidence_status(self):
        bundle = (
            ("P20", {"data_integrity": True}),
            ("P21", {}),  # empty = missing
        )
        req = ProductionAdoptionReviewRequest(
            rollback_plan=_rollback_plan(),
            monitoring_sla=_monitoring_sla(),
        )
        dossier = build_production_adoption_dossier(bundle, req)
        assert dossier.status == "blocked_missing_evidence"

    def test_blocked_risk_controls_status(self):
        bundle = _minimal_bundle()
        req = ProductionAdoptionReviewRequest(
            rollback_plan=None,
            monitoring_sla=None,
        )
        dossier = build_production_adoption_dossier(bundle, req)
        assert dossier.status == "blocked_risk_controls_incomplete"

    def test_ready_for_human_review_status(self):
        bundle = _minimal_bundle()
        req = ProductionAdoptionReviewRequest(
            rollback_plan=_rollback_plan(),
            monitoring_sla=_monitoring_sla(),
        )
        dossier = build_production_adoption_dossier(bundle, req)
        assert dossier.status == "ready_for_human_review"
