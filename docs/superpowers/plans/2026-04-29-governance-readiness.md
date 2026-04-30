# Governance Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a governance readiness workflow that turns the existing P20-P30 scaffold into version-level, signal-family-level, and daily governance review artifacts.

**Architecture:** Add three focused stdlib-only modules under `agent/research_v1/`: `version_readiness.py`, `signal_family_readiness.py`, and `daily_governance.py`. Each module uses frozen dataclasses, pure gate functions, deterministic `to_dict()` serialization, and no production config writes.

**Tech Stack:** Python 3.11, dataclasses, pathlib, json, pytest, existing Hermes P29/P30 governance contracts.

---

## File Structure

- Create `agent/research_v1/version_readiness.py`
  - Owns version-level contracts, required evidence phase gates, test evidence gates, risk-control gates, and `build_version_readiness_dossier()`.
- Create `tests/agent/research_v1/test_version_readiness.py`
  - Tests missing evidence, failed tests, missing controls, freeze warnings, defensive serialization, and P29-compatible evidence mapping.
- Create `agent/research_v1/signal_family_readiness.py`
  - Owns signal-family contracts and `build_signal_family_readiness_dossier()`.
- Create `tests/agent/research_v1/test_signal_family_readiness.py`
  - Tests blocked parent version, missing family evidence, shadow-only status, human-review status, and promotion boundaries.
- Create `agent/research_v1/daily_governance.py`
  - Owns daily run orchestration and JSON/Markdown file output.
- Create `tests/agent/research_v1/test_daily_governance.py`
  - Tests output files, summary statuses, degraded mode, zero family candidates, and no production config mutation.

No existing runtime path should be modified in this plan. CLI wiring is intentionally left out of the first implementation slice.

---

### Task 1: Version Readiness Contracts And Evidence Gates

**Files:**
- Create: `agent/research_v1/version_readiness.py`
- Test: `tests/agent/research_v1/test_version_readiness.py`

- [ ] **Step 1: Write failing contract tests**

Create `tests/agent/research_v1/test_version_readiness.py` with:

```python
"""Tests for Hermes version readiness governance dossier."""

from __future__ import annotations

import json

import pytest

from agent.research_v1.phase29_production_adoption_review import (
    MonitoringSLA,
    RollbackPlan,
    VersionFreezeProposal,
)
from agent.research_v1.version_readiness import (
    REQUIRED_VERSION_PHASE_IDS,
    EvidenceItem,
    TestEvidence,
    VersionMetadata,
    VersionReadinessDossier,
    VersionReadinessError,
    VersionReadinessRequest,
    build_version_readiness_dossier,
)


def _metadata() -> VersionMetadata:
    return VersionMetadata(
        branch="codex/quant-governance-p20-p30",
        commit="c3abd67",
        dirty=False,
        frozen_version_label="hermes-governance-p30",
    )


def _passing_tests() -> TestEvidence:
    return TestEvidence(
        command="/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_phase30_advanced_model_pack.py -q",
        status="passed",
        passed_count=55,
        failed_count=0,
        raw_summary="55 passed in 0.10s",
    )


def _evidence_bundle() -> tuple[EvidenceItem, ...]:
    return tuple(
        EvidenceItem(phase_id=phase_id, present=True, summary=f"{phase_id} evidence present")
        for phase_id in REQUIRED_VERSION_PHASE_IDS
    )


def _rollback_plan() -> RollbackPlan:
    return RollbackPlan(
        rollback_owner="risk-owner",
        rollback_trigger="governance blocker or production regression",
        description="Freeze adoption and return to prior reviewed version.",
    )


def _monitoring_sla() -> MonitoringSLA:
    return MonitoringSLA(
        monitoring_cadence="daily governance run",
        alert_routing="operator-review",
        description="Review blockers, degradation, and newly ready candidates daily.",
    )


def _version_freeze() -> VersionFreezeProposal:
    return VersionFreezeProposal(
        frozen_version="hermes-governance-p30",
        freeze_scope="P20-P30 governance contracts and tests",
        thaw_conditions="new human-approved governance spec",
    )


def _request(
    *,
    evidence: tuple[EvidenceItem, ...] | None = None,
    tests: tuple[TestEvidence, ...] | None = None,
    rollback_plan: RollbackPlan | None = None,
    monitoring_sla: MonitoringSLA | None = None,
    version_freeze: VersionFreezeProposal | None = None,
) -> VersionReadinessRequest:
    return VersionReadinessRequest(
        metadata=_metadata(),
        evidence_items=evidence if evidence is not None else _evidence_bundle(),
        test_evidence=tests if tests is not None else (_passing_tests(),),
        rollback_plan=rollback_plan if rollback_plan is not None else _rollback_plan(),
        monitoring_sla=monitoring_sla if monitoring_sla is not None else _monitoring_sla(),
        version_freeze_proposal=version_freeze,
    )


class TestVersionReadinessContracts:
    def test_metadata_contract(self):
        d = _metadata().to_dict()
        assert d["branch"] == "codex/quant-governance-p20-p30"
        assert d["commit"] == "c3abd67"
        assert d["dirty"] is False

    def test_test_evidence_contract(self):
        d = _passing_tests().to_dict()
        assert d["status"] == "passed"
        assert d["failed_count"] == 0

    def test_evidence_item_contract(self):
        item = EvidenceItem(phase_id="P20", present=True, summary="factor snapshots present")
        assert item.to_dict() == {
            "phase_id": "P20",
            "present": True,
            "summary": "factor snapshots present",
            "details": {},
        }

    def test_dossier_json_round_trip(self):
        dossier = build_version_readiness_dossier(_request(version_freeze=_version_freeze()))
        parsed = json.loads(json.dumps(dossier.to_dict()))
        assert parsed["status"] == "ready_for_human_review"
        assert parsed["metadata"]["branch"] == "codex/quant-governance-p20-p30"

    def test_invalid_test_status_rejected(self):
        with pytest.raises(VersionReadinessError, match="status must be one of"):
            TestEvidence(command="pytest", status="unknown", passed_count=0, failed_count=0, raw_summary="")


class TestVersionReadinessGates:
    def test_missing_phase_evidence_blocks(self):
        evidence = tuple(
            item for item in _evidence_bundle()
            if item.phase_id != "P25"
        )
        dossier = build_version_readiness_dossier(_request(evidence=evidence))
        assert dossier.status == "blocked_missing_evidence"
        assert "missing_phase_evidence:P25" in dossier.decision_reasons

    def test_failed_test_blocks(self):
        tests = (
            TestEvidence(
                command="pytest failing-suite",
                status="failed",
                passed_count=10,
                failed_count=1,
                raw_summary="1 failed, 10 passed",
            ),
        )
        dossier = build_version_readiness_dossier(_request(tests=tests))
        assert dossier.status == "blocked_test_failures"
        assert "test_failures:pytest failing-suite" in dossier.decision_reasons

    def test_missing_rollback_plan_blocks_controls(self):
        dossier = build_version_readiness_dossier(
            VersionReadinessRequest(
                metadata=_metadata(),
                evidence_items=_evidence_bundle(),
                test_evidence=(_passing_tests(),),
                rollback_plan=None,
                monitoring_sla=_monitoring_sla(),
                version_freeze_proposal=_version_freeze(),
            )
        )
        assert dossier.status == "blocked_risk_controls_incomplete"
        assert "missing_risk_controls:rollback_plan" in dossier.decision_reasons

    def test_missing_monitoring_sla_blocks_controls(self):
        dossier = build_version_readiness_dossier(
            VersionReadinessRequest(
                metadata=_metadata(),
                evidence_items=_evidence_bundle(),
                test_evidence=(_passing_tests(),),
                rollback_plan=_rollback_plan(),
                monitoring_sla=None,
                version_freeze_proposal=_version_freeze(),
            )
        )
        assert dossier.status == "blocked_risk_controls_incomplete"
        assert "missing_risk_controls:monitoring_sla" in dossier.decision_reasons

    def test_missing_version_freeze_warns_but_does_not_block(self):
        dossier = build_version_readiness_dossier(_request(version_freeze=None))
        assert dossier.status == "ready_for_human_review"
        assert "version_freeze_proposal_not_provided" in dossier.warnings

    def test_complete_request_ready_for_human_review(self):
        dossier = build_version_readiness_dossier(_request(version_freeze=_version_freeze()))
        assert dossier.status == "ready_for_human_review"
        assert "all_gates_passed_awaiting_human_signoff" in dossier.decision_reasons

    def test_to_dict_rebuilds_status_from_gate_fields(self):
        dossier = build_version_readiness_dossier(_request(version_freeze=_version_freeze()))
        object.__setattr__(dossier, "status", "blocked_missing_evidence")
        assert dossier.to_dict()["status"] == "ready_for_human_review"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_version_readiness.py -q
```

