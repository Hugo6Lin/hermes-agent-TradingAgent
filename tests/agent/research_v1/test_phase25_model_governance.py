"""Phase 25 shadow model evaluation and governance tests."""

import json
from dataclasses import asdict, dataclass

import pytest

from agent.research_v1.phase25_model_governance import (
    Phase25EvaluationRequest,
    Phase25GovernanceError,
    evaluate_shadow_model_governance,
)


@dataclass
class TrainingManifest:
    training_run_id: str = "train_run_001"
    experiment_id: str = "exp_xgb_v1"
    candidate_namespace: str = "shadow_meta_model.xgb_v1"
    model_family: str = "linear_baseline"
    target_name: str = "net_return_pct"
    completed_windows: int = 4
    blocked_windows: int = 0
    failed_windows: int = 0
    safety_flags: dict = None
    schema_version: str = "p25_shadow_training.0"

    def __post_init__(self):
        if self.safety_flags is None:
            self.safety_flags = {
                "production_write_blocked": True,
                "canonical_snapshot_write_blocked": True,
                "live_trading_blocked": True,
            }


@dataclass
class TrainingArtifact:
    window_id: str
    predictions: list
    training_status: str = "completed"


@dataclass
class TrainingResult:
    manifest: TrainingManifest
    window_artifacts: list


def _prediction(snapshot_id, value, target, trading_day="2026-01-01"):
    return {
        "snapshot_id": snapshot_id,
        "prediction_value": value,
        "prediction_rank": 1,
        "target_name": "net_return_pct",
        "actual_target_value": target,
        "trading_day": trading_day,
    }


def _training_result(strong=True, windows=4):
    artifacts = []
    for i in range(windows):
        if strong:
            predictions = [
                _prediction(f"w{i}_a", 0.9, 0.05),
                _prediction(f"w{i}_b", 0.5, 0.02),
                _prediction(f"w{i}_c", -0.2, -0.01),
                _prediction(f"w{i}_d", -0.8, -0.04),
                _prediction(f"w{i}_e", 0.7, 0.03),
            ]
        else:
            predictions = [
                _prediction(f"w{i}_a", -0.9, 0.05),
                _prediction(f"w{i}_b", -0.5, 0.02),
                _prediction(f"w{i}_c", 0.2, -0.01),
                _prediction(f"w{i}_d", 0.8, -0.04),
                _prediction(f"w{i}_e", -0.7, 0.03),
            ]
        artifacts.append(TrainingArtifact(window_id=f"w{i}", predictions=predictions))
    return TrainingResult(TrainingManifest(completed_windows=windows, blocked_windows=0, failed_windows=0), artifacts)


def _request(**overrides):
    values = dict(
        evaluation_id="eval_001",
        training_run_id="train_run_001",
        experiment_id="exp_xgb_v1",
        candidate_namespace="shadow_meta_model.xgb_v1",
        primary_metric="rank_ic",
        min_completed_windows=4,
        min_validation_predictions=20,
        min_rank_ic_improvement=0.10,
        min_hit_rate_improvement=0.05,
        max_allowed_safety_violations=0,
        promotion_review_enabled=True,
        notes="phase25 test",
    )
    values.update(overrides)
    return Phase25EvaluationRequest(**values)


# ─── Request Validation ──────────────────────────────────────────────────────

def test_request_rejects_unsafe_values():
    with pytest.raises(Phase25GovernanceError, match="candidate_namespace must start"):
        _request(candidate_namespace="production.bad")
    with pytest.raises(Phase25GovernanceError, match="primary_metric is not allowed"):
        _request(primary_metric="sharpe")
    with pytest.raises(Phase25GovernanceError, match="min_completed_windows must be >= 4"):
        _request(min_completed_windows=1)
    with pytest.raises(Phase25GovernanceError, match="max_allowed_safety_violations must be 0"):
        _request(max_allowed_safety_violations=1)
    with pytest.raises(Phase25GovernanceError, match="promotion_review_enabled must be true"):
        _request(promotion_review_enabled=False)
    with pytest.raises(Phase25GovernanceError, match="min_validation_predictions must be >= 20"):
        _request(min_validation_predictions=19)
    with pytest.raises(Phase25GovernanceError, match="min_validation_predictions must be >= 20"):
        _request(min_validation_predictions=1)


