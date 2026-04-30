"""P25-C Walk-Forward Split Manifest Builder acceptance tests."""

import json
from datetime import date, timedelta

import pytest

from agent.research_v1.p25_split_manifest_builder import (
    SplitManifestBuilderError,
    SplitManifestRequest,
    build_split_manifest,
)


def _request(**overrides):
    values = dict(
        split_id="split_xgb_meta_21d",
        dataset_id="dataset_xgb_meta_21d",
        candidate_namespace="shadow_meta_model.xgb_v1",
        train_window_days=30,
        validation_window_days=10,
        step_days=10,
        purged_gap_days=2,
        embargo_days=2,
        min_train_rows=2,
        min_validation_rows=1,
        walk_forward_enabled=True,
        notes="test split",
    )
    values.update(overrides)
    return SplitManifestRequest(**values)


def _row(snapshot_id, trading_day):
    return {
        "snapshot_id": snapshot_id,
        "trading_day": trading_day,
        "features": {"company_quality_score": 80},
        "target_name": "net_return_pct",
        "target_value": 0.05,
        "horizon_days": 21,
    }


# ─── Request Validation ──────────────────────────────────────────────────────

def test_request_rejects_non_shadow_namespace():
    with pytest.raises(SplitManifestBuilderError, match="candidate_namespace must start with shadow_meta_model."):
        _request(candidate_namespace="candidate_event.bad")


def test_request_rejects_walk_forward_disabled():
    with pytest.raises(SplitManifestBuilderError, match="walk_forward_enabled must be true"):
        _request(walk_forward_enabled=False)


def test_request_rejects_zero_or_negative_windows():
    with pytest.raises(SplitManifestBuilderError, match="train_window_days must be positive"):
        _request(train_window_days=0)
    with pytest.raises(SplitManifestBuilderError, match="validation_window_days must be positive"):
        _request(validation_window_days=0)
    with pytest.raises(SplitManifestBuilderError, match="step_days must be positive"):
        _request(step_days=0)


# ─── Split Generation ─────────────────────────────────────────────────────────

def _rows():
    return [
        _row("snap_01", "2026-01-01"),
        _row("snap_02", "2026-01-05"),
        _row("snap_03", "2026-01-10"),
        _row("snap_04", "2026-01-15"),
        _row("snap_05", "2026-01-20"),
        _row("snap_06", "2026-01-25"),
        _row("snap_07", "2026-02-01"),
        _row("snap_08", "2026-02-05"),
        _row("snap_09", "2026-02-10"),
        _row("snap_10", "2026-02-15"),
        _row("snap_11", "2026-02-20"),
        _row("snap_12", "2026-02-25"),
        _row("snap_13", "2026-03-01"),
        _row("snap_14", "2026-03-05"),
        _row("snap_15", "2026-03-10"),
        _row("snap_16", "2026-03-15"),
        _row("snap_17", "2026-03-20"),
    ]


def test_sorted_rows_produce_at_least_one_split_window():
    result = build_split_manifest(list(reversed(_rows())), _request())

    assert result.manifest.schema_version == "p25_split_manifest.0"
    assert result.manifest.included_windows >= 1
    assert result.manifest.windows[0].train_row_count >= 2
    assert result.manifest.windows[0].validation_row_count >= 1
    json.dumps(result.manifest.to_dict())


def test_train_dates_are_before_validation_dates_and_purge_gap_enforced():
    result = build_split_manifest(_rows(), _request(purged_gap_days=2))
    window = result.manifest.windows[0]

    assert window.train_end < window.validation_start
    assert window.purged_gap_days == 2


def test_embargo_fields_are_preserved():
    result = build_split_manifest(_rows(), _request(embargo_days=5))

    assert result.manifest.embargo_days == 5
    assert result.manifest.windows[0].embargo_days == 5


def test_train_validation_snapshot_ids_do_not_overlap():
    result = build_split_manifest(_rows(), _request())
    window = result.manifest.windows[0]

    assert set(window.train_snapshot_ids).isdisjoint(set(window.validation_snapshot_ids))


# ─── Exclusion Rules ─────────────────────────────────────────────────────────

def test_insufficient_train_rows_exclude_window():
    result = build_split_manifest(_rows(), _request(min_train_rows=99))

    assert result.manifest.included_windows == 0
    assert result.manifest.exclusion_reasons["insufficient_train_rows"] >= 1


def test_insufficient_validation_rows_exclude_window():
    result = build_split_manifest(_rows(), _request(min_validation_rows=99))

    assert result.manifest.included_windows == 0
    assert result.manifest.exclusion_reasons["insufficient_validation_rows"] >= 1


# ─── Dataclass-Like Rows ────────────────────────────────────────────────────

from dataclasses import dataclass


@dataclass
class RowObject:
    snapshot_id: str
    trading_day: str
    features: dict
    target_name: str
    target_value: float
    horizon_days: int


def test_rows_can_be_dataclass_like():
    rows = [
        RowObject("snap_01", "2026-01-01", {}, "net_return_pct", 0.01, 21),
        RowObject("snap_02", "2026-01-05", {}, "net_return_pct", 0.02, 21),
        RowObject("snap_03", "2026-01-20", {}, "net_return_pct", 0.03, 21),
    ]

    result = build_split_manifest(rows, _request(train_window_days=10, validation_window_days=5, step_days=5))

    assert result.manifest.total_rows == 3


