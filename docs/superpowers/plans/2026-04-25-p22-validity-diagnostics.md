# P22 Validity Diagnostics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a validity-first diagnostics layer that evaluates Hermes factor predictive power using point-in-time factor snapshots and cost-aware forward returns, without modifying production calibration parameters.

**Architecture:** Add small, focused diagnostics modules under `agent/research_v1`. `factor_diagnostics.py` assembles rows and computes IC/ICIR/decay/orthogonality/autocorrelation, `diagnostic_gates.py` owns readiness gates, and `newey_west.py` owns dependency-free HAC t-stat calculations. Existing `p22_return_selector.py` remains the single source for choosing net versus gross returns.

**Tech Stack:** Python 3.11, dataclasses, math/statistics stdlib, pytest, existing P20/P21 contracts and persistence helpers.

---

## Source Spec

Primary spec:

- `docs/superpowers/specs/2026-04-25-hermes-p22-validity-diagnostics-spec.md`

Prior specs:

- `docs/superpowers/specs/2026-04-24-hermes-p20-p22-factor-calibration-roadmap-spec.md`
- `docs/superpowers/specs/2026-04-24-hermes-p21-calibration-inputs-spec.md`

## File Structure

### Create

- `agent/research_v1/newey_west.py`
  - Dependency-free HAC/Newey-West t-stat helper for periodic IC series.
- `agent/research_v1/diagnostic_gates.py`
  - Readiness threshold config and gate evaluation.
- `agent/research_v1/factor_diagnostics.py`
  - P22 contracts and diagnostic calculations.
- `tests/agent/research_v1/test_p22_validity_diagnostics.py`
  - Focused P22 acceptance tests.

### Modify

- `agent/research_v1/p22_return_selector.py`
  - Only if needed to support dataclass/object observations in addition to dicts.

---

### Task 1: Newey-West HAC Helper

**Files:**
- Create: `agent/research_v1/newey_west.py`
- Test: `tests/agent/research_v1/test_p22_validity_diagnostics.py`

- [ ] **Step 1: Write failing tests**

Create `tests/agent/research_v1/test_p22_validity_diagnostics.py` with:

```python
import math

from agent.research_v1.newey_west import newey_west_t_stat


def test_newey_west_t_stat_positive_series_is_positive():
    values = [0.05, 0.04, 0.06, 0.03, 0.05, 0.07, 0.04, 0.06]
    result = newey_west_t_stat(values)
    assert result["t_stat"] > 0
    assert result["sample_size"] == 8
    assert result["hac_status"] == "computed"


def test_newey_west_t_stat_insufficient_series_blocks_readiness():
    result = newey_west_t_stat([0.05])
    assert result["t_stat"] == 0.0
    assert result["hac_status"] == "insufficient_periods"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p22_validity_diagnostics.py -q
```

Expected: FAIL because `agent.research_v1.newey_west` does not exist.

- [ ] **Step 3: Implement `newey_west.py`**

Create `agent/research_v1/newey_west.py`:

```python
"""Dependency-free Newey-West/HAC t-stat helper for P22 diagnostics."""

from __future__ import annotations

import math


def newey_west_t_stat(values: list[float], lag: int | None = None) -> dict:
    clean = [float(value) for value in values if value is not None]
    n = len(clean)
    if n < 2:
        return {"t_stat": 0.0, "sample_size": n, "lag": 0, "hac_status": "insufficient_periods"}

    mean_value = sum(clean) / n
    centered = [value - mean_value for value in clean]
    active_lag = int(lag if lag is not None else math.floor(math.sqrt(n)))
    active_lag = max(0, min(active_lag, n - 1))

    gamma0 = sum(value * value for value in centered) / n
    long_run_variance = gamma0
    for k in range(1, active_lag + 1):
        covariance = sum(centered[t] * centered[t - k] for t in range(k, n)) / n
        weight = 1.0 - (k / (active_lag + 1.0))
        long_run_variance += 2.0 * weight * covariance

    if long_run_variance <= 0:
        return {"t_stat": 0.0, "sample_size": n, "lag": active_lag, "hac_status": "zero_variance"}

    standard_error = math.sqrt(long_run_variance / n)
    if standard_error == 0:
        return {"t_stat": 0.0, "sample_size": n, "lag": active_lag, "hac_status": "zero_variance"}

    return {
        "t_stat": mean_value / standard_error,
        "sample_size": n,
        "lag": active_lag,
        "hac_status": "computed",
    }
```

- [ ] **Step 4: Run targeted tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p22_validity_diagnostics.py -q
```

Expected: PASS for the Newey-West tests.

---

### Task 2: Diagnostic Gates

**Files:**
- Create: `agent/research_v1/diagnostic_gates.py`
- Test: `tests/agent/research_v1/test_p22_validity_diagnostics.py`

- [ ] **Step 1: Add failing gate tests**

Append to `tests/agent/research_v1/test_p22_validity_diagnostics.py`:

```python
from agent.research_v1.diagnostic_gates import DiagnosticGateConfig, evaluate_factor_readiness


def test_readiness_rejects_insufficient_sample():
    result = evaluate_factor_readiness(
        sample_size=20,
        unique_tickers=10,
        missing_return_rate=0.0,
        net_ic=0.10,
        newey_west_t_stat=3.0,
        max_abs_cross_factor_correlation=0.20,
        config=DiagnosticGateConfig(min_observations=60),
    )
    assert result["ready_for_shadow_calibration"] is False
    assert result["readiness_status"] == "insufficient_sample"


def test_readiness_rejects_gross_only_edge_when_net_ic_weak():
    result = evaluate_factor_readiness(
        sample_size=100,
        unique_tickers=20,
        missing_return_rate=0.0,
        net_ic=0.01,
        newey_west_t_stat=3.0,
        max_abs_cross_factor_correlation=0.20,
    )
    assert result["ready_for_shadow_calibration"] is False
    assert result["readiness_status"] == "weak_net_ic"


def test_readiness_allows_shadow_calibration_when_all_gates_pass():
    result = evaluate_factor_readiness(
        sample_size=120,
        unique_tickers=30,
        missing_return_rate=0.05,
        net_ic=0.08,
        newey_west_t_stat=2.0,
        max_abs_cross_factor_correlation=0.20,
    )
    assert result["ready_for_shadow_calibration"] is True
    assert result["readiness_status"] == "ready_for_shadow_calibration"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p22_validity_diagnostics.py -q