Expected: import failure for `agent.research_v1.version_readiness`.

- [ ] **Step 3: Implement version readiness module**

Create `agent/research_v1/version_readiness.py` with:

```python
"""Version-level governance readiness dossier for Hermes P20-P30 evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agent.research_v1.phase29_production_adoption_review import (
    MonitoringSLA,
    RollbackPlan,
    VersionFreezeProposal,
)


class VersionReadinessError(ValueError):
    """Raised for unsafe or invalid version readiness inputs."""


REQUIRED_VERSION_PHASE_IDS: tuple[str, ...] = (
    "P20",
    "P21",
    "P22",
    "P23",
    "P24",
    "P25",
    "P26",
    "P28",
    "P29",
    "P30",
)

ALLOWED_TEST_STATUSES: frozenset[str] = frozenset({"passed", "failed", "not_run"})
ALLOWED_VERSION_STATUSES: frozenset[str] = frozenset({
    "blocked_missing_evidence",
    "blocked_test_failures",
    "blocked_risk_controls_incomplete",
    "ready_for_human_review",
})


@dataclass(frozen=True)
class VersionMetadata:
    branch: str
    commit: str
    dirty: bool
    frozen_version_label: str = ""

    def __post_init__(self) -> None:
        if not self.branch.strip():
            raise VersionReadinessError("branch must be non-empty")
        if not self.commit.strip():
            raise VersionReadinessError("commit must be non-empty")

    def to_dict(self) -> dict[str, Any]:
        return {
            "branch": self.branch,
            "commit": self.commit,
            "dirty": self.dirty,
            "frozen_version_label": self.frozen_version_label,
        }


@dataclass(frozen=True)
class EvidenceItem:
    phase_id: str
    present: bool
    summary: str
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.phase_id.strip():
            raise VersionReadinessError("phase_id must be non-empty")

    def to_dict(self) -> dict[str, Any]:
        return {
            "phase_id": self.phase_id,
            "present": self.present,
            "summary": self.summary,
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class TestEvidence:
    command: str
    status: str
    passed_count: int
    failed_count: int
    raw_summary: str

    def __post_init__(self) -> None:
        if not self.command.strip():
            raise VersionReadinessError("command must be non-empty")
        if self.status not in ALLOWED_TEST_STATUSES:
            raise VersionReadinessError(
                f"status must be one of {sorted(ALLOWED_TEST_STATUSES)}, got {self.status!r}"
            )
        if self.passed_count < 0:
            raise VersionReadinessError("passed_count must be >= 0")
        if self.failed_count < 0:
            raise VersionReadinessError("failed_count must be >= 0")

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "status": self.status,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "raw_summary": self.raw_summary,
        }


@dataclass(frozen=True)
class VersionReadinessRequest:
    metadata: VersionMetadata
    evidence_items: tuple[EvidenceItem, ...]
    test_evidence: tuple[TestEvidence, ...]
    rollback_plan: RollbackPlan | None
    monitoring_sla: MonitoringSLA | None
    version_freeze_proposal: VersionFreezeProposal | None = None
    notes: str = ""


@dataclass(frozen=True)
class VersionReadinessDossier:
    status: str
    metadata: VersionMetadata
    evidence_matrix: tuple[EvidenceItem, ...]
    test_summary: tuple[TestEvidence, ...]
    rollback_plan: RollbackPlan | None
    monitoring_sla: MonitoringSLA | None
    version_freeze_candidate: VersionFreezeProposal | None
    human_review_questions: tuple[str, ...]
    next_actions: tuple[str, ...]
    decision_reasons: tuple[str, ...]
    warnings: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.status not in ALLOWED_VERSION_STATUSES:
            raise VersionReadinessError(
                f"status must be one of {sorted(ALLOWED_VERSION_STATUSES)}, got {self.status!r}"
            )

    def to_dict(self) -> dict[str, Any]:
        evidence_missing = [
            item.phase_id for item in self.evidence_matrix
            if item.phase_id in REQUIRED_VERSION_PHASE_IDS and not item.present
        ]
        failed_tests = [
            item.command for item in self.test_summary
            if item.status == "failed" or item.failed_count > 0
        ]
        controls_complete = self.rollback_plan is not None and self.monitoring_sla is not None

        if evidence_missing:
            rebuilt_status = "blocked_missing_evidence"
        elif failed_tests:
            rebuilt_status = "blocked_test_failures"
        elif not controls_complete:
            rebuilt_status = "blocked_risk_controls_incomplete"
        else:
            rebuilt_status = "ready_for_human_review"

        return {
            "status": rebuilt_status,
            "metadata": self.metadata.to_dict(),
            "evidence_matrix": [item.to_dict() for item in self.evidence_matrix],
            "test_summary": [item.to_dict() for item in self.test_summary],
            "risk_control_summary": {
                "rollback_plan": self.rollback_plan.to_dict() if self.rollback_plan else None,
                "monitoring_sla": self.monitoring_sla.to_dict() if self.monitoring_sla else None,
            },
            "version_freeze_candidate": (
                self.version_freeze_candidate.to_dict()
                if self.version_freeze_candidate
                else None
            ),
            "human_review_questions": list(self.human_review_questions),
            "next_actions": list(self.next_actions),
            "decision_reasons": list(self.decision_reasons),
            "warnings": list(self.warnings),
        }


def _normalize_evidence(items: tuple[EvidenceItem, ...]) -> tuple[EvidenceItem, ...]:
    by_phase = {item.phase_id: item for item in items}
    normalized: list[EvidenceItem] = []
    for phase_id in REQUIRED_VERSION_PHASE_IDS:
        normalized.append(
            by_phase.get(
                phase_id,
                EvidenceItem(
                    phase_id=phase_id,
                    present=False,
                    summary=f"{phase_id} evidence missing",
                ),
            )
        )
    for item in items:
        if item.phase_id not in REQUIRED_VERSION_PHASE_IDS:
            normalized.append(item)
    return tuple(normalized)


def build_version_readiness_dossier(
    request: VersionReadinessRequest,
) -> VersionReadinessDossier:
    evidence_matrix = _normalize_evidence(request.evidence_items)
    missing_phase_ids = [
        item.phase_id for item in evidence_matrix
        if item.phase_id in REQUIRED_VERSION_PHASE_IDS and not item.present
    ]
    failed_tests = [
        item.command for item in request.test_evidence
        if item.status == "failed" or item.failed_count > 0
    ]

    decision_reasons: list[str] = []
    warnings: list[str] = []
    next_actions: list[str] = []
    human_review_questions: list[str] = []

    if missing_phase_ids:
        decision_reasons.append(f"missing_phase_evidence:{','.join(missing_phase_ids)}")
        next_actions.append("collect_missing_phase_evidence")

    if failed_tests:
        for command in failed_tests:
            decision_reasons.append(f"test_failures:{command}")
        next_actions.append("fix_or_explain_failed_tests")

    missing_controls: list[str] = []
    if request.rollback_plan is None:
        missing_controls.append("rollback_plan")
    if request.monitoring_sla is None:
        missing_controls.append("monitoring_sla")
    if missing_controls:
        decision_reasons.append(f"missing_risk_controls:{','.join(missing_controls)}")
        next_actions.append("complete_risk_controls")

    if request.version_freeze_proposal is None:
        warnings.append("version_freeze_proposal_not_provided")
        human_review_questions.append("Should this commit be frozen for review?")

    if missing_phase_ids:
        status = "blocked_missing_evidence"
    elif failed_tests:
        status = "blocked_test_failures"
    elif missing_controls:
        status = "blocked_risk_controls_incomplete"
    else:
        status = "ready_for_human_review"
        decision_reasons.append("all_gates_passed_awaiting_human_signoff")
        next_actions.append("prepare_human_review")

    if request.metadata.dirty:
        warnings.append("working_tree_dirty")
        human_review_questions.append("Should dirty local changes be included in the reviewed version?")

    return VersionReadinessDossier(
        status=status,
        metadata=request.metadata,
        evidence_matrix=evidence_matrix,
        test_summary=request.test_evidence,
        rollback_plan=request.rollback_plan,
        monitoring_sla=request.monitoring_sla,
        version_freeze_candidate=request.version_freeze_proposal,
        human_review_questions=tuple(human_review_questions),
        next_actions=tuple(dict.fromkeys(next_actions)),
        decision_reasons=tuple(decision_reasons),
        warnings=tuple(warnings),
    )
```

