"""Tests for P33 signal-family edge review."""

from __future__ import annotations

from agent.research_v1.evidence_artifact_registry import ArtifactRecord, EvidenceArtifactRegistryReport
from agent.research_v1.signal_family_edge_review import (
    EdgeReviewPolicy,
    SignalFamilyEdgeReviewRequest,
    build_signal_family_edge_review,
)


def _record(
    artifact_type: str,
    phase_id: str,
    status: str = "present",
    family_namespace: str = "factor_family.quality",
    details: dict | None = None,
) -> ArtifactRecord:
    return ArtifactRecord(
        artifact_id=f"{artifact_type}:demo",
        artifact_type=artifact_type,
        phase_id=phase_id,
        path=f"/tmp/{artifact_type}.json",
        present=status == "present",
        status=status,
        family_namespace=family_namespace,
        created_at="2026-04-29",
        freshness_days=0,
        summary=status,
        details=details or {},
    )


def _registry(records: tuple[ArtifactRecord, ...]) -> EvidenceArtifactRegistryReport:
    return EvidenceArtifactRegistryReport(
        status="complete",
        run_date="2026-04-29",
        scan_roots=("/tmp",),
        artifact_records=records,
        missing_artifact_types=(),
        stale_artifact_ids=(),
        invalid_artifact_ids=(),
        coverage_by_phase=(("P22", 1.0),),
        coverage_by_family=(("factor_family.quality", 1.0),),
        next_actions=(),
        warnings=(),
    )


def _policy() -> EdgeReviewPolicy:
    return EdgeReviewPolicy(
        minimum_observation_count=20,
        require_net_return_basis=True,
        require_execution_realism=True,
    )


def test_missing_p22_diagnostics_blocks_factor_review():
    report = build_signal_family_edge_review(
        SignalFamilyEdgeReviewRequest(
            family_namespace="factor_family.quality",
            family_type="factor_family",
            registry_report=_registry(()),
            policy=_policy(),
        )
    )
    assert report.status == "blocked_missing_evidence"
    assert "missing_artifact:p22_validity_report" in report.missing_artifacts


def test_gross_only_edge_is_not_ready_for_human_review():
    report = build_signal_family_edge_review(
        SignalFamilyEdgeReviewRequest(
            family_namespace="factor_family.quality",
            family_type="factor_family",
            registry_report=_registry((
                _record("p22_validity_report", "P22", details={
                    "return_basis": "gross_return_pct",
                    "observation_count": 100,
                    "net_ic_positive": False,
                }),
                _record("p28_execution_realism_report", "P28"),
            )),
            policy=_policy(),
        )
    )
    assert report.status == "blocked_integrity_failure"
    assert "net_return_basis_required" in report.integrity_blockers


def test_lookahead_blocker_blocks_review():
    report = build_signal_family_edge_review(
        SignalFamilyEdgeReviewRequest(
            family_namespace="factor_family.quality",
            family_type="factor_family",
            registry_report=_registry((
                _record("p22_validity_report", "P22", details={
                    "return_basis": "net_return_pct",
                    "observation_count": 100,
                    "lookahead_blocker": True,
                }),
                _record("p28_execution_realism_report", "P28"),
            )),
            policy=_policy(),
        )
    )
    assert report.status == "blocked_integrity_failure"
    assert "lookahead_blocker_present" in report.integrity_blockers


def test_execution_cost_blocker_blocks_positive_review():
    report = build_signal_family_edge_review(
        SignalFamilyEdgeReviewRequest(
            family_namespace="factor_family.quality",
            family_type="factor_family",
            registry_report=_registry((
                _record("p22_validity_report", "P22", details={
                    "return_basis": "net_return_pct",
                    "observation_count": 100,
                    "net_ic_positive": True,
                }),
                _record("p28_execution_realism_report", "P28", details={
                    "stress_cost_exceeds_edge": True,
                }),
            )),
            policy=_policy(),
        )
    )
    assert report.status == "blocked_integrity_failure"
    assert "execution_cost_exceeds_edge" in report.execution_cost_warnings


def test_mature_net_evidence_ready_for_human_review():
    report = build_signal_family_edge_review(
        SignalFamilyEdgeReviewRequest(
            family_namespace="factor_family.quality",
            family_type="factor_family",
            registry_report=_registry((
                _record("p22_validity_report", "P22", details={
                    "return_basis": "net_return_pct",
                    "observation_count": 100,
                    "net_ic_positive": True,
                }),
                _record("p28_execution_realism_report", "P28", details={
                    "stress_cost_exceeds_edge": False,
                }),
            )),
            policy=_policy(),
        )
    )
    assert report.status == "ready_for_human_review"
    assert report.allowed_next_step == "prepare_human_review"


def test_missing_p28_blocks_positive_review_when_required():
    # P28 is absent entirely — with require_execution_realism=True,
    # this must block a positive human-review status.
    report = build_signal_family_edge_review(
        SignalFamilyEdgeReviewRequest(
            family_namespace="factor_family.quality",
            family_type="factor_family",
            registry_report=_registry((
                _record("p22_validity_report", "P22", details={
                    "return_basis": "net_return_pct",
                    "observation_count": 100,
                    "net_ic_positive": True,
                }),
                # no p28_execution_realism_report
            )),
            policy=_policy(),
        )
    )
    assert report.status == "blocked_missing_evidence"
    assert "missing_artifact:p28_execution_realism_report" in report.missing_artifacts


def test_stale_p25_artifact_blocks_shadow_model():
    # Stale P25 shadow training result must not pass the evidence gate.
    report = build_signal_family_edge_review(
        SignalFamilyEdgeReviewRequest(
            family_namespace="shadow_meta_model.xgboost_dry_candidate",
            family_type="shadow_model_family",
            registry_report=_registry((
                _record("p22_validity_report", "P22",
                    family_namespace="shadow_meta_model.xgboost_dry_candidate",
                    details={
                        "return_basis": "net_return_pct",
                        "observation_count": 100,
                        "net_ic_positive": True,
                    }),
                _record("p25_shadow_training_result", "P25",
                    family_namespace="shadow_meta_model.xgboost_dry_candidate",
                    status="stale"),  # stale, not present
                _record("p26_shadow_portfolio_report", "P26",
                    family_namespace="shadow_meta_model.xgboost_dry_candidate"),
                _record("p28_execution_realism_report", "P28",
                    family_namespace="shadow_meta_model.xgboost_dry_candidate"),
            )),
            policy=_policy(),
        )
    )
    assert report.status == "blocked_missing_evidence"
    assert "missing_artifact:p25_shadow_training_result" in report.missing_artifacts


def test_invalid_p26_artifact_blocks_shadow_model():
    # Invalid P26 portfolio report must not pass the evidence gate.
    report = build_signal_family_edge_review(
        SignalFamilyEdgeReviewRequest(
            family_namespace="shadow_meta_model.xgboost_dry_candidate",
            family_type="shadow_model_family",
            registry_report=_registry((
                _record("p22_validity_report", "P22",
                    family_namespace="shadow_meta_model.xgboost_dry_candidate",
                    details={
                        "return_basis": "net_return_pct",
                        "observation_count": 100,
                        "net_ic_positive": True,
                    }),
                _record("p25_shadow_training_result", "P25",
                    family_namespace="shadow_meta_model.xgboost_dry_candidate"),
                _record("p26_shadow_portfolio_report", "P26",
                    family_namespace="shadow_meta_model.xgboost_dry_candidate",
                    status="invalid"),  # invalid, not present
                _record("p28_execution_realism_report", "P28",
                    family_namespace="shadow_meta_model.xgboost_dry_candidate"),
            )),
            policy=_policy(),
        )
    )
    assert report.status == "blocked_missing_evidence"
    assert "missing_artifact:p26_shadow_portfolio_report" in report.missing_artifacts


def test_shadow_model_promotion_forbidden_reason_present():
    report = build_signal_family_edge_review(
        SignalFamilyEdgeReviewRequest(
            family_namespace="shadow_meta_model.xgboost_dry_candidate",
            family_type="shadow_model_family",
            registry_report=_registry((
                _record("p22_validity_report", "P22", family_namespace="shadow_meta_model.xgboost_dry_candidate", details={
                    "return_basis": "net_return_pct",
                    "observation_count": 100,
                    "net_ic_positive": True,
                }),
                _record("p25_shadow_training_result", "P25", family_namespace="shadow_meta_model.xgboost_dry_candidate"),
                _record("p26_shadow_portfolio_report", "P26", family_namespace="shadow_meta_model.xgboost_dry_candidate"),
                _record("p28_execution_realism_report", "P28", family_namespace="shadow_meta_model.xgboost_dry_candidate"),
            )),
            policy=_policy(),
        )
    )
    assert "shadow_outputs_must_not_promote_to_production" in report.promotion_forbidden_reasons
