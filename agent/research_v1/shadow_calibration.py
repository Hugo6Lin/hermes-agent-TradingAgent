"""P23 shadow-only calibration recommendations."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def calculate_evidence_strength(
    net_ic: float,
    newey_west_t_stat: float,
    sample_size: int,
    missing_return_rate: float,
    diagnostic_flags: list[str],
    daily_health_status: str,
) -> float:
    strength = (
        0.40 * min(abs(float(net_ic)) / 0.10, 1.0)
        + 0.30 * min(abs(float(newey_west_t_stat)) / 3.0, 1.0)
        + 0.20 * min(float(sample_size) / 240.0, 1.0)
        + 0.10 * (1.0 - _clamp(float(missing_return_rate), 0.0, 1.0))
    )
    if "cost_fragile" in diagnostic_flags:
        strength -= 0.20
    if "orthogonality_warning" in diagnostic_flags:
        strength -= 0.20
    if daily_health_status == "critical":
        strength -= 0.30
    return round(_clamp(strength, 0.0, 1.0), 6)


def calculate_delta(evidence_strength: float) -> float:
    return round(_clamp(1.0 - float(evidence_strength), 0.25, 0.90), 6)


def shrink_value(prior_value: float, data_suggested_value: float, delta: float) -> float:
    return round(float(delta) * float(prior_value) + (1.0 - float(delta)) * float(data_suggested_value), 6)


from agent.research_v1.shadow_calibration_mappings import map_factor_to_shadow_parameters


@dataclass(frozen=True)
class ShadowCalibrationRecommendation:
    parameter_family: str
    parameter_name: str
    factor_name: str
    horizon_days: int
    prior_value: float
    data_suggested_value: float
    shadow_value: float
    delta: float
    evidence_strength: float
    sample_size: int
    net_ic: float
    newey_west_t_stat: float
    readiness_status: str
    calibration_status: str
    apply_to_production: bool
    diagnostic_flags: list[str]
    human_reason: str


@dataclass(frozen=True)
class ShadowCalibrationReport:
    schema_version: str
    mode: str
    generated_at: str
    source_report_schema_version: str
    recommendations: list[ShadowCalibrationRecommendation]
    blocked_candidates: list[dict]
    global_warnings: list[str]
    production_config_changes: list[dict]
    overall_status: str

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "mode": self.mode,
            "generated_at": self.generated_at,
            "source_report_schema_version": self.source_report_schema_version,
            "recommendations": [asdict(item) for item in self.recommendations],
            "blocked_candidates": self.blocked_candidates,
            "global_warnings": self.global_warnings,
            "production_config_changes": self.production_config_changes,
            "overall_status": self.overall_status,
        }


def _prior_value(parameter_family: str, parameter_name: str) -> float:
    priors = {
        ("role_weight", "fundamentals"): 0.40,
        ("role_weight", "technical"): 0.25,
        ("role_weight", "valuation"): 0.00,
        ("role_weight", "sentiment"): 0.10,
        ("thesis_threshold", "investable_quality_threshold"): 0.65,
        ("thesis_threshold", "investable_valuation_threshold"): 0.15,
        ("exit_multiple", "timing_exit_responsiveness"): 1.00,
    }
    return priors.get((parameter_family, parameter_name), 0.50)


def _data_suggested_value(prior: float, parameter_family: str, net_ic: float) -> float:
    direction = 1.0 if net_ic >= 0 else -1.0
    if parameter_family == "thesis_threshold":
        return _clamp(prior + direction * min(abs(net_ic), 0.05), 0.0, 1.0)
    if parameter_family == "exit_multiple":
        return _clamp(prior + direction * min(abs(net_ic) * 2.0, 0.25), 0.25, 5.0)
    return _clamp(prior + direction * min(abs(net_ic), 0.10), 0.0, 1.0)


def generate_shadow_recommendations(p22_report: dict) -> ShadowCalibrationReport:
    warnings = []
    blocked = []
    recommendations = []
    health_status = p22_report.get("daily_health_report", {}).get("overall_health_status", "unknown")
    source_schema = p22_report.get("schema_version", "unknown")

    if p22_report.get("return_basis_default") != "net":
        warnings.append("return_basis_not_net")
    integrity = p22_report.get("data_integrity_report", {})
    if integrity.get("lookahead_violation_rate", 0.0) > 0.0:
        warnings.append("lookahead_violations_present")
    if integrity.get("source_audit_gap_rate", 0.0) > 0.20:
        warnings.append("source_audit_gap_too_high")
    if health_status == "critical":
        warnings.append("daily_health_critical")

    for metric in p22_report.get("factor_metrics", []):
        factor = metric.get("factor_name")
        horizon = int(metric.get("horizon_days", 0))
        if warnings:
            blocked.append({"factor_name": factor, "horizon_days": horizon, "reason": ";".join(warnings)})
            continue
        if not metric.get("ready_for_shadow_calibration"):
            blocked.append({"factor_name": factor, "horizon_days": horizon, "reason": metric.get("readiness_status", "not_ready")})
            continue
        net_ic = float(metric.get("net_ic") or 0.0)
        strength = calculate_evidence_strength(
            net_ic=net_ic,
            newey_west_t_stat=float(metric.get("newey_west_t_stat") or 0.0),
            sample_size=int(metric.get("sample_size") or 0),
            missing_return_rate=float(metric.get("missing_return_rate") or 0.0),
            diagnostic_flags=list(metric.get("diagnostic_flags") or []),
            daily_health_status=health_status,
        )
        delta = calculate_delta(strength)
        for mapping in map_factor_to_shadow_parameters(factor, horizon):
            prior = _prior_value(mapping["parameter_family"], mapping["parameter_name"])
            data_value = _data_suggested_value(prior, mapping["parameter_family"], net_ic)
            recommendations.append(ShadowCalibrationRecommendation(
                parameter_family=mapping["parameter_family"],
                parameter_name=mapping["parameter_name"],
                factor_name=factor,
                horizon_days=horizon,
                prior_value=prior,
                data_suggested_value=data_value,
                shadow_value=shrink_value(prior, data_value, delta),
                delta=delta,
                evidence_strength=strength,
                sample_size=int(metric.get("sample_size") or 0),
                net_ic=net_ic,
                newey_west_t_stat=float(metric.get("newey_west_t_stat") or 0.0),
                readiness_status=str(metric.get("readiness_status")),
                calibration_status="shadow_only",
                apply_to_production=False,
                diagnostic_flags=list(metric.get("diagnostic_flags") or []),
                human_reason=f"{factor}@{horizon}d passed P22-A+ readiness; shadow-only recommendation.",
            ))

    if warnings and not recommendations:
        if "return_basis_not_net" in warnings:
            status = "blocked_by_return_basis"
        elif "lookahead_violations_present" in warnings or "source_audit_gap_too_high" in warnings:
            status = "blocked_by_data_integrity"
        else:
            status = "blocked_by_health_check"
    elif recommendations:
        status = "shadow_recommendations_available"
    else:
        status = "no_ready_factors"
    return ShadowCalibrationReport(
        schema_version="p23.0",
        mode="shadow_only",
        generated_at=datetime.now(timezone.utc).isoformat(),
        source_report_schema_version=source_schema,
        recommendations=recommendations,
        blocked_candidates=blocked,
        global_warnings=warnings,
        production_config_changes=[],
        overall_status=status,
    )
