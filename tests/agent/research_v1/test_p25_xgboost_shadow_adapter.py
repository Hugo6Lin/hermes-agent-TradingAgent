"""P25-A XGBoost Shadow Dry Adapter acceptance tests."""

import pytest

from agent.research_v1.p24_entry_gate import P24CandidateRequest, P24SystemEvidence, evaluate_p24_entry_gate
from agent.research_v1.p24_experiment_registry import ShadowExperimentRegistry, ShadowExperimentRequest
from agent.research_v1.p24_health_report import build_shadow_experiment_health_report
from agent.research_v1.p24_run_persistence import ShadowRunStore
from agent.research_v1.p24_shadow_runner import ShadowAdapterResult, ShadowExperimentRunRequest, run_shadow_experiment
from agent.research_v1.p25_xgboost_shadow_adapter import (
    XGBoostDryRunAdapter,
    XGBoostMetaFeatureContract,
    XGBoostShadowAdapterConfig,
    XGBoostShadowAdapterConfigError,
)


# ─── Config Tests ────────────────────────────────────────────────────────────────

def test_default_config_uses_shadow_meta_model_namespace():
    config = XGBoostShadowAdapterConfig.default("shadow_meta_model.xgb_v1")

    assert config.schema_version == "p25_xgb_adapter.0"
    assert config.candidate_namespace == "shadow_meta_model.xgb_v1"
    assert config.score_output_name == "shadow_meta_model.xgb_v1.shadow_predictions"
    assert config.calibration_status == "shadow_dry_run"


def test_config_rejects_non_shadow_namespace():
    with pytest.raises(XGBoostShadowAdapterConfigError, match="namespace must start with shadow_meta_model."):
        XGBoostShadowAdapterConfig.default("candidate_event.bad")


def test_config_rejects_output_outside_namespace():
    contract = XGBoostMetaFeatureContract.default("shadow_meta_model.xgb_v1")

    with pytest.raises(XGBoostShadowAdapterConfigError, match="output names must stay within candidate namespace"):
        XGBoostShadowAdapterConfig(
            schema_version="p25_xgb_adapter.0",
            candidate_namespace="shadow_meta_model.xgb_v1",
            adapter_name="xgboost_dry_run",
            adapter_version="0.1",
            feature_contract=contract,
            score_output_name="shadow_meta_model.other.shadow_predictions",
            feature_audit_output_name="shadow_meta_model.xgb_v1.feature_audit",
            metadata_output_name="shadow_meta_model.xgb_v1.dry_run_metadata",
            min_rows=1,
            allow_missing_optional_features=True,
            calibration_status="shadow_dry_run",
        )


def test_feature_contract_rejects_non_net_target_basis():
    with pytest.raises(XGBoostShadowAdapterConfigError, match="target_return_basis must be net"):
        XGBoostMetaFeatureContract(
            schema_version="p25_xgb_feature_contract.0",
            required_features=["snapshot_id"],
            optional_features=[],
            target_return_basis="gross",
            point_in_time_required=True,
            forbidden_features=[],
            namespace="shadow_meta_model.xgb_v1",
        )


def test_feature_contract_contains_required_point_in_time_fields():
    contract = XGBoostMetaFeatureContract.default("shadow_meta_model.xgb_v1")

    assert "data_as_of_date" in contract.required_features
    assert "universe_membership_snapshot_id" in contract.required_features
    assert contract.point_in_time_required is True


# ─── Adapter Tests ───────────────────────────────────────────────────────────────

def _valid_row(**overrides):
    row = {
        "snapshot_id": "snap_1",
        "ticker": "MSFT",
        "trading_day": "2026-01-05",
        "company_quality_score": 80,
        "valuation_attractiveness_score": 60,
        "timing_market_fit_score": 50,
        "llm_adjustment_total": 10,
        "coverage_confidence_score": 0.9,
        "data_as_of_date": "2026-01-04",
        "universe_membership_snapshot_id": "sp500_2026_01_05",
        "sector": "technology",
    }
    row.update(overrides)
    return row


def test_adapter_returns_shadow_adapter_result():
    adapter = XGBoostDryRunAdapter(XGBoostShadowAdapterConfig.default("shadow_meta_model.xgb_v1"), [_valid_row()])

    result = adapter.run(manifest=None, request=None)

    assert isinstance(result, ShadowAdapterResult)
    assert result.adapter_name == "xgboost_dry_run"
    assert result.produced_artifacts == [
        "shadow_meta_model.xgb_v1.shadow_predictions",
        "shadow_meta_model.xgb_v1.feature_audit",
        "shadow_meta_model.xgb_v1.dry_run_metadata",
    ]
    assert result.metrics["input_rows"] == 1
    assert result.metrics["valid_rows"] == 1


