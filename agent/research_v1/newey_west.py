"""Dependency-free Newey-West/HAC t-stat helper."""

from __future__ import annotations

import math


def newey_west_t_stat(values: list[float], lag: int | None = None) -> dict:
    clean = [float(value) for value in values if value is not None]
    n = len(clean)
    if n < 2:
        return {"t_stat": 0.0, "sample_size": n, "lag": 0, "hac_status": "insufficient_periods"}
    mean_value = sum(clean) / n
    centered = [value - mean_value for value in clean]
    active_lag = max(0, min(int(lag if lag is not None else math.floor(math.sqrt(n))), n - 1))
    gamma0 = sum(value * value for value in centered) / n
    long_run_variance = gamma0
    for k in range(1, active_lag + 1):
        covariance = sum(centered[t] * centered[t - k] for t in range(k, n)) / n
        weight = 1.0 - (k / (active_lag + 1.0))
        long_run_variance += 2.0 * weight * covariance
    if long_run_variance <= 0:
        return {"t_stat": 0.0, "sample_size": n, "lag": active_lag, "hac_status": "zero_variance"}
    standard_error = math.sqrt(long_run_variance / n)
    return {
        "t_stat": 0.0 if standard_error == 0 else mean_value / standard_error,
        "sample_size": n,
        "lag": active_lag,
        "hac_status": "computed",
    }