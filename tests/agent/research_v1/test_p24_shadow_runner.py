"""P24-C Shadow Experiment Runner Scaffold acceptance tests."""

import json

from dataclasses import replace

from agent.research_v1.p24_entry_gate import (
    P24CandidateRequest,
    P24SystemEvidence,
    evaluate_p24_entry_gate,
)
from agent.research_v1.p24_experiment_registry import (
    ShadowExperimentRegistry,
    ShadowExperimentRequest,
)
from agent.research_v1.p24_shadow_runner import (
    ShadowAdapterResult,
    ShadowExperimentRunRequest,
    run_shadow_experiment,
)


def _gate_report(**request_overrides):
    values = dict(
        candidate_name="xgb_meta_v1",
        candidate_family="xgboost_meta_model",
        candidate_namespace="shadow_meta_model.xgb_v1",
        requested_phase="P24",
        intended_outputs=["shadow_meta_model.xgb_v1.shadow_ranking_score"],
        uses_point_in_time_sources=True,
        source_audit_plan_defined=True,
        simple_baseline_defined=True,
        out_of_sample_plan_defined=True,
        uses_gross_returns_as_primary=False,
        writes_production_fields=False,
        requires_portfolio_layer=False,
        requires_execution_data=False,
        residualization_plan_defined=False,
        notes="runner test",
    )
    values.update(request_overrides)
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
    return evaluate_p24_entry_gate(P24CandidateRequest(**values), evidence)