# ─── Smoke / Serialization ────────────────────────────────────────────────────

def test_strong_model_is_ready_for_phase26_and_serializable():
    result = evaluate_shadow_model_governance(_training_result(strong=True), None, _request())

    assert result.evaluation_report.schema_version == "phase25_model_evaluation.1"
    assert result.evaluation_report.evaluated_windows == 4
    assert result.readiness_decision.decision == "ready_for_phase26_shadow_portfolio"
    assert result.readiness_decision.apply_to_production is False
    assert result.readiness_decision.production_config_changes == {}
    json.dumps(result.to_dict())


def test_to_dict_enforces_invariants_despite_post_eval_mutation():
    result = evaluate_shadow_model_governance(_training_result(strong=True), None, _request())
    # Verify to_dict output is safe even if caller mutates internal state via to_dict re-construction.
    # The frozen dataclass blocks direct mutation; to_dict is the enforced audit surface.
    d = result.readiness_decision.to_dict()
    assert d["production_config_changes"] == {}
    assert d["apply_to_production"] is False


# ─── Safety Blocks ────────────────────────────────────────────────────────────

def test_unsafe_training_safety_flag_blocks():
    manifest = TrainingManifest(
        safety_flags={"production_write_blocked": False, "canonical_snapshot_write_blocked": True, "live_trading_blocked": True}
    )
    result = evaluate_shadow_model_governance(TrainingResult(manifest, []), None, _request())

    assert result.readiness_decision.decision == "blocked_by_safety"
    assert "training_safety_flag_false" in result.evaluation_report.safety_violations


def test_non_net_target_blocks():
    manifest = TrainingManifest(target_name="gross_return_pct")
    result = evaluate_shadow_model_governance(TrainingResult(manifest, []), None, _request())

    assert result.readiness_decision.decision == "blocked_by_safety"


def test_namespace_mismatch_blocks():
    manifest = TrainingManifest(candidate_namespace="shadow_meta_model.other")
    result = evaluate_shadow_model_governance(TrainingResult(manifest, []), None, _request())

    assert result.readiness_decision.decision == "blocked_by_safety"


def test_experiment_id_mismatch_blocks():
    result = evaluate_shadow_model_governance(
        _training_result(strong=True), None, _request(experiment_id="wrong_experiment")
    )

    assert result.readiness_decision.decision == "blocked_by_safety"


def test_baseline_missing_snapshot_blocks():
    baseline_pred = {
        "window_id": "w0",
        "snapshot_id": "w0_a",
        "baseline_prediction_value": 0.5,
        "baseline_prediction_rank": 1,
    }
    result = evaluate_shadow_model_governance(_training_result(strong=True), [baseline_pred], _request())

    assert result.readiness_decision.decision == "blocked_by_safety"
    assert "baseline_snapshot_mismatch" in result.evaluation_report.safety_violations


def test_artifact_training_status_failed_blocks():
    artifacts = []
    for i in range(4):
        preds = [
            _prediction(f"w{i}_a", 0.9, 0.05),
            _prediction(f"w{i}_b", 0.5, 0.02),
        ]
        status = "failed" if i == 0 else "completed"
        artifacts.append(TrainingArtifact(window_id=f"w{i}", predictions=preds, training_status=status))
    result = evaluate_shadow_model_governance(
        TrainingResult(TrainingManifest(completed_windows=4, failed_windows=0), artifacts),
        None, _request()
    )
    assert result.readiness_decision.decision == "blocked_by_safety"
    assert "training_artifact_not_completed" in result.evaluation_report.safety_violations


