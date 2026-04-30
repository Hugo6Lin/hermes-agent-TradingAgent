"""P22-A+ daily factor health check: drift detection and completion gaps."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DailyFactorHealthReport:
    factor_distribution_alerts: list[str]
    gate_rate_alerts: list[str]
    forward_return_completion_alerts: list[str]
    overall_health_status: str  # "ok" | "warn" | "critical"
    diagnostic_flags: list[str]


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _std(values: list[float]) -> float:
    m = _mean(values)
    variance = sum((v - m) ** 2 for v in values) / len(values) if values else 0.0
    return math.sqrt(variance)


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    idx = (p / 100.0) * (len(sorted_vals) - 1)
    lower = int(math.floor(idx))
    upper = int(math.ceil(idx))
    if lower == upper:
        return sorted_vals[lower]
    frac = idx - lower
    return sorted_vals[lower] * (1 - frac) + sorted_vals[upper] * frac


def _factor_drift_detected(
    latest_values: list[float],
    baseline_values: list[float],
    factor_name: str,
    z_threshold: float = 3.0,
) -> bool:
    """Detect factor distribution drift via z-score vs baseline."""
    if len(baseline_values) < 10 or len(latest_values) < 3:
        return False
    baseline_mean = _mean(baseline_values)
    baseline_std = _std(baseline_values)
    if baseline_std == 0:
        return False
    latest_mean = _mean(latest_values)
    z_score = abs(latest_mean - baseline_mean) / baseline_std
    return z_score > z_threshold


def _compute_completion_gap(rows: list[dict], horizon: int) -> dict[str, Any]:
    """Compute forward-return completion metrics for a given horizon."""
    horizon_rows = [r for r in rows if r.get("horizon_days") == horizon]
    total = len(horizon_rows)
    if total == 0:
        return {
            "horizon_days": horizon,
            "expected_observations": 0,
            "computed_observations": 0,
            "missing_observations": 0,
            "completion_rate": 0.0,
            "missing_return_rate": 1.0,
        }
    computed = sum(1 for r in horizon_rows if r.get("observation_status") == "computed")
    missing = total - computed
    return {
        "horizon_days": horizon,
        "expected_observations": total,
        "computed_observations": computed,
        "missing_observations": missing,
        "completion_rate": computed / total if total > 0 else 0.0,
        "missing_return_rate": missing / total if total > 0 else 0.0,
    }


def run_daily_factor_health_check(
    latest_rows: list[dict],
    baseline_rows: list[dict],
    factors: list[str],
    horizons: list[int],
) -> DailyFactorHealthReport:
    """Run daily health checks on factor distributions, gate rates, and return completion."""
    factor_alerts = []
    gate_alerts = []
    completion_alerts = []

    # Factor distribution drift
    for factor in factors:
        latest_vals = [r[factor] for r in latest_rows if r.get(factor) is not None]
        baseline_vals = [r[factor] for r in baseline_rows if r.get(factor) is not None]
        if _factor_drift_detected(latest_vals, baseline_vals, factor):
            factor_alerts.append(f"factor_distribution_drift:{factor}")

    # Forward-return completion gaps
    for horizon in horizons:
        gap = _compute_completion_gap(latest_rows, horizon)
        if gap["missing_return_rate"] > 0.20:
            completion_alerts.append(
                f"forward_return_completion_gap:horizon_{horizon}d_missing_{gap['missing_observations']}"
            )

    # Classification gate rate drift (optional, detect major shifts)
    if baseline_rows and latest_rows:
        baseline_classes = [r.get("classification", "unknown") for r in baseline_rows]
        latest_classes = [r.get("classification", "unknown") for r in latest_rows]
        for cls in set(baseline_classes + latest_classes):
            b_rate = baseline_classes.count(cls) / len(baseline_classes) if baseline_classes else 0.0
            l_rate = latest_classes.count(cls) / len(latest_classes) if latest_classes else 0.0
            if abs(l_rate - b_rate) > 0.15:
                gate_alerts.append(f"gate_pass_rate_drift:{cls}")

    all_alerts = factor_alerts + gate_alerts + completion_alerts
    if all_alerts:
        overall = "critical" if len(all_alerts) > 3 else "warn"
    else:
        overall = "ok"

    return DailyFactorHealthReport(
        factor_distribution_alerts=factor_alerts,
        gate_rate_alerts=gate_alerts,
        forward_return_completion_alerts=completion_alerts,
        overall_health_status=overall,
        diagnostic_flags=all_alerts,
    )