# P21 Calibration Inputs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Hermes P21 decision parameters explicit, versioned, testable prior-only calibration inputs before P22 consumes factor snapshots and forward returns.

**Architecture:** Extend the existing P20 modules instead of creating a parallel scoring stack. `calibration_config.py` becomes the canonical home for weights, thresholds, exits, valuation benchmarks, sizing, and regime config; existing scoring modules receive injected config while preserving backward-compatible outputs. Add focused tests that prove behavior is config-driven and P22 defaults to net returns.

**Tech Stack:** Python 3.11, dataclasses, pytest, existing `agent/research_v1` modules, no new external dependencies.

---

## Source Spec

Primary spec:

- `docs/superpowers/specs/2026-04-24-hermes-p21-calibration-inputs-spec.md`

Prior roadmap/spec:

- `docs/superpowers/specs/2026-04-24-hermes-p20-p22-factor-calibration-roadmap-spec.md`
- `docs/superpowers/plans/2026-04-24-p20-p22-pnl-integrity-factor-calibration.md`

## File Structure

### Create

- `agent/research_v1/p22_return_selector.py`
  - Minimal P21 helper proving P22 diagnostics default to `net_return_pct` and can explicitly select `gross_return_pct`.
- `agent/research_v1/regime_gate.py`
  - P21 v1 regime feature contract and conservative gate evaluator.
- `tests/agent/research_v1/test_p21_calibration_inputs.py`
  - Focused P21 acceptance tests.

### Modify

- `agent/research_v1/calibration_config.py`
  - Add config metadata/status, exit config, sector valuation config, sizing config, and regime config.
- `agent/research_v1/exit_planning.py`
  - Use/re-export canonical `ExitPlanConfig` from calibration config.
- `agent/research_v1/final_judge.py`
  - Allow injected `RoleWeightConfig` while preserving `ROLE_WEIGHTS`.
- `agent/research_v1/grading.py`
  - Validate merged dynamic weights and use config-derived weights only.
- `agent/research_v1/valuation_models.py`
  - Use `SectorBenchmarkConfig` and return benchmark metadata.
- `agent/research_v1/trade_plan.py`
  - Add volatility-aware sizing output fields and cap flags.
- `agent/research_v1/stress_testing.py`
  - Keep boss-facing output disabled unless real resimulation is enabled; add a test if not already covered.

---

### Task 1: Add P21 Calibration Config Contracts

**Files:**
- Modify: `agent/research_v1/calibration_config.py`
- Test: `tests/agent/research_v1/test_p21_calibration_inputs.py`

- [ ] **Step 1: Write failing tests for config contracts**

Create `tests/agent/research_v1/test_p21_calibration_inputs.py` with:

```python
import pytest

from agent.research_v1.calibration_config import (
    CalibrationMetadata,
    ExitPlanConfig,
    GradingWeightConfig,
    PositionSizingConfig,
    RegimeGateConfig,
    RoleWeight,
    RoleWeightConfig,
    SectorBenchmarkConfig,
    ThesisThresholdConfig,
)


def test_calibration_metadata_defaults_to_p21_prior_only():
    meta = CalibrationMetadata(config_name="test")
    assert meta.config_version == "p21.0"
    assert meta.calibration_status == "prior_only"
    assert meta.source == "engineering_prior"


def test_thesis_threshold_config_carries_metadata():
    config = ThesisThresholdConfig()
    assert config.config_version == "p21.0"
    assert config.calibration_status == "prior_only"


def test_exit_plan_config_is_prior_only_and_versioned():
    config = ExitPlanConfig(stop_multiple=2.0, target_multiple=3.0)
    assert config.calibration_status == "prior_only"
    assert config.config_version == "p21.0"
    assert config.horizon_bucket == "default"


def test_role_weight_config_rejects_zero_without_reason():
    config = RoleWeightConfig(weights={"risk": RoleWeight(0.0)})
    with pytest.raises(ValueError, match="zero weight without disabled_with_reason"):
        config.as_plain_weights()


def test_grading_weight_config_rejects_invalid_dynamic_override_sum():
    base = GradingWeightConfig()
    with pytest.raises(ValueError, match="sum to 1.0"):
        base.with_overrides({"fundamental": 0.9})


def test_sector_benchmark_config_returns_sector_and_fallback_metadata():
    config = SectorBenchmarkConfig()
    tech = config.get("technology")
    unknown = config.get("unknown-sector")
    assert tech["multiples"]["pe"] != unknown["multiples"]["pe"]
    assert tech["used_fallback"] is False
    assert unknown["used_fallback"] is True
    assert unknown["calibration_status"] == "prior_only"


def test_position_sizing_config_validates_caps():
    with pytest.raises(ValueError, match="max_single_name_weight"):
        PositionSizingConfig(max_single_name_weight=1.5)
    with pytest.raises(ValueError, match="max_position_as_pct_adv"):
        PositionSizingConfig(max_position_as_pct_adv=-0.1)


def test_regime_gate_config_defaults_to_insufficient_definition():
    config = RegimeGateConfig()
    assert config.calibration_status == "prior_only"
    assert config.missing_data_status == "insufficient_definition"
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p21_calibration_inputs.py -q
```

