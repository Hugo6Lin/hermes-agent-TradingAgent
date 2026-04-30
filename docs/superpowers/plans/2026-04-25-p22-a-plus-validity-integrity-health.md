# P22-A+ Validity, Integrity, and Health Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a P22-A+ diagnostics layer that validates factor predictive power only after data-integrity preflight, then emits readiness and daily health reports without changing production calibration.

**Architecture:** Add focused modules under `agent/research_v1`: `data_integrity.py` for preflight checks, `newey_west.py` for HAC t-stats, `diagnostic_gates.py` for readiness gates, `factor_diagnostics.py` for IC/ICIR/decay/orthogonality/autocorrelation, `factor_health_check.py` for daily drift/completion checks, and `diagnostic_reports.py` for final report assembly. Reuse `p22_return_selector.py` so net returns remain the default.

**Tech Stack:** Python 3.11, dataclasses, math/statistics stdlib, pytest, existing P20/P21 contracts and persistence helpers.

---

## Source Spec

- `docs/superpowers/specs/2026-04-25-hermes-p22-a-plus-validity-integrity-health-spec.md`

## Files

### Create

- `agent/research_v1/data_integrity.py`
- `agent/research_v1/newey_west.py`
- `agent/research_v1/diagnostic_gates.py`
- `agent/research_v1/factor_diagnostics.py`
- `agent/research_v1/factor_health_check.py`
- `agent/research_v1/diagnostic_reports.py`
- `tests/agent/research_v1/test_p22_a_plus_validity_integrity_health.py`

### Modify

- `agent/research_v1/p22_return_selector.py` only if object-style observations need support.

---

## Task 1: Data Integrity Preflight

**Files:**
- Create: `agent/research_v1/data_integrity.py`
- Test: `tests/agent/research_v1/test_p22_a_plus_validity_integrity_health.py`

- [ ] **Step 1: Write failing tests**

Create `tests/agent/research_v1/test_p22_a_plus_validity_integrity_health.py`:

```python
from agent.research_v1.data_integrity import run_data_integrity_preflight


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
```

- [ ] **Step 2: Run failing test**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p22_a_plus_validity_integrity_health.py -q
```

Expected: FAIL because `data_integrity.py` does not exist.

- [ ] **Step 3: Implement `data_integrity.py`**

Create:

```python
"""P22-A+ data integrity preflight checks."""

from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class DataIntegrityReport:
    sample_size: int
    lookahead_violation_count: int
    lookahead_violation_rate: float
    source_audit_gap_count: int
    source_audit_gap_rate: float
    restatement_risk_count: int
    sector_snapshot_missing_count: int
    excluded_snapshot_ids: list[str]
    diagnostic_flags: list[str]
    clean_rows: list[dict]

    def to_dict(self) -> dict:
        return asdict(self)


def _date(value: str | None) -> str | None:
    if not value:
        return None
    return str(value)[:10]


def _has_lookahead(row: dict) -> bool:
    source_as_of = _date(row.get("source_as_of_date"))
    data_as_of = _date(row.get("data_as_of_date"))
    trading_day = _date(row.get("trading_day"))
    source_fetched = str(row.get("source_fetched_at") or "")
    snapshot_time = str(row.get("as_of_timestamp") or "")
    if source_as_of and data_as_of and source_as_of > data_as_of:
        return True
    if data_as_of and trading_day and data_as_of > trading_day:
        return True
    if source_fetched and snapshot_time and source_fetched > snapshot_time:
        return True
    return False


def _has_source_audit_gap(row: dict) -> bool:
    return not (
        row.get("source_refs")
        and row.get("source_as_of_date")
        and row.get("source_fetched_at")
        and row.get("provider")
    )


def _has_sector_snapshot_gap(row: dict) -> bool:
    return not (row.get("sector_id") and row.get("classification_as_of_date"))


def _has_restatement_risk(row: dict) -> bool:
    return bool(row.get("restatement_flag") or row.get("possible_restatement_risk"))


def run_data_integrity_preflight(rows: list[dict]) -> DataIntegrityReport:
    sample_size = len(rows)
    excluded = []
    clean_rows = []
    source_gaps = 0
    sector_gaps = 0
    restatement_risks = 0

    for row in rows:
        snapshot_id = str(row.get("snapshot_id", ""))
        lookahead = _has_lookahead(row)
        if _has_source_audit_gap(row):
            source_gaps += 1
        if _has_sector_snapshot_gap(row):
            sector_gaps += 1
        if _has_restatement_risk(row):
            restatement_risks += 1
        if lookahead:
            excluded.append(snapshot_id)
        else:
            clean_rows.append(row)

    flags = []
    if excluded:
        flags.append("lookahead_violation")
    if source_gaps:
        flags.append("source_audit_gap")
    if sector_gaps:
        flags.append("sector_snapshot_missing")
    if restatement_risks:
        flags.append("restatement_risk")

    return DataIntegrityReport(
        sample_size=sample_size,
        lookahead_violation_count=len(excluded),
        lookahead_violation_rate=0.0 if sample_size == 0 else len(excluded) / sample_size,
        source_audit_gap_count=source_gaps,
        source_audit_gap_rate=0.0 if sample_size == 0 else source_gaps / sample_size,
        restatement_risk_count=restatement_risks,
        sector_snapshot_missing_count=sector_gaps,
        excluded_snapshot_ids=excluded,
        diagnostic_flags=flags,
        clean_rows=clean_rows,
    )
```

- [ ] **Step 4: Run tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p22_a_plus_validity_integrity_health.py -q
```

Expected: preflight tests pass.

---

## Task 2: Newey-West and Readiness Gates

**Files:**
- Create: `agent/research_v1/newey_west.py`
- Create: `agent/research_v1/diagnostic_gates.py`
- Test: `tests/agent/research_v1/test_p22_a_plus_validity_integrity_health.py`

- [ ] **Step 1: Add failing tests**

Append:

```python
from agent.research_v1.newey_west import newey_west_t_stat
from agent.research_v1.diagnostic_gates import DiagnosticGateConfig, evaluate_factor_readiness


def test_newey_west_positive_series_is_positive():
    result = newey_west_t_stat([0.05, 0.04, 0.06, 0.03, 0.05, 0.07])
    assert result["t_stat"] > 0
    assert result["hac_status"] == "computed"


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
```

- [ ] **Step 2: Implement helpers**

Create `agent/research_v1/newey_west.py`:

```python
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
```

Create `agent/research_v1/diagnostic_gates.py`:

```python
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
```

- [ ] **Step 3: Run tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p22_a_plus_validity_integrity_health.py -q
```

Expected: PASS for preflight/gate tests.

---

## Task 3: Factor Diagnostics

**Files:**
- Create: `agent/research_v1/factor_diagnostics.py`
- Test: `tests/agent/research_v1/test_p22_a_plus_validity_integrity_health.py`

- [ ] **Step 1: Add failing diagnostics tests**

Append:

```python
from agent.research_v1.factor_diagnostics import compute_factor_metric, compute_orthogonality_results


def _rows(n=80, factor="company_quality_score", negative=False):
    rows = []
    for i in range(n):
        score = i / (n - 1)
        net_return = -score * 0.10 if negative else score * 0.10
        rows.append({
            "snapshot_id": f"snap_{i}",
            "ticker": f"T{i % 20}",
            "trading_day": f"2026-01-{(i % 20) + 1:02d}",
            "horizon_days": 21,
            factor: score,
            "gross_return_pct": net_return + 0.005,
            "net_return_pct": net_return,
            "observation_status": "computed",
        })
    return rows


def test_compute_factor_metric_uses_net_return_and_passes_ready_case():
    result = compute_factor_metric(_rows(), "company_quality_score", 21)
    assert result.sample_size == 80
    assert result.net_ic > 0.95
    assert result.gross_ic > 0.95
    assert result.ready_for_shadow_calibration is True


def test_compute_factor_metric_blocks_small_sample():
    result = compute_factor_metric(_rows(n=20), "company_quality_score", 21)
    assert result.ready_for_shadow_calibration is False
    assert result.readiness_status == "insufficient_sample"


def test_orthogonality_flags_high_correlation():
    rows = [{"company_quality_score": i, "valuation_attractiveness_score": i * 0.99, "timing_market_fit_score": 100 - i, "llm_adjustment_total": 0.0} for i in range(80)]
    results = compute_orthogonality_results(rows)
    pair = next(r for r in results if r.factor_a == "company_quality_score" and r.factor_b == "valuation_attractiveness_score")
    assert pair.highly_correlated is True
```

- [ ] **Step 2: Implement diagnostics**

Create `agent/research_v1/factor_diagnostics.py` with dataclasses and helpers for:

- `FactorMetricResult`
- `OrthogonalityResult`
- `FactorDecayResult`
- `P22ValidityReport`
- `compute_factor_metric()`
- `compute_orthogonality_results()`
- `compute_decay_result()`
- `compute_autocorrelation()`

Implementation must:

- use `select_forward_return(row, return_basis="net")` for primary IC
- compute gross IC only for comparison
- call `newey_west_t_stat()` over periodic IC
- call `evaluate_factor_readiness()`
- exclude rows whose `observation_status` is not `None` or `"computed"`

- [ ] **Step 3: Run tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p22_a_plus_validity_integrity_health.py -q
```

Expected: diagnostics tests pass.

---

## Task 4: Daily Factor Health Check

**Files:**
- Create: `agent/research_v1/factor_health_check.py`
- Test: `tests/agent/research_v1/test_p22_a_plus_validity_integrity_health.py`

- [ ] **Step 1: Add failing health tests**

Append:

```python
from agent.research_v1.factor_health_check import run_daily_factor_health_check


def test_health_check_flags_factor_distribution_drift():
    baseline = [{"company_quality_score": 0.50 + i * 0.001, "classification": "Watchlist", "horizon_days": 21, "observation_status": "computed"} for i in range(100)]
    latest = [{"company_quality_score": 0.95, "classification": "Investable", "horizon_days": 21, "observation_status": "computed"} for _ in range(20)]
    report = run_daily_factor_health_check(latest, baseline, factors=["company_quality_score"], horizons=[21])
    assert report.overall_health_status == "warn"
    assert report.factor_distribution_alerts


def test_health_check_flags_forward_return_completion_gap():
    latest = [{"company_quality_score": 0.5, "classification": "Watchlist", "horizon_days": 21, "observation_status": "missing_horizon"} for _ in range(10)]
    report = run_daily_factor_health_check(latest, [], factors=["company_quality_score"], horizons=[21])
    assert report.forward_return_completion_alerts
```

- [ ] **Step 2: Implement health check**

Create `agent/research_v1/factor_health_check.py` with:

- `DailyFactorHealthReport`
- `run_daily_factor_health_check(latest_rows, baseline_rows, factors, horizons)`

The implementation must compute factor mean drift, classification rate drift where possible, and forward-return completion gaps.

- [ ] **Step 3: Run tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p22_a_plus_validity_integrity_health.py -q
```

Expected: health tests pass.

---

## Task 5: Final Report Assembly

**Files:**
- Create: `agent/research_v1/diagnostic_reports.py`
- Modify: `agent/research_v1/p22_return_selector.py` only if object observations need support
- Test: `tests/agent/research_v1/test_p22_a_plus_validity_integrity_health.py`

- [ ] **Step 1: Add failing report tests**

Append:

```python
from agent.research_v1.diagnostic_reports import build_p22_a_plus_report


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
```

- [ ] **Step 2: Implement report assembly**

Create `agent/research_v1/diagnostic_reports.py` with `build_p22_a_plus_report()` that:

- runs `run_data_integrity_preflight()`
- passes only clean rows into factor diagnostics
- builds factor metrics, orthogonality, decay, autocorrelation
- runs `run_daily_factor_health_check()`
- returns a `P22ValidityReport`

- [ ] **Step 3: Run tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p22_a_plus_validity_integrity_health.py -q
```

Expected: all P22-A+ focused tests pass.

---

## Task 6: Final Verification

- [ ] **Step 1: Run P22-A+ focused tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p22_a_plus_validity_integrity_health.py -q
```

- [ ] **Step 2: Run P20/P21/P22 regression bundle**

Run:

```bash
python3.11 -m pytest \
  tests/agent/research_v1/test_p20_factor_contracts.py \
  tests/agent/research_v1/test_p20_pnl_integrity.py \
  tests/agent/research_v1/test_p21_calibration_inputs.py \
  tests/agent/research_v1/test_p22_a_plus_validity_integrity_health.py \
  tests/agent/research_v1/test_backtest.py \
  tests/agent/research_v1/test_final_judge.py \
  tests/agent/research_v1/test_thesis_engine.py \
  tests/agent/research_v1/test_review_grade_monitor.py \
  tests/agent/research_v1/test_p4_valuation_risk.py \
  -q
```

- [ ] **Step 3: Run full research suite**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1 -q
```

If unrelated infrastructure failures appear, report exact failures and keep the focused regression bundle green.

- [ ] **Step 4: Handoff report**

Return:

```text
P22-A+ Validity, Integrity, and Health Handoff

Changed files:
- <path> — <created/modified> — <purpose>

Tests run:
- <command> -> <result>
- <command> -> <result>
- <command> -> <result or known failures>

Acceptance checklist:
- lookahead rows excluded by default: yes/no
- source audit gaps visible: yes/no
- sector snapshot gaps visible: yes/no
- net return default: yes/no
- gross vs net IC comparison: yes/no
- IC/ICIR/decay/HAC implemented: yes/no
- orthogonality implemented: yes/no
- autocorrelation implemented: yes/no
- daily factor health check implemented: yes/no
- forward-return completion gaps detected: yes/no
- no production config changed to calibrated: yes/no
- P20/P21 regression green: yes/no

Known issues:
- <none or exact issue>
```
