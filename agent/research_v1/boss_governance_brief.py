"""P34 boss-facing governance daily brief."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent.research_v1.daily_governance import DailyGovernanceResult
from agent.research_v1.evidence_artifact_registry import EvidenceArtifactRegistryReport
from agent.research_v1.evidence_generation_dry_run import ControlledEvidenceGenerationReport
from agent.research_v1.signal_family_edge_review import SignalFamilyEdgeReviewReport


ALLOWED_BOSS_BRIEF_STATUSES = frozenset({
    "governance_ready_for_review",
    "governance_incomplete",
    "governance_degraded",
    "no_review_candidates",
})

FORBIDDEN_BOSS_BRIEF_TERMS = (
    "buy this now",
    "sell this now",
    "production approved",
    "model promoted",
    "follow this trade",
    "guaranteed edge",
)


@dataclass(frozen=True)
class BossGovernanceBriefRequest:
    run_date: str
    daily_governance_result: DailyGovernanceResult
    registry_report: EvidenceArtifactRegistryReport
    generation_report: ControlledEvidenceGenerationReport
    edge_review_reports: tuple[SignalFamilyEdgeReviewReport, ...]


@dataclass(frozen=True)
class BossGovernanceDailyBrief:
    run_date: str
    overall_status: str
    system_health_summary: str
    missing_evidence_summary: tuple[str, ...]
    stale_evidence_summary: tuple[str, ...]
    family_review_candidates: tuple[str, ...]
    families_in_shadow_observation: tuple[str, ...]
    blocked_families: tuple[str, ...]
    risk_warnings: tuple[str, ...]
    next_actions: tuple[str, ...]
    forbidden_actions_disclaimer: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_date": self.run_date,
            "overall_status": self.overall_status,
            "system_health_summary": self.system_health_summary,
            "missing_evidence_summary": list(self.missing_evidence_summary),
            "stale_evidence_summary": list(self.stale_evidence_summary),
            "family_review_candidates": list(self.family_review_candidates),
            "families_in_shadow_observation": list(self.families_in_shadow_observation),
            "blocked_families": list(self.blocked_families),
            "risk_warnings": list(self.risk_warnings),
            "next_actions": list(self.next_actions),
            "forbidden_actions_disclaimer": self.forbidden_actions_disclaimer,
        }


def build_boss_governance_daily_brief(
    request: BossGovernanceBriefRequest,
) -> BossGovernanceDailyBrief:
    daily = request.daily_governance_result
    registry = request.registry_report
    edge_reports = request.edge_review_reports

    # ── Determine overall status ────────────────────────────────────────────────
    if daily.status == "governance_degraded":
        overall_status = "governance_degraded"
    elif registry.status != "complete":
        overall_status = "governance_incomplete"
    elif any(er.status == "ready_for_human_review" for er in edge_reports):
        overall_status = "governance_ready_for_review"
    else:
        overall_status = "no_review_candidates"

    # ── Classify edge reports ───────────────────────────────────────────────────
    review_candidates = tuple(
        er.family_namespace for er in edge_reports
        if er.status == "ready_for_human_review"
    )
    shadow_observation = tuple(
        er.family_namespace for er in edge_reports
        if er.status == "shadow_observation_only"
    )
    blocked_families = tuple(
        er.family_namespace for er in edge_reports
        if er.status.startswith("blocked_") or er.status == "rejected_for_now"
    )

    # ── Summaries ───────────────────────────────────────────────────────────────
    missing_ev: list[str] = list(registry.missing_artifact_types)
    stale_ev: list[str] = list(registry.stale_artifact_ids)
    risk_warnings: list[str] = list(registry.warnings)

    for er in edge_reports:
        risk_warnings.extend(er.degradation_warnings)
        risk_warnings.extend(er.execution_cost_warnings)

    # ── Next actions ───────────────────────────────────────────────────────────
    next_actions: list[str] = []
    if registry.missing_artifact_types:
        next_actions.append("collect_missing_artifacts")
    if registry.stale_artifact_ids:
        next_actions.append("refresh_stale_artifacts")
    if review_candidates:
        next_actions.append("review_candidate_families")
    if shadow_observation:
        next_actions.append("continue_shadow_observation")
    if blocked_families:
        next_actions.append("address_blocked_families")

    # ── System health summary ───────────────────────────────────────────────────
    system_health = daily.version_status
    if registry.status != "complete":
        system_health += f"; registry {registry.status}"

    disclaimer = (
        "This brief is governance-only and does not approve production or instruct trades."
    )

    return BossGovernanceDailyBrief(
        run_date=request.run_date,
        overall_status=overall_status,
        system_health_summary=system_health,
        missing_evidence_summary=tuple(dict.fromkeys(missing_ev)),
        stale_evidence_summary=tuple(dict.fromkeys(stale_ev)),
        family_review_candidates=review_candidates,
        families_in_shadow_observation=shadow_observation,
        blocked_families=blocked_families,
        risk_warnings=tuple(dict.fromkeys(risk_warnings)),
        next_actions=tuple(dict.fromkeys(next_actions)),
        forbidden_actions_disclaimer=disclaimer,
    )


def write_boss_governance_daily_brief(
    brief: BossGovernanceDailyBrief,
    output_dir: Path,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "boss_daily_brief.json"
    md_path = output_dir / "boss_daily_brief.md"

    _write_json(json_path, brief.to_dict())
    _write_markdown(md_path, brief)

    return {"json": json_path, "markdown": md_path}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _write_markdown(path: Path, brief: BossGovernanceDailyBrief) -> None:
    data = brief.to_dict()
    lines = [
        "# Boss Governance Daily Brief",
        "",
        f"Run date: `{data['run_date']}`",
        f"Overall status: `{data['overall_status']}`",
        f"System health: {data['system_health_summary']}",
        "",
        "## Human Review Candidates",
    ]
    if data["family_review_candidates"]:
        for candidate in data["family_review_candidates"]:
            lines.append(f"- {candidate} — ready for human review")
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Families in Shadow Observation")
    if data["families_in_shadow_observation"]:
        for family in data["families_in_shadow_observation"]:
            lines.append(f"- {family}")
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Blocked Families")
    if data["blocked_families"]:
        for family in data["blocked_families"]:
            lines.append(f"- {family}")
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Missing Evidence")
    if data["missing_evidence_summary"]:
        for item in data["missing_evidence_summary"]:
            lines.append(f"- {item}")
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Risk Warnings")
    if data["risk_warnings"]:
        for warning in data["risk_warnings"]:
            lines.append(f"- {warning}")
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Next Actions")
    if data["next_actions"]:
        for action in data["next_actions"]:
            lines.append(f"- {action}")
    else:
        lines.append("- none")
    lines.append("")
    lines.append(f"> {data['forbidden_actions_disclaimer']}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
