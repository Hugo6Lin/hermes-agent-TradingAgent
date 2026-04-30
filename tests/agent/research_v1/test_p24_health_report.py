"""P24-E Shadow Experiment Health Report acceptance tests."""

import json

from dataclasses import replace

from agent.research_v1.p24_entry_gate import (
    P24CandidateRequest,
    P24SystemEvidence,
    evaluate_p24_entry_gate,
)
from agent.research_v1.p24_experiment_registry import ShadowExperimentRegistry, ShadowExperimentRequest
from agent.research_v1.p24_health_report import build_shadow_experiment_health_report
from agent.research_v1.p24_run_persistence import ShadowRunStore
from agent.research_v1.p24_shadow_runner import ShadowExperimentRunRequest, run_shadow_experiment


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
        notes="health report test",
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
        purpose="Health report test.",
        input_contract={
            "allowed_sources": ["factor_snapshots"],
            "required_point_in_time_fields": ["trading_day"],
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
            "baseline_name": "prior",
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
            "revocation_triggers": ["net_underperformance"],
        },
        resource_policy={
            "max_runtime_minutes": 30,
            "max_memory_mb": 4096,
            "model_libraries_allowed": False,
        },
        expected_artifacts=["manifest"],
        notes="health manifest",
    )
    values.update(overrides)
    return ShadowExperimentRequest(**values)


def _manifest(**overrides):
    registry = ShadowExperimentRegistry()
    request = _experiment_request(**overrides)
    gate_report = _gate_report(
        candidate_name=request.candidate_name,
        candidate_family=request.candidate_family,
        candidate_namespace=request.candidate_namespace,
        intended_outputs=list(request.output_contract["allowed_outputs"]),
    )
    return registry.register_shadow_experiment(request, gate_report)


def _run_request(run_id="run_001", experiment_id="exp_xgb_meta_v1", requested_artifacts=None):
    return ShadowExperimentRunRequest(
        run_id=run_id,
        experiment_id=experiment_id,
        run_mode="dry_run",
        input_window={
            "start_date": "2026-01-01",
            "end_date": "2026-03-31",
            "data_as_of_policy": "manifest_point_in_time_policy",
            "point_in_time_required": True,
        },
        requested_artifacts=requested_artifacts or ["shadow_meta_model.xgb_v1.dry_run_metadata"],
        operator="codex",
        reason="health report",
        notes="health run",
    )


# ─── Empty Report ────────────────────────────────────────────────────────────────

def test_empty_manifest_list_returns_empty_report():
    report = build_shadow_experiment_health_report([], ShadowRunStore())

    assert report.schema_version == "p24_health_report.0"
    assert report.total_experiments == 0
    assert report.registered_count == 0
    assert report.healthy_count == 0
    assert report.watch_count == 0
    assert report.no_runs_count == 0
    assert report.revocation_recommended_count == 0
    assert report.experiments == []
    assert report.recommended_actions == []
    json.dumps(report.to_dict())


# ─── Healthy / No-Run Rows ─────────────────────────────────────────────────────

def test_registered_experiment_with_completed_runs_appears_healthy():
    manifest = _manifest()
    store = ShadowRunStore()
    store.save_run_record(run_shadow_experiment(manifest, None, _run_request()).record)

    report = build_shadow_experiment_health_report([manifest], store)

    assert report.total_experiments == 1
    assert report.healthy_count == 1
    assert report.experiments[0].health_status == "healthy"
    assert report.recommended_actions == ["continue_observation"]


def test_no_run_experiment_appears_as_no_runs():
    manifest = _manifest()

    report = build_shadow_experiment_health_report([manifest], ShadowRunStore())

    assert report.no_runs_count == 1
    assert report.experiments[0].health_status == "no_runs"
    assert "schedule_shadow_runs_for_no_run_experiments" in report.recommended_actions


# ─── Watch / Revocation / Sorting ──────────────────────────────────────────────