def _experiment_request(**overrides):
    values = dict(
        experiment_id="exp_xgb_meta_v1",
        candidate_id="xgb_meta_v1",
        candidate_name="xgb_meta_v1",
        candidate_family="xgboost_meta_model",
        candidate_namespace="shadow_meta_model.xgb_v1",
        source_gate_report_id="gate_xgb_meta_v1",
        owner="research",
        purpose="Runner scaffold test.",
        input_contract={
            "allowed_sources": ["factor_snapshots", "forward_return_observations"],
            "required_point_in_time_fields": ["trading_day", "data_as_of_date", "universe_membership_snapshot_id"],
            "forbidden_sources": ["future_prices"],
            "max_source_audit_gap_rate": 0.20,
            "lookahead_policy": "strict_no_future_data",
        },
        output_contract={
            "allowed_outputs": ["shadow_meta_model.xgb_v1.shadow_ranking_score"],
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
        expected_artifacts=["manifest", "shadow_predictions_file", "observation_report"],
        notes="runner manifest",
    )
    values.update(overrides)
    return ShadowExperimentRequest(**values)


def _manifest():
    registry = ShadowExperimentRegistry()
    return registry.register_shadow_experiment(_experiment_request(), _gate_report())


def _run_request(**overrides):
    values = dict(
        run_id="run_xgb_meta_v1_001",
        experiment_id="exp_xgb_meta_v1",
        run_mode="dry_run",
        input_window={
            "start_date": "2026-01-01",
            "end_date": "2026-03-31",
            "data_as_of_policy": "manifest_point_in_time_policy",
            "point_in_time_required": True,
        },
        requested_artifacts=["shadow_meta_model.xgb_v1.dry_run_metadata"],
        operator="codex",
        reason="verify runner scaffold",
        notes="dry run",
    )
    values.update(overrides)
    return ShadowExperimentRunRequest(**values)


# ─── Dry Run ──────────────────────────────────────────────────────────────────

def test_dry_run_registered_manifest_completes_without_adapter_execution():
    result = run_shadow_experiment(_manifest(), adapter=None, run_request=_run_request())

    assert result.adapter_result is None
    assert result.record.status == "completed"
    assert result.record.run_mode == "dry_run"
    assert result.record.no_production_write_confirmed is True
    assert result.record.canonical_snapshot_write_blocked is True
    assert result.record.production_config_write_blocked is True
    assert result.record.live_trading_blocked is True
    json.dumps(result.record.to_dict())


# ─── Pre-Run Safety Blocks ────────────────────────────────────────────────────

def test_revoked_manifest_is_blocked():
    manifest = replace(_manifest(), status="revoked")

    result = run_shadow_experiment(manifest, adapter=None, run_request=_run_request())

    assert result.record.status == "blocked"
    assert "manifest_not_registered" in result.record.blocked_artifacts
    assert result.adapter_result is None


def test_experiment_id_mismatch_is_blocked():
    result = run_shadow_experiment(
        _manifest(),
        adapter=None,
        run_request=_run_request(experiment_id="wrong_exp"),
    )

    assert result.record.status == "blocked"
    assert "experiment_id_mismatch" in result.record.blocked_artifacts


def test_non_point_in_time_input_window_is_blocked():
    request = _run_request(
        input_window={
            "start_date": "2026-01-01",
            "end_date": "2026-03-31",
            "data_as_of_policy": "latest_available",
            "point_in_time_required": False,
        }
    )

    result = run_shadow_experiment(_manifest(), adapter=None, run_request=request)

    assert result.record.status == "blocked"
    assert "input_window_not_point_in_time" in result.record.blocked_artifacts
    assert "data_as_of_policy_invalid" in result.record.blocked_artifacts


def test_requested_artifact_outside_namespace_is_blocked():
    result = run_shadow_experiment(
        _manifest(),
        adapter=None,
        run_request=_run_request(requested_artifacts=["production_config"]),
    )

    assert result.record.status == "blocked"
    assert "requested_artifact_outside_namespace:production_config" in result.record.blocked_artifacts
    assert "requested_forbidden_artifact:production_config" in result.record.blocked_artifacts


# ─── Shadow Stub Adapter Execution ─────────────────────────────────────────────

class GoodAdapter:
    adapter_name = "good_stub"
    adapter_version = "0.1"

    def run(self, manifest, request):
        return ShadowAdapterResult(
            adapter_name=self.adapter_name,
            adapter_version=self.adapter_version,
            produced_artifacts=["shadow_meta_model.xgb_v1.shadow_predictions"],
            attempted_outputs=["shadow_meta_model.xgb_v1.shadow_predictions"],
            metrics={"rows": 10},
            logs=["stub run"],
            warnings=[],
        )


class BadNamespaceAdapter:
    adapter_name = "bad_namespace"
    adapter_version = "0.1"

    def run(self, manifest, request):
        return ShadowAdapterResult(
            adapter_name=self.adapter_name,
            adapter_version=self.adapter_version,
            produced_artifacts=["other_namespace.predictions"],
            attempted_outputs=["other_namespace.predictions"],
            metrics={},
            logs=[],
            warnings=[],
        )


class ForbiddenOutputAdapter:
    adapter_name = "forbidden_output"
    adapter_version = "0.1"

    def run(self, manifest, request):
        return ShadowAdapterResult(
            adapter_name=self.adapter_name,
            adapter_version=self.adapter_version,
            produced_artifacts=["classification"],
            attempted_outputs=["classification"],
            metrics={},
            logs=[],
            warnings=["attempted forbidden output"],
        )


class ExplodingAdapter:
    adapter_name = "exploding"
    adapter_version = "0.1"

    def run(self, manifest, request):
        raise RuntimeError("adapter exploded")


def test_shadow_stub_registered_manifest_executes_adapter():
    result = run_shadow_experiment(
        _manifest(),
        adapter=GoodAdapter(),
        run_request=_run_request(run_mode="shadow_stub"),
    )

    assert result.record.status == "completed"
    assert result.adapter_result is not None
    assert result.record.adapter_name == "good_stub"
    assert result.record.produced_artifacts == ["shadow_meta_model.xgb_v1.shadow_predictions"]


def test_adapter_artifact_outside_namespace_is_blocked():
    result = run_shadow_experiment(
        _manifest(),
        adapter=BadNamespaceAdapter(),
        run_request=_run_request(run_mode="shadow_stub"),
    )

    assert result.record.status == "blocked"
    assert "adapter_output_outside_namespace:other_namespace.predictions" in result.record.blocked_artifacts


def test_adapter_forbidden_output_is_blocked():
    result = run_shadow_experiment(
        _manifest(),
        adapter=ForbiddenOutputAdapter(),
        run_request=_run_request(run_mode="shadow_stub"),
    )

    assert result.record.status == "blocked"
    assert "adapter_forbidden_output:classification" in result.record.blocked_artifacts


def test_adapter_exception_becomes_failed_record():
    result = run_shadow_experiment(
        _manifest(),
        adapter=ExplodingAdapter(),
        run_request=_run_request(run_mode="shadow_stub"),
    )

    assert result.record.status == "failed"
    assert "RuntimeError: adapter exploded" in result.record.error_message
    assert result.record.no_production_write_confirmed is True


def test_shadow_stub_without_adapter_is_blocked():
    result = run_shadow_experiment(
        _manifest(),
        adapter=None,
        run_request=_run_request(run_mode="shadow_stub"),
    )

    assert result.record.status == "blocked"
    assert "adapter_missing_for_shadow_stub" in result.record.blocked_artifacts
    assert result.adapter_result is None


# ─── Namespace Boundary ─────────────────────────────────────────────────────────

class SiblingNamespaceAdapter:
    adapter_name = "sibling_escape"
    adapter_version = "0.1"

    def run(self, manifest, request):
        return ShadowAdapterResult(
            adapter_name=self.adapter_name,
            adapter_version=self.adapter_version,
            produced_artifacts=["shadow_meta_model.xgb_v10.bad"],
            attempted_outputs=["shadow_meta_model.xgb_v10.bad"],
            metrics={},
            logs=[],
            warnings=[],
        )


def test_sibling_namespace_escape_is_blocked():
    result = run_shadow_experiment(
        _manifest(),
        adapter=SiblingNamespaceAdapter(),
        run_request=_run_request(run_mode="shadow_stub"),
    )

    assert result.record.status == "blocked"
    assert "adapter_output_outside_namespace:shadow_meta_model.xgb_v10.bad" in result.record.blocked_artifacts


def test_requested_artifact_sibling_namespace_escape_is_blocked():
    result = run_shadow_experiment(
        _manifest(),
        adapter=None,
        run_request=_run_request(requested_artifacts=["shadow_meta_model.xgb_v10.bad"]),
    )

    assert result.record.status == "blocked"
    assert "requested_artifact_outside_namespace:shadow_meta_model.xgb_v10.bad" in result.record.blocked_artifacts


# ─── Safety Confirmation ───────────────────────────────────────────────────────

def test_run_record_confirms_all_production_paths_blocked():
    result = run_shadow_experiment(_manifest(), adapter=None, run_request=_run_request())

    assert result.record.safety_checks["no_production_write"] is True
    assert result.record.safety_checks["canonical_snapshot_write_blocked"] is True
    assert result.record.safety_checks["production_config_write_blocked"] is True
    assert result.record.safety_checks["live_trading_blocked"] is True


def test_runner_module_does_not_import_model_libraries():
    import agent.research_v1.p24_shadow_runner as runner_module

    module_names = set(runner_module.__dict__)
    forbidden_names = {"xgboost", "torch", "tensorflow", "sklearn", "stable_baselines3"}

    assert module_names.isdisjoint(forbidden_names)