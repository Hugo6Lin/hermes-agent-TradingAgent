"""P24-D Shadow Run Persistence and Observation Bridge acceptance tests."""

import json

import pytest
from dataclasses import replace

from agent.research_v1.p24_entry_gate import (
    P24CandidateRequest,
    P24SystemEvidence,
    evaluate_p24_entry_gate,
)
from agent.research_v1.p24_experiment_registry import ShadowExperimentRegistry, ShadowExperimentRequest
from agent.research_v1.p24_shadow_runner import (
    ShadowAdapterResult,
    ShadowExperimentRunRequest,
    run_shadow_experiment,
)
from agent.research_v1.p24_run_persistence import (
    ShadowRunPersistenceError,
    ShadowRunStore,
    build_shadow_experiment_observation,
)


def _gate_report(**overrides):
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
        notes="persistence test",
    )
    values.update(overrides)
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
        purpose="Persistence bridge test.",
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
        notes="persistence manifest",
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
        reason="verify persistence",
        notes="dry run",
    )
    values.update(overrides)
    return ShadowExperimentRunRequest(**values)


def _run_record(**request_overrides):
    return run_shadow_experiment(_manifest(), adapter=None, run_request=_run_request(**request_overrides)).record


# ─── Adapters for shadow_stub runs ────────────────────────────────────────────

class GoodAdapter:
    adapter_name = "good"
    adapter_version = "0.1"

    def run(self, manifest, request):
        return ShadowAdapterResult(
            adapter_name=self.adapter_name,
            adapter_version=self.adapter_version,
            produced_artifacts=["shadow_meta_model.xgb_v1.predictions"],
            attempted_outputs=["shadow_meta_model.xgb_v1.predictions"],
            metrics={},
            logs=[],
            warnings=[],
        )


class ExplodingAdapter:
    adapter_name = "boom"
    adapter_version = "0.1"

    def run(self, manifest, request):
        raise RuntimeError("boom")


def _blocked_record(run_id="run_blocked_001"):
    return run_shadow_experiment(
        _manifest(),
        adapter=None,
        run_request=_run_request(run_id=run_id, requested_artifacts=["company_quality_score"]),
    ).record


def _production_blocked_record(run_id="run_prod_blocked_001"):
    return run_shadow_experiment(
        _manifest(),
        adapter=None,
        run_request=_run_request(run_id=run_id, requested_artifacts=["production_config"]),
    ).record


def _failed_record(run_id="run_failed_001"):
    return run_shadow_experiment(
        _manifest(),
        adapter=ExplodingAdapter(),
        run_request=_run_request(run_id=run_id, run_mode="shadow_stub"),
    ).record


# ─── Persistence ────────────────────────────────────────────────────────────────

def test_completed_run_is_saved_and_retrieved():
    store = ShadowRunStore()
    record = _run_record()

    saved = store.save_run_record(record)

    assert saved.run_id == "run_xgb_meta_v1_001"
    assert store.get_run_record("run_xgb_meta_v1_001") == saved
    json.dumps(saved.to_dict())


def test_duplicate_run_id_is_rejected():
    store = ShadowRunStore()
    record = _run_record()
    store.save_run_record(record)

    with pytest.raises(ShadowRunPersistenceError, match="duplicate run_id"):
        store.save_run_record(record)


def test_false_production_safety_flag_is_rejected():
    store = ShadowRunStore()
    record = replace(_run_record(), no_production_write_confirmed=False)

    with pytest.raises(ShadowRunPersistenceError, match="no_production_write_confirmed must be true"):
        store.save_run_record(record)


# ─── Query ─────────────────────────────────────────────────────────────────────

def test_blocked_and_failed_runs_are_saved_and_retrieved():
    store = ShadowRunStore()
    blocked = store.save_run_record(_blocked_record())
    failed = store.save_run_record(_failed_record())

    assert store.get_run_record(blocked.run_id).status == "blocked"
    assert store.get_run_record(failed.run_id).status == "failed"


def test_records_query_by_experiment_and_status():
    store = ShadowRunStore()
    completed = store.save_run_record(_run_record(run_id="run_completed_001"))
    blocked = store.save_run_record(_blocked_record())
    store.save_run_record(_failed_record())

    assert store.list_run_records(experiment_id="exp_xgb_meta_v1")[0] == completed
    assert store.list_run_records(status="blocked") == [blocked]


# ─── Summary ───────────────────────────────────────────────────────────────────

