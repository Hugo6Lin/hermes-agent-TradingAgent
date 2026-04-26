# P24-C Shadow Experiment Runner Scaffold Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a safe runner scaffold that executes registered P24 shadow experiments in dry-run or stub mode and emits auditable run records without training models or touching production behavior.

**Architecture:** Add `p24_shadow_runner.py` with run request/result dataclasses, adapter result contract, safety-check helpers, and `run_shadow_experiment()`. The runner consumes immutable `ShadowExperimentManifest` objects from P24-B and accepts simple stdlib-only adapters. Tests validate pre-run blocks, post-adapter blocks, failure handling, JSON serialization, and model-library absence.

**Tech Stack:** Python 3.11, dataclasses, stdlib only, pytest.

---

## Source Specs

- `docs/superpowers/specs/2026-04-25-hermes-p24-shadow-experiment-runner-spec.md`
- `docs/superpowers/specs/2026-04-25-hermes-p24-shadow-experiment-registry-spec.md`
- `docs/superpowers/specs/2026-04-25-hermes-p24-entry-gate-evaluator-spec.md`

## Files

### Create

- `agent/research_v1/p24_shadow_runner.py`
- `tests/agent/research_v1/test_p24_shadow_runner.py`

### Modify

- None expected.

---

## Task 1: Contracts and Dry Run

**Files:**
- Create: `agent/research_v1/p24_shadow_runner.py`
- Test: `tests/agent/research_v1/test_p24_shadow_runner.py`

- [ ] **Step 1: Write failing dry-run test**

Create `tests/agent/research_v1/test_p24_shadow_runner.py`:

```python
import json

from agent.research_v1.p24_entry_gate import (
    P24CandidateRequest,
    P24SystemEvidence,
    evaluate_p24_entry_gate,
)
from agent.research_v1.p24_experiment_registry import (
    ShadowExperimentRegistry,
    ShadowExperimentRequest,
)
from agent.research_v1.p24_shadow_runner import (
    ShadowExperimentRunRequest,
    run_shadow_experiment,
)


def _gate_report(**request_overrides):
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
        notes="runner test",
    )
    values.update(request_overrides)
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
        purpose="Runner scaffold test.",
        input_contract={
            "allowed_sources": ["factor_snapshots", "forward_return_observations"],
            "required_point_in_time_fields": ["trading_day", "data_as_of_date", "universe_membership_snapshot_id"],
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
            "baseline_name": "prior_linear_factor_blend",
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
            "revocation_triggers": ["lookahead_violation", "net_underperformance"],
        },
        resource_policy={
            "max_runtime_minutes": 30,
            "max_memory_mb": 4096,
            "model_libraries_allowed": False,
        },
        expected_artifacts=["manifest", "shadow_predictions_file", "observation_report"],
        notes="runner manifest",
    )
    values.update(overrides)
    return ShadowExperimentRequest(**values)


def _manifest():
    registry = ShadowExperimentRegistry()
    return registry.register_shadow_experiment(_experiment_request(), _gate_report())


def _run_request(**overrides):
    values = dict(
        run_id="run_xgb_meta_v1_001",
        experiment_id="exp_xgb_meta_v1",
        run_mode="dry_run",
        input_window={
            "start_date": "2026-01-01",
            "end_date": "2026-03-31",
            "data_as_of_policy": "manifest_point_in_time_policy",
            "point_in_time_required": True,
        },
        requested_artifacts=["shadow_meta_model.xgb_v1.dry_run_metadata"],
        operator="codex",
        reason="verify runner scaffold",
        notes="dry run",
    )
    values.update(overrides)
    return ShadowExperimentRunRequest(**values)


def test_dry_run_registered_manifest_completes_without_adapter_execution():
    result = run_shadow_experiment(_manifest(), adapter=None, run_request=_run_request())

    assert result.adapter_result is None
    assert result.record.status == "completed"
    assert result.record.run_mode == "dry_run"
    assert result.record.no_production_write_confirmed is True
    assert result.record.canonical_snapshot_write_blocked is True
    assert result.record.production_config_write_blocked is True
    assert result.record.live_trading_blocked is True
    json.dumps(result.record.to_dict())
```

- [ ] **Step 2: Run failing test**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p24_shadow_runner.py::test_dry_run_registered_manifest_completes_without_adapter_execution -q
```

Expected: FAIL because `p24_shadow_runner.py` does not exist.

- [ ] **Step 3: Implement contracts and dry-run path**

Create `agent/research_v1/p24_shadow_runner.py`:

```python
"""P24-C safe shadow experiment runner scaffold."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from agent.research_v1.p24_experiment_registry import ShadowExperimentManifest


FORBIDDEN_ARTIFACTS = frozenset(
    {
        "company_quality_score",
        "valuation_attractiveness_score",
        "timing_market_fit_score",
        "llm_adjustment_total",
        "classification",
        "production_config",
        "canonical_factor_snapshot",
        "live_trade_signal",
    }
)

ALLOWED_RUN_MODES = frozenset({"dry_run", "shadow_stub"})


@dataclass(frozen=True)
class ShadowExperimentRunRequest:
    run_id: str
    experiment_id: str
    run_mode: str
    input_window: dict
    requested_artifacts: list[str]
    operator: str
    reason: str
    notes: str = ""


@dataclass(frozen=True)
class ShadowAdapterResult:
    adapter_name: str
    adapter_version: str
    produced_artifacts: list[str]
    attempted_outputs: list[str]
    metrics: dict
    logs: list[str]
    warnings: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ShadowExperimentRunRecord:
    schema_version: str
    run_id: str
    experiment_id: str
    candidate_id: str
    candidate_family: str
    manifest_schema_version: str
    manifest_status: str
    run_mode: str
    input_window: dict
    output_namespace: str
    adapter_name: str
    adapter_version: str
    status: str
    produced_artifacts: list[str]
    blocked_artifacts: list[str]
    safety_checks: dict
    warnings: list[str]
    error_message: str
    no_production_write_confirmed: bool
    canonical_snapshot_write_blocked: bool
    production_config_write_blocked: bool
    live_trading_blocked: bool
    started_at: str
    completed_at: str
    notes: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ShadowRunnerResult:
    record: ShadowExperimentRunRecord
    adapter_result: ShadowAdapterResult | None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_shadow_experiment(
    manifest: ShadowExperimentManifest,
    adapter: Any,
    run_request: ShadowExperimentRunRequest,
) -> ShadowRunnerResult:
    started_at = _utc_now()
    pre_block = _evaluate_pre_run_safety(manifest, run_request)
    if pre_block:
        return ShadowRunnerResult(
            record=_build_record(
                manifest=manifest,
                run_request=run_request,
                started_at=started_at,
                status="blocked",
                adapter_name="none",
                adapter_version="none",
                produced_artifacts=[],
                blocked_artifacts=pre_block,
                warnings=[],
                error_message=f"pre-run safety block: {', '.join(pre_block)}",
            ),
            adapter_result=None,
        )

    if run_request.run_mode == "dry_run":
        return ShadowRunnerResult(
            record=_build_record(
                manifest=manifest,
                run_request=run_request,
                started_at=started_at,
                status="completed",
                adapter_name="none",
                adapter_version="none",
                produced_artifacts=list(run_request.requested_artifacts),
                blocked_artifacts=[],
                warnings=[],
                error_message="",
            ),
            adapter_result=None,
        )

    try:
        adapter_result = adapter.run(manifest, run_request)
    except Exception as exc:
        return ShadowRunnerResult(
            record=_build_record(
                manifest=manifest,
                run_request=run_request,
                started_at=started_at,
                status="failed",
                adapter_name=getattr(adapter, "adapter_name", "unknown"),
                adapter_version=getattr(adapter, "adapter_version", "unknown"),
                produced_artifacts=[],
                blocked_artifacts=[],
                warnings=[],
                error_message=f"{exc.__class__.__name__}: {exc}",
            ),
            adapter_result=None,
        )

    post_block = _evaluate_adapter_safety(manifest, adapter_result)
    return ShadowRunnerResult(
        record=_build_record(
            manifest=manifest,
            run_request=run_request,
            started_at=started_at,
            status="blocked" if post_block else "completed",
            adapter_name=adapter_result.adapter_name,
            adapter_version=adapter_result.adapter_version,
            produced_artifacts=[] if post_block else list(adapter_result.produced_artifacts),
            blocked_artifacts=post_block,
            warnings=list(adapter_result.warnings),
            error_message=f"adapter safety block: {', '.join(post_block)}" if post_block else "",
        ),
        adapter_result=adapter_result,
    )
```

- [ ] **Step 4: Add pre-run and record helpers**

Append to `agent/research_v1/p24_shadow_runner.py`:

```python
def _namespace() -> str:
    return ""


def _within_namespace(name: str, namespace: str) -> bool:
    return str(name).startswith(namespace)


def _is_forbidden(name: str) -> bool:
    return str(name) in FORBIDDEN_ARTIFACTS


def _evaluate_pre_run_safety(
    manifest: ShadowExperimentManifest,
    run_request: ShadowExperimentRunRequest,
) -> list[str]:
    blocked = []
    output_contract = manifest.output_contract
    if manifest.status != "registered":
        blocked.append("manifest_not_registered")
    if manifest.promotion_blocked is not True:
        blocked.append("promotion_not_blocked")
    if manifest.production_write_blocked is not True:
        blocked.append("production_write_not_blocked")
    if manifest.canonical_snapshot_write_blocked is not True:
        blocked.append("canonical_snapshot_write_not_blocked")
    if output_contract.get("writes_canonical_factor_snapshot") is not False:
        blocked.append("manifest_allows_canonical_snapshot_write")
    if output_contract.get("writes_production_config") is not False:
        blocked.append("manifest_allows_production_config_write")
    if output_contract.get("affects_live_trading") is not False:
        blocked.append("manifest_allows_live_trading")
    if output_contract.get("return_basis") != "net":
        blocked.append("manifest_return_basis_not_net")
    if run_request.experiment_id != manifest.experiment_id:
        blocked.append("experiment_id_mismatch")
    if run_request.run_mode not in ALLOWED_RUN_MODES:
        blocked.append("run_mode_not_allowed")
    if run_request.input_window.get("point_in_time_required") is not True:
        blocked.append("input_window_not_point_in_time")
    if run_request.input_window.get("data_as_of_policy") != "manifest_point_in_time_policy":
        blocked.append("data_as_of_policy_invalid")
    for artifact in run_request.requested_artifacts:
        if not _within_namespace(artifact, manifest.shadow_namespace):
            blocked.append(f"requested_artifact_outside_namespace:{artifact}")
        if _is_forbidden(artifact):
            blocked.append(f"requested_forbidden_artifact:{artifact}")
    return blocked


def _evaluate_adapter_safety(
    manifest: ShadowExperimentManifest,
    adapter_result: ShadowAdapterResult,
) -> list[str]:
    blocked = []
    for artifact in list(adapter_result.produced_artifacts) + list(adapter_result.attempted_outputs):
        if not _within_namespace(artifact, manifest.shadow_namespace):
            blocked.append(f"adapter_output_outside_namespace:{artifact}")
        if _is_forbidden(artifact):
            blocked.append(f"adapter_forbidden_output:{artifact}")
    return blocked


def _build_record(
    manifest: ShadowExperimentManifest,
    run_request: ShadowExperimentRunRequest,
    started_at: str,
    status: str,
    adapter_name: str,
    adapter_version: str,
    produced_artifacts: list[str],
    blocked_artifacts: list[str],
    warnings: list[str],
    error_message: str,
) -> ShadowExperimentRunRecord:
    return ShadowExperimentRunRecord(
        schema_version="p24_run.0",
        run_id=run_request.run_id,
        experiment_id=run_request.experiment_id,
        candidate_id=manifest.candidate_id,
        candidate_family=manifest.candidate_family,
        manifest_schema_version=manifest.schema_version,
        manifest_status=manifest.status,
        run_mode=run_request.run_mode,
        input_window=dict(run_request.input_window),
        output_namespace=manifest.shadow_namespace,
        adapter_name=adapter_name,
        adapter_version=adapter_version,
        status=status,
        produced_artifacts=produced_artifacts,
        blocked_artifacts=blocked_artifacts,
        safety_checks={
            "no_production_write": True,
            "canonical_snapshot_write_blocked": True,
            "production_config_write_blocked": True,
            "live_trading_blocked": True,
        },
        warnings=warnings,
        error_message=error_message,
        no_production_write_confirmed=True,
        canonical_snapshot_write_blocked=True,
        production_config_write_blocked=True,
        live_trading_blocked=True,
        started_at=started_at,
        completed_at=_utc_now(),
        notes=run_request.notes,
    )
```

- [ ] **Step 5: Run dry-run test**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p24_shadow_runner.py::test_dry_run_registered_manifest_completes_without_adapter_execution -q
```

Expected: PASS.

---

## Task 2: Pre-Run Safety Blocks

**Files:**
- Modify: `tests/agent/research_v1/test_p24_shadow_runner.py`

- [ ] **Step 1: Add pre-run block tests**

Append to `tests/agent/research_v1/test_p24_shadow_runner.py`:

```python
from dataclasses import replace


def test_revoked_manifest_is_blocked():
    manifest = replace(_manifest(), status="revoked")

    result = run_shadow_experiment(manifest, adapter=None, run_request=_run_request())

    assert result.record.status == "blocked"
    assert "manifest_not_registered" in result.record.blocked_artifacts
    assert result.adapter_result is None


def test_experiment_id_mismatch_is_blocked():
    result = run_shadow_experiment(
        _manifest(),
        adapter=None,
        run_request=_run_request(experiment_id="wrong_exp"),
    )

    assert result.record.status == "blocked"
    assert "experiment_id_mismatch" in result.record.blocked_artifacts


def test_non_point_in_time_input_window_is_blocked():
    request = _run_request(
        input_window={
            "start_date": "2026-01-01",
            "end_date": "2026-03-31",
            "data_as_of_policy": "latest_available",
            "point_in_time_required": False,
        }
    )

    result = run_shadow_experiment(_manifest(), adapter=None, run_request=request)

    assert result.record.status == "blocked"
    assert "input_window_not_point_in_time" in result.record.blocked_artifacts
    assert "data_as_of_policy_invalid" in result.record.blocked_artifacts


def test_requested_artifact_outside_namespace_is_blocked():
    result = run_shadow_experiment(
        _manifest(),
        adapter=None,
        run_request=_run_request(requested_artifacts=["production_config"]),
    )

    assert result.record.status == "blocked"
    assert "requested_artifact_outside_namespace:production_config" in result.record.blocked_artifacts
    assert "requested_forbidden_artifact:production_config" in result.record.blocked_artifacts
```

- [ ] **Step 2: Run pre-run block tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p24_shadow_runner.py -q
```

Expected: PASS.

---

## Task 3: Shadow Stub Adapter Execution and Post-Run Blocks

**Files:**
- Modify: `tests/agent/research_v1/test_p24_shadow_runner.py`

- [ ] **Step 1: Add adapter tests**

Append to `tests/agent/research_v1/test_p24_shadow_runner.py`:

```python
from agent.research_v1.p24_shadow_runner import ShadowAdapterResult


class GoodAdapter:
    adapter_name = "good_stub"
    adapter_version = "0.1"

    def run(self, manifest, request):
        return ShadowAdapterResult(
            adapter_name=self.adapter_name,
            adapter_version=self.adapter_version,
            produced_artifacts=["shadow_meta_model.xgb_v1.shadow_predictions"],
            attempted_outputs=["shadow_meta_model.xgb_v1.shadow_predictions"],
            metrics={"rows": 10},
            logs=["stub run"],
            warnings=[],
        )


class BadNamespaceAdapter:
    adapter_name = "bad_namespace"
    adapter_version = "0.1"

    def run(self, manifest, request):
        return ShadowAdapterResult(
            adapter_name=self.adapter_name,
            adapter_version=self.adapter_version,
            produced_artifacts=["other_namespace.predictions"],
            attempted_outputs=["other_namespace.predictions"],
            metrics={},
            logs=[],
            warnings=[],
        )


class ForbiddenOutputAdapter:
    adapter_name = "forbidden_output"
    adapter_version = "0.1"

    def run(self, manifest, request):
        return ShadowAdapterResult(
            adapter_name=self.adapter_name,
            adapter_version=self.adapter_version,
            produced_artifacts=["classification"],
            attempted_outputs=["classification"],
            metrics={},
            logs=[],
            warnings=["attempted forbidden output"],
        )


class ExplodingAdapter:
    adapter_name = "exploding"
    adapter_version = "0.1"

    def run(self, manifest, request):
        raise RuntimeError("adapter exploded")


def test_shadow_stub_registered_manifest_executes_adapter():
    result = run_shadow_experiment(
        _manifest(),
        adapter=GoodAdapter(),
        run_request=_run_request(run_mode="shadow_stub"),
    )

    assert result.record.status == "completed"
    assert result.adapter_result is not None
    assert result.record.adapter_name == "good_stub"
    assert result.record.produced_artifacts == ["shadow_meta_model.xgb_v1.shadow_predictions"]


def test_adapter_artifact_outside_namespace_is_blocked():
    result = run_shadow_experiment(
        _manifest(),
        adapter=BadNamespaceAdapter(),
        run_request=_run_request(run_mode="shadow_stub"),
    )

    assert result.record.status == "blocked"
    assert "adapter_output_outside_namespace:other_namespace.predictions" in result.record.blocked_artifacts


def test_adapter_forbidden_output_is_blocked():
    result = run_shadow_experiment(
        _manifest(),
        adapter=ForbiddenOutputAdapter(),
        run_request=_run_request(run_mode="shadow_stub"),
    )

    assert result.record.status == "blocked"
    assert "adapter_forbidden_output:classification" in result.record.blocked_artifacts


def test_adapter_exception_becomes_failed_record():
    result = run_shadow_experiment(
        _manifest(),
        adapter=ExplodingAdapter(),
        run_request=_run_request(run_mode="shadow_stub"),
    )

    assert result.record.status == "failed"
    assert "RuntimeError: adapter exploded" in result.record.error_message
    assert result.record.no_production_write_confirmed is True
```

- [ ] **Step 2: Run adapter tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p24_shadow_runner.py -q
```

Expected: PASS.

---

## Task 4: Serialization, No Model Libraries, and Regression

**Files:**
- Modify: `tests/agent/research_v1/test_p24_shadow_runner.py`

- [ ] **Step 1: Add final safety tests**

Append to `tests/agent/research_v1/test_p24_shadow_runner.py`:

```python
def test_run_record_confirms_all_production_paths_blocked():
    result = run_shadow_experiment(_manifest(), adapter=None, run_request=_run_request())

    assert result.record.safety_checks["no_production_write"] is True
    assert result.record.safety_checks["canonical_snapshot_write_blocked"] is True
    assert result.record.safety_checks["production_config_write_blocked"] is True
    assert result.record.safety_checks["live_trading_blocked"] is True


def test_runner_module_does_not_import_model_libraries():
    import agent.research_v1.p24_shadow_runner as runner_module

    module_names = set(runner_module.__dict__)
    forbidden_names = {"xgboost", "torch", "tensorflow", "sklearn", "stable_baselines3"}

    assert module_names.isdisjoint(forbidden_names)
```

- [ ] **Step 2: Run P24-C tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p24_shadow_runner.py -q
```

Expected: all P24-C tests PASS.

- [ ] **Step 3: Run P24-A/B/C tests together**

Run:

```bash
python3.11 -m pytest \
  tests/agent/research_v1/test_p24_entry_gate.py \
  tests/agent/research_v1/test_p24_experiment_registry.py \
  tests/agent/research_v1/test_p24_shadow_runner.py \
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
  -q
```

Expected: all selected tests PASS.

- [ ] **Step 5: Scan for forbidden model imports**

Run:

```bash
grep -R "import xgboost\|from xgboost\|import torch\|from torch\|import tensorflow\|from tensorflow\|stable_baselines\|import sklearn\|from sklearn" -n \
  agent/research_v1/p24_shadow_runner.py \
  tests/agent/research_v1/test_p24_shadow_runner.py || true
```

Expected: no output.

---

## Final Handoff Format

Return:

```text
P24-C Shadow Experiment Runner Scaffold Handoff

Changed files:
- <path> — <created/modified> — <purpose>

Tests run:
- <command> → <result>

Acceptance checklist:
- runner accepts only registered manifests: yes/no
- dry run completes without adapter: yes/no
- shadow stub calls adapter: yes/no
- pre-run safety blocks return blocked records: yes/no
- post-adapter violations return blocked records: yes/no
- adapter exceptions return failed records: yes/no
- output namespace enforced: yes/no
- forbidden artifacts enforced: yes/no
- no production write confirmed: yes/no
- run records JSON-serializable: yes/no
- no model libraries imported: yes/no
- P20-P24 regression green: yes/no

Known issues:
- <issue or None>
```