def test_adapter_excludes_rows_with_missing_required_features():
    row = _valid_row()
    del row["data_as_of_date"]
    adapter = XGBoostDryRunAdapter(XGBoostShadowAdapterConfig.default("shadow_meta_model.xgb_v1"), [row])

    result = adapter.run(manifest=None, request=None)

    assert result.metrics["input_rows"] == 1
    assert result.metrics["valid_rows"] == 0
    assert result.metrics["missing_required_feature_rows"] == 1
    assert "row_excluded_missing_required_features" in result.warnings


def test_adapter_excludes_rows_with_forbidden_future_return_features():
    row = _valid_row(future_return=0.20)
    adapter = XGBoostDryRunAdapter(XGBoostShadowAdapterConfig.default("shadow_meta_model.xgb_v1"), [row])

    result = adapter.run(manifest=None, request=None)

    assert result.metrics["valid_rows"] == 0
    assert result.metrics["forbidden_feature_rows"] == 1
    assert "row_excluded_forbidden_features" in result.warnings


def test_adapter_emits_optional_feature_warnings():
    row = _valid_row()
    del row["sector"]
    adapter = XGBoostDryRunAdapter(XGBoostShadowAdapterConfig.default("shadow_meta_model.xgb_v1"), [row])

    result = adapter.run(manifest=None, request=None)

    assert result.metrics["valid_rows"] == 1
    assert "missing_optional_features:sector" in result.warnings


def test_stub_scores_are_deterministic_and_clamped():
    config = XGBoostShadowAdapterConfig.default("shadow_meta_model.xgb_v1")
    row = _valid_row(
        company_quality_score=120,
        valuation_attractiveness_score=100,
        timing_market_fit_score=100,
        llm_adjustment_total=50,
        coverage_confidence_score=2,
    )
    adapter_a = XGBoostDryRunAdapter(config, [row])
    adapter_b = XGBoostDryRunAdapter(config, [row])

    result_a = adapter_a.run(manifest=None, request=None)
    result_b = adapter_b.run(manifest=None, request=None)

    assert result_a.metrics["stub_score_min"] == result_b.metrics["stub_score_min"]
    assert 0 <= result_a.metrics["stub_score_min"] <= 1
    assert 0 <= result_a.metrics["stub_score_max"] <= 1


# ─── P24 Integration Tests ───────────────────────────────────────────────────────

def _gate_report():
    request = P24CandidateRequest(
        candidate_name="xgb_meta_v1",
        candidate_family="xgboost_meta_model",
        candidate_namespace="shadow_meta_model.xgb_v1",
        requested_phase="P25",
        intended_outputs=["shadow_meta_model.xgb_v1.shadow_predictions"],
        uses_point_in_time_sources=True,
        source_audit_plan_defined=True,
        simple_baseline_defined=True,
        out_of_sample_plan_defined=True,
        uses_gross_returns_as_primary=False,
        writes_production_fields=False,
        requires_portfolio_layer=False,
        requires_execution_data=False,
        residualization_plan_defined=False,
        notes="p25 xgb adapter",
    )
    evidence = P24SystemEvidence(
        p20_accepted=True,
        p21_accepted=True,
        p22_accepted=True,
        p23_accepted=True,
        return_basis_default="net",
        lookahead_violation_rate=0.0,
        source_audit_gap_rate=0.0,
        ready_for_p24_gate=True,
        ready_factor_count=3,
        core_factors_with_net_icir_gt_030=3,
        ready_factor_horizon_count=3,
        max_abs_cross_factor_correlation=0.50,
        independent_cross_sectional_observations=800,
        regime_gate_has_return_separation=True,
        portfolio_layer_exists=False,
        execution_dataset_exists=False,
    )
    return evaluate_p24_entry_gate(request, evidence)


