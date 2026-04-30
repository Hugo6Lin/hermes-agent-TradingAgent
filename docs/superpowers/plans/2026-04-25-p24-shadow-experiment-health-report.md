# P24-E Shadow Experiment Health Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a read-only health report over P24 shadow experiment manifests and persisted run records.

**Architecture:** Add `p24_health_report.py` with report dataclasses and `build_shadow_experiment_health_report(manifests, run_store)`. The module consumes P24-B manifests and P24-D summaries, computes row-level health, family breakdowns, blocked-reason aggregates, production-safety summary, and advisory recommended actions. It must not mutate registry or run store.

**Tech Stack:** Python 3.11, dataclasses, stdlib only, pytest.

---

## Source Specs

- `docs/superpowers/specs/2026-04-25-hermes-p24-shadow-experiment-health-report-spec.md`
- `docs/superpowers/specs/2026-04-25-hermes-p24-shadow-run-persistence-observation-spec.md`
- `docs/superpowers/specs/2026-04-25-hermes-p24-shadow-experiment-registry-spec.md`

## Files

### Create

- `agent/research_v1/p24_health_report.py`
- `tests/agent/research_v1/test_p24_health_report.py`

### Modify

- None expected.

---

## Task 1: Report Contracts and Empty Report

**Files:**
- Create: `agent/research_v1/p24_health_report.py`
- Test: `tests/agent/research_v1/test_p24_health_report.py`

- [ ] **Step 1: Write failing empty-report test**

Create `tests/agent/research_v1/test_p24_health_report.py`:

```python
import json

from agent.research_v1.p24_health_report import build_shadow_experiment_health_report
from agent.research_v1.p24_run_persistence import ShadowRunStore


def test_empty_manifest_list_returns_empty_report():
    report = build_shadow_experiment_health_report([], ShadowRunStore())

    assert report.schema_version == "p24_health_report.0"
    assert report.total_experiments == 0
    assert report.registered_count == 0
    assert report.healthy_count == 0
    assert report.watch_count == 0
    assert report.no_runs_count == 0
    assert report.revocation_recommended_count == 0
    assert report.experiments == []
    assert report.recommended_actions == []
    json.dumps(report.to_dict())
```