def test_watch_experiment_and_top_blocked_reasons_are_reported():
    manifest = _manifest()
    store = ShadowRunStore()
    store.save_run_record(
        run_shadow_experiment(
            manifest,
            None,
            _run_request(run_id="run_blocked", requested_artifacts=["company_quality_score"]),
        ).record
    )

    report = build_shadow_experiment_health_report([manifest], store)

    assert report.watch_count == 1
    assert report.experiments[0].health_status == "watch"
    assert report.top_blocked_reasons["requested_forbidden_artifact:company_quality_score"] == 1
    assert "inspect_watch_experiments" in report.recommended_actions


def test_revocation_recommended_experiment_sorts_first():
    healthy_manifest = _manifest()
    risky_manifest = _manifest(
        experiment_id="exp_risky",
        candidate_id="risky",
        candidate_name="risky",
        candidate_namespace="shadow_meta_model.risky",
        output_contract={
            **_experiment_request().output_contract,
            "allowed_outputs": ["shadow_meta_model.risky.score"],
            "output_namespace": "shadow_meta_model.risky",
        },
    )
    store = ShadowRunStore()
    store.save_run_record(run_shadow_experiment(healthy_manifest, None, _run_request()).record)
    store.save_run_record(
        run_shadow_experiment(
            risky_manifest,
            None,
            _run_request(
                run_id="run_risky",
                experiment_id="exp_risky",
                requested_artifacts=["production_config"],
            ),
        ).record
    )

    report = build_shadow_experiment_health_report([healthy_manifest, risky_manifest], store)

    assert report.revocation_recommended_count == 1
    assert report.experiments[0].experiment_id == "exp_risky"
    assert report.experiments[0].revocation_recommended is True
    assert "review_revocation_recommended_experiments" in report.recommended_actions


# ─── Family Breakdown ───────────────────────────────────────────────────────────

def test_family_breakdown_counts_experiments_and_run_statuses():
    manifest = _manifest()
    store = ShadowRunStore()
    store.save_run_record(run_shadow_experiment(manifest, None, _run_request()).record)

    report = build_shadow_experiment_health_report([manifest], store)
    family = report.family_breakdown["xgboost_meta_model"]

    assert family["total_experiments"] == 1
    assert family["registered_count"] == 1
    assert family["healthy_count"] == 1
    assert family["completed_runs"] == 1
    assert family["blocked_runs"] == 0
    assert family["failed_runs"] == 0


# ─── Production Safety Summary ──────────────────────────────────────────────────

def test_production_safety_summary_detects_unsafe_manifest_flags():
    manifest = replace(_manifest(), production_write_blocked=False)

    report = build_shadow_experiment_health_report([manifest], ShadowRunStore())

    assert report.production_safety_summary["all_no_production_write_confirmed"] is False
    assert report.production_safety_summary["any_production_config_write_attempt"] is True
    assert report.production_safety_summary["unsafe_experiment_ids"] == ["exp_xgb_meta_v1"]
    assert "investigate_production_safety_violation" in report.recommended_actions


def test_production_safety_summary_detects_unsafe_run_flags():
    manifest = _manifest()
    store = ShadowRunStore()
    record = run_shadow_experiment(manifest, None, _run_request()).record
    store.save_run_record(record)
    from agent.research_v1.p24_shadow_runner import ShadowExperimentRunRecord
    record_dict = store.get_run_record("run_001").to_dict()
    record_dict["no_production_write_confirmed"] = False
    store._records["run_001"] = record_dict

    report = build_shadow_experiment_health_report([manifest], store)

    assert report.production_safety_summary["all_no_production_write_confirmed"] is False
    assert report.production_safety_summary["unsafe_experiment_ids"] == ["exp_xgb_meta_v1"]
    assert "investigate_production_safety_violation" in report.recommended_actions


# ─── Serialization / Safety ─────────────────────────────────────────────────────

def test_health_report_is_json_serializable():
    manifest = _manifest()
    store = ShadowRunStore()
    store.save_run_record(run_shadow_experiment(manifest, None, _run_request()).record)

    report = build_shadow_experiment_health_report([manifest], store)

    json.dumps(report.to_dict())


def test_health_report_module_does_not_import_model_libraries():
    import agent.research_v1.p24_health_report as health_report_module

    module_names = set(health_report_module.__dict__)
    forbidden_names = {"xgboost", "torch", "tensorflow", "sklearn", "stable_baselines3"}

    assert module_names.isdisjoint(forbidden_names)