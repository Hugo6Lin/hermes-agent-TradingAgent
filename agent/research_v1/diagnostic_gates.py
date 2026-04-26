"""P22-A+ diagnostic readiness gates."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DiagnosticGateConfig:
    min_observations: int = 60
    min_unique_tickers: int = 10
    max_missing_return_rate: float = 0.20
    max_lookahead_violation_rate: float = 0.0
    max_source_audit_gap_rate: float = 0.20
    min_abs_net_ic_for_ready: float = 0.05
    max_abs_factor_correlation: float = 0.70
    min_newey_west_t_stat_for_ready: float = 1.50


def evaluate_factor_readiness(
    sample_size: int,
    unique_tickers: int,
    missing_return_rate: float,
    lookahead_violation_rate: float,
    source_audit_gap_rate: float,
    net_ic: float,
    newey_west_t_stat: float,
    max_abs_cross_factor_correlation: float,
    config: DiagnosticGateConfig | None = None,
) -> dict:
    active = config or DiagnosticGateConfig()
    if sample_size < active.min_observations or unique_tickers < active.min_unique_tickers:
        return {"readiness_status": "insufficient_sample", "ready_for_shadow_calibration": False, "diagnostic_flags": ["insufficient_sample"]}
    if missing_return_rate > active.max_missing_return_rate:
        return {"readiness_status": "missing_returns_too_high", "ready_for_shadow_calibration": False, "diagnostic_flags": ["missing_returns_too_high"]}
    if lookahead_violation_rate > active.max_lookahead_violation_rate:
        return {"readiness_status": "lookahead_violations_present", "ready_for_shadow_calibration": False, "diagnostic_flags": ["lookahead_violations_present"]}
    if source_audit_gap_rate > active.max_source_audit_gap_rate:
        return {"readiness_status": "source_audit_gap_too_high", "ready_for_shadow_calibration": False, "diagnostic_flags": ["source_audit_gap_too_high"]}
    if abs(net_ic) < active.min_abs_net_ic_for_ready:
        return {"readiness_status": "weak_net_ic", "ready_for_shadow_calibration": False, "diagnostic_flags": ["weak_net_ic"]}
    if abs(newey_west_t_stat) < active.min_newey_west_t_stat_for_ready:
        return {"readiness_status": "hac_tstat_too_low", "ready_for_shadow_calibration": False, "diagnostic_flags": ["hac_tstat_too_low"]}
    flags = []
    if abs(max_abs_cross_factor_correlation) > active.max_abs_factor_correlation:
        flags.append("orthogonality_warning")
    return {"readiness_status": "ready_for_shadow_calibration", "ready_for_shadow_calibration": True, "diagnostic_flags": flags}