- [ ] **Step 4: Run focused version tests**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_version_readiness.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit Task 1**

```bash
git add agent/research_v1/version_readiness.py tests/agent/research_v1/test_version_readiness.py
git commit -m "feat: add version readiness dossier"
```

---

### Task 2: Signal Family Readiness

**Files:**
- Create: `agent/research_v1/signal_family_readiness.py`
- Test: `tests/agent/research_v1/test_signal_family_readiness.py`

- [ ] **Step 1: Write failing signal-family tests**

Create `tests/agent/research_v1/test_signal_family_readiness.py` with:

```python
"""Tests for signal-family readiness governance dossier."""

from __future__ import annotations

import json

import pytest

from agent.research_v1.signal_family_readiness import (
    ALLOWED_FAMILY_TYPES,
    FamilyEvidence,
    SignalFamilyReadinessError,
    SignalFamilyReadinessRequest,
    build_signal_family_readiness_dossier,
)


def _evidence(
    *,
    p20_p23: bool = True,
    p24_p26: bool = False,
    p28: bool = False,
    p30: bool = False,
    mature: bool = True,
) -> FamilyEvidence:
    return FamilyEvidence(
        p20_p23_present=p20_p23,
        p24_p26_present=p24_p26,
        p28_present=p28,
        p30_present=p30,
        maturity=mature,
        edge_summary="net IC positive in shadow observations",
        risk_summary="no critical degradation warnings",
    )


def _request(
    *,
    parent_status: str = "ready_for_human_review",
    family_type: str = "signal_family",
    namespace: str = "signal_family.high_conviction_bullish_equity",
    evidence: FamilyEvidence | None = None,
) -> SignalFamilyReadinessRequest:
    return SignalFamilyReadinessRequest(
        parent_version_status=parent_status,
        family_type=family_type,
        family_namespace=namespace,
        evidence=evidence if evidence is not None else _evidence(),
        notes="candidate for human review",
    )


class TestSignalFamilyContracts:
    def test_allowed_family_types(self):
        assert ALLOWED_FAMILY_TYPES == frozenset({
            "factor_family",
            "signal_family",
            "shadow_model_family",
            "advanced_model_candidate",
        })

    def test_family_evidence_contract(self):
        d = _evidence().to_dict()
        assert d["p20_p23_present"] is True
        assert d["edge_summary"] == "net IC positive in shadow observations"

    def test_invalid_family_type_rejected(self):
        with pytest.raises(SignalFamilyReadinessError, match="family_type must be one of"):
            _request(family_type="portfolio_optimizer")

    def test_json_round_trip(self):
        dossier = build_signal_family_readiness_dossier(_request())
        parsed = json.loads(json.dumps(dossier.to_dict()))
        assert parsed["family_status"] == "ready_for_human_review"
        assert parsed["family_namespace"] == "signal_family.high_conviction_bullish_equity"


class TestSignalFamilyGates:
    def test_blocked_parent_blocks_family(self):
        dossier = build_signal_family_readiness_dossier(
            _request(parent_status="blocked_missing_evidence")
        )
        assert dossier.family_status == "blocked_system_not_ready"
        assert "parent_version_not_ready:blocked_missing_evidence" in dossier.promotion_forbidden_reasons

    def test_missing_core_evidence_blocks(self):
        dossier = build_signal_family_readiness_dossier(
            _request(evidence=_evidence(p20_p23=False))
        )
        assert dossier.family_status == "blocked_missing_family_evidence"
        assert "p20_p23_family_evidence_missing" in dossier.promotion_forbidden_reasons

    def test_partial_evidence_is_shadow_observation_only(self):
        dossier = build_signal_family_readiness_dossier(
            _request(evidence=_evidence(mature=False))
        )
        assert dossier.family_status == "shadow_observation_only"
        assert dossier.allowed_next_step == "continue_shadow_observation"

    def test_shadow_model_requires_p24_p26(self):
        dossier = build_signal_family_readiness_dossier(
            _request(
                family_type="shadow_model_family",
                namespace="shadow_meta_model.xgboost_dry_candidate",
                evidence=_evidence(p24_p26=False, mature=True),
            )
        )
        assert dossier.family_status == "blocked_missing_family_evidence"
        assert "p24_p26_shadow_model_evidence_missing" in dossier.promotion_forbidden_reasons

    def test_advanced_model_requires_p30_and_stays_sandbox_only(self):
        dossier = build_signal_family_readiness_dossier(
            _request(
                family_type="advanced_model_candidate",
                namespace="shadow_advanced_model.real_xgboost_meta_model",
                evidence=_evidence(p24_p26=True, p30=True, mature=True),
            )
        )
        assert dossier.family_status == "ready_for_human_review"
        assert "advanced_model_remains_sandbox_only" in dossier.promotion_forbidden_reasons

    def test_to_dict_rebuilds_family_status(self):
        dossier = build_signal_family_readiness_dossier(_request())
        object.__setattr__(dossier, "family_status", "blocked_system_not_ready")
        assert dossier.to_dict()["family_status"] == "ready_for_human_review"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_signal_family_readiness.py -q
```

