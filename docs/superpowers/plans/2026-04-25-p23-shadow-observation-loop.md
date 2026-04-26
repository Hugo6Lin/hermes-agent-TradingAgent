# P23 Shadow Observation Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist and monitor P23 shadow calibration recommendations over time, comparing shadow behavior against prior-only references without applying recommendations to production.

**Architecture:** Add `shadow_observation.py` as a focused module with observation contracts, conversion from `ShadowCalibrationReport`, evaluation helpers, revocation rules, and monitor report assembly. Keep persistence serialization-ready but avoid database migration unless explicitly requested.

**Tech Stack:** Python 3.11, dataclasses, stdlib only, pytest, existing `shadow_calibration.py` report contracts.

---

## Source Spec

- `docs/superpowers/specs/2026-04-25-hermes-p23-shadow-observation-loop-spec.md`

## Files

### Create

- `agent/research_v1/shadow_observation.py`
- `tests/agent/research_v1/test_p23_shadow_observation_loop.py`

### Modify

- None expected.

---

## Task 1: Observation Contracts and Conversion

**Files:**
- Create: `agent/research_v1/shadow_observation.py`
- Test: `tests/agent/research_v1/test_p23_shadow_observation_loop.py`

- [ ] **Step 1: Write failing tests**

Create `tests/agent/research_v1/test_p23_shadow_observation_loop.py`:

```python
from agent.research_v1.shadow_observation import (
    ShadowRecommendationObservation,
    observations_from_shadow_report,
)


def _shadow_report_payload():
    return {
        "schema_version": "p23.0",
        "mode": "shadow_only",
        "generated_at": "2026-04-25T00:00:00Z",
        "source_report_schema_version": "p22.0",
        "recommendations": [{
            "parameter_family": "role_weight",
            "parameter_name": "fundamentals",
            "factor_name": "company_quality_score",
            "horizon_days": 63,
            "prior_value": 0.40,
            "data_suggested_value": 0.48,
            "shadow_value": 0.44,
            "delta": 0.50,
            "evidence_strength": 0.50,
            "sample_size": 180,
            "net_ic": 0.08,
            "newey_west_t_stat": 2.4,
            "readiness_status": "ready_for_shadow_calibration",
            "calibration_status": "shadow_only",
            "apply_to_production": False,
            "diagnostic_flags": [],
            "human_reason": "test",
        }],
        "blocked_candidates": [],
        "global_warnings": [],
        "production_config_changes": [],
        "overall_status": "shadow_recommendations_available",
    }


def test_observations_from_shadow_report_preserve_source_ids():
    observations = observations_from_shadow_report(
        _shadow_report_payload(),
        source_p22_report_id="p22_report_001",
        source_p23_report_id="p23_report_001",
    )
    assert len(observations) == 1
    obs = observations[0]
    assert obs.source_p22_report_id == "p22_report_001"
    assert obs.source_p23_report_id == "p23_report_001"
    assert obs.observation_status == "active"
    assert obs.apply_to_production is False
```

- [ ] **Step 2: Run failing test**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p23_shadow_observation_loop.py -q
```

Expected: FAIL because `shadow_observation.py` does not exist.

- [ ] **Step 3: Implement contracts and conversion**

Create `agent/research_v1/shadow_observation.py`:

```python
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
```

- [ ] **Step 4: Run tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p23_shadow_observation_loop.py -q
```

Expected: observation conversion test passes.

---

## Task 2: Evaluation and Revocation Rules

**Files:**
- Modify: `agent/research_v1/shadow_observation.py`
- Test: `tests/agent/research_v1/test_p23_shadow_observation_loop.py`

- [ ] **Step 1: Add failing evaluation tests**

Append:

```python
from agent.research_v1.shadow_observation import evaluate_shadow_observation


def _observation():
    return observations_from_shadow_report(
        _shadow_report_payload(),
        source_p22_report_id="p22_report_001",
        source_p23_report_id="p23_report_001",
    )[0]


def test_evaluation_marks_shadow_outperformance():
    evaluation = evaluate_shadow_observation(
        _observation(),
        latest_net_ic=0.09,
        latest_newey_west_t_stat=2.2,
        latest_evidence_strength=0.60,
        prior_metric=0.02,
        shadow_metric=0.04,
        health_status="ok",
        reversal_count=0,
        consecutive_underperformance=0,
        source_blocker_active=False,
    )
    assert evaluation.shadow_outperformed_prior is True
    assert evaluation.revocation_triggered is False


def test_evaluation_revokes_on_weak_net_ic():
    evaluation = evaluate_shadow_observation(
        _observation(),
        latest_net_ic=0.01,
        latest_newey_west_t_stat=2.2,
        latest_evidence_strength=0.40,
        prior_metric=0.03,
        shadow_metric=0.02,
        health_status="ok",
        reversal_count=0,
        consecutive_underperformance=0,
        source_blocker_active=False,
    )
    assert evaluation.revocation_triggered is True
    assert "latest_net_ic_below_floor" in evaluation.diagnostic_flags
```

