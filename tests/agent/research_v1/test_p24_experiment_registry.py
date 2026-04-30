"""P24-B Shadow Experiment Registry acceptance tests."""

import pytest

from agent.research_v1.p24_entry_gate import (
    P24CandidateRequest,
    P24SystemEvidence,
    evaluate_p24_entry_gate,
)
from agent.research_v1.p24_experiment_registry import (
    ShadowExperimentRegistry,
    ShadowExperimentRequest,
)


def _gate_report(**request_overrides):
    request_values = dict(
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
        notes="registry test",
    )
    request_values.update(request_overrides)
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
    return evaluate_p24_entry_gate(P24CandidateRequest(**request_values), evidence)


def _experiment_request(**overrides):
    values = dict(
        experiment_id="exp_xgb_meta_v1",
        candidate_id="xgb_meta_v1",
        candidate_name="xgb_meta_v1",
        candidate_family="xgboost_meta_model",
        candidate_namespace="shadow_meta_model.xgb_v1",
        source_gate_report_id="gate_xgb_meta_v1",
        owner="research",
        purpose="Shadow-test nonlinear combination of validated factors.",
        input_contract={
            "allowed_sources": ["factor_snapshots", "forward_return_observations"],
            "required_point_in_time_fields": ["trading_day", "data_as_of_date", "universe_membership_snapshot_id"],
            "forbidden_sources": ["future_prices", "restated_fundamentals_without_asof"],
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
            "secondary_metrics": ["net_ic", "net_return_spread"],
            "comparison_direction": "higher_is_better",
            "minimum_evaluation_windows": 4,
        },
        out_of_sample_validation_plan={
            "method": "walk_forward",
            "walk_forward_enabled": True,
            "holdout_periods": ["2025H2", "2026H1"],
            "leakage_checks": ["point_in_time", "purged_embargo"],
            "promotion_criteria_documented": True,
        },
        observation_plan={
            "observation_frequency": "weekly",
            "minimum_shadow_windows": 4,
            "required_reports": ["ModelAdmissionGateReport", "ShadowExperimentManifest", "ShadowObservationReport"],
            "revocation_triggers": ["lookahead_violation", "source_audit_gap_too_high", "net_underperformance"],
        },
        resource_policy={
            "max_runtime_minutes": 30,
            "max_memory_mb": 4096,
            "model_libraries_allowed": False,
        },
        expected_artifacts=["manifest", "shadow_predictions_file", "observation_report"],
        notes="happy path",
    )
    values.update(overrides)
    return ShadowExperimentRequest(**values)


def test_register_passing_gate_report_creates_manifest():
    registry = ShadowExperimentRegistry()
    manifest = registry.register_shadow_experiment(_experiment_request(), _gate_report())

    assert manifest.status == "registered"
    assert manifest.schema_version == "p24_manifest.0"
    assert manifest.source_gate_report_id == "gate_xgb_meta_v1"
    assert manifest.source_gate_schema_version == "p24_gate.0"
    assert manifest.promotion_blocked is True
    assert manifest.production_write_blocked is True
    assert manifest.canonical_snapshot_write_blocked is True
    assert manifest.shadow_namespace == "shadow_meta_model.xgb_v1"
    assert registry.get_experiment("exp_xgb_meta_v1") == manifest


from agent.research_v1.p24_experiment_registry import ShadowExperimentRegistrationError


def test_failed_gate_report_cannot_register():
    failed_report = _gate_report(writes_production_fields=True)
    registry = ShadowExperimentRegistry()

    with pytest.raises(ShadowExperimentRegistrationError, match="gate report did not pass"):
        registry.register_shadow_experiment(_experiment_request(), failed_report)


def test_namespace_mismatch_is_blocked():
    registry = ShadowExperimentRegistry()
    request = _experiment_request(candidate_namespace="shadow_meta_model.other")

    with pytest.raises(ShadowExperimentRegistrationError, match="candidate namespace mismatch"):
        registry.register_shadow_experiment(request, _gate_report())


def test_canonical_snapshot_write_is_blocked():
    registry = ShadowExperimentRegistry()
    request = _experiment_request(
        output_contract={
            **_experiment_request().output_contract,
            "writes_canonical_factor_snapshot": True,
        }
    )

    with pytest.raises(ShadowExperimentRegistrationError, match="canonical factor snapshot writes are forbidden"):
        registry.register_shadow_experiment(request, _gate_report())


def test_production_config_write_is_blocked():
    registry = ShadowExperimentRegistry()
    request = _experiment_request(
        output_contract={
            **_experiment_request().output_contract,
            "writes_production_config": True,
        }
    )

    with pytest.raises(ShadowExperimentRegistrationError, match="production config writes are forbidden"):
        registry.register_shadow_experiment(request, _gate_report())


def test_gross_return_primary_output_is_blocked():
    registry = ShadowExperimentRegistry()
    request = _experiment_request(
        output_contract={
            **_experiment_request().output_contract,
            "return_basis": "gross",
        }
    )

    with pytest.raises(ShadowExperimentRegistrationError, match="return_basis must be net"):
        registry.register_shadow_experiment(request, _gate_report())


def test_missing_baseline_plan_is_blocked():
    registry = ShadowExperimentRegistry()
    request = _experiment_request(baseline_comparison_plan={})

    with pytest.raises(ShadowExperimentRegistrationError, match="baseline_name is required"):
        registry.register_shadow_experiment(request, _gate_report())


def test_oos_plan_requires_point_in_time_and_embargo_checks():
    registry = ShadowExperimentRegistry()
    request = _experiment_request(
        out_of_sample_validation_plan={
            "method": "walk_forward",
            "walk_forward_enabled": True,
            "holdout_periods": ["2026H1"],
            "leakage_checks": ["point_in_time"],
            "promotion_criteria_documented": True,
        }
    )

    with pytest.raises(ShadowExperimentRegistrationError, match="purged_embargo leakage check is required"):
        registry.register_shadow_experiment(request, _gate_report())


