"""P23 Shadow Observation Loop acceptance tests."""

import pytest

from agent.research_v1.shadow_observation import (
    ShadowRecommendationObservation,
    observations_from_shadow_report,
)


def _shadow_report_payload():
    return {
        "schema_version": "p23.0",
        "mode": "shadow_only",
        "generated_at": "2026-04-25T00:00:00Z",
        "source_report_schema_version": "p22.0",
        "recommendations": [{
            "parameter_family": "role_weight",
            "parameter_name": "fundamentals",
            "factor_name": "company_quality_score",
            "horizon_days": 63,
            "prior_value": 0.40,
            "data_suggested_value": 0.48,
            "shadow_value": 0.44,
            "delta": 0.50,
            "evidence_strength": 0.50,
            "sample_size": 180,
            "net_ic": 0.08,
            "newey_west_t_stat": 2.4,
            "readiness_status": "ready_for_shadow_calibration",
            "calibration_status": "shadow_only",
            "apply_to_production": False,
            "diagnostic_flags": [],
            "human_reason": "test",
        }],
        "blocked_candidates": [],
        "global_warnings": [],
        "production_config_changes": [],
        "overall_status": "shadow_recommendations_available",
    }


def test_observations_from_shadow_report_preserve_source_ids():
    observations = observations_from_shadow_report(
        _shadow_report_payload(),
        source_p22_report_id="p22_report_001",
        source_p23_report_id="p23_report_001",
    )
    assert len(observations) == 1
    obs = observations[0]
    assert obs.source_p22_report_id == "p22_report_001"
    assert obs.source_p23_report_id == "p23_report_001"
    assert obs.observation_status == "active"
    assert obs.apply_to_production is False


from agent.research_v1.shadow_observation import evaluate_shadow_observation


def _observation():
    return observations_from_shadow_report(
        _shadow_report_payload(),
        source_p22_report_id="p22_report_001",
        source_p23_report_id="p23_report_001",
    )[0]


def test_evaluation_marks_shadow_outperformance():
    evaluation = evaluate_shadow_observation(
        _observation(),
        latest_net_ic=0.09,
        latest_newey_west_t_stat=2.2,
        latest_evidence_strength=0.60,
        prior_metric=0.02,
        shadow_metric=0.04,
        health_status="ok",
        reversal_count=0,
        consecutive_underperformance=0,
        source_blocker_active=False,
    )
    assert evaluation.shadow_outperformed_prior is True
    assert evaluation.revocation_triggered is False


def test_evaluation_revokes_on_weak_net_ic():
    evaluation = evaluate_shadow_observation(
        _observation(),
        latest_net_ic=0.01,
        latest_newey_west_t_stat=2.2,
        latest_evidence_strength=0.40,
        prior_metric=0.03,
        shadow_metric=0.02,
        health_status="ok",
        reversal_count=0,
        consecutive_underperformance=0,
        source_blocker_active=False,
    )
    assert evaluation.revocation_triggered is True
    assert "latest_net_ic_below_floor" in evaluation.diagnostic_flags


from agent.research_v1.shadow_observation import (
    update_observation_status,
    build_shadow_monitor_report,
)


def test_update_observation_status_revoked_is_retained():
    obs = _observation()
    evaluation = evaluate_shadow_observation(
        obs,
        latest_net_ic=0.01,
        latest_newey_west_t_stat=0.8,
        latest_evidence_strength=0.20,
        prior_metric=0.03,
        shadow_metric=0.02,
        health_status="ok",
        reversal_count=0,
        consecutive_underperformance=0,
        source_blocker_active=False,
    )
    updated = update_observation_status(obs, [evaluation], min_windows_for_p24=2)
    assert updated.observation_status == "revoked"
    assert updated.recommendation_id == obs.recommendation_id


def test_monitor_report_requires_observation_windows_for_p24_gate():
    obs = _observation()
    evaluation = evaluate_shadow_observation(
        obs,
        latest_net_ic=0.09,
        latest_newey_west_t_stat=2.0,
        latest_evidence_strength=0.65,
        prior_metric=0.02,
        shadow_metric=0.04,
        health_status="ok",
        reversal_count=0,
        consecutive_underperformance=0,
        source_blocker_active=False,
    )
    report = build_shadow_monitor_report([obs], [evaluation], min_windows_for_p24=2)
    assert report.ready_for_p24_gate is False
    assert report.watch_recommendation_count == 1


def test_monitor_report_marks_ready_for_p24_after_enough_positive_windows():
    obs = _observation()
    evaluations = [
        evaluate_shadow_observation(
            obs,
            latest_net_ic=0.09,
            latest_newey_west_t_stat=2.0,
            latest_evidence_strength=0.65,
            prior_metric=0.02,
            shadow_metric=0.04,
            health_status="ok",
            reversal_count=0,
            consecutive_underperformance=0,
            source_blocker_active=False,
            evaluation_window=f"week_{i}",
        )
        for i in range(4)
    ]
    report = build_shadow_monitor_report([obs], evaluations, min_windows_for_p24=4)
    assert report.ready_for_p24_gate is True
    assert report.eligible_for_p24_count == 1
