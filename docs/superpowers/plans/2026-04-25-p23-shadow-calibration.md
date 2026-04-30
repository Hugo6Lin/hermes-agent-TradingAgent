# P23 Shadow Calibration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a shadow-only calibration recommendation layer that consumes P22-A+ validity reports and emits auditable shrinkage recommendations without modifying production configuration.

**Architecture:** Add two focused P23 modules. `shadow_calibration.py` owns evidence strength, bounded shrinkage, recommendation contracts, safety blockers, and report assembly. `shadow_calibration_mappings.py` owns conservative mappings from validated factor names to shadow parameter families. Existing P20/P21/P22 modules are read-only inputs.

**Tech Stack:** Python 3.11, dataclasses, stdlib only, pytest, existing P22-A+ report payloads.

---

## Source Spec

- `docs/superpowers/specs/2026-04-25-hermes-p23-shadow-calibration-spec.md`

## Files

### Create

- `agent/research_v1/shadow_calibration_mappings.py`
- `agent/research_v1/shadow_calibration.py`
- `tests/agent/research_v1/test_p23_shadow_calibration.py`

### Modify

- None expected. P23 must not modify production config modules.

---

## Task 1: Evidence Strength and Shrinkage Helpers

**Files:**
- Create: `agent/research_v1/shadow_calibration.py`
- Test: `tests/agent/research_v1/test_p23_shadow_calibration.py`

- [ ] **Step 1: Write failing tests**

Create `tests/agent/research_v1/test_p23_shadow_calibration.py`:

```python
from agent.research_v1.shadow_calibration import (
    calculate_evidence_strength,
    calculate_delta,
    shrink_value,
)


def test_evidence_strength_uses_net_ic_hac_sample_and_missing_rate():
    strength = calculate_evidence_strength(
        net_ic=0.08,
        newey_west_t_stat=2.4,
        sample_size=180,
        missing_return_rate=0.05,
        diagnostic_flags=[],
        daily_health_status="ok",
    )
    assert 0.0 < strength <= 1.0
    assert strength > 0.50


def test_evidence_strength_penalizes_cost_fragile_and_health_critical():
    clean = calculate_evidence_strength(0.08, 2.4, 180, 0.05, [], "ok")
    penalized = calculate_evidence_strength(0.08, 2.4, 180, 0.05, ["cost_fragile"], "critical")
    assert penalized < clean


def test_delta_is_bounded_between_prior_and_data():
    assert calculate_delta(0.0) == 0.90
    assert calculate_delta(1.0) == 0.25
    assert 0.25 <= calculate_delta(0.55) <= 0.90


def test_shrink_value_keeps_prior_influence():
    value = shrink_value(prior_value=0.40, data_suggested_value=0.80, delta=0.50)
    assert value == 0.60
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p23_shadow_calibration.py -q
```

Expected: FAIL because `shadow_calibration.py` does not exist.

- [ ] **Step 3: Implement helper functions**

Create `agent/research_v1/shadow_calibration.py`:

```python
"""P23 shadow-only calibration recommendations."""

from __future__ import annotations

from dataclasses import dataclass, asdict
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
```

- [ ] **Step 4: Run helper tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p23_shadow_calibration.py -q
```

Expected: helper tests pass.

---

## Task 2: Factor-to-Parameter Mappings

**Files:**
- Create: `agent/research_v1/shadow_calibration_mappings.py`
- Test: `tests/agent/research_v1/test_p23_shadow_calibration.py`

- [ ] **Step 1: Add failing mapping tests**

Append:

```python
from agent.research_v1.shadow_calibration_mappings import map_factor_to_shadow_parameters


def test_quality_factor_maps_to_fundamentals_weight_and_ranking_hint():
    mappings = map_factor_to_shadow_parameters("company_quality_score", horizon_days=63)
    names = {(m["parameter_family"], m["parameter_name"]) for m in mappings}
    assert ("role_weight", "fundamentals") in names
    assert ("ranking_hint", "company_quality_score") in names


def test_timing_short_horizon_maps_to_exit_multiple_hint():
    mappings = map_factor_to_shadow_parameters("timing_market_fit_score", horizon_days=5)
    names = {(m["parameter_family"], m["parameter_name"]) for m in mappings}
    assert ("role_weight", "technical") in names
    assert ("exit_multiple", "timing_exit_responsiveness") in names
```

- [ ] **Step 2: Implement mappings**

Create `agent/research_v1/shadow_calibration_mappings.py`:

```python
"""Conservative factor-to-shadow-parameter mappings for P23."""

from __future__ import annotations


def map_factor_to_shadow_parameters(factor_name: str, horizon_days: int) -> list[dict]:
    mappings = [{"parameter_family": "ranking_hint", "parameter_name": factor_name}]
    if factor_name == "company_quality_score":
        mappings.append({"parameter_family": "role_weight", "parameter_name": "fundamentals"})
        if horizon_days >= 21:
            mappings.append({"parameter_family": "thesis_threshold", "parameter_name": "investable_quality_threshold"})
    elif factor_name == "valuation_attractiveness_score":
        mappings.append({"parameter_family": "role_weight", "parameter_name": "valuation"})
        if horizon_days >= 21:
            mappings.append({"parameter_family": "thesis_threshold", "parameter_name": "investable_valuation_threshold"})
    elif factor_name == "timing_market_fit_score":
        mappings.append({"parameter_family": "role_weight", "parameter_name": "technical"})
        if horizon_days <= 5:
            mappings.append({"parameter_family": "exit_multiple", "parameter_name": "timing_exit_responsiveness"})
    elif factor_name == "llm_adjustment_total":
        mappings.append({"parameter_family": "role_weight", "parameter_name": "sentiment"})
    elif factor_name == "negative_signal_strength_decile":
        mappings.append({"parameter_family": "ranking_hint", "parameter_name": "negative_signal_filter"})
    return mappings