Expected: import failure for `agent.research_v1.signal_family_readiness`.

- [ ] **Step 3: Implement signal family readiness module**

Create `agent/research_v1/signal_family_readiness.py` with:

```python
"""Signal-family governance readiness dossier for Hermes candidates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class SignalFamilyReadinessError(ValueError):
    """Raised for unsafe or invalid signal-family readiness inputs."""


ALLOWED_FAMILY_TYPES: frozenset[str] = frozenset({
    "factor_family",
    "signal_family",
    "shadow_model_family",
    "advanced_model_candidate",
})

ALLOWED_PARENT_READY_STATUSES: frozenset[str] = frozenset({"ready_for_human_review"})

ALLOWED_FAMILY_STATUSES: frozenset[str] = frozenset({
    "blocked_system_not_ready",
    "blocked_missing_family_evidence",
    "shadow_observation_only",
    "ready_for_human_review",
})

ALLOWED_NEXT_STEPS: frozenset[str] = frozenset({
    "collect_more_evidence",
    "continue_shadow_observation",
    "prepare_human_review",
    "reject_for_now",
})


@dataclass(frozen=True)
class FamilyEvidence:
    p20_p23_present: bool
    p24_p26_present: bool = False
    p28_present: bool = False
    p30_present: bool = False
    maturity: bool = False
    edge_summary: str = ""
    risk_summary: str = ""
    degradation_warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "p20_p23_present": self.p20_p23_present,
            "p24_p26_present": self.p24_p26_present,
            "p28_present": self.p28_present,
            "p30_present": self.p30_present,
            "maturity": self.maturity,
            "edge_summary": self.edge_summary,
            "risk_summary": self.risk_summary,
            "degradation_warnings": list(self.degradation_warnings),
        }


@dataclass(frozen=True)
class SignalFamilyReadinessRequest:
    parent_version_status: str
    family_type: str
    family_namespace: str
    evidence: FamilyEvidence
    notes: str = ""

    def __post_init__(self) -> None:
        if self.family_type not in ALLOWED_FAMILY_TYPES:
            raise SignalFamilyReadinessError(
                f"family_type must be one of {sorted(ALLOWED_FAMILY_TYPES)}, got {self.family_type!r}"
            )
        if not self.family_namespace.strip():
            raise SignalFamilyReadinessError("family_namespace must be non-empty")


@dataclass(frozen=True)
class SignalFamilyReadinessDossier:
    family_status: str
    parent_version_status: str
    family_type: str
    family_namespace: str
    edge_evidence_summary: str
    risk_evidence_summary: str
    degradation_warnings: tuple[str, ...]
    promotion_forbidden_reasons: tuple[str, ...]
    allowed_next_step: str
    human_review_questions: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.family_status not in ALLOWED_FAMILY_STATUSES:
            raise SignalFamilyReadinessError(
                f"family_status must be one of {sorted(ALLOWED_FAMILY_STATUSES)}, got {self.family_status!r}"
            )
        if self.allowed_next_step not in ALLOWED_NEXT_STEPS:
            raise SignalFamilyReadinessError(
                f"allowed_next_step must be one of {sorted(ALLOWED_NEXT_STEPS)}, got {self.allowed_next_step!r}"
            )

    def to_dict(self) -> dict[str, Any]:
        if self.parent_version_status not in ALLOWED_PARENT_READY_STATUSES:
            rebuilt_status = "blocked_system_not_ready"
        elif any(r.endswith("_missing") for r in self.promotion_forbidden_reasons):
            rebuilt_status = "blocked_missing_family_evidence"
        elif self.allowed_next_step == "continue_shadow_observation":
            rebuilt_status = "shadow_observation_only"
        else:
            rebuilt_status = "ready_for_human_review"

        return {
            "family_status": rebuilt_status,
            "parent_version_status": self.parent_version_status,
            "family_type": self.family_type,
            "family_namespace": self.family_namespace,
            "edge_evidence_summary": self.edge_evidence_summary,
            "risk_evidence_summary": self.risk_evidence_summary,
            "degradation_warnings": list(self.degradation_warnings),
            "promotion_forbidden_reasons": list(self.promotion_forbidden_reasons),
            "allowed_next_step": self.allowed_next_step,
            "human_review_questions": list(self.human_review_questions),
        }


def build_signal_family_readiness_dossier(
    request: SignalFamilyReadinessRequest,
) -> SignalFamilyReadinessDossier:
    forbidden: list[str] = []
    questions: list[str] = []

    if request.parent_version_status not in ALLOWED_PARENT_READY_STATUSES:
        forbidden.append(f"parent_version_not_ready:{request.parent_version_status}")
        return SignalFamilyReadinessDossier(
            family_status="blocked_system_not_ready",
            parent_version_status=request.parent_version_status,
            family_type=request.family_type,
            family_namespace=request.family_namespace,
            edge_evidence_summary=request.evidence.edge_summary,
            risk_evidence_summary=request.evidence.risk_summary,
            degradation_warnings=request.evidence.degradation_warnings,
            promotion_forbidden_reasons=tuple(forbidden),
            allowed_next_step="reject_for_now",
            human_review_questions=("Review system version blockers before family review.",),
        )

    if not request.evidence.p20_p23_present:
        forbidden.append("p20_p23_family_evidence_missing")

    if request.family_type == "shadow_model_family" and not request.evidence.p24_p26_present:
        forbidden.append("p24_p26_shadow_model_evidence_missing")

    if request.family_type == "advanced_model_candidate":
        if not request.evidence.p30_present:
            forbidden.append("p30_advanced_model_admission_missing")
        forbidden.append("advanced_model_remains_sandbox_only")

    blocking_missing = [reason for reason in forbidden if reason.endswith("_missing")]
    if blocking_missing:
        status = "blocked_missing_family_evidence"
        next_step = "collect_more_evidence"
    elif not request.evidence.maturity:
        status = "shadow_observation_only"
        next_step = "continue_shadow_observation"
    else:
        status = "ready_for_human_review"
        next_step = "prepare_human_review"
        questions.append("Does the human reviewer accept the evidence maturity claim?")

    if request.family_type in {"shadow_model_family", "advanced_model_candidate"}:
        if "shadow_outputs_must_not_promote_to_production" not in forbidden:
            forbidden.append("shadow_outputs_must_not_promote_to_production")

    return SignalFamilyReadinessDossier(
        family_status=status,
        parent_version_status=request.parent_version_status,
        family_type=request.family_type,
        family_namespace=request.family_namespace,
        edge_evidence_summary=request.evidence.edge_summary,
        risk_evidence_summary=request.evidence.risk_summary,
        degradation_warnings=request.evidence.degradation_warnings,
        promotion_forbidden_reasons=tuple(forbidden),
        allowed_next_step=next_step,
        human_review_questions=tuple(questions),
    )
```

- [ ] **Step 4: Run focused signal-family tests**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_signal_family_readiness.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Run Task 1 + Task 2 regression**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_version_readiness.py tests/agent/research_v1/test_signal_family_readiness.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit Task 2**

```bash
git add agent/research_v1/signal_family_readiness.py tests/agent/research_v1/test_signal_family_readiness.py
git commit -m "feat: add signal family readiness dossier"
```

---

### Task 3: Daily Governance File Output

**Files:**
- Create: `agent/research_v1/daily_governance.py`
- Test: `tests/agent/research_v1/test_daily_governance.py`

- [ ] **Step 1: Write failing daily governance tests**

Create `tests/agent/research_v1/test_daily_governance.py` with:

```python
"""Tests for daily governance run output."""

from __future__ import annotations

import json
from pathlib import Path

from agent.research_v1.daily_governance import (
    DailyGovernanceRequest,
    DailyGovernanceRunError,
    run_daily_governance,
)
from agent.research_v1.phase29_production_adoption_review import MonitoringSLA, RollbackPlan
from agent.research_v1.signal_family_readiness import FamilyEvidence, SignalFamilyReadinessRequest
from agent.research_v1.version_readiness import (
    EvidenceItem,
    REQUIRED_VERSION_PHASE_IDS,
    TestEvidence,
    VersionMetadata,
    VersionReadinessRequest,
)


def _version_request() -> VersionReadinessRequest:
    return VersionReadinessRequest(
        metadata=VersionMetadata(
            branch="codex/quant-governance-p20-p30",
            commit="c3abd67",
            dirty=False,
            frozen_version_label="",
        ),
        evidence_items=tuple(
            EvidenceItem(phase_id=phase_id, present=True, summary=f"{phase_id} ok")
            for phase_id in REQUIRED_VERSION_PHASE_IDS
        ),
        test_evidence=(
            TestEvidence(
                command="/opt/homebrew/bin/python3.11 -m pytest governance-tests -q",
                status="passed",
                passed_count=12,
                failed_count=0,
                raw_summary="12 passed",
            ),
        ),
        rollback_plan=RollbackPlan(
            rollback_owner="operator",
            rollback_trigger="new governance blocker",
            description="Stop adoption review and return to previous reviewed commit.",
        ),
        monitoring_sla=MonitoringSLA(
            monitoring_cadence="daily",
            alert_routing="operator-review",
            description="Daily review of governance blockers.",
        ),
        version_freeze_proposal=None,
    )


def _family_request() -> SignalFamilyReadinessRequest:
    return SignalFamilyReadinessRequest(
        parent_version_status="ready_for_human_review",
        family_type="signal_family",
        family_namespace="signal_family.high_conviction_bullish_equity",
        evidence=FamilyEvidence(
            p20_p23_present=True,
            maturity=True,
            edge_summary="shadow evidence present",
            risk_summary="no critical warnings",
        ),
    )


class TestDailyGovernance:
    def test_run_writes_expected_json_and_markdown_files(self, tmp_path: Path):
        result = run_daily_governance(
            DailyGovernanceRequest(
                run_date="2026-04-29",
                output_root=tmp_path,
                version_request=_version_request(),
                family_requests=(_family_request(),),
            )
        )
        assert result.status == "completed_with_warnings"
        run_dir = tmp_path / "2026-04-29"
        expected_files = {
            "version_readiness.json",
            "version_readiness.md",
            "signal_families.json",
            "signal_families.md",
            "daily_summary.json",
            "daily_summary.md",
        }
        assert expected_files == {p.name for p in run_dir.iterdir()}

    def test_daily_summary_is_machine_readable(self, tmp_path: Path):
        run_daily_governance(
            DailyGovernanceRequest(
                run_date="2026-04-29",
                output_root=tmp_path,
                version_request=_version_request(),
                family_requests=(_family_request(),),
            )
        )
        summary = json.loads((tmp_path / "2026-04-29" / "daily_summary.json").read_text(encoding="utf-8"))
        assert summary["run_date"] == "2026-04-29"
        assert summary["version_status"] == "ready_for_human_review"
        assert summary["human_review_candidates"] == ["signal_family.high_conviction_bullish_equity"]

    def test_zero_family_candidates_supported(self, tmp_path: Path):
        result = run_daily_governance(
            DailyGovernanceRequest(
                run_date="2026-04-29",
                output_root=tmp_path,
                version_request=_version_request(),
                family_requests=(),
            )
        )
        assert result.status == "completed_with_warnings"
        assert result.family_count == 0

    def test_degraded_mode_for_invalid_output_root(self, tmp_path: Path):
        file_path = tmp_path / "not-a-directory"
        file_path.write_text("x", encoding="utf-8")
        result = run_daily_governance(
            DailyGovernanceRequest(
                run_date="2026-04-29",
                output_root=file_path,
                version_request=_version_request(),
                family_requests=(_family_request(),),
            )
        )
        assert result.status == "governance_degraded"
        assert "output_path_not_directory" in result.warnings

    def test_invalid_run_date_rejected(self, tmp_path: Path):
        try:
            DailyGovernanceRequest(
                run_date="29-04-2026",
                output_root=tmp_path,
                version_request=_version_request(),
                family_requests=(),
            )
        except DailyGovernanceRunError as exc:
            assert "run_date must use YYYY-MM-DD" in str(exc)
        else:
            raise AssertionError("DailyGovernanceRunError was not raised")
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_daily_governance.py -q
```

Expected: import failure for `agent.research_v1.daily_governance`.

- [ ] **Step 3: Implement daily governance module**

Create `agent/research_v1/daily_governance.py` with:

```python
"""Daily governance run orchestration for Hermes readiness artifacts."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent.research_v1.signal_family_readiness import (
    SignalFamilyReadinessDossier,
    SignalFamilyReadinessRequest,
    build_signal_family_readiness_dossier,
)
from agent.research_v1.version_readiness import (
    VersionReadinessDossier,
    VersionReadinessRequest,
    build_version_readiness_dossier,
)


class DailyGovernanceRunError(ValueError):
    """Raised for invalid daily governance run inputs."""


RUN_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass(frozen=True)
class DailyGovernanceRequest:
    run_date: str
    output_root: Path
    version_request: VersionReadinessRequest
    family_requests: tuple[SignalFamilyReadinessRequest, ...]

    def __post_init__(self) -> None:
        if not RUN_DATE_RE.match(self.run_date):
            raise DailyGovernanceRunError("run_date must use YYYY-MM-DD")


@dataclass(frozen=True)
class DailyGovernanceResult:
    status: str
    run_date: str
    output_dir: str
    version_status: str
    family_count: int
    human_review_candidates: tuple[str, ...]
    blocked_items: tuple[str, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "run_date": self.run_date,
            "output_dir": self.output_dir,
            "version_status": self.version_status,
            "family_count": self.family_count,
            "human_review_candidates": list(self.human_review_candidates),
            "blocked_items": list(self.blocked_items),
            "warnings": list(self.warnings),
        }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _version_markdown(dossier: VersionReadinessDossier) -> str:
    data = dossier.to_dict()
    lines = [
        "# Version Readiness",
        "",
        f"Status: `{data['status']}`",
        f"Branch: `{data['metadata']['branch']}`",
        f"Commit: `{data['metadata']['commit']}`",
        "",
        "## Decision Reasons",
    ]
    lines.extend(f"- {reason}" for reason in data["decision_reasons"])
    lines.append("")
    lines.append("## Warnings")
    lines.extend(f"- {warning}" for warning in data["warnings"])
    return "\n".join(lines) + "\n"


def _families_markdown(dossiers: tuple[SignalFamilyReadinessDossier, ...]) -> str:
    lines = ["# Signal Family Readiness", ""]
    if not dossiers:
        lines.append("No signal family candidates configured.")
        return "\n".join(lines) + "\n"
    for dossier in dossiers:
        data = dossier.to_dict()
        lines.append(f"## {data['family_namespace']}")
        lines.append(f"- Status: `{data['family_status']}`")
        lines.append(f"- Next step: `{data['allowed_next_step']}`")
        lines.append(f"- Edge: {data['edge_evidence_summary']}")
        lines.append(f"- Risk: {data['risk_evidence_summary']}")
        lines.append("")
    return "\n".join(lines)


def _summary_markdown(result: DailyGovernanceResult) -> str:
    data = result.to_dict()
    lines = [
        "# Daily Governance Summary",
        "",
        f"Status: `{data['status']}`",
        f"Run date: `{data['run_date']}`",
        f"Version status: `{data['version_status']}`",
        "",
        "## Human Review Candidates",
    ]
    if data["human_review_candidates"]:
        lines.extend(f"- {item}" for item in data["human_review_candidates"])
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Blocked Items")
    if data["blocked_items"]:
        lines.extend(f"- {item}" for item in data["blocked_items"])
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Warnings")
    if data["warnings"]:
        lines.extend(f"- {item}" for item in data["warnings"])
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def _build_result(
    request: DailyGovernanceRequest,
    output_dir: Path,
    version_dossier: VersionReadinessDossier,
    family_dossiers: tuple[SignalFamilyReadinessDossier, ...],
    warnings: tuple[str, ...],
) -> DailyGovernanceResult:
    human_review_candidates = tuple(
        dossier.family_namespace for dossier in family_dossiers
        if dossier.to_dict()["family_status"] == "ready_for_human_review"
    )
    blocked_items = []
    if version_dossier.to_dict()["status"].startswith("blocked_"):
        blocked_items.append(f"version:{version_dossier.to_dict()['status']}")
    for dossier in family_dossiers:
        family_data = dossier.to_dict()
        if family_data["family_status"].startswith("blocked_"):
            blocked_items.append(f"{family_data['family_namespace']}:{family_data['family_status']}")

    status = "completed"
    all_warnings = list(warnings)
    all_warnings.extend(version_dossier.warnings)
    for dossier in family_dossiers:
        all_warnings.extend(dossier.degradation_warnings)
    if all_warnings:
        status = "completed_with_warnings"

    return DailyGovernanceResult(
        status=status,
        run_date=request.run_date,
        output_dir=str(output_dir),
        version_status=version_dossier.to_dict()["status"],
        family_count=len(family_dossiers),
        human_review_candidates=human_review_candidates,
        blocked_items=tuple(blocked_items),
        warnings=tuple(dict.fromkeys(all_warnings)),
    )


def run_daily_governance(request: DailyGovernanceRequest) -> DailyGovernanceResult:
    version_dossier = build_version_readiness_dossier(request.version_request)
    family_dossiers = tuple(
        build_signal_family_readiness_dossier(family_request)
        for family_request in request.family_requests
    )
    output_dir = request.output_root / request.run_date

    if request.output_root.exists() and not request.output_root.is_dir():
        return DailyGovernanceResult(
            status="governance_degraded",
            run_date=request.run_date,
            output_dir=str(output_dir),
            version_status=version_dossier.to_dict()["status"],
            family_count=len(family_dossiers),
            human_review_candidates=(),
            blocked_items=(),
            warnings=("output_path_not_directory",),
        )

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        families_payload = [dossier.to_dict() for dossier in family_dossiers]
        result = _build_result(
            request=request,
            output_dir=output_dir,
            version_dossier=version_dossier,
            family_dossiers=family_dossiers,
            warnings=(),
        )
        _write_json(output_dir / "version_readiness.json", version_dossier.to_dict())
        (output_dir / "version_readiness.md").write_text(_version_markdown(version_dossier), encoding="utf-8")
        _write_json(output_dir / "signal_families.json", {"families": families_payload})
        (output_dir / "signal_families.md").write_text(_families_markdown(family_dossiers), encoding="utf-8")
        _write_json(output_dir / "daily_summary.json", result.to_dict())
        (output_dir / "daily_summary.md").write_text(_summary_markdown(result), encoding="utf-8")
        return result
    except OSError as exc:
        return DailyGovernanceResult(
            status="governance_degraded",
            run_date=request.run_date,
            output_dir=str(output_dir),
            version_status=version_dossier.to_dict()["status"],
            family_count=len(family_dossiers),
            human_review_candidates=(),
            blocked_items=(),
            warnings=(f"output_write_failed:{exc.__class__.__name__}",),
        )
```

- [ ] **Step 4: Run focused daily governance tests**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_daily_governance.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Run full governance readiness tests**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest \
  tests/agent/research_v1/test_version_readiness.py \
  tests/agent/research_v1/test_signal_family_readiness.py \
  tests/agent/research_v1/test_daily_governance.py \
  -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit Task 3**

```bash
git add agent/research_v1/daily_governance.py tests/agent/research_v1/test_daily_governance.py
git commit -m "feat: add daily governance run"
```

---

### Task 4: Governance Regression And Existing P28-P30 Safety Check

**Files:**
- Verify only. No file edits expected.

- [ ] **Step 1: Run new governance readiness tests**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest \
  tests/agent/research_v1/test_version_readiness.py \
  tests/agent/research_v1/test_signal_family_readiness.py \
  tests/agent/research_v1/test_daily_governance.py \
  -q
```

Expected: all tests pass.

- [ ] **Step 2: Run adjacent governance pack tests**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest \
  tests/agent/research_v1/test_phase28_execution_realism.py \
  tests/agent/research_v1/test_phase29_production_adoption_review.py \
  tests/agent/research_v1/test_phase30_advanced_model_pack.py \
  -q
```

Expected: all tests pass. The known good baseline before this plan was `151 passed`.

- [ ] **Step 3: Run P20-P30 governance chain tests**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest \
  tests/agent/research_v1/test_p20_factor_contracts.py \
  tests/agent/research_v1/test_p20_pnl_integrity.py \
  tests/agent/research_v1/test_p21_calibration_inputs.py \
  tests/agent/research_v1/test_p22_a_plus_validity_integrity_health.py \
  tests/agent/research_v1/test_p23_shadow_calibration.py \
  tests/agent/research_v1/test_p23_shadow_observation_loop.py \
  tests/agent/research_v1/test_p24_entry_gate.py \
  tests/agent/research_v1/test_p24_experiment_registry.py \
  tests/agent/research_v1/test_p24_shadow_runner.py \
  tests/agent/research_v1/test_p24_run_persistence.py \
  tests/agent/research_v1/test_p24_health_report.py \
  tests/agent/research_v1/test_phase25_model_governance.py \
  tests/agent/research_v1/test_p25_xgboost_shadow_adapter.py \
  tests/agent/research_v1/test_p25_training_dataset_builder.py \
  tests/agent/research_v1/test_p25_split_manifest_builder.py \
  tests/agent/research_v1/test_p25_shadow_training_runner.py \
  tests/agent/research_v1/test_phase26_shadow_portfolio.py \
  tests/agent/research_v1/test_phase27_factor_expansion.py \
  tests/agent/research_v1/test_phase28_execution_realism.py \
  tests/agent/research_v1/test_phase29_production_adoption_review.py \
  tests/agent/research_v1/test_phase30_advanced_model_pack.py \
  tests/agent/research_v1/test_version_readiness.py \
  tests/agent/research_v1/test_signal_family_readiness.py \
  tests/agent/research_v1/test_daily_governance.py \
  -q
