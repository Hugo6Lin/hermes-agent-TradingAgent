"""P25-D shadow-only offline training runner.

This module trains only in-memory shadow baselines from approved P25-B/P25-C
contracts. It does not persist models or modify production state.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from typing import Any


ALLOWED_MODEL_FAMILIES = {"linear_baseline", "stump_ensemble_stub", "xgboost_style_stub"}
ALLOWED_TRAINING_MODES = {"shadow_offline", "dry_run"}
ALLOWED_EXPERIMENT_STATUSES = {"registered", "running", "active"}


class ShadowTrainingError(ValueError):
    """Raised when P25-D request values are unsafe."""


@dataclass(frozen=True)
class ShadowTrainingRequest:
    training_run_id: str
    experiment_id: str
    dataset_id: str
    split_id: str
    candidate_namespace: str
    model_family: str
    feature_names: list[str]
    target_name: str
    training_mode: str
    hyperparameters: dict[str, Any]
    baseline_name: str
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.training_run_id:
            raise ShadowTrainingError("training_run_id is required")
        if not self.experiment_id:
            raise ShadowTrainingError("experiment_id is required")
        if not self.dataset_id:
            raise ShadowTrainingError("dataset_id is required")
        if not self.split_id:
            raise ShadowTrainingError("split_id is required")
        if not self.candidate_namespace.startswith("shadow_meta_model."):
            raise ShadowTrainingError("candidate_namespace must start with shadow_meta_model")
        if self.model_family not in ALLOWED_MODEL_FAMILIES:
            raise ShadowTrainingError("model_family is not allowed")
        if self.training_mode not in ALLOWED_TRAINING_MODES:
            raise ShadowTrainingError("training_mode is not allowed")
        if not self.feature_names:
            raise ShadowTrainingError("feature_names must be non-empty")
        if self.target_name != "net_return_pct":
            raise ShadowTrainingError("target_name must be net_return_pct")
        try:
            json.dumps(self.hyperparameters)
        except TypeError as exc:
            raise ShadowTrainingError("hyperparameters must be JSON-serializable") from exc


@dataclass(frozen=True)
class WindowTrainingArtifact:
    training_run_id: str
    experiment_id: str
    window_id: str
    candidate_namespace: str
    model_family: str
    feature_names: list[str]
    train_snapshot_ids: list[str]
    validation_snapshot_ids: list[str]
    train_row_count: int
    validation_row_count: int
    fitted_parameters: dict[str, Any]
    predictions: list[dict[str, Any]]
    training_status: str
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ShadowTrainingRunManifest:
    schema_version: str
    training_run_id: str
    experiment_id: str
    dataset_id: str
    split_id: str
    candidate_namespace: str
    model_family: str
    training_mode: str
    feature_names: list[str]
    target_name: str
    total_windows: int
    completed_windows: int
    blocked_windows: int
    failed_windows: int
    hyperparameters: dict[str, Any]
    baseline_name: str
    dataset_schema_version: str
    split_schema_version: str
    created_at: str
    safety_flags: dict[str, bool]
    warnings: list[str]
    notes: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ShadowTrainingRunResult:
    manifest: ShadowTrainingRunManifest
    window_artifacts: list[WindowTrainingArtifact]

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest": self.manifest.to_dict(),
            "window_artifacts": [artifact.to_dict() for artifact in self.window_artifacts],
        }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "to_dict"):
        return dict(value.to_dict())
    if hasattr(value, "__dict__"):
        return dict(value.__dict__)
    raise ShadowTrainingError("input object must be dict-like")


def _get_manifest_dict(container: Any) -> dict[str, Any]:
    if isinstance(container, dict) and "manifest" in container:
        return _as_dict(container["manifest"])
    return _as_dict(container.manifest)


def _get_rows(dataset_result: Any) -> list[dict[str, Any]]:
    rows = dataset_result["rows"] if isinstance(dataset_result, dict) else dataset_result.rows
    return [_as_dict(row) for row in rows]


def _get_windows(split_manifest: Any) -> list[dict[str, Any]]:
    manifest = _as_dict(split_manifest)
    return [_as_dict(window) for window in manifest.get("windows", [])]


def _namespace_child(name: str, namespace: str) -> bool:
    return name == namespace or name.startswith(namespace + ".")


def _validate_run(
    dataset_result: Any, split_manifest: Any, experiment_manifest: Any, request: ShadowTrainingRequest
) -> list[str]:
    dataset_manifest = _get_manifest_dict(dataset_result)
    split = _as_dict(split_manifest)
    experiment = _as_dict(experiment_manifest)
    rows = _get_rows(dataset_result)
    row_by_id = {str(row.get("snapshot_id")): row for row in rows}
    warnings: list[str] = []

    if dataset_manifest.get("dataset_id") != request.dataset_id:
        warnings.append("dataset_id_mismatch")
    if split.get("split_id") != request.split_id:
        warnings.append("split_id_mismatch")
    if split.get("dataset_id") != dataset_manifest.get("dataset_id"):
        warnings.append("split_dataset_id_mismatch")
    namespaces = {
        str(dataset_manifest.get("candidate_namespace")),
        str(split.get("candidate_namespace")),
        str(experiment.get("candidate_namespace")),
        request.candidate_namespace,
    }
    if len(namespaces) != 1:
        warnings.append("candidate_namespace_mismatch")
    if not _namespace_child(str(experiment.get("output_namespace")), request.candidate_namespace):
        warnings.append("output_namespace_escape")
    if dataset_manifest.get("return_basis") != "net":
        warnings.append("return_basis_not_net")
    if dataset_manifest.get("point_in_time_confirmed") is not True:
        warnings.append("point_in_time_not_confirmed")
    if dataset_manifest.get("meets_min_rows") is not True:
        warnings.append("dataset_min_rows_not_met")
    if split.get("walk_forward_enabled") is not True:
        warnings.append("walk_forward_not_enabled")
    if experiment.get("status") not in ALLOWED_EXPERIMENT_STATUSES:
        warnings.append("experiment_not_registered")
    if str(experiment.get("experiment_id")) != request.experiment_id:
        warnings.append("experiment_id_mismatch")
    for flag in ["production_write_blocked", "canonical_snapshot_write_blocked", "live_trading_blocked"]:
        if experiment.get(flag) is not True:
            warnings.append(f"{flag}_false")
    dataset_features = set(dataset_manifest.get("feature_names", []))
    if not set(request.feature_names).issubset(dataset_features):
        warnings.append("requested_feature_not_in_dataset_manifest")
    for row in rows:
        features = row.get("features") or {}
        for feature_name in request.feature_names:
            if feature_name not in features or features[feature_name] is None:
                warnings.append("missing_requested_feature_in_row")
                break
        if row.get("target_name") != request.target_name:
            warnings.append("row_target_name_mismatch")
        dataset_horizon = int(dataset_manifest.get("horizon_days", 0))
        if dataset_horizon > 0 and int(row.get("horizon_days", 0)) != dataset_horizon:
            warnings.append("row_horizon_days_mismatch")
    for window in _get_windows(split_manifest):
        train_ids = {str(item) for item in window.get("train_snapshot_ids", [])}
        validation_ids = {str(item) for item in window.get("validation_snapshot_ids", [])}
        if train_ids.intersection(validation_ids):
            warnings.append("train_validation_overlap")
        missing_ids = [snapshot_id for snapshot_id in sorted(train_ids | validation_ids) if snapshot_id not in row_by_id]
        if missing_ids:
            warnings.append("split_snapshot_id_missing_from_dataset")
    return sorted(set(warnings))


def _blocked_result(
    dataset_result: Any, split_manifest: Any, experiment_manifest: Any, request: ShadowTrainingRequest, warnings: list[str]
) -> ShadowTrainingRunResult:
    dataset_manifest = _get_manifest_dict(dataset_result)
    split = _as_dict(split_manifest)
    experiment = _as_dict(experiment_manifest)
    total_windows = len(split.get("windows", []))
    manifest = ShadowTrainingRunManifest(
        schema_version="p25_shadow_training.0",
        training_run_id=request.training_run_id,
        experiment_id=request.experiment_id,
        dataset_id=request.dataset_id,
        split_id=request.split_id,
        candidate_namespace=request.candidate_namespace,
        model_family=request.model_family,
        training_mode=request.training_mode,
        feature_names=list(request.feature_names),
        target_name=request.target_name,
        total_windows=total_windows,
        completed_windows=0,
        blocked_windows=total_windows,
        failed_windows=0,
        hyperparameters=dict(request.hyperparameters),
        baseline_name=request.baseline_name,
        dataset_schema_version=str(dataset_manifest.get("schema_version", "unknown")),
        split_schema_version=str(split.get("schema_version", "unknown")),
        created_at=_utc_now(),
        safety_flags={
            "production_write_blocked": bool(experiment.get("production_write_blocked")),
            "canonical_snapshot_write_blocked": bool(experiment.get("canonical_snapshot_write_blocked")),
            "live_trading_blocked": bool(experiment.get("live_trading_blocked")),
        },
        warnings=warnings,
        notes=request.notes,
    )
    return ShadowTrainingRunResult(manifest=manifest, window_artifacts=[])


def _float_feature(row: dict[str, Any], feature_name: str) -> float:
    return float((row.get("features") or {})[feature_name])


def _fit_linear_baseline(train_rows: list[dict[str, Any]], feature_names: list[str]) -> dict[str, Any]:
    targets = [float(row["target_value"]) for row in train_rows]
    target_mean = sum(targets) / len(targets)
    feature_weights: dict[str, float] = {}
    feature_means: dict[str, float] = {}
    for feature_name in feature_names:
        values = [_float_feature(row, feature_name) for row in train_rows]
        feature_mean = sum(values) / len(values)
        feature_means[feature_name] = feature_mean
        covariance = sum(
            (value - feature_mean) * (target - target_mean) for value, target in zip(values, targets)
        )
        feature_weights[feature_name] = 1.0 if covariance > 0 else -1.0 if covariance < 0 else 0.0
    return {
        "mode": "linear_baseline",
        "target_mean": target_mean,
        "feature_means": feature_means,
        "feature_weights": feature_weights,
    }


def _predict_linear_baseline(
    validation_rows: list[dict[str, Any]],
    request: ShadowTrainingRequest,
    fitted_parameters: dict[str, Any],
) -> list[dict[str, Any]]:
    clip = float(request.hyperparameters.get("prediction_clip", 1.0))
    raw_predictions = []
    for row in validation_rows:
        score = float(fitted_parameters["target_mean"])
        for feature_name in request.feature_names:
            score += fitted_parameters["feature_weights"][feature_name] * (
                _float_feature(row, feature_name) - fitted_parameters["feature_means"][feature_name]
            )
        score = max(-clip, min(clip, score))
        raw_predictions.append((row, score))
    ranked = sorted(raw_predictions, key=lambda item: (-item[1], str(item[0]["snapshot_id"])))
    rank_by_id = {str(row["snapshot_id"]): rank for rank, (row, _score) in enumerate(ranked, start=1)}
    predictions = []
    for row, score in sorted(raw_predictions, key=lambda item: str(item[0]["snapshot_id"])):
        predictions.append(
            {
                "snapshot_id": str(row["snapshot_id"]),
                "prediction_value": score,
                "prediction_rank": rank_by_id[str(row["snapshot_id"])],
                "target_name": request.target_name,
                "actual_target_value": row.get("target_value"),
                "trading_day": row.get("trading_day"),
            }
        )
    return predictions


def _zero_predictions(validation_rows: list[dict[str, Any]], request: ShadowTrainingRequest) -> list[dict[str, Any]]:
    predictions = []
    for rank, row in enumerate(sorted(validation_rows, key=lambda item: str(item["snapshot_id"])), start=1):
        predictions.append(
            {
                "snapshot_id": str(row["snapshot_id"]),
                "prediction_value": 0.0,
                "prediction_rank": rank,
                "target_name": request.target_name,
                "actual_target_value": row.get("target_value"),
                "trading_day": row.get("trading_day"),
            }
        )
    return predictions


def run_shadow_offline_training(
    dataset_result: Any,
    split_manifest: Any,
    experiment_manifest: Any,
    request: ShadowTrainingRequest,
) -> ShadowTrainingRunResult:
    warnings = _validate_run(dataset_result, split_manifest, experiment_manifest, request)
    if warnings:
        return _blocked_result(dataset_result, split_manifest, experiment_manifest, request, warnings)

    if request.training_mode == "shadow_offline" and request.model_family != "linear_baseline":
        return _blocked_result(
            dataset_result, split_manifest, experiment_manifest, request,
            [f"unsupported_model_family_for_shadow_offline:{request.model_family}"]
        )

    dataset_manifest = _get_manifest_dict(dataset_result)
    split = _as_dict(split_manifest)
    rows = _get_rows(dataset_result)
    row_by_id = {str(row["snapshot_id"]): row for row in rows}
    artifacts: list[WindowTrainingArtifact] = []

    for window in _get_windows(split_manifest):
        train_ids = [str(item) for item in window.get("train_snapshot_ids", [])]
        validation_ids = [str(item) for item in window.get("validation_snapshot_ids", [])]
        train_rows = [row_by_id[snapshot_id] for snapshot_id in train_ids]
        validation_rows = [row_by_id[snapshot_id] for snapshot_id in validation_ids]

        if request.training_mode == "dry_run":
            predictions = _zero_predictions(validation_rows, request)
            fitted_parameters = {"mode": "dry_run", "feature_weights": {feature: 0.0 for feature in request.feature_names}}
        else:
            fitted_parameters = _fit_linear_baseline(train_rows, request.feature_names)
            predictions = _predict_linear_baseline(validation_rows, request, fitted_parameters)

        artifacts.append(
            WindowTrainingArtifact(
                training_run_id=request.training_run_id,
                experiment_id=request.experiment_id,
                window_id=str(window["window_id"]),
                candidate_namespace=request.candidate_namespace,
                model_family=request.model_family,
                feature_names=list(request.feature_names),
                train_snapshot_ids=train_ids,
                validation_snapshot_ids=validation_ids,
                train_row_count=len(train_rows),
                validation_row_count=len(validation_rows),
                fitted_parameters=fitted_parameters,
                predictions=predictions,
                training_status="completed",
                warnings=[],
            )
        )

    manifest = ShadowTrainingRunManifest(
        schema_version="p25_shadow_training.0",
        training_run_id=request.training_run_id,
        experiment_id=request.experiment_id,
        dataset_id=request.dataset_id,
        split_id=request.split_id,
        candidate_namespace=request.candidate_namespace,
        model_family=request.model_family,
        training_mode=request.training_mode,
        feature_names=list(request.feature_names),
        target_name=request.target_name,
        total_windows=len(split.get("windows", [])),
        completed_windows=len(artifacts),
        blocked_windows=0,
        failed_windows=0,
        hyperparameters=dict(request.hyperparameters),
        baseline_name=request.baseline_name,
        dataset_schema_version=str(dataset_manifest.get("schema_version", "unknown")),
        split_schema_version=str(split.get("schema_version", "unknown")),
        created_at=_utc_now(),
        safety_flags={
            "production_write_blocked": True,
            "canonical_snapshot_write_blocked": True,
            "live_trading_blocked": True,
        },
        warnings=[],
        notes=request.notes,
    )
    return ShadowTrainingRunResult(manifest=manifest, window_artifacts=artifacts)
