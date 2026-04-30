"""Tests for P34 boss governance daily brief."""

from __future__ import annotations

import json
from pathlib import Path

from agent.research_v1.boss_governance_brief import (
    BossGovernanceBriefRequest,
    build_boss_governance_daily_brief,
    write_boss_governance_daily_brief,
)
from agent.research_v1.daily_governance import DailyGovernanceResult
from agent.research_v1.evidence_artifact_registry import EvidenceArtifactRegistryReport
from agent.research_v1.evidence_generation_dry_run import ControlledEvidenceGenerationReport
from agent.research_v1.signal_family_edge_review import SignalFamilyEdgeReviewReport


def _daily_result(status: str = "completed") -> DailyGovernanceResult:
    return DailyGovernanceResult(
        status=status,
        run_date="2026-04-29",
        output_dir="/tmp/output/governance/2026-04-29",
        version_status="ready_for_human_review",
        family_count=1,
        human_review_candidates=("factor_family.quality",),
        blocked_items=(),
        warnings=(),
    )


def _registry_report(status: str = "complete") -> EvidenceArtifactRegistryReport:
    return EvidenceArtifactRegistryReport(
        status=status,
        run_date="2026-04-29",
        scan_roots=("/tmp",),
        artifact_records=(),
        missing_artifact_types=("p25_shadow_training_result",) if status != "complete" else (),
        stale_artifact_ids=(),
        invalid_artifact_ids=(),
        coverage_by_phase=(("P31", 1.0),),
        coverage_by_family=(("factor_family.quality", 1.0),),
        next_actions=("collect_missing_artifacts",) if status != "complete" else (),
        warnings=(),
    )


def _generation_report() -> ControlledEvidenceGenerationReport:
    return ControlledEvidenceGenerationReport(
        status="dry_run_complete",
        run_date="2026-04-29",
        requested_artifacts=(),
        allowed_requests=(),
        blocked_requests=(),
        required_inputs_by_artifact=(),
        dry_run_manifest_path="",
        next_actions=(),
        warnings=(),
    )


def _edge_report(status: str = "ready_for_human_review") -> SignalFamilyEdgeReviewReport:
    return SignalFamilyEdgeReviewReport(
        family_namespace="factor_family.quality",
        family_type="factor_family",
        status=status,
        edge_evidence_summary="net evidence positive",
        risk_evidence_summary="execution cost acceptable",
        integrity_blockers=(),
        missing_artifacts=(),
        degradation_warnings=(),
        execution_cost_warnings=(),
        allowed_next_step="prepare_human_review",
        promotion_forbidden_reasons=(),
        human_review_questions=("Review quality family evidence.",),
    )


def test_brief_includes_system_health_and_review_candidate():
    brief = build_boss_governance_daily_brief(
        BossGovernanceBriefRequest(
            run_date="2026-04-29",
            daily_governance_result=_daily_result(),
            registry_report=_registry_report(),
            generation_report=_generation_report(),
            edge_review_reports=(_edge_report(),),
        )
    )
    assert brief.overall_status == "governance_ready_for_review"
    assert "factor_family.quality" in brief.family_review_candidates
    assert "ready_for_human_review" in brief.system_health_summary


def test_incomplete_registry_produces_governance_incomplete():
    brief = build_boss_governance_daily_brief(
        BossGovernanceBriefRequest(
            run_date="2026-04-29",
            daily_governance_result=_daily_result(),
            registry_report=_registry_report(status="incomplete_missing_artifacts"),
            generation_report=_generation_report(),
            edge_review_reports=(_edge_report(status="shadow_observation_only"),),
        )
    )
    assert brief.overall_status == "governance_incomplete"
    assert "p25_shadow_training_result" in brief.missing_evidence_summary


def test_degraded_daily_input_produces_governance_degraded():
    brief = build_boss_governance_daily_brief(
        BossGovernanceBriefRequest(
            run_date="2026-04-29",
            daily_governance_result=_daily_result(status="governance_degraded"),
            registry_report=_registry_report(),
            generation_report=_generation_report(),
            edge_review_reports=(),
        )
    )
    assert brief.overall_status == "governance_degraded"


def test_brief_markdown_excludes_trading_instructions(tmp_path: Path):
    brief = build_boss_governance_daily_brief(
        BossGovernanceBriefRequest(
            run_date="2026-04-29",
            daily_governance_result=_daily_result(),
            registry_report=_registry_report(),
            generation_report=_generation_report(),
            edge_review_reports=(_edge_report(),),
        )
    )
    paths = write_boss_governance_daily_brief(brief, tmp_path / "2026-04-29")
    text = paths["markdown"].read_text(encoding="utf-8").lower()
    forbidden = ("buy this now", "sell this now", "production approved", "follow this trade", "guaranteed edge")
    assert not any(term in text for term in forbidden)
    parsed = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert parsed["overall_status"] == "governance_ready_for_review"
