"""P25-B Offline Training Dataset Builder acceptance tests."""

import json

import pytest

from agent.research_v1.p25_training_dataset_builder import (
    TrainingDatasetBuilderError,
    TrainingDatasetRequest,
    build_training_dataset,
)


FEATURE_NAMES = [
    "company_quality_score",
    "valuation_attractiveness_score",
    "timing_market_fit_score",
    "llm_adjustment_total",
    "coverage_confidence_score",
]


def _request(**overrides):
    values = dict(
        dataset_id="dataset_xgb_meta_21d",
        candidate_namespace="shadow_meta_model.xgb_v1",
        horizon_days=21,
        feature_names=list(FEATURE_NAMES),
        target_name="net_return_pct",
        min_rows=1,
        require_point_in_time=True,
        require_universe_membership=True,
        max_source_audit_gap_rate=0.20,
        notes="test dataset",
    )
    values.update(overrides)
    return TrainingDatasetRequest(**values)


def _snapshot(**overrides):
    values = dict(
        snapshot_id="snap_1",
        ticker="MSFT",
        trading_day="2026-01-05",
        company_quality_score=80,
        valuation_attractiveness_score=60,
        timing_market_fit_score=50,
        llm_adjustment_total=10,
        coverage_confidence_score=0.9,
        data_as_of_date="2026-01-04",
        universe_membership_snapshot_id="sp500_2026_01_05",
        schema_version="p20_factor_snapshot.0",
        lookahead_violation=False,
        source_audit_gap=0.0,
    )
    values.update(overrides)
    return values


def _forward_return(**overrides):
    values = dict(
        snapshot_id="snap_1",
        horizon_days=21,
        net_return_pct=0.05,
        gross_return_pct=0.055,
        transaction_cost_pct=0.005,
        return_basis="net",
        computed_at="2026-02-01T00:00:00Z",
        schema_version="p20_forward_return.0",
    )
    values.update(overrides)
    return values


# ─── Happy Path ────────────────────────────────────────────────────────────────

def test_valid_snapshot_and_net_forward_return_produces_one_row():
    result = build_training_dataset([_snapshot()], [_forward_return()], _request())

    assert result.manifest.schema_version == "p25_training_dataset.0"
    assert result.manifest.included_rows == 1
    assert result.manifest.target_name == "net_return_pct"
    assert result.manifest.return_basis == "net"
    assert result.manifest.point_in_time_confirmed is True
    assert result.rows[0].snapshot_id == "snap_1"
    assert result.rows[0].target_value == 0.05
    assert result.rows[0].features["company_quality_score"] == 80
    json.dumps(result.manifest.to_dict())
    json.dumps([row.to_dict() for row in result.rows])


# ─── Request Validation ──────────────────────────────────────────────────────

def test_request_rejects_non_shadow_namespace():
    with pytest.raises(TrainingDatasetBuilderError, match="candidate_namespace must start with shadow_meta_model."):
        _request(candidate_namespace="candidate_event.bad")


def test_request_rejects_non_net_target():
    with pytest.raises(TrainingDatasetBuilderError, match="target_name must be net_return_pct"):
        _request(target_name="gross_return_pct")


def test_request_rejects_target_or_forward_return_feature_names():
    for forbidden in ["net_return_pct", "gross_return_pct", "future_return", "forward_return"]:
        with pytest.raises(TrainingDatasetBuilderError, match="feature_names may not include"):
            _request(feature_names=["company_quality_score", forbidden])


# ─── Exclusion Rules ─────────────────────────────────────────────────────────

def test_join_uses_snapshot_id_not_ticker_date():
    snapshot = _snapshot(snapshot_id="snap_left", ticker="MSFT", trading_day="2026-01-05")
    wrong_return = _forward_return(snapshot_id="snap_right")

    result = build_training_dataset([snapshot], [wrong_return], _request())

    assert result.rows == []
    assert result.manifest.excluded_counts["missing_forward_return"] == 1