# ─── Serialization / Safety ─────────────────────────────────────────────────

def test_manifest_is_json_serializable():
    result = build_split_manifest(_rows(), _request())

    json.dumps(result.manifest.to_dict())


def test_embargo_actually_excludes_overlapping_train_dates():
    rows = [
        _row("snap_01", "2026-01-01"),
        _row("snap_02", "2026-01-05"),
        _row("snap_03", "2026-01-10"),
        _row("snap_04", "2026-01-15"),
        _row("snap_05", "2026-01-20"),
        _row("snap_06", "2026-01-25"),
        _row("snap_07", "2026-02-01"),
        _row("snap_08", "2026-02-05"),
        _row("snap_09", "2026-02-10"),
        _row("snap_10", "2026-02-15"),
        _row("snap_11", "2026-02-20"),
        _row("snap_12", "2026-02-25"),
        _row("snap_13", "2026-03-01"),
        _row("snap_14", "2026-03-05"),
        _row("snap_15", "2026-03-10"),
        _row("snap_16", "2026-03-15"),
        _row("snap_17", "2026-03-20"),
    ]
    result = build_split_manifest(rows, _request(embargo_days=5))
    for i, window in enumerate(result.manifest.windows):
        if i > 0:
            prev_window = result.manifest.windows[i - 1]
            embargo_end = date.fromisoformat(prev_window.validation_end) + timedelta(days=5)
            next_train_start = date.fromisoformat(window.train_start)
            assert next_train_start > embargo_end, (
                f"Window {i} train_start={window.train_start} must be after embargo_end={embargo_end.isoformat()}"
            )


def test_excluded_windows_counts_one_per_excluded_candidate():
    rows = [
        _row("snap_01", "2026-01-01"),
        _row("snap_02", "2026-01-05"),
        _row("snap_03", "2026-01-10"),
        _row("snap_04", "2026-01-15"),
        _row("snap_05", "2026-01-20"),
        _row("snap_06", "2026-01-25"),
        _row("snap_07", "2026-02-01"),
        _row("snap_08", "2026-02-05"),
        _row("snap_09", "2026-02-10"),
        _row("snap_10", "2026-02-15"),
        _row("snap_11", "2026-02-20"),
        _row("snap_12", "2026-02-25"),
        _row("snap_13", "2026-03-01"),
        _row("snap_14", "2026-03-05"),
        _row("snap_15", "2026-03-10"),
        _row("snap_16", "2026-03-15"),
        _row("snap_17", "2026-03-20"),
    ]
    result = build_split_manifest(rows, _request(min_train_rows=99, min_validation_rows=99))
    total_excluded = sum(result.manifest.exclusion_reasons.values())
    assert result.manifest.excluded_windows <= total_excluded
    assert result.manifest.excluded_windows == result.manifest.total_windows - result.manifest.included_windows


def test_step_days_affects_window_positions():
    rows = [
        _row("snap_01", "2026-01-01"),
        _row("snap_02", "2026-01-05"),
        _row("snap_03", "2026-01-10"),
        _row("snap_04", "2026-01-15"),
        _row("snap_05", "2026-01-20"),
        _row("snap_06", "2026-01-25"),
        _row("snap_07", "2026-02-01"),
        _row("snap_08", "2026-02-05"),
        _row("snap_09", "2026-02-10"),
        _row("snap_10", "2026-02-15"),
        _row("snap_11", "2026-02-20"),
        _row("snap_12", "2026-02-25"),
        _row("snap_13", "2026-03-01"),
        _row("snap_14", "2026-03-05"),
        _row("snap_15", "2026-03-10"),
        _row("snap_16", "2026-03-15"),
        _row("snap_17", "2026-03-20"),
    ]
    # Short train/val + small embargo lets step_days drive window count
    result_1 = build_split_manifest(
        rows, _request(train_window_days=5, validation_window_days=3, step_days=1, purged_gap_days=1, embargo_days=1, min_train_rows=1, min_validation_rows=1)
    )
    result_10 = build_split_manifest(
        rows, _request(train_window_days=5, validation_window_days=3, step_days=10, purged_gap_days=1, embargo_days=1, min_train_rows=1, min_validation_rows=1)
    )

    assert result_1.manifest.included_windows != result_10.manifest.included_windows
    assert result_1.manifest.included_windows > result_10.manifest.included_windows
    from agent.research_v1.p25_split_manifest_builder import SplitManifestBuilderError

    bad_rows = [{"snapshot_id": "s1", "trading_day": "2026-01-01"}]
    with pytest.raises(SplitManifestBuilderError, match="features is required"):
        build_split_manifest(bad_rows, _request())

    bad_rows = [{"snapshot_id": "s1", "trading_day": "2026-01-01", "features": {}, "target_name": "net_return_pct", "target_value": 0.01, "horizon_days": 21}]
    del bad_rows[0]["target_value"]
    with pytest.raises(SplitManifestBuilderError, match="target_value is required"):
        build_split_manifest(bad_rows, _request())
    import agent.research_v1.p25_split_manifest_builder as builder_module

    module_names = set(builder_module.__dict__)
    forbidden_names = {"xgboost", "torch", "tensorflow", "sklearn", "stable_baselines3"}

    assert module_names.isdisjoint(forbidden_names)