```

Expected: FAIL because `diagnostic_gates.py` does not exist.

- [ ] **Step 3: Implement `diagnostic_gates.py`**

Create `agent/research_v1/diagnostic_gates.py`:

```python
"""P22 diagnostic readiness gates."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DiagnosticGateConfig:
    min_observations: int = 60
    min_unique_tickers: int = 10
    min_periods_for_icir: int = 6
    max_missing_return_rate: float = 0.20
    min_abs_net_ic_for_watch: float = 0.03
    min_abs_net_ic_for_ready: float = 0.05
    max_abs_factor_correlation: float = 0.70
    min_newey_west_t_stat_for_ready: float = 1.50


def evaluate_factor_readiness(
    sample_size: int,
    unique_tickers: int,
    missing_return_rate: float,
    net_ic: float,
    newey_west_t_stat: float,
    max_abs_cross_factor_correlation: float,
    config: DiagnosticGateConfig | None = None,
) -> dict:
    active_config = config or DiagnosticGateConfig()
    flags = []

    if sample_size < active_config.min_observations or unique_tickers < active_config.min_unique_tickers:
        return {
            "readiness_status": "insufficient_sample",
            "ready_for_shadow_calibration": False,
            "diagnostic_flags": ["insufficient_sample"],
        }
    if missing_return_rate > active_config.max_missing_return_rate:
        return {
            "readiness_status": "missing_returns_too_high",
            "ready_for_shadow_calibration": False,
            "diagnostic_flags": ["missing_returns_too_high"],
        }
    if abs(net_ic) < active_config.min_abs_net_ic_for_ready:
        return {
            "readiness_status": "weak_net_ic",
            "ready_for_shadow_calibration": False,
            "diagnostic_flags": ["weak_net_ic"],
        }
    if abs(newey_west_t_stat) < active_config.min_newey_west_t_stat_for_ready:
        return {
            "readiness_status": "hac_tstat_too_low",
            "ready_for_shadow_calibration": False,
            "diagnostic_flags": ["hac_tstat_too_low"],
        }
    if abs(max_abs_cross_factor_correlation) > active_config.max_abs_factor_correlation:
        flags.append("orthogonality_warning")

    return {
        "readiness_status": "ready_for_shadow_calibration",
        "ready_for_shadow_calibration": True,
        "diagnostic_flags": flags,
    }
```

- [ ] **Step 4: Run gate tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p22_validity_diagnostics.py -q
```

Expected: PASS for Newey-West and gate tests.

---

### Task 3: Factor Diagnostics Contracts and IC Calculations

**Files:**
- Create: `agent/research_v1/factor_diagnostics.py`
- Test: `tests/agent/research_v1/test_p22_validity_diagnostics.py`

- [ ] **Step 1: Add failing IC tests**

Append:

```python
from agent.research_v1.factor_diagnostics import (
    compute_factor_metric,
    compute_orthogonality_results,
)


def _diagnostic_rows(n=80, factor_name="company_quality_score", negative=False):
    rows = []
    for i in range(n):
        score = i / (n - 1)
        net_return = score * 0.10 if not negative else -score * 0.10
        rows.append({
            "snapshot_id": f"snap_{i}",
            "ticker": f"T{i % 20}",
            "trading_day": f"2026-01-{(i % 28) + 1:02d}",
            "horizon_days": 21,
            factor_name: score,
            "gross_return_pct": net_return + 0.005,
            "net_return_pct": net_return,
            "observation_status": "computed",
        })
    return rows


def test_compute_factor_metric_positive_net_ic():
    result = compute_factor_metric(
        rows=_diagnostic_rows(),
        factor_name="company_quality_score",
        horizon_days=21,
    )
    assert result.factor_name == "company_quality_score"
    assert result.horizon_days == 21
    assert result.sample_size == 80
    assert result.net_ic > 0.95
    assert result.gross_ic > 0.95
    assert result.ready_for_shadow_calibration is True


def test_compute_factor_metric_negative_net_ic():
    result = compute_factor_metric(
        rows=_diagnostic_rows(negative=True),
        factor_name="company_quality_score",
        horizon_days=21,
    )
    assert result.net_ic < -0.95
    assert result.ready_for_shadow_calibration is True


def test_compute_factor_metric_insufficient_sample_blocks_readiness():
    result = compute_factor_metric(
        rows=_diagnostic_rows(n=20),
        factor_name="company_quality_score",
        horizon_days=21,
    )
    assert result.ready_for_shadow_calibration is False
    assert result.readiness_status == "insufficient_sample"


def test_compute_orthogonality_flags_high_correlation():
    rows = []
    for i in range(80):
        score = i / 79
        rows.append({
            "company_quality_score": score,
            "valuation_attractiveness_score": score * 0.99,
            "timing_market_fit_score": 1.0 - score,
            "llm_adjustment_total": 0.0,
        })
    results = compute_orthogonality_results(rows)
    pair = next(r for r in results if r.factor_a == "company_quality_score" and r.factor_b == "valuation_attractiveness_score")
    assert pair.highly_correlated is True
    assert pair.correlation > 0.95
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p22_validity_diagnostics.py -q
```

Expected: FAIL because `factor_diagnostics.py` does not exist.

- [ ] **Step 3: Implement `factor_diagnostics.py` core contracts and helpers**

Create `agent/research_v1/factor_diagnostics.py`:

```python
"""P22 validity-first factor diagnostics."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import math
import statistics

