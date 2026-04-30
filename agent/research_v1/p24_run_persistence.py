"""P24-D shadow run persistence and observation bridge."""

from __future__ import annotations

import copy
import json
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from agent.research_v1.p24_experiment_registry import ShadowExperimentManifest
from agent.research_v1.p24_shadow_runner import ShadowExperimentRunRecord


class ShadowRunPersistenceError(ValueError):
    """Raised when a shadow run record cannot be persisted or observed safely."""


@dataclass(frozen=True)
class ShadowRunSummary:
    schema_version: str
    experiment_id: str
    total_runs: int
    completed_count: int
    blocked_count: int
    failed_count: int
    last_run_id: str
    last_run_status: str
    blocked_reason_frequency: dict[str, int]
    failed_error_frequency: dict[str, int]
    latest_completed_at: str
    health_status: str
    revocation_recommended: bool
    revocation_reasons: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ShadowExperimentObservation:
    schema_version: str
    experiment_id: str
    run_id: str
    candidate_id: str
    candidate_family: str
    run_status: str
    health_status: str
    produced_artifacts: list[str]
    blocked_artifacts: list[str]
    warnings: list[str]
    revocation_recommended: bool
    revocation_reasons: list[str]
    source_manifest_schema_version: str
    source_run_schema_version: str
    no_production_write_confirmed: bool
    created_at: str

    def to_dict(self) -> dict:
        return asdict(self)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ShadowRunPersistenceError(message)


def _is_production_path_reason(reason: str) -> bool:
    return any(
        token in reason
        for token in (
            "production",
            "canonical",
            "live_trading",
            "live_trade_signal",
        )
    )


def _validate_record_for_persistence(record: ShadowExperimentRunRecord) -> None:
    _require(record.schema_version.startswith("p24_run."), "run schema_version must start with p24_run.")
    _require(bool(record.run_id), "run_id is required")
    _require(record.no_production_write_confirmed is True, "no_production_write_confirmed must be true")
    _require(record.canonical_snapshot_write_blocked is True, "canonical_snapshot_write_blocked must be true")
    _require(record.production_config_write_blocked is True, "production_config_write_blocked must be true")
    _require(record.live_trading_blocked is True, "live_trading_blocked must be true")


def _observation_health(record: ShadowExperimentRunRecord) -> tuple[str, list[str]]:
    if record.status == "completed":
        return "healthy", []
    if record.status == "blocked" and any(_is_production_path_reason(reason) for reason in record.blocked_artifacts):
        return "revocation_recommended", ["production_or_canonical_path_blocked"]
    if record.status in {"blocked", "failed"}:
        return "watch", []
    return "watch", []


