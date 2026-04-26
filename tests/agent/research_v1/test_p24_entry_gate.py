"""P24 Entry Gate Evaluator acceptance tests."""

import pytest

from agent.research_v1.p24_entry_gate import (
    P24CandidateRequest,
    P24SystemEvidence,
    evaluate_p24_entry_gate,
)


def _base_request(**overrides):
    values = dict(
        candidate_name="xgb_meta_v1",
        candidate_family="xgboost_meta_model",
        candidate_namespace="shadow_meta_model.xgb_v1",
        requested_phase="P24",
        intended_outputs=["shadow_ranking_score"],
        uses_point_in_time_sources=True,
        source_audit_plan_defined=True,
        simple_baseline_defined=True,
        out_of_sample_plan_defined=True,
        uses_gross_returns_as_primary=False,
        writes_production_fields=False,
        requires_portfolio_layer=False,
        requires_execution_data=False,
        notes="test",
        residualization_plan_defined=False,
        event_taxonomy_defined=False,
        label_consistency_score=0.0,
        event_timestamp_policy_defined=False,
        bounded_overlay_preserved=False,
        macro_source_point_in_time=False,
        feature_frequency_matches_horizon=False,
        forward_fill_policy_defined=False,
        exploratory_mode=False,
        point_in_time_relation_graph=False,
        relation_group_count=0,
        average_tickers_per_group=0.0,
        simple_relation_baseline_tested=False,
        timing_factor_weak_or_unstable=False,
        simple_timing_baselines_tested=False,
        walk_forward_validation_defined=False,
        sequence_history_sufficient=False,
        ppo_objective="",
        affects_stock_selection=False,
    )
    values.update(overrides)
    return P24CandidateRequest(**values)


