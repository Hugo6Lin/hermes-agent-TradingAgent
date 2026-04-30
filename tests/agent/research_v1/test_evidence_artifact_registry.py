"""Tests for P32-A evidence artifact registry."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent.research_v1.evidence_artifact_registry import (
    EXPECTED_ARTIFACT_TYPES,
    ArtifactDefinition,
    ArtifactRecord,
    EvidenceArtifactRegistryError,
    EvidenceArtifactRegistryRequest,
    build_evidence_artifact_registry,
)


def _definition(
    artifact_type: str = "p31_daily_governance",
    relative_path: str = "2026-04-29/daily_summary.json",
    family_namespace: str = "",
) -> ArtifactDefinition:
    return ArtifactDefinition(
        artifact_type=artifact_type,
        relative_path=relative_path,
        family_namespace=family_namespace,
        required=True,
    )


def test_expected_artifact_types_include_p31_daily_governance():
    assert "p31_daily_governance" in EXPECTED_ARTIFACT_TYPES
    assert "p22_validity_report" in EXPECTED_ARTIFACT_TYPES
    assert "p25_shadow_training_result" in EXPECTED_ARTIFACT_TYPES


def test_present_artifact_is_recorded_as_present(tmp_path: Path):
    artifact = tmp_path / "2026-04-29" / "daily_summary.json"
    artifact.parent.mkdir()
    artifact.write_text('{"status": "completed"}', encoding="utf-8")
    report = build_evidence_artifact_registry(
        EvidenceArtifactRegistryRequest(
            run_date="2026-04-29",
            scan_roots=(tmp_path,),
            expected_artifacts=(_definition(),),
            freshness_policy_days=7,
        )
    )
    assert report.status == "complete"
    assert report.artifact_records[0].status == "present"
    assert report.coverage_by_phase == (("P31", 1.0),)


def test_missing_expected_artifact_is_recorded_as_missing(tmp_path: Path):
    report = build_evidence_artifact_registry(
        EvidenceArtifactRegistryRequest(
            run_date="2026-04-29",
            scan_roots=(tmp_path,),
            expected_artifacts=(_definition(),),
            freshness_policy_days=7,
        )
    )
    assert report.status == "incomplete_missing_artifacts"
    assert report.missing_artifact_types == ("p31_daily_governance",)
    assert report.artifact_records[0].status == "missing"


def test_stale_artifact_is_recorded_as_stale(tmp_path: Path):
    artifact = tmp_path / "2026-04-01" / "daily_summary.json"
    artifact.parent.mkdir()
    artifact.write_text("{}", encoding="utf-8")
    report = build_evidence_artifact_registry(
        EvidenceArtifactRegistryRequest(
            run_date="2026-04-29",
            scan_roots=(tmp_path,),
            expected_artifacts=(
                _definition(relative_path="2026-04-01/daily_summary.json"),
            ),
            freshness_policy_days=7,
        )
    )
    assert report.status == "incomplete_stale_artifacts"
    assert report.artifact_records[0].status == "stale"
    assert report.stale_artifact_ids == ("p31_daily_governance:2026-04-01/daily_summary.json",)


def test_invalid_artifact_path_is_recorded_as_invalid(tmp_path: Path):
    artifact_dir = tmp_path / "2026-04-29" / "daily_summary.json"
    artifact_dir.mkdir(parents=True)
    report = build_evidence_artifact_registry(
        EvidenceArtifactRegistryRequest(
            run_date="2026-04-29",
            scan_roots=(tmp_path,),
            expected_artifacts=(_definition(),),
            freshness_policy_days=7,
        )
    )
    assert report.status == "invalid_registry"
    assert report.artifact_records[0].status == "invalid"
    assert report.invalid_artifact_ids == ("p31_daily_governance:2026-04-29/daily_summary.json",)


def test_coverage_by_family_is_computed(tmp_path: Path):
    artifact = tmp_path / "families" / "quality.json"
    artifact.parent.mkdir()
    artifact.write_text("{}", encoding="utf-8")
    report = build_evidence_artifact_registry(
        EvidenceArtifactRegistryRequest(
            run_date="2026-04-29",
            scan_roots=(tmp_path,),
            expected_artifacts=(
                _definition(
                    artifact_type="p22_validity_report",
                    relative_path="families/quality.json",
                    family_namespace="factor_family.quality",
                ),
            ),
            freshness_policy_days=30,
        )
    )
    assert report.coverage_by_family == (("factor_family.quality", 1.0),)


def test_artifact_record_json_round_trip():
    record = ArtifactRecord(
        artifact_id="p31_daily_governance:2026-04-29/daily_summary.json",
        artifact_type="p31_daily_governance",
        phase_id="P31",
        path="/tmp/output/governance/2026-04-29/daily_summary.json",
        present=True,
        status="present",
        family_namespace="",
        created_at="2026-04-29",
        freshness_days=0,
        summary="present",
        details={},
    )
    parsed = json.loads(json.dumps(record.to_dict()))
    assert parsed["artifact_type"] == "p31_daily_governance"


def test_unknown_artifact_type_rejected():
    with pytest.raises(EvidenceArtifactRegistryError, match="artifact_type must be one of"):
        ArtifactDefinition(
            artifact_type="unknown_artifact",
            relative_path="x.json",
            family_namespace="",
            required=True,
        )