def test_summary_counts_statuses_and_blocked_reason_frequency():
    store = ShadowRunStore()
    store.save_run_record(_run_record(run_id="run_completed_001"))
    store.save_run_record(_blocked_record(run_id="run_blocked_001"))
    store.save_run_record(_failed_record(run_id="run_failed_001"))

    summary = store.summarize_experiment_runs("exp_xgb_meta_v1")

    assert summary.total_runs == 3
    assert summary.completed_count == 1
    assert summary.blocked_count == 1
    assert summary.failed_count == 1
    assert summary.blocked_reason_frequency["requested_forbidden_artifact:company_quality_score"] == 1
    assert summary.last_run_status == "failed"
    assert summary.health_status == "watch"


def test_three_consecutive_blocked_or_failed_runs_recommend_revocation():
    store = ShadowRunStore()
    store.save_run_record(_blocked_record(run_id="run_blocked_001"))
    store.save_run_record(_failed_record(run_id="run_failed_001"))
    store.save_run_record(_blocked_record(run_id="run_blocked_002"))

    summary = store.summarize_experiment_runs("exp_xgb_meta_v1")

    assert summary.health_status == "revocation_recommended"
    assert summary.revocation_recommended is True
    assert "three_consecutive_blocked_or_failed_runs" in summary.revocation_reasons


# ─── Observation Bridge ─────────────────────────────────────────────────────────

def test_observation_bridge_creates_healthy_observation_for_completed_run():
    manifest = _manifest()
    record = _run_record()

    observation = build_shadow_experiment_observation(record, manifest)

    assert observation.schema_version == "p24_observation.0"
    assert observation.experiment_id == "exp_xgb_meta_v1"
    assert observation.run_id == record.run_id
    assert observation.run_status == "completed"
    assert observation.health_status == "healthy"
    assert observation.revocation_recommended is False
    assert observation.no_production_write_confirmed is True
    json.dumps(observation.to_dict())


def test_observation_bridge_recommends_revocation_for_production_block():
    manifest = _manifest()
    record = _production_blocked_record()

    observation = build_shadow_experiment_observation(record, manifest)

    assert observation.health_status == "revocation_recommended"
    assert observation.revocation_recommended is True
    assert "production_or_canonical_path_blocked" in observation.revocation_reasons


def test_observation_bridge_blocks_manifest_run_mismatch():
    manifest = _manifest()
    record = replace(_run_record(), experiment_id="other_experiment")

    with pytest.raises(ShadowRunPersistenceError, match="experiment_id mismatch"):
        build_shadow_experiment_observation(record, manifest)


# ─── Mutation Isolation ──────────────────────────────────────────────────────────

def test_saved_record_is_not_mutated_by_original_object_changes():
    store = ShadowRunStore()
    original = _run_record()
    store.save_run_record(original)

    original.produced_artifacts.append("mutated_artifact")
    original.blocked_artifacts.append("mutated_block")
    original.warnings.append("mutated_warning")

    retrieved = store.get_run_record("run_xgb_meta_v1_001")
    assert "mutated_artifact" not in retrieved.produced_artifacts
    assert "mutated_block" not in retrieved.blocked_artifacts
    assert "mutated_warning" not in retrieved.warnings


def test_retrieved_record_mutation_does_not_mutate_store():
    store = ShadowRunStore()
    saved = store.save_run_record(_run_record())

    retrieved = store.get_run_record("run_xgb_meta_v1_001")
    retrieved.produced_artifacts.append("mutated_artifact")
    retrieved.blocked_artifacts.append("mutated_block")
    retrieved.warnings.append("mutated_warning")

    re_retrieved = store.get_run_record("run_xgb_meta_v1_001")
    assert "mutated_artifact" not in re_retrieved.produced_artifacts
    assert "mutated_block" not in re_retrieved.blocked_artifacts
    assert "mutated_warning" not in re_retrieved.warnings


# ─── Safety ─────────────────────────────────────────────────────────────────────

def test_store_returns_json_serializable_records():
    store = ShadowRunStore()
    saved = store.save_run_record(_run_record())

    json.dumps(saved.to_dict())
    json.dumps(store.summarize_experiment_runs("exp_xgb_meta_v1").to_dict())


def test_persistence_module_does_not_import_model_libraries():
    import agent.research_v1.p24_run_persistence as persistence_module

    module_names = set(persistence_module.__dict__)
    forbidden_names = {"xgboost", "torch", "tensorflow", "sklearn", "stable_baselines3"}

    assert module_names.isdisjoint(forbidden_names)