Expected: FAIL because the new classes/methods do not exist yet.

- [ ] **Step 3: Implement config contracts**

Modify `agent/research_v1/calibration_config.py` to include these definitions while preserving existing public classes:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

CALIBRATION_STATUSES = {"prior_only", "shadow_observed", "calibrated", "disabled"}


def _validate_status(status: str) -> None:
    if status not in CALIBRATION_STATUSES:
        raise ValueError(f"invalid calibration_status: {status}")


@dataclass(frozen=True)
class CalibrationMetadata:
    config_name: str
    config_version: str = "p21.0"
    calibration_status: str = "prior_only"
    source: str = "engineering_prior"

    def __post_init__(self):
        _validate_status(self.calibration_status)


@dataclass(frozen=True)
class ThesisThresholdConfig:
    no_trade_quality_threshold: float = 0.35
    investable_quality_threshold: float = 0.65
    investable_valuation_threshold: float = 0.15
    investable_catalyst_threshold: float = 0.50
    config_version: str = "p21.0"
    calibration_status: str = "prior_only"

    def __post_init__(self):
        _validate_status(self.calibration_status)


@dataclass(frozen=True)
class RoleWeight:
    weight: float
    disabled_with_reason: Optional[str] = None


@dataclass(frozen=True)
class RoleWeightConfig:
    config_version: str = "p21.0"
    calibration_status: str = "prior_only"
    weights: dict = field(default_factory=lambda: {
        "fundamentals": RoleWeight(0.40),
        "technical": RoleWeight(0.25),
        "news": RoleWeight(0.15),
        "sentiment": RoleWeight(0.10),
        "industry": RoleWeight(0.05),
        "options": RoleWeight(0.05),
        "risk": RoleWeight(0.00, "risk informs warnings until P22 IC calibration"),
        "valuation": RoleWeight(0.00, "valuation handled by thesis layer until P22 IC calibration"),
    })

    def __post_init__(self):
        _validate_status(self.calibration_status)

    def as_plain_weights(self) -> dict:
        plain: dict = {}
        for role, config in self.weights.items():
            if config.weight < 0:
                raise ValueError(f"role {role} has negative weight")
            if config.weight == 0.0 and not config.disabled_with_reason:
                raise ValueError(f"role {role} has zero weight without disabled_with_reason")
            plain[role] = config.weight
        return plain


@dataclass(frozen=True)
class GradingWeightConfig:
    fundamental: float = 0.40
    technical: float = 0.30
    macro: float = 0.30
    config_version: str = "p21.0"
    calibration_status: str = "prior_only"

    def __post_init__(self):
        _validate_status(self.calibration_status)
        self._validate_sum()

    def _validate_sum(self) -> None:
        total = self.fundamental + self.technical + self.macro
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Grading weights must sum to 1.0, got {total}")
        if self.fundamental < 0 or self.technical < 0 or self.macro < 0:
            raise ValueError("Grading weights must be non-negative")

    def with_overrides(self, overrides: dict[str, float]) -> "GradingWeightConfig":
        values = {
            "fundamental": self.fundamental,
            "technical": self.technical,
            "macro": self.macro,
        }
        for key, value in overrides.items():
            if key not in values:
                raise ValueError(f"unknown grading weight override: {key}")
            values[key] = float(value)
        return GradingWeightConfig(
            fundamental=values["fundamental"],
            technical=values["technical"],
            macro=values["macro"],
            config_version=self.config_version,
            calibration_status=self.calibration_status,
        )


