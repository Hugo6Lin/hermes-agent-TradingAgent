"""P23 shadow recommendation observation loop."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import hashlib


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_id(*parts: object) -> str:
    raw = "|".join(str(part) for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class ShadowRecommendationObservation:
    recommendation_id: str
    generated_at: str
    source_p22_report_id: str
    source_p23_report_id: str
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
    diagnostic_flags: list[str]
    observation_status: str
    apply_to_production: bool
    created_at: str
    updated_at: str

    def to_dict(self) -> dict:
        return asdict(self)


def observations_from_shadow_report(
    shadow_report: dict,
    source_p22_report_id: str,
    source_p23_report_id: str,
) -> list[ShadowRecommendationObservation]:
    observations = []
    generated_at = shadow_report.get("generated_at", _utc_now())
    now = _utc_now()
    for rec in shadow_report.get("recommendations", []):
        recommendation_id = _stable_id(
            source_p23_report_id,
            rec.get("parameter_family"),
            rec.get("parameter_name"),
            rec.get("factor_name"),
            rec.get("horizon_days"),
        )
        observations.append(ShadowRecommendationObservation(
            recommendation_id=recommendation_id,
            generated_at=generated_at,
            source_p22_report_id=source_p22_report_id,
            source_p23_report_id=source_p23_report_id,
            parameter_family=str(rec["parameter_family"]),
            parameter_name=str(rec["parameter_name"]),
            factor_name=str(rec["factor_name"]),
            horizon_days=int(rec["horizon_days"]),
            prior_value=float(rec["prior_value"]),
            data_suggested_value=float(rec["data_suggested_value"]),
            shadow_value=float(rec["shadow_value"]),
            delta=float(rec["delta"]),
            evidence_strength=float(rec["evidence_strength"]),
            sample_size=int(rec["sample_size"]),
            net_ic=float(rec["net_ic"]),
            newey_west_t_stat=float(rec["newey_west_t_stat"]),
            diagnostic_flags=list(rec.get("diagnostic_flags") or []),
            observation_status="active",
            apply_to_production=bool(rec.get("apply_to_production", False)),
            created_at=now,
            updated_at=now,
        ))
    return observations


@dataclass(frozen=True)
class ShadowObservationEvaluation:
    evaluation_id: str
    recommendation_id: str
    evaluation_date: str
    evaluation_window: str
    latest_net_ic: float
    latest_newey_west_t_stat: float
    latest_evidence_strength: float
    prior_reference_value: float
    shadow_reference_value: float
    shadow_vs_prior_delta: float
    shadow_outperformed_prior: bool
    health_status: str
    reversal_detected: bool
    revocation_triggered: bool
    diagnostic_flags: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def evaluate_shadow_observation(
    observation: ShadowRecommendationObservation,
    latest_net_ic: float,
    latest_newey_west_t_stat: float,
    latest_evidence_strength: float,
    prior_metric: float,
    shadow_metric: float,
    health_status: str,
    reversal_count: int,
    consecutive_underperformance: int,
    source_blocker_active: bool,
    evaluation_window: str = "weekly",
) -> ShadowObservationEvaluation:
    flags = []
    if latest_net_ic < 0.03:
        flags.append("latest_net_ic_below_floor")
    if latest_newey_west_t_stat < 1.0:
        flags.append("latest_hac_tstat_below_floor")
    if health_status == "critical":
        flags.append("health_critical")
    if source_blocker_active:
        flags.append("source_blocker_active")
    if reversal_count >= 2:
        flags.append("direction_reversed_twice")
    if consecutive_underperformance >= 3:
        flags.append("shadow_underperformed_prior_3_windows")

    delta = shadow_metric - prior_metric
    return ShadowObservationEvaluation(
        evaluation_id=_stable_id(observation.recommendation_id, _utc_now(), evaluation_window),
        recommendation_id=observation.recommendation_id,
        evaluation_date=_utc_now(),
        evaluation_window=evaluation_window,
        latest_net_ic=float(latest_net_ic),
        latest_newey_west_t_stat=float(latest_newey_west_t_stat),
        latest_evidence_strength=float(latest_evidence_strength),
        prior_reference_value=float(prior_metric),
        shadow_reference_value=float(shadow_metric),
        shadow_vs_prior_delta=round(delta, 10),
        shadow_outperformed_prior=delta > 0,
        health_status=health_status,
        reversal_detected=reversal_count > 0,
        revocation_triggered=bool(flags),
        diagnostic_flags=flags,
    )


@dataclass(frozen=True)
class ShadowRecommendationMonitorReport:
    schema_version: str
    generated_at: str
    active_recommendation_count: int
    watch_recommendation_count: int
    revoked_recommendation_count: int
    expired_recommendation_count: int
    eligible_for_p24_count: int
    average_evidence_strength: float
    shadow_hit_rate: float
    average_shadow_vs_prior_delta: float
    recommendation_reversal_rate: float
    health_degradation_count: int
    recommendations: list[dict]
    global_flags: list[str]
    ready_for_p24_gate: bool

    def to_dict(self) -> dict:
        return asdict(self)


def update_observation_status(
    observation: ShadowRecommendationObservation,
    evaluations: list[ShadowObservationEvaluation],
    min_windows_for_p24: int = 4,
) -> ShadowRecommendationObservation:
    status = observation.observation_status
    if any(item.revocation_triggered for item in evaluations):
        status = "revoked"
    elif len(evaluations) >= min_windows_for_p24 and all(item.shadow_outperformed_prior for item in evaluations):
        status = "eligible_for_p24_gate"
    elif evaluations:
        status = "watch"
    return ShadowRecommendationObservation(
        **{**observation.to_dict(), "observation_status": status, "updated_at": _utc_now()}
    )


def build_shadow_monitor_report(
    observations: list[ShadowRecommendationObservation],
    evaluations: list[ShadowObservationEvaluation],
    min_windows_for_p24: int = 4,
) -> ShadowRecommendationMonitorReport:
    by_recommendation = {}
    for evaluation in evaluations:
        by_recommendation.setdefault(evaluation.recommendation_id, []).append(evaluation)
    updated = [
        update_observation_status(obs, by_recommendation.get(obs.recommendation_id, []), min_windows_for_p24)
        for obs in observations
    ]
    active = sum(1 for obs in updated if obs.observation_status == "active")
    watch = sum(1 for obs in updated if obs.observation_status == "watch")
    revoked = sum(1 for obs in updated if obs.observation_status == "revoked")
    expired = sum(1 for obs in updated if obs.observation_status == "expired")
    eligible = sum(1 for obs in updated if obs.observation_status == "eligible_for_p24_gate")
    avg_strength = sum(obs.evidence_strength for obs in updated) / len(updated) if updated else 0.0
    hit_rate = sum(1 for ev in evaluations if ev.shadow_outperformed_prior) / len(evaluations) if evaluations else 0.0
    avg_delta = sum(ev.shadow_vs_prior_delta for ev in evaluations) / len(evaluations) if evaluations else 0.0
    reversal_rate = sum(1 for ev in evaluations if ev.reversal_detected) / len(evaluations) if evaluations else 0.0
    health_degradation = sum(1 for ev in evaluations if ev.health_status == "critical")
    flags = []
    if revoked:
        flags.append("revoked_recommendations_present")
    if health_degradation:
        flags.append("health_degradation_present")
    return ShadowRecommendationMonitorReport(
        schema_version="p23_observation.0",
        generated_at=_utc_now(),
        active_recommendation_count=active,
        watch_recommendation_count=watch,
        revoked_recommendation_count=revoked,
        expired_recommendation_count=expired,
        eligible_for_p24_count=eligible,
        average_evidence_strength=round(avg_strength, 6),
        shadow_hit_rate=round(hit_rate, 6),
        average_shadow_vs_prior_delta=round(avg_delta, 10),
        recommendation_reversal_rate=round(reversal_rate, 6),
        health_degradation_count=health_degradation,
        recommendations=[obs.to_dict() for obs in updated],
        global_flags=flags,
        ready_for_p24_gate=eligible > 0 and not health_degradation,
    )
