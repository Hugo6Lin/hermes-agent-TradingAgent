"""P23 Shadow Calibration acceptance tests."""

import pytest

from agent.research_v1.shadow_calibration import (
    calculate_evidence_strength,
    calculate_delta,
    shrink_value,
)


def test_evidence_strength_uses_net_ic_hac_sample_and_missing_rate():
    strength = calculate_evidence_strength(
        net_ic=0.08,
        newey_west_t_stat=2.4,
        sample_size=180,
        missing_return_rate=0.05,
        diagnostic_flags=[],
        daily_health_status="ok",
    )
    assert 0.0 < strength <= 1.0
    assert strength > 0.50


def test_evidence_strength_penalizes_cost_fragile_and_health_critical():
    clean = calculate_evidence_strength(0.08, 2.4, 180, 0.05, [], "ok")
    penalized = calculate_evidence_strength(0.08, 2.4, 180, 0.05, ["cost_fragile"], "critical")
    assert penalized < clean


def test_delta_is_bounded_between_prior_and_data():
    assert calculate_delta(0.0) == 0.90
    assert calculate_delta(1.0) == 0.25
    assert 0.25 <= calculate_delta(0.55) <= 0.90


def test_shrink_value_keeps_prior_influence():
    value = shrink_value(prior_value=0.40, data_suggested_value=0.80, delta=0.50)
    assert value == 0.60


from agent.research_v1.shadow_calibration_mappings import map_factor_to_shadow_parameters


def test_quality_factor_maps_to_fundamentals_weight_and_ranking_hint():
    mappings = map_factor_to_shadow_parameters("company_quality_score", horizon_days=63)
    names = {(m["parameter_family"], m["parameter_name"]) for m in mappings}
    assert ("role_weight", "fundamentals") in names
    assert ("ranking_hint", "company_quality_score") in names


def test_timing_short_horizon_maps_to_exit_multiple_hint():
    mappings = map_factor_to_shadow_parameters("timing_market_fit_score", horizon_days=5)
    names = {(m["parameter_family"], m["parameter_name"]) for m in mappings}
    assert ("role_weight", "technical") in names
    assert ("exit_multiple", "timing_exit_responsiveness") in names


from agent.research_v1.shadow_calibration import generate_shadow_recommendations


def _p22_report(metric_overrides=None, health_status="ok", return_basis="net"):
    metric = {
        "factor_name": "company_quality_score",
        "horizon_days": 63,
        "sample_size": 180,
        "unique_tickers": 40,
        "gross_ic": 0.09,
        "net_ic": 0.08,
        "icir": 0.5,
        "newey_west_t_stat": 2.4,
        "missing_return_rate": 0.05,
        "readiness_status": "ready_for_shadow_calibration",
        "ready_for_shadow_calibration": True,
        "diagnostic_flags": [],
    }
    if metric_overrides:
        metric.update(metric_overrides)
    return {
        "schema_version": "p22.0",
        "return_basis_default": return_basis,
        "data_integrity_report": {"lookahead_violation_rate": 0.0, "source_audit_gap_rate": 0.0},
        "factor_metrics": [metric],
        "daily_health_report": {"overall_health_status": health_status},
    }


def test_generate_shadow_recommendations_for_ready_factor():
    report = generate_shadow_recommendations(_p22_report())
    assert report.mode == "shadow_only"
    assert report.production_config_changes == []
    assert report.recommendations
    rec = report.recommendations[0]
    assert rec.apply_to_production is False
    assert rec.calibration_status == "shadow_only"
    assert rec.prior_value != rec.shadow_value


def test_non_ready_factor_is_blocked_not_recommended():
    report = generate_shadow_recommendations(_p22_report({
        "ready_for_shadow_calibration": False,
        "readiness_status": "weak_net_ic",
        "net_ic": 0.01,
    }))
    assert report.recommendations == []
    assert report.blocked_candidates


def test_gross_only_edge_is_blocked_when_net_not_ready():
    report = generate_shadow_recommendations(_p22_report({
        "gross_ic": 0.10,
        "net_ic": 0.01,
        "ready_for_shadow_calibration": False,
        "readiness_status": "weak_net_ic",
    }))
    assert report.recommendations == []
    assert report.blocked_candidates[0]["reason"] == "weak_net_ic"


def test_lookahead_warning_blocks_all_recommendations():
    payload = _p22_report()
    payload["data_integrity_report"]["lookahead_violation_rate"] = 0.01
    report = generate_shadow_recommendations(payload)
    assert report.recommendations == []
    assert "lookahead_violations_present" in report.global_warnings
    assert report.overall_status == "blocked_by_data_integrity"


def test_critical_health_blocks_all_recommendations():
    report = generate_shadow_recommendations(_p22_report(health_status="critical"))
    assert report.recommendations == []
    assert "daily_health_critical" in report.global_warnings


def test_report_never_contains_production_config_changes():
    report = generate_shadow_recommendations(_p22_report())
    payload = report.to_dict()
    assert payload["production_config_changes"] == []
    assert all(item["apply_to_production"] is False for item in payload["recommendations"])
    assert "calibrated" not in str(payload).lower()


def test_source_audit_gap_blocks_all_recommendations():
    payload = _p22_report()
    payload["data_integrity_report"]["source_audit_gap_rate"] = 1.0
    report = generate_shadow_recommendations(payload)
    assert report.recommendations == []
    assert "source_audit_gap_too_high" in report.global_warnings
    assert report.overall_status == "blocked_by_data_integrity"


def test_non_net_return_basis_reports_correct_block_status():
    report = generate_shadow_recommendations(_p22_report(return_basis="gross"))
    assert report.recommendations == []
    assert "return_basis_not_net" in report.global_warnings
    assert report.overall_status == "blocked_by_return_basis"
