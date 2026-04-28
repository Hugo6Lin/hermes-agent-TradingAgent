"""P32-B controlled evidence generation dry-run manifest."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent.research_v1.evidence_artifact_registry import EXPECTED_ARTIFACT_TYPES


REQUIRED_INPUTS_BY_ARTIFACT: dict[str, tuple[str, ...]] = {
    "p22_validity_report": (
        "factor_snapshot_rows",
        "forward_return_observations",
        "data_integrity_policy",
    ),
    "p25_training_dataset_result": (
        "point_in_time_factor_snapshots",
        "target_definition",
        "feature_namespace",
    ),
    "p25_shadow_training_result": (
        "training_dataset_result",
        "walk_forward_split_manifest",
        "p24_experiment_manifest",
    ),
    "p28_execution_realism_report": (
        "trade_intents",
        "liquidity_inputs",
        "alpha_edge_estimate",
    ),
}

ALLOWED_GENERATION_STATUSES = frozenset({
    "dry_run_complete",
    "blocked_unsafe_request",
    "blocked_missing_inputs",
})


@dataclass(frozen=True)
class EvidenceGenerationRequest:
    artifact_type: str
    phase_id: str
    family_namespace: str
    requested_output_dir: str
    input_refs: dict[str, Any]
    allow_actual_execution: bool = False
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_type": self.artifact_type,
            "phase_id": self.phase_id,
            "family_namespace": self.family_namespace,
            "requested_output_dir": self.requested_output_dir,
            "input_refs": dict(self.input_refs),
            "allow_actual_execution": self.allow_actual_execution,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class EvidenceGenerationDecision:
    request: EvidenceGenerationRequest
    allowed: bool
    blocked_reasons: tuple[str, ...]
    required_inputs: tuple[str, ...]

    @property
    def artifact_type(self) -> str:
        return self.request.artifact_type

    def to_dict(self) -> dict[str, Any]:
        return {
            "request": self.request.to_dict(),
            "allowed": self.allowed,
            "blocked_reasons": list(self.blocked_reasons),
            "required_inputs": list(self.required_inputs),
        }


@dataclass(frozen=True)
class ControlledEvidenceGenerationReport:
    status: str
    run_date: str
    requested_artifacts: tuple[str, ...]
    allowed_requests: tuple[EvidenceGenerationDecision, ...]
    blocked_requests: tuple[EvidenceGenerationDecision, ...]
    required_inputs_by_artifact: tuple[tuple[str, tuple[str, ...]], ...]
    dry_run_manifest_path: str
    next_actions: tuple[str, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "run_date": self.run_date,
            "requested_artifacts": list(self.requested_artifacts),
            "allowed_requests": [item.to_dict() for item in self.allowed_requests],
            "blocked_requests": [item.to_dict() for item in self.blocked_requests],
            "required_inputs_by_artifact": {
                key: list(value) for key, value in self.required_inputs_by_artifact
            },
            "dry_run_manifest_path": self.dry_run_manifest_path,
            "next_actions": list(self.next_actions),
            "warnings": list(self.warnings),
        }


def _validate_request(request: EvidenceGenerationRequest) -> EvidenceGenerationDecision:
    """Validate a single evidence generation request in dry-run mode."""
    blocked: list[str] = []
    required: tuple[str, ...] = ()

    # Unsafe: actual execution requested
    if request.allow_actual_execution:
        blocked.append("actual_execution_not_allowed_in_p32_b")

    # Unsafe: unknown artifact type
    if request.artifact_type not in EXPECTED_ARTIFACT_TYPES:
        blocked.append(f"unknown_artifact_type:{request.artifact_type}")

    # Unsafe: production namespace output
    if request.requested_output_dir and "output/governance" not in request.requested_output_dir:
        blocked.append("requested_output_dir_must_be_under_output_governance")

    # Missing inputs check
    if request.artifact_type in REQUIRED_INPUTS_BY_ARTIFACT:
        required = REQUIRED_INPUTS_BY_ARTIFACT[request.artifact_type]
        for req_input in required:
            if req_input not in request.input_refs:
                blocked.append(f"missing_required_input:{req_input}")

    allowed = len(blocked) == 0
    return EvidenceGenerationDecision(
        request=request,
        allowed=allowed,
        blocked_reasons=tuple(blocked),
        required_inputs=required,
    )


def build_controlled_evidence_generation_report(
    run_date: str,
    requests: tuple[EvidenceGenerationRequest, ...],
    dry_run_manifest_path: str = "",
) -> ControlledEvidenceGenerationReport:
    decisions = [_validate_request(r) for r in requests]
    allowed = tuple(d for d in decisions if d.allowed)
    blocked = tuple(d for d in decisions if not d.allowed)

    # Status priority: unsafe > missing inputs > dry_run_complete
    UNSAFE_REASONS = frozenset({
        "actual_execution_not_allowed_in_p32_b",
        "unknown_artifact_type:",
        "requested_output_dir_must_be_under_output_governance",
    })
    if any(
        any(reason.startswith(unsafe) for unsafe in UNSAFE_REASONS)
        for d in blocked
        for reason in d.blocked_reasons
    ):
        status = "blocked_unsafe_request"
    elif blocked:
        status = "blocked_missing_inputs"
    else:
        status = "dry_run_complete"

    requested_artifacts = tuple(r.artifact_type for r in requests)

    return ControlledEvidenceGenerationReport(
        status=status,
        run_date=run_date,
        requested_artifacts=requested_artifacts,
        allowed_requests=allowed,
        blocked_requests=blocked,
        required_inputs_by_artifact=tuple(
            (atype, REQUIRED_INPUTS_BY_ARTIFACT[atype])
            for atype in REQUIRED_INPUTS_BY_ARTIFACT
            if atype in requested_artifacts
        ),
        dry_run_manifest_path=dry_run_manifest_path,
        next_actions=(
            ("submit_safe_requests_for_review",) if allowed else
            ("fix_blocked_requests",) if blocked else
            ("no_requests_to_process",)
        ),
        warnings=(
            ("actual_execution_requests_require_future_phase",) if
            any("actual_execution_not_allowed" in str(d.blocked_reasons) for d in blocked)
            else ()
        ),
    )


def write_evidence_generation_dry_run_manifest(
    report: ControlledEvidenceGenerationReport,
    output_dir: Path,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "evidence_generation_dry_run.json"
    md_path = output_dir / "evidence_generation_dry_run.md"

    _write_json(json_path, report.to_dict())
    _write_markdown(md_path, report)

    return {"json": json_path, "markdown": md_path}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _write_markdown(path: Path, report: ControlledEvidenceGenerationReport) -> None:
    data = report.to_dict()
    lines = [
        "# Evidence Generation Dry Run",
        "",
        f"Status: `{data['status']}`",
        f"Run date: `{data['run_date']}`",
        "",
        "## Allowed Requests",
    ]
    if data["allowed_requests"]:
        for item in data["allowed_requests"]:
            lines.append(f"- `{item['request']['artifact_type']}` — {item['request']['family_namespace']}")
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Blocked Requests")
    if data["blocked_requests"]:
        for item in data["blocked_requests"]:
            lines.append(f"- `{item['request']['artifact_type']}` — {item['request']['family_namespace']}")
            for reason in item["blocked_reasons"]:
                lines.append(f"  - {reason}")
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Next Actions")
    for action in data["next_actions"]:
        lines.append(f"- {action}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