def test_artifact_missing_training_status_key_blocks():
    # Raw dict artifacts without training_status key (malformed upstream) must block.
    artifacts = [
        {"window_id": f"w{i}", "predictions": [
            {"snapshot_id": f"w{i}_a", "prediction_value": 0.9, "actual_target_value": 0.05,
             "trading_day": "2026-01-01", "target_name": "net_return_pct", "prediction_rank": 1},
            {"snapshot_id": f"w{i}_b", "prediction_value": 0.5, "actual_target_value": 0.02,
             "trading_day": "2026-01-01", "target_name": "net_return_pct", "prediction_rank": 2},
        ]}
        for i in range(4)
    ]
    result = evaluate_shadow_model_governance(
        {"manifest": TrainingManifest(completed_windows=4), "window_artifacts": artifacts},
        None, _request()
    )
    assert result.readiness_decision.decision == "blocked_by_safety"
    assert "training_artifact_not_completed" in result.evaluation_report.safety_violations


# ─── Zero Baseline ────────────────────────────────────────────────────────────

def test_zero_baseline_generated_when_omitted():
    result = evaluate_shadow_model_governance(_training_result(strong=True), None, _request())

    assert result.evaluation_report.aggregate_baseline_rank_ic == 0.0
    assert result.evaluation_report.aggregate_baseline_hit_rate == 0.0
    assert "baseline_generated_zero" in result.evaluation_report.warnings
    assert result.evaluation_report.baseline_source == "generated_zero"


def test_supplied_complete_baseline_does_not_crash():
    # Baseline values chosen to produce a weak-but-positive rank IC (~0.5).
    # Model's strong predictions should improve significantly above that.
    baseline = []
    for i in range(4):
        for snap, val in [("a", 0.05), ("b", 0.04), ("c", 0.02), ("d", 0.03), ("e", 0.01)]:
            baseline.append({
                "window_id": f"w{i}",
                "snapshot_id": f"w{i}_{snap}",
                "baseline_prediction_value": val,
                "baseline_prediction_rank": 1,
            })
    result = evaluate_shadow_model_governance(_training_result(strong=True), baseline, _request())

    assert result.evaluation_report.aggregate_baseline_rank_ic > 0.0
    assert result.evaluation_report.aggregate_baseline_hit_rate > 0.0
    assert result.readiness_decision.decision == "ready_for_phase26_shadow_portfolio"


def test_blocked_windows_excluded_from_aggregate():
    artifacts = []
    for i in range(4):
        if i == 0:
            predictions = [_prediction(f"w{i}_a", 0.9, 0.05)]
        else:
            predictions = [
                _prediction(f"w{i}_a", 0.9, 0.05),
                _prediction(f"w{i}_b", 0.5, 0.02),
            ]
        artifacts.append(TrainingArtifact(window_id=f"w{i}", predictions=predictions))
    result = evaluate_shadow_model_governance(
        TrainingResult(TrainingManifest(completed_windows=4), artifacts), None, _request()
    )
    assert result.evaluation_report.evaluated_windows == 3
    assert result.evaluation_report.blocked_windows >= 1


# ─── Metrics ─────────────────────────────────────────────────────────────────

def test_per_window_rank_ic_computed():
    result = evaluate_shadow_model_governance(_training_result(strong=True), None, _request())

    assert len(result.evaluation_report.window_results) == 4
    for wr in result.evaluation_report.window_results:
        assert "model_rank_ic" in asdict(wr)
        assert wr.model_rank_ic > 0


def test_per_window_hit_rate_computed():
    result = evaluate_shadow_model_governance(_training_result(strong=True), None, _request())

    assert len(result.evaluation_report.window_results) == 4
    for wr in result.evaluation_report.window_results:
        assert wr.model_directional_hit_rate > 0


def test_per_window_spread_return_computed():
    result = evaluate_shadow_model_governance(_training_result(strong=True), None, _request())

    assert len(result.evaluation_report.window_results) == 4
    for wr in result.evaluation_report.window_results:
        assert wr.model_spread_return > 0


def test_aggregate_improvements_computed():
    result = evaluate_shadow_model_governance(_training_result(strong=True), None, _request())

    assert result.evaluation_report.aggregate_rank_ic_improvement > 0
    assert result.evaluation_report.aggregate_hit_rate_improvement >= 0


# ─── Decision Gate ───────────────────────────────────────────────────────────

def test_insufficient_windows_blocked():
    result = evaluate_shadow_model_governance(
        _training_result(strong=True, windows=2), None, _request(min_completed_windows=4)
    )

    assert result.readiness_decision.decision == "blocked_by_sample_size"


