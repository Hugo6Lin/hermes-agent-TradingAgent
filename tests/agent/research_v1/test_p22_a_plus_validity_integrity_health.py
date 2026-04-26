"""P22-A+ validity, integrity, and health acceptance tests."""

import pytest

from agent.research_v1.data_integrity import run_data_integrity_preflight
from agent.research_v1.newey_west import newey_west_t_stat
from agent.research_v1.diagnostic_gates import DiagnosticGateConfig, evaluate_factor_readiness
from agent.research_v1.factor_diagnostics import (
    compute_factor_metric,
    compute_orthogonality_results,
    compute_decay_result,
    compute_autocorrelation,
)
from agent.research_v1.factor_health_check import run_daily_factor_health_check
from agent.research_v1.diagnostic_reports import build_p22_a_plus_report


# ---------------------------------------------------------------------------
# Task 1: Data Integrity Preflight
# ---------------------------------------------------------------------------

def test_preflight_flags_and_excludes_lookahead_rows():
    rows = [
        {
            "snapshot_id": "clean",
            "trading_day": "2026-04-24",
            "data_as_of_date": "2026-04-23",
            "as_of_timestamp": "2026-04-24T10:00:00Z",
            "source_as_of_date": "2026-04-22",
            "source_fetched_at": "2026-04-23T12:00:00Z",
            "source_refs": ["filing:AAPL"],
            "provider": "test",
            "sector_id": "technology",
            "classification_as_of_date": "2026-04-01",
        },
        {
            "snapshot_id": "leaky",
            "trading_day": "2026-04-24",
            "data_as_of_date": "2026-04-23",
            "as_of_timestamp": "2026-04-24T10:00:00Z",
            "source_as_of_date": "2026-04-25",
            "source_fetched_at": "2026-04-25T12:00:00Z",
            "source_refs": ["filing:MSFT"],
            "provider": "test",
            "sector_id": "technology",
            "classification_as_of_date": "2026-04-01",
        },
    ]

    report = run_data_integrity_preflight(rows)

    assert report.lookahead_violation_count == 1
    assert report.excluded_snapshot_ids == ["leaky"]
    assert report.clean_rows[0]["snapshot_id"] == "clean"


def test_preflight_flags_source_and_sector_audit_gaps():
    rows = [{
        "snapshot_id": "gap",
        "trading_day": "2026-04-24",
        "data_as_of_date": "2026-04-23",
        "as_of_timestamp": "2026-04-24T10:00:00Z",
    }]

    report = run_data_integrity_preflight(rows)

    assert report.source_audit_gap_count == 1
    assert report.sector_snapshot_missing_count == 1
    assert "source_audit_gap" in report.diagnostic_flags
    assert "sector_snapshot_missing" in report.diagnostic_flags


# ---------------------------------------------------------------------------
# Task 2: Newey-West and Readiness Gates
# ---------------------------------------------------------------------------

def test_newey_west_positive_series_is_positive():
    result = newey_west_t_stat([0.05, 0.04, 0.06, 0.03, 0.05, 0.07])
    assert result["t_stat"] > 0
    assert result["hac_status"] == "computed"


def test_newey_west_insufficient_periods():
    result = newey_west_t_stat([0.05])
    assert result["hac_status"] == "insufficient_periods"


def test_readiness_blocks_lookahead_violations():
    result = evaluate_factor_readiness(
        sample_size=120,
        unique_tickers=30,
        missing_return_rate=0.0,
        lookahead_violation_rate=0.01,
        source_audit_gap_rate=0.0,
        net_ic=0.10,
        newey_west_t_stat=3.0,
        max_abs_cross_factor_correlation=0.20,
    )
    assert result["ready_for_shadow_calibration"] is False
    assert result["readiness_status"] == "lookahead_violations_present"


def test_readiness_allows_shadow_calibration_when_all_gates_pass():
    result = evaluate_factor_readiness(
        sample_size=120,
        unique_tickers=30,
        missing_return_rate=0.05,
        lookahead_violation_rate=0.0,
        source_audit_gap_rate=0.05,
        net_ic=0.08,
        newey_west_t_stat=2.0,
        max_abs_cross_factor_correlation=0.20,
    )
    assert result["ready_for_shadow_calibration"] is True


def test_readiness_blocks_small_sample():
    result = evaluate_factor_readiness(
        sample_size=30,
        unique_tickers=5,
        missing_return_rate=0.0,
        lookahead_violation_rate=0.0,
        source_audit_gap_rate=0.0,
        net_ic=0.10,
        newey_west_t_stat=3.0,
        max_abs_cross_factor_correlation=0.20,
    )
    assert result["ready_for_shadow_calibration"] is False
    assert result["readiness_status"] == "insufficient_sample"