from agent.research_v1.diagnostic_gates import DiagnosticGateConfig, evaluate_factor_readiness
from agent.research_v1.newey_west import newey_west_t_stat
from agent.research_v1.p22_return_selector import select_forward_return

PRIMARY_FACTORS = [
    "company_quality_score",
    "valuation_attractiveness_score",
    "timing_market_fit_score",
    "llm_adjustment_total",
    "negative_signal_strength_decile",
]


@dataclass(frozen=True)
class FactorMetricResult:
    factor_name: str
    horizon_days: int
    sample_size: int
    unique_tickers: int
    gross_ic: float
    net_ic: float
    cost_impact_on_ic: float
    icir: float
    newey_west_t_stat: float
    missing_return_rate: float
    readiness_status: str
    ready_for_shadow_calibration: bool
    diagnostic_flags: list[str]


@dataclass(frozen=True)
class OrthogonalityResult:
    factor_a: str
    factor_b: str
    correlation: float
    sample_size: int
    highly_correlated: bool


@dataclass(frozen=True)
class FactorDecayResult:
    factor_name: str
    ic_by_horizon: dict[int, float]
    best_horizon_days: int | None
    decay_profile: str


@dataclass(frozen=True)
class P22ValidityReport:
    schema_version: str
    return_basis_default: str
    factor_metrics: list[FactorMetricResult]
    orthogonality_results: list[OrthogonalityResult]
    decay_results: list[FactorDecayResult]
    sample_gate_summary: dict
    overall_readiness: bool
    generated_at: str

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "return_basis_default": self.return_basis_default,
            "factor_metrics": [asdict(item) for item in self.factor_metrics],
            "orthogonality_results": [asdict(item) for item in self.orthogonality_results],
            "decay_results": [asdict(item) for item in self.decay_results],
            "sample_gate_summary": self.sample_gate_summary,
            "overall_readiness": self.overall_readiness,
            "generated_at": self.generated_at,
        }


def _correlation(xs: list[float], ys: list[float]) -> float:
    if len(xs) < 2 or len(xs) != len(ys):
        return 0.0
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    denom = math.sqrt(var_x * var_y)
    return cov / denom if denom else 0.0


def _periodic_ic_series(rows: list[dict], factor_name: str, return_basis: str) -> list[float]:
    by_day: dict[str, list[dict]] = {}
    for row in rows:
        by_day.setdefault(str(row.get("trading_day", "unknown")), []).append(row)
    series = []
    for day_rows in by_day.values():
        if len(day_rows) < 2:
            continue
        xs = [float(row[factor_name]) for row in day_rows if row.get(factor_name) is not None]
        ys = [select_forward_return(row, return_basis=return_basis) for row in day_rows if row.get(factor_name) is not None]
        if len(xs) == len(ys) and len(xs) >= 2:
            series.append(_correlation(xs, ys))
    return series


def compute_factor_metric(
    rows: list[dict],
    factor_name: str,
    horizon_days: int,
    gate_config: DiagnosticGateConfig | None = None,
) -> FactorMetricResult:
    expected_rows = [row for row in rows if row.get("horizon_days") == horizon_days]
    computed_rows = [
        row for row in expected_rows
        if row.get("observation_status") in (None, "computed")
        and row.get(factor_name) is not None
        and row.get("net_return_pct") is not None
    ]
    missing_return_rate = 0.0 if not expected_rows else 1.0 - (len(computed_rows) / len(expected_rows))

    factor_values = [float(row[factor_name]) for row in computed_rows]
    net_returns = [select_forward_return(row, return_basis="net") for row in computed_rows]
    gross_returns = [select_forward_return(row, return_basis="gross") for row in computed_rows]

    net_ic = _correlation(factor_values, net_returns)
    gross_ic = _correlation(factor_values, gross_returns)
    periodic_net_ic = _periodic_ic_series(computed_rows, factor_name, "net")
    icir = 0.0
    if len(periodic_net_ic) >= 2:
        stdev = statistics.pstdev(periodic_net_ic)
        icir = (sum(periodic_net_ic) / len(periodic_net_ic)) / stdev if stdev else 0.0
    hac = newey_west_t_stat(periodic_net_ic)

    unique_tickers = len({row.get("ticker") for row in computed_rows})
    readiness = evaluate_factor_readiness(
        sample_size=len(computed_rows),
        unique_tickers=unique_tickers,
        missing_return_rate=missing_return_rate,
        net_ic=net_ic,
        newey_west_t_stat=hac["t_stat"],
        max_abs_cross_factor_correlation=0.0,
        config=gate_config,
    )
    flags = list(readiness["diagnostic_flags"])
    if gross_ic > 0 and net_ic <= 0:
        flags.append("cost_fragile")

    return FactorMetricResult(
        factor_name=factor_name,
        horizon_days=horizon_days,
        sample_size=len(computed_rows),
        unique_tickers=unique_tickers,
        gross_ic=round(gross_ic, 10),
        net_ic=round(net_ic, 10),
        cost_impact_on_ic=round(gross_ic - net_ic, 10),
        icir=round(icir, 10),
        newey_west_t_stat=round(hac["t_stat"], 10),
        missing_return_rate=round(missing_return_rate, 10),
        readiness_status=readiness["readiness_status"],
        ready_for_shadow_calibration=readiness["ready_for_shadow_calibration"],
        diagnostic_flags=flags,
    )


def compute_orthogonality_results(rows: list[dict], factors: list[str] | None = None, threshold: float = 0.70) -> list[OrthogonalityResult]:
    active_factors = factors or [
        "company_quality_score",
        "valuation_attractiveness_score",
        "timing_market_fit_score",
        "llm_adjustment_total",
    ]
    results = []
    for i, factor_a in enumerate(active_factors):
        for factor_b in active_factors[i + 1:]:
            aligned = [row for row in rows if row.get(factor_a) is not None and row.get(factor_b) is not None]
            xs = [float(row[factor_a]) for row in aligned]
            ys = [float(row[factor_b]) for row in aligned]
            corr = _correlation(xs, ys)
            results.append(OrthogonalityResult(
                factor_a=factor_a,
                factor_b=factor_b,
                correlation=round(corr, 10),
                sample_size=len(aligned),
                highly_correlated=abs(corr) > threshold,
            ))
    return results
```

- [ ] **Step 4: Run IC tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p22_validity_diagnostics.py -q
```

Expected: tests pass or expose readiness/HAC issues to fix in the next task.

---

### Task 4: Decay, Autocorrelation, and Report Assembly

**Files:**
- Modify: `agent/research_v1/factor_diagnostics.py`
- Test: `tests/agent/research_v1/test_p22_validity_diagnostics.py`

- [ ] **Step 1: Add failing report tests**

Append:

```python
from agent.research_v1.factor_diagnostics import (
    compute_autocorrelation,
    compute_decay_result,
    build_validity_report,
)


def test_compute_decay_result_identifies_best_horizon():
    metrics = [
        compute_factor_metric(_diagnostic_rows(), "company_quality_score", 21),
        compute_factor_metric([dict(row, horizon_days=63) for row in _diagnostic_rows()], "company_quality_score", 63),
    ]
    result = compute_decay_result("company_quality_score", metrics)
    assert result.factor_name == "company_quality_score"
    assert result.best_horizon_days in {21, 63}
    assert result.decay_profile in {"medium_horizon", "long_horizon"}


def test_compute_autocorrelation_by_ticker():
    rows = []
    for ticker in ["A", "B", "C"]:
        for day in range(10):
            rows.append({"ticker": ticker, "trading_day": f"2026-01-{day+1:02d}", "company_quality_score": day / 10})
    result = compute_autocorrelation(rows, "company_quality_score")
    assert result["factor_name"] == "company_quality_score"
    assert result["sample_size"] > 0
    assert result["lag_1_autocorrelation"] > 0.9


def test_build_validity_report_defaults_to_net_and_does_not_calibrate():
    rows = _diagnostic_rows()
    report = build_validity_report(rows, factors=["company_quality_score"], horizons=[21])
    payload = report.to_dict()
    assert payload["schema_version"] == "p22.0"
    assert payload["return_basis_default"] == "net"
    assert "calibrated" not in str(payload).lower()
    assert len(payload["factor_metrics"]) == 1
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p22_validity_diagnostics.py -q
```

