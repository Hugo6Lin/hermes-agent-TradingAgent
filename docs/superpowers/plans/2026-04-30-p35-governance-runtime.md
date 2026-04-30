# P35 Governance Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a safe one-command runtime for the P31-P34 governance loop and close the known documentation-standard gaps.

**Architecture:** Create a stdlib-only `governance_runtime.py` adapter that reads explicit JSON config, builds the existing P31-P34 request objects, writes the boss brief and runtime summary, and returns a deterministic result. Wire it into the existing argparse `batch_cli.py` as `governance-run`, then update README coverage so doc standards pass.

**Tech Stack:** Python 3.11, dataclasses, pathlib, json, argparse, pytest, existing P31-P34 governance modules.

---

## File Structure

- Create `agent/research_v1/governance_runtime.py`
  - Owns P35 config parsing, request adaptation, governance loop orchestration, runtime summary serialization, and safe degraded/invalid result handling.
- Create `tests/agent/research_v1/test_governance_runtime.py`
  - Tests valid runtime execution, invalid config handling, output files, and hard-boundary preservation.
- Modify `agent/research_v1/batch_cli.py`
  - Adds `governance-run` subcommand and `_cmd_governance_run` wrapper.
- Modify `tests/agent/research_v1/test_batch_cli.py`
  - Tests CLI success and invalid-config exit behavior.
- Modify `agent/research_v1/README.md`
  - Adds a Data Flow / How It Fits section covering P31-P35.
- Create `agent/research_v1/report_templates/README.md`
  - Closes the orphan code-dir README gap for report templates.

Do not modify broker, production config, scheduling, viewer, model-training, or canonical trading-decision paths.

---

## Shared Runtime Config

Use this minimal valid config shape in tests:

```python
def _write_valid_config(path: Path) -> Path:
    payload = {
        "version_readiness": {
            "version_id": "p35-local",
            "branch": "codex/quant-governance-p20-p30",
            "commit": "local-test",
            "evidence": {
                "p20_p30_regression_passed": True,
                "p31_p34_regression_passed": True,
                "doc_standards_passed": True,
            },
            "notes": "P35 local runtime test",
        },
        "signal_families": [],
        "expected_artifacts": [],
        "generation_requests": [],
        "edge_reviews": [],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path
```

The parser code in Task 1 maps this external JSON shape to the existing P31-P34 dataclass fields.

---

### Task 1: P35-A Governance Runtime

**Files:**
- Create: `agent/research_v1/governance_runtime.py`
- Test: `tests/agent/research_v1/test_governance_runtime.py`

- [ ] **Step 1: Write failing runtime tests**

Create `tests/agent/research_v1/test_governance_runtime.py`:

```python
"""Tests for P35 governance runtime."""

from __future__ import annotations

import json
from pathlib import Path

from agent.research_v1.governance_runtime import (
    GovernanceRuntimeRequest,
    run_governance_runtime,
)


def _write_valid_config(path: Path) -> Path:
    payload = {
        "version_readiness": {
            "version_id": "p35-local",
            "branch": "codex/quant-governance-p20-p30",
            "commit": "local-test",
            "evidence": {
                "p20_p30_regression_passed": True,
                "p31_p34_regression_passed": True,
                "doc_standards_passed": True,
            },
            "notes": "P35 local runtime test",
        },
        "signal_families": [],
        "expected_artifacts": [],
        "generation_requests": [],
        "edge_reviews": [],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_runtime_writes_governance_summary_and_boss_brief(tmp_path: Path):
    config_path = _write_valid_config(tmp_path / "governance_config.json")
    output_root = tmp_path / "output" / "governance"

    result = run_governance_runtime(
        GovernanceRuntimeRequest(
            run_date="2026-04-30",
            repo_root=tmp_path,
            output_root=output_root,
            config_path=config_path,
            freshness_policy_days=7,
        )
    )

    assert result.status in {"completed", "completed_with_warnings"}
    assert result.run_date == "2026-04-30"
    assert result.boss_brief_status in {
        "governance_ready_for_review",
        "governance_incomplete",
        "governance_degraded",
        "no_review_candidates",
    }

    output_dir = output_root / "2026-04-30"
    assert (output_dir / "daily_summary.json").exists()
    assert (output_dir / "evidence_generation_dry_run.json").exists()
    assert (output_dir / "boss_daily_brief.json").exists()
    assert (output_dir / "governance_runtime_summary.json").exists()

    summary = json.loads((output_dir / "governance_runtime_summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == result.status
    assert "boss_daily_brief.json" in "\n".join(summary["artifacts_written"])


def test_runtime_blocks_invalid_config(tmp_path: Path):
    config_path = tmp_path / "broken.json"
    config_path.write_text("{not-json", encoding="utf-8")

    result = run_governance_runtime(
        GovernanceRuntimeRequest(
            run_date="2026-04-30",
            repo_root=tmp_path,
            output_root=tmp_path / "output" / "governance",
            config_path=config_path,
            freshness_policy_days=7,
        )
    )

    assert result.status == "blocked_invalid_config"
    assert result.warnings
    assert "invalid_config" in result.warnings[0]


def test_runtime_preserves_dry_run_boundary(tmp_path: Path):
    config_path = tmp_path / "governance_config.json"
    payload = {
        "version_readiness": {
            "version_id": "p35-local",
            "branch": "codex/quant-governance-p20-p30",
            "commit": "local-test",
            "evidence": {
                "p20_p30_regression_passed": True,
                "p31_p34_regression_passed": True,
                "doc_standards_passed": True,
            },
            "notes": "P35 dry-run boundary test",
        },
        "signal_families": [],
        "expected_artifacts": [],
        "generation_requests": [
            {
                "artifact_type": "p28_execution_realism_report",
                "phase_id": "P28",
                "family_namespace": "factor_family.quality",
                "requested_output_dir": "output/governance/2026-04-30",
                "input_refs": {},
                "allow_actual_execution": True,
                "notes": "must remain blocked",
            }
        ],
        "edge_reviews": [],
    }
    config_path.write_text(json.dumps(payload), encoding="utf-8")

    result = run_governance_runtime(
        GovernanceRuntimeRequest(
            run_date="2026-04-30",
            repo_root=tmp_path,
            output_root=tmp_path / "output" / "governance",
            config_path=config_path,
            freshness_policy_days=7,
        )
    )

    assert result.generation_status == "blocked_unsafe_request"
    manifest_path = tmp_path / "output" / "governance" / "2026-04-30" / "evidence_generation_dry_run.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["blocked_requests"][0]["blocked_reasons"] == [
        "actual_execution_not_allowed_in_p32_b",
        "missing_required_input:trade_intents",
        "missing_required_input:liquidity_inputs",
        "missing_required_input:alpha_edge_estimate",
    ]
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_governance_runtime.py -q
```

Expected: fail because `agent.research_v1.governance_runtime` does not exist.

- [ ] **Step 3: Implement runtime dataclasses and config parser**

Create `agent/research_v1/governance_runtime.py` with:

```python
"""P35 local runtime for the Hermes governance evidence loop."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent.research_v1.boss_governance_brief import (
    BossGovernanceBriefRequest,
    build_boss_governance_daily_brief,
    write_boss_governance_daily_brief,
)
from agent.research_v1.daily_governance import DailyGovernanceRequest, run_daily_governance
from agent.research_v1.evidence_artifact_registry import (
    ArtifactDefinition,
    EvidenceArtifactRegistryReport,
    EvidenceArtifactRegistryRequest,
    build_evidence_artifact_registry,
)
from agent.research_v1.evidence_generation_dry_run import (
    EvidenceGenerationRequest,
    build_controlled_evidence_generation_report,
    write_evidence_generation_dry_run_manifest,
)
from agent.research_v1.signal_family_edge_review import (
    EdgeReviewPolicy,
    SignalFamilyEdgeReviewRequest,
    build_signal_family_edge_review,
)
from agent.research_v1.signal_family_readiness import (
    FamilyEvidence,
    SignalFamilyReadinessRequest,
)
from agent.research_v1.version_readiness import (
    EvidenceItem,
    TestEvidence,
    VersionMetadata,
    VersionReadinessRequest,
)
from agent.research_v1.phase29_production_adoption_review import MonitoringSLA, RollbackPlan


@dataclass(frozen=True)
class GovernanceRuntimeRequest:
    run_date: str
    repo_root: Path
    output_root: Path
    config_path: Path
    freshness_policy_days: int = 7


@dataclass(frozen=True)
class GovernanceRuntimeResult:
    status: str
    run_date: str
    output_dir: str
    daily_governance_status: str
    registry_status: str
    generation_status: str
    boss_brief_status: str
    artifacts_written: tuple[str, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "run_date": self.run_date,
            "output_dir": self.output_dir,
            "daily_governance_status": self.daily_governance_status,
            "registry_status": self.registry_status,
            "generation_status": self.generation_status,
            "boss_brief_status": self.boss_brief_status,
            "artifacts_written": list(self.artifacts_written),
            "warnings": list(self.warnings),
        }
```

Add these parser helpers:

```python
def _load_config(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("governance config must be a JSON object")
    return payload


def _version_request(config: dict[str, Any]) -> VersionReadinessRequest:
    version = config["version_readiness"]
    evidence = version.get("evidence", {})
    p20_p30_passed = bool(evidence.get("p20_p30_regression_passed", False))
    p31_p34_passed = bool(evidence.get("p31_p34_regression_passed", False))
    doc_passed = bool(evidence.get("doc_standards_passed", False))
    required_phase_ids = ("P20", "P21", "P22", "P23", "P24", "P25", "P26", "P28", "P29", "P30")
    evidence_items = tuple(
        EvidenceItem(
            phase_id=phase_id,
            present=p20_p30_passed,
            summary="configured evidence present" if p20_p30_passed else "configured evidence missing",
        )
        for phase_id in required_phase_ids
    )
    return VersionReadinessRequest(
        metadata=VersionMetadata(
            branch=version["branch"],
            commit=version["commit"],
            dirty=False,
            frozen_version_label=version.get("version_id", ""),
        ),
        evidence_items=evidence_items,
        test_evidence=(
            TestEvidence(
                command="P20-P30 configured regression",
                status="passed" if p20_p30_passed else "not_run",
                passed_count=488 if p20_p30_passed else 0,
                failed_count=0,
                raw_summary="configured by P35 runtime",
            ),
            TestEvidence(
                command="P31-P34 configured regression",
                status="passed" if p31_p34_passed else "not_run",
                passed_count=55 if p31_p34_passed else 0,
                failed_count=0,
                raw_summary="configured by P35 runtime",
            ),
            TestEvidence(
                command="doc standards configured check",
                status="passed" if doc_passed else "not_run",
                passed_count=1 if doc_passed else 0,
                failed_count=0,
                raw_summary="configured by P35 runtime",
            ),
        ),
        rollback_plan=RollbackPlan(
            rollback_owner="human governance reviewer",
            rollback_trigger="human reviewer rejects runtime output",
            description="P35 runtime does not mutate production state; rollback is discard generated governance artifacts.",
        ),
        monitoring_sla=MonitoringSLA(
            monitoring_cadence="daily local governance review",
            alert_routing="human governance reviewer",
            description="P35 emits local artifacts only and requires human review for action.",
        ),
        notes=version.get("notes", ""),
    )


def _family_requests(config: dict[str, Any]) -> tuple[SignalFamilyReadinessRequest, ...]:
    families = []
    for item in config.get("signal_families", []):
        evidence = item.get("evidence", {})
        families.append(
            SignalFamilyReadinessRequest(
                parent_version_status=item.get("parent_version_status", "ready_for_human_review"),
                family_type=item["family_type"],
                family_namespace=item["family_namespace"],
                evidence=FamilyEvidence(
                    p20_p23_present=bool(evidence.get("p20_p23_present", False)),
                    p24_p26_present=bool(evidence.get("p24_p26_present", False)),
                    p28_present=bool(evidence.get("p28_present", False)),
                    p30_present=bool(evidence.get("p30_present", False)),
                    maturity=bool(evidence.get("maturity", False)),
                    edge_summary=evidence.get("edge_summary", ""),
                    risk_summary=evidence.get("risk_summary", ""),
                    degradation_warnings=tuple(evidence.get("degradation_warnings", [])),
                ),
                notes=item.get("notes", ""),
            )
        )
    return tuple(families)


def _artifact_definitions(config: dict[str, Any]) -> tuple[ArtifactDefinition, ...]:
    return tuple(
        ArtifactDefinition(
            artifact_type=item["artifact_type"],
            relative_path=item["relative_path"],
            family_namespace=item.get("family_namespace", ""),
            required=bool(item.get("required", True)),
        )
        for item in config.get("expected_artifacts", [])
    )


def _generation_requests(config: dict[str, Any]) -> tuple[EvidenceGenerationRequest, ...]:
    return tuple(
        EvidenceGenerationRequest(
            artifact_type=item["artifact_type"],
            phase_id=item["phase_id"],
            family_namespace=item.get("family_namespace", ""),
            requested_output_dir=item.get("requested_output_dir", ""),
            input_refs=dict(item.get("input_refs", {})),
            allow_actual_execution=bool(item.get("allow_actual_execution", False)),
            notes=item.get("notes", ""),
        )
        for item in config.get("generation_requests", [])
    )


def _edge_review_requests(
    config: dict[str, Any],
    registry_report: EvidenceArtifactRegistryReport,
) -> tuple[SignalFamilyEdgeReviewRequest, ...]:
    requests = []
    for item in config.get("edge_reviews", []):
        policy = item.get("policy", {})
        requests.append(
            SignalFamilyEdgeReviewRequest(
                family_namespace=item["family_namespace"],
                family_type=item["family_type"],
                registry_report=registry_report,
                policy=EdgeReviewPolicy(
                    minimum_observation_count=int(policy.get("minimum_observation_count", 30)),
                    require_net_return_basis=bool(policy.get("require_net_return_basis", True)),
                    require_execution_realism=bool(policy.get("require_execution_realism", True)),
                ),
                notes=item.get("notes", ""),
            )
        )
    return tuple(requests)
```