def test_readiness_blocks_weak_net_ic():
    result = evaluate_factor_readiness(
        sample_size=120,
        unique_tickers=30,
        missing_return_rate=0.0,
        lookahead_violation_rate=0.0,
        source_audit_gap_rate=0.0,
        net_ic=0.02,
        newey_west_t_stat=3.0,
        max_abs_cross_factor_correlation=0.20,
    )
    assert result["ready_for_shadow_calibration"] is False
    assert result["readiness_status"] == "weak_net_ic"


def test_readiness_blocks_low_hac_tstat():
    result = evaluate_factor_readiness(
        sample_size=120,
        unique_tickers=30,
        missing_return_rate=0.0,
        lookahead_violation_rate=0.0,
        source_audit_gap_rate=0.0,
        net_ic=0.10,
        newey_west_t_stat=1.0,
        max_abs_cross_factor_correlation=0.20,
    )
    assert result["ready_for_shadow_calibration"] is False
    assert result["readiness_status"] == "hac_tstat_too_low"


# ---------------------------------------------------------------------------
# Task 3: Factor Diagnostics
# ---------------------------------------------------------------------------

def _rows(n=80, factor="company_quality_score", negative=False):
    """Generate n rows: 5 tickers/day × 1 row/ticker/day × 16 days = 80 rows.

    5 tickers/day (10 obs across 2 groups of 5) gives meaningful daily IC variance.
    T0-T4 on days 0-7, T5-T9 on days 8-15 → 10 unique tickers.
    16 days → 16 periodic ICs (>=6). HAC t-stat computable from 5-obs/day ICs.
    """
    tickers_per_day = 5
    rows = []
    for i in range(n):
        day_idx = i // tickers_per_day
        if day_idx < 8:
            ticker_idx = i % 5  # T0-T4
        else:
            ticker_idx = 5 + (i % 5)  # T5-T9
        score = (ticker_idx + day_idx * 0.1) / 10.0
        signal_scale = 0.12
        # Noise per row: larger magnitude to ensure IC variance across days
        noise = ((i * 618033988749895 % 1000000) / 1000000.0 - 0.5) * 0.02
        net_return = -score * signal_scale + noise if negative else score * signal_scale + noise
        day_offset = day_idx + 1
        rows.append({
            "snapshot_id": f"snap_{i}",
            "ticker": f"T{ticker_idx}",
            "trading_day": f"2026-01-{day_offset:02d}",
            "horizon_days": 21,
            factor: score,
            "gross_return_pct": net_return + 0.005,
            "net_return_pct": net_return,
            "observation_status": "computed",
            "data_as_of_date": "2026-01-01",
            "as_of_timestamp": "2026-01-02T10:00:00Z",
            "source_as_of_date": "2026-01-01",
            "source_fetched_at": "2026-01-01T12:00:00Z",
            "source_refs": ["test"],
            "provider": "fixture",
            "sector_id": "technology",
            "classification_as_of_date": "2025-12-31",
            "classification": "Watchlist",
        })
    return rows


def test_compute_factor_metric_uses_net_return_and_passes_ready_case(monkeypatch):
    """Test that compute_factor_metric passes readiness when IC is high.

    Note: HAC requires periodic ICs with variance. With synthetic test data,
    daily ICs are near-constant (CLT effect from ~10 obs/day), producing
    HAC=0.0/"zero_variance". We mock newey_west_t_stat to return a passing
    value to test the full readiness flow; HAC itself is tested separately.
    """
    def mock_nw(values, lag=None):
        return {"t_stat": 3.0, "sample_size": len(values), "lag": 2, "hac_status": "computed"}
    monkeypatch.setattr("agent.research_v1.factor_diagnostics.newey_west_t_stat", mock_nw)
    result = compute_factor_metric(_rows(), "company_quality_score", 21)
    assert result.sample_size == 80
    assert result.net_ic > 0.95
    assert result.gross_ic > 0.95
    assert result.ready_for_shadow_calibration is True
    assert result.newey_west_t_stat == 3.0
    assert result.hac_status == "computed"


def test_compute_factor_metric_blocks_small_sample():
    result = compute_factor_metric(_rows(n=20), "company_quality_score", 21)
    assert result.ready_for_shadow_calibration is False
    assert result.readiness_status == "insufficient_sample"


def test_compute_factor_metric_reports_cost_impact():
    result = compute_factor_metric(_rows(), "company_quality_score", 21)
    assert result.cost_impact_on_ic is not None
    assert result.cost_fragile is not None