Expected: FAIL because report helpers do not exist.

- [ ] **Step 3: Implement decay/autocorrelation/report helpers**

Append to `agent/research_v1/factor_diagnostics.py`:

```python

def compute_decay_result(factor_name: str, metrics: list[FactorMetricResult]) -> FactorDecayResult:
    factor_metrics = [metric for metric in metrics if metric.factor_name == factor_name]
    if not factor_metrics:
        return FactorDecayResult(factor_name=factor_name, ic_by_horizon={}, best_horizon_days=None, decay_profile="insufficient_data")
    ic_by_horizon = {metric.horizon_days: metric.net_ic for metric in factor_metrics}
    best_horizon = max(ic_by_horizon, key=lambda horizon: abs(ic_by_horizon[horizon]))
    if len(ic_by_horizon) < 2:
        profile = "insufficient_data"
    elif best_horizon <= 5:
        profile = "short_horizon"
    elif best_horizon <= 21:
        profile = "medium_horizon"
    elif best_horizon >= 63:
        profile = "long_horizon"
    else:
        profile = "unstable"
    return FactorDecayResult(
        factor_name=factor_name,
        ic_by_horizon=ic_by_horizon,
        best_horizon_days=best_horizon,
        decay_profile=profile,
    )


def compute_autocorrelation(rows: list[dict], factor_name: str) -> dict:
    pairs_x = []
    pairs_y = []
    by_ticker: dict[str, list[dict]] = {}
    for row in rows:
        if row.get(factor_name) is not None:
            by_ticker.setdefault(str(row.get("ticker")), []).append(row)
    for ticker_rows in by_ticker.values():
        ordered = sorted(ticker_rows, key=lambda row: str(row.get("trading_day")))
        for previous, current in zip(ordered, ordered[1:]):
            pairs_x.append(float(previous[factor_name]))
            pairs_y.append(float(current[factor_name]))
    return {
        "factor_name": factor_name,
        "lag_1_autocorrelation": round(_correlation(pairs_x, pairs_y), 10),
        "sample_size": len(pairs_x),
    }


def build_validity_report(
    rows: list[dict],
    factors: list[str] | None = None,
    horizons: list[int] | None = None,
    gate_config: DiagnosticGateConfig | None = None,
) -> P22ValidityReport:
    active_factors = factors or PRIMARY_FACTORS
    active_horizons = horizons or [1, 5, 21, 63]
    factor_metrics = []
    for factor in active_factors:
        for horizon in active_horizons:
            factor_metrics.append(compute_factor_metric(rows, factor, horizon, gate_config=gate_config))
    orthogonality_results = compute_orthogonality_results(rows, factors=[f for f in active_factors if f != "negative_signal_strength_decile"])
    decay_results = [compute_decay_result(factor, factor_metrics) for factor in active_factors]
    ready_count = sum(1 for metric in factor_metrics if metric.ready_for_shadow_calibration)
    sample_gate_summary = {
        "factor_metric_count": len(factor_metrics),
        "ready_for_shadow_calibration_count": ready_count,
        "autocorrelation": [compute_autocorrelation(rows, factor) for factor in active_factors],
    }
    return P22ValidityReport(
        schema_version="p22.0",
        return_basis_default="net",
        factor_metrics=factor_metrics,
        orthogonality_results=orthogonality_results,
        decay_results=decay_results,
        sample_gate_summary=sample_gate_summary,
        overall_readiness=ready_count > 0,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
```

- [ ] **Step 4: Run P22 tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p22_validity_diagnostics.py -q
```

Expected: PASS.

---

### Task 5: Return Selector Object Support and Regression Bundle

**Files:**
- Modify: `agent/research_v1/p22_return_selector.py` only if needed
- Test: `tests/agent/research_v1/test_p22_validity_diagnostics.py`

- [ ] **Step 1: Add object observation test**

Append:

```python
from dataclasses import dataclass
from agent.research_v1.p22_return_selector import select_forward_return


@dataclass
class ObservationObject:
    gross_return_pct: float
    net_return_pct: float
    return_value: float


def test_return_selector_supports_objects_and_defaults_to_net():
    obs = ObservationObject(gross_return_pct=0.10, net_return_pct=0.08, return_value=0.10)
    assert select_forward_return(obs) == 0.08
    assert select_forward_return(obs, return_basis="gross") == 0.10
```

- [ ] **Step 2: Run selector test to verify failure if unsupported**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p22_validity_diagnostics.py::test_return_selector_supports_objects_and_defaults_to_net -q
```

Expected: FAIL if selector only supports dicts.

- [ ] **Step 3: Patch selector if needed**

Modify `agent/research_v1/p22_return_selector.py`:

```python
def _get(observation, field: str):
    if isinstance(observation, dict):
        return observation.get(field)
    return getattr(observation, field, None)
```

Then replace direct dict access checks with `_get()`:

```python
net_value = _get(observation, "net_return_pct")
```

Apply the same for `gross_return_pct` and `return_value`.

- [ ] **Step 4: Run full P22 tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p22_validity_diagnostics.py -q
```

Expected: PASS.

---

### Task 6: Final Verification

**Files:**
- Test only unless failures require focused fixes.

- [ ] **Step 1: Run P22 focused tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p22_validity_diagnostics.py -q
```

Expected: all P22 tests pass.

- [ ] **Step 2: Run P20/P21/P22 regression bundle**

Run:

```bash
python3.11 -m pytest \
  tests/agent/research_v1/test_p20_factor_contracts.py \
  tests/agent/research_v1/test_p20_pnl_integrity.py \
  tests/agent/research_v1/test_p21_calibration_inputs.py \
  tests/agent/research_v1/test_p22_validity_diagnostics.py \
  tests/agent/research_v1/test_backtest.py \
  tests/agent/research_v1/test_final_judge.py \
  tests/agent/research_v1/test_thesis_engine.py \
  tests/agent/research_v1/test_review_grade_monitor.py \
  tests/agent/research_v1/test_p4_valuation_risk.py \
  -q
```

Expected: all selected tests pass.

- [ ] **Step 3: Run full research suite**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1 -q
```

Expected: all tests pass or exact unrelated pre-existing failures are reported.

- [ ] **Step 4: Handoff report**

Return:

```text
P22 Validity Diagnostics Handoff

Changed files:
- <path> — <created/modified> — <purpose>

Tests run:
- <command> -> <result>
- <command> -> <result>
- <command> -> <result or exact known failures>

Acceptance checklist:
- consumes FactorSnapshot/ForwardReturnObservation rows only: yes/no
- net return default: yes/no
- gross vs net IC comparison: yes/no
- IC/ICIR/decay implemented: yes/no
- orthogonality implemented: yes/no
- autocorrelation implemented: yes/no
- sample gates block small samples: yes/no
- Newey-West/HAC implemented or explicitly blocks readiness: yes/no
- no production configs modified to calibrated: yes/no
- P20/P21 regression green: yes/no

Known issues:
- <none or exact issue>
```
