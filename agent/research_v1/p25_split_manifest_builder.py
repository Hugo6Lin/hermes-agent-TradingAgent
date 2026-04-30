"""P25-C purged walk-forward split manifest builder.

This module creates train/validation split manifests. It does not train models.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone


EXCLUSION_REASONS = (
    "insufficient_train_rows",
    "insufficient_validation_rows",
    "train_validation_overlap",
    "validation_not_after_train",
    "purge_gap_violation",
)


class SplitManifestBuilderError(ValueError):
    """Raised when split manifest request or rows are unsafe."""


@dataclass(frozen=True)
class SplitManifestRequest:
    split_id: str
    dataset_id: str
    candidate_namespace: str
    train_window_days: int
    validation_window_days: int
    step_days: int
    purged_gap_days: int
    embargo_days: int
    min_train_rows: int
    min_validation_rows: int
    walk_forward_enabled: bool
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.candidate_namespace.startswith("shadow_meta_model."):
            raise SplitManifestBuilderError("candidate_namespace must start with shadow_meta_model.")
        if self.walk_forward_enabled is not True:
            raise SplitManifestBuilderError("walk_forward_enabled must be true")
        if self.train_window_days <= 0:
            raise SplitManifestBuilderError("train_window_days must be positive")
        if self.validation_window_days <= 0:
            raise SplitManifestBuilderError("validation_window_days must be positive")
        if self.step_days <= 0:
            raise SplitManifestBuilderError("step_days must be positive")
        if self.purged_gap_days < 1:
            raise SplitManifestBuilderError("purged_gap_days must be >= 1")
        if self.embargo_days < 1:
            raise SplitManifestBuilderError("embargo_days must be >= 1")
        if self.min_train_rows < 1:
            raise SplitManifestBuilderError("min_train_rows must be >= 1")
        if self.min_validation_rows < 1:
            raise SplitManifestBuilderError("min_validation_rows must be >= 1")


@dataclass(frozen=True)
class SplitWindow:
    window_id: str
    train_start: str
    train_end: str
    validation_start: str
    validation_end: str
    purged_gap_days: int
    embargo_days: int
    train_snapshot_ids: list[str]
    validation_snapshot_ids: list[str]
    train_row_count: int
    validation_row_count: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class SplitManifest:
    schema_version: str
    split_id: str
    dataset_id: str
    candidate_namespace: str
    walk_forward_enabled: bool
    train_window_days: int
    validation_window_days: int
    step_days: int
    purged_gap_days: int
    embargo_days: int
    min_train_rows: int
    min_validation_rows: int
    total_rows: int
    total_windows: int
    included_windows: int
    excluded_windows: int
    exclusion_reasons: dict[str, int]
    windows: list[SplitWindow]
    created_at: str
    notes: str

    def to_dict(self) -> dict:
        data = asdict(self)
        data["windows"] = [window.to_dict() for window in self.windows]
        return data


@dataclass(frozen=True)
class SplitBuildResult:
    manifest: SplitManifest


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_dict(value) -> dict:
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "to_dict"):
        return dict(value.to_dict())
    if hasattr(value, "__dict__"):
        return dict(value.__dict__)
    raise SplitManifestBuilderError("rows must be dict-like")


def _parse_day(value: str) -> date:
    return date.fromisoformat(str(value))


def _sorted_rows(rows: list) -> list[dict]:
    normalized = [_as_dict(row) for row in rows]
    for row in normalized:
        if not row.get("snapshot_id"):
            raise SplitManifestBuilderError("snapshot_id is required")
        if not row.get("trading_day"):
            raise SplitManifestBuilderError("trading_day is required")
        if "features" not in row or row["features"] is None:
            raise SplitManifestBuilderError("features is required")
        if not row.get("target_name"):
            raise SplitManifestBuilderError("target_name is required")
        if row.get("target_value") is None:
            raise SplitManifestBuilderError("target_value is required")
        if row.get("horizon_days") is None:
            raise SplitManifestBuilderError("horizon_days is required")
    return sorted(normalized, key=lambda row: (str(row["trading_day"]), str(row["snapshot_id"])))


def _window_exclusions(
    train_rows: list[dict],
    validation_rows: list[dict],
    train_end: date,
    validation_start: date,
    request: SplitManifestRequest,
) -> list[str]:
    reasons: list[str] = []
    if len(train_rows) < request.min_train_rows:
        reasons.append("insufficient_train_rows")
    if len(validation_rows) < request.min_validation_rows:
        reasons.append("insufficient_validation_rows")
    train_ids = {row["snapshot_id"] for row in train_rows}
    validation_ids = {row["snapshot_id"] for row in validation_rows}
    if train_ids.intersection(validation_ids):
        reasons.append("train_validation_overlap")
    if validation_start <= train_end:
        reasons.append("validation_not_after_train")
    if (validation_start - train_end).days < request.purged_gap_days:
        reasons.append("purge_gap_violation")
    return reasons


def _manifest(
    request: SplitManifestRequest,
    total_rows: int,
    total_windows: int,
    excluded_windows: int,
    exclusion_reasons: dict[str, int],
    windows: list[SplitWindow],
) -> SplitManifest:
    return SplitManifest(
        schema_version="p25_split_manifest.0",
        split_id=request.split_id,
        dataset_id=request.dataset_id,
        candidate_namespace=request.candidate_namespace,
        walk_forward_enabled=True,
        train_window_days=request.train_window_days,
        validation_window_days=request.validation_window_days,
        step_days=request.step_days,
        purged_gap_days=request.purged_gap_days,
        embargo_days=request.embargo_days,
        min_train_rows=request.min_train_rows,
        min_validation_rows=request.min_validation_rows,
        total_rows=total_rows,
        total_windows=total_windows,
        included_windows=len(windows),
        excluded_windows=excluded_windows,
        exclusion_reasons=dict(exclusion_reasons),
        windows=windows,
        created_at=_utc_now(),
        notes=request.notes,
    )


def build_split_manifest(rows: list, request: SplitManifestRequest) -> SplitBuildResult:
    sorted_rows = _sorted_rows(rows)
    exclusion_reasons = {reason: 0 for reason in EXCLUSION_REASONS}
    windows: list[SplitWindow] = []
    total_windows = 0
    excluded_window_count = 0

    if not sorted_rows:
        manifest = _manifest(request, 0, 0, 0, exclusion_reasons, [])
        return SplitBuildResult(manifest=manifest)

    first_day = _parse_day(sorted_rows[0]["trading_day"])
    last_day = _parse_day(sorted_rows[-1]["trading_day"])
    cursor = first_day
    window_index = 1

    while cursor + timedelta(days=request.train_window_days + request.purged_gap_days + request.validation_window_days) <= last_day + timedelta(days=1):
        total_windows += 1
        train_start = cursor
        train_end = train_start + timedelta(days=request.train_window_days - 1)
        validation_start = train_end + timedelta(days=request.purged_gap_days)
        validation_end = validation_start + timedelta(days=request.validation_window_days - 1)
        train_rows = [row for row in sorted_rows if train_start <= _parse_day(row["trading_day"]) <= train_end]
        validation_rows = [row for row in sorted_rows if validation_start <= _parse_day(row["trading_day"]) <= validation_end]
        reasons = _window_exclusions(train_rows, validation_rows, train_end, validation_start, request)
        if reasons:
            for reason in reasons:
                exclusion_reasons[reason] += 1
            excluded_window_count += 1
        else:
            windows.append(
                SplitWindow(
                    window_id=f"{request.split_id}_w{window_index:03d}",
                    train_start=train_start.isoformat(),
                    train_end=train_end.isoformat(),
                    validation_start=validation_start.isoformat(),
                    validation_end=validation_end.isoformat(),
                    purged_gap_days=request.purged_gap_days,
                    embargo_days=request.embargo_days,
                    train_snapshot_ids=[str(row["snapshot_id"]) for row in train_rows],
                    validation_snapshot_ids=[str(row["snapshot_id"]) for row in validation_rows],
                    train_row_count=len(train_rows),
                    validation_row_count=len(validation_rows),
                )
            )
            window_index += 1
        next_cursor = cursor + timedelta(days=request.step_days)
        embargo_boundary = validation_end + timedelta(days=request.embargo_days) + timedelta(days=1)
        cursor = max(next_cursor, embargo_boundary)

    manifest = _manifest(
        request=request,
        total_rows=len(sorted_rows),
        total_windows=total_windows,
        excluded_windows=excluded_window_count,
        exclusion_reasons=exclusion_reasons,
        windows=windows,
    )
    return SplitBuildResult(manifest=manifest)
