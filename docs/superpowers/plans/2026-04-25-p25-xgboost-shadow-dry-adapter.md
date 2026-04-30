# P25-A XGBoost Meta-Model Shadow Dry Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the first real P25 shadow candidate: an XGBoost-style meta-model dry adapter that validates feature contracts and produces deterministic shadow-only stub artifacts through the P24 runner.

**Architecture:** Add `p25_xgboost_shadow_adapter.py` with feature contract/config dataclasses, validation helpers, deterministic stub scoring, and `XGBoostDryRunAdapter.run()`. The adapter returns P24-C `ShadowAdapterResult` and is exercised through P24-C/D/E in tests. It must remain stdlib-only and must not import XGBoost or any model library.

**Tech Stack:** Python 3.11, dataclasses, stdlib only, pytest.

---

## Source Specs

- `docs/superpowers/specs/2026-04-25-hermes-p25-xgboost-shadow-dry-adapter-spec.md`
- `docs/superpowers/specs/2026-04-25-hermes-p24-shadow-experiment-runner-spec.md`
- `docs/superpowers/specs/2026-04-25-hermes-p24-shadow-experiment-health-report-spec.md`

## Files

### Create

- `agent/research_v1/p25_xgboost_shadow_adapter.py`
- `tests/agent/research_v1/test_p25_xgboost_shadow_adapter.py`

### Modify

- None expected.

---

## Task 1: Feature Contract and Config

**Files:**
- Create: `agent/research_v1/p25_xgboost_shadow_adapter.py`
- Test: `tests/agent/research_v1/test_p25_xgboost_shadow_adapter.py`

- [ ] **Step 1: Write failing config tests**

Create `tests/agent/research_v1/test_p25_xgboost_shadow_adapter.py`:

```python
import pytest

from agent.research_v1.p25_xgboost_shadow_adapter import (
    XGBoostMetaFeatureContract,
    XGBoostShadowAdapterConfig,
    XGBoostShadowAdapterConfigError,
)


def test_default_config_uses_shadow_meta_model_namespace():
    config = XGBoostShadowAdapterConfig.default("shadow_meta_model.xgb_v1")

    assert config.schema_version == "p25_xgb_adapter.0"
    assert config.candidate_namespace == "shadow_meta_model.xgb_v1"
    assert config.score_output_name == "shadow_meta_model.xgb_v1.shadow_predictions"
    assert config.calibration_status == "shadow_dry_run"


def test_config_rejects_non_shadow_namespace():
    with pytest.raises(XGBoostShadowAdapterConfigError, match="candidate_namespace must start with shadow_meta_model."):
        XGBoostShadowAdapterConfig.default("candidate_event.bad")


def test_config_rejects_output_outside_namespace():
    contract = XGBoostMetaFeatureContract.default("shadow_meta_model.xgb_v1")

    with pytest.raises(XGBoostShadowAdapterConfigError, match="output names must stay within candidate namespace"):
        XGBoostShadowAdapterConfig(
            schema_version="p25_xgb_adapter.0",
            candidate_namespace="shadow_meta_model.xgb_v1",
            adapter_name="xgboost_dry_run",
            adapter_version="0.1",
            feature_contract=contract,
            score_output_name="shadow_meta_model.other.shadow_predictions",
            feature_audit_output_name="shadow_meta_model.xgb_v1.feature_audit",
            metadata_output_name="shadow_meta_model.xgb_v1.dry_run_metadata",
            min_rows=1,
            allow_missing_optional_features=True,
            calibration_status="shadow_dry_run",
        )


def test_feature_contract_rejects_non_net_target_basis():
    with pytest.raises(XGBoostShadowAdapterConfigError, match="target_return_basis must be net"):
        XGBoostMetaFeatureContract(
            schema_version="p25_xgb_feature_contract.0",
            required_features=["snapshot_id"],
            optional_features=[],
            target_return_basis="gross",
            point_in_time_required=True,
            forbidden_features=[],
            namespace="shadow_meta_model.xgb_v1",
        )


def test_feature_contract_contains_required_point_in_time_fields():
    contract = XGBoostMetaFeatureContract.default("shadow_meta_model.xgb_v1")

    assert "data_as_of_date" in contract.required_features
    assert "universe_membership_snapshot_id" in contract.required_features
    assert contract.point_in_time_required is True
```

- [ ] **Step 2: Run failing config tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p25_xgboost_shadow_adapter.py -q
```

Expected: FAIL because `p25_xgboost_shadow_adapter.py` does not exist.

- [ ] **Step 3: Implement contract and config**

Create `agent/research_v1/p25_xgboost_shadow_adapter.py`:

```python
"""P25-A XGBoost-style shadow dry adapter.

This module intentionally does not import xgboost or train models. It provides
a deterministic dry-run adapter that exercises the P24 shadow experiment path.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean

from agent.research_v1.p24_shadow_runner import ShadowAdapterResult


REQUIRED_FEATURES = (
    "snapshot_id",
    "ticker",
    "trading_day",
    "company_quality_score",
    "valuation_attractiveness_score",
    "timing_market_fit_score",
    "llm_adjustment_total",
    "coverage_confidence_score",
    "data_as_of_date",
    "universe_membership_snapshot_id",
)

OPTIONAL_FEATURES = (
    "sector",
    "market_cap_bucket",
    "regime_label",
    "negative_signal_strength_decile",
)

FORBIDDEN_FEATURES = (
    "future_return",
    "forward_return",
    "net_return_pct",
    "gross_return_pct",
    "return_value",
    "classification",
    "take_profit",
    "stop_loss",
    "live_trade_signal",
)


class XGBoostShadowAdapterConfigError(ValueError):
    """Raised when P25-A shadow adapter config or feature contract is unsafe."""


@dataclass(frozen=True)
class XGBoostMetaFeatureContract:
    schema_version: str
    required_features: list[str]
    optional_features: list[str]
    target_return_basis: str
    point_in_time_required: bool
    forbidden_features: list[str]
    namespace: str

    def __post_init__(self) -> None:
        if self.schema_version != "p25_xgb_feature_contract.0":
            raise XGBoostShadowAdapterConfigError("schema_version must be p25_xgb_feature_contract.0")
        if self.target_return_basis != "net":
            raise XGBoostShadowAdapterConfigError("target_return_basis must be net")
        if self.point_in_time_required is not True:
            raise XGBoostShadowAdapterConfigError("point_in_time_required must be true")
        if not self.namespace.startswith("shadow_meta_model."):
            raise XGBoostShadowAdapterConfigError("namespace must start with shadow_meta_model.")
        for feature in ("data_as_of_date", "universe_membership_snapshot_id"):
            if feature not in self.required_features:
                raise XGBoostShadowAdapterConfigError(f"required point-in-time feature missing: {feature}")

    @classmethod
    def default(cls, namespace: str) -> "XGBoostMetaFeatureContract":
        return cls(
            schema_version="p25_xgb_feature_contract.0",
            required_features=list(REQUIRED_FEATURES),
            optional_features=list(OPTIONAL_FEATURES),
            target_return_basis="net",
            point_in_time_required=True,
            forbidden_features=list(FORBIDDEN_FEATURES),
            namespace=namespace,
        )


@dataclass(frozen=True)
class XGBoostShadowAdapterConfig:
    schema_version: str
    candidate_namespace: str
    adapter_name: str
    adapter_version: str
    feature_contract: XGBoostMetaFeatureContract
    score_output_name: str
    feature_audit_output_name: str
    metadata_output_name: str
    min_rows: int
    allow_missing_optional_features: bool
    calibration_status: str

    def __post_init__(self) -> None:
        if self.schema_version != "p25_xgb_adapter.0":
            raise XGBoostShadowAdapterConfigError("schema_version must be p25_xgb_adapter.0")
        if not self.candidate_namespace.startswith("shadow_meta_model."):
            raise XGBoostShadowAdapterConfigError("candidate_namespace must start with shadow_meta_model.")
        for output_name in (self.score_output_name, self.feature_audit_output_name, self.metadata_output_name):
            if not _within_namespace(output_name, self.candidate_namespace):
                raise XGBoostShadowAdapterConfigError("output names must stay within candidate namespace")
        if self.feature_contract.namespace != self.candidate_namespace:
            raise XGBoostShadowAdapterConfigError("feature contract namespace must match candidate namespace")
        if self.min_rows < 1:
            raise XGBoostShadowAdapterConfigError("min_rows must be >= 1")
        if self.calibration_status != "shadow_dry_run":
            raise XGBoostShadowAdapterConfigError("calibration_status must be shadow_dry_run")

    @classmethod
    def default(cls, candidate_namespace: str) -> "XGBoostShadowAdapterConfig":
        contract = XGBoostMetaFeatureContract.default(candidate_namespace)
        return cls(
            schema_version="p25_xgb_adapter.0",
            candidate_namespace=candidate_namespace,
            adapter_name="xgboost_dry_run",
            adapter_version="0.1",
            feature_contract=contract,
            score_output_name=f"{candidate_namespace}.shadow_predictions",
            feature_audit_output_name=f"{candidate_namespace}.feature_audit",
            metadata_output_name=f"{candidate_namespace}.dry_run_metadata",
            min_rows=1,
            allow_missing_optional_features=True,
            calibration_status="shadow_dry_run",
        )
```

- [ ] **Step 4: Add namespace helper**

Append to `agent/research_v1/p25_xgboost_shadow_adapter.py`:

```python
def _within_namespace(name: str, namespace: str) -> bool:
    return str(name) == namespace or str(name).startswith(namespace + ".")
```

- [ ] **Step 5: Run config tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p25_xgboost_shadow_adapter.py -q
```

Expected: PASS for config tests.

---

## Task 2: Adapter Validation and Stub Scoring

**Files:**
- Modify: `agent/research_v1/p25_xgboost_shadow_adapter.py`
- Modify: `tests/agent/research_v1/test_p25_xgboost_shadow_adapter.py`

- [ ] **Step 1: Add adapter tests**

Append to `tests/agent/research_v1/test_p25_xgboost_shadow_adapter.py`:

```python
from agent.research_v1.p24_shadow_runner import ShadowAdapterResult
from agent.research_v1.p25_xgboost_shadow_adapter import XGBoostDryRunAdapter


def _valid_row(**overrides):
    row = {
        "snapshot_id": "snap_1",
        "ticker": "MSFT",
        "trading_day": "2026-01-05",
        "company_quality_score": 80,
        "valuation_attractiveness_score": 60,
        "timing_market_fit_score": 50,
        "llm_adjustment_total": 10,
        "coverage_confidence_score": 0.9,
        "data_as_of_date": "2026-01-04",
        "universe_membership_snapshot_id": "sp500_2026_01_05",
        "sector": "technology",
    }
    row.update(overrides)
    return row


def test_adapter_returns_shadow_adapter_result():
    adapter = XGBoostDryRunAdapter(XGBoostShadowAdapterConfig.default("shadow_meta_model.xgb_v1"), [_valid_row()])

    result = adapter.run(manifest=None, request=None)

    assert isinstance(result, ShadowAdapterResult)
    assert result.adapter_name == "xgboost_dry_run"
    assert result.produced_artifacts == [
        "shadow_meta_model.xgb_v1.shadow_predictions",
        "shadow_meta_model.xgb_v1.feature_audit",
        "shadow_meta_model.xgb_v1.dry_run_metadata",
    ]
    assert result.metrics["input_rows"] == 1
    assert result.metrics["valid_rows"] == 1


def test_adapter_excludes_rows_with_missing_required_features():
    row = _valid_row()
    del row["data_as_of_date"]
    adapter = XGBoostDryRunAdapter(XGBoostShadowAdapterConfig.default("shadow_meta_model.xgb_v1"), [row])

    result = adapter.run(manifest=None, request=None)

    assert result.metrics["input_rows"] == 1
    assert result.metrics["valid_rows"] == 0
    assert result.metrics["missing_required_feature_rows"] == 1
    assert "row_excluded_missing_required_features" in result.warnings


def test_adapter_excludes_rows_with_forbidden_future_return_features():
    row = _valid_row(future_return=0.20)
    adapter = XGBoostDryRunAdapter(XGBoostShadowAdapterConfig.default("shadow_meta_model.xgb_v1"), [row])

    result = adapter.run(manifest=None, request=None)

    assert result.metrics["valid_rows"] == 0
    assert result.metrics["forbidden_feature_rows"] == 1
    assert "row_excluded_forbidden_features" in result.warnings


def test_adapter_emits_optional_feature_warnings():
    row = _valid_row()
    del row["sector"]
    adapter = XGBoostDryRunAdapter(XGBoostShadowAdapterConfig.default("shadow_meta_model.xgb_v1"), [row])

    result = adapter.run(manifest=None, request=None)

    assert result.metrics["valid_rows"] == 1
    assert "missing_optional_features:sector" in result.warnings


def test_stub_scores_are_deterministic_and_clamped():
    config = XGBoostShadowAdapterConfig.default("shadow_meta_model.xgb_v1")
    row = _valid_row(
        company_quality_score=120,
        valuation_attractiveness_score=100,
        timing_market_fit_score=100,
        llm_adjustment_total=50,
        coverage_confidence_score=2,
    )
    adapter_a = XGBoostDryRunAdapter(config, [row])
    adapter_b = XGBoostDryRunAdapter(config, [row])

    result_a = adapter_a.run(manifest=None, request=None)
    result_b = adapter_b.run(manifest=None, request=None)

    assert result_a.metrics["stub_score_min"] == result_b.metrics["stub_score_min"]
    assert 0 <= result_a.metrics["stub_score_min"] <= 1
    assert 0 <= result_a.metrics["stub_score_max"] <= 1
```

- [ ] **Step 2: Run failing adapter tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p25_xgboost_shadow_adapter.py -q
```

Expected: FAIL because `XGBoostDryRunAdapter` does not exist.

- [ ] **Step 3: Implement adapter**

Append to `agent/research_v1/p25_xgboost_shadow_adapter.py`:

```python
@dataclass(frozen=True)
class _ValidatedRows:
    valid_rows: list[dict]
    missing_required_feature_rows: int
    forbidden_feature_rows: int
    warnings: list[str]


class XGBoostDryRunAdapter:
    def __init__(self, config: XGBoostShadowAdapterConfig, feature_rows: list[dict]) -> None:
        self.config = config
        self.feature_rows = list(feature_rows)
        self.adapter_name = config.adapter_name
        self.adapter_version = config.adapter_version

    def run(self, manifest, request) -> ShadowAdapterResult:
        validated = _validate_rows(self.config.feature_contract, self.feature_rows, self.config.allow_missing_optional_features)
        scores = [_stub_score(row) for row in validated.valid_rows]
        metrics = _build_metrics(
            input_rows=len(self.feature_rows),
            validated=validated,
            scores=scores,
        )
        produced = [
            self.config.score_output_name,
            self.config.feature_audit_output_name,
            self.config.metadata_output_name,
        ]
        return ShadowAdapterResult(
            adapter_name=self.adapter_name,
            adapter_version=self.adapter_version,
            produced_artifacts=produced,
            attempted_outputs=produced,
            metrics=metrics,
            logs=["p25_xgboost_shadow_dry_adapter_completed"],
            warnings=validated.warnings,
        )
```

- [ ] **Step 4: Implement validation and scoring helpers**

Append to `agent/research_v1/p25_xgboost_shadow_adapter.py`:

```python
def _validate_rows(
    contract: XGBoostMetaFeatureContract,
    rows: list[dict],
    allow_missing_optional_features: bool,
) -> _ValidatedRows:
    valid_rows: list[dict] = []
    missing_required_count = 0
    forbidden_count = 0
    warnings: list[str] = []
    missing_optional_seen: set[str] = set()

    for row in rows:
        missing_required = [feature for feature in contract.required_features if feature not in row or row.get(feature) in (None, "")]
        forbidden_present = [feature for feature in contract.forbidden_features if feature in row]
        if missing_required:
            missing_required_count += 1
            continue
        if forbidden_present:
            forbidden_count += 1
            continue
        for feature in contract.optional_features:
            if feature not in row and feature not in missing_optional_seen:
                missing_optional_seen.add(feature)
                if allow_missing_optional_features:
                    warnings.append(f"missing_optional_features:{feature}")
        valid_rows.append(dict(row))

    if missing_required_count:
        warnings.append("row_excluded_missing_required_features")
    if forbidden_count:
        warnings.append("row_excluded_forbidden_features")
    return _ValidatedRows(
        valid_rows=valid_rows,
        missing_required_feature_rows=missing_required_count,
        forbidden_feature_rows=forbidden_count,
        warnings=warnings,
    )


def _normalize_score(value) -> float:
    numeric = float(value)
    if numeric > 1:
        numeric = numeric / 100.0
    return _clamp(numeric, 0.0, 1.0)


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _stub_score(row: dict) -> float:
    quality = _normalize_score(row["company_quality_score"])
    valuation = _normalize_score(row["valuation_attractiveness_score"])
    timing = _normalize_score(row["timing_market_fit_score"])
    llm_adjustment = _clamp(float(row["llm_adjustment_total"]), -15.0, 15.0) / 100.0
    coverage = _clamp(float(row["coverage_confidence_score"]), 0.0, 1.0)
    base = (0.45 * quality) + (0.30 * valuation) + (0.20 * timing) + (0.05 * llm_adjustment)
    return round(_clamp(base * coverage, 0.0, 1.0), 6)


def _build_metrics(input_rows: int, validated: _ValidatedRows, scores: list[float]) -> dict:
    if scores:
        score_min = min(scores)
        score_max = max(scores)
        score_mean = round(mean(scores), 6)
    else:
        score_min = 0.0
        score_max = 0.0
        score_mean = 0.0
    return {
        "input_rows": input_rows,
        "valid_rows": len(validated.valid_rows),
        "missing_required_feature_rows": validated.missing_required_feature_rows,
        "forbidden_feature_rows": validated.forbidden_feature_rows,
        "stub_score_min": score_min,
        "stub_score_max": score_max,
        "stub_score_mean": score_mean,
    }
```

- [ ] **Step 5: Run adapter tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p25_xgboost_shadow_adapter.py -q
```

Expected: PASS for config and adapter tests.

---

## Task 3: P24 Integration Path

**Files:**
- Modify: `tests/agent/research_v1/test_p25_xgboost_shadow_adapter.py`

- [ ] **Step 1: Add P24 integration fixtures and test**

Append to `tests/agent/research_v1/test_p25_xgboost_shadow_adapter.py`:

```python
from agent.research_v1.p24_entry_gate import P24CandidateRequest, P24SystemEvidence, evaluate_p24_entry_gate
from agent.research_v1.p24_experiment_registry import ShadowExperimentRegistry, ShadowExperimentRequest
from agent.research_v1.p24_health_report import build_shadow_experiment_health_report
from agent.research_v1.p24_run_persistence import ShadowRunStore
from agent.research_v1.p24_shadow_runner import ShadowExperimentRunRequest, run_shadow_experiment


def _gate_report():
    request = P24CandidateRequest(
        candidate_name="xgb_meta_v1",
        candidate_family="xgboost_meta_model",
        candidate_namespace="shadow_meta_model.xgb_v1",
        requested_phase="P25",
        intended_outputs=["shadow_meta_model.xgb_v1.shadow_predictions"],
        uses_point_in_time_sources=True,
        source_audit_plan_defined=True,
        simple_baseline_defined=True,
        out_of_sample_plan_defined=True,
        uses_gross_returns_as_primary=False,
        writes_production_fields=False,
        requires_portfolio_layer=False,
        requires_execution_data=False,
        residualization_plan_defined=False,
        notes="p25 xgb adapter",
    )
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
    return evaluate_p24_entry_gate(request, evidence)


def _manifest():
    registry = ShadowExperimentRegistry()
    request = ShadowExperimentRequest(
        experiment_id="exp_xgb_meta_v1",
        candidate_id="xgb_meta_v1",
        candidate_name="xgb_meta_v1",
        candidate_family="xgboost_meta_model",
        candidate_namespace="shadow_meta_model.xgb_v1",
        source_gate_report_id="gate_xgb_meta_v1",
        owner="research",
        purpose="P25 XGBoost dry adapter integration.",
        input_contract={
            "allowed_sources": ["factor_snapshots"],
            "required_point_in_time_fields": ["data_as_of_date", "universe_membership_snapshot_id"],
            "forbidden_sources": ["future_prices"],
            "max_source_audit_gap_rate": 0.20,
            "lookahead_policy": "strict_no_future_data",
        },
        output_contract={
            "allowed_outputs": [
                "shadow_meta_model.xgb_v1.shadow_predictions",
                "shadow_meta_model.xgb_v1.feature_audit",
                "shadow_meta_model.xgb_v1.dry_run_metadata",
            ],
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
        expected_artifacts=["shadow_predictions", "feature_audit", "dry_run_metadata"],
        notes="p25 integration",
    )
    return registry.register_shadow_experiment(request, _gate_report())


def test_adapter_runs_through_p24_runner_persistence_and_health_report():
    manifest = _manifest()
    adapter = XGBoostDryRunAdapter(
        XGBoostShadowAdapterConfig.default("shadow_meta_model.xgb_v1"),
        [_valid_row()],
    )
    run_request = ShadowExperimentRunRequest(
        run_id="run_xgb_meta_v1_001",
        experiment_id="exp_xgb_meta_v1",
        run_mode="shadow_stub",
        input_window={
            "start_date": "2026-01-01",
            "end_date": "2026-03-31",
            "data_as_of_policy": "manifest_point_in_time_policy",
            "point_in_time_required": True,
        },
        requested_artifacts=["shadow_meta_model.xgb_v1.shadow_predictions"],
        operator="codex",
        reason="p25 integration",
        notes="shadow stub",
    )

    runner_result = run_shadow_experiment(manifest, adapter, run_request)
    store = ShadowRunStore()
    store.save_run_record(runner_result.record)
    report = build_shadow_experiment_health_report([manifest], store)

    assert runner_result.record.status == "completed"
    assert runner_result.adapter_result.metrics["valid_rows"] == 1
    assert report.total_experiments == 1
    assert report.experiments[0].health_status == "healthy"
```

- [ ] **Step 2: Run P25 tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p25_xgboost_shadow_adapter.py -q
```

Expected: all P25-A tests PASS.

---

## Task 4: No Model Libraries and Regression

**Files:**
- Modify: `tests/agent/research_v1/test_p25_xgboost_shadow_adapter.py`

- [ ] **Step 1: Add no-model-library test**

Append to `tests/agent/research_v1/test_p25_xgboost_shadow_adapter.py`:

```python
def test_xgboost_shadow_adapter_module_does_not_import_model_libraries():
    import agent.research_v1.p25_xgboost_shadow_adapter as adapter_module

    module_names = set(adapter_module.__dict__)
    forbidden_names = {"xgboost", "torch", "tensorflow", "sklearn", "stable_baselines3"}

    assert module_names.isdisjoint(forbidden_names)
```

- [ ] **Step 2: Run P25-A tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p25_xgboost_shadow_adapter.py -q
```

Expected: all P25-A tests PASS.

- [ ] **Step 3: Run P24/P25 integration tests**

Run:

```bash
python3.11 -m pytest \
  tests/agent/research_v1/test_p24_entry_gate.py \
  tests/agent/research_v1/test_p24_experiment_registry.py \
  tests/agent/research_v1/test_p24_shadow_runner.py \
  tests/agent/research_v1/test_p24_run_persistence.py \
  tests/agent/research_v1/test_p24_health_report.py \
  tests/agent/research_v1/test_p25_xgboost_shadow_adapter.py \
  -q
```

Expected: all selected tests PASS.

- [ ] **Step 4: Run P20-P25 regression bundle**

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
  tests/agent/research_v1/test_p25_xgboost_shadow_adapter.py \
  -q
```

Expected: all selected tests PASS.

- [ ] **Step 5: Scan for forbidden model imports**

Run:

```bash
grep -R "import xgboost\|from xgboost\|import torch\|from torch\|import tensorflow\|from tensorflow\|stable_baselines\|import sklearn\|from sklearn" -n \
  agent/research_v1/p25_xgboost_shadow_adapter.py \
  tests/agent/research_v1/test_p25_xgboost_shadow_adapter.py || true
```

Expected: no output except possible string literals inside the no-model-library test.

---

## Final Handoff Format

Return:

```text
P25-A XGBoost Meta-Model Shadow Dry Adapter Handoff

Changed files:
- <path> — <created/modified> — <purpose>

Tests run:
- <command> → <result>

Acceptance checklist:
- feature contract exists: yes/no
- adapter config exists: yes/no
- namespace validation works: yes/no
- point-in-time fields required: yes/no
- forbidden features blocked: yes/no
- missing required feature rows excluded: yes/no
- optional feature warnings emitted: yes/no
- stub scores deterministic and clamped: yes/no
- outputs stay under shadow_meta_model namespace: yes/no
- P24 runner executes adapter: yes/no
- P24 persistence stores run: yes/no
- P24 health report sees experiment: yes/no
- no model libraries imported: yes/no
- no production outputs written: yes/no
- P20-P25 regression green: yes/no

Known issues:
- <issue or None>
```
