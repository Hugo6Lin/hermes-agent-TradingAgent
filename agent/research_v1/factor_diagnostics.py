"""P22-A+ factor diagnostics engine: IC, ICIR, decay, orthogonality, autocorrelation."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from agent.research_v1.p22_return_selector import select_forward_return
from agent.research_v1.newey_west import newey_west_t_stat
from agent.research_v1.diagnostic_gates import evaluate_factor_readiness


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FactorMetricResult:
    factor_name: str
    horizon_days: int
    sample_size: int
    unique_tickers: int
    gross_ic: float | None
    net_ic: float | None
    cost_impact_on_ic: float | None
    cost_fragile: bool
    icir: float | None
    newey_west_t_stat: float | None
    hac_status: str | None
    missing_return_rate: float
    readiness_status: str
    ready_for_shadow_calibration: bool
    diagnostic_flags: list[str]


@dataclass(frozen=True)
class OrthogonalityResult:
    factor_a: str
    factor_b: str
    correlation: float
    highly_correlated: bool


@dataclass(frozen=True)
class FactorDecayResult:
    factor_name: str
    decay_classification: str  # short_horizon | medium_horizon | long_horizon | unstable | insufficient_data
    ic_by_horizon: dict[int, float]


# ---------------------------------------------------------------------------
# Pearson correlation (stdlib-only)
# ---------------------------------------------------------------------------

def _pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 2 or n != len(ys):
        return None
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    num = sum((xs[i] - mean_x) * (ys[i] - mean_y) for i in range(n))
    den_x = math.sqrt(sum((x - mean_x) ** 2 for x in xs))
    den_y = math.sqrt(sum((y - mean_y) ** 2 for y in ys))
    if den_x == 0 or den_y == 0:
        return None
    return num / (den_x * den_y)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_factor_value(row: dict, factor: str) -> float | None:
    """Get factor value from row, returning None for missing or non-computed observations."""
    if row.get("observation_status") not in (None, "computed"):
        return None
    val = row.get(factor)
    if val is None:
        return None
    return float(val)


def _filter_valid(rows: list[dict], factor: str) -> tuple[list[dict], float]:
    """Return (valid_rows, missing_return_rate)."""
    valid = [r for r in rows if _get_factor_value(r, factor) is not None]
    missing_rate = 1.0 - (len(valid) / len(rows)) if rows else 0.0
    return valid, missing_rate


# ---------------------------------------------------------------------------
# IC computation
# ---------------------------------------------------------------------------

def _compute_ic(rows: list[dict], factor: str, return_basis: str) -> float | None:
    """Compute IC for a factor using the specified return basis."""
    valid, _ = _filter_valid(rows, factor)
    if len(valid) < 2:
        return None
    scores = [_get_factor_value(r, factor) for r in valid]
    try:
        returns = [select_forward_return(r, return_basis=return_basis) for r in valid]
    except ValueError:
        return None
    return _pearson(scores, returns)


# ---------------------------------------------------------------------------
# ICIR (periodic IC mean / std)
# ---------------------------------------------------------------------------

def _compute_icir(periodic_ics: list[float]) -> float:
    if len(periodic_ics) < 2:
        return 0.0
    mean_ic = sum(periodic_ics) / len(periodic_ics)
    std_ic = math.sqrt(sum((ic - mean_ic) ** 2 for ic in periodic_ics) / len(periodic_ics))
    if std_ic == 0:
        return 0.0
    return mean_ic / std_ic


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_factor_metric(
    rows: list[dict],
    factor: str,
    horizon_days: int,
    lookahead_violation_rate: float = 0.0,
    source_audit_gap_rate: float = 0.0,
    max_abs_cross_factor_correlation: float = 0.0,
    min_periods_for_icir: int = 6,
) -> FactorMetricResult:
    """Compute IC, ICIR, HAC t-stat, and readiness for a factor-horizon pair.

    Readiness gates use net IC only. Gross IC is reported for comparison.
    Periodic IC is computed as cross-sectional Pearson per trading_day (requires >=2 tickers/day).
    """
    horizon_rows = [r for r in rows if r.get("horizon_days") == horizon_days]
    valid_rows, missing_return_rate = _filter_valid(horizon_rows, factor)

    sample_size = len(valid_rows)
    unique_tickers = len({r.get("ticker") for r in valid_rows if r.get("ticker")})

    gross_ic = _compute_ic(valid_rows, factor, "gross")
    net_ic = _compute_ic(valid_rows, factor, "net")

    cost_impact = None
    cost_fragile = False
    if gross_ic is not None and net_ic is not None:
        cost_impact = gross_ic - net_ic
        cost_fragile = gross_ic > 0 and net_ic is not None and net_ic < 0.03

    # Periodic IC for ICIR/HAC — cross-sectional Pearson per trading_day
    # Each trading_day contributes one IC: corr(factor_scores, net_returns) across tickers
    day_scores: dict[str, list[float]] = {}
    day_returns: dict[str, list[float]] = {}
    for r in valid_rows:
        day = r.get("trading_day", "")
        val = _get_factor_value(r, factor)
        if val is None:
            continue
        try:
            ret = select_forward_return(r, return_basis="net")
        except ValueError:
            continue
        day_scores.setdefault(day, []).append(val)
        day_returns.setdefault(day, []).append(ret)

    periodic_ics = []
    for day in day_scores:
        if len(day_scores[day]) < 2:
            continue
        ic = _pearson(day_scores[day], day_returns[day])
        if ic is not None:
            periodic_ics.append(ic)

    icir = _compute_icir(periodic_ics) if len(periodic_ics) >= 2 else None

    # HAC t-stat over periodic ICs
    nw_result = newey_west_t_stat(periodic_ics) if periodic_ics else {"t_stat": 0.0, "hac_status": "insufficient_periods"}

    readiness = evaluate_factor_readiness(
        sample_size=sample_size,
        unique_tickers=unique_tickers,
        missing_return_rate=missing_return_rate,
        lookahead_violation_rate=lookahead_violation_rate,
        source_audit_gap_rate=source_audit_gap_rate,
        net_ic=net_ic if net_ic is not None else 0.0,
        newey_west_t_stat=nw_result["t_stat"],
        max_abs_cross_factor_correlation=max_abs_cross_factor_correlation,
    )

    return FactorMetricResult(
        factor_name=factor,
        horizon_days=horizon_days,
        sample_size=sample_size,
        unique_tickers=unique_tickers,
        gross_ic=gross_ic,
        net_ic=net_ic,
        cost_impact_on_ic=cost_impact,
        cost_fragile=cost_fragile,
        icir=icir,
        newey_west_t_stat=nw_result["t_stat"],
        hac_status=nw_result["hac_status"],
        missing_return_rate=missing_return_rate,
        readiness_status=readiness["readiness_status"],
        ready_for_shadow_calibration=readiness["ready_for_shadow_calibration"],
        diagnostic_flags=readiness["diagnostic_flags"],
    )


def compute_orthogonality_results(rows: list[dict]) -> list[OrthogonalityResult]:
    """Compute cross-factor correlations and flag highly correlated pairs."""
    factors = [
        "company_quality_score",
        "valuation_attractiveness_score",
        "timing_market_fit_score",
        "llm_adjustment_total",
    ]
    # Only include rows where all factors are present and observation_status is computed
    valid_rows = [
        r for r in rows
        if r.get("observation_status") in (None, "computed")
        and all(r.get(f) is not None for f in factors)
    ]
    if len(valid_rows) < 2:
        return []

    results = []
    n = len(factors)
    for i in range(n):
        for j in range(i + 1, n):
            fa, fb = factors[i], factors[j]
            xs = [r[fa] for r in valid_rows]
            ys = [r[fb] for r in valid_rows]
            corr = _pearson(xs, ys)
            if corr is None:
                continue
            results.append(OrthogonalityResult(
                factor_a=fa,
                factor_b=fb,
                correlation=round(corr, 4),
                highly_correlated=abs(corr) > 0.70,
            ))
    return results


def compute_decay_result(
    factor_name: str,
    ic_1d: float | None,
    ic_5d: float | None,
    ic_21d: float | None,
    ic_63d: float | None,
) -> FactorDecayResult:
    """Classify IC decay pattern across horizons.

    Horizons: 1, 5, 21, 63 trading days (spec §5.2, §5.7).
    """
    ics = {1: ic_1d, 5: ic_5d, 21: ic_21d, 63: ic_63d}
    valid = {h: v for h, v in ics.items() if v is not None and abs(v) >= 0.01}
    if len(valid) < 2:
        classification = "insufficient_data"
    else:
        sorted_ics = sorted(valid.items(), key=lambda x: x[0])
        first_ic = sorted_ics[0][1]
        last_ic = sorted_ics[-1][1]
        ratio = abs(last_ic / first_ic) if first_ic != 0 else 0.0
        if ratio > 0.80:
            classification = "long_horizon"
        elif ratio > 0.50:
            classification = "medium_horizon"
        elif sorted_ics[0][0] <= 5:
            classification = "short_horizon"
        else:
            classification = "unstable"
    return FactorDecayResult(
        factor_name=factor_name,
        decay_classification=classification,
        ic_by_horizon={h: round(v, 4) if v is not None else None for h, v in ics.items()},
    )


def compute_autocorrelation(scores: list[float], lag: int = 1) -> dict:
    """Compute lag-N autocorrelation of a factor score time series."""
    if len(scores) <= lag:
        return {"lag_1_autocorrelation": None, "sample_size": len(scores)}
    series = [float(s) for s in scores if s is not None]
    lagged = series[lag:]
    current = series[:-lag]
    corr = _pearson(current, lagged)
    return {
        "lag_1_autocorrelation": round(corr, 4) if corr is not None else None,
        "sample_size": len(series),
    }