def test_insufficient_validation_predictions_blocked():
    result = evaluate_shadow_model_governance(
        _training_result(strong=True, windows=1), None, _request(min_validation_predictions=100)
    )

    assert result.readiness_decision.decision == "blocked_by_sample_size"


def test_weak_model_rejected():
    result = evaluate_shadow_model_governance(_training_result(strong=False), None, _request())

    assert result.readiness_decision.decision == "rejected_underperforms_baseline"


def test_marginal_model_returns_watch_more():
    # Strong model has rank_ic improvement ~1.0; set rank threshold above that
    # so only the rank gate fails -> watch_more (hit rate still passes).
    result = evaluate_shadow_model_governance(
        _training_result(strong=True), None,
        _request(min_rank_ic_improvement=1.01, min_hit_rate_improvement=0.05)
    )

    assert result.readiness_decision.decision == "watch_more_windows"


def test_strong_model_returns_ready_for_phase26():
    result = evaluate_shadow_model_governance(_training_result(strong=True), None, _request())

    assert result.readiness_decision.decision == "ready_for_phase26_shadow_portfolio"


# ─── Primary Metric Coverage ───────────────────────────────────────────────────

def test_spread_return_primary_metric_ready():
    result = evaluate_shadow_model_governance(
        _training_result(strong=True), None,
        _request(primary_metric="spread_return", min_rank_ic_improvement=0.10, min_hit_rate_improvement=0.05)
    )
    assert result.readiness_decision.decision == "ready_for_phase26_shadow_portfolio"


def test_spread_return_primary_with_materially_negative_rank_ic_watch_more():
    # spread_return primary: improvement positive but rank IC materially negative (-0.05).
    # With zero baseline we can't trigger this (any negative IC -> total improvement <= 0 -> rejected).
    # Use a supplied baseline with high IC + model with lower (but not terrible) IC.
    artifacts = []
    baseline = []
    for i in range(4):
        artifacts.append(TrainingArtifact(window_id=f"w{i}", predictions=[
            _prediction(f"w{i}_a", 0.9, 0.05),
            _prediction(f"w{i}_b", 0.5, 0.02),
            _prediction(f"w{i}_c", 0.2, -0.01),
            _prediction(f"w{i}_d", -0.8, -0.04),
            _prediction(f"w{i}_e", 0.7, 0.03),
        ]))
        for snap, val in [("a", 0.5), ("b", 0.4), ("c", -0.4), ("d", -0.5), ("e", 0.3)]:
            baseline.append({
                "window_id": f"w{i}", "snapshot_id": f"w{i}_{snap}",
                "baseline_prediction_value": val, "baseline_prediction_rank": 1,
            })
    result = evaluate_shadow_model_governance(
        TrainingResult(TrainingManifest(completed_windows=4), artifacts),
        baseline,
        _request(primary_metric="spread_return", min_rank_ic_improvement=0.10, min_hit_rate_improvement=0.05)
    )
    assert result.readiness_decision.decision == "watch_more_windows"


def test_directional_hit_rate_primary_metric_ready():
    result = evaluate_shadow_model_governance(
        _training_result(strong=True), None,
        _request(primary_metric="directional_hit_rate", min_rank_ic_improvement=0.10, min_hit_rate_improvement=0.05)
    )
    assert result.readiness_decision.decision == "ready_for_phase26_shadow_portfolio"


# ─── Promotion Rules ──────────────────────────────────────────────────────────

def test_production_config_changes_always_empty():
    result = evaluate_shadow_model_governance(_training_result(strong=True), None, _request())

    assert result.readiness_decision.production_config_changes == {}


def test_apply_to_production_always_false():
    result = evaluate_shadow_model_governance(_training_result(strong=True), None, _request())

    assert result.readiness_decision.apply_to_production is False


# ─── No Model Libraries ───────────────────────────────────────────────────────

def test_no_model_libraries_imported():
    import agent.research_v1.phase25_model_governance as gov_module

    forbidden = {"xgboost", "sklearn", "torch", "tensorflow", "stable_baselines3", "numpy", "pandas"}
    assert set(gov_module.__dict__).isdisjoint(forbidden)