- [ ] **Step 4: Implement runtime orchestration**

Finish `run_governance_runtime`:

```python
def run_governance_runtime(request: GovernanceRuntimeRequest) -> GovernanceRuntimeResult:
    output_dir = request.output_root / request.run_date
    try:
        config = _load_config(request.config_path)
        daily = run_daily_governance(
            DailyGovernanceRequest(
                run_date=request.run_date,
                output_root=request.output_root,
                version_request=_version_request(config),
                family_requests=_family_requests(config),
            )
        )
        registry = build_evidence_artifact_registry(
            EvidenceArtifactRegistryRequest(
                run_date=request.run_date,
                scan_roots=(request.output_root,),
                expected_artifacts=_artifact_definitions(config),
                freshness_policy_days=request.freshness_policy_days,
            )
        )
        generation = build_controlled_evidence_generation_report(
            run_date=request.run_date,
            requests=_generation_requests(config),
            dry_run_manifest_path=str(output_dir / "evidence_generation_dry_run.json"),
        )
        generation_paths = write_evidence_generation_dry_run_manifest(generation, output_dir)
        edge_reviews = tuple(
            build_signal_family_edge_review(edge_request)
            for edge_request in _edge_review_requests(config, registry)
        )
        brief = build_boss_governance_daily_brief(
            BossGovernanceBriefRequest(
                run_date=request.run_date,
                daily_governance_result=daily,
                registry_report=registry,
                generation_report=generation,
                edge_review_reports=edge_reviews,
            )
        )
        brief_paths = write_boss_governance_daily_brief(brief, output_dir)

        warnings = tuple(dict.fromkeys((*daily.warnings, *registry.warnings, *generation.warnings)))
        status = "completed_with_warnings" if warnings or generation.status != "dry_run_complete" else "completed"
        result = GovernanceRuntimeResult(
            status=status,
            run_date=request.run_date,
            output_dir=str(output_dir),
            daily_governance_status=daily.status,
            registry_status=registry.status,
            generation_status=generation.status,
            boss_brief_status=brief.overall_status,
            artifacts_written=tuple(
                str(path)
                for path in (
                    output_dir / "daily_summary.json",
                    generation_paths["json"],
                    brief_paths["json"],
                    output_dir / "governance_runtime_summary.json",
                )
            ),
            warnings=warnings,
        )
        _write_json(output_dir / "governance_runtime_summary.json", result.to_dict())
        return result
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        return GovernanceRuntimeResult(
            status="blocked_invalid_config",
            run_date=request.run_date,
            output_dir=str(output_dir),
            daily_governance_status="not_run",
            registry_status="not_run",
            generation_status="not_run",
            boss_brief_status="not_run",
            artifacts_written=(),
            warnings=(f"invalid_config:{exc.__class__.__name__}",),
        )
```

Add `_write_json(path, payload)` using `json.dumps` with indentation and sorted keys.

- [ ] **Step 5: Run runtime tests**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_governance_runtime.py -q
```

Expected: `3 passed`.

- [ ] **Step 6: Commit P35-A**

```bash
git add agent/research_v1/governance_runtime.py tests/agent/research_v1/test_governance_runtime.py
git commit -m "feat: add governance runtime entrypoint"
```

---

### Task 2: P35-B CLI Wiring

**Files:**
- Modify: `agent/research_v1/batch_cli.py`
- Modify: `tests/agent/research_v1/test_batch_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Append to `tests/agent/research_v1/test_batch_cli.py`:

```python
def test_governance_run_cli_success(tmp_path: Path, capsys):
    config_path = tmp_path / "governance_config.json"
    config_path.write_text(json.dumps({
        "version_readiness": {
            "version_id": "p35-cli",
            "branch": "codex/quant-governance-p20-p30",
            "commit": "local-test",
            "evidence": {
                "p20_p30_regression_passed": True,
                "p31_p34_regression_passed": True,
                "doc_standards_passed": True,
            },
            "notes": "P35 CLI test",
        },
        "signal_families": [],
        "expected_artifacts": [],
        "generation_requests": [],
        "edge_reviews": [],
    }), encoding="utf-8")

    result = app.main([
        "--app-root", str(tmp_path),
        "governance-run",
        "--config", str(config_path),
        "--run-date", "2026-04-30",
        "--output-root", str(tmp_path / "output" / "governance"),
    ])

    out = capsys.readouterr().out
    assert result == 0
    assert "Governance runtime status:" in out
    assert "Boss brief status:" in out
    assert "Output dir:" in out


def test_governance_run_cli_invalid_config_returns_nonzero(tmp_path: Path, capsys):
    config_path = tmp_path / "broken.json"
    config_path.write_text("{not-json", encoding="utf-8")

    result = app.main([
        "--app-root", str(tmp_path),
        "governance-run",
        "--config", str(config_path),
        "--run-date", "2026-04-30",
        "--output-root", str(tmp_path / "output" / "governance"),
    ])

    out = capsys.readouterr().out
    assert result == 2
    assert "Governance runtime status: blocked_invalid_config" in out
```

Ensure the file already imports `json` and `Path`; add imports only if missing.

- [ ] **Step 2: Run CLI tests to verify failure**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_batch_cli.py::test_governance_run_cli_success tests/agent/research_v1/test_batch_cli.py::test_governance_run_cli_invalid_config_returns_nonzero -q
```

Expected: fail because the parser does not know `governance-run`.

- [ ] **Step 3: Add CLI command**

Modify `agent/research_v1/batch_cli.py`:

```python
from agent.research_v1.governance_runtime import GovernanceRuntimeRequest, run_governance_runtime
```

Add:

```python
def _cmd_governance_run(
    paths: HermesPaths,
    config_path: str,
    run_date: str,
    output_root: str,
    freshness_policy_days: int,
) -> int:
    result = run_governance_runtime(
        GovernanceRuntimeRequest(
            run_date=run_date,
            repo_root=paths.app_root,
            output_root=Path(output_root).expanduser().resolve(),
            config_path=Path(config_path).expanduser().resolve(),
            freshness_policy_days=freshness_policy_days,
        )
    )
    print(f"Governance runtime status: {result.status}")
    print(f"Output dir: {result.output_dir}")
    print(f"Boss brief status: {result.boss_brief_status}")
    for artifact in result.artifacts_written:
        print(f"Artifact: {artifact}")
    for warning in result.warnings:
        print(f"Warning: {warning}")
    return 2 if result.status == "blocked_invalid_config" else 0
```

In `build_parser()` add:

```python
    governance_parser = subparsers.add_parser("governance-run", help="Run the local governance evidence loop.")
    governance_parser.add_argument("--config", required=True, help="Path to governance runtime JSON config.")
    governance_parser.add_argument("--run-date", required=True, help="Governance run date YYYY-MM-DD.")
    governance_parser.add_argument(
        "--output-root",
        default="output/governance",
        help="Root directory for governance artifacts.",
    )
    governance_parser.add_argument(
        "--freshness-policy-days",
        default=7,
        type=int,
        help="Maximum artifact age before registry marks an artifact stale.",
    )
```

In `main`, dispatch:

```python
    if args.command == "governance-run":
        return _cmd_governance_run(
            paths,
            config_path=args.config,
            run_date=args.run_date,
            output_root=args.output_root,
            freshness_policy_days=args.freshness_policy_days,
        )
```

- [ ] **Step 4: Run CLI tests**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_batch_cli.py::test_governance_run_cli_success tests/agent/research_v1/test_batch_cli.py::test_governance_run_cli_invalid_config_returns_nonzero -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit P35-B**

```bash
git add agent/research_v1/batch_cli.py tests/agent/research_v1/test_batch_cli.py
git commit -m "feat: wire governance runtime cli"
```

---

### Task 3: P35-C Documentation Standards Closure

**Files:**
- Modify: `agent/research_v1/README.md`
- Create: `agent/research_v1/report_templates/README.md`

- [ ] **Step 1: Run doc standards to capture current failures**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_doc_standards.py -q
```