- [ ] **Step 2: Run failing test**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p24_health_report.py::test_empty_manifest_list_returns_empty_report -q
```

Expected: FAIL because `p24_health_report.py` does not exist.

- [ ] **Step 3: Implement report contracts**

Create `agent/research_v1/p24_health_report.py`:

```python
"""P24-E read-only shadow experiment health reporting."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from agent.research_v1.p24_experiment_registry import ShadowExperimentManifest
from agent.research_v1.p24_run_persistence import ShadowRunStore


@dataclass(frozen=True)
class ExperimentHealthRow:
    experiment_id: str
    candidate_id: str
    candidate_name: str
    candidate_family: str
    manifest_status: str
    shadow_namespace: str
    total_runs: int
    completed_count: int
    blocked_count: int
    failed_count: int
    last_run_id: str
    last_run_status: str
    health_status: str
    revocation_recommended: bool
    revocation_reasons: list[str]
    top_blocked_reasons: dict[str, int]
    latest_completed_at: str
    no_production_write_confirmed: bool
    canonical_snapshot_write_blocked: bool
    production_config_write_blocked: bool
    live_trading_blocked: bool

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ShadowExperimentHealthReport:
    schema_version: str
    generated_at: str
    total_experiments: int
    registered_count: int
    revoked_count: int
    archived_count: int
    healthy_count: int
    watch_count: int
    no_runs_count: int
    revocation_recommended_count: int
    family_breakdown: dict
    top_blocked_reasons: dict[str, int]
    production_safety_summary: dict
    experiments: list[ExperimentHealthRow]
    recommended_actions: list[str]

    def to_dict(self) -> dict:
        data = asdict(self)
        data["experiments"] = [row.to_dict() for row in self.experiments]
        return data


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_shadow_experiment_health_report(
    manifests: list[ShadowExperimentManifest],
    run_store: ShadowRunStore,
) -> ShadowExperimentHealthReport:
    rows = [_build_row(manifest, run_store) for manifest in manifests]
    rows = sorted(rows, key=_row_sort_key)
    family_breakdown = _build_family_breakdown(rows)
    top_blocked_reasons = _aggregate_blocked_reasons(rows)
    production_safety_summary = _build_production_safety_summary(rows)
    recommended_actions = _build_recommended_actions(rows, production_safety_summary)
    return ShadowExperimentHealthReport(
        schema_version="p24_health_report.0",
        generated_at=_utc_now(),
        total_experiments=len(rows),
        registered_count=sum(1 for row in rows if row.manifest_status == "registered"),
        revoked_count=sum(1 for row in rows if row.manifest_status == "revoked"),
        archived_count=sum(1 for row in rows if row.manifest_status == "archived"),
        healthy_count=sum(1 for row in rows if row.health_status == "healthy"),
        watch_count=sum(1 for row in rows if row.health_status == "watch"),
        no_runs_count=sum(1 for row in rows if row.health_status == "no_runs"),
        revocation_recommended_count=sum(1 for row in rows if row.revocation_recommended),
        family_breakdown=family_breakdown,
        top_blocked_reasons=top_blocked_reasons,
        production_safety_summary=production_safety_summary,
        experiments=rows,
        recommended_actions=recommended_actions,
    )
```

- [ ] **Step 4: Implement helpers for empty report**

Append to `agent/research_v1/p24_health_report.py`:

```python
def _row_sort_key(row: ExperimentHealthRow) -> tuple:
    risk_rank = {
        "revocation_recommended": 0,
        "watch": 1,
        "no_runs": 2,
        "healthy": 3,
    }.get(row.health_status, 4)
    return (risk_rank, row.candidate_family, row.experiment_id)


def _build_family_breakdown(rows: list[ExperimentHealthRow]) -> dict:
    breakdown: dict[str, dict] = {}
    for row in rows:
        bucket = breakdown.setdefault(
            row.candidate_family,
            {
                "total_experiments": 0,
                "registered_count": 0,
                "healthy_count": 0,
                "watch_count": 0,
                "no_runs_count": 0,
                "revocation_recommended_count": 0,
                "completed_runs": 0,
                "blocked_runs": 0,
                "failed_runs": 0,
            },
        )
        bucket["total_experiments"] += 1
        bucket["registered_count"] += 1 if row.manifest_status == "registered" else 0
        bucket["healthy_count"] += 1 if row.health_status == "healthy" else 0
        bucket["watch_count"] += 1 if row.health_status == "watch" else 0
        bucket["no_runs_count"] += 1 if row.health_status == "no_runs" else 0
        bucket["revocation_recommended_count"] += 1 if row.revocation_recommended else 0
        bucket["completed_runs"] += row.completed_count
        bucket["blocked_runs"] += row.blocked_count
        bucket["failed_runs"] += row.failed_count
    return breakdown


def _aggregate_blocked_reasons(rows: list[ExperimentHealthRow]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for row in rows:
        counter.update(row.top_blocked_reasons)
    return dict(counter.most_common())


def _build_production_safety_summary(rows: list[ExperimentHealthRow]) -> dict:
    unsafe_experiment_ids = [
        row.experiment_id
        for row in rows
        if not (
            row.no_production_write_confirmed
            and row.canonical_snapshot_write_blocked
            and row.production_config_write_blocked
            and row.live_trading_blocked
        )
    ]
    return {
        "all_no_production_write_confirmed": all(row.no_production_write_confirmed for row in rows),
        "any_canonical_snapshot_write_attempt": any(not row.canonical_snapshot_write_blocked for row in rows),
        "any_production_config_write_attempt": any(not row.production_config_write_blocked for row in rows),
        "any_live_trading_attempt": any(not row.live_trading_blocked for row in rows),
        "unsafe_experiment_ids": unsafe_experiment_ids,
    }


def _build_recommended_actions(rows: list[ExperimentHealthRow], production_safety_summary: dict) -> list[str]:
    actions: list[str] = []
    if any(row.revocation_recommended for row in rows):
        actions.append("review_revocation_recommended_experiments")
    if any(row.health_status == "no_runs" for row in rows):
        actions.append("schedule_shadow_runs_for_no_run_experiments")
    if any(row.health_status == "watch" for row in rows):
        actions.append("inspect_watch_experiments")
    if production_safety_summary["unsafe_experiment_ids"]:
        actions.append("investigate_production_safety_violation")
    if rows and all(row.health_status == "healthy" for row in rows):
        actions.append("continue_observation")
    return actions
```

- [ ] **Step 5: Add placeholder row builder**

Append to `agent/research_v1/p24_health_report.py`:

```python
def _build_row(manifest: ShadowExperimentManifest, run_store: ShadowRunStore) -> ExperimentHealthRow:
    summary = run_store.summarize_experiment_runs(manifest.experiment_id)
    return ExperimentHealthRow(
        experiment_id=manifest.experiment_id,
        candidate_id=manifest.candidate_id,
        candidate_name=manifest.candidate_name,
        candidate_family=manifest.candidate_family,
        manifest_status=manifest.status,
        shadow_namespace=manifest.shadow_namespace,
        total_runs=summary.total_runs,
        completed_count=summary.completed_count,
        blocked_count=summary.blocked_count,
        failed_count=summary.failed_count,
        last_run_id=summary.last_run_id,
        last_run_status=summary.last_run_status,
        health_status=summary.health_status,
        revocation_recommended=summary.revocation_recommended,
        revocation_reasons=list(summary.revocation_reasons),
        top_blocked_reasons=dict(summary.blocked_reason_frequency),
        latest_completed_at=summary.latest_completed_at,
        no_production_write_confirmed=manifest.production_write_blocked,
        canonical_snapshot_write_blocked=manifest.canonical_snapshot_write_blocked,
        production_config_write_blocked=manifest.production_write_blocked,
        live_trading_blocked=manifest.output_contract.get("affects_live_trading") is False,
    )
```

- [ ] **Step 6: Run empty-report test**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p24_health_report.py::test_empty_manifest_list_returns_empty_report -q
```

Expected: PASS.

---

## Task 2: Fixtures and Healthy/No-Run Rows

**Files:**
- Modify: `tests/agent/research_v1/test_p24_health_report.py`

- [ ] **Step 1: Add fixture helpers and tests**

Append to `tests/agent/research_v1/test_p24_health_report.py`:

```python
from dataclasses import replace

from agent.research_v1.p24_entry_gate import (
    P24CandidateRequest,
    P24SystemEvidence,
    evaluate_p24_entry_gate,
)
from agent.research_v1.p24_experiment_registry import ShadowExperimentRegistry, ShadowExperimentRequest
from agent.research_v1.p24_shadow_runner import ShadowExperimentRunRequest, run_shadow_experiment


def _gate_report(**overrides):
    values = dict(
        candidate_name="xgb_meta_v1",
        candidate_family="xgboost_meta_model",
        candidate_namespace="shadow_meta_model.xgb_v1",
        requested_phase="P24",
        intended_outputs=["shadow_meta_model.xgb_v1.shadow_ranking_score"],
        uses_point_in_time_sources=True,
        source_audit_plan_defined=True,
        simple_baseline_defined=True,
        out_of_sample_plan_defined=True,
        uses_gross_returns_as_primary=False,
        writes_production_fields=False,
        requires_portfolio_layer=False,
        requires_execution_data=False,
        residualization_plan_defined=False,
        notes="health report test",
    )
    values.update(overrides)
    evidence = P24SystemEvidence(
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
    return evaluate_p24_entry_gate(P24CandidateRequest(**values), evidence)


def _experiment_request(**overrides):
    values = dict(
        experiment_id="exp_xgb_meta_v1",
        candidate_id="xgb_meta_v1",
        candidate_name="xgb_meta_v1",
        candidate_family="xgboost_meta_model",
        candidate_namespace="shadow_meta_model.xgb_v1",
        source_gate_report_id="gate_xgb_meta_v1",
        owner="research",
        purpose="Health report test.",
        input_contract={
            "allowed_sources": ["factor_snapshots"],
            "required_point_in_time_fields": ["trading_day"],
            "forbidden_sources": ["future_prices"],
            "max_source_audit_gap_rate": 0.20,
            "lookahead_policy": "strict_no_future_data",
        },
        output_contract={
            "allowed_outputs": ["shadow_meta_model.xgb_v1.shadow_ranking_score"],
            "output_namespace": "shadow_meta_model.xgb_v1",
            "writes_canonical_factor_snapshot": False,
            "writes_production_config": False,
            "affects_live_trading": False,
            "return_basis": "net",
        },
        forbidden_outputs=[
            "company_quality_score",
            "valuation_attractiveness_score",
            "timing_market_fit_score",
            "llm_adjustment_total",
            "classification",
            "production_config",
            "canonical_factor_snapshot",
            "live_trade_signal",
        ],
        training_data_window={
            "start_date": "2024-01-01",
            "end_date": "2026-01-01",
            "minimum_observations": 500,
            "purged_validation_gap_days": 5,
            "embargo_days": 5,
            "point_in_time_membership_required": True,
        },
        point_in_time_policy={
            "source_timestamp_required": True,
            "membership_snapshot_required": True,
            "revision_policy": "as_reported_only",
        },
        baseline_comparison_plan={
            "baseline_name": "prior",
            "baseline_type": "current_prior",
            "primary_metric": "net_icir",
            "secondary_metrics": ["net_ic"],
            "comparison_direction": "higher_is_better",
            "minimum_evaluation_windows": 4,
        },
        out_of_sample_validation_plan={
            "method": "walk_forward",
            "walk_forward_enabled": True,
            "holdout_periods": ["2026H1"],
            "leakage_checks": ["point_in_time", "purged_embargo"],
            "promotion_criteria_documented": True,
        },
        observation_plan={
            "observation_frequency": "weekly",
            "minimum_shadow_windows": 4,
            "required_reports": ["ModelAdmissionGateReport", "ShadowExperimentManifest", "ShadowObservationReport"],
            "revocation_triggers": ["net_underperformance"],
        },
        resource_policy={
            "max_runtime_minutes": 30,
            "max_memory_mb": 4096,
            "model_libraries_allowed": False,
        },
        expected_artifacts=["manifest"],
        notes="health manifest",
    )
    values.update(overrides)
    return ShadowExperimentRequest(**values)


def _manifest(**overrides):
    registry = ShadowExperimentRegistry()
    request = _experiment_request(**overrides)
    gate_report = _gate_report(
        candidate_name=request.candidate_name,
        candidate_family=request.candidate_family,
        candidate_namespace=request.candidate_namespace,
        intended_outputs=list(request.output_contract["allowed_outputs"]),
    )
    return registry.register_shadow_experiment(request, gate_report)


def _run_request(run_id="run_001", experiment_id="exp_xgb_meta_v1", requested_artifacts=None):
    return ShadowExperimentRunRequest(
        run_id=run_id,
        experiment_id=experiment_id,
        run_mode="dry_run",
        input_window={
            "start_date": "2026-01-01",
            "end_date": "2026-03-31",
            "data_as_of_policy": "manifest_point_in_time_policy",
            "point_in_time_required": True,
        },
        requested_artifacts=requested_artifacts or ["shadow_meta_model.xgb_v1.dry_run_metadata"],
        operator="codex",
        reason="health report",
        notes="health run",
    )


def test_registered_experiment_with_completed_runs_appears_healthy():
    manifest = _manifest()
    store = ShadowRunStore()
    store.save_run_record(run_shadow_experiment(manifest, None, _run_request()).record)

    report = build_shadow_experiment_health_report([manifest], store)

    assert report.total_experiments == 1
    assert report.healthy_count == 1
    assert report.experiments[0].health_status == "healthy"
    assert report.recommended_actions == ["continue_observation"]


def test_no_run_experiment_appears_as_no_runs():
    manifest = _manifest()

    report = build_shadow_experiment_health_report([manifest], ShadowRunStore())

    assert report.no_runs_count == 1
    assert report.experiments[0].health_status == "no_runs"
    assert "schedule_shadow_runs_for_no_run_experiments" in report.recommended_actions
```

- [ ] **Step 2: Run health/no-run tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p24_health_report.py -q
```

Expected: PASS.

---

## Task 3: Watch, Revocation, Sorting, and Aggregates

**Files:**
- Modify: `tests/agent/research_v1/test_p24_health_report.py`

- [ ] **Step 1: Add risk and aggregate tests**

Append to `tests/agent/research_v1/test_p24_health_report.py`:

```python
def test_watch_experiment_and_top_blocked_reasons_are_reported():
    manifest = _manifest()
    store = ShadowRunStore()
    store.save_run_record(
        run_shadow_experiment(
            manifest,
            None,
            _run_request(run_id="run_blocked", requested_artifacts=["company_quality_score"]),
        ).record
    )

    report = build_shadow_experiment_health_report([manifest], store)

    assert report.watch_count == 1
    assert report.experiments[0].health_status == "watch"
    assert report.top_blocked_reasons["requested_forbidden_artifact:company_quality_score"] == 1
    assert "inspect_watch_experiments" in report.recommended_actions


def test_revocation_recommended_experiment_sorts_first():
    healthy_manifest = _manifest()
    risky_manifest = _manifest(
        experiment_id="exp_risky",
        candidate_id="risky",
        candidate_name="risky",
        candidate_namespace="shadow_meta_model.risky",
        output_contract={
            **dict(_experiment_request().output_contract),
            "allowed_outputs": ["shadow_meta_model.risky.score"],
            "output_namespace": "shadow_meta_model.risky",
        },
    )
    store = ShadowRunStore()
    store.save_run_record(run_shadow_experiment(healthy_manifest, None, _run_request()).record)
    store.save_run_record(
        run_shadow_experiment(
            risky_manifest,
            None,
            _run_request(
                run_id="run_risky",
                experiment_id="exp_risky",
                requested_artifacts=["production_config"],
            ),
        ).record
    )

    report = build_shadow_experiment_health_report([healthy_manifest, risky_manifest], store)

    assert report.revocation_recommended_count == 1
    assert report.experiments[0].experiment_id == "exp_risky"
    assert report.experiments[0].revocation_recommended is True
    assert "review_revocation_recommended_experiments" in report.recommended_actions


def test_family_breakdown_counts_experiments_and_run_statuses():
    manifest = _manifest()
    store = ShadowRunStore()
    store.save_run_record(run_shadow_experiment(manifest, None, _run_request()).record)

    report = build_shadow_experiment_health_report([manifest], store)
    family = report.family_breakdown["xgboost_meta_model"]

    assert family["total_experiments"] == 1
    assert family["registered_count"] == 1
    assert family["healthy_count"] == 1
    assert family["completed_runs"] == 1
    assert family["blocked_runs"] == 0
    assert family["failed_runs"] == 0
```

- [ ] **Step 2: Run aggregate tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p24_health_report.py -q
```

Expected: PASS.

---

## Task 4: Production Safety Summary and Serialization

**Files:**
- Modify: `tests/agent/research_v1/test_p24_health_report.py`

- [ ] **Step 1: Add final safety tests**

Append to `tests/agent/research_v1/test_p24_health_report.py`:

```python
def test_production_safety_summary_detects_unsafe_manifest_flags():
    manifest = replace(_manifest(), production_write_blocked=False)

    report = build_shadow_experiment_health_report([manifest], ShadowRunStore())

    assert report.production_safety_summary["all_no_production_write_confirmed"] is False
    assert report.production_safety_summary["any_production_config_write_attempt"] is True
    assert report.production_safety_summary["unsafe_experiment_ids"] == ["exp_xgb_meta_v1"]
    assert "investigate_production_safety_violation" in report.recommended_actions


def test_health_report_is_json_serializable():
    manifest = _manifest()
    store = ShadowRunStore()
    store.save_run_record(run_shadow_experiment(manifest, None, _run_request()).record)

    report = build_shadow_experiment_health_report([manifest], store)

    json.dumps(report.to_dict())


def test_health_report_module_does_not_import_model_libraries():
    import agent.research_v1.p24_health_report as health_report_module

    module_names = set(health_report_module.__dict__)
    forbidden_names = {"xgboost", "torch", "tensorflow", "sklearn", "stable_baselines3"}

    assert module_names.isdisjoint(forbidden_names)
```

- [ ] **Step 2: Run P24-E tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p24_health_report.py -q
```

Expected: all P24-E tests PASS.

- [ ] **Step 3: Run P24-A/B/C/D/E tests together**

Run:

```bash
python3.11 -m pytest \
  tests/agent/research_v1/test_p24_entry_gate.py \
  tests/agent/research_v1/test_p24_experiment_registry.py \
  tests/agent/research_v1/test_p24_shadow_runner.py \
  tests/agent/research_v1/test_p24_run_persistence.py \
  tests/agent/research_v1/test_p24_health_report.py \
  -q
```

Expected: all P24 tests PASS.

- [ ] **Step 4: Run P20-P24 regression bundle**

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
  tests/agent/research_v1/test_p24_experiment_registry.py \
  tests/agent/research_v1/test_p24_shadow_runner.py \
  tests/agent/research_v1/test_p24_run_persistence.py \
  tests/agent/research_v1/test_p24_health_report.py \
  -q
```

Expected: all selected tests PASS.

- [ ] **Step 5: Scan for forbidden model imports**

Run:

```bash
grep -R "import xgboost\|from xgboost\|import torch\|from torch\|import tensorflow\|from tensorflow\|stable_baselines\|import sklearn\|from sklearn" -n \
  agent/research_v1/p24_health_report.py \
  tests/agent/research_v1/test_p24_health_report.py || true
```

Expected: no output except possible string literals inside the no-model-library test.

---

## Final Handoff Format

Return:

```text
P24-E Shadow Experiment Health Report Handoff

Changed files:
- <path> — <created/modified> — <purpose>

Tests run:
- <command> → <result>

Acceptance checklist:
- health report contract exists: yes/no
- empty report works: yes/no
- healthy experiments reported: yes/no
- watch experiments reported: yes/no
- no-run experiments reported: yes/no
- revocation-recommended experiments reported: yes/no
- risk sorting works: yes/no
- family breakdown computed: yes/no
- top blocked reasons aggregated: yes/no
- production safety summary computed: yes/no
- recommended actions advisory only: yes/no
- JSON serialization works: yes/no
- no model libraries imported: yes/no
- P20-P24 regression green: yes/no

Known issues:
- <issue or None>
```