- [ ] **Step 2: Implement evaluation**

Append to `agent/research_v1/shadow_observation.py`:

```python
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
```

- [ ] **Step 3: Run tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p23_shadow_observation_loop.py -q
```

Expected: evaluation tests pass.

---

## Task 3: Status Update and Monitor Report

**Files:**
- Modify: `agent/research_v1/shadow_observation.py`
- Test: `tests/agent/research_v1/test_p23_shadow_observation_loop.py`

- [ ] **Step 1: Add failing monitor tests**

Append:

```python
from agent.research_v1.shadow_observation import (
    update_observation_status,
    build_shadow_monitor_report,
)


def test_update_observation_status_revoked_is_retained():
    obs = _observation()
    evaluation = evaluate_shadow_observation(
        obs,
        latest_net_ic=0.01,
        latest_newey_west_t_stat=0.8,
        latest_evidence_strength=0.20,
        prior_metric=0.03,
        shadow_metric=0.02,
        health_status="ok",
        reversal_count=0,
        consecutive_underperformance=0,
        source_blocker_active=False,
    )
    updated = update_observation_status(obs, [evaluation], min_windows_for_p24=2)
    assert updated.observation_status == "revoked"
    assert updated.recommendation_id == obs.recommendation_id


def test_monitor_report_requires_observation_windows_for_p24_gate():
    obs = _observation()
    evaluation = evaluate_shadow_observation(
        obs,
        latest_net_ic=0.09,
        latest_newey_west_t_stat=2.0,
        latest_evidence_strength=0.65,
        prior_metric=0.02,
        shadow_metric=0.04,
        health_status="ok",
        reversal_count=0,
        consecutive_underperformance=0,
        source_blocker_active=False,
    )
    report = build_shadow_monitor_report([obs], [evaluation], min_windows_for_p24=2)
    assert report.ready_for_p24_gate is False
    assert report.active_recommendation_count == 1
```

- [ ] **Step 2: Implement status and report**

Append:

```python
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
```

- [ ] **Step 3: Run monitor tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p23_shadow_observation_loop.py -q
```

Expected: monitor tests pass.

---

## Task 4: P24 Eligibility Path

**Files:**
- Modify: `tests/agent/research_v1/test_p23_shadow_observation_loop.py`
- Modify: `agent/research_v1/shadow_observation.py` only if tests fail

- [ ] **Step 1: Add P24 eligibility test**

Append:

```python

def test_monitor_report_marks_ready_for_p24_after_enough_positive_windows():
    obs = _observation()
    evaluations = [
        evaluate_shadow_observation(
            obs,
            latest_net_ic=0.09,
            latest_newey_west_t_stat=2.0,
            latest_evidence_strength=0.65,
            prior_metric=0.02,
            shadow_metric=0.04,
            health_status="ok",
            reversal_count=0,
            consecutive_underperformance=0,
            source_blocker_active=False,
            evaluation_window=f"week_{i}",
        )
        for i in range(4)
    ]
    report = build_shadow_monitor_report([obs], evaluations, min_windows_for_p24=4)
    assert report.ready_for_p24_gate is True
    assert report.eligible_for_p24_count == 1
```

- [ ] **Step 2: Run all P23 observation tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p23_shadow_observation_loop.py -q
```

Expected: PASS.

---

## Task 5: Final Verification

- [ ] **Step 1: Run P23 observation focused tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p23_shadow_observation_loop.py -q
```

- [ ] **Step 2: Run P20-P23 regression bundle**

Run:

```bash
python3.11 -m pytest \
  tests/agent/research_v1/test_p20_factor_contracts.py \
  tests/agent/research_v1/test_p20_pnl_integrity.py \
  tests/agent/research_v1/test_p21_calibration_inputs.py \
  tests/agent/research_v1/test_p22_a_plus_validity_integrity_health.py \
  tests/agent/research_v1/test_p23_shadow_calibration.py \
  tests/agent/research_v1/test_p23_shadow_observation_loop.py \
  tests/agent/research_v1/test_backtest.py \
  tests/agent/research_v1/test_final_judge.py \
  tests/agent/research_v1/test_thesis_engine.py \
  tests/agent/research_v1/test_review_grade_monitor.py \
  tests/agent/research_v1/test_p4_valuation_risk.py \
  -q
```

- [ ] **Step 3: Handoff report**

Return:

```text
P23 Shadow Observation Loop Handoff

Changed files:
- <path> — <created/modified> — <purpose>

Tests run:
- <command> -> <result>
- <command> -> <result>

Acceptance checklist:
- shadow recommendations converted to observations: yes/no
- source P22/P23 IDs preserved: yes/no
- shadow vs prior evaluation implemented: yes/no
- revocation triggers implemented: yes/no
- revoked recommendations retained: yes/no
- monitor report summarizes states: yes/no
- P24 gate requires enough observation windows: yes/no
- no production config modified: yes/no
- P20-P23 regression green: yes/no

Known issues:
- <none or exact issue>
```