@dataclass(frozen=True)
class ExitPlanConfig:
    stop_multiple: float = 2.0
    target_multiple: float = 3.0
    horizon_bucket: str = "default"
    config_version: str = "p21.0"
    calibration_status: str = "prior_only"

    def __post_init__(self):
        _validate_status(self.calibration_status)
        if self.stop_multiple <= 0 or self.target_multiple <= 0:
            raise ValueError("exit multiples must be positive")


@dataclass(frozen=True)
class SectorBenchmarkConfig:
    config_version: str = "p21.0"
    calibration_status: str = "prior_only"
    sector_multiples: dict = field(default_factory=lambda: {
        "technology": {"pe": 26.0, "pb": 8.0, "ps": 7.0},
        "financials": {"pe": 12.0, "pb": 1.4, "ps": 3.0},
        "healthcare": {"pe": 22.0, "pb": 4.5, "ps": 5.0},
        "consumer_discretionary": {"pe": 20.0, "pb": 4.0, "ps": 2.5},
        "industrials": {"pe": 18.0, "pb": 3.0, "ps": 2.0},
        "default": {"pe": 18.0, "pb": 3.0, "ps": 4.0},
    })

    def __post_init__(self):
        _validate_status(self.calibration_status)

    def normalize_sector(self, sector: str | None) -> str:
        return (sector or "default").strip().lower().replace(" ", "_")

    def get(self, sector: str | None) -> dict:
        key = self.normalize_sector(sector)
        used_fallback = key not in self.sector_multiples
        resolved_key = key if not used_fallback else "default"
        return {
            "sector": key,
            "resolved_sector": resolved_key,
            "used_fallback": used_fallback,
            "multiples": dict(self.sector_multiples[resolved_key]),
            "config_version": self.config_version,
            "calibration_status": self.calibration_status,
        }


@dataclass(frozen=True)
class PositionSizingConfig:
    target_position_volatility: float = 0.02
    max_single_name_weight: float = 0.05
    max_position_as_pct_adv: float = 0.05
    min_position_units: int = 1
    config_version: str = "p21.0"
    calibration_status: str = "prior_only"

    def __post_init__(self):
        _validate_status(self.calibration_status)
        if not 0 < self.max_single_name_weight <= 1:
            raise ValueError("max_single_name_weight must be in (0, 1]")
        if not 0 <= self.max_position_as_pct_adv <= 1:
            raise ValueError("max_position_as_pct_adv must be in [0, 1]")
        if self.target_position_volatility <= 0:
            raise ValueError("target_position_volatility must be positive")
        if self.min_position_units < 0:
            raise ValueError("min_position_units must be non-negative")


@dataclass(frozen=True)
class RegimeGateConfig:
    vix_fail_percentile: float = 0.95
    realized_vol_fail_percentile: float = 0.95
    breadth_warn_percentile: float = 0.20
    dispersion_fail_percentile: float = 0.95
    missing_data_status: str = "insufficient_definition"
    config_version: str = "p21.0"
    calibration_status: str = "prior_only"

    def __post_init__(self):
        _validate_status(self.calibration_status)
        if self.missing_data_status not in {"stubbed", "insufficient_definition"}:
            raise ValueError("missing_data_status must be stubbed or insufficient_definition")
```

- [ ] **Step 4: Run config tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p21_calibration_inputs.py -q
```

Expected: the config tests in Task 1 pass; later tests may not exist yet.

---

### Task 2: Wire Config Into Exits, Final Judge, and Grading

**Files:**
- Modify: `agent/research_v1/exit_planning.py`
- Modify: `agent/research_v1/final_judge.py`
- Modify: `agent/research_v1/grading.py`
- Test: `tests/agent/research_v1/test_p21_calibration_inputs.py`