def test_observation_plan_requires_four_windows():
    registry = ShadowExperimentRegistry()
    request = _experiment_request(
        observation_plan={
            "observation_frequency": "weekly",
            "minimum_shadow_windows": 2,
            "required_reports": ["ModelAdmissionGateReport", "ShadowExperimentManifest", "ShadowObservationReport"],
            "revocation_triggers": ["net_underperformance"],
        }
    )

    with pytest.raises(ShadowExperimentRegistrationError, match="minimum_shadow_windows must be >= 4"):
        registry.register_shadow_experiment(request, _gate_report())


def test_required_forbidden_outputs_are_enforced():
    registry = ShadowExperimentRegistry()
    request = _experiment_request(forbidden_outputs=["production_config"])

    with pytest.raises(ShadowExperimentRegistrationError, match="missing required forbidden outputs"):
        registry.register_shadow_experiment(request, _gate_report())


def test_registered_manifests_are_queryable_by_family():
    registry = ShadowExperimentRegistry()
    xgb_manifest = registry.register_shadow_experiment(_experiment_request(), _gate_report())

    event_report = _gate_report(
        candidate_name="event_surprise_v1",
        candidate_family="llm_event_surprise_factor",
        candidate_namespace="candidate_event.surprise_v1",
        intended_outputs=["candidate_event.surprise_v1.event_surprise_score"],
        event_taxonomy_defined=True,
        label_consistency_score=0.90,
        event_timestamp_policy_defined=True,
        bounded_overlay_preserved=True,
    )
    event_request = _experiment_request(
        experiment_id="exp_event_surprise_v1",
        candidate_id="event_surprise_v1",
        candidate_name="event_surprise_v1",
        candidate_family="llm_event_surprise_factor",
        candidate_namespace="candidate_event.surprise_v1",
        source_gate_report_id="gate_event_surprise_v1",
        output_contract={
            **_experiment_request().output_contract,
            "allowed_outputs": ["candidate_event.surprise_v1.event_surprise_score"],
            "output_namespace": "candidate_event.surprise_v1",
        },
        training_data_window={
            **_experiment_request().training_data_window,
            "minimum_observations": 100,
        },
    )
    event_manifest = registry.register_shadow_experiment(event_request, event_report)

    assert registry.list_active_experiments(candidate_family="xgboost_meta_model") == [xgb_manifest]
    assert registry.list_active_experiments(candidate_family="llm_event_surprise_factor") == [event_manifest]


def test_revocation_preserves_manifest_but_removes_from_active_list():
    registry = ShadowExperimentRegistry()
    original = registry.register_shadow_experiment(_experiment_request(), _gate_report())

    revoked = registry.revoke_experiment("exp_xgb_meta_v1", "source audit gap too high")

    assert original.status == "registered"
    assert revoked.status == "revoked"
    assert "source audit gap too high" in revoked.notes
    assert registry.get_experiment("exp_xgb_meta_v1") == revoked
    assert registry.get_experiment_history("exp_xgb_meta_v1") == [original, revoked]
    assert registry.list_active_experiments() == []


def test_archive_preserves_audit_record():
    registry = ShadowExperimentRegistry()
    registry.register_shadow_experiment(_experiment_request(), _gate_report())

    archived = registry.archive_experiment("exp_xgb_meta_v1", "experiment superseded")

    assert archived.status == "archived"
    assert "experiment superseded" in archived.notes
    assert registry.list_experiments(status="archived") == [archived]
    assert len(registry.get_experiment_history("exp_xgb_meta_v1")) == 2


def test_registry_module_does_not_import_model_libraries():
    import agent.research_v1.p24_experiment_registry as registry_module

    module_names = set(registry_module.__dict__)
    forbidden_names = {"xgboost", "torch", "tensorflow", "sklearn", "stable_baselines3"}

    assert module_names.isdisjoint(forbidden_names)


def test_manifest_nested_contracts_are_immutable():
    registry = ShadowExperimentRegistry()
    manifest = registry.register_shadow_experiment(_experiment_request(), _gate_report())

    with pytest.raises((TypeError, AttributeError)):
        manifest.output_contract["writes_production_config"] = True

    with pytest.raises((TypeError, AttributeError)):
        manifest.forbidden_outputs.append("something")

    with pytest.raises((TypeError, AttributeError)):
        manifest.input_contract["allowed_sources"].append("something")

    with pytest.raises((TypeError, AttributeError)):
        manifest.gate_warnings.append("extra_warning")


def test_duplicate_experiment_id_registration_is_blocked_after_revocation():
    registry = ShadowExperimentRegistry()
    registry.register_shadow_experiment(_experiment_request(), _gate_report())
    registry.revoke_experiment("exp_xgb_meta_v1", "test revocation")

    with pytest.raises(ShadowExperimentRegistrationError, match="already registered"):
        registry.register_shadow_experiment(
            _experiment_request(experiment_id="exp_xgb_meta_v1"), _gate_report()
        )


def test_manifest_to_dict_returns_plain_serializable_structures():
    registry = ShadowExperimentRegistry()
    manifest = registry.register_shadow_experiment(_experiment_request(), _gate_report())

    d = manifest.to_dict()

    assert isinstance(d["input_contract"], dict)
    assert isinstance(d["output_contract"], dict)
    assert isinstance(d["forbidden_outputs"], list)
    assert isinstance(d["gate_warnings"], list)
    assert isinstance(d["blocking_reasons"], list)

    # Verify it is actually JSON-serializable (no MappingProxyType or tuple inside)
    import json
    json.dumps(d)
