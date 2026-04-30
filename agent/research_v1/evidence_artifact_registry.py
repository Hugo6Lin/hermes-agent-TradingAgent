"""P32-A evidence artifact registry for governance outputs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any


class EvidenceArtifactRegistryError(ValueError):
    """Raised for unsafe or invalid evidence artifact registry inputs."""


EXPECTED_ARTIFACT_TYPES: tuple[str, ...] = (
    "p20_factor_snapshot",
    "p22_validity_report",
    "p23_shadow_calibration_report",
    "p24_shadow_experiment_manifest",
    "p25_training_dataset_result",
    "p25_shadow_training_result",
    "p26_shadow_portfolio_report",
    "p28_execution_realism_report",
    "p29_adoption_dossier",
    "p30_advanced_model_admission",
    "p31_version_readiness",
    "p31_signal_family_readiness",
    "p31_daily_governance",
)

ARTIFACT_PHASE_BY_TYPE: dict[str, str] = {
    "p20_factor_snapshot": "P20",
    "p22_validity_report": "P22",
    "p23_shadow_calibration_report": "P23",
    "p24_shadow_experiment_manifest": "P24",
    "p25_training_dataset_result": "P25",
    "p25_shadow_training_result": "P25",
    "p26_shadow_portfolio_report": "P26",
    "p28_execution_realism_report": "P28",
    "p29_adoption_dossier": "P29",
    "p30_advanced_model_admission": "P30",
    "p31_version_readiness": "P31",
    "p31_signal_family_readiness": "P31",
    "p31_daily_governance": "P31",
}

ALLOWED_ARTIFACT_STATUSES = frozenset({"present", "missing", "stale", "invalid"})
ALLOWED_REGISTRY_STATUSES = frozenset({
    "complete",
    "incomplete_missing_artifacts",
    "incomplete_stale_artifacts",
    "invalid_registry",
})


@dataclass(frozen=True)
class ArtifactDefinition:
    artifact_type: str
    relative_path: str
    family_namespace: str = ""
    required: bool = True

    def __post_init__(self) -> None:
        if self.artifact_type not in EXPECTED_ARTIFACT_TYPES:
            raise EvidenceArtifactRegistryError(
                f"artifact_type must be one of {list(EXPECTED_ARTIFACT_TYPES)}, got {self.artifact_type!r}"
            )
        if not self.relative_path.strip():
            raise EvidenceArtifactRegistryError("relative_path must be non-empty")

    @property
    def phase_id(self) -> str:
        return ARTIFACT_PHASE_BY_TYPE[self.artifact_type]


@dataclass(frozen=True)
class ArtifactRecord:
    artifact_id: str
    artifact_type: str
    phase_id: str
    path: str
    present: bool
    status: str
    family_namespace: str
    created_at: str
    freshness_days: int | None
    summary: str
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in ALLOWED_ARTIFACT_STATUSES:
            raise EvidenceArtifactRegistryError(
                f"status must be one of {sorted(ALLOWED_ARTIFACT_STATUSES)}, got {self.status!r}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "artifact_type": self.artifact_type,
            "phase_id": self.phase_id,
            "path": self.path,
            "present": self.present,
            "status": self.status,
            "family_namespace": self.family_namespace,
            "created_at": self.created_at,
            "freshness_days": self.freshness_days,
            "summary": self.summary,
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class EvidenceArtifactRegistryRequest:
    run_date: str
    scan_roots: tuple[Path, ...]
    expected_artifacts: tuple[ArtifactDefinition, ...]
    freshness_policy_days: int


@dataclass(frozen=True)
class EvidenceArtifactRegistryReport:
    status: str
    run_date: str
    scan_roots: tuple[str, ...]
    artifact_records: tuple[ArtifactRecord, ...]
    missing_artifact_types: tuple[str, ...]
    stale_artifact_ids: tuple[str, ...]
    invalid_artifact_ids: tuple[str, ...]
    coverage_by_phase: tuple[tuple[str, float], ...]
    coverage_by_family: tuple[tuple[str, float], ...]
    next_actions: tuple[str, ...]
    warnings: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.status not in ALLOWED_REGISTRY_STATUSES:
            raise EvidenceArtifactRegistryError(
                f"status must be one of {sorted(ALLOWED_REGISTRY_STATUSES)}, got {self.status!r}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "run_date": self.run_date,
            "scan_roots": list(self.scan_roots),
            "artifact_records": [record.to_dict() for record in self.artifact_records],
            "missing_artifact_types": list(self.missing_artifact_types),
            "stale_artifact_ids": list(self.stale_artifact_ids),
            "invalid_artifact_ids": list(self.invalid_artifact_ids),
            "coverage_by_phase": dict(self.coverage_by_phase),
            "coverage_by_family": dict(self.coverage_by_family),
            "next_actions": list(self.next_actions),
            "warnings": list(self.warnings),
        }


def _parse_date_segment(path: str) -> date | None:
    """Extract YYYY-MM-DD date segment from the start of a path component."""
    parts = Path(path).parts
    for part in parts:
        if len(part) == 10 and part[4] == "-" and part[7] == "-":
            try:
                return date.fromisoformat(part)
            except ValueError:
                pass
    return None


def _resolve_artifact(
    definition: ArtifactDefinition,
    scan_roots: tuple[Path, ...],
    run_date: date,
    freshness_days: int,
) -> ArtifactRecord:
    """Resolve a single artifact definition against scan roots."""
    artifact_id = f"{definition.artifact_type}:{definition.relative_path}"
    found_path: Path | None = None
    for root in scan_roots:
        candidate = root / definition.relative_path
        if candidate.exists():
            found_path = candidate
            break

    if found_path is None:
        return ArtifactRecord(
            artifact_id=artifact_id,
            artifact_type=definition.artifact_type,
            phase_id=definition.phase_id,
            path="",
            present=False,
            status="missing",
            family_namespace=definition.family_namespace,
            created_at="",
            freshness_days=None,
            summary="artifact not found",
        )

    if not found_path.is_file():
        return ArtifactRecord(
            artifact_id=artifact_id,
            artifact_type=definition.artifact_type,
            phase_id=definition.phase_id,
            path=str(found_path),
            present=False,
            status="invalid",
            family_namespace=definition.family_namespace,
            created_at="",
            freshness_days=None,
            summary="path exists but is not a file",
        )

    # Compute freshness from date segment in path
    date_segment = _parse_date_segment(definition.relative_path)
    freshness: int | None = None
    if date_segment is not None:
        freshness = (run_date - date_segment).days

    if freshness is not None and freshness > freshness_days:
        return ArtifactRecord(
            artifact_id=artifact_id,
            artifact_type=definition.artifact_type,
            phase_id=definition.phase_id,
            path=str(found_path),
            present=True,
            status="stale",
            family_namespace=definition.family_namespace,
            created_at=date_segment.isoformat() if date_segment else "",
            freshness_days=freshness,
            summary=f"stale: {freshness} days old",
        )

    return ArtifactRecord(
        artifact_id=artifact_id,
        artifact_type=definition.artifact_type,
        phase_id=definition.phase_id,
        path=str(found_path),
        present=True,
        status="present",
        family_namespace=definition.family_namespace,
        created_at=date_segment.isoformat() if date_segment else run_date.isoformat(),
        freshness_days=freshness if freshness is not None else 0,
        summary="present",
    )


def _compute_coverage(
    records: tuple[ArtifactRecord, ...],
    definitions: tuple[ArtifactDefinition, ...],
) -> tuple[tuple[str, float], ...]:
    """Compute present ratio per phase."""
    by_phase: dict[str, dict[str, int]] = {}
    for defn in definitions:
        by_phase.setdefault(defn.phase_id, {"present": 0, "total": 0})
        by_phase[defn.phase_id]["total"] += 1

    for rec in records:
        if rec.status == "present":
            by_phase.setdefault(rec.phase_id, {"present": 0, "total": 0})
            by_phase[rec.phase_id]["present"] += 1

    return tuple(
        (phase, data["present"] / data["total"]) if data["total"] > 0 else (phase, 0.0)
        for phase, data in sorted(by_phase.items())
    )


def _compute_family_coverage(
    records: tuple[ArtifactRecord, ...],
    definitions: tuple[ArtifactDefinition, ...],
) -> tuple[tuple[str, float], ...]:
    """Compute present ratio per family namespace."""
    by_family: dict[str, dict[str, int]] = {}
    for defn in definitions:
        ns = defn.family_namespace or ""
        by_family.setdefault(ns, {"present": 0, "total": 0})
        by_family[ns]["total"] += 1

    for rec in records:
        ns = rec.family_namespace or ""
        if rec.status == "present":
            by_family.setdefault(ns, {"present": 0, "total": 0})
            by_family[ns]["present"] += 1

    return tuple(
        (ns, data["present"] / data["total"]) if data["total"] > 0 else (ns, 0.0)
        for ns, data in sorted(by_family.items())
    )


def build_evidence_artifact_registry(
    request: EvidenceArtifactRegistryRequest,
) -> EvidenceArtifactRegistryReport:
    run_date = date.fromisoformat(request.run_date)

    records: list[ArtifactRecord] = []
    for definition in request.expected_artifacts:
        record = _resolve_artifact(
            definition,
            request.scan_roots,
            run_date,
            request.freshness_policy_days,
        )
        records.append(record)

    records_tuple = tuple(records)

    missing_types = tuple(
        r.artifact_type for r in records_tuple
        if r.status == "missing"
    )
    stale_ids = tuple(
        r.artifact_id for r in records_tuple
        if r.status == "stale"
    )
    invalid_ids = tuple(
        r.artifact_id for r in records_tuple
        if r.status == "invalid"
    )

    # Status priority: invalid > missing > stale > complete
    if invalid_ids:
        status = "invalid_registry"
    elif missing_types:
        status = "incomplete_missing_artifacts"
    elif stale_ids:
        status = "incomplete_stale_artifacts"
    else:
        status = "complete"

    next_actions: list[str] = []
    if missing_types:
        next_actions.append("collect_missing_artifacts")
    if stale_ids:
        next_actions.append("refresh_stale_artifacts")

    coverage_by_phase = _compute_coverage(records_tuple, request.expected_artifacts)
    coverage_by_family = _compute_family_coverage(records_tuple, request.expected_artifacts)

    return EvidenceArtifactRegistryReport(
        status=status,
        run_date=request.run_date,
        scan_roots=tuple(str(r) for r in request.scan_roots),
        artifact_records=records_tuple,
        missing_artifact_types=missing_types,
        stale_artifact_ids=stale_ids,
        invalid_artifact_ids=invalid_ids,
        coverage_by_phase=coverage_by_phase,
        coverage_by_family=coverage_by_family,
        next_actions=tuple(dict.fromkeys(next_actions)),
        warnings=(),
    )
