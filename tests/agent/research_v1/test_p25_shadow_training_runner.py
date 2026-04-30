"""P25-D Shadow Offline Training Runner acceptance tests."""

import json
from dataclasses import dataclass

import pytest

from agent.research_v1.p25_shadow_training_runner import (
    ShadowTrainingError,
    ShadowTrainingRequest,
    run_shadow_offline_training,
)


@dataclass
class DatasetManifest:
    dataset_id: str = "dataset_xgb_meta_21d"
    candidate_namespace: str = "shadow_meta_model.xgb_v1"
    feature_names: list = None
    target_name: str = "net_return_pct"
    horizon_days: int = 21
    return_basis: str = "net"
    point_in_time_confirmed: bool = True
    meets_min_rows: bool = True
    schema_version: str = "p25_training_dataset.0"

    def __post_init__(self):
        if self.feature_names is None:
            self.feature_names = ["company_quality_score", "valuation_attractiveness_score"]


@dataclass
class DatasetResult:
    manifest: DatasetManifest
    rows: list


@dataclass
class SplitWindow:
    window_id: str
    train_snapshot_ids: list
    validation_snapshot_ids: list
    train_row_count: int = 2
    validation_row_count: int = 2
    train_start: str = "2026-01-01"
    train_end: str = "2026-01-10"
    validation_start: str = "2026-01-13"
    validation_end: str = "2026-01-20"


@dataclass
class SplitManifest:
    split_id: str = "split_xgb_meta_21d"
    dataset_id: str = "dataset_xgb_meta_21d"
    candidate_namespace: str = "shadow_meta_model.xgb_v1"
    walk_forward_enabled: bool = True
    schema_version: str = "p25_split_manifest.0"
    windows: list = None

    def __post_init__(self):
        if self.windows is None:
            self.windows = [SplitWindow("w1", ["s1", "s2"], ["s3", "s4"])]


@dataclass
class ExperimentManifest:
    experiment_id: str = "exp_xgb_v1"
    candidate_namespace: str = "shadow_meta_model.xgb_v1"
    candidate_family: str = "xgboost"
    status: str = "registered"
    output_namespace: str = "shadow_meta_model.xgb_v1"
    production_write_blocked: bool = True
    canonical_snapshot_write_blocked: bool = True
    live_trading_blocked: bool = True


def _row(snapshot_id, trading_day, quality, valuation, target):
    return {
        "snapshot_id": snapshot_id,
        "ticker": snapshot_id.upper(),
        "trading_day": trading_day,
        "features": {
            "company_quality_score": quality,
            "valuation_attractiveness_score": valuation,
        },
        "target_name": "net_return_pct",
        "target_value": target,
        "horizon_days": 21,
    }


def _dataset(rows=None, manifest=None):
    return DatasetResult(
        manifest=manifest or DatasetManifest(),
        rows=rows
        or [
            _row("s1", "2026-01-01", 0.8, 0.3, 0.04),
            _row("s2", "2026-01-02", 0.2, 0.7, -0.02),
            _row("s3", "2026-01-13", 0.9, 0.4, 0.05),
            _row("s4", "2026-01-14", 0.1, 0.8, -0.03),
        ],
    )


def _request(**overrides):
    values = dict(
        training_run_id="train_run_001",
        experiment_id="exp_xgb_v1",
        dataset_id="dataset_xgb_meta_21d",
        split_id="split_xgb_meta_21d",
        candidate_namespace="shadow_meta_model.xgb_v1",
        model_family="linear_baseline",
        feature_names=["company_quality_score", "valuation_attractiveness_score"],
        target_name="net_return_pct",
        training_mode="shadow_offline",
        hyperparameters={"prediction_clip": 1.0},
        baseline_name="linear_covariance_baseline",
        notes="test run",
    )
    values.update(overrides)
    return ShadowTrainingRequest(**values)


# ─── Request Validation ──────────────────────────────────────────────────────