```

- [ ] **Step 3: Run mapping tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p23_shadow_calibration.py -q
```

Expected: PASS for helper and mapping tests.

---

## Task 3: Recommendation Contracts and Generation

**Files:**
- Modify: `agent/research_v1/shadow_calibration.py`
- Test: `tests/agent/research_v1/test_p23_shadow_calibration.py`

- [ ] **Step 1: Add failing recommendation tests**

Append:

```python
from agent.research_v1.shadow_calibration import generate_shadow_recommendations


def _p22_report(metric_overrides=None, health_status="ok", return_basis="net"):
    metric = {
        "factor_name": "company_quality_score",
        "horizon_days": 63,
        "sample_size": 180,
        "unique_tickers": 40,
        "gross_ic": 0.09,
        "net_ic": 0.08,
        "icir": 0.5,
        "newey_west_t_stat": 2.4,
        "missing_return_rate": 0.05,
        "readiness_status": "ready_for_shadow_calibration",
        "ready_for_shadow_calibration": True,
        "diagnostic_flags": [],
    }
    if metric_overrides:
        metric.update(metric_overrides)
    return {
        "schema_version": "p22.0",
        "return_basis_default": return_basis,
        "data_integrity_report": {"lookahead_violation_rate": 0.0, "source_audit_gap_rate": 0.0},
        "factor_metrics": [metric],
        "daily_health_report": {"overall_health_status": health_status},
    }


def test_generate_shadow_recommendations_for_ready_factor():
    report = generate_shadow_recommendations(_p22_report())
    assert report.mode == "shadow_only"
    assert report.production_config_changes == []
    assert report.recommendations
    rec = report.recommendations[0]
    assert rec.apply_to_production is False
    assert rec.calibration_status == "shadow_only"
    assert rec.prior_value != rec.shadow_value


def test_non_ready_factor_is_blocked_not_recommended():
    report = generate_shadow_recommendations(_p22_report({
        "ready_for_shadow_calibration": False,
        "readiness_status": "weak_net_ic",
        "net_ic": 0.01,
    }))
    assert report.recommendations == []
    assert report.blocked_candidates
```

- [ ] **Step 2: Implement contracts and generator**

Append to `agent/research_v1/shadow_calibration.py`:

```python
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
        status = "blocked_by_data_integrity" if "lookahead_violations_present" in warnings else "blocked_by_health_check"
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
```

- [ ] **Step 3: Run recommendation tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p23_shadow_calibration.py -q
```

Expected: PASS.

---

## Task 4: Safety Blocking Tests

**Files:**
- Modify: `tests/agent/research_v1/test_p23_shadow_calibration.py`
- Modify: `agent/research_v1/shadow_calibration.py` only if tests fail

- [ ] **Step 1: Add safety tests**

Append:

```python

def test_gross_only_edge_is_blocked_when_net_not_ready():
    report = generate_shadow_recommendations(_p22_report({
        "gross_ic": 0.10,
        "net_ic": 0.01,
        "ready_for_shadow_calibration": False,
        "readiness_status": "weak_net_ic",
    }))
    assert report.recommendations == []
    assert report.blocked_candidates[0]["reason"] == "weak_net_ic"


def test_lookahead_warning_blocks_all_recommendations():
    payload = _p22_report()
    payload["data_integrity_report"]["lookahead_violation_rate"] = 0.01
    report = generate_shadow_recommendations(payload)
    assert report.recommendations == []
    assert "lookahead_violations_present" in report.global_warnings
    assert report.overall_status == "blocked_by_data_integrity"


def test_critical_health_blocks_all_recommendations():
    report = generate_shadow_recommendations(_p22_report(health_status="critical"))
    assert report.recommendations == []
    assert "daily_health_critical" in report.global_warnings


def test_report_never_contains_production_config_changes():
    report = generate_shadow_recommendations(_p22_report())
    payload = report.to_dict()
    assert payload["production_config_changes"] == []
    assert all(item["apply_to_production"] is False for item in payload["recommendations"])
    assert "calibrated" not in str(payload).lower()
```

- [ ] **Step 2: Run safety tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p23_shadow_calibration.py -q
```

Expected: PASS.

---

## Task 5: Final Verification

- [ ] **Step 1: Run P23 focused tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p23_shadow_calibration.py -q
```

- [ ] **Step 2: Run P20/P21/P22/P23 regression bundle**

Run:

```bash
python3.11 -m pytest \
  tests/agent/research_v1/test_p20_factor_contracts.py \
  tests/agent/research_v1/test_p20_pnl_integrity.py \
  tests/agent/research_v1/test_p21_calibration_inputs.py \
  tests/agent/research_v1/test_p22_a_plus_validity_integrity_health.py \
  tests/agent/research_v1/test_p23_shadow_calibration.py \
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
P23 Shadow Calibration Handoff

Changed files:
- <path> — <created/modified> — <purpose>

Tests run:
- <command> -> <result>
- <command> -> <result>
- <command> -> <result or known failures>

Acceptance checklist:
- consumes P22-A+ reports only: yes/no
- non-ready factors blocked: yes/no
- net IC drives recommendations: yes/no
- gross-only edge rejected: yes/no
- shrinkage formula implemented: yes/no
- delta bounded: yes/no
- production_config_changes empty: yes/no
- apply_to_production always false: yes/no
- lookahead/health blockers enforced: yes/no
- no production config changed to calibrated: yes/no
- P20/P21/P22 regression green: yes/no

Known issues:
- <none or exact issue>
```