def _manifest():
    registry = ShadowExperimentRegistry()
    request = ShadowExperimentRequest(
        experiment_id="exp_xgb_meta_v1",
        candidate_id="xgb_meta_v1",
        candidate_name="xgb_meta_v1",
        candidate_family="xgboost_meta_model",
        candidate_namespace="shadow_meta_model.xgb_v1",
        source_gate_report_id="gate_xgb_meta_v1",
        owner="research",
        purpose="P25 XGBoost dry adapter integration.",
        input_contract={
            "allowed_sources": ["factor_snapshots"],
            "required_point_in_time_fields": ["data_as_of_date", "universe_membership_snapshot_id"],
            "forbidden_sources": ["future_prices"],
            "max_source_audit_gap_rate": 0.20,
            "lookahead_policy": "strict_no_future_data",
        },
        output_contract={
            "allowed_outputs": [
                "shadow_meta_model.xgb_v1.shadow_predictions",
                "shadow_meta_model.xgb_v1.feature_audit",
                "shadow_meta_model.xgb_v1.dry_run_metadata",
            ],
            "output_namespace": "shadow_meta_model.xgb_v1",
            "writes_canonical_factor_snapshot": False,
            "writes_production_config": False,
            "affects_live_trading": False,
            "return_basis": "net",
        },
        forbidden_outputs=[
            "company_quality_score",
            "valuation_attractiveness_score",
            "timing_market_fit_score",
            "llm_adjustment_total",
            "classification",
            "production_config",
            "canonical_factor_snapshot",
            "live_trade_signal",
        ],
        training_data_window={
            "start_date": "2024-01-01",
            "end_date": "2026-01-01",
            "minimum_observations": 500,
            "purged_validation_gap_days": 5,
            "embargo_days": 5,
            "point_in_time_membership_required": True,
        },
        point_in_time_policy={
            "source_timestamp_required": True,
            "membership_snapshot_required": True,
            "revision_policy": "as_reported_only",
        },
        baseline_comparison_plan={
            "baseline_name": "prior_linear_factor_blend",
            "baseline_type": "current_prior",
            "primary_metric": "net_icir",
            "secondary_metrics": ["net_ic"],
            "comparison_direction": "higher_is_better",
            "minimum_evaluation_windows": 4,
        },
        out_of_sample_validation_plan={
            "method": "walk_forward",
            "walk_forward_enabled": True,
            "holdout_periods": ["2026H1"],
            "leakage_checks": ["point_in_time", "purged_embargo"],
            "promotion_criteria_documented": True,
        },
        observation_plan={
            "observation_frequency": "weekly",
            "minimum_shadow_windows": 4,
            "required_reports": ["ModelAdmissionGateReport", "ShadowExperimentManifest", "ShadowObservationReport"],
            "revocation_triggers": ["lookahead_violation", "net_underperformance"],
        },
        resource_policy={
            "max_runtime_minutes": 30,
            "max_memory_mb": 4096,
            "model_libraries_allowed": False,
        },
        expected_artifacts=["shadow_predictions", "feature_audit", "dry_run_metadata"],
        notes="p25 integration",
    )
    return registry.register_shadow_experiment(request, _gate_report())


def test_adapter_runs_through_p24_runner_persistence_and_health_report():
    manifest = _manifest()
    adapter = XGBoostDryRunAdapter(
        XGBoostShadowAdapterConfig.default("shadow_meta_model.xgb_v1"),
        [_valid_row()],
    )
    run_request = ShadowExperimentRunRequest(
        run_id="run_xgb_meta_v1_001",
        experiment_id="exp_xgb_meta_v1",
        run_mode="shadow_stub",
        input_window={
            "start_date": "2026-01-01",
            "end_date": "2026-03-31",
            "data_as_of_policy": "manifest_point_in_time_policy",
            "point_in_time_required": True,
        },
        requested_artifacts=["shadow_meta_model.xgb_v1.shadow_predictions"],
        operator="codex",
        reason="p25 integration",
        notes="shadow stub",
    )

    runner_result = run_shadow_experiment(manifest, adapter, run_request)
    store = ShadowRunStore()
    store.save_run_record(runner_result.record)
    report = build_shadow_experiment_health_report([manifest], store)

    assert runner_result.record.status == "completed"
    assert runner_result.adapter_result.metrics["valid_rows"] == 1
    assert report.total_experiments == 1
    assert report.experiments[0].health_status == "healthy"


# ─── Safety ─────────────────────────────────────────────────────────────────────

def test_xgboost_shadow_adapter_module_does_not_import_model_libraries():
    import agent.research_v1.p25_xgboost_shadow_adapter as adapter_module

    module_names = set(adapter_module.__dict__)
    forbidden_names = {"xgboost", "torch", "tensorflow", "sklearn", "stable_baselines3"}

    assert module_names.isdisjoint(forbidden_names)