def test_request_rejects_unsafe_values():
    with pytest.raises(ShadowTrainingError, match="candidate_namespace must start with shadow_meta_model"):
        _request(candidate_namespace="production.bad")
    with pytest.raises(ShadowTrainingError, match="target_name must be net_return_pct"):
        _request(target_name="gross_return_pct")
    with pytest.raises(ShadowTrainingError, match="feature_names must be non-empty"):
        _request(feature_names=[])


def test_dry_run_contracts_are_json_serializable():
    result = run_shadow_offline_training(
        _dataset(),
        SplitManifest(),
        ExperimentManifest(),
        _request(training_mode="dry_run", model_family="linear_baseline"),
    )

    assert result.manifest.schema_version == "p25_shadow_training.0"
    assert result.manifest.completed_windows == 1
    assert result.window_artifacts[0].training_status == "completed"
    assert all(pred["prediction_value"] == 0.0 for pred in result.window_artifacts[0].predictions)
    json.dumps(result.to_dict())


# ─── Safety Blocks ─────────────────────────────────────────────────────────────

def test_namespace_mismatch_blocks_run():
    split = SplitManifest(candidate_namespace="shadow_meta_model.other")
    result = run_shadow_offline_training(_dataset(), split, ExperimentManifest(), _request())

    assert result.manifest.completed_windows == 0
    assert "candidate_namespace_mismatch" in result.manifest.warnings


def test_non_net_dataset_blocks_run():
    manifest = DatasetManifest(return_basis="gross")
    result = run_shadow_offline_training(_dataset(manifest=manifest), SplitManifest(), ExperimentManifest(), _request())

    assert result.manifest.blocked_windows == 1
    assert "return_basis_not_net" in result.manifest.warnings


def test_point_in_time_false_blocks_run():
    manifest = DatasetManifest(point_in_time_confirmed=False)
    result = run_shadow_offline_training(_dataset(manifest=manifest), SplitManifest(), ExperimentManifest(), _request())

    assert "point_in_time_not_confirmed" in result.manifest.warnings


def test_production_safety_flag_false_blocks_run():
    experiment = ExperimentManifest(production_write_blocked=False)
    result = run_shadow_offline_training(_dataset(), SplitManifest(), experiment, _request())

    assert "production_write_blocked_false" in result.manifest.warnings


def test_missing_split_snapshot_id_blocks_run():
    split = SplitManifest(windows=[SplitWindow("w1", ["s1", "missing"], ["s3"])])
    result = run_shadow_offline_training(_dataset(), split, ExperimentManifest(), _request())

    assert "split_snapshot_id_missing_from_dataset" in result.manifest.warnings


def test_train_validation_overlap_blocks_run():
    split = SplitManifest(windows=[SplitWindow("w1", ["s1", "s2"], ["s2", "s3"])])
    result = run_shadow_offline_training(_dataset(), split, ExperimentManifest(), _request())

    assert "train_validation_overlap" in result.manifest.warnings


def test_requested_feature_not_in_dataset_manifest_blocks_run():
    result = run_shadow_offline_training(
        _dataset(),
        SplitManifest(),
        ExperimentManifest(),
        _request(feature_names=["company_quality_score", "missing_feature"]),
    )

    assert "requested_feature_not_in_dataset_manifest" in result.manifest.warnings


def test_experiment_id_mismatch_blocks_run():
    result = run_shadow_offline_training(
        _dataset(),
        SplitManifest(),
        ExperimentManifest(),
        _request(experiment_id="wrong_experiment"),
    )

    assert result.manifest.completed_windows == 0
    assert "experiment_id_mismatch" in result.manifest.warnings


def test_row_target_name_mismatch_blocks_run():
    bad_rows = [
        _row("s1", "2026-01-01", 0.8, 0.3, 0.04),
        _row("s2", "2026-01-02", 0.2, 0.7, -0.02),
        _row("s3", "2026-01-13", 0.9, 0.4, 0.05),
        _row("s4", "2026-01-14", 0.1, 0.8, -0.03),
    ]
    bad_rows[0]["target_name"] = "gross_return_pct"
    result = run_shadow_offline_training(
        _dataset(rows=bad_rows),
        SplitManifest(),
        ExperimentManifest(),
        _request(),
    )

    assert "row_target_name_mismatch" in result.manifest.warnings