- [ ] **Step 1: Add failing tests for injected config behavior**

Append to `tests/agent/research_v1/test_p21_calibration_inputs.py`:

```python
from agent.research_v1.exit_planning import build_exit_plan
from agent.research_v1.final_judge import FinalJudge
from agent.research_v1.grading import GradingAgent


class DummyLLM:
    pass


def test_exit_plan_uses_canonical_config_metadata():
    config = ExitPlanConfig(stop_multiple=1.5, target_multiple=2.5)
    plan = build_exit_plan(entry_price=100.0, atr_20=4.0, config=config)
    assert plan.stop_loss == 94.0
    assert plan.take_profit == 110.0
    assert plan.calibration_status == "prior_only"
    assert plan.config_version == "p21.0"


def test_final_judge_accepts_injected_role_weight_config():
    config = RoleWeightConfig(weights={
        "fundamentals": RoleWeight(1.0),
        "risk": RoleWeight(0.0, "disabled in test"),
    })
    judge = FinalJudge(role_weight_config=config)
    assert judge.role_weights["fundamentals"] == 1.0
    assert judge.role_weights["risk"] == 0.0


def test_grading_agent_rejects_invalid_dynamic_weight_merge():
    with pytest.raises(ValueError, match="sum to 1.0"):
        GradingAgent(llm_client=DummyLLM(), dynamic_weights={"fundamental": 0.9})
```

- [ ] **Step 2: Run new tests to verify failure**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p21_calibration_inputs.py -q
```

Expected: FAIL because `ExitPlan.config_version`, `FinalJudge(role_weight_config=...)`, or `GradingWeightConfig.with_overrides()` wiring is missing.

- [ ] **Step 3: Update `exit_planning.py`**

Modify imports and dataclass fields:

```python
from agent.research_v1.calibration_config import ExitPlanConfig
```

Remove the local `ExitPlanConfig` definition from `exit_planning.py`. Add `config_version` to `ExitPlan`:

```python
config_version: str
```

In `build_exit_plan()`, set:

```python
config_version=active_config.config_version,
```

- [ ] **Step 4: Update `final_judge.py`**

Change initialization and composite score usage:

```python
ROLE_WEIGHTS = RoleWeightConfig().as_plain_weights()


class FinalJudge:
    def __init__(self, role_weight_config: RoleWeightConfig | None = None):
        self.role_weight_config = role_weight_config or RoleWeightConfig()
        self.role_weights = self.role_weight_config.as_plain_weights()
```

In `_compute_composite_score()`, replace:

```python
weight = ROLE_WEIGHTS.get(role, 0.05)
```

with:

```python
weight = self.role_weights.get(role, 0.05)
```

- [ ] **Step 5: Update `grading.py` dynamic weight resolution**

In `GradingAgent.__init__()`, replace direct dynamic override storage with validated merge:

```python
self.grading_weights = grading_weights or GradingWeightConfig()
if dynamic_weights:
    self.grading_weights = self.grading_weights.with_overrides(dynamic_weights)
self.dynamic_weights = dynamic_weights or {}
self.fundamental_weight, self.technical_weight, self.macro_weight = self._resolve_weights()
```

Update `_resolve_weights()` to return only config-derived values:

```python
def _resolve_weights(self) -> tuple[float, float, float]:
    return (
        self.grading_weights.fundamental,
        self.grading_weights.technical,
        self.grading_weights.macro,
    )
```

- [ ] **Step 6: Run targeted tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p21_calibration_inputs.py tests/agent/research_v1/test_final_judge.py tests/agent/research_v1/test_review_grade_monitor.py -q
```

Expected: PASS.

---

### Task 3: Make Sector Valuation Config-Auditable

**Files:**
- Modify: `agent/research_v1/valuation_models.py`
- Test: `tests/agent/research_v1/test_p21_calibration_inputs.py`
- Regression Test: `tests/agent/research_v1/test_p4_valuation_risk.py`

- [ ] **Step 1: Add failing valuation metadata test**

Append:

