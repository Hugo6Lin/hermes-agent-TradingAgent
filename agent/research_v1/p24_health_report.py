"""P24-E read-only shadow experiment health reporting."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from agent.research_v1.p24_experiment_registry import ShadowExperimentManifest
from agent.research_v1.p24_run_persistence import ShadowRunStore


@dataclass(frozen=True)
class ExperimentHealthRow:
    experiment_id: str
    candidate_id: str
    candidate_name: str
    candidate_family: str
    manifest_status: str
    shadow_namespace: str
    total_runs: int
    completed_count: int
    blocked_count: int
    failed_count: int
    last_run_id: str
    last_run_status: str
    health_status: str
    revocation_recommended: bool
    revocation_reasons: list[str]
    top_blocked_reasons: dict[str, int]
    latest_completed_at: str
    no_production_write_confirmed: bool
    canonical_snapshot_write_blocked: bool
    production_config_write_blocked: bool
    live_trading_blocked: bool

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ShadowExperimentHealthReport:
    schema_version: str
    generated_at: str
    total_experiments: int
    registered_count: int
    revoked_count: int
    archived_count: int
    healthy_count: int
    watch_count: int
    no_runs_count: int
    revocation_recommended_count: int
    family_breakdown: dict
    top_blocked_reasons: dict[str, int]
    production_safety_summary: dict
    experiments: list[ExperimentHealthRow]
    recommended_actions: list[str]

    def to_dict(self) -> dict:
        data = asdict(self)
        data["experiments"] = [row.to_dict() for row in self.experiments]
        return data


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_sort_key(row: ExperimentHealthRow) -> tuple:
    risk_rank = {
        "revocation_recommended": 0,
        "watch": 1,
        "no_runs": 2,
        "healthy": 3,
    }.get(row.health_status, 4)
    return (risk_rank, row.candidate_family, row.experiment_id)


def _build_row(manifest: ShadowExperimentManifest, run_store: ShadowRunStore) -> ExperimentHealthRow:
    summary = run_store.summarize_experiment_runs(manifest.experiment_id)
    run_records = run_store.list_run_records(experiment_id=manifest.experiment_id)
    run_no_prod = all(r.no_production_write_confirmed for r in run_records) if run_records else True
    run_canonical_blocked = all(r.canonical_snapshot_write_blocked for r in run_records) if run_records else True
    run_prod_config_blocked = all(r.production_config_write_blocked for r in run_records) if run_records else True
    run_live_trading_blocked = all(r.live_trading_blocked for r in run_records) if run_records else True
    return ExperimentHealthRow(
        experiment_id=manifest.experiment_id,
        candidate_id=manifest.candidate_id,
        candidate_name=manifest.candidate_name,
        candidate_family=manifest.candidate_family,
        manifest_status=manifest.status,
        shadow_namespace=manifest.shadow_namespace,
        total_runs=summary.total_runs,
        completed_count=summary.completed_count,
        blocked_count=summary.blocked_count,
        failed_count=summary.failed_count,
        last_run_id=summary.last_run_id,
        last_run_status=summary.last_run_status,
        health_status=summary.health_status,
        revocation_recommended=summary.revocation_recommended,
        revocation_reasons=list(summary.revocation_reasons),
        top_blocked_reasons=dict(summary.blocked_reason_frequency),
        latest_completed_at=summary.latest_completed_at,
        no_production_write_confirmed=manifest.production_write_blocked and run_no_prod,
        canonical_snapshot_write_blocked=manifest.canonical_snapshot_write_blocked and run_canonical_blocked,
        production_config_write_blocked=manifest.production_write_blocked and run_prod_config_blocked,
        live_trading_blocked=(manifest.output_contract.get("affects_live_trading") is False) and run_live_trading_blocked,
    )


def _build_family_breakdown(rows: list[ExperimentHealthRow]) -> dict:
    breakdown: dict = {}
    for row in rows:
        bucket = breakdown.setdefault(
            row.candidate_family,
            {
                "total_experiments": 0,
                "registered_count": 0,
                "healthy_count": 0,
                "watch_count": 0,
                "no_runs_count": 0,
                "revocation_recommended_count": 0,
                "completed_runs": 0,
                "blocked_runs": 0,
                "failed_runs": 0,
            },
        )
        bucket["total_experiments"] += 1
        bucket["registered_count"] += 1 if row.manifest_status == "registered" else 0
        bucket["healthy_count"] += 1 if row.health_status == "healthy" else 0
        bucket["watch_count"] += 1 if row.health_status == "watch" else 0
        bucket["no_runs_count"] += 1 if row.health_status == "no_runs" else 0
        bucket["revocation_recommended_count"] += 1 if row.revocation_recommended else 0
        bucket["completed_runs"] += row.completed_count
        bucket["blocked_runs"] += row.blocked_count
        bucket["failed_runs"] += row.failed_count
    return breakdown


def _aggregate_blocked_reasons(rows: list[ExperimentHealthRow]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for row in rows:
        counter.update(row.top_blocked_reasons)
    return dict(counter.most_common())


def _build_production_safety_summary(rows: list[ExperimentHealthRow]) -> dict:
    unsafe_experiment_ids = [
        row.experiment_id
        for row in rows
        if not (
            row.no_production_write_confirmed
            and row.canonical_snapshot_write_blocked
            and row.production_config_write_blocked
            and row.live_trading_blocked
        )
    ]
    return {
        "all_no_production_write_confirmed": all(row.no_production_write_confirmed for row in rows) if rows else True,
        "any_canonical_snapshot_write_attempt": any(not row.canonical_snapshot_write_blocked for row in rows),
        "any_production_config_write_attempt": any(not row.production_config_write_blocked for row in rows),
        "any_live_trading_attempt": any(not row.live_trading_blocked for row in rows),
        "unsafe_experiment_ids": unsafe_experiment_ids,
    }


def _build_recommended_actions(rows: list[ExperimentHealthRow], production_safety_summary: dict) -> list[str]:
    actions: list[str] = []
    if any(row.revocation_recommended for row in rows):
        actions.append("review_revocation_recommended_experiments")
    if any(row.health_status == "no_runs" for row in rows):
        actions.append("schedule_shadow_runs_for_no_run_experiments")
    if any(row.health_status == "watch" for row in rows):
        actions.append("inspect_watch_experiments")
    if production_safety_summary["unsafe_experiment_ids"]:
        actions.append("investigate_production_safety_violation")
    if rows and all(row.health_status == "healthy" for row in rows):
        actions.append("continue_observation")
    return actions


def build_shadow_experiment_health_report(
    manifests: list[ShadowExperimentManifest],
    run_store: ShadowRunStore,
) -> ShadowExperimentHealthReport:
    rows = [_build_row(manifest, run_store) for manifest in manifests]
    rows = sorted(rows, key=_row_sort_key)
    family_breakdown = _build_family_breakdown(rows)
    top_blocked_reasons = _aggregate_blocked_reasons(rows)
    production_safety_summary = _build_production_safety_summary(rows)
    recommended_actions = _build_recommended_actions(rows, production_safety_summary)
    return ShadowExperimentHealthReport(
        schema_version="p24_health_report.0",
        generated_at=_utc_now(),
        total_experiments=len(rows),
        registered_count=sum(1 for row in rows if row.manifest_status == "registered"),
        revoked_count=sum(1 for row in rows if row.manifest_status == "revoked"),
        archived_count=sum(1 for row in rows if row.manifest_status == "archived"),
        healthy_count=sum(1 for row in rows if row.health_status == "healthy"),
        watch_count=sum(1 for row in rows if row.health_status == "watch"),
        no_runs_count=sum(1 for row in rows if row.health_status == "no_runs"),
        revocation_recommended_count=sum(1 for row in rows if row.revocation_recommended),
        family_breakdown=family_breakdown,
        top_blocked_reasons=top_blocked_reasons,
        production_safety_summary=production_safety_summary,
        experiments=rows,
        recommended_actions=recommended_actions,
    )