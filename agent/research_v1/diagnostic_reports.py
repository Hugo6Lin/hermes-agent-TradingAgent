"""P22-A+ diagnostic report assembly: wires preflight, diagnostics, and health checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from agent.research_v1.data_integrity import run_data_integrity_preflight, DataIntegrityReport
from agent.research_v1.factor_diagnostics import (
    compute_factor_metric,
    compute_orthogonality_results,
    compute_decay_result,
    compute_autocorrelation,
    FactorMetricResult,
    OrthogonalityResult,
    FactorDecayResult,
)
from agent.research_v1.factor_health_check import run_daily_factor_health_check, DailyFactorHealthReport


# ---------------------------------------------------------------------------
# Calibration readiness report
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CalibrationReadinessReport:
    ready_count: int
    not_ready_count: int
    ready_factor_horizons: list[tuple[str, int]]
    blocked_factor_horizons: list[tuple[str, int]]
    blocking_reasons: list[str]

    def to_dict(self) -> dict:
        return {
            "ready_count": self.ready_count,
            "not_ready_count": self.not_ready_count,
            "ready_factor_horizons": [
                {"factor": f, "horizon": h} for f, h in self.ready_factor_horizons
            ],
            "blocked_factor_horizons": [
                {"factor": f, "horizon": h} for f, h in self.blocked_factor_horizons
            ],
            "blocking_reasons": self.blocking_reasons,
        }


# ---------------------------------------------------------------------------
# P22 validity report
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class P22ValidityReport:
    schema_version: str = "p22.0"
    return_basis_default: str = "net"
    data_integrity_report: DataIntegrityReport | None = None
    factor_metrics: list[FactorMetricResult] = field(default_factory=list)
    orthogonality_results: list[OrthogonalityResult] = field(default_factory=list)
    decay_results: list[FactorDecayResult] = field(default_factory=list)
    autocorrelation_results: dict[str, dict] = field(default_factory=dict)
    calibration_readiness_report: CalibrationReadinessReport | None = None
    daily_health_report: DailyFactorHealthReport | None = None
    overall_readiness: str = "unknown"
    generated_at: str = ""

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "return_basis_default": self.return_basis_default,
            "data_integrity_report": (
                self.data_integrity_report.to_dict()
                if self.data_integrity_report else {}
            ),
            "factor_metrics": [
                {
                    "factor_name": m.factor_name,
                    "horizon_days": m.horizon_days,
                    "sample_size": m.sample_size,
                    "unique_tickers": m.unique_tickers,
                    "gross_ic": m.gross_ic,
                    "net_ic": m.net_ic,
                    "cost_impact_on_ic": m.cost_impact_on_ic,
                    "cost_fragile": m.cost_fragile,
                    "icir": m.icir,
                    "newey_west_t_stat": m.newey_west_t_stat,
                    "hac_status": m.hac_status,
                    "missing_return_rate": m.missing_return_rate,
                    "readiness_status": m.readiness_status,
                    "ready_for_shadow_calibration": m.ready_for_shadow_calibration,
                    "diagnostic_flags": m.diagnostic_flags,
                }
                for m in self.factor_metrics
            ],
            "orthogonality_results": [
                {
                    "factor_a": r.factor_a,
                    "factor_b": r.factor_b,
                    "correlation": r.correlation,
                    "highly_correlated": r.highly_correlated,
                }
                for r in self.orthogonality_results
            ],
            "decay_results": [
                {
                    "factor_name": d.factor_name,
                    "decay_classification": d.decay_classification,
                    "ic_by_horizon": d.ic_by_horizon,
                }
                for d in self.decay_results
            ],
            "autocorrelation_results": self.autocorrelation_results,
            "calibration_readiness_report": (
                self.calibration_readiness_report.to_dict()
                if self.calibration_readiness_report else {}
            ),
            "daily_health_report": (
                self.daily_health_report.__dict__
                if self.daily_health_report else {}
            ),
            "overall_readiness": self.overall_readiness,
            "generated_at": self.generated_at,
        }


# ---------------------------------------------------------------------------
# Report builder
# ---------------------------------------------------------------------------

def build_p22_a_plus_report(
    rows: list[dict],
    baseline_rows: list[dict] | None = None,
    factors: list[str] | None = None,
    horizons: list[int] | None = None,
) -> P22ValidityReport:
    """Build a full P22-A+ validity report from factor snapshot rows.

    Args:
        rows: Factor snapshot rows with forward return observations merged in.
        baseline_rows: Historical rows for drift comparison (optional).
        factors: List of factor names to diagnose (default: primary factors).
        horizons: List of horizon days to diagnose (default: [1, 5, 21, 63]).
    """
    if factors is None:
        factors = [
            "company_quality_score",
            "valuation_attractiveness_score",
            "timing_market_fit_score",
            "llm_adjustment_total",
        ]
    if horizons is None:
        horizons = [1, 5, 21, 63]
    if baseline_rows is None:
        baseline_rows = []

    # 1. Data integrity preflight
    integrity_report = run_data_integrity_preflight(rows)
    clean_rows = integrity_report.clean_rows

    # 2. Orthogonality results (needed for max cross-factor correlation)
    ortho_results = compute_orthogonality_results(clean_rows)
    max_cross_corr = (
        max(abs(r.correlation) for r in ortho_results) if ortho_results else 0.0
    )

    # 3. Factor metrics for each factor-horizon pair
    metrics: list[FactorMetricResult] = []
    for factor in factors:
        for horizon in horizons:
            result = compute_factor_metric(
                clean_rows,
                factor,
                horizon,
                lookahead_violation_rate=integrity_report.lookahead_violation_rate,
                source_audit_gap_rate=integrity_report.source_audit_gap_rate,
                max_abs_cross_factor_correlation=max_cross_corr,
            )
            metrics.append(result)

    # 4. IC decay across horizons for each factor
    decay_results: list[FactorDecayResult] = []
    for factor in factors:
        ic_by_horizon = {}
        for horizon in horizons:
            ic = compute_factor_metric(
                clean_rows,
                factor,
                horizon,
                lookahead_violation_rate=integrity_report.lookahead_violation_rate,
                source_audit_gap_rate=integrity_report.source_audit_gap_rate,
                max_abs_cross_factor_correlation=max_cross_corr,
            ).net_ic
            ic_by_horizon[horizon] = ic
        ic_1d = ic_by_horizon.get(1)
        ic_5d = ic_by_horizon.get(5)
        ic_21d = ic_by_horizon.get(21)
        ic_63d = ic_by_horizon.get(63)
        decay_results.append(compute_decay_result(factor, ic_1d, ic_5d, ic_21d, ic_63d))

    # 5. Autocorrelation per factor (using clean rows grouped by ticker)
    autocorr_results: dict[str, dict] = {}
    for factor in factors:
        tickers = {}
        for r in clean_rows:
            ticker = r.get("ticker")
            val = r.get(factor)
            if ticker and val is not None and r.get("observation_status") in (None, "computed"):
                tickers.setdefault(ticker, []).append(float(val))
        for ticker, scores in tickers.items():
            key = f"{factor}:{ticker}"
            autocorr_results[key] = compute_autocorrelation(scores)

    # 6. Calibration readiness
    ready_fh = [
        (m.factor_name, m.horizon_days)
        for m in metrics if m.ready_for_shadow_calibration
    ]
    blocked_fh = [
        (m.factor_name, m.horizon_days)
        for m in metrics if not m.ready_for_shadow_calibration
    ]
    blocking_reasons = list({
        m.readiness_status
        for m in metrics
        if not m.ready_for_shadow_calibration
    })
    readiness_report = CalibrationReadinessReport(
        ready_count=len(ready_fh),
        not_ready_count=len(blocked_fh),
        ready_factor_horizons=ready_fh,
        blocked_factor_horizons=blocked_fh,
        blocking_reasons=blocking_reasons,
    )

    # 7. Daily health check
    health_report = run_daily_factor_health_check(
        latest_rows=clean_rows,
        baseline_rows=baseline_rows,
        factors=factors,
        horizons=horizons,
    )

    # 8. Overall readiness
    if readiness_report.ready_count > 0 and health_report.overall_health_status in ("ok", "warn"):
        overall = "ready_for_shadow_calibration"
    elif readiness_report.ready_count == 0:
        overall = "not_ready"
    else:
        overall = "review_required"

    return P22ValidityReport(
        schema_version="p22.0",
        return_basis_default="net",
        data_integrity_report=integrity_report,
        factor_metrics=metrics,
        orthogonality_results=ortho_results,
        decay_results=decay_results,
        autocorrelation_results=autocorr_results,
        calibration_readiness_report=readiness_report,
        daily_health_report=health_report,
        overall_readiness=overall,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )