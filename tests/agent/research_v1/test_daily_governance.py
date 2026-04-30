"""Tests for daily governance run output."""

from __future__ import annotations

import json
from pathlib import Path

from agent.research_v1.daily_governance import (
    DailyGovernanceRequest,
    DailyGovernanceRunError,
    run_daily_governance,
)
from agent.research_v1.phase29_production_adoption_review import MonitoringSLA, RollbackPlan
from agent.research_v1.signal_family_readiness import FamilyEvidence, SignalFamilyReadinessRequest
from agent.research_v1.version_readiness import (
    EvidenceItem,
    REQUIRED_VERSION_PHASE_IDS,
    TestEvidence,
    VersionMetadata,
    VersionReadinessRequest,
)


def _version_request() -> VersionReadinessRequest:
    return VersionReadinessRequest(
        metadata=VersionMetadata(
            branch="codex/quant-governance-p20-p30",
            commit="c3abd67",
            dirty=False,
            frozen_version_label="",
        ),
        evidence_items=tuple(
            EvidenceItem(phase_id=phase_id, present=True, summary=f"{phase_id} ok")
            for phase_id in REQUIRED_VERSION_PHASE_IDS
        ),
        test_evidence=(
            TestEvidence(
                command="/opt/homebrew/bin/python3.11 -m pytest governance-tests -q",
                status="passed",
                passed_count=12,
                failed_count=0,
                raw_summary="12 passed",
            ),
        ),
        rollback_plan=RollbackPlan(
            rollback_owner="operator",
            rollback_trigger="new governance blocker",
            description="Stop adoption review and return to previous reviewed commit.",
        ),
        monitoring_sla=MonitoringSLA(
            monitoring_cadence="daily",
            alert_routing="operator-review",
            description="Daily review of governance blockers.",
        ),
        version_freeze_proposal=None,
    )


def _family_request() -> SignalFamilyReadinessRequest:
    return SignalFamilyReadinessRequest(
        parent_version_status="ready_for_human_review",
        family_type="signal_family",
        family_namespace="signal_family.high_conviction_bullish_equity",
        evidence=FamilyEvidence(
            p20_p23_present=True,
            maturity=True,
            edge_summary="shadow evidence present",
            risk_summary="no critical warnings",
        ),
    )


class TestDailyGovernance:
    def test_run_writes_expected_json_and_markdown_files(self, tmp_path: Path):
        result = run_daily_governance(
            DailyGovernanceRequest(
                run_date="2026-04-29",
                output_root=tmp_path,
                version_request=_version_request(),
                family_requests=(_family_request(),),
            )
        )
        assert result.status == "completed_with_warnings"
        run_dir = tmp_path / "2026-04-29"
        expected_files = {
            "version_readiness.json",
            "version_readiness.md",
            "signal_families.json",
            "signal_families.md",
            "daily_summary.json",
            "daily_summary.md",
        }
        assert expected_files == {p.name for p in run_dir.iterdir()}

    def test_daily_summary_is_machine_readable(self, tmp_path: Path):
        run_daily_governance(
            DailyGovernanceRequest(
                run_date="2026-04-29",
                output_root=tmp_path,
                version_request=_version_request(),
                family_requests=(_family_request(),),
            )
        )
        summary = json.loads((tmp_path / "2026-04-29" / "daily_summary.json").read_text(encoding="utf-8"))
        assert summary["run_date"] == "2026-04-29"
        assert summary["version_status"] == "ready_for_human_review"
        assert summary["human_review_candidates"] == ["signal_family.high_conviction_bullish_equity"]

    def test_zero_family_candidates_supported(self, tmp_path: Path):
        result = run_daily_governance(
            DailyGovernanceRequest(
                run_date="2026-04-29",
                output_root=tmp_path,
                version_request=_version_request(),
                family_requests=(),
            )
        )
        assert result.status == "completed_with_warnings"
        assert result.family_count == 0

    def test_degraded_mode_for_invalid_output_root(self, tmp_path: Path):
        file_path = tmp_path / "not-a-directory"
        file_path.write_text("x", encoding="utf-8")
        result = run_daily_governance(
            DailyGovernanceRequest(
                run_date="2026-04-29",
                output_root=file_path,
                version_request=_version_request(),
                family_requests=(_family_request(),),
            )
        )
        assert result.status == "governance_degraded"
        assert "output_path_not_directory" in result.warnings

    def test_invalid_run_date_rejected(self, tmp_path: Path):
        try:
            DailyGovernanceRequest(
                run_date="29-04-2026",
                output_root=tmp_path,
                version_request=_version_request(),
                family_requests=(),
            )
        except DailyGovernanceRunError as exc:
            assert "run_date must use YYYY-MM-DD" in str(exc)
        else:
            raise AssertionError("DailyGovernanceRunError was not raised")

    def test_blocked_version_prevents_family_human_review_candidate(self, tmp_path: Path):
        # Version is blocked because evidence is missing (P25 absent)
        blocked_version_req = VersionReadinessRequest(
            metadata=VersionMetadata(
                branch="codex/quant-governance-p20-p30",
                commit="c3abd67",
                dirty=False,
                frozen_version_label="",
            ),
            evidence_items=tuple(
                EvidenceItem(phase_id=pid, present=True, summary=f"{pid} ok")
                for pid in REQUIRED_VERSION_PHASE_IDS
                if pid != "P25"  # P25 missing → blocked_missing_evidence
            ),
            test_evidence=(
                TestEvidence(
                    command="pytest suite",
                    status="passed",
                    passed_count=10,
                    failed_count=0,
                    raw_summary="10 passed",
                ),
            ),
            rollback_plan=RollbackPlan(
                rollback_owner="operator",
                rollback_trigger="blocker",
                description="Return to prior.",
            ),
            monitoring_sla=MonitoringSLA(
                monitoring_cadence="daily",
                alert_routing="operator",
                description="Daily review.",
            ),
            version_freeze_proposal=None,
        )
        # Caller mistakenly says parent is ready — daily governance must override this
        wrong_family_req = SignalFamilyReadinessRequest(
            parent_version_status="ready_for_human_review",  # wrong!
            family_type="signal_family",
            family_namespace="signal_family.demo",
            evidence=FamilyEvidence(
                p20_p23_present=True,
                maturity=True,
                edge_summary="looks good",
                risk_summary="clean",
            ),
        )
        result = run_daily_governance(
            DailyGovernanceRequest(
                run_date="2026-04-29",
                output_root=tmp_path,
                version_request=blocked_version_req,
                family_requests=(wrong_family_req,),
            )
        )
        # Version is blocked → no family may be a human review candidate
        assert result.human_review_candidates == ()
        # Both version and family must appear in blocked_items
        assert "version:blocked_missing_evidence" in result.blocked_items
        assert "signal_family.demo:blocked_system_not_ready" in result.blocked_items
        # daily_summary.json must reflect the correct derived statuses
        summary = json.loads(
            (tmp_path / "2026-04-29" / "daily_summary.json").read_text(encoding="utf-8")
        )
        assert summary["human_review_candidates"] == []
        assert any("blocked_system_not_ready" in item for item in summary["blocked_items"])
