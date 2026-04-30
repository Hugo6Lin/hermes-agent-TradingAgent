"""Tests for P35 governance runtime."""

from __future__ import annotations

import json
from pathlib import Path

from agent.research_v1.governance_runtime import (
    GovernanceRuntimeRequest,
    run_governance_runtime,
)


def _write_valid_config(path: Path) -> Path:
    payload = {
        "version_readiness": {
            "version_id": "p35-local",
            "branch": "codex/quant-governance-p20-p30",
            "commit": "local-test",
            "evidence": {
                "p20_p30_regression_passed": True,
                "p31_p34_regression_passed": True,
                "doc_standards_passed": True,
            },
            "notes": "P35 local runtime test",
        },
        "signal_families": [],
        "expected_artifacts": [],
        "generation_requests": [],
        "edge_reviews": [],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_runtime_writes_governance_summary_and_boss_brief(tmp_path: Path):
    config_path = _write_valid_config(tmp_path / "governance_config.json")
    output_root = tmp_path / "output" / "governance"

    result = run_governance_runtime(
        GovernanceRuntimeRequest(
            run_date="2026-04-30",
            repo_root=tmp_path,
            output_root=output_root,
            config_path=config_path,
            freshness_policy_days=7,
        )
    )

    assert result.status in {"completed", "completed_with_warnings"}
    assert result.run_date == "2026-04-30"
    assert result.boss_brief_status in {
        "governance_ready_for_review",
        "governance_incomplete",
        "governance_degraded",
        "no_review_candidates",
    }

    output_dir = output_root / "2026-04-30"
    assert (output_dir / "daily_summary.json").exists()
    assert (output_dir / "evidence_generation_dry_run.json").exists()
    assert (output_dir / "boss_daily_brief.json").exists()
    assert (output_dir / "governance_runtime_summary.json").exists()

    summary = json.loads((output_dir / "governance_runtime_summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == result.status
    assert "boss_daily_brief.json" in "\n".join(summary["artifacts_written"])


def test_runtime_blocks_invalid_config(tmp_path: Path):
    config_path = tmp_path / "broken.json"
    config_path.write_text("{not-json", encoding="utf-8")

    result = run_governance_runtime(
        GovernanceRuntimeRequest(
            run_date="2026-04-30",
            repo_root=tmp_path,
            output_root=tmp_path / "output" / "governance",
            config_path=config_path,
            freshness_policy_days=7,
        )
    )

    assert result.status == "blocked_invalid_config"
    assert result.warnings
    assert "invalid_config" in result.warnings[0]


def test_runtime_preserves_dry_run_boundary(tmp_path: Path):
    config_path = tmp_path / "governance_config.json"
    payload = {
        "version_readiness": {
            "version_id": "p35-local",
            "branch": "codex/quant-governance-p20-p30",
            "commit": "local-test",
            "evidence": {
                "p20_p30_regression_passed": True,
                "p31_p34_regression_passed": True,
                "doc_standards_passed": True,
            },
            "notes": "P35 dry-run boundary test",
        },
        "signal_families": [],
        "expected_artifacts": [],
        "generation_requests": [
            {
                "artifact_type": "p28_execution_realism_report",
                "phase_id": "P28",
                "family_namespace": "factor_family.quality",
                "requested_output_dir": "output/governance/2026-04-30",
                "input_refs": {},
                "allow_actual_execution": True,
                "notes": "must remain blocked",
            }
        ],
        "edge_reviews": [],
    }
    config_path.write_text(json.dumps(payload), encoding="utf-8")

    result = run_governance_runtime(
        GovernanceRuntimeRequest(
            run_date="2026-04-30",
            repo_root=tmp_path,
            output_root=tmp_path / "output" / "governance",
            config_path=config_path,
            freshness_policy_days=7,
        )
    )

    assert result.generation_status == "blocked_unsafe_request"
    manifest_path = tmp_path / "output" / "governance" / "2026-04-30" / "evidence_generation_dry_run.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["blocked_requests"][0]["blocked_reasons"] == [
        "actual_execution_not_allowed_in_p32_b",
        "missing_required_input:trade_intents",
        "missing_required_input:liquidity_inputs",
        "missing_required_input:alpha_edge_estimate",
    ]


def test_runtime_blocks_version_when_configured_checks_fail(tmp_path: Path):
    config_path = tmp_path / "governance_config.json"
    payload = {
        "version_readiness": {
            "version_id": "p35-local",
            "branch": "codex/quant-governance-p20-p30",
            "commit": "local-test",
            "evidence": {
                "p20_p30_regression_passed": True,
                "p31_p34_regression_passed": False,
                "doc_standards_passed": False,
            },
            "notes": "P35 blocked test",
        },
        "signal_families": [],
        "expected_artifacts": [],
        "generation_requests": [],
        "edge_reviews": [],
    }
    config_path.write_text(json.dumps(payload), encoding="utf-8")

    result = run_governance_runtime(
        GovernanceRuntimeRequest(
            run_date="2026-04-30",
            repo_root=tmp_path,
            output_root=tmp_path / "output" / "governance",
            config_path=config_path,
            freshness_policy_days=7,
        )
    )

    daily_summary_path = tmp_path / "output" / "governance" / "2026-04-30" / "daily_summary.json"
    summary = json.loads(daily_summary_path.read_text(encoding="utf-8"))
    assert summary["version_status"] == "blocked_test_failures"
    assert result.boss_brief_status != "ready_for_human_review"


def test_runtime_returns_degraded_on_write_failure(tmp_path: Path):
    config_path = _write_valid_config(tmp_path / "governance_config.json")
    output_root = tmp_path / "output" / "governance"
    output_root.mkdir(parents=True)
    (output_root / "2026-04-30").write_text("block directory creation", encoding="utf-8")

    result = run_governance_runtime(
        GovernanceRuntimeRequest(
            run_date="2026-04-30",
            repo_root=tmp_path,
            output_root=output_root,
            config_path=config_path,
            freshness_policy_days=7,
        )
    )

    assert result.status == "governance_degraded"
    assert "write_failure" in result.warnings[0]


def test_runtime_blocks_structurally_invalid_config(tmp_path: Path):
    config_path = tmp_path / "governance_config.json"
    payload = {
        "version_readiness": {
            "version_id": "p35-local",
            "notes": "missing branch and commit",
        },
        "signal_families": [],
        "expected_artifacts": [],
        "generation_requests": [],
        "edge_reviews": [],
    }
    config_path.write_text(json.dumps(payload), encoding="utf-8")

    result = run_governance_runtime(
        GovernanceRuntimeRequest(
            run_date="2026-04-30",
            repo_root=tmp_path,
            output_root=tmp_path / "output" / "governance",
            config_path=config_path,
            freshness_policy_days=7,
        )
    )

    assert result.status == "blocked_invalid_config"
    assert "invalid_config" in result.warnings[0]