```python
from agent.research_v1.valuation_models import calculate_relative_valuation


def test_relative_valuation_reports_sector_benchmark_metadata():
    result = calculate_relative_valuation(
        market_data={"eps": 5.0, "book_value_per_share": 20.0, "sales_per_share": 12.0},
        benchmark_multiples={"sector": "technology"},
    )
    assert result["target_price"] is not None
    assert result["benchmark_metadata"]["resolved_sector"] == "technology"
    assert result["benchmark_metadata"]["used_fallback"] is False
    assert result["benchmark_metadata"]["calibration_status"] == "prior_only"


def test_relative_valuation_reports_default_fallback_metadata():
    result = calculate_relative_valuation(
        market_data={"eps": 5.0},
        benchmark_multiples={"sector": "unknown-sector"},
    )
    assert result["benchmark_metadata"]["resolved_sector"] == "default"
    assert result["benchmark_metadata"]["used_fallback"] is True
```

- [ ] **Step 2: Run valuation tests to verify failure**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p21_calibration_inputs.py::test_relative_valuation_reports_sector_benchmark_metadata tests/agent/research_v1/test_p21_calibration_inputs.py::test_relative_valuation_reports_default_fallback_metadata -q
```

Expected: FAIL because `benchmark_metadata` is missing.

- [ ] **Step 3: Update valuation model**

In `agent/research_v1/valuation_models.py`, import config:

```python
from agent.research_v1.calibration_config import SectorBenchmarkConfig
```

Replace module-level benchmark lookup with:

```python
def get_sector_benchmark_multiples(sector: str | None) -> dict:
    payload = SectorBenchmarkConfig().get(sector)
    return dict(payload["multiples"])
```

Inside `calculate_relative_valuation()`, initialize metadata:

```python
benchmark_metadata = None
```

When sector lookup is used:

```python
payload = SectorBenchmarkConfig().get(benchmark_multiples["sector"])
multiples = payload["multiples"]
benchmark_metadata = {k: v for k, v in payload.items() if k != "multiples"}
```

In the return payload, include:

```python
"benchmark_metadata": benchmark_metadata,
```

For the no-methods return, include the same key:

```python
return {"methods": {}, "target_price": None, "benchmark_metadata": benchmark_metadata}
```

- [ ] **Step 4: Run valuation regression**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p21_calibration_inputs.py tests/agent/research_v1/test_p4_valuation_risk.py -q
```

Expected: PASS.

---

### Task 4: Add Volatility-Aware Trade Sizing

**Files:**
- Modify: `agent/research_v1/trade_plan.py`
- Test: `tests/agent/research_v1/test_p21_calibration_inputs.py`

- [ ] **Step 1: Add failing trade sizing tests**

Append:

```python
from agent.research_v1.contracts import CanonicalSignal
from agent.research_v1.trade_plan import TradePlanGenerator


def _signal(**extra_attrs):
    signal = CanonicalSignal(
        ticker="AAPL",
        rating="BUY",
        confidence=0.8,
        priority_score=8.0,
        entry_price=100.0,
        stop_loss=94.0,
        take_profit=112.0,
        holding_horizon="20d",
        risk_flags=[],
        decision_reason="test",
    )
    for name, value in extra_attrs.items():
        setattr(signal, name, value)
    return signal


def test_trade_plan_includes_volatility_aware_sizing_metadata():
    generator = TradePlanGenerator(
        sizing_config=PositionSizingConfig(
            target_position_volatility=0.02,
            max_single_name_weight=0.05,
            max_position_as_pct_adv=0.05,
        )
    )
    plan = generator.generate(
        _signal(signal_volatility=0.20, portfolio_equity=100_000, adv_shares_20d=1_000_000)
    )
    assert plan["suggested_position_size"] >= 1
    assert 0 < plan["suggested_position_weight"] <= 0.05
    assert plan["target_position_volatility"] == 0.02
    assert plan["input_signal_volatility"] == 0.20
    assert plan["calibration_status"] == "prior_only"
    assert "sizing_flags" in plan


def test_trade_plan_caps_position_by_adv_and_single_name_weight():
    generator = TradePlanGenerator(
        sizing_config=PositionSizingConfig(
            target_position_volatility=0.10,
            max_single_name_weight=0.05,
            max_position_as_pct_adv=0.01,
        )
    )
    plan = generator.generate(
        _signal(signal_volatility=0.01, portfolio_equity=1_000_000, adv_shares_20d=20_000)
    )
    assert plan["single_name_cap_applied"] is True or plan["adv_cap_applied"] is True
```