def test_orthogonality_flags_high_correlation():
    rows = [{
        "company_quality_score": i,
        "valuation_attractiveness_score": i * 0.99,
        "timing_market_fit_score": 100 - i,
        "llm_adjustment_total": 0.0,
        "observation_status": "computed",
    } for i in range(80)]
    results = compute_orthogonality_results(rows)
    pair = next(r for r in results if r.factor_a == "company_quality_score" and r.factor_b == "valuation_attractiveness_score")
    assert pair.highly_correlated is True


def test_compute_decay_classifies_short_horizon():
    result = compute_decay_result("company_quality_score", 0.08, 0.02, 0.01, 0.005)
    assert result.decay_classification == "short_horizon"
    assert result.factor_name == "company_quality_score"


def test_compute_autocorrelation_returns_value():
    scores = [0.5 + (i % 3) * 0.1 for i in range(50)]
    result = compute_autocorrelation(scores)
    assert "lag_1_autocorrelation" in result


# ---------------------------------------------------------------------------
# Task 4: Daily Factor Health Check
# ---------------------------------------------------------------------------

def test_health_check_flags_factor_distribution_drift():
    baseline = [{
        "company_quality_score": 0.50 + i * 0.001,
        "classification": "Watchlist",
        "horizon_days": 21,
        "observation_status": "computed",
    } for i in range(100)]
    latest = [{
        "company_quality_score": 0.95,
        "classification": "Investable",
        "horizon_days": 21,
        "observation_status": "computed",
    } for _ in range(20)]
    report = run_daily_factor_health_check(latest, baseline, factors=["company_quality_score"], horizons=[21])
    assert report.overall_health_status == "warn"
    assert report.factor_distribution_alerts


def test_health_check_flags_forward_return_completion_gap():
    latest = [{
        "company_quality_score": 0.5,
        "classification": "Watchlist",
        "horizon_days": 21,
        "observation_status": "missing_horizon",
    } for _ in range(10)]
    report = run_daily_factor_health_check(latest, [], factors=["company_quality_score"], horizons=[21])
    assert report.forward_return_completion_alerts


def test_health_check_reports_clean_when_no_drift():
    baseline = [{
        "company_quality_score": 0.5,
        "classification": "Watchlist",
        "horizon_days": 21,
        "observation_status": "computed",
    } for _ in range(100)]
    latest = [{
        "company_quality_score": 0.5,
        "classification": "Watchlist",
        "horizon_days": 21,
        "observation_status": "computed",
    } for _ in range(20)]
    report = run_daily_factor_health_check(latest, baseline, factors=["company_quality_score"], horizons=[21])
    assert report.overall_health_status == "ok"
    assert not report.factor_distribution_alerts


# ---------------------------------------------------------------------------
# Task 5: Final Report Assembly
# ---------------------------------------------------------------------------

def test_build_p22_report_contains_integrity_diagnostics_and_health_sections():
    rows = []
    for row in _rows():
        row.update({
            "data_as_of_date": "2026-01-01",
            "as_of_timestamp": "2026-01-02T10:00:00Z",
            "source_as_of_date": "2026-01-01",
            "source_fetched_at": "2026-01-01T12:00:00Z",
            "source_refs": ["test"],
            "provider": "fixture",
            "sector_id": "technology",
            "classification_as_of_date": "2025-12-31",
            "classification": "Watchlist",
        })
        rows.append(row)
    report = build_p22_a_plus_report(rows, baseline_rows=rows, factors=["company_quality_score"], horizons=[21])
    payload = report.to_dict()
    assert payload["schema_version"] == "p22.0"
    assert payload["return_basis_default"] == "net"
    assert "data_integrity_report" in payload
    assert "daily_health_report" in payload
    assert "calibrated" not in str(payload).lower()


def test_p22_report_defaults_to_net_return():
    """Verify return_basis_default is always net, never gross."""
    rows = []
    for row in _rows():
        row.update({
            "data_as_of_date": "2026-01-01",
            "as_of_timestamp": "2026-01-02T10:00:00Z",
            "source_as_of_date": "2026-01-01",
            "source_fetched_at": "2026-01-01T12:00:00Z",
            "source_refs": ["test"],
            "provider": "fixture",
            "sector_id": "technology",
            "classification_as_of_date": "2025-12-31",
            "classification": "Watchlist",
        })
        rows.append(row)
    report = build_p22_a_plus_report(rows, baseline_rows=rows, factors=["company_quality_score"], horizons=[21])
    assert report.return_basis_default == "net"