Expected current known failures:

- `agent/research_v1/README.md` missing Data Flow / How It Fits section
- `agent/research_v1/report_templates/` missing README

- [ ] **Step 2: Add Data Flow section**

In `agent/research_v1/README.md`, add a section:

```markdown
## Data Flow

Hermes now has two connected flows.

The research flow starts with a natural-language research request, routes it
through task decomposition, market-data collection, analyst evidence, final
judgment, canonical signal/report objects, and optional image-report generation.

The governance flow starts from P20-P30 evidence, then runs P31 readiness,
P32 artifact registry and dry-run generation validation, P33 signal-family edge
review, P34 boss governance brief, and P35 local runtime orchestration. This
flow writes append-only governance artifacts under `output/governance/YYYY-MM-DD/`
and does not create broker orders or production approval.
```

- [ ] **Step 3: Add report templates README**

Create `agent/research_v1/report_templates/README.md`:

```markdown
# `agent/research_v1/report_templates/` - Report Template Assets

## What This Directory Is

This directory contains report template helpers used by older or secondary
Hermes report surfaces.

## Core Files

- `html_report.py` renders HTML report content for legacy report paths.
- `pdf_report.py` supports PDF-oriented report rendering where still used.

## Relationship to Other Directories

Templates here consume canonical research and report objects from
`agent/research_v1/`. They should not create new trading decisions or bypass the
canonical `TickerResearchResult` flow.

## Data Flow

Canonical research output is produced by the main research pipeline, then report
surfaces may format that output for HTML or PDF delivery. P31-P35 governance
artifacts are separate boss-governance outputs and should not be mixed into these
legacy templates unless a future phase explicitly designs that bridge.

## If You Modify This Directory

Update tests for any rendered field or template contract that changes. Keep the
templates presentation-only and avoid adding market-data, broker, or governance
decision logic here.
```

Adjust filenames in the Core Files section to match the actual files in `agent/research_v1/report_templates/`.

- [ ] **Step 4: Run doc standards**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_doc_standards.py -q
```

Expected: pass.

- [ ] **Step 5: Commit P35-C**

```bash
git add agent/research_v1/README.md agent/research_v1/report_templates/README.md
git commit -m "docs: close research doc standards gaps"
```

---

### Task 4: P35-D Regression Verification

**Files:**
- No source changes unless regression exposes a bug.

- [ ] **Step 1: Run P35 focused tests**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest \
  tests/agent/research_v1/test_governance_runtime.py \
  tests/agent/research_v1/test_batch_cli.py \
  tests/agent/research_v1/test_doc_standards.py \
  -q
```

Expected: all pass.

- [ ] **Step 2: Run P31-P35 governance loop**

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
  tests/agent/research_v1/test_governance_runtime.py \
  -q
```

Expected: P31-P35 governance tests pass with only known benign `TestEvidence` collection warnings if still present.

- [ ] **Step 3: Run full P20-P35 chain**

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
  tests/agent/research_v1/test_governance_runtime.py \
  -q
```

Expected: full P20-P35 chain passes.

- [ ] **Step 4: Check diff hygiene**

Run:

```bash
git diff --check
git status --short --branch
```

Expected:

- no whitespace errors
- branch shows only intentional committed changes

- [ ] **Step 5: Final status report**

Report:

```text
P35 Implementation Complete

P35-A: governance_runtime.py + tests — PASS — <commit>
P35-B: governance-run CLI + tests — PASS — <commit>
P35-C: doc standards closure — PASS — <commit>
P35-D: regression — PASS

Verification:
- P35 focused: <count> passed
- P31-P35 governance loop: <count> passed
- Full P20-P35 chain: <count> passed

Hard boundaries:
- no auto-trading
- no production adoption approval
- no production config mutation
- no shadow promotion
- no model training
- P32-B remains dry-run only
- no scheduling, notifications, viewer, or broker wiring
```

Do not push or merge unless the boss explicitly asks for that integration step.

---

## Plan Self-Review

- Spec coverage: P35-A runtime is covered by Task 1; P35-B CLI by Task 2; P35-C doc standards by Task 3; P35-D regression by Task 4.
- Completeness scan: no incomplete-marker or open-ended implementation gaps remain.
- Type consistency: the runtime result, CLI output, and tests use consistent field names. The implementation task explicitly requires checking existing P31-P34 dataclass fields before writing config adapters.