def test_missing_forward_return_excludes_row():
    result = build_training_dataset([_snapshot()], [], _request())

    assert result.manifest.included_rows == 0
    assert result.manifest.excluded_counts["missing_forward_return"] == 1


def test_non_net_return_excludes_row():
    result = build_training_dataset([_snapshot()], [_forward_return(return_basis="gross")], _request())

    assert result.manifest.included_rows == 0
    assert result.manifest.excluded_counts["non_net_return"] == 1


def test_wrong_horizon_excludes_row():
    result = build_training_dataset([_snapshot()], [_forward_return(horizon_days=63)], _request(horizon_days=21))

    assert result.manifest.included_rows == 0
    assert result.manifest.excluded_counts["wrong_horizon"] == 1


def test_lookahead_violation_excludes_row():
    result = build_training_dataset([_snapshot(lookahead_violation=True)], [_forward_return()], _request())

    assert result.manifest.included_rows == 0
    assert result.manifest.excluded_counts["lookahead_violation"] == 1


def test_data_as_of_after_trading_day_excludes_as_lookahead():
    result = build_training_dataset(
        [_snapshot(data_as_of_date="2026-01-06", trading_day="2026-01-05")],
        [_forward_return()],
        _request(),
    )

    assert result.manifest.included_rows == 0
    assert result.manifest.excluded_counts["lookahead_violation"] == 1


def test_source_audit_gap_excludes_row():
    result = build_training_dataset([_snapshot(source_audit_gap=0.50)], [_forward_return()], _request())

    assert result.manifest.included_rows == 0
    assert result.manifest.excluded_counts["source_audit_gap"] == 1


def test_missing_universe_membership_excludes_row():
    result = build_training_dataset(
        [_snapshot(universe_membership_snapshot_id="")],
        [_forward_return()],
        _request(),
    )

    assert result.manifest.included_rows == 0
    assert result.manifest.excluded_counts["universe_mismatch"] == 1


def test_missing_requested_feature_excludes_row():
    snapshot = _snapshot()
    del snapshot["company_quality_score"]

    result = build_training_dataset([snapshot], [_forward_return()], _request())

    assert result.manifest.included_rows == 0
    assert result.manifest.excluded_counts["missing_required_feature"] == 1


# ─── Duplicate Returns ───────────────────────────────────────────────────────

def test_duplicate_forward_returns_choose_latest_net_observation():
    older = _forward_return(net_return_pct=0.01, computed_at="2026-01-20T00:00:00Z")
    newer = _forward_return(net_return_pct=0.07, computed_at="2026-01-21T00:00:00Z")

    result = build_training_dataset([_snapshot()], [older, newer], _request())

    assert result.manifest.included_rows == 1
    assert result.rows[0].target_value == 0.07
    assert result.manifest.total_forward_returns == 2


# ─── Manifest / Counts ────────────────────────────────────────────────────────

def test_manifest_meets_min_rows_reflects_row_count():
    result = build_training_dataset([_snapshot()], [_forward_return()], _request(min_rows=2))

    assert result.manifest.included_rows == 1
    assert result.manifest.meets_min_rows is False


def test_manifest_excluded_counts_include_all_keys():
    result = build_training_dataset([_snapshot()], [_forward_return()], _request())

    assert set(result.manifest.excluded_counts) == {
        "missing_forward_return",
        "non_net_return",
        "lookahead_violation",
        "source_audit_gap",
        "universe_mismatch",
        "missing_required_feature",
        "wrong_horizon",
    }


# ─── Serialization / Safety ─────────────────────────────────────────────────

def test_output_is_json_serializable():
    result = build_training_dataset([_snapshot()], [_forward_return()], _request())

    json.dumps(result.manifest.to_dict())
    json.dumps([row.to_dict() for row in result.rows])


def test_training_dataset_builder_does_not_import_model_libraries():
    import agent.research_v1.p25_training_dataset_builder as builder_module

    module_names = set(builder_module.__dict__)
    forbidden_names = {"xgboost", "torch", "tensorflow", "sklearn", "stable_baselines3"}

    assert module_names.isdisjoint(forbidden_names)