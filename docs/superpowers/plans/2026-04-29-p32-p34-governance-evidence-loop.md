# P32-P34 Governance Evidence Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build P32-P34 so Hermes can collect governance artifacts, dry-run missing evidence generation, review signal-family edge evidence, and produce a boss-readable governance daily brief.

**Architecture:** Add four stdlib-only modules under `agent/research_v1/`: `evidence_artifact_registry.py`, `evidence_generation_dry_run.py`, `signal_family_edge_review.py`, and `boss_governance_brief.py`. Each module follows the P31 style: frozen dataclasses, explicit allowed status constants, deterministic `to_dict()` serialization, pure builder functions, append-only file outputs where applicable, and no production/trading side effects.

**Tech Stack:** Python 3.11, dataclasses, pathlib, json, datetime, pytest, existing P31 governance readiness contracts.

---

## File Structure

- Create `agent/research_v1/evidence_artifact_registry.py`
  - Owns P32-A artifact definitions, registry scanning, freshness classification, coverage summaries, and registry report serialization.
- Create `tests/agent/research_v1/test_evidence_artifact_registry.py`
  - Tests present/missing/stale/invalid artifacts, phase/family coverage, and JSON round-trip.
- Create `agent/research_v1/evidence_generation_dry_run.py`
  - Owns P32-B dry-run generation request validation, required-input mapping, production namespace rejection, actual-execution rejection, and manifest writing.
- Create `tests/agent/research_v1/test_evidence_generation_dry_run.py`
  - Tests safe request admission, missing input blockers, unknown artifact blockers, actual-execution blockers, production namespace blockers, and JSON/Markdown manifest output.
- Create `agent/research_v1/signal_family_edge_review.py`
  - Owns P33 edge review based on P32 registry evidence and explicit review policy.
- Create `tests/agent/research_v1/test_signal_family_edge_review.py`
  - Tests missing diagnostics blockers, gross-only edge blockers, integrity blockers, execution-cost blockers, shadow/model promotion boundaries, and ready-for-human-review path.
- Create `agent/research_v1/boss_governance_brief.py`
  - Owns P34 boss daily brief assembly and file output.
- Create `tests/agent/research_v1/test_boss_governance_brief.py`
  - Tests brief content, degraded status, missing/stale summaries, review candidates, forbidden trading language exclusion, and output files.

No existing runtime path or CLI should be modified in P32-P34. Do not wire scheduling, notifications, viewer routes, or trading actions.

---

## Shared Constants

Use these artifact type strings consistently across P32-P34:

```python
EXPECTED_ARTIFACT_TYPES = (
    "p20_factor_snapshot",
    "p22_validity_report",
    "p23_shadow_calibration_report",
    "p24_shadow_experiment_manifest",
    "p25_training_dataset_result",
    "p25_shadow_training_result",
    "p26_shadow_portfolio_report",
    "p28_execution_realism_report",
    "p29_adoption_dossier",
    "p30_advanced_model_admission",
    "p31_version_readiness",
    "p31_signal_family_readiness",
    "p31_daily_governance",
)
```

Use these phase IDs consistently:

```python
ARTIFACT_PHASE_BY_TYPE = {
    "p20_factor_snapshot": "P20",
    "p22_validity_report": "P22",
    "p23_shadow_calibration_report": "P23",
    "p24_shadow_experiment_manifest": "P24",
    "p25_training_dataset_result": "P25",
    "p25_shadow_training_result": "P25",
    "p26_shadow_portfolio_report": "P26",
    "p28_execution_realism_report": "P28",
    "p29_adoption_dossier": "P29",
    "p30_advanced_model_admission": "P30",
    "p31_version_readiness": "P31",
    "p31_signal_family_readiness": "P31",
    "p31_daily_governance": "P31",
}
```

---

### Task 1: P32-A Evidence Artifact Registry

**Files:**
- Create: `agent/research_v1/evidence_artifact_registry.py`
- Test: `tests/agent/research_v1/test_evidence_artifact_registry.py`

- [ ] **Step 1: Write failing registry tests**

Create `tests/agent/research_v1/test_evidence_artifact_registry.py` with these tests:

```python
"""Tests for P32-A evidence artifact registry."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent.research_v1.evidence_artifact_registry import (
    EXPECTED_ARTIFACT_TYPES,
    ArtifactDefinition,
    ArtifactRecord,
    EvidenceArtifactRegistryError,
    EvidenceArtifactRegistryRequest,
    build_evidence_artifact_registry,
)


def _definition(
    artifact_type: str = "p31_daily_governance",
    relative_path: str = "2026-04-29/daily_summary.json",
    family_namespace: str = "",
) -> ArtifactDefinition:
    return ArtifactDefinition(
        artifact_type=artifact_type,
        relative_path=relative_path,
        family_namespace=family_namespace,
        required=True,
    )


def test_expected_artifact_types_include_p31_daily_governance():
    assert "p31_daily_governance" in EXPECTED_ARTIFACT_TYPES
    assert "p22_validity_report" in EXPECTED_ARTIFACT_TYPES
    assert "p25_shadow_training_result" in EXPECTED_ARTIFACT_TYPES


def test_present_artifact_is_recorded_as_present(tmp_path: Path):
    artifact = tmp_path / "2026-04-29" / "daily_summary.json"
    artifact.parent.mkdir()
    artifact.write_text('{"status": "completed"}', encoding="utf-8")
    report = build_evidence_artifact_registry(
        EvidenceArtifactRegistryRequest(
            run_date="2026-04-29",
            scan_roots=(tmp_path,),
            expected_artifacts=(_definition(),),
            freshness_policy_days=7,
        )
    )
    assert report.status == "complete"
    assert report.artifact_records[0].status == "present"
    assert report.coverage_by_phase == (("P31", 1.0),)


def test_missing_expected_artifact_is_recorded_as_missing(tmp_path: Path):
    report = build_evidence_artifact_registry(
        EvidenceArtifactRegistryRequest(
            run_date="2026-04-29",
            scan_roots=(tmp_path,),
            expected_artifacts=(_definition(),),
            freshness_policy_days=7,
        )
    )
    assert report.status == "incomplete_missing_artifacts"
    assert report.missing_artifact_types == ("p31_daily_governance",)
    assert report.artifact_records[0].status == "missing"


def test_stale_artifact_is_recorded_as_stale(tmp_path: Path):
    artifact = tmp_path / "2026-04-01" / "daily_summary.json"
    artifact.parent.mkdir()
    artifact.write_text("{}", encoding="utf-8")
    report = build_evidence_artifact_registry(
        EvidenceArtifactRegistryRequest(
            run_date="2026-04-29",
            scan_roots=(tmp_path,),
            expected_artifacts=(
                _definition(relative_path="2026-04-01/daily_summary.json"),
            ),
            freshness_policy_days=7,
        )
    )
    assert report.status == "incomplete_stale_artifacts"
    assert report.artifact_records[0].status == "stale"
    assert report.stale_artifact_ids == ("p31_daily_governance:2026-04-01/daily_summary.json",)


def test_invalid_artifact_path_is_recorded_as_invalid(tmp_path: Path):
    artifact_dir = tmp_path / "2026-04-29" / "daily_summary.json"
    artifact_dir.mkdir(parents=True)
    report = build_evidence_artifact_registry(
        EvidenceArtifactRegistryRequest(
            run_date="2026-04-29",
            scan_roots=(tmp_path,),
            expected_artifacts=(_definition(),),
            freshness_policy_days=7,
        )
    )
    assert report.status == "invalid_registry"
    assert report.artifact_records[0].status == "invalid"
    assert report.invalid_artifact_ids == ("p31_daily_governance:2026-04-29/daily_summary.json",)


def test_coverage_by_family_is_computed(tmp_path: Path):
    artifact = tmp_path / "families" / "quality.json"
    artifact.parent.mkdir()
    artifact.write_text("{}", encoding="utf-8")
    report = build_evidence_artifact_registry(
        EvidenceArtifactRegistryRequest(
            run_date="2026-04-29",
            scan_roots=(tmp_path,),
            expected_artifacts=(
                _definition(
                    artifact_type="p22_validity_report",
                    relative_path="families/quality.json",
                    family_namespace="factor_family.quality",
                ),
            ),
            freshness_policy_days=30,
        )
    )
    assert report.coverage_by_family == (("factor_family.quality", 1.0),)


def test_artifact_record_json_round_trip():
    record = ArtifactRecord(
        artifact_id="p31_daily_governance:2026-04-29/daily_summary.json",
        artifact_type="p31_daily_governance",
        phase_id="P31",
        path="/tmp/output/governance/2026-04-29/daily_summary.json",
        present=True,
        status="present",
        family_namespace="",
        created_at="2026-04-29",
        freshness_days=0,
        summary="present",
        details={},
    )
    parsed = json.loads(json.dumps(record.to_dict()))
    assert parsed["artifact_type"] == "p31_daily_governance"


def test_unknown_artifact_type_rejected():
    with pytest.raises(EvidenceArtifactRegistryError, match="artifact_type must be one of"):
        ArtifactDefinition(
            artifact_type="unknown_artifact",
            relative_path="x.json",
            family_namespace="",
            required=True,
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_evidence_artifact_registry.py -q
```

Expected: import failure for `agent.research_v1.evidence_artifact_registry`.

- [ ] **Step 3: Implement registry module**

Create `agent/research_v1/evidence_artifact_registry.py` with these required contracts and behavior:

```python
"""P32-A evidence artifact registry for governance outputs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any


class EvidenceArtifactRegistryError(ValueError):
    """Raised for unsafe or invalid evidence artifact registry inputs."""


EXPECTED_ARTIFACT_TYPES: tuple[str, ...] = (
    "p20_factor_snapshot",
    "p22_validity_report",
    "p23_shadow_calibration_report",
    "p24_shadow_experiment_manifest",
    "p25_training_dataset_result",
    "p25_shadow_training_result",
    "p26_shadow_portfolio_report",
    "p28_execution_realism_report",
    "p29_adoption_dossier",
    "p30_advanced_model_admission",
    "p31_version_readiness",
    "p31_signal_family_readiness",
    "p31_daily_governance",
)

ARTIFACT_PHASE_BY_TYPE: dict[str, str] = {
    "p20_factor_snapshot": "P20",
    "p22_validity_report": "P22",
    "p23_shadow_calibration_report": "P23",
    "p24_shadow_experiment_manifest": "P24",
    "p25_training_dataset_result": "P25",
    "p25_shadow_training_result": "P25",
    "p26_shadow_portfolio_report": "P26",
    "p28_execution_realism_report": "P28",
    "p29_adoption_dossier": "P29",
    "p30_advanced_model_admission": "P30",
    "p31_version_readiness": "P31",
    "p31_signal_family_readiness": "P31",
    "p31_daily_governance": "P31",
}

ALLOWED_ARTIFACT_STATUSES = frozenset({"present", "missing", "stale", "invalid"})
ALLOWED_REGISTRY_STATUSES = frozenset({
    "complete",
    "incomplete_missing_artifacts",
    "incomplete_stale_artifacts",
    "invalid_registry",
})


@dataclass(frozen=True)
class ArtifactDefinition:
    artifact_type: str
    relative_path: str
    family_namespace: str = ""
    required: bool = True

    def __post_init__(self) -> None:
        if self.artifact_type not in EXPECTED_ARTIFACT_TYPES:
            raise EvidenceArtifactRegistryError(
                f"artifact_type must be one of {list(EXPECTED_ARTIFACT_TYPES)}, got {self.artifact_type!r}"
            )
        if not self.relative_path.strip():
            raise EvidenceArtifactRegistryError("relative_path must be non-empty")

    @property
    def phase_id(self) -> str:
        return ARTIFACT_PHASE_BY_TYPE[self.artifact_type]


@dataclass(frozen=True)
class ArtifactRecord:
    artifact_id: str
    artifact_type: str
    phase_id: str
    path: str
    present: bool
    status: str
    family_namespace: str
    created_at: str
    freshness_days: int | None
    summary: str
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in ALLOWED_ARTIFACT_STATUSES:
            raise EvidenceArtifactRegistryError(
                f"status must be one of {sorted(ALLOWED_ARTIFACT_STATUSES)}, got {self.status!r}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "artifact_type": self.artifact_type,
            "phase_id": self.phase_id,
            "path": self.path,
            "present": self.present,
            "status": self.status,
            "family_namespace": self.family_namespace,
            "created_at": self.created_at,
            "freshness_days": self.freshness_days,
            "summary": self.summary,
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class EvidenceArtifactRegistryRequest:
    run_date: str
    scan_roots: tuple[Path, ...]
    expected_artifacts: tuple[ArtifactDefinition, ...]
    freshness_policy_days: int


@dataclass(frozen=True)
class EvidenceArtifactRegistryReport:
    status: str
    run_date: str
    scan_roots: tuple[str, ...]
    artifact_records: tuple[ArtifactRecord, ...]
    missing_artifact_types: tuple[str, ...]
    stale_artifact_ids: tuple[str, ...]
    invalid_artifact_ids: tuple[str, ...]
    coverage_by_phase: tuple[tuple[str, float], ...]
    coverage_by_family: tuple[tuple[str, float], ...]
    next_actions: tuple[str, ...]
    warnings: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.status not in ALLOWED_REGISTRY_STATUSES:
            raise EvidenceArtifactRegistryError(
                f"status must be one of {sorted(ALLOWED_REGISTRY_STATUSES)}, got {self.status!r}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "run_date": self.run_date,
            "scan_roots": list(self.scan_roots),
            "artifact_records": [record.to_dict() for record in self.artifact_records],
            "missing_artifact_types": list(self.missing_artifact_types),
            "stale_artifact_ids": list(self.stale_artifact_ids),
            "invalid_artifact_ids": list(self.invalid_artifact_ids),
            "coverage_by_phase": dict(self.coverage_by_phase),
            "coverage_by_family": dict(self.coverage_by_family),
            "next_actions": list(self.next_actions),
            "warnings": list(self.warnings),
        }
```

Also implement `build_evidence_artifact_registry(request: EvidenceArtifactRegistryRequest) -> EvidenceArtifactRegistryReport`.

Implementation requirements:

- Parse `request.run_date` with `date.fromisoformat`.
- For each `ArtifactDefinition`, search roots in order for `root / relative_path`.
- If no file exists, record `missing`.
- If the path exists but is not a file, record `invalid`.
- If it exists and a leading `YYYY-MM-DD` segment can be parsed from `relative_path`, compute freshness against `run_date`.
- If freshness exceeds `freshness_policy_days`, record `stale`.
- Otherwise record `present`.
- Compute coverage as present count divided by expected count per phase/family. Treat stale and invalid as not present for coverage.
- Status priority is: invalid > missing > stale > complete.

- [ ] **Step 4: Run focused P32-A tests**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_evidence_artifact_registry.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit P32-A**

```bash
git add agent/research_v1/evidence_artifact_registry.py tests/agent/research_v1/test_evidence_artifact_registry.py
git commit -m "feat: add evidence artifact registry"
```

---

### Task 2: P32-B Controlled Evidence Generation Dry Run

**Files:**
- Create: `agent/research_v1/evidence_generation_dry_run.py`
- Test: `tests/agent/research_v1/test_evidence_generation_dry_run.py`

- [ ] **Step 1: Write failing dry-run tests**

Create `tests/agent/research_v1/test_evidence_generation_dry_run.py` with:

```python
"""Tests for P32-B controlled evidence generation dry run."""

from __future__ import annotations

import json
from pathlib import Path

from agent.research_v1.evidence_generation_dry_run import (
    EvidenceGenerationRequest,
    build_controlled_evidence_generation_report,
    write_evidence_generation_dry_run_manifest,
)


def test_known_artifact_with_required_inputs_is_allowed(tmp_path: Path):
    report = build_controlled_evidence_generation_report(
        run_date="2026-04-29",
        requests=(
            EvidenceGenerationRequest(
                artifact_type="p22_validity_report",
                phase_id="P22",
                family_namespace="factor_family.quality",
                requested_output_dir=str(tmp_path / "output/governance/2026-04-29"),
                input_refs={
                    "factor_snapshot_rows": "snapshots.json",
                    "forward_return_observations": "returns.json",
                    "data_integrity_policy": "strict",
                },
                allow_actual_execution=False,
            ),
        ),
    )
    assert report.status == "dry_run_complete"
    assert report.allowed_requests[0].artifact_type == "p22_validity_report"


def test_missing_required_inputs_blocks_request(tmp_path: Path):
    report = build_controlled_evidence_generation_report(
        run_date="2026-04-29",
        requests=(
            EvidenceGenerationRequest(
                artifact_type="p25_shadow_training_result",
                phase_id="P25",
                family_namespace="shadow_meta_model.xgboost_dry_candidate",
                requested_output_dir=str(tmp_path / "output/governance/2026-04-29"),
                input_refs={"training_dataset_result": "dataset.json"},
                allow_actual_execution=False,
            ),
        ),
    )
    assert report.status == "blocked_missing_inputs"
    assert report.blocked_requests[0].blocked_reasons == (
        "missing_required_input:walk_forward_split_manifest",
        "missing_required_input:p24_experiment_manifest",
    )


def test_unknown_artifact_type_blocks_request(tmp_path: Path):
    report = build_controlled_evidence_generation_report(
        run_date="2026-04-29",
        requests=(
            EvidenceGenerationRequest(
                artifact_type="unknown_artifact",
                phase_id="P99",
                family_namespace="",
                requested_output_dir=str(tmp_path),
                input_refs={},
                allow_actual_execution=False,
            ),
        ),
    )
    assert report.status == "blocked_unsafe_request"
    assert "unknown_artifact_type:unknown_artifact" in report.blocked_requests[0].blocked_reasons


def test_allow_actual_execution_is_rejected(tmp_path: Path):
    report = build_controlled_evidence_generation_report(
        run_date="2026-04-29",
        requests=(
            EvidenceGenerationRequest(
                artifact_type="p28_execution_realism_report",
                phase_id="P28",
                family_namespace="signal_family.demo",
                requested_output_dir=str(tmp_path),
                input_refs={
                    "trade_intents": "intents.json",
                    "liquidity_inputs": "liquidity.json",
                    "alpha_edge_estimate": "50bps",
                },
                allow_actual_execution=True,
            ),
        ),
    )
    assert report.status == "blocked_unsafe_request"
    assert "actual_execution_not_allowed_in_p32_b" in report.blocked_requests[0].blocked_reasons


def test_production_namespace_output_is_rejected(tmp_path: Path):
    report = build_controlled_evidence_generation_report(
        run_date="2026-04-29",
        requests=(
            EvidenceGenerationRequest(
                artifact_type="p22_validity_report",
                phase_id="P22",
                family_namespace="factor_family.quality",
                requested_output_dir="production/config",
                input_refs={
                    "factor_snapshot_rows": "snapshots.json",
                    "forward_return_observations": "returns.json",
                    "data_integrity_policy": "strict",
                },
                allow_actual_execution=False,
            ),
        ),
    )
    assert report.status == "blocked_unsafe_request"
    assert "requested_output_dir_must_be_under_output_governance" in report.blocked_requests[0].blocked_reasons


def test_dry_run_manifest_writes_json_and_markdown(tmp_path: Path):
    report = build_controlled_evidence_generation_report(
        run_date="2026-04-29",
        requests=(),
    )
    paths = write_evidence_generation_dry_run_manifest(report, tmp_path / "2026-04-29")
    assert paths["json"].name == "evidence_generation_dry_run.json"
    assert paths["markdown"].name == "evidence_generation_dry_run.md"
    parsed = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert parsed["status"] == "dry_run_complete"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_evidence_generation_dry_run.py -q
```

Expected: import failure for `agent.research_v1.evidence_generation_dry_run`.

- [ ] **Step 3: Implement dry-run module**

Create `agent/research_v1/evidence_generation_dry_run.py` with:

```python
"""P32-B controlled evidence generation dry-run manifest."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent.research_v1.evidence_artifact_registry import EXPECTED_ARTIFACT_TYPES


REQUIRED_INPUTS_BY_ARTIFACT: dict[str, tuple[str, ...]] = {
    "p22_validity_report": (
        "factor_snapshot_rows",
        "forward_return_observations",
        "data_integrity_policy",
    ),
    "p25_training_dataset_result": (
        "point_in_time_factor_snapshots",
        "target_definition",
        "feature_namespace",
    ),
    "p25_shadow_training_result": (
        "training_dataset_result",
        "walk_forward_split_manifest",
        "p24_experiment_manifest",
    ),
    "p28_execution_realism_report": (
        "trade_intents",
        "liquidity_inputs",
        "alpha_edge_estimate",
    ),
}

ALLOWED_GENERATION_STATUSES = frozenset({
    "dry_run_complete",
    "blocked_unsafe_request",
    "blocked_missing_inputs",
})


@dataclass(frozen=True)
class EvidenceGenerationRequest:
    artifact_type: str
    phase_id: str
    family_namespace: str
    requested_output_dir: str
    input_refs: dict[str, Any]
    allow_actual_execution: bool = False
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_type": self.artifact_type,
            "phase_id": self.phase_id,
            "family_namespace": self.family_namespace,
            "requested_output_dir": self.requested_output_dir,
            "input_refs": dict(self.input_refs),
            "allow_actual_execution": self.allow_actual_execution,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class EvidenceGenerationDecision:
    request: EvidenceGenerationRequest
    allowed: bool
    blocked_reasons: tuple[str, ...]
    required_inputs: tuple[str, ...]

    @property
    def artifact_type(self) -> str:
        return self.request.artifact_type

    def to_dict(self) -> dict[str, Any]:
        return {
            "request": self.request.to_dict(),
            "allowed": self.allowed,
            "blocked_reasons": list(self.blocked_reasons),
            "required_inputs": list(self.required_inputs),
        }


@dataclass(frozen=True)
class ControlledEvidenceGenerationReport:
    status: str
    run_date: str
    requested_artifacts: tuple[str, ...]
    allowed_requests: tuple[EvidenceGenerationDecision, ...]
    blocked_requests: tuple[EvidenceGenerationDecision, ...]
    required_inputs_by_artifact: tuple[tuple[str, tuple[str, ...]], ...]
    dry_run_manifest_path: str
    next_actions: tuple[str, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "run_date": self.run_date,
            "requested_artifacts": list(self.requested_artifacts),
            "allowed_requests": [item.to_dict() for item in self.allowed_requests],
            "blocked_requests": [item.to_dict() for item in self.blocked_requests],
            "required_inputs_by_artifact": {
                key: list(value) for key, value in self.required_inputs_by_artifact
            },
            "dry_run_manifest_path": self.dry_run_manifest_path,
            "next_actions": list(self.next_actions),
            "warnings": list(self.warnings),
        }
```

Also implement `build_controlled_evidence_generation_report(run_date: str, requests: tuple[EvidenceGenerationRequest, ...], dry_run_manifest_path: str = "") -> ControlledEvidenceGenerationReport`.

Also implement `write_evidence_generation_dry_run_manifest(report: ControlledEvidenceGenerationReport, output_dir: Path) -> dict[str, Path]`.

Implementation requirements:

- A request is unsafe if `allow_actual_execution` is true.
- A request is unsafe if `artifact_type` is not in `EXPECTED_ARTIFACT_TYPES`.
- A request is unsafe if `requested_output_dir` does not contain `output/governance` and is not empty. The tests use an absolute temp path containing `output/governance/2026-04-29`; accept that.
- A request has missing inputs when any key in `REQUIRED_INPUTS_BY_ARTIFACT[artifact_type]` is absent from `input_refs`.
- Unknown but expected artifact types with no required-input mapping are allowed when safe.
- Status priority is unsafe > missing inputs > dry-run complete.
- `write_evidence_generation_dry_run_manifest()` writes JSON and Markdown only; it must not run jobs.

- [ ] **Step 4: Run focused P32-B tests**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_evidence_generation_dry_run.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Run P32 tests together**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest \
  tests/agent/research_v1/test_evidence_artifact_registry.py \
  tests/agent/research_v1/test_evidence_generation_dry_run.py \
  -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit P32-B**

```bash
git add agent/research_v1/evidence_generation_dry_run.py tests/agent/research_v1/test_evidence_generation_dry_run.py
git commit -m "feat: add evidence generation dry run"
```

---

### Task 3: P33 Signal Family Edge Review

**Files:**
- Create: `agent/research_v1/signal_family_edge_review.py`
- Test: `tests/agent/research_v1/test_signal_family_edge_review.py`

- [ ] **Step 1: Write failing P33 tests**

Create `tests/agent/research_v1/test_signal_family_edge_review.py` with:

```python
"""Tests for P33 signal-family edge review."""

from __future__ import annotations

from agent.research_v1.evidence_artifact_registry import ArtifactRecord, EvidenceArtifactRegistryReport
from agent.research_v1.signal_family_edge_review import (
    EdgeReviewPolicy,
    SignalFamilyEdgeReviewRequest,
    build_signal_family_edge_review,
)


def _record(
    artifact_type: str,
    phase_id: str,
    status: str = "present",
    family_namespace: str = "factor_family.quality",
    details: dict | None = None,
) -> ArtifactRecord:
    return ArtifactRecord(
        artifact_id=f"{artifact_type}:demo",
        artifact_type=artifact_type,
        phase_id=phase_id,
        path=f"/tmp/{artifact_type}.json",
        present=status == "present",
        status=status,
        family_namespace=family_namespace,
        created_at="2026-04-29",
        freshness_days=0,
        summary=status,
        details=details or {},
    )


def _registry(records: tuple[ArtifactRecord, ...]) -> EvidenceArtifactRegistryReport:
    return EvidenceArtifactRegistryReport(
        status="complete",
        run_date="2026-04-29",
        scan_roots=("/tmp",),
        artifact_records=records,
        missing_artifact_types=(),
        stale_artifact_ids=(),
        invalid_artifact_ids=(),
        coverage_by_phase=(("P22", 1.0),),
        coverage_by_family=(("factor_family.quality", 1.0),),
        next_actions=(),
        warnings=(),
    )


def _policy() -> EdgeReviewPolicy:
    return EdgeReviewPolicy(
        minimum_observation_count=20,
        require_net_return_basis=True,
        require_execution_realism=True,
    )


def test_missing_p22_diagnostics_blocks_factor_review():
    report = build_signal_family_edge_review(
        SignalFamilyEdgeReviewRequest(
            family_namespace="factor_family.quality",
            family_type="factor_family",
            registry_report=_registry(()),
            policy=_policy(),
        )
    )
    assert report.status == "blocked_missing_evidence"
    assert "missing_artifact:p22_validity_report" in report.missing_artifacts


def test_gross_only_edge_is_not_ready_for_human_review():
    report = build_signal_family_edge_review(
        SignalFamilyEdgeReviewRequest(
            family_namespace="factor_family.quality",
            family_type="factor_family",
            registry_report=_registry((
                _record("p22_validity_report", "P22", details={
                    "return_basis": "gross_return_pct",
                    "observation_count": 100,
                    "net_ic_positive": False,
                }),
                _record("p28_execution_realism_report", "P28"),
            )),
            policy=_policy(),
        )
    )
    assert report.status == "blocked_integrity_failure"
    assert "net_return_basis_required" in report.integrity_blockers


def test_lookahead_blocker_blocks_review():
    report = build_signal_family_edge_review(
        SignalFamilyEdgeReviewRequest(
            family_namespace="factor_family.quality",
            family_type="factor_family",
            registry_report=_registry((
                _record("p22_validity_report", "P22", details={
                    "return_basis": "net_return_pct",
                    "observation_count": 100,
                    "lookahead_blocker": True,
                }),
                _record("p28_execution_realism_report", "P28"),
            )),
            policy=_policy(),
        )
    )
    assert report.status == "blocked_integrity_failure"
    assert "lookahead_blocker_present" in report.integrity_blockers


def test_execution_cost_blocker_blocks_positive_review():
    report = build_signal_family_edge_review(
        SignalFamilyEdgeReviewRequest(
            family_namespace="factor_family.quality",
            family_type="factor_family",
            registry_report=_registry((
                _record("p22_validity_report", "P22", details={
                    "return_basis": "net_return_pct",
                    "observation_count": 100,
                    "net_ic_positive": True,
                }),
                _record("p28_execution_realism_report", "P28", details={
                    "stress_cost_exceeds_edge": True,
                }),
            )),
            policy=_policy(),
        )
    )
    assert report.status == "blocked_integrity_failure"
    assert "execution_cost_exceeds_edge" in report.execution_cost_warnings


def test_mature_net_evidence_ready_for_human_review():
    report = build_signal_family_edge_review(
        SignalFamilyEdgeReviewRequest(
            family_namespace="factor_family.quality",
            family_type="factor_family",
            registry_report=_registry((
                _record("p22_validity_report", "P22", details={
                    "return_basis": "net_return_pct",
                    "observation_count": 100,
                    "net_ic_positive": True,
                }),
                _record("p28_execution_realism_report", "P28", details={
                    "stress_cost_exceeds_edge": False,
                }),
            )),
            policy=_policy(),
        )
    )
    assert report.status == "ready_for_human_review"
    assert report.allowed_next_step == "prepare_human_review"


def test_shadow_model_promotion_forbidden_reason_present():
    report = build_signal_family_edge_review(
        SignalFamilyEdgeReviewRequest(
            family_namespace="shadow_meta_model.xgboost_dry_candidate",
            family_type="shadow_model_family",
            registry_report=_registry((
                _record("p22_validity_report", "P22", family_namespace="shadow_meta_model.xgboost_dry_candidate", details={
                    "return_basis": "net_return_pct",
                    "observation_count": 100,
                    "net_ic_positive": True,
                }),
                _record("p25_shadow_training_result", "P25", family_namespace="shadow_meta_model.xgboost_dry_candidate"),
                _record("p26_shadow_portfolio_report", "P26", family_namespace="shadow_meta_model.xgboost_dry_candidate"),
                _record("p28_execution_realism_report", "P28", family_namespace="shadow_meta_model.xgboost_dry_candidate"),
            )),
            policy=_policy(),
        )
    )
    assert "shadow_outputs_must_not_promote_to_production" in report.promotion_forbidden_reasons
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_signal_family_edge_review.py -q
```

Expected: import failure for `agent.research_v1.signal_family_edge_review`.

- [ ] **Step 3: Implement edge review module**

Create `agent/research_v1/signal_family_edge_review.py` with:

```python
"""P33 signal-family edge review based on governance artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agent.research_v1.evidence_artifact_registry import ArtifactRecord, EvidenceArtifactRegistryReport


ALLOWED_EDGE_REVIEW_STATUSES = frozenset({
    "blocked_missing_evidence",
    "blocked_integrity_failure",
    "shadow_observation_only",
    "ready_for_human_review",
    "rejected_for_now",
})

ALLOWED_EDGE_NEXT_STEPS = frozenset({
    "collect_more_evidence",
    "continue_shadow_observation",
    "prepare_human_review",
    "reject_for_now",
})


@dataclass(frozen=True)
class EdgeReviewPolicy:
    minimum_observation_count: int
    require_net_return_basis: bool = True
    require_execution_realism: bool = True


@dataclass(frozen=True)
class SignalFamilyEdgeReviewRequest:
    family_namespace: str
    family_type: str
    registry_report: EvidenceArtifactRegistryReport
    policy: EdgeReviewPolicy
    notes: str = ""


@dataclass(frozen=True)
class SignalFamilyEdgeReviewReport:
    family_namespace: str
    family_type: str
    status: str
    edge_evidence_summary: str
    risk_evidence_summary: str
    integrity_blockers: tuple[str, ...]
    missing_artifacts: tuple[str, ...]
    degradation_warnings: tuple[str, ...]
    execution_cost_warnings: tuple[str, ...]
    allowed_next_step: str
    promotion_forbidden_reasons: tuple[str, ...]
    human_review_questions: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "family_namespace": self.family_namespace,
            "family_type": self.family_type,
            "status": self.status,
            "edge_evidence_summary": self.edge_evidence_summary,
            "risk_evidence_summary": self.risk_evidence_summary,
            "integrity_blockers": list(self.integrity_blockers),
            "missing_artifacts": list(self.missing_artifacts),
            "degradation_warnings": list(self.degradation_warnings),
            "execution_cost_warnings": list(self.execution_cost_warnings),
            "allowed_next_step": self.allowed_next_step,
            "promotion_forbidden_reasons": list(self.promotion_forbidden_reasons),
            "human_review_questions": list(self.human_review_questions),
        }
```

Also implement `build_signal_family_edge_review(request: SignalFamilyEdgeReviewRequest) -> SignalFamilyEdgeReviewReport`.

Implementation requirements:

- Filter registry records by exact `family_namespace`, but include records with empty family namespace only if no exact family-specific records exist for that artifact type.
- Require `p22_validity_report` for all family types.
- Require `p28_execution_realism_report` when policy requires execution realism.
- Require `p25_shadow_training_result` and `p26_shadow_portfolio_report` for `shadow_model_family`.
- Missing requirements produce `blocked_missing_evidence`.
- P22 details:
  - `return_basis` must equal `net_return_pct` when net basis required.
  - `lookahead_blocker` true blocks.
  - `source_audit_blocker` true blocks.
  - `observation_count` below policy minimum produces `shadow_observation_only`.
  - `net_ic_positive` false produces `shadow_observation_only`.
- P28 details:
  - `stress_cost_exceeds_edge` true blocks with execution warning.
- Shadow/model family reports always include `shadow_outputs_must_not_promote_to_production`.

- [ ] **Step 4: Run focused P33 tests**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_signal_family_edge_review.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit P33**

```bash
git add agent/research_v1/signal_family_edge_review.py tests/agent/research_v1/test_signal_family_edge_review.py
git commit -m "feat: add signal family edge review"
```

---

### Task 4: P34 Boss Governance Daily Brief

**Files:**
- Create: `agent/research_v1/boss_governance_brief.py`
- Test: `tests/agent/research_v1/test_boss_governance_brief.py`

- [ ] **Step 1: Write failing P34 tests**

Create `tests/agent/research_v1/test_boss_governance_brief.py` with:

```python
"""Tests for P34 boss governance daily brief."""

from __future__ import annotations

import json
from pathlib import Path

from agent.research_v1.boss_governance_brief import (
    BossGovernanceBriefRequest,
    build_boss_governance_daily_brief,
    write_boss_governance_daily_brief,
)
from agent.research_v1.daily_governance import DailyGovernanceResult
from agent.research_v1.evidence_artifact_registry import EvidenceArtifactRegistryReport
from agent.research_v1.evidence_generation_dry_run import ControlledEvidenceGenerationReport
from agent.research_v1.signal_family_edge_review import SignalFamilyEdgeReviewReport


def _daily_result(status: str = "completed") -> DailyGovernanceResult:
    return DailyGovernanceResult(
        status=status,
        run_date="2026-04-29",
        output_dir="/tmp/output/governance/2026-04-29",
        version_status="ready_for_human_review",
        family_count=1,
        human_review_candidates=("factor_family.quality",),
        blocked_items=(),
        warnings=(),
    )


def _registry_report(status: str = "complete") -> EvidenceArtifactRegistryReport:
    return EvidenceArtifactRegistryReport(
        status=status,
        run_date="2026-04-29",
        scan_roots=("/tmp",),
        artifact_records=(),
        missing_artifact_types=("p25_shadow_training_result",) if status != "complete" else (),
        stale_artifact_ids=(),
        invalid_artifact_ids=(),
        coverage_by_phase=(("P31", 1.0),),
        coverage_by_family=(("factor_family.quality", 1.0),),
        next_actions=("collect_missing_artifacts",) if status != "complete" else (),
        warnings=(),
    )


def _generation_report() -> ControlledEvidenceGenerationReport:
    return ControlledEvidenceGenerationReport(
        status="dry_run_complete",
        run_date="2026-04-29",
        requested_artifacts=(),
        allowed_requests=(),
        blocked_requests=(),
        required_inputs_by_artifact=(),
        dry_run_manifest_path="",
        next_actions=(),
        warnings=(),
    )


def _edge_report(status: str = "ready_for_human_review") -> SignalFamilyEdgeReviewReport:
    return SignalFamilyEdgeReviewReport(
        family_namespace="factor_family.quality",
        family_type="factor_family",
        status=status,
        edge_evidence_summary="net evidence positive",
        risk_evidence_summary="execution cost acceptable",
        integrity_blockers=(),
        missing_artifacts=(),
        degradation_warnings=(),
        execution_cost_warnings=(),
        allowed_next_step="prepare_human_review",
        promotion_forbidden_reasons=(),
        human_review_questions=("Review quality family evidence.",),
    )


def test_brief_includes_system_health_and_review_candidate():
    brief = build_boss_governance_daily_brief(
        BossGovernanceBriefRequest(
            run_date="2026-04-29",
            daily_governance_result=_daily_result(),
            registry_report=_registry_report(),
            generation_report=_generation_report(),
            edge_review_reports=(_edge_report(),),
        )
    )
    assert brief.overall_status == "governance_ready_for_review"
    assert "factor_family.quality" in brief.family_review_candidates
    assert "ready_for_human_review" in brief.system_health_summary


def test_incomplete_registry_produces_governance_incomplete():
    brief = build_boss_governance_daily_brief(
        BossGovernanceBriefRequest(
            run_date="2026-04-29",
            daily_governance_result=_daily_result(),
            registry_report=_registry_report(status="incomplete_missing_artifacts"),
            generation_report=_generation_report(),
            edge_review_reports=(_edge_report(status="shadow_observation_only"),),
        )
    )
    assert brief.overall_status == "governance_incomplete"
    assert "p25_shadow_training_result" in brief.missing_evidence_summary


def test_degraded_daily_input_produces_governance_degraded():
    brief = build_boss_governance_daily_brief(
        BossGovernanceBriefRequest(
            run_date="2026-04-29",
            daily_governance_result=_daily_result(status="governance_degraded"),
            registry_report=_registry_report(),
            generation_report=_generation_report(),
            edge_review_reports=(),
        )
    )
    assert brief.overall_status == "governance_degraded"


def test_brief_markdown_excludes_trading_instructions(tmp_path: Path):
    brief = build_boss_governance_daily_brief(
        BossGovernanceBriefRequest(
            run_date="2026-04-29",
            daily_governance_result=_daily_result(),
            registry_report=_registry_report(),
            generation_report=_generation_report(),
            edge_review_reports=(_edge_report(),),
        )
    )
    paths = write_boss_governance_daily_brief(brief, tmp_path / "2026-04-29")
    text = paths["markdown"].read_text(encoding="utf-8").lower()
    forbidden = ("buy this now", "sell this now", "production approved", "follow this trade", "guaranteed edge")
    assert not any(term in text for term in forbidden)
    parsed = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert parsed["overall_status"] == "governance_ready_for_review"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_boss_governance_brief.py -q
```

Expected: import failure for `agent.research_v1.boss_governance_brief`.

- [ ] **Step 3: Implement boss brief module**

Create `agent/research_v1/boss_governance_brief.py` with:

```python
"""P34 boss-facing governance daily brief."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent.research_v1.daily_governance import DailyGovernanceResult
from agent.research_v1.evidence_artifact_registry import EvidenceArtifactRegistryReport
from agent.research_v1.evidence_generation_dry_run import ControlledEvidenceGenerationReport
from agent.research_v1.signal_family_edge_review import SignalFamilyEdgeReviewReport


ALLOWED_BOSS_BRIEF_STATUSES = frozenset({
    "governance_ready_for_review",
    "governance_incomplete",
    "governance_degraded",
    "no_review_candidates",
})

FORBIDDEN_BOSS_BRIEF_TERMS = (
    "buy this now",
    "sell this now",
    "production approved",
    "model promoted",
    "follow this trade",
    "guaranteed edge",
)


@dataclass(frozen=True)
class BossGovernanceBriefRequest:
    run_date: str
    daily_governance_result: DailyGovernanceResult
    registry_report: EvidenceArtifactRegistryReport
    generation_report: ControlledEvidenceGenerationReport
    edge_review_reports: tuple[SignalFamilyEdgeReviewReport, ...]


@dataclass(frozen=True)
class BossGovernanceDailyBrief:
    run_date: str
    overall_status: str
    system_health_summary: str
    missing_evidence_summary: tuple[str, ...]
    stale_evidence_summary: tuple[str, ...]
    family_review_candidates: tuple[str, ...]
    families_in_shadow_observation: tuple[str, ...]
    blocked_families: tuple[str, ...]
    risk_warnings: tuple[str, ...]
    next_actions: tuple[str, ...]
    forbidden_actions_disclaimer: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_date": self.run_date,
            "overall_status": self.overall_status,
            "system_health_summary": self.system_health_summary,
            "missing_evidence_summary": list(self.missing_evidence_summary),
            "stale_evidence_summary": list(self.stale_evidence_summary),
            "family_review_candidates": list(self.family_review_candidates),
            "families_in_shadow_observation": list(self.families_in_shadow_observation),
            "blocked_families": list(self.blocked_families),
            "risk_warnings": list(self.risk_warnings),
            "next_actions": list(self.next_actions),
            "forbidden_actions_disclaimer": self.forbidden_actions_disclaimer,
        }
```