- [ ] **Step 2: Run sizing tests to verify failure**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p21_calibration_inputs.py -q
```

Expected: FAIL because `TradePlanGenerator` does not accept sizing config or output sizing metadata.

- [ ] **Step 3: Update `TradePlanGenerator`**

Modify `agent/research_v1/trade_plan.py`:

```python
from agent.research_v1.calibration_config import PositionSizingConfig
```

Add constructor:

```python
class TradePlanGenerator:
    def __init__(self, sizing_config: PositionSizingConfig | None = None):
        self.sizing_config = sizing_config or PositionSizingConfig()
```

Inside `generate()`, after the legacy integer size calculation, compute:

```python
signal_volatility = getattr(signal, "signal_volatility", None)
portfolio_equity = getattr(signal, "portfolio_equity", None)
adv_shares_20d = getattr(signal, "adv_shares_20d", None)
sizing_flags = []

if not signal_volatility or signal_volatility <= 0:
    signal_volatility = 0.30
    sizing_flags.append("missing_signal_volatility")
if not portfolio_equity or portfolio_equity <= 0:
    portfolio_equity = entry_price * max(suggested_position_size, 1)
    sizing_flags.append("missing_portfolio_equity")

raw_weight = self.sizing_config.target_position_volatility / signal_volatility
confidence_scaled_weight = raw_weight * max(0.0, min(1.0, confidence))
single_name_cap_applied = confidence_scaled_weight > self.sizing_config.max_single_name_weight
suggested_position_weight = min(confidence_scaled_weight, self.sizing_config.max_single_name_weight)

adv_cap_applied = False
if adv_shares_20d and entry_price > 0 and portfolio_equity > 0:
    max_shares_by_adv = adv_shares_20d * self.sizing_config.max_position_as_pct_adv
    shares_by_weight = (portfolio_equity * suggested_position_weight) / entry_price
    if shares_by_weight > max_shares_by_adv:
        adv_cap_applied = True
        suggested_position_weight = (max_shares_by_adv * entry_price) / portfolio_equity

vol_position_units = round((portfolio_equity * suggested_position_weight) / entry_price) if entry_price > 0 else 0
suggested_position_size = max(self.sizing_config.min_position_units, vol_position_units, suggested_position_size)
```

Add fields to returned dict:

```python
"suggested_position_weight": round(suggested_position_weight, 6),
"target_position_volatility": self.sizing_config.target_position_volatility,
"input_signal_volatility": signal_volatility,
"adv_cap_applied": adv_cap_applied,
"single_name_cap_applied": single_name_cap_applied,
"sizing_flags": sizing_flags,
"calibration_status": self.sizing_config.calibration_status,
"sizing_config_version": self.sizing_config.config_version,
```

- [ ] **Step 4: Run trade-plan and existing tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p21_calibration_inputs.py tests/agent/research_v1/test_trade_plan.py -q
```

If `test_trade_plan.py` does not exist, run only `test_p21_calibration_inputs.py`.

Expected: PASS.

---

### Task 5: Add Conservative Regime Gate V1

**Files:**
- Create: `agent/research_v1/regime_gate.py`
- Test: `tests/agent/research_v1/test_p21_calibration_inputs.py`

- [ ] **Step 1: Add failing regime-gate tests**

Append:

```python
from agent.research_v1.regime_gate import evaluate_regime_gate


def test_regime_gate_missing_inputs_is_not_pass():
    result = evaluate_regime_gate({})
    assert result["regime_gate_status"] == "insufficient_definition"
    assert result["calibration_status"] == "prior_only"
    assert result["missing_features"]


def test_regime_gate_fails_extreme_volatility_features():
    result = evaluate_regime_gate({
        "vix_percentile": 0.99,
        "realized_vol_percentile": 0.96,
        "market_breadth_percentile": 0.50,
        "cross_sectional_dispersion_percentile": 0.50,
        "major_index_trend_state": "uptrend",
    })
    assert result["regime_gate_status"] == "fail"
    assert "vix_percentile" in result["failing_features"]
    assert "realized_vol_percentile" in result["failing_features"]


def test_regime_gate_warns_on_weak_breadth():
    result = evaluate_regime_gate({
        "vix_percentile": 0.50,
        "realized_vol_percentile": 0.50,
        "market_breadth_percentile": 0.10,
        "cross_sectional_dispersion_percentile": 0.50,
        "major_index_trend_state": "uptrend",
    })
    assert result["regime_gate_status"] == "warn"
    assert "market_breadth_percentile" in result["failing_features"]
```

- [ ] **Step 2: Run regime tests to verify failure**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p21_calibration_inputs.py -q
```

Expected: FAIL because `regime_gate.py` does not exist.

- [ ] **Step 3: Implement regime gate**

Create `agent/research_v1/regime_gate.py`:

```python
"""P21 conservative regime gate."""

from __future__ import annotations

from agent.research_v1.calibration_config import RegimeGateConfig

REQUIRED_REGIME_FEATURES = [
    "vix_percentile",
    "realized_vol_percentile",
    "market_breadth_percentile",
    "cross_sectional_dispersion_percentile",
    "major_index_trend_state",
]


def evaluate_regime_gate(features: dict, config: RegimeGateConfig | None = None) -> dict:
    active_config = config or RegimeGateConfig()
    missing_features = [name for name in REQUIRED_REGIME_FEATURES if name not in features]
    if missing_features:
        return {
            "regime_gate_status": active_config.missing_data_status,
            "failing_features": [],
            "missing_features": missing_features,
            "calibration_status": active_config.calibration_status,
            "config_version": active_config.config_version,
        }

    failing_features = []
    warn_features = []
    if float(features["vix_percentile"]) >= active_config.vix_fail_percentile:
        failing_features.append("vix_percentile")
    if float(features["realized_vol_percentile"]) >= active_config.realized_vol_fail_percentile:
        failing_features.append("realized_vol_percentile")
    if float(features["cross_sectional_dispersion_percentile"]) >= active_config.dispersion_fail_percentile:
        failing_features.append("cross_sectional_dispersion_percentile")
    if float(features["market_breadth_percentile"]) <= active_config.breadth_warn_percentile:
        warn_features.append("market_breadth_percentile")
    if str(features["major_index_trend_state"]).lower() in {"downtrend", "crash"}:
        warn_features.append("major_index_trend_state")

    if failing_features:
        status = "fail"
    elif warn_features:
        status = "warn"
    else:
        status = "pass"

    return {
        "regime_gate_status": status,
        "failing_features": failing_features + warn_features,
        "missing_features": [],
        "calibration_status": active_config.calibration_status,
        "config_version": active_config.config_version,
    }
```

- [ ] **Step 4: Run regime tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p21_calibration_inputs.py -q
```

Expected: PASS for regime tests.

---

### Task 6: Add P22 Return Selector and Stress Disclosure Tests

**Files:**
- Create: `agent/research_v1/p22_return_selector.py`
- Modify: `agent/research_v1/stress_testing.py` only if tests fail
- Test: `tests/agent/research_v1/test_p21_calibration_inputs.py`

- [ ] **Step 1: Add failing P22 return selector and stress tests**

Append:

```python
from agent.research_v1.p22_return_selector import select_forward_return
from agent.research_v1.stress_testing import evaluate_stress_scenarios


def test_p22_return_selector_defaults_to_net_return():
    observation = {
        "gross_return_pct": 0.10,
        "net_return_pct": 0.085,
        "return_value": 0.10,
    }
    assert select_forward_return(observation) == 0.085
    assert select_forward_return(observation, return_basis="gross") == 0.10


def test_p22_return_selector_rejects_unknown_basis():
    with pytest.raises(ValueError, match="return_basis"):
        select_forward_return({"net_return_pct": 0.01}, return_basis="raw")


def test_stress_testing_boss_output_hidden_without_resimulation():
    result = evaluate_stress_scenarios(
        {"2008_crisis": {"max_drawdown": -0.30}},
        resimulation_enabled=False,
        boss_facing_enabled=True,
    )
    assert result["resimulation_status"] == "disabled"
    assert result["boss_facing_enabled"] is False
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p21_calibration_inputs.py -q
```

