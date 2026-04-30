"""Tests for P32-B controlled evidence generation dry run."""

from __future__ import annotations

import json
from pathlib import Path

from agent.research_v1.evidence_generation_dry_run import (
    EvidenceGenerationRequest,
    build_controlled_evidence_generation_report,
    write_evidence_generation_dry_run_manifest,
)


def test_known_artifact_with_required_inputs_is_allowed(tmp_path: Path):
    report = build_controlled_evidence_generation_report(
        run_date="2026-04-29",
        requests=(
            EvidenceGenerationRequest(
                artifact_type="p22_validity_report",
                phase_id="P22",
                family_namespace="factor_family.quality",
                requested_output_dir=str(tmp_path / "output/governance/2026-04-29"),
                input_refs={
                    "factor_snapshot_rows": "snapshots.json",
                    "forward_return_observations": "returns.json",
                    "data_integrity_policy": "strict",
                },
                allow_actual_execution=False,
            ),
        ),
    )
    assert report.status == "dry_run_complete"
    assert report.allowed_requests[0].artifact_type == "p22_validity_report"


def test_missing_required_inputs_blocks_request(tmp_path: Path):
    report = build_controlled_evidence_generation_report(
        run_date="2026-04-29",
        requests=(
            EvidenceGenerationRequest(
                artifact_type="p25_shadow_training_result",
                phase_id="P25",
                family_namespace="shadow_meta_model.xgboost_dry_candidate",
                requested_output_dir=str(tmp_path / "output/governance/2026-04-29"),
                input_refs={"training_dataset_result": "dataset.json"},
                allow_actual_execution=False,
            ),
        ),
    )
    assert report.status == "blocked_missing_inputs"
    assert report.blocked_requests[0].blocked_reasons == (
        "missing_required_input:walk_forward_split_manifest",
        "missing_required_input:p24_experiment_manifest",
    )


def test_unknown_artifact_type_blocks_request(tmp_path: Path):
    report = build_controlled_evidence_generation_report(
        run_date="2026-04-29",
        requests=(
            EvidenceGenerationRequest(
                artifact_type="unknown_artifact",
                phase_id="P99",
                family_namespace="",
                requested_output_dir=str(tmp_path),
                input_refs={},
                allow_actual_execution=False,
            ),
        ),
    )
    assert report.status == "blocked_unsafe_request"
    assert "unknown_artifact_type:unknown_artifact" in report.blocked_requests[0].blocked_reasons


def test_allow_actual_execution_is_rejected(tmp_path: Path):
    report = build_controlled_evidence_generation_report(
        run_date="2026-04-29",
        requests=(
            EvidenceGenerationRequest(
                artifact_type="p28_execution_realism_report",
                phase_id="P28",
                family_namespace="signal_family.demo",
                requested_output_dir=str(tmp_path),
                input_refs={
                    "trade_intents": "intents.json",
                    "liquidity_inputs": "liquidity.json",
                    "alpha_edge_estimate": "50bps",
                },
                allow_actual_execution=True,
            ),
        ),
    )
    assert report.status == "blocked_unsafe_request"
    assert "actual_execution_not_allowed_in_p32_b" in report.blocked_requests[0].blocked_reasons


def test_production_namespace_output_is_rejected(tmp_path: Path):
    report = build_controlled_evidence_generation_report(
        run_date="2026-04-29",
        requests=(
            EvidenceGenerationRequest(
                artifact_type="p22_validity_report",
                phase_id="P22",
                family_namespace="factor_family.quality",
                requested_output_dir="production/config",
                input_refs={
                    "factor_snapshot_rows": "snapshots.json",
                    "forward_return_observations": "returns.json",
                    "data_integrity_policy": "strict",
                },
                allow_actual_execution=False,
            ),
        ),
    )
    assert report.status == "blocked_unsafe_request"
    assert "requested_output_dir_must_be_under_output_governance" in report.blocked_requests[0].blocked_reasons


def test_dry_run_manifest_writes_json_and_markdown(tmp_path: Path):
    report = build_controlled_evidence_generation_report(
        run_date="2026-04-29",
        requests=(),
    )
    paths = write_evidence_generation_dry_run_manifest(report, tmp_path / "2026-04-29")
    assert paths["json"].name == "evidence_generation_dry_run.json"
    assert paths["markdown"].name == "evidence_generation_dry_run.md"
    parsed = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert parsed["status"] == "dry_run_complete"