def test_row_horizon_days_mismatch_blocks_run():
    bad_rows = [
        _row("s1", "2026-01-01", 0.8, 0.3, 0.04),
        _row("s2", "2026-01-02", 0.2, 0.7, -0.02),
        _row("s3", "2026-01-13", 0.9, 0.4, 0.05),
        _row("s4", "2026-01-14", 0.1, 0.8, -0.03),
    ]
    bad_rows[0]["horizon_days"] = 63
    result = run_shadow_offline_training(
        _dataset(rows=bad_rows),
        SplitManifest(),
        ExperimentManifest(),
        _request(),
    )

    assert "row_horizon_days_mismatch" in result.manifest.warnings


def test_blocked_result_safety_flags_reflect_experiment():
    experiment = ExperimentManifest(production_write_blocked=False, live_trading_blocked=True)
    result = run_shadow_offline_training(
        _dataset(),
        SplitManifest(),
        experiment,
        _request(),
    )

    assert result.manifest.safety_flags["production_write_blocked"] is False
    assert result.manifest.safety_flags["canonical_snapshot_write_blocked"] is True


def test_unsupported_model_family_blocks_shadow_offline():
    result = run_shadow_offline_training(
        _dataset(),
        SplitManifest(),
        ExperimentManifest(),
        _request(model_family="xgboost_style_stub", training_mode="shadow_offline"),
    )

    assert result.manifest.completed_windows == 0
    assert any("unsupported_model_family_for_shadow_offline" in w for w in result.manifest.warnings)


# ─── Linear Baseline Training ─────────────────────────────────────────────────

def test_linear_baseline_predicts_validation_rows():
    result = run_shadow_offline_training(_dataset(), SplitManifest(), ExperimentManifest(), _request())

    artifact = result.window_artifacts[0]
    assert artifact.fitted_parameters["mode"] == "linear_baseline"
    assert len(artifact.predictions) == 2
    assert {pred["snapshot_id"] for pred in artifact.predictions} == {"s3", "s4"}
    assert all("actual_target_value" in pred for pred in artifact.predictions)


def test_validation_targets_do_not_affect_predictions():
    baseline = run_shadow_offline_training(_dataset(), SplitManifest(), ExperimentManifest(), _request())
    changed_rows = [dict(row) for row in _dataset().rows]
    for row in changed_rows:
        if row["snapshot_id"] in {"s3", "s4"}:
            row["target_value"] = row["target_value"] * 1000
    changed = run_shadow_offline_training(_dataset(rows=changed_rows), SplitManifest(), ExperimentManifest(), _request())

    baseline_predictions = [(pred["snapshot_id"], pred["prediction_value"]) for pred in baseline.window_artifacts[0].predictions]
    changed_predictions = [(pred["snapshot_id"], pred["prediction_value"]) for pred in changed.window_artifacts[0].predictions]
    assert baseline_predictions == changed_predictions


def test_repeated_runs_are_deterministic_except_created_at():
    first = run_shadow_offline_training(_dataset(), SplitManifest(), ExperimentManifest(), _request()).to_dict()
    second = run_shadow_offline_training(_dataset(), SplitManifest(), ExperimentManifest(), _request()).to_dict()
    first["manifest"]["created_at"] = "normalized"
    second["manifest"]["created_at"] = "normalized"

    assert first == second


# ─── Namespace / Import Safety ─────────────────────────────────────────────────

def test_artifacts_stay_inside_namespace():
    result = run_shadow_offline_training(_dataset(), SplitManifest(), ExperimentManifest(), _request())

    for artifact in result.window_artifacts:
        assert artifact.candidate_namespace == "shadow_meta_model.xgb_v1"
        assert artifact.candidate_namespace == result.manifest.candidate_namespace


def test_no_model_libraries_imported():
    import agent.research_v1.p25_shadow_training_runner as runner_module

    forbidden = {"xgboost", "sklearn", "torch", "tensorflow", "stable_baselines3", "numpy", "pandas"}
    assert set(runner_module.__dict__).isdisjoint(forbidden)