def _base_evidence(**overrides):
    values = dict(
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
    values.update(overrides)
    return P24SystemEvidence(**values)


def test_xgboost_candidate_passes_when_all_gates_pass():
    report = evaluate_p24_entry_gate(_base_request(), _base_evidence())
    assert report.passed is True
    assert report.universal_gate_status == "pass"
    assert report.model_specific_gate_status == "pass"
    assert report.production_write_blocked is True


def test_universal_gate_blocks_without_p24_readiness():
    report = evaluate_p24_entry_gate(_base_request(), _base_evidence(ready_for_p24_gate=False))
    assert report.passed is False
    assert "ready_for_p24_gate_false" in report.blocking_reasons


def test_xgboost_blocks_when_sample_size_too_small():
    report = evaluate_p24_entry_gate(
        _base_request(),
        _base_evidence(independent_cross_sectional_observations=200),
    )
    assert report.passed is False
    assert "xgboost_insufficient_observations" in report.blocking_reasons


def test_ppo_blocks_without_portfolio_and_execution_layers():
    request = _base_request(
        candidate_name="ppo_exec_v1",
        candidate_family="ppo_execution_model",
        candidate_namespace="shadow_execution.ppo_v1",
        ppo_objective="execution_cost_reduction",
        affects_stock_selection=False,
        requires_portfolio_layer=True,
        requires_execution_data=True,
    )
    report = evaluate_p24_entry_gate(request, _base_evidence(portfolio_layer_exists=False, execution_dataset_exists=False))
    assert report.passed is False
    assert "ppo_portfolio_layer_missing" in report.blocking_reasons
    assert "ppo_execution_dataset_missing" in report.blocking_reasons


def test_macro_candidate_passes_in_exploratory_mode_with_namespace():
    request = _base_request(
        candidate_name="macro_rates_v1",
        candidate_family="macro_regime_factor",
        candidate_namespace="candidate_macro.rates_v1",
        macro_source_point_in_time=True,
        feature_frequency_matches_horizon=True,
        forward_fill_policy_defined=True,
        exploratory_mode=True,
    )
    report = evaluate_p24_entry_gate(request, _base_evidence(regime_gate_has_return_separation=False))
    assert report.passed is True


def test_llm_event_blocks_without_taxonomy():
    request = _base_request(
        candidate_name="event_surprise_v1",
        candidate_family="llm_event_surprise_factor",
        candidate_namespace="candidate_event.surprise_v1",
        event_taxonomy_defined=False,
        label_consistency_score=0.90,
        event_timestamp_policy_defined=True,
        bounded_overlay_preserved=True,
    )
    report = evaluate_p24_entry_gate(request, _base_evidence())
    assert report.passed is False
    assert "event_taxonomy_missing" in report.blocking_reasons


def test_llm_event_blocks_with_low_label_consistency():
    request = _base_request(
        candidate_name="event_surprise_v1",
        candidate_family="llm_event_surprise_factor",
        candidate_namespace="candidate_event.surprise_v1",
        event_taxonomy_defined=True,
        label_consistency_score=0.70,
        event_timestamp_policy_defined=True,
        bounded_overlay_preserved=True,
    )
    report = evaluate_p24_entry_gate(request, _base_evidence())
    assert report.passed is False
    assert "event_label_consistency_too_low" in report.blocking_reasons


def test_relation_blocks_with_insufficient_groups():
    request = _base_request(
        candidate_name="relation_v1",
        candidate_family="relation_model",
        candidate_namespace="candidate_relation.graph_v1",
        point_in_time_relation_graph=True,
        relation_group_count=10,
        average_tickers_per_group=15.0,
        simple_relation_baseline_tested=True,
    )
    report = evaluate_p24_entry_gate(request, _base_evidence())
    assert report.passed is False
    assert "relation_insufficient_groups" in report.blocking_reasons


def test_sequence_blocks_without_walk_forward():
    request = _base_request(
        candidate_name="sequence_v1",
        candidate_family="sequence_timing_model",
        candidate_namespace="candidate_timing_sequence.seq_v1",
        timing_factor_weak_or_unstable=True,
        simple_timing_baselines_tested=True,
        walk_forward_validation_defined=False,
        sequence_history_sufficient=True,
    )
    report = evaluate_p24_entry_gate(request, _base_evidence())
    assert report.passed is False
    assert "sequence_walk_forward_not_defined" in report.blocking_reasons


def test_ppo_blocks_with_wrong_objective():
    request = _base_request(
        candidate_name="ppo_exec_v1",
        candidate_family="ppo_execution_model",
        candidate_namespace="shadow_execution.ppo_v1",
        ppo_objective="alpha_generation",
        affects_stock_selection=False,
        requires_portfolio_layer=True,
        requires_execution_data=True,
    )
    report = evaluate_p24_entry_gate(request, _base_evidence(portfolio_layer_exists=True, execution_dataset_exists=True))
    assert report.passed is False
    assert "ppo_objective_must_be_execution_cost_reduction" in report.blocking_reasons


def test_ppo_blocks_if_affects_stock_selection():
    request = _base_request(
        candidate_name="ppo_exec_v1",
        candidate_family="ppo_execution_model",
        candidate_namespace="shadow_execution.ppo_v1",
        ppo_objective="execution_cost_reduction",
        affects_stock_selection=True,
        requires_portfolio_layer=True,
        requires_execution_data=True,
    )
    report = evaluate_p24_entry_gate(request, _base_evidence(portfolio_layer_exists=True, execution_dataset_exists=True))
    assert report.passed is False
    assert "ppo_cannot_affect_stock_selection" in report.blocking_reasons


def test_xgboost_passes_with_residualization_when_high_correlation():
    request = _base_request(residualization_plan_defined=True)
    report = evaluate_p24_entry_gate(request, _base_evidence(max_abs_cross_factor_correlation=0.85))
    assert report.passed is True


def test_xgboost_blocks_without_residualization_when_high_correlation():
    request = _base_request(residualization_plan_defined=False)
    report = evaluate_p24_entry_gate(request, _base_evidence(max_abs_cross_factor_correlation=0.85))
    assert report.passed is False
    assert "xgboost_factor_correlation_too_high" in report.blocking_reasons


def test_blocks_production_field_writes():
    report = evaluate_p24_entry_gate(_base_request(writes_production_fields=True), _base_evidence())
    assert report.passed is False
    assert "writes_production_fields" in report.blocking_reasons
    assert report.production_write_blocked is True


def test_blocks_gross_return_primary_candidate():
    report = evaluate_p24_entry_gate(_base_request(uses_gross_returns_as_primary=True), _base_evidence())
    assert report.passed is False
    assert "uses_gross_returns_as_primary" in report.blocking_reasons


def test_blocks_missing_point_in_time_source_policy():
    report = evaluate_p24_entry_gate(_base_request(uses_point_in_time_sources=False), _base_evidence())
    assert report.passed is False
    assert "missing_point_in_time_sources" in report.blocking_reasons
