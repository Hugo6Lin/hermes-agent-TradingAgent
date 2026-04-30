"""P25-B point-in-time training dataset builder.

This module constructs offline training rows from factor snapshots and
forward-return observations. It does not train models or read raw prices.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone


EXCLUSION_KEYS = (
    "missing_forward_return",
    "non_net_return",
    "lookahead_violation",
    "source_audit_gap",
    "universe_mismatch",
    "missing_required_feature",
    "wrong_horizon",
)


class TrainingDatasetBuilderError(ValueError):
    """Raised when P25-B dataset request or inputs are unsafe."""


@dataclass(frozen=True)
class TrainingDatasetRequest:
    dataset_id: str
    candidate_namespace: str
    horizon_days: int
    feature_names: list[str]
    target_name: str
    min_rows: int
    require_point_in_time: bool
    require_universe_membership: bool
    max_source_audit_gap_rate: float
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.candidate_namespace.startswith("shadow_meta_model."):
            raise TrainingDatasetBuilderError("candidate_namespace must start with shadow_meta_model.")
        if self.target_name != "net_return_pct":
            raise TrainingDatasetBuilderError("target_name must be net_return_pct")
        if self.horizon_days <= 0:
            raise TrainingDatasetBuilderError("horizon_days must be positive")
        if not self.feature_names:
            raise TrainingDatasetBuilderError("feature_names is required")
        forbidden = FORBIDDEN_FEATURE_NAMES.intersection(self.feature_names)
        if forbidden:
            raise TrainingDatasetBuilderError(f"feature_names may not include target or forward-return fields: {sorted(forbidden)}")
        if self.min_rows < 1:
            raise TrainingDatasetBuilderError("min_rows must be >= 1")
        if self.require_point_in_time is not True:
            raise TrainingDatasetBuilderError("require_point_in_time must be true")
        if self.require_universe_membership is not True:
            raise TrainingDatasetBuilderError("require_universe_membership must be true")
        if self.max_source_audit_gap_rate > 0.20:
            raise TrainingDatasetBuilderError("max_source_audit_gap_rate must be <= 0.20")


FORBIDDEN_FEATURE_NAMES = frozenset([
    "net_return_pct",
    "gross_return_pct",
    "return_value",
    "future_return",
    "forward_return",
    "classification",
    "take_profit",
    "stop_loss",
    "live_trade_signal",
])


@dataclass(frozen=True)
class TrainingDatasetRow:
    snapshot_id: str
    ticker: str
    trading_day: str
    features: dict
    target_name: str
    target_value: float
    horizon_days: int
    data_as_of_date: str
    universe_membership_snapshot_id: str
    source_snapshot_schema_version: str
    source_return_schema_version: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class TrainingDatasetManifest:
    schema_version: str
    dataset_id: str
    candidate_namespace: str
    horizon_days: int
    feature_names: list[str]
    target_name: str
    total_snapshots: int
    total_forward_returns: int
    included_rows: int
    excluded_counts: dict[str, int]
    point_in_time_confirmed: bool
    return_basis: str
    min_rows: int
    meets_min_rows: bool
    created_at: str
    notes: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class TrainingDatasetBuildResult:
    manifest: TrainingDatasetManifest
    rows: list[TrainingDatasetRow]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_dict(value) -> dict:
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "to_dict"):
        return dict(value.to_dict())
    if hasattr(value, "__dict__"):
        return dict(value.__dict__)
    raise TrainingDatasetBuilderError("input rows must be dict-like")


def _index_forward_returns(forward_returns: list[dict], horizon_days: int) -> dict[str, dict]:
    indexed: dict[str, dict] = {}
    for raw_return in forward_returns:
        observation = _as_dict(raw_return)
        snapshot_id = observation.get("snapshot_id")
        if not snapshot_id:
            continue
        current = indexed.get(snapshot_id)
        if current is None:
            indexed[snapshot_id] = observation
            continue
        indexed[snapshot_id] = _choose_return(current, observation, horizon_days)
    return indexed


def _choose_return(left: dict, right: dict, horizon_days: int) -> dict:
    left_is_net = left.get("return_basis") == "net" and left.get("horizon_days") == horizon_days
    right_is_net = right.get("return_basis") == "net" and right.get("horizon_days") == horizon_days
    if left_is_net and not right_is_net:
        return left
    if right_is_net and not left_is_net:
        return right
    return right if str(right.get("computed_at", "")) >= str(left.get("computed_at", "")) else left


def _snapshot_exclusions(snapshot: dict, request: TrainingDatasetRequest) -> list[str]:
    exclusions: list[str] = []
    if snapshot.get("lookahead_violation") is True:
        exclusions.append("lookahead_violation")
    data_as_of = snapshot.get("data_as_of_date", "")
    trading_day = snapshot.get("trading_day", "")
    if data_as_of and trading_day and data_as_of > trading_day:
        exclusions.append("lookahead_violation")
    if float(snapshot.get("source_audit_gap", 0.0) or 0.0) > request.max_source_audit_gap_rate:
        exclusions.append("source_audit_gap")
    if request.require_universe_membership and not snapshot.get("universe_membership_snapshot_id"):
        exclusions.append("universe_mismatch")
    required_snapshot_fields = [
        "snapshot_id",
        "ticker",
        "trading_day",
        "data_as_of_date",
        "universe_membership_snapshot_id",
        *request.feature_names,
    ]
    if any(field not in snapshot or snapshot.get(field) in (None, "") for field in required_snapshot_fields):
        exclusions.append("missing_required_feature")
    return exclusions


def _return_exclusions(observation: dict, request: TrainingDatasetRequest) -> list[str]:
    exclusions: list[str] = []
    if observation.get("horizon_days") != request.horizon_days:
        exclusions.append("wrong_horizon")
    if observation.get("return_basis") != "net":
        exclusions.append("non_net_return")
    if observation.get("net_return_pct") is None:
        exclusions.append("non_net_return")
    return exclusions


def _build_row(snapshot: dict, observation: dict, request: TrainingDatasetRequest) -> TrainingDatasetRow:
    return TrainingDatasetRow(
        snapshot_id=str(snapshot["snapshot_id"]),
        ticker=str(snapshot["ticker"]),
        trading_day=str(snapshot["trading_day"]),
        features={feature: snapshot[feature] for feature in request.feature_names},
        target_name=request.target_name,
        target_value=float(observation["net_return_pct"]),
        horizon_days=int(observation["horizon_days"]),
        data_as_of_date=str(snapshot["data_as_of_date"]),
        universe_membership_snapshot_id=str(snapshot["universe_membership_snapshot_id"]),
        source_snapshot_schema_version=str(snapshot.get("schema_version", "")),
        source_return_schema_version=str(observation.get("schema_version", "")),
    )


def build_training_dataset(
    factor_snapshots: list[dict],
    forward_returns: list[dict],
    request: TrainingDatasetRequest,
) -> TrainingDatasetBuildResult:
    excluded_counts = {key: 0 for key in EXCLUSION_KEYS}
    returns_by_snapshot = _index_forward_returns(forward_returns, request.horizon_days)
    rows: list[TrainingDatasetRow] = []

    for raw_snapshot in factor_snapshots:
        snapshot = _as_dict(raw_snapshot)
        row_exclusions = _snapshot_exclusions(snapshot, request)
        matching_return = returns_by_snapshot.get(snapshot.get("snapshot_id"))
        if matching_return is None:
            row_exclusions.append("missing_forward_return")
        else:
            row_exclusions.extend(_return_exclusions(matching_return, request))
        if row_exclusions:
            for reason in set(row_exclusions):
                excluded_counts[reason] += 1
            continue
        rows.append(_build_row(snapshot, matching_return, request))

    manifest = TrainingDatasetManifest(
        schema_version="p25_training_dataset.0",
        dataset_id=request.dataset_id,
        candidate_namespace=request.candidate_namespace,
        horizon_days=request.horizon_days,
        feature_names=list(request.feature_names),
        target_name=request.target_name,
        total_snapshots=len(factor_snapshots),
        total_forward_returns=len(forward_returns),
        included_rows=len(rows),
        excluded_counts=excluded_counts,
        point_in_time_confirmed=True,
        return_basis="net",
        min_rows=request.min_rows,
        meets_min_rows=len(rows) >= request.min_rows,
        created_at=_utc_now(),
        notes=request.notes,
    )
    return TrainingDatasetBuildResult(manifest=manifest, rows=rows)