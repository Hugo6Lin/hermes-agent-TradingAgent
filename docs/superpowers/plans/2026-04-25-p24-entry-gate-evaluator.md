# P24 Entry Gate Evaluator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a P24 admission evaluator that produces `ModelAdmissionGateReport` for advanced model/factor candidates without training models or modifying production configuration.

**Architecture:** Add `p24_entry_gate.py` with request/evidence/report dataclasses and pure evaluation functions. The evaluator uses explicit universal gates plus candidate-family-specific gates. It is stdlib-only and must not import model libraries.

**Tech Stack:** Python 3.11, dataclasses, stdlib only, pytest.

---

## Source Spec

- `docs/superpowers/specs/2026-04-25-hermes-p24-entry-gate-evaluator-spec.md`
- `docs/superpowers/specs/2026-04-25-hermes-p24-entry-gate-spec.md`
- `docs/superpowers/specs/2026-04-25-hermes-p24-p26-advanced-quant-capability-roadmap.md`

## Files

### Create

- `agent/research_v1/p24_entry_gate.py`
- `tests/agent/research_v1/test_p24_entry_gate.py`

### Modify

- None expected.

---

## Task 1: Contracts and Universal Gate

**Files:**
- Create: `agent/research_v1/p24_entry_gate.py`
- Test: `tests/agent/research_v1/test_p24_entry_gate.py`

- [ ] **Step 1: Write failing tests**

Create `tests/agent/research_v1/test_p24_entry_gate.py`:

```python
from agent.research_v1.p24_entry_gate import (
    P24CandidateRequest,
    P24SystemEvidence,
    evaluate_p24_entry_gate,
)


def _base_request(**overrides):
    values = dict(
        candidate_name="xgb_meta_v1",
        candidate_family="xgboost_meta_model",
        candidate_namespace="shadow_meta_model.xgb_v1",
        requested_phase="P24",
        intended_outputs=["shadow_ranking_score"],
        uses_point_in_time_sources=True,
        source_audit_plan_defined=True,
        simple_baseline_defined=True,
        out_of_sample_plan_defined=True,
        uses_gross_returns_as_primary=False,
        writes_production_fields=False,
        requires_portfolio_layer=False,
        requires_execution_data=False,
        notes="test",
    )
    values.update(overrides)
    return P24CandidateRequest(**values)


def _base_evidence(**overrides):
    values = dict(
        p20_accepted=True,
        p21_accepted=True,
        p22_accepted=True,
        p23_accepted=True,
        return_basis_default="net",
        lookahead_violation_rate=0.0,
        source_audit_gap_rate=0.0,
        ready_for_p24_gate=True,
        ready_factor_count=3,
        core_factors_with_net_icir_gt_030=3,
        ready_factor_horizon_count=3,
        max_abs_cross_factor_correlation=0.50,
        independent_cross_sectional_observations=800,
        regime_gate_has_return_separation=True,
        portfolio_layer_exists=False,
        execution_dataset_exists=False,
    )
    values.update(overrides)
    return P24SystemEvidence(**values)


def test_xgboost_candidate_passes_when_all_gates_pass():
    report = evaluate_p24_entry_gate(_base_request(), _base_evidence())
    assert report.passed is True
    assert report.universal_gate_status == "pass"
    assert report.model_specific_gate_status == "pass"
    assert report.production_write_blocked is True


def test_universal_gate_blocks_without_p24_readiness():
    report = evaluate_p24_entry_gate(_base_request(), _base_evidence(ready_for_p24_gate=False))
    assert report.passed is False
    assert "ready_for_p24_gate_false" in report.blocking_reasons
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p24_entry_gate.py -q
```

Expected: FAIL because `p24_entry_gate.py` does not exist.

- [ ] **Step 3: Implement contracts and universal gate**

Create `agent/research_v1/p24_entry_gate.py`:

```python
"""P24 model/factor admission gate evaluator."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone


ALLOWED_NAMESPACES = (
    "candidate_macro.",
    "candidate_event.",
    "candidate_relation.",
    "candidate_timing_sequence.",
    "shadow_meta_model.",
    "candidate_execution.",
    "shadow_execution.",
)


@dataclass(frozen=True)
class P24CandidateRequest:
    candidate_name: str
    candidate_family: str
    candidate_namespace: str
    requested_phase: str
    intended_outputs: list[str]
    uses_point_in_time_sources: bool
    source_audit_plan_defined: bool
    simple_baseline_defined: bool
    out_of_sample_plan_defined: bool
    uses_gross_returns_as_primary: bool
    writes_production_fields: bool
    requires_portfolio_layer: bool
    requires_execution_data: bool
    notes: str = ""


@dataclass(frozen=True)
class P24SystemEvidence:
    p20_accepted: bool
    p21_accepted: bool
    p22_accepted: bool
    p23_accepted: bool
    return_basis_default: str
    lookahead_violation_rate: float
    source_audit_gap_rate: float
    ready_for_p24_gate: bool
    ready_factor_count: int
    core_factors_with_net_icir_gt_030: int
    ready_factor_horizon_count: int
    max_abs_cross_factor_correlation: float
    independent_cross_sectional_observations: int
    regime_gate_has_return_separation: bool
    portfolio_layer_exists: bool
    execution_dataset_exists: bool


@dataclass(frozen=True)
class ModelAdmissionGateReport:
    schema_version: str
    candidate_name: str
    candidate_family: str
    candidate_namespace: str
    requested_phase: str
    universal_gate_status: str
    model_specific_gate_status: str
    passed: bool
    blocking_reasons: list[str]
    warnings: list[str]
    required_evidence: dict
    available_evidence: dict
    simple_baseline_defined: bool
    point_in_time_status: str
    shadow_only_confirmed: bool
    production_write_blocked: bool
    reviewer_notes: str
    generated_at: str

    def to_dict(self) -> dict:
        return asdict(self)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _namespace_allowed(namespace: str) -> bool:
    return namespace.startswith(ALLOWED_NAMESPACES)


def _evaluate_universal_gate(request: P24CandidateRequest, evidence: P24SystemEvidence) -> list[str]:
    reasons = []
    if not evidence.p20_accepted:
        reasons.append("p20_not_accepted")
    if not evidence.p21_accepted:
        reasons.append("p21_not_accepted")
    if not evidence.p22_accepted:
        reasons.append("p22_not_accepted")
    if not evidence.p23_accepted:
        reasons.append("p23_not_accepted")
    if evidence.return_basis_default != "net":
        reasons.append("return_basis_not_net")
    if evidence.lookahead_violation_rate > 0.0:
        reasons.append("lookahead_violations_present")
    if evidence.source_audit_gap_rate > 0.20:
        reasons.append("source_audit_gap_too_high")
    if not evidence.ready_for_p24_gate:
        reasons.append("ready_for_p24_gate_false")
    if not _namespace_allowed(request.candidate_namespace):
        reasons.append("candidate_namespace_not_allowed")
    if request.writes_production_fields:
        reasons.append("writes_production_fields")
    if not request.uses_point_in_time_sources:
        reasons.append("missing_point_in_time_sources")
    if not request.source_audit_plan_defined:
        reasons.append("source_audit_plan_missing")
    if not request.simple_baseline_defined:
        reasons.append("simple_baseline_missing")
    if not request.out_of_sample_plan_defined:
        reasons.append("out_of_sample_plan_missing")
    if request.uses_gross_returns_as_primary:
        reasons.append("uses_gross_returns_as_primary")
    return reasons
```

- [ ] **Step 4: Run tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p24_entry_gate.py -q
```

Expected: still FAIL until candidate-specific gate and evaluator are implemented.

---

## Task 2: Candidate-Specific Gates

**Files:**
- Modify: `agent/research_v1/p24_entry_gate.py`
- Test: `tests/agent/research_v1/test_p24_entry_gate.py`

- [ ] **Step 1: Add failing tests**

Append:

```python

def test_xgboost_blocks_when_sample_size_too_small():
    report = evaluate_p24_entry_gate(
        _base_request(),
        _base_evidence(independent_cross_sectional_observations=200),
    )
    assert report.passed is False
    assert "xgboost_insufficient_observations" in report.blocking_reasons


def test_ppo_blocks_without_portfolio_and_execution_layers():
    request = _base_request(
        candidate_name="ppo_exec_v1",
        candidate_family="ppo_execution_model",
        candidate_namespace="shadow_execution.ppo_v1",
        requires_portfolio_layer=True,
        requires_execution_data=True,
    )
    report = evaluate_p24_entry_gate(request, _base_evidence(portfolio_layer_exists=False, execution_dataset_exists=False))
    assert report.passed is False
    assert "ppo_portfolio_layer_missing" in report.blocking_reasons
    assert "ppo_execution_dataset_missing" in report.blocking_reasons


def test_macro_candidate_passes_in_exploratory_mode_with_namespace():
    request = _base_request(
        candidate_name="macro_rates_v1",
        candidate_family="macro_regime_factor",
        candidate_namespace="candidate_macro.rates_v1",
    )
    report = evaluate_p24_entry_gate(request, _base_evidence(regime_gate_has_return_separation=False))
    assert report.passed is True
    assert "macro_exploratory_mode" in report.warnings
```

- [ ] **Step 2: Implement specific gates and evaluator**

Append to `agent/research_v1/p24_entry_gate.py`:

```python
def _evaluate_specific_gate(request: P24CandidateRequest, evidence: P24SystemEvidence) -> tuple[list[str], list[str]]:
    reasons = []
    warnings = []
    family = request.candidate_family
    namespace = request.candidate_namespace

    if family == "xgboost_meta_model":
        if not namespace.startswith("shadow_meta_model."):
            reasons.append("xgboost_namespace_invalid")
        if evidence.core_factors_with_net_icir_gt_030 < 3:
            reasons.append("xgboost_needs_three_core_factors")
        if evidence.ready_factor_horizon_count < 2:
            reasons.append("xgboost_needs_two_ready_factor_horizons")
        if evidence.max_abs_cross_factor_correlation >= 0.70:
            reasons.append("xgboost_factor_correlation_too_high")
        if evidence.independent_cross_sectional_observations < 500:
            reasons.append("xgboost_insufficient_observations")
    elif family == "llm_event_surprise_factor":
        if not namespace.startswith("candidate_event."):
            reasons.append("event_namespace_invalid")
    elif family == "macro_regime_factor":
        if not namespace.startswith("candidate_macro."):
            reasons.append("macro_namespace_invalid")
        if not evidence.regime_gate_has_return_separation:
            warnings.append("macro_exploratory_mode")
    elif family == "relation_model":
        if not namespace.startswith("candidate_relation."):
            reasons.append("relation_namespace_invalid")
        warnings.append("relation_requires_external_group_evidence")
    elif family == "sequence_timing_model":
        if not namespace.startswith("candidate_timing_sequence."):
            reasons.append("sequence_namespace_invalid")
        warnings.append("sequence_requires_timing_baseline_evidence")
    elif family == "ppo_execution_model":
        if not (namespace.startswith("candidate_execution.") or namespace.startswith("shadow_execution.")):
            reasons.append("ppo_namespace_invalid")
        if not evidence.portfolio_layer_exists:
            reasons.append("ppo_portfolio_layer_missing")
        if not evidence.execution_dataset_exists:
            reasons.append("ppo_execution_dataset_missing")
    else:
        reasons.append("unsupported_candidate_family")
    return reasons, warnings


def evaluate_p24_entry_gate(
    request: P24CandidateRequest,
    evidence: P24SystemEvidence,
) -> ModelAdmissionGateReport:
    universal_reasons = _evaluate_universal_gate(request, evidence)
    specific_reasons, warnings = _evaluate_specific_gate(request, evidence)
    blocking_reasons = universal_reasons + specific_reasons
    passed = not blocking_reasons
    return ModelAdmissionGateReport(
        schema_version="p24_gate.0",
        candidate_name=request.candidate_name,
        candidate_family=request.candidate_family,
        candidate_namespace=request.candidate_namespace,
        requested_phase=request.requested_phase,
        universal_gate_status="pass" if not universal_reasons else "fail",
        model_specific_gate_status="pass" if not specific_reasons else "fail",
        passed=passed,
        blocking_reasons=blocking_reasons,
        warnings=warnings,
        required_evidence={
            "return_basis_default": "net",
            "ready_for_p24_gate": True,
            "point_in_time_sources": True,
            "simple_baseline": True,
            "out_of_sample_plan": True,
        },
        available_evidence=evidence.__dict__,
        simple_baseline_defined=request.simple_baseline_defined,
        point_in_time_status="defined" if request.uses_point_in_time_sources else "missing",
        shadow_only_confirmed=not request.writes_production_fields,
        production_write_blocked=True,
        reviewer_notes=request.notes,
        generated_at=_utc_now(),
    )
```

- [ ] **Step 3: Run tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p24_entry_gate.py -q
```

Expected: PASS.

---

## Task 3: Safety Tests

**Files:**
- Modify: `tests/agent/research_v1/test_p24_entry_gate.py`
- Modify: `agent/research_v1/p24_entry_gate.py` only if tests fail

- [ ] **Step 1: Add safety tests**

Append:

```python

def test_blocks_production_field_writes():
    report = evaluate_p24_entry_gate(_base_request(writes_production_fields=True), _base_evidence())
    assert report.passed is False
    assert "writes_production_fields" in report.blocking_reasons
    assert report.production_write_blocked is True


def test_blocks_gross_return_primary_candidate():
    report = evaluate_p24_entry_gate(_base_request(uses_gross_returns_as_primary=True), _base_evidence())
    assert report.passed is False
    assert "uses_gross_returns_as_primary" in report.blocking_reasons


def test_blocks_missing_point_in_time_source_policy():
    report = evaluate_p24_entry_gate(_base_request(uses_point_in_time_sources=False), _base_evidence())
    assert report.passed is False
    assert "missing_point_in_time_sources" in report.blocking_reasons
```

- [ ] **Step 2: Run safety tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p24_entry_gate.py -q
```

Expected: PASS.

---

## Task 4: Final Verification

- [ ] **Step 1: Run P24 focused tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p24_entry_gate.py -q
```

- [ ] **Step 2: Run P20-P24 regression bundle**

Run:

```bash
python3.11 -m pytest \
  tests/agent/research_v1/test_p20_factor_contracts.py \
  tests/agent/research_v1/test_p20_pnl_integrity.py \
  tests/agent/research_v1/test_p21_calibration_inputs.py \
  tests/agent/research_v1/test_p22_a_plus_validity_integrity_health.py \
  tests/agent/research_v1/test_p23_shadow_calibration.py \
  tests/agent/research_v1/test_p23_shadow_observation_loop.py \
  tests/agent/research_v1/test_p24_entry_gate.py \
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
P24 Entry Gate Evaluator Handoff

Changed files:
- <path> — <created/modified> — <purpose>

Tests run:
- <command> -> <result>
- <command> -> <result>

Acceptance checklist:
- all supported candidate families evaluated: yes/no
- P23 observation readiness required: yes/no
- production field writes blocked: yes/no
- point-in-time source policy required: yes/no
- gross-return-primary candidates blocked: yes/no
- simple baseline required: yes/no
- out-of-sample plan required: yes/no
- PPO blocked without portfolio/execution layers: yes/no
- no model libraries imported: yes/no
- no production config modified: yes/no
- P20-P23 regression green: yes/no

Known issues:
- <none or exact issue>
```
