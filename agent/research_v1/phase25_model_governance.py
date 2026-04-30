"""Phase 25 shadow model evaluation and advisory governance."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from typing import Any


ALLOWED_PRIMARY_METRICS = {"rank_ic", "directional_hit_rate", "spread_return"}


class Phase25GovernanceError(ValueError):
    """Raised for unsafe Phase 25 evaluation requests."""


@dataclass(frozen=True)
class Phase25EvaluationRequest:
    evaluation_id: str
    training_run_id: str
    experiment_id: str
    candidate_namespace: str
    primary_metric: str
    min_completed_windows: int
    min_validation_predictions: int
    min_rank_ic_improvement: float
    min_hit_rate_improvement: float
    max_allowed_safety_violations: int
    promotion_review_enabled: bool
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.candidate_namespace.startswith("shadow_meta_model."):
            raise Phase25GovernanceError("candidate_namespace must start with shadow_meta_model")
        if self.primary_metric not in ALLOWED_PRIMARY_METRICS:
            raise Phase25GovernanceError("primary_metric is not allowed")
        if self.min_completed_windows < 4:
            raise Phase25GovernanceError("min_completed_windows must be >= 4")
        if self.min_validation_predictions < 20:
            raise Phase25GovernanceError("min_validation_predictions must be >= 20")
        if self.max_allowed_safety_violations != 0:
            raise Phase25GovernanceError("max_allowed_safety_violations must be 0")
        if self.promotion_review_enabled is not True:
            raise Phase25GovernanceError("promotion_review_enabled must be true")


@dataclass(frozen=True)
class WindowEvaluationResult:
    evaluation_id: str
    training_run_id: str
    window_id: str
    candidate_namespace: str
    validation_prediction_count: int
    model_rank_ic: float
    baseline_rank_ic: float
    rank_ic_improvement: float
    model_directional_hit_rate: float
    baseline_directional_hit_rate: float
    hit_rate_improvement: float
    model_spread_return: float
    baseline_spread_return: float
    spread_return_improvement: float
    status: str
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ShadowModelEvaluationReport:
    schema_version: str
    evaluation_id: str
    training_run_id: str
    experiment_id: str
    candidate_namespace: str
    model_family: str
    total_windows: int
    evaluated_windows: int
    blocked_windows: int
    total_validation_predictions: int
    aggregate_model_rank_ic: float
    aggregate_baseline_rank_ic: float
    aggregate_rank_ic_improvement: float
    aggregate_model_hit_rate: float
    aggregate_baseline_hit_rate: float
    aggregate_hit_rate_improvement: float
    aggregate_model_spread_return: float
    aggregate_baseline_spread_return: float
    aggregate_spread_return_improvement: float
    window_results: list[WindowEvaluationResult]
    safety_violations: list[str]
    warnings: list[str]
    baseline_source: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["window_results"] = [w.to_dict() for w in self.window_results]
        return data


@dataclass(frozen=True)
class PromotionReadinessDecision:
    schema_version: str
    evaluation_id: str
    training_run_id: str
    experiment_id: str
    candidate_namespace: str
    decision: str
    decision_reasons: list[str]
    required_observation_windows: int
    production_config_changes: dict[str, Any]
    apply_to_production: bool
    next_phase_recommendation: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["production_config_changes"] = {}
        data["apply_to_production"] = False
        return data


@dataclass(frozen=True)
class Phase25GovernanceResult:
    evaluation_report: ShadowModelEvaluationReport
    readiness_decision: PromotionReadinessDecision

    def to_dict(self) -> dict[str, Any]:
        return {
            "evaluation_report": self.evaluation_report.to_dict(),
            "readiness_decision": self.readiness_decision.to_dict(),
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
    raise Phase25GovernanceError("input must be dict-like")


def _get_manifest_dict(container: Any) -> dict[str, Any]:
    if isinstance(container, dict) and "manifest" in container:
        return _as_dict(container["manifest"])
    return _as_dict(container.manifest)


def _get_artifacts(training_result: Any) -> list[dict[str, Any]]:
    if isinstance(training_result, dict):
        return [_as_dict(a) for a in training_result.get("window_artifacts", [])]
    return [_as_dict(a) for a in training_result.window_artifacts]


# ─── Metric helpers ───────────────────────────────────────────────────────────

def _rank(values: list[float], reverse: bool = False) -> list[float]:
    if not values:
        return []
    indexed = sorted(enumerate(values), key=lambda item: item[1], reverse=reverse)
    ranks = [0.0] * len(values)
    i = 0
    while i < len(indexed):
        j = i
        tied_value = indexed[i][1]
        while j < len(indexed) and indexed[j][1] == tied_value:
            j += 1
        avg_rank = sum(range(i + 1, j + 1)) / (j - i)
        for k in range(i, j):
            ranks[indexed[k][0]] = float(avg_rank)
        i = j
    return ranks


def _pearson(xs: list[float], ys: list[float]) -> float:
    if len(xs) < 2 or len(xs) != len(ys):
        return 0.0
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    denom_x = sum((x - mean_x) ** 2 for x in xs) ** 0.5
    denom_y = sum((y - mean_y) ** 2 for y in ys) ** 0.5
    if denom_x == 0 or denom_y == 0:
        return 0.0
    return numerator / (denom_x * denom_y)


def _rank_ic(predictions: list[dict[str, Any]], value_key: str) -> float:
    scores = [float(pred[value_key]) for pred in predictions]
    targets = [float(pred["actual_target_value"]) for pred in predictions]
    return _pearson(_rank(scores, reverse=True), _rank(targets, reverse=True))


def _sign(value: float) -> int:
    return 1 if value > 0 else -1 if value < 0 else 0


def _hit_rate(predictions: list[dict[str, Any]], value_key: str) -> float:
    if not predictions:
        return 0.0
    hits = sum(
        1 for pred in predictions
        if _sign(float(pred[value_key])) == _sign(float(pred["actual_target_value"]))
    )
    return hits / len(predictions)


def _spread_return(predictions: list[dict[str, Any]], value_key: str) -> float:
    if len(predictions) < 2:
        return 0.0
    ordered = sorted(predictions, key=lambda pred: float(pred[value_key]), reverse=True)
    half = len(ordered) // 2
    if half == 0:
        return 0.0
    top = ordered[:half]
    bottom = ordered[-half:]
    top_avg = sum(float(p["actual_target_value"]) for p in top) / len(top)
    bottom_avg = sum(float(p["actual_target_value"]) for p in bottom) / len(bottom)
    return top_avg - bottom_avg


# ─── Baseline helpers ─────────────────────────────────────────────────────────

def _build_zero_baseline(artifacts: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    return {}


def _build_baseline_index(baseline_predictions: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    index: dict[str, dict[str, dict[str, Any]]] = {}
    for pred in baseline_predictions:
        window_id = str(pred.get("window_id", ""))
        snapshot_id = str(pred.get("snapshot_id", ""))
        if window_id not in index:
            index[window_id] = {}
        index[window_id][snapshot_id] = _as_dict(pred)
    return index


# ─── Safety validation ────────────────────────────────────────────────────────

def _validate_safety(training_result: Any, baseline_predictions: Any, request: Phase25EvaluationRequest) -> list[str]:
    manifest = _get_manifest_dict(training_result)
    artifacts = _get_artifacts(training_result)
    warnings: list[str] = []

    if str(manifest.get("training_run_id", "")) != str(request.training_run_id):
        warnings.append("training_run_id_mismatch")
    if str(manifest.get("experiment_id", "")) != str(request.experiment_id):
        warnings.append("experiment_id_mismatch")
    if str(manifest.get("candidate_namespace", "")) != str(request.candidate_namespace):
        warnings.append("candidate_namespace_mismatch")
    if manifest.get("target_name") != "net_return_pct":
        warnings.append("target_not_net_return_pct")

    safety_flags = manifest.get("safety_flags", {}) or {}
    for flag in ["production_write_blocked", "canonical_snapshot_write_blocked", "live_trading_blocked"]:
        if safety_flags.get(flag) is not True:
            warnings.append("training_safety_flag_false")

    if int(manifest.get("blocked_windows", 0)) > 0:
        warnings.append("training_has_blocked_windows")
    if int(manifest.get("failed_windows", 0)) > 0:
        warnings.append("training_has_failed_windows")

    for artifact in artifacts:
        status = str(artifact.get("training_status", "")).lower()
        if status != "completed":
            warnings.append("training_artifact_not_completed")
            break

    if baseline_predictions is not None:
        baseline_index = _build_baseline_index(baseline_predictions)
        for artifact in artifacts:
            window_id = str(artifact.get("window_id", ""))
            model_snapshots = {str(p["snapshot_id"]) for p in artifact.get("predictions", [])}
            baseline_snapshots = set(baseline_index.get(window_id, {}).keys())
            if model_snapshots != baseline_snapshots:
                warnings.append("baseline_snapshot_mismatch")
                break

    return sorted(set(warnings))


# ─── Window evaluation ────────────────────────────────────────────────────────

def _evaluate_window(
    window_artifact: dict[str, Any],
    request: Phase25EvaluationRequest,
    baseline_index: dict[str, dict[str, dict[str, Any]]],
) -> tuple[WindowEvaluationResult, bool]:
    window_id = str(window_artifact.get("window_id", ""))
    predictions = [_as_dict(p) for p in window_artifact.get("predictions", [])]
    warnings: list[str] = []

    if len(predictions) < 2:
        result = WindowEvaluationResult(
            evaluation_id=request.evaluation_id,
            training_run_id=request.training_run_id,
            window_id=window_id,
            candidate_namespace=request.candidate_namespace,
            validation_prediction_count=len(predictions),
            model_rank_ic=0.0,
            baseline_rank_ic=0.0,
            rank_ic_improvement=0.0,
            model_directional_hit_rate=0.0,
            baseline_directional_hit_rate=0.0,
            hit_rate_improvement=0.0,
            model_spread_return=0.0,
            baseline_spread_return=0.0,
            spread_return_improvement=0.0,
            status="blocked",
            warnings=["insufficient_validation_predictions"],
        )
        return result, True

    model_rank_ic = _rank_ic(predictions, "prediction_value")
    model_hit_rate = _hit_rate(predictions, "prediction_value")
    model_spread = _spread_return(predictions, "prediction_value")

    window_baseline = baseline_index.get(window_id, {})
    model_snapshot_ids = {str(p["snapshot_id"]) for p in predictions}

    if window_baseline:
        baseline_snapshot_ids = set(window_baseline.keys())
        if model_snapshot_ids != baseline_snapshot_ids:
            warnings.append("baseline_snapshot_mismatch")
            baseline_rank_ic = 0.0
            baseline_hit_rate = 0.0
            baseline_spread = 0.0
        else:
            snapshot_to_actual = {str(p["snapshot_id"]): float(p["actual_target_value"]) for p in predictions}
            baseline_preds = []
            for sid in sorted(model_snapshot_ids):
                baseline_row = window_baseline[sid]
                baseline_preds.append({
                    "baseline_prediction_value": float(baseline_row["baseline_prediction_value"]),
                    "actual_target_value": snapshot_to_actual[sid],
                })
            baseline_rank_ic = _rank_ic(baseline_preds, "baseline_prediction_value")
            baseline_hit_rate = _hit_rate(baseline_preds, "baseline_prediction_value")
            baseline_spread = _spread_return(baseline_preds, "baseline_prediction_value")
    else:
        baseline_rank_ic = 0.0
        baseline_hit_rate = 0.0
        baseline_spread = 0.0

    rank_ic_imp = model_rank_ic - baseline_rank_ic
    hit_rate_imp = model_hit_rate - baseline_hit_rate
    spread_imp = model_spread - baseline_spread

    result = WindowEvaluationResult(
        evaluation_id=request.evaluation_id,
        training_run_id=request.training_run_id,
        window_id=window_id,
        candidate_namespace=request.candidate_namespace,
        validation_prediction_count=len(predictions),
        model_rank_ic=model_rank_ic,
        baseline_rank_ic=baseline_rank_ic,
        rank_ic_improvement=rank_ic_imp,
        model_directional_hit_rate=model_hit_rate,
        baseline_directional_hit_rate=baseline_hit_rate,
        hit_rate_improvement=hit_rate_imp,
        model_spread_return=model_spread,
        baseline_spread_return=baseline_spread,
        spread_return_improvement=spread_imp,
        status="evaluated" if not warnings else "blocked",
        warnings=warnings,
    )
    return result, bool(warnings)


# ─── Decision gate ───────────────────────────────────────────────────────────

def _make_decision(
    request: Phase25EvaluationRequest,
    report: ShadowModelEvaluationReport,
) -> PromotionReadinessDecision:
    safety_violations = report.safety_violations

    if safety_violations:
        return PromotionReadinessDecision(
            schema_version="phase25_promotion_readiness.0",
            evaluation_id=request.evaluation_id,
            training_run_id=request.training_run_id,
            experiment_id=request.experiment_id,
            candidate_namespace=request.candidate_namespace,
            decision="blocked_by_safety",
            decision_reasons=safety_violations,
            required_observation_windows=0,
            production_config_changes={},
            apply_to_production=False,
            next_phase_recommendation="resolve_safety_violations",
            created_at=_utc_now(),
        )

    if report.evaluated_windows < request.min_completed_windows:
        return PromotionReadinessDecision(
            schema_version="phase25_promotion_readiness.0",
            evaluation_id=request.evaluation_id,
            training_run_id=request.training_run_id,
            experiment_id=request.experiment_id,
            candidate_namespace=request.candidate_namespace,
            decision="blocked_by_sample_size",
            decision_reasons=[f"only {report.evaluated_windows} windows evaluated, {request.min_completed_windows} required"],
            required_observation_windows=request.min_completed_windows - report.evaluated_windows,
            production_config_changes={},
            apply_to_production=False,
            next_phase_recommendation="collect_more_windows",
            created_at=_utc_now(),
        )

    if report.total_validation_predictions < request.min_validation_predictions:
        preds_needed = request.min_validation_predictions - report.total_validation_predictions
        avg_preds_per_window = report.total_validation_predictions // max(1, report.evaluated_windows)
        preds_per_window = max(avg_preds_per_window, 2)
        windows_needed = max(1, (preds_needed + preds_per_window - 1) // preds_per_window)
        return PromotionReadinessDecision(
            schema_version="phase25_promotion_readiness.0",
            evaluation_id=request.evaluation_id,
            training_run_id=request.training_run_id,
            experiment_id=request.experiment_id,
            candidate_namespace=request.candidate_namespace,
            decision="blocked_by_sample_size",
            decision_reasons=[f"only {report.total_validation_predictions} validation predictions, {request.min_validation_predictions} required"],
            required_observation_windows=windows_needed,
            production_config_changes={},
            apply_to_production=False,
            next_phase_recommendation="collect_more_predictions",
            created_at=_utc_now(),
        )

    primary = request.primary_metric
    if primary == "rank_ic":
        improvement = report.aggregate_rank_ic_improvement
    elif primary == "directional_hit_rate":
        improvement = report.aggregate_hit_rate_improvement
    else:
        improvement = report.aggregate_spread_return_improvement

    if improvement <= 0:
        return PromotionReadinessDecision(
            schema_version="phase25_promotion_readiness.0",
            evaluation_id=request.evaluation_id,
            training_run_id=request.training_run_id,
            experiment_id=request.experiment_id,
            candidate_namespace=request.candidate_namespace,
            decision="rejected_underperforms_baseline",
            decision_reasons=[f"{primary} improvement {improvement:.4f} <= 0"],
            required_observation_windows=0,
            production_config_changes={},
            apply_to_production=False,
            next_phase_recommendation="do_not_promote",
            created_at=_utc_now(),
        )

    if primary == "spread_return":
        rank_not_materially_negative = report.aggregate_rank_ic_improvement >= -0.01
        hit_not_materially_negative = report.aggregate_hit_rate_improvement >= -0.01
        if not (rank_not_materially_negative and hit_not_materially_negative):
            return PromotionReadinessDecision(
                schema_version="phase25_promotion_readiness.0",
                evaluation_id=request.evaluation_id,
                training_run_id=request.training_run_id,
                experiment_id=request.experiment_id,
                candidate_namespace=request.candidate_namespace,
                decision="watch_more_windows",
                decision_reasons=[
                    f"rank_ic improvement {report.aggregate_rank_ic_improvement:.4f} {'ok' if rank_not_materially_negative else 'materially negative'}",
                    f"hit_rate improvement {report.aggregate_hit_rate_improvement:.4f} {'ok' if hit_not_materially_negative else 'materially negative'}",
                ],
                required_observation_windows=max(0, request.min_completed_windows - report.evaluated_windows),
                production_config_changes={},
                apply_to_production=False,
                next_phase_recommendation="continue_shadow_observation",
                created_at=_utc_now(),
            )
    else:
        rank_ok = report.aggregate_rank_ic_improvement >= request.min_rank_ic_improvement
        hit_ok = report.aggregate_hit_rate_improvement >= request.min_hit_rate_improvement
        if not (rank_ok and hit_ok):
            return PromotionReadinessDecision(
                schema_version="phase25_promotion_readiness.0",
                evaluation_id=request.evaluation_id,
                training_run_id=request.training_run_id,
                experiment_id=request.experiment_id,
                candidate_namespace=request.candidate_namespace,
                decision="watch_more_windows",
                decision_reasons=[
                    f"rank_ic improvement {report.aggregate_rank_ic_improvement:.4f} {'ok' if rank_ok else f'below {request.min_rank_ic_improvement}'}",
                    f"hit_rate improvement {report.aggregate_hit_rate_improvement:.4f} {'ok' if hit_ok else f'below {request.min_hit_rate_improvement}'}",
                ],
                required_observation_windows=max(0, request.min_completed_windows - report.evaluated_windows),
                production_config_changes={},
                apply_to_production=False,
                next_phase_recommendation="continue_shadow_observation",
                created_at=_utc_now(),
            )

    return PromotionReadinessDecision(
        schema_version="phase25_promotion_readiness.0",
        evaluation_id=request.evaluation_id,
        training_run_id=request.training_run_id,
        experiment_id=request.experiment_id,
        candidate_namespace=request.candidate_namespace,
        decision="ready_for_phase26_shadow_portfolio",
        decision_reasons=[f"all gates passed on {report.evaluated_windows} windows"],
        required_observation_windows=0,
        production_config_changes={},
        apply_to_production=False,
        next_phase_recommendation="proceed_to_phase26_shadow_portfolio",
        created_at=_utc_now(),
    )


# ─── Public API ───────────────────────────────────────────────────────────────

def evaluate_shadow_model_governance(
    training_result: Any,
    baseline_predictions: Any,
    request: Phase25EvaluationRequest,
) -> Phase25GovernanceResult:
    safety_warnings = _validate_safety(training_result, baseline_predictions, request)

    manifest = _get_manifest_dict(training_result)
    artifacts = _get_artifacts(training_result)

    if baseline_predictions is None:
        baseline_index: dict[str, dict[str, dict[str, Any]]] = _build_zero_baseline(artifacts)
        baseline_warnings = ["baseline_generated_zero"]
    else:
        baseline_index = _build_baseline_index(baseline_predictions)
        baseline_warnings = []

    window_results: list[WindowEvaluationResult] = []
    for artifact in artifacts:
        result, has_warning = _evaluate_window(artifact, request, baseline_index)
        window_results.append(result)
        if has_warning:
            safety_warnings = sorted(set(safety_warnings + ["baseline_snapshot_mismatch"]))

    evaluated_results = [w for w in window_results if w.status == "evaluated"]
    n = len(evaluated_results)
    agg_model_rank_ic = sum(w.model_rank_ic for w in evaluated_results) / n if n else 0.0
    agg_baseline_rank_ic = sum(w.baseline_rank_ic for w in evaluated_results) / n if n else 0.0
    agg_rank_ic_imp = agg_model_rank_ic - agg_baseline_rank_ic
    agg_model_hit = sum(w.model_directional_hit_rate for w in evaluated_results) / n if n else 0.0
    agg_baseline_hit = sum(w.baseline_directional_hit_rate for w in evaluated_results) / n if n else 0.0
    agg_hit_imp = agg_model_hit - agg_baseline_hit
    agg_model_spread = sum(w.model_spread_return for w in evaluated_results) / n if n else 0.0
    agg_baseline_spread = sum(w.baseline_spread_return for w in evaluated_results) / n if n else 0.0
    agg_spread_imp = agg_model_spread - agg_baseline_spread
    total_preds = sum(w.validation_prediction_count for w in evaluated_results)
    evaluation_blocked = len(window_results) - len(evaluated_results)

    report = ShadowModelEvaluationReport(
        schema_version="phase25_model_evaluation.1",
        evaluation_id=request.evaluation_id,
        training_run_id=request.training_run_id,
        experiment_id=request.experiment_id,
        candidate_namespace=request.candidate_namespace,
        model_family=str(manifest.get("model_family", "unknown")),
        total_windows=int(manifest.get("completed_windows", 0)),
        evaluated_windows=len(evaluated_results),
        blocked_windows=int(manifest.get("blocked_windows", 0)) + evaluation_blocked,
        total_validation_predictions=total_preds,
        aggregate_model_rank_ic=agg_model_rank_ic,
        aggregate_baseline_rank_ic=agg_baseline_rank_ic,
        aggregate_rank_ic_improvement=agg_rank_ic_imp,
        aggregate_model_hit_rate=agg_model_hit,
        aggregate_baseline_hit_rate=agg_baseline_hit,
        aggregate_hit_rate_improvement=agg_hit_imp,
        aggregate_model_spread_return=agg_model_spread,
        aggregate_baseline_spread_return=agg_baseline_spread,
        aggregate_spread_return_improvement=agg_spread_imp,
        window_results=window_results,
        safety_violations=safety_warnings,
        warnings=baseline_warnings,
        baseline_source="generated_zero" if baseline_predictions is None else "supplied",
        created_at=_utc_now(),
    )

    decision = _make_decision(request, report)

    return Phase25GovernanceResult(evaluation_report=report, readiness_decision=decision)