Expected: FAIL because `p22_return_selector.py` does not exist.

- [ ] **Step 3: Implement return selector**

Create `agent/research_v1/p22_return_selector.py`:

```python
"""Return-basis selection for P22 diagnostics."""

from __future__ import annotations


def select_forward_return(observation: dict, return_basis: str = "net") -> float:
    if return_basis == "net":
        if "net_return_pct" in observation and observation["net_return_pct"] is not None:
            return float(observation["net_return_pct"])
        raise ValueError("net_return_pct is required for net return_basis")
    if return_basis == "gross":
        if "gross_return_pct" in observation and observation["gross_return_pct"] is not None:
            return float(observation["gross_return_pct"])
        if "return_value" in observation and observation["return_value"] is not None:
            return float(observation["return_value"])
        raise ValueError("gross_return_pct or return_value is required for gross return_basis")
    raise ValueError(f"unknown return_basis: {return_basis}")
```

- [ ] **Step 4: Run selector/stress tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p21_calibration_inputs.py -q
```

Expected: PASS.

---

### Task 7: Final Regression and Acceptance Checklist

**Files:**
- Test only unless failures require focused fixes.

- [ ] **Step 1: Run P21 focused tests**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1/test_p21_calibration_inputs.py -q
```

Expected: all P21 tests pass.

- [ ] **Step 2: Run P20/P21 regression bundle**

Run:

```bash
python3.11 -m pytest \
  tests/agent/research_v1/test_p20_factor_contracts.py \
  tests/agent/research_v1/test_p20_pnl_integrity.py \
  tests/agent/research_v1/test_backtest.py \
  tests/agent/research_v1/test_final_judge.py \
  tests/agent/research_v1/test_thesis_engine.py \
  tests/agent/research_v1/test_review_grade_monitor.py \
  tests/agent/research_v1/test_p4_valuation_risk.py \
  tests/agent/research_v1/test_p21_calibration_inputs.py \
  -q
```

Expected: all selected tests pass.

- [ ] **Step 3: Run full research_v1 test suite**

Run:

```bash
python3.11 -m pytest tests/agent/research_v1 -q
```

Expected: all tests pass. If unrelated legacy failures appear, record exact failing tests and prove the P20/P21 bundle still passes.

- [ ] **Step 4: Final handoff report**

Report:

```text
Changed files:
- agent/research_v1/calibration_config.py
- agent/research_v1/exit_planning.py
- agent/research_v1/final_judge.py
- agent/research_v1/grading.py
- agent/research_v1/valuation_models.py
- agent/research_v1/trade_plan.py
- agent/research_v1/regime_gate.py
- agent/research_v1/p22_return_selector.py
- tests/agent/research_v1/test_p21_calibration_inputs.py

Verification:
- P21 focused: <command> -> <result>
- P20/P21 regression bundle: <command> -> <result>
- Full research_v1 suite: <command> -> <result or exact known failures>

Acceptance checklist:
- config contracts versioned/prior-only: yes/no
- thesis thresholds config-driven: yes/no
- role weights injectable and zero-guarded: yes/no
- grading dynamic overrides validated: yes/no
- exit multiples prior-only and versioned: yes/no
- sector valuation metadata emitted: yes/no
- volatility-aware sizing fields emitted: yes/no
- regime gate missing data does not pass: yes/no
- P22 return selector defaults to net: yes/no
- stress output hidden without resimulation: yes/no
```

---

## Review Notes for the Implementer

The review model will reject the delivery if:

- any scoring threshold is newly hardcoded inside logic instead of config
- any `calibration_status="calibrated"` appears in P21 production defaults
- `select_forward_return()` defaults to gross returns
- `FinalJudge` cannot receive injected `RoleWeightConfig`
- invalid `dynamic_weights` can slip through `GradingAgent`
- missing regime inputs produce `pass`
- trade sizing lacks volatility/cap metadata
- sector valuation does not expose fallback metadata