def _summary_health(
    records: list[ShadowExperimentRunRecord],
    completed_count: int,
    blocked_count: int,
    failed_count: int,
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if any(_is_production_path_reason(reason) for record in records for reason in record.blocked_artifacts):
        reasons.append("production_or_canonical_path_blocked")
    if len(records) >= 3 and all(record.status in {"blocked", "failed"} for record in records[-3:]):
        reasons.append("three_consecutive_blocked_or_failed_runs")
    if reasons:
        return "revocation_recommended", reasons
    if records[-1].status == "completed" and blocked_count == 0 and failed_count == 0:
        return "healthy", []
    if blocked_count + failed_count > completed_count:
        return "watch", []
    return "watch", []


class ShadowRunStore:
    def __init__(self) -> None:
        self._records: dict[str, dict] = {}
        self._order: list[str] = []

    def save_run_record(self, record: ShadowExperimentRunRecord) -> ShadowExperimentRunRecord:
        _validate_record_for_persistence(record)
        if record.run_id in self._records:
            raise ShadowRunPersistenceError(f"duplicate run_id: {record.run_id}")
        stored = copy.deepcopy(record.to_dict())
        json.loads(json.dumps(stored))
        self._records[record.run_id] = stored
        self._order.append(record.run_id)
        return ShadowExperimentRunRecord(**stored)

    def get_run_record(self, run_id: str) -> ShadowExperimentRunRecord | None:
        stored = self._records.get(run_id)
        if stored is None:
            return None
        return ShadowExperimentRunRecord(**copy.deepcopy(stored))

    def list_run_records(
        self,
        experiment_id: str | None = None,
        status: str | None = None,
    ) -> list[ShadowExperimentRunRecord]:
        records = [ShadowExperimentRunRecord(**copy.deepcopy(self._records[run_id])) for run_id in self._order]
        if experiment_id is not None:
            records = [record for record in records if record.experiment_id == experiment_id]
        if status is not None:
            records = [record for record in records if record.status == status]
        return records

    def summarize_experiment_runs(self, experiment_id: str) -> ShadowRunSummary:
        records = self.list_run_records(experiment_id=experiment_id)
        return summarize_run_records(experiment_id, records)


def summarize_run_records(experiment_id: str, records: list[ShadowExperimentRunRecord]) -> ShadowRunSummary:
    if not records:
        return ShadowRunSummary(
            schema_version="p24_run_summary.0",
            experiment_id=experiment_id,
            total_runs=0,
            completed_count=0,
            blocked_count=0,
            failed_count=0,
            last_run_id="",
            last_run_status="",
            blocked_reason_frequency={},
            failed_error_frequency={},
            latest_completed_at="",
            health_status="no_runs",
            revocation_recommended=False,
            revocation_reasons=[],
        )
    completed_count = sum(1 for record in records if record.status == "completed")
    blocked_count = sum(1 for record in records if record.status == "blocked")
    failed_count = sum(1 for record in records if record.status == "failed")
    blocked_reason_frequency = Counter(reason for record in records for reason in record.blocked_artifacts)
    failed_error_frequency = Counter(record.error_message for record in records if record.status == "failed" and record.error_message)
    latest_completed_at = max((record.completed_at for record in records), default="")
    health_status, revocation_reasons = _summary_health(records, completed_count, blocked_count, failed_count)
    return ShadowRunSummary(
        schema_version="p24_run_summary.0",
        experiment_id=experiment_id,
        total_runs=len(records),
        completed_count=completed_count,
        blocked_count=blocked_count,
        failed_count=failed_count,
        last_run_id=records[-1].run_id,
        last_run_status=records[-1].status,
        blocked_reason_frequency=dict(blocked_reason_frequency),
        failed_error_frequency=dict(failed_error_frequency),
        latest_completed_at=latest_completed_at,
        health_status=health_status,
        revocation_recommended=health_status == "revocation_recommended",
        revocation_reasons=revocation_reasons,
    )


def build_shadow_experiment_observation(
    record: ShadowExperimentRunRecord,
    manifest: ShadowExperimentManifest,
) -> ShadowExperimentObservation:
    _require(record.experiment_id == manifest.experiment_id, "experiment_id mismatch")
    _require(record.candidate_id == manifest.candidate_id, "candidate_id mismatch")
    _require(record.output_namespace == manifest.shadow_namespace, "output namespace mismatch")
    health_status, revocation_reasons = _observation_health(record)
    return ShadowExperimentObservation(
        schema_version="p24_observation.0",
        experiment_id=record.experiment_id,
        run_id=record.run_id,
        candidate_id=record.candidate_id,
        candidate_family=record.candidate_family,
        run_status=record.status,
        health_status=health_status,
        produced_artifacts=list(record.produced_artifacts),
        blocked_artifacts=list(record.blocked_artifacts),
        warnings=list(record.warnings),
        revocation_recommended=health_status == "revocation_recommended",
        revocation_reasons=revocation_reasons,
        source_manifest_schema_version=manifest.schema_version,
        source_run_schema_version=record.schema_version,
        no_production_write_confirmed=record.no_production_write_confirmed,
        created_at=_utc_now(),
    )