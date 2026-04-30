"""Daily governance run orchestration for Hermes readiness artifacts."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent.research_v1.signal_family_readiness import (
    SignalFamilyReadinessDossier,
    SignalFamilyReadinessRequest,
    build_signal_family_readiness_dossier,
)
from agent.research_v1.version_readiness import (
    VersionReadinessDossier,
    VersionReadinessRequest,
    build_version_readiness_dossier,
)


class DailyGovernanceRunError(ValueError):
    """Raised for invalid daily governance run inputs."""


RUN_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass(frozen=True)
class DailyGovernanceRequest:
    run_date: str
    output_root: Path
    version_request: VersionReadinessRequest
    family_requests: tuple[SignalFamilyReadinessRequest, ...]

    def __post_init__(self) -> None:
        if not RUN_DATE_RE.match(self.run_date):
            raise DailyGovernanceRunError("run_date must use YYYY-MM-DD")


@dataclass(frozen=True)
class DailyGovernanceResult:
    status: str
    run_date: str
    output_dir: str
    version_status: str
    family_count: int
    human_review_candidates: tuple[str, ...]
    blocked_items: tuple[str, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "run_date": self.run_date,
            "output_dir": self.output_dir,
            "version_status": self.version_status,
            "family_count": self.family_count,
            "human_review_candidates": list(self.human_review_candidates),
            "blocked_items": list(self.blocked_items),
            "warnings": list(self.warnings),
        }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _version_markdown(dossier: VersionReadinessDossier) -> str:
    data = dossier.to_dict()
    lines = [
        "# Version Readiness",
        "",
        f"Status: `{data['status']}`",
        f"Branch: `{data['metadata']['branch']}`",
        f"Commit: `{data['metadata']['commit']}`",
        "",
        "## Decision Reasons",
    ]
    lines.extend(f"- {reason}" for reason in data["decision_reasons"])
    lines.append("")
    lines.append("## Warnings")
    lines.extend(f"- {warning}" for warning in data["warnings"])
    return "\n".join(lines) + "\n"


def _families_markdown(dossiers: tuple[SignalFamilyReadinessDossier, ...]) -> str:
    lines = ["# Signal Family Readiness", ""]
    if not dossiers:
        lines.append("No signal family candidates configured.")
        return "\n".join(lines) + "\n"
    for dossier in dossiers:
        data = dossier.to_dict()
        lines.append(f"## {data['family_namespace']}")
        lines.append(f"- Status: `{data['family_status']}`")
        lines.append(f"- Next step: `{data['allowed_next_step']}`")
        lines.append(f"- Edge: {data['edge_evidence_summary']}")
        lines.append(f"- Risk: {data['risk_evidence_summary']}")
        lines.append("")
    return "\n".join(lines)


def _summary_markdown(result: DailyGovernanceResult) -> str:
    data = result.to_dict()
    lines = [
        "# Daily Governance Summary",
        "",
        f"Status: `{data['status']}`",
        f"Run date: `{data['run_date']}`",
        f"Version status: `{data['version_status']}`",
        "",
        "## Human Review Candidates",
    ]
    if data["human_review_candidates"]:
        lines.extend(f"- {item}" for item in data["human_review_candidates"])
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Blocked Items")
    if data["blocked_items"]:
        lines.extend(f"- {item}" for item in data["blocked_items"])
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Warnings")
    if data["warnings"]:
        lines.extend(f"- {item}" for item in data["warnings"])
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def _build_result(
    request: DailyGovernanceRequest,
    output_dir: Path,
    version_dossier: VersionReadinessDossier,
    family_dossiers: tuple[SignalFamilyReadinessDossier, ...],
    warnings: tuple[str, ...],
) -> DailyGovernanceResult:
    human_review_candidates = tuple(
        dossier.family_namespace for dossier in family_dossiers
        if dossier.to_dict()["family_status"] == "ready_for_human_review"
    )
    blocked_items = []
    if version_dossier.to_dict()["status"].startswith("blocked_"):
        blocked_items.append(f"version:{version_dossier.to_dict()['status']}")
    for dossier in family_dossiers:
        family_data = dossier.to_dict()
        if family_data["family_status"].startswith("blocked_"):
            blocked_items.append(f"{family_data['family_namespace']}:{family_data['family_status']}")

    status = "completed"
    all_warnings = list(warnings)
    all_warnings.extend(version_dossier.warnings)
    for dossier in family_dossiers:
        all_warnings.extend(dossier.degradation_warnings)
    if all_warnings:
        status = "completed_with_warnings"

    return DailyGovernanceResult(
        status=status,
        run_date=request.run_date,
        output_dir=str(output_dir),
        version_status=version_dossier.to_dict()["status"],
        family_count=len(family_dossiers),
        human_review_candidates=human_review_candidates,
        blocked_items=tuple(blocked_items),
        warnings=tuple(dict.fromkeys(all_warnings)),
    )


def run_daily_governance(request: DailyGovernanceRequest) -> DailyGovernanceResult:
    version_dossier = build_version_readiness_dossier(request.version_request)
    actual_version_status = version_dossier.to_dict()["status"]
    # Derive family readiness from actual version dossier status, not caller input.
    # P31 design: VersionReadinessDossier -> SignalFamilyReadinessDossier[];
    # family review chain is only valid when version is ready_for_human_review.
    family_dossiers = tuple(
        build_signal_family_readiness_dossier(
            SignalFamilyReadinessRequest(
                parent_version_status=actual_version_status,
                family_type=fr.family_type,
                family_namespace=fr.family_namespace,
                evidence=fr.evidence,
                notes=fr.notes,
            )
        )
        for fr in request.family_requests
    )
    output_dir = request.output_root / request.run_date

    if request.output_root.exists() and not request.output_root.is_dir():
        return DailyGovernanceResult(
            status="governance_degraded",
            run_date=request.run_date,
            output_dir=str(output_dir),
            version_status=version_dossier.to_dict()["status"],
            family_count=len(family_dossiers),
            human_review_candidates=(),
            blocked_items=(),
            warnings=("output_path_not_directory",),
        )

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        families_payload = [dossier.to_dict() for dossier in family_dossiers]
        result = _build_result(
            request=request,
            output_dir=output_dir,
            version_dossier=version_dossier,
            family_dossiers=family_dossiers,
            warnings=(),
        )
        _write_json(output_dir / "version_readiness.json", version_dossier.to_dict())
        (output_dir / "version_readiness.md").write_text(_version_markdown(version_dossier), encoding="utf-8")
        _write_json(output_dir / "signal_families.json", {"families": families_payload})
        (output_dir / "signal_families.md").write_text(_families_markdown(family_dossiers), encoding="utf-8")
        _write_json(output_dir / "daily_summary.json", result.to_dict())
        (output_dir / "daily_summary.md").write_text(_summary_markdown(result), encoding="utf-8")
        return result
    except OSError as exc:
        return DailyGovernanceResult(
            status="governance_degraded",
            run_date=request.run_date,
            output_dir=str(output_dir),
            version_status=version_dossier.to_dict()["status"],
            family_count=len(family_dossiers),
            human_review_candidates=(),
            blocked_items=(),
            warnings=(f"output_write_failed:{exc.__class__.__name__}",),
        )