```

Expected: all tests pass. The known good baseline before adding these tests was `488 passed`; the new expected count should be higher by the new governance readiness tests.

- [ ] **Step 4: Check git diff hygiene**

Run:

```bash
git diff --check
git status --short
```

Expected: no whitespace errors. Status shows only intentional governance readiness files if anything remains uncommitted.

- [ ] **Step 5: Commit verification note if code changed after prior commits**

If Task 4 required any code changes, commit only those changes:

```bash
git add agent/research_v1 tests/agent/research_v1
git commit -m "test: verify governance readiness regression"
```

If Task 4 required no code changes, do not create an empty commit.

---

## Known Existing Test Gap

The existing `tests/agent/research_v1/test_doc_standards.py` is currently failing on pre-existing documentation issues:

- `agent/research_v1/README.md` is missing a required Data Flow / How It Fits heading.
- `agent/research_v1/report_templates/` has Python files but no `README.md`.

Those failures are outside this governance readiness implementation plan. Do not fix them in this plan unless the user explicitly expands the scope.

---

## Self-Review Checklist

- Spec section 4 maps to Task 1.
- Spec section 5 maps to Task 2.
- Spec section 6 maps to Task 3.
- Spec testing and acceptance criteria map to Task 4.
- No task mutates production config.
- No task enables auto-trading.
- No task wires the workflow into the existing runtime or CLI before the pure file-output path is tested.