Also implement `build_boss_governance_daily_brief(request: BossGovernanceBriefRequest) -> BossGovernanceDailyBrief`.

Also implement `write_boss_governance_daily_brief(brief: BossGovernanceDailyBrief, output_dir: Path) -> dict[str, Path]`.

Implementation requirements:

- If daily governance status is `governance_degraded`, overall status is `governance_degraded`.
- Else if registry status is not `complete`, overall status is `governance_incomplete`.
- Else if any edge review is `ready_for_human_review`, overall status is `governance_ready_for_review`.
- Else overall status is `no_review_candidates`.
- Human review candidates are edge reports with status `ready_for_human_review`.
- Shadow observation list is edge reports with status `shadow_observation_only`.
- Blocked family list is edge reports whose status starts with `blocked_` or equals `rejected_for_now`.
- Markdown must include the disclaimer: `This brief is governance-only and does not approve production or instruct trades.`
- `write_boss_governance_daily_brief()` writes `boss_daily_brief.json` and `boss_daily_brief.md` only.

- [ ] **Step 4: Run focused P34 tests**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_boss_governance_brief.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit P34**

```bash
git add agent/research_v1/boss_governance_brief.py tests/agent/research_v1/test_boss_governance_brief.py
git commit -m "feat: add boss governance daily brief"
```

---

### Task 5: P32-P34 Regression And P20-P34 Governance Chain

**Files:**
- Verify only. No file edits expected unless a regression exposes a real bug in P32-P34 files.

- [ ] **Step 1: Run P32-P34 focused tests**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest \
  tests/agent/research_v1/test_evidence_artifact_registry.py \
  tests/agent/research_v1/test_evidence_generation_dry_run.py \
  tests/agent/research_v1/test_signal_family_edge_review.py \
  tests/agent/research_v1/test_boss_governance_brief.py \
  -q
```

Expected: all tests pass.

- [ ] **Step 2: Run P31-P34 governance loop tests**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest \
  tests/agent/research_v1/test_version_readiness.py \
  tests/agent/research_v1/test_signal_family_readiness.py \
  tests/agent/research_v1/test_daily_governance.py \
  tests/agent/research_v1/test_evidence_artifact_registry.py \
  tests/agent/research_v1/test_evidence_generation_dry_run.py \
  tests/agent/research_v1/test_signal_family_edge_review.py \
  tests/agent/research_v1/test_boss_governance_brief.py \
  -q
```

Expected: all tests pass. Existing benign `PytestCollectionWarning` for `TestEvidence` may remain.

- [ ] **Step 3: Run full P20-P34 governance chain**

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
  tests/agent/research_v1/test_evidence_artifact_registry.py \
  tests/agent/research_v1/test_evidence_generation_dry_run.py \
  tests/agent/research_v1/test_signal_family_edge_review.py \
  tests/agent/research_v1/test_boss_governance_brief.py \
  -q
```

Expected: all tests pass. P20-P31 baseline before P32-P34 was `516 passed`; final count should be higher by the new P32-P34 focused tests.

- [ ] **Step 4: Boundary scan**

Run:

```bash
rg -n "broker|auto.?trad|place_order|production_config|calibration_config|canonical factor|canonical_factor|approved_production|buy this now|sell this now|follow this trade|guaranteed edge" \
  agent/research_v1/evidence_artifact_registry.py \
  agent/research_v1/evidence_generation_dry_run.py \
  agent/research_v1/signal_family_edge_review.py \
  agent/research_v1/boss_governance_brief.py \
  tests/agent/research_v1/test_evidence_artifact_registry.py \
  tests/agent/research_v1/test_evidence_generation_dry_run.py \
  tests/agent/research_v1/test_signal_family_edge_review.py \
  tests/agent/research_v1/test_boss_governance_brief.py
```

Expected: no matches except test assertions that forbidden boss-brief strings are excluded.

- [ ] **Step 5: Diff hygiene**

Run:

```bash
git diff --check
git status --short --branch
```

Expected: no whitespace errors; branch shows only intentional committed work.

- [ ] **Step 6: Commit any regression fix if needed**

If Task 5 required any code changes, commit them:

```bash
git add agent/research_v1 tests/agent/research_v1
git commit -m "test: verify p32 p34 governance regression"
```

If no code changes were needed, do not create an empty commit.

---

## Known Existing Test Gap

`tests/agent/research_v1/test_doc_standards.py` has known pre-existing failures unrelated to P32-P34:

- `agent/research_v1/README.md` missing a required Data Flow / How It Fits heading.
- `agent/research_v1/report_templates/` has Python files but no `README.md`.

Do not fix those documentation gaps in this plan unless the user explicitly expands scope.

---

## Self-Review Checklist

- P32-A spec sections 5 and 10.1 map to Task 1.
- P32-B spec sections 6 and 10.2 map to Task 2.
- P33 spec sections 7 and 10.3 map to Task 3.
- P34 spec sections 8 and 10.4 map to Task 4.
- End-to-end regression and boundary checks map to Task 5.
- P32-B is dry-run only and rejects actual execution.
- No task runs P22/P25/P28 jobs.
- No task mutates production config.
- No task promotes shadow outputs.
- No task adds CLI, viewer, scheduling, notifications, or broker integration.
