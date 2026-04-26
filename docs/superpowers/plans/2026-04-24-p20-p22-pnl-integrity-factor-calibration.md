# P20-P22 P&L Integrity and Factor Calibration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the P20-P22 P&L integrity prerequisites that make Hermes factor calibration trustworthy: corrected drawdowns, cost-aware forward returns, adaptive exits, coverage-safe thesis gates, bounded LLM overlays, calibration-configured weights/thresholds, sector-aware valuation, and stronger risk metrics.

**Architecture:** Keep the canonical Hermes research pipeline intact. Add focused helper modules for cost modeling, exit planning, and calibration config, then wire them into existing backtest, grading, thesis, valuation, and risk paths. P20 must produce clean, schema-versioned statistics before P21/P22 diagnostics consume them.

**Tech Stack:** Python 3.11, dataclasses, pytest, existing `agent/research_v1` modules, SQLite persistence where already used.

---

## Source Spec

Primary spec:

- `docs/superpowers/specs/2026-04-24-hermes-p20-p22-factor-calibration-roadmap-spec.md`

The executor must treat that spec as authoritative. This plan operationalizes the P&L integrity portion of that spec.

## File Structure

### New files

- `agent/research_v1/cost_model.py`
  - Owns transaction cost estimation and gross-to-net return conversion.
- `agent/research_v1/exit_planning.py`
  - Owns ATR/realized-vol adaptive stop and target generation.
- `agent/research_v1/calibration_config.py`
  - Owns prior-only calibration inputs: role weights, thesis thresholds, exit multiples, sector benchmark multiples.
- `tests/agent/research_v1/test_p20_pnl_integrity.py`
  - New focused tests for drawdown, costs, adaptive exits, coverage, overlays, config guards, and net-return behavior.

### Existing files to modify

- `agent/research_v1/backtest.py`
  - Correct max drawdown and add optional cost-aware gross/net outcomes.
- `agent/research_v1/backtest_pipeline.py`
  - Persist/use extended outcome fields when database support exists; remain backward compatible if the DB has not been migrated yet.
- `agent/research_v1/data/database.py`
  - Add compatible columns for schema version and gross/net/cost fields in signal outcomes.
- `agent/research_v1/grading.py`
  - Replace hardcoded stops/targets, direct verdict scoring, and hidden static weights with helper-driven behavior.
- `agent/research_v1/thesis_engine.py`
  - Load thresholds from config and fix missing-field quality scoring.
- `agent/research_v1/final_judge.py`
  - Replace literal `ROLE_WEIGHTS` with validated config-derived weights while preserving the public symbol for tests/imports.
- `agent/research_v1/valuation_models.py`
  - Add minimal sector-indexed benchmark multiple support.
- `agent/research_v1/risk_metrics.py`
  - Add Sortino, Calmar, Expected Shortfall, and annualization helpers.
- `agent/research_v1/stress_testing.py`
  - Feature-flag cosmetic stress evaluation until real regime-window resimulation exists.

---

### Task 1: Correct Drawdown and Add Cost-Aware Backtest Outcomes

**Files:**
- Create: `agent/research_v1/cost_model.py`
- Modify: `agent/research_v1/backtest.py`
- Modify: `agent/research_v1/backtest_pipeline.py`
- Modify: `agent/research_v1/data/database.py`
- Test: `tests/agent/research_v1/test_p20_pnl_integrity.py`

- [ ] **Step 1: Write failing tests for drawdown and cost model**

Add this test file if it does not exist:

```python
from agent.research_v1.backtest import compute_signal_outcomes
from agent.research_v1.cost_model import CostModel


def test_backtest_uses_peak_to_trough_drawdown_for_winning_path():
    signal = {"entry_price": 100.0}
    price_points = [
        {"day": 0, "close": 100.0},
        {"day": 1, "close": 120.0},
        {"day": 2, "close": 108.0},
        {"day": 5, "close": 115.0},
    ]

    outcomes = compute_signal_outcomes(signal, price_points, horizons=(5,))

    assert round(outcomes[5]["max_drawdown_pct"], 4) == -0.10
    assert outcomes[5]["schema_version"] == "p20.1"


def test_cost_model_converts_gross_return_to_net_return_with_liquidity_flags():
    model = CostModel(
        commission_bps=1.0,
        half_spread_bps=2.0,
        impact_coefficient_bps=10.0,
        illiquidity_penalty_threshold=0.05,
        illiquidity_penalty_bps=25.0,
    )

    result = model.apply(
        gross_return_pct=0.05,
        adv_shares_20d=1_000_000,
        position_shares=100_000,
    )

    assert result["gross_return_pct"] == 0.05
    assert result["net_return_pct"] < result["gross_return_pct"]
    assert result["transaction_cost_pct"] > 0
    assert result["position_as_pct_of_adv"] == 0.10
    assert "position_exceeds_adv_threshold" in result["liquidity_flags"]


def test_backtest_outcomes_include_gross_and_net_returns_when_cost_model_enabled():
    signal = {
        "entry_price": 100.0,
        "position_shares": 50_000,
        "adv_shares_20d": 1_000_000,
    }
    price_points = [
        {"day": 0, "close": 100.0},
        {"day": 5, "close": 110.0},
    ]

    outcomes = compute_signal_outcomes(
        signal,
        price_points,
        horizons=(5,),
        cost_model=CostModel(commission_bps=1.0, half_spread_bps=2.0),
    )

    assert outcomes[5]["gross_return_pct"] == 0.10
    assert outcomes[5]["net_return_pct"] < 0.10
    assert outcomes[5]["return_pct"] == outcomes[5]["net_return_pct"]
    assert outcomes[5]["cost_source"] == "CostModel"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python3 -m pytest tests/agent/research_v1/test_p20_pnl_integrity.py -q
```

Expected:

- FAIL because `cost_model.py` does not exist and `compute_signal_outcomes()` does not accept `cost_model`.

- [ ] **Step 3: Implement `CostModel`**

Create `agent/research_v1/cost_model.py`:

```python
"""Transaction cost model for P20/P22 net-return evaluation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CostModel:
    """Estimate round-trip transaction costs for signal outcome analysis."""

    commission_bps: float = 0.5
    half_spread_bps: float = 1.0
    impact_coefficient_bps: float = 0.0
    illiquidity_penalty_threshold: float = 0.05
    illiquidity_penalty_bps: float = 0.0

    def estimate(
        self,
        adv_shares_20d: float | None = None,
        position_shares: float | None = None,
    ) -> dict:
        adv = float(adv_shares_20d or 0.0)
        position = float(position_shares or 0.0)
        position_as_pct_of_adv = position / adv if adv > 0 else 0.0
        impact_bps = self.impact_coefficient_bps * position_as_pct_of_adv
        liquidity_flags: list[str] = []
        illiquidity_penalty_bps = 0.0
        if adv <= 0 and position > 0:
            liquidity_flags.append("missing_adv")
        if position_as_pct_of_adv > self.illiquidity_penalty_threshold:
            liquidity_flags.append("position_exceeds_adv_threshold")
            illiquidity_penalty_bps = self.illiquidity_penalty_bps
        total_bps = (
            self.commission_bps
            + self.half_spread_bps
            + impact_bps
            + illiquidity_penalty_bps
        )
        return {
            "commission_bps": round(self.commission_bps, 6),
            "half_spread_bps": round(self.half_spread_bps, 6),
            "impact_bps": round(impact_bps, 6),
            "illiquidity_penalty_bps": round(illiquidity_penalty_bps, 6),
            "transaction_cost_pct": round(total_bps / 10_000.0, 10),
            "position_as_pct_of_adv": round(position_as_pct_of_adv, 10),
            "liquidity_flags": liquidity_flags,
        }

    def apply(
        self,
        gross_return_pct: float,
        adv_shares_20d: float | None = None,
        position_shares: float | None = None,
    ) -> dict:
        estimate = self.estimate(
            adv_shares_20d=adv_shares_20d,
            position_shares=position_shares,
        )
        net_return = gross_return_pct - estimate["transaction_cost_pct"]
        return {
            **estimate,
            "gross_return_pct": round(gross_return_pct, 10),
            "net_return_pct": round(net_return, 10),
        }
```

- [ ] **Step 4: Patch `compute_signal_outcomes()`**

Modify `agent/research_v1/backtest.py` so `compute_signal_outcomes()` accepts `cost_model=None`, computes peak-to-trough drawdown up to each horizon, and emits schema/gross/net fields:

```python
def _max_drawdown_until(points: list[dict]) -> float:
    if not points:
        return 0.0
    peak = float(points[0]["close"])
    max_drawdown = 0.0
    for point in points:
        close = float(point["close"])
        peak = max(peak, close)
        drawdown = (close - peak) / peak if peak else 0.0
        max_drawdown = min(max_drawdown, drawdown)
    return max_drawdown
```

Inside each horizon calculation:

```python
path_points = [point for point in normalized if point["day"] <= target_point["day"]]
gross_return_pct = (exit_price - entry_price) / entry_price if entry_price else 0.0
cost_payload = {
    "gross_return_pct": gross_return_pct,
    "net_return_pct": gross_return_pct,
    "transaction_cost_pct": 0.0,
    "cost_source": "none",
}
if cost_model is not None:
    applied = cost_model.apply(
        gross_return_pct=gross_return_pct,
        adv_shares_20d=signal.get("adv_shares_20d"),
        position_shares=signal.get("position_shares"),
    )
    cost_payload.update(applied)
    cost_payload["cost_source"] = cost_model.__class__.__name__
return_pct = cost_payload["net_return_pct"]
max_drawdown_pct = _max_drawdown_until(path_points)
```

Each outcome must include:

```python
"schema_version": "p20.1",
"gross_return_pct": cost_payload["gross_return_pct"],
"net_return_pct": cost_payload["net_return_pct"],
"transaction_cost_pct": cost_payload["transaction_cost_pct"],
"cost_source": cost_payload["cost_source"],
"return_pct": return_pct,
"max_drawdown_pct": max_drawdown_pct,
```

- [ ] **Step 5: Extend database persistence compatibly**

Modify the signal outcome table in `agent/research_v1/data/database.py` to include nullable/defaulted columns:

```sql
schema_version TEXT DEFAULT 'legacy_p1',
gross_return_pct REAL,
net_return_pct REAL,
transaction_cost_pct REAL DEFAULT 0.0,
cost_source TEXT DEFAULT 'none'
```

Update `save_signal_outcome()` to accept optional keyword arguments with defaults:

```python
schema_version: str = "p20.1",
gross_return_pct: float | None = None,
net_return_pct: float | None = None,
transaction_cost_pct: float = 0.0,
cost_source: str = "none",
```

If `gross_return_pct` or `net_return_pct` is `None`, default them to `return_pct` before insert.

- [ ] **Step 6: Patch `BacktestPipeline.backtest_signal()`**

When calling `save_signal_outcome()`, pass:

```python
schema_version=outcome.get("schema_version", "p20.1"),
gross_return_pct=outcome.get("gross_return_pct", outcome["return_pct"]),
net_return_pct=outcome.get("net_return_pct", outcome["return_pct"]),
transaction_cost_pct=outcome.get("transaction_cost_pct", 0.0),
cost_source=outcome.get("cost_source", "none"),
```

- [ ] **Step 7: Run focused tests**

Run:

```bash
python3 -m pytest tests/agent/research_v1/test_p20_pnl_integrity.py tests/agent/research_v1/test_backtest.py tests/agent/research_v1/test_database.py -q
```

Expected:

- PASS.

- [ ] **Step 8: Commit**

```bash
git add agent/research_v1/cost_model.py agent/research_v1/backtest.py agent/research_v1/backtest_pipeline.py agent/research_v1/data/database.py tests/agent/research_v1/test_p20_pnl_integrity.py
git commit -m "fix: add cost-aware corrected backtest outcomes"
```

If the workspace is not a git repository, record the changed files in the final handoff instead of committing.

---

### Task 2: Add ATR/Vol Adaptive Exit Planning and Remove Fixed Stop/Target Percentages

**Files:**
- Create: `agent/research_v1/exit_planning.py`
- Create/Modify: `agent/research_v1/calibration_config.py`
- Modify: `agent/research_v1/grading.py`
- Test: `tests/agent/research_v1/test_p20_pnl_integrity.py`

- [ ] **Step 1: Write failing exit-plan tests**

Append to `tests/agent/research_v1/test_p20_pnl_integrity.py`:

```python
from agent.research_v1.exit_planning import ExitPlanConfig, build_exit_plan


def test_exit_plan_uses_atr_and_marks_prior_only_calibration():
    low_vol = build_exit_plan(
        entry_price=100.0,
        atr_20=2.0,
        realized_vol_20d=0.20,
        holding_horizon="20d",
        config=ExitPlanConfig(stop_multiple=2.0, target_multiple=3.0),
    )
    high_vol = build_exit_plan(
        entry_price=100.0,
        atr_20=8.0,
        realized_vol_20d=0.20,
        holding_horizon="20d",
        config=ExitPlanConfig(stop_multiple=2.0, target_multiple=3.0),
    )

    assert low_vol.stop_loss == 96.0
    assert low_vol.take_profit == 106.0
    assert high_vol.stop_loss == 84.0
    assert high_vol.take_profit == 124.0
    assert low_vol.calibration_status == "prior_only"


def test_grading_signal_no_longer_uses_fixed_minus_7_plus_12_percent_exits():
    grader = GradingAgent(llm_client=None)
    decision = {
        "symbol": "AAPL",
        "market_data": {"price": 100.0},
        "technical_summary": {"atr_20": 5.0, "realized_vol_20d": 0.25},
    }

    result = grader._build_signal(decision, grade="A", composite_score=75.0)

    assert result["stop_loss"] != 93.0
    assert result["take_profit"] != 112.0
    assert result["exit_plan"]["calibration_status"] == "prior_only"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python3 -m pytest tests/agent/research_v1/test_p20_pnl_integrity.py::test_exit_plan_uses_atr_and_marks_prior_only_calibration tests/agent/research_v1/test_p20_pnl_integrity.py::test_grading_signal_no_longer_uses_fixed_minus_7_plus_12_percent_exits -q
```

Expected:

- FAIL because `exit_planning.py` does not exist and grading still uses fixed percentages.

- [ ] **Step 3: Create exit planning helper**

Create `agent/research_v1/exit_planning.py`:

```python
"""Adaptive exit planning for P20 P&L integrity."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ExitPlanConfig:
    stop_multiple: float = 2.0
    target_multiple: float = 3.0
    calibration_status: str = "prior_only"


@dataclass(frozen=True)
class ExitPlan:
    entry_price: float
    stop_loss: float
    take_profit: float
    atr_20: float
    realized_vol_20d: float | None
    holding_horizon: str
    stop_multiple: float
    target_multiple: float
    calibration_status: str

    def to_dict(self) -> dict:
        return asdict(self)


def _fallback_atr(entry_price: float, realized_vol_20d: float | None) -> float:
    if entry_price <= 0:
        return 0.0
    if realized_vol_20d and realized_vol_20d > 0:
        return entry_price * min(max(realized_vol_20d, 0.05), 1.0) / (252 ** 0.5)
    return entry_price * 0.02


def build_exit_plan(
    entry_price: float,
    atr_20: float | None = None,
    realized_vol_20d: float | None = None,
    holding_horizon: str = "20d",
    config: ExitPlanConfig | None = None,
) -> ExitPlan:
    active_config = config or ExitPlanConfig()
    entry = float(entry_price or 0.0)
    atr = float(atr_20 or 0.0)
    if atr <= 0:
        atr = _fallback_atr(entry, realized_vol_20d)
    stop_loss = max(0.0, entry - active_config.stop_multiple * atr)
    take_profit = entry + active_config.target_multiple * atr
    return ExitPlan(
        entry_price=round(entry, 4),
        stop_loss=round(stop_loss, 4),
        take_profit=round(take_profit, 4),
        atr_20=round(atr, 4),
        realized_vol_20d=realized_vol_20d,
        holding_horizon=holding_horizon,
        stop_multiple=active_config.stop_multiple,
        target_multiple=active_config.target_multiple,
        calibration_status=active_config.calibration_status,
    )
```

- [ ] **Step 4: Wire grading to exit planning**

In `agent/research_v1/grading.py`, import:

```python
from agent.research_v1.exit_planning import ExitPlanConfig, build_exit_plan
```

Inside `_build_signal()`, replace fixed stop/target lines with:

```python
technical_summary = research_decision.get("technical_summary", {})
exit_plan = build_exit_plan(
    entry_price=current_price,
    atr_20=technical_summary.get("atr_20") or technical_summary.get("atr"),
    realized_vol_20d=technical_summary.get("realized_vol_20d"),
    holding_horizon=holding_horizon,
    config=ExitPlanConfig(),
)
```

Return:

```python
"stop_loss": exit_plan.stop_loss,
"take_profit": exit_plan.take_profit,
"exit_plan": exit_plan.to_dict(),
```

- [ ] **Step 5: Run focused tests**

Run:

```bash
python3 -m pytest tests/agent/research_v1/test_p20_pnl_integrity.py tests/agent/research_v1/test_review_grade_monitor.py -q
```

Expected:

- PASS.

- [ ] **Step 6: Commit**

```bash
git add agent/research_v1/exit_planning.py agent/research_v1/grading.py tests/agent/research_v1/test_p20_pnl_integrity.py
git commit -m "feat: add adaptive prior-only exit planning"
```

If the workspace is not a git repository, record the changed files in the final handoff instead of committing.

---

### Task 3: Fix Thesis Coverage Handling and Configurable Thresholds

**Files:**
- Create/Modify: `agent/research_v1/calibration_config.py`
- Modify: `agent/research_v1/thesis_engine.py`
- Test: `tests/agent/research_v1/test_p20_pnl_integrity.py`
- Test: `tests/agent/research_v1/test_thesis_engine.py`

- [ ] **Step 1: Write failing tests for coverage and threshold config**

Append to `tests/agent/research_v1/test_p20_pnl_integrity.py`:

```python
from agent.research_v1.calibration_config import ThesisThresholdConfig
from agent.research_v1.thesis_engine import ThesisEngine


def test_thesis_quality_penalizes_missing_expected_fields():
    engine = ThesisEngine()

    sparse = engine._quality_score({"profitability": 0.80})
    covered = engine._quality_score({
        "profitability": 0.60,
        "balance_sheet": 0.60,
        "earnings_quality": 0.60,
        "capital_allocation": 0.60,
        "industry_position": 0.60,
    })

    assert sparse < covered


def test_thesis_classification_uses_threshold_config_not_literals():
    engine = ThesisEngine(thresholds=ThesisThresholdConfig(
        no_trade_quality_threshold=0.20,
        investable_quality_threshold=0.90,
        investable_valuation_threshold=0.50,
        investable_catalyst_threshold=0.90,
    ))

    result = engine.evaluate(
        ticker="AAPL",
        fundamentals={
            "profitability": 0.80,
            "balance_sheet": 0.80,
            "earnings_quality": 0.80,
            "capital_allocation": 0.80,
            "industry_position": 0.80,
        },
        valuation={"upside_pct": 0.30},
        catalysts={"clarity": 0.70},
    )

    assert result.classification == "Watchlist"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python3 -m pytest tests/agent/research_v1/test_p20_pnl_integrity.py::test_thesis_quality_penalizes_missing_expected_fields tests/agent/research_v1/test_p20_pnl_integrity.py::test_thesis_classification_uses_threshold_config_not_literals -q
```

Expected:

- FAIL because sparse quality currently averages present fields only and `ThesisEngine` has no threshold config.

- [ ] **Step 3: Add threshold config**

Create or extend `agent/research_v1/calibration_config.py`:

```python
"""Prior-only calibration configuration for P20-P22."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ThesisThresholdConfig:
    no_trade_quality_threshold: float = 0.35
    investable_quality_threshold: float = 0.65
    investable_valuation_threshold: float = 0.15
    investable_catalyst_threshold: float = 0.50
    calibration_status: str = "prior_only"


@dataclass(frozen=True)
class RoleWeight:
    weight: float
    disabled_with_reason: str | None = None


@dataclass(frozen=True)
class RoleWeightConfig:
    weights: dict[str, RoleWeight] = field(default_factory=lambda: {
        "fundamentals": RoleWeight(0.40),
        "technical": RoleWeight(0.25),
        "news": RoleWeight(0.15),
        "sentiment": RoleWeight(0.10),
        "industry": RoleWeight(0.05),
        "options": RoleWeight(0.05),
        "risk": RoleWeight(0.00, "risk informs warnings until P22 IC calibration"),
        "valuation": RoleWeight(0.00, "valuation handled by thesis layer until P22 IC calibration"),
    })

    def as_plain_weights(self) -> dict[str, float]:
        plain: dict[str, float] = {}
        for role, config in self.weights.items():
            if config.weight == 0.0 and not config.disabled_with_reason:
                raise ValueError(f"role {role} has zero weight without disabled_with_reason")
            plain[role] = config.weight
        return plain
```

- [ ] **Step 4: Patch `ThesisEngine`**

Modify `agent/research_v1/thesis_engine.py`:

```python
from agent.research_v1.calibration_config import ThesisThresholdConfig
```

Add constructor:

```python
    def __init__(self, thresholds: ThesisThresholdConfig | None = None):
        self.thresholds = thresholds or ThesisThresholdConfig()
```

Replace `_quality_score()` with expected-field-count scoring:

```python
    def _quality_score(self, fundamentals: dict) -> float:
        keys = ["profitability", "balance_sheet", "earnings_quality", "capital_allocation", "industry_position"]
        if not keys:
            return 0.0
        scores = [float(fundamentals.get(k, 0.0) or 0.0) for k in keys]
        return max(0.0, min(1.0, sum(scores) / len(keys)))
```

Replace `_classify()` threshold literals:

```python
        if quality < self.thresholds.no_trade_quality_threshold:
            return "No Trade"
        if (
            quality >= self.thresholds.investable_quality_threshold
            and valuation_score >= self.thresholds.investable_valuation_threshold
            and catalyst_score >= self.thresholds.investable_catalyst_threshold
        ):
            return "Investable"
        return "Watchlist"
```

- [ ] **Step 5: Run focused tests**

Run:

```bash
python3 -m pytest tests/agent/research_v1/test_p20_pnl_integrity.py tests/agent/research_v1/test_thesis_engine.py -q
```

Expected:

- PASS.

- [ ] **Step 6: Commit**

```bash
git add agent/research_v1/calibration_config.py agent/research_v1/thesis_engine.py tests/agent/research_v1/test_p20_pnl_integrity.py tests/agent/research_v1/test_thesis_engine.py
git commit -m "fix: make thesis gates coverage-safe and configurable"
```

If the workspace is not a git repository, record the changed files in the final handoff instead of committing.

---

### Task 4: Bound LLM Verdict Overlays and Guard Role Weights

**Files:**
- Modify: `agent/research_v1/calibration_config.py`
- Modify: `agent/research_v1/grading.py`
- Modify: `agent/research_v1/final_judge.py`
- Test: `tests/agent/research_v1/test_p20_pnl_integrity.py`
- Test: `tests/agent/research_v1/test_final_judge.py`
- Test: `tests/agent/research_v1/test_review_grade_monitor.py`

- [ ] **Step 1: Write failing tests for overlay bounds and zero-weight guards**

Append to `tests/agent/research_v1/test_p20_pnl_integrity.py`:

```python
from agent.research_v1.calibration_config import RoleWeight, RoleWeightConfig


def test_llm_verdict_overlay_is_bounded_and_does_not_set_base_score_directly():
    grader = GradingAgent(llm_client=None)

    score = grader._score_fundamentals({
        "base_score": 50,
        "verdict": "strong_buy",
        "confidence": 1.0,
    })

    assert score <= 65
    assert score != 95


def test_zero_role_weight_requires_disabled_reason():
    config = RoleWeightConfig(weights={"risk": RoleWeight(0.0)})

    try:
        config.as_plain_weights()
    except ValueError as exc:
        assert "disabled_with_reason" in str(exc)
    else:
        raise AssertionError("zero role weight without reason should fail")
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python3 -m pytest tests/agent/research_v1/test_p20_pnl_integrity.py::test_llm_verdict_overlay_is_bounded_and_does_not_set_base_score_directly tests/agent/research_v1/test_p20_pnl_integrity.py::test_zero_role_weight_requires_disabled_reason -q
```

Expected:

- FAIL because `_score_fundamentals()` still maps `strong_buy` to 95.

- [ ] **Step 3: Patch fundamental scoring overlay**

In `agent/research_v1/grading.py`, replace `_score_fundamentals()` internals with:

```python
        if not fundamentals_summary:
            return 50.0

        base_score = float(fundamentals_summary.get("base_score", 50.0))
        verdict = str(fundamentals_summary.get("verdict", "unknown")).lower()
        confidence = float(fundamentals_summary.get("confidence", 0.5))
        verdict_overlay = {
            "strong_buy": 15.0,
            "buy": 10.0,
            "hold": 0.0,
            "sell": -10.0,
            "strong_sell": -15.0,
            "unknown": 0.0,
        }.get(verdict, 0.0)
        confidence_scale = max(0.0, min(1.0, confidence))
        signed_overlay = verdict_overlay * confidence_scale
        return max(0.0, min(100.0, base_score + signed_overlay))
```

- [ ] **Step 4: Patch final judge role weights**

In `agent/research_v1/final_judge.py`, import `RoleWeightConfig` and set:

```python
from agent.research_v1.calibration_config import RoleWeightConfig

ROLE_WEIGHTS = RoleWeightConfig().as_plain_weights()
```

Keep the public `ROLE_WEIGHTS` symbol because existing tests import it.

- [ ] **Step 5: Run focused tests**

Run:

```bash
python3 -m pytest tests/agent/research_v1/test_p20_pnl_integrity.py tests/agent/research_v1/test_final_judge.py tests/agent/research_v1/test_review_grade_monitor.py -q
```

Expected:

- PASS.

- [ ] **Step 6: Commit**

```bash
git add agent/research_v1/calibration_config.py agent/research_v1/grading.py agent/research_v1/final_judge.py tests/agent/research_v1/test_p20_pnl_integrity.py
git commit -m "fix: bound llm overlays and guard disabled role weights"
```

If the workspace is not a git repository, record the changed files in the final handoff instead of committing.

---

### Task 5: Add Sector-Aware Valuation and Stronger Risk Metrics

**Files:**
- Modify: `agent/research_v1/calibration_config.py`
- Modify: `agent/research_v1/valuation_models.py`
- Modify: `agent/research_v1/risk_metrics.py`
- Test: `tests/agent/research_v1/test_p20_pnl_integrity.py`
- Test: `tests/agent/research_v1/test_p4_valuation_risk.py`

- [ ] **Step 1: Write failing valuation and risk tests**

Append to `tests/agent/research_v1/test_p20_pnl_integrity.py`:

```python
from agent.research_v1.risk_metrics import (
    calculate_calmar_ratio,
    calculate_expected_shortfall,
    calculate_sortino_ratio,
)
from agent.research_v1.valuation_models import get_sector_benchmark_multiples


def test_sector_benchmark_multiples_differ_by_sector():
    bank = get_sector_benchmark_multiples("financials")
    tech = get_sector_benchmark_multiples("technology")

    assert bank != tech
    assert bank["pb"] < tech["pb"]


def test_expected_shortfall_uses_average_tail_loss():
    result = calculate_expected_shortfall([-0.10, -0.05, 0.01, 0.02], confidence_level=0.75)

    assert result == -0.10


def test_sortino_and_calmar_are_defined_for_positive_series_with_drawdown():
    returns = [0.05, -0.02, 0.03, -0.01]
    equity_curve = [100.0, 105.0, 102.0, 108.0, 106.0]

    assert calculate_sortino_ratio(returns) > 0
    assert calculate_calmar_ratio(annual_return=0.12, equity_curve=equity_curve) > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python3 -m pytest tests/agent/research_v1/test_p20_pnl_integrity.py::test_sector_benchmark_multiples_differ_by_sector tests/agent/research_v1/test_p20_pnl_integrity.py::test_expected_shortfall_uses_average_tail_loss tests/agent/research_v1/test_p20_pnl_integrity.py::test_sortino_and_calmar_are_defined_for_positive_series_with_drawdown -q
```

Expected:

- FAIL because the new helpers do not exist.

- [ ] **Step 3: Add sector benchmark helper**

In `agent/research_v1/valuation_models.py`, add:

```python
SECTOR_BENCHMARK_MULTIPLES = {
    "technology": {"pe": 26.0, "pb": 8.0, "ps": 7.0},
    "financials": {"pe": 12.0, "pb": 1.4, "ps": 3.0},
    "healthcare": {"pe": 22.0, "pb": 4.5, "ps": 5.0},
    "consumer_discretionary": {"pe": 20.0, "pb": 4.0, "ps": 2.5},
    "industrials": {"pe": 18.0, "pb": 3.0, "ps": 2.0},
    "default": {"pe": 18.0, "pb": 3.0, "ps": 4.0},
}


def get_sector_benchmark_multiples(sector: str | None) -> dict:
    key = (sector or "default").strip().lower().replace(" ", "_")
    return dict(SECTOR_BENCHMARK_MULTIPLES.get(key, SECTOR_BENCHMARK_MULTIPLES["default"]))
```

Modify `calculate_relative_valuation()` so if `benchmark_multiples` contains `sector` but no explicit `pe/pb/ps`, it calls `get_sector_benchmark_multiples()`.

- [ ] **Step 4: Add risk metrics**

In `agent/research_v1/risk_metrics.py`, add:

```python
def calculate_sortino_ratio(returns: list[float], risk_free_rate: float = 0.0) -> float:
    if not returns:
        return 0.0
    average_return = sum(returns) / len(returns)
    downside = [min(0.0, ret - risk_free_rate) for ret in returns]
    downside_variance = sum(value * value for value in downside) / len(downside)
    downside_deviation = downside_variance ** 0.5
    if downside_deviation == 0:
        return 0.0
    return (average_return - risk_free_rate) / downside_deviation


def calculate_expected_shortfall(returns: list[float], confidence_level: float = 0.95) -> float:
    if not returns:
        return 0.0
    sorted_returns = sorted(returns)
    tail_count = max(1, int((1 - confidence_level) * len(sorted_returns)))
    tail = sorted_returns[:tail_count]
    return sum(tail) / len(tail)


def calculate_calmar_ratio(annual_return: float, equity_curve: list[float]) -> float:
    max_drawdown = abs(calculate_max_drawdown(equity_curve))
    if max_drawdown == 0:
        return 0.0
    return annual_return / max_drawdown


def annualize_return(period_return: float, periods_per_year: int) -> float:
    return ((1 + period_return) ** periods_per_year) - 1


def annualize_volatility(period_volatility: float, periods_per_year: int) -> float:
    return period_volatility * (periods_per_year ** 0.5)
```

- [ ] **Step 5: Run focused tests**

Run:

```bash
python3 -m pytest tests/agent/research_v1/test_p20_pnl_integrity.py tests/agent/research_v1/test_p4_valuation_risk.py -q
```

Expected:

- PASS.

- [ ] **Step 6: Commit**

```bash
git add agent/research_v1/valuation_models.py agent/research_v1/risk_metrics.py tests/agent/research_v1/test_p20_pnl_integrity.py
git commit -m "feat: add sector valuation and stronger risk metrics"
```

If the workspace is not a git repository, record the changed files in the final handoff instead of committing.

---

### Task 6: Feature-Flag Cosmetic Stress Testing

**Files:**
- Modify: `agent/research_v1/stress_testing.py`
- Test: `tests/agent/research_v1/test_p20_pnl_integrity.py`
- Test: `tests/agent/research_v1/test_p5_service_mode.py`

- [ ] **Step 1: Write failing feature-flag test**

Append to `tests/agent/research_v1/test_p20_pnl_integrity.py`:

```python
from agent.research_v1.stress_testing import evaluate_stress_scenarios


def test_stress_testing_discloses_disabled_resimulation_status_by_default():
    result = evaluate_stress_scenarios({
        "2008_crisis": {"max_drawdown": -0.30, "average_return": -0.10, "win_rate": 0.20}
    })

    assert result["resimulation_status"] == "disabled"
    assert result["boss_facing_enabled"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tests/agent/research_v1/test_p20_pnl_integrity.py::test_stress_testing_discloses_disabled_resimulation_status_by_default -q
```

Expected:

- FAIL because stress output has no disclosure fields.

- [ ] **Step 3: Patch stress output**

Modify `agent/research_v1/stress_testing.py` so `evaluate_stress_scenarios()` accepts:

```python
resimulation_enabled: bool = False,
boss_facing_enabled: bool = False,
```

Return payload must include:

```python
"resimulation_status": "enabled" if resimulation_enabled else "disabled",
"boss_facing_enabled": bool(boss_facing_enabled and resimulation_enabled),
```

The existing warning behavior should remain for compatibility, but boss-facing surfaces must be able to hide it when `boss_facing_enabled` is false.

- [ ] **Step 4: Run focused tests**

Run:

```bash
python3 -m pytest tests/agent/research_v1/test_p20_pnl_integrity.py tests/agent/research_v1/test_p5_service_mode.py -q
```

Expected:

- PASS.

- [ ] **Step 5: Commit**

```bash
git add agent/research_v1/stress_testing.py tests/agent/research_v1/test_p20_pnl_integrity.py
git commit -m "fix: disclose disabled stress resimulation status"
```

If the workspace is not a git repository, record the changed files in the final handoff instead of committing.

---

### Task 7: Final Integration Verification

**Files:**
- Modify only if required by failing tests: files already touched in Tasks 1-6.
- Test: all affected focused suites.

- [ ] **Step 1: Run P20/P21 focused test bundle**

Run:

```bash
python3 -m pytest \
  tests/agent/research_v1/test_p20_pnl_integrity.py \
  tests/agent/research_v1/test_backtest.py \
  tests/agent/research_v1/test_database.py \
  tests/agent/research_v1/test_thesis_engine.py \
  tests/agent/research_v1/test_final_judge.py \
  tests/agent/research_v1/test_review_grade_monitor.py \
  tests/agent/research_v1/test_p4_valuation_risk.py \
  tests/agent/research_v1/test_p5_service_mode.py \
  -q
```

Expected:

- PASS.

- [ ] **Step 2: Run image/report regression guard**

Run:

```bash
python3 -m pytest tests/agent/research_v1/test_image_report_pipeline.py tests/agent/research_v1/test_bullish_decision_integration.py -q
```

Expected:

- PASS. Report delivery must remain downstream and must not change research decisions.

- [ ] **Step 3: Run full research_v1 suite if time allows**

Run:

```bash
python3 -m pytest tests/agent/research_v1 -q
```

Expected:

- PASS, or clearly document unrelated pre-existing failures with exact failing test names.

- [ ] **Step 4: Final handoff summary**

The executor final message must include:

```text
Changed files:
- ...

Verification run:
- command: ...
- result: PASS/FAIL

P20-P22 acceptance notes:
- corrected drawdown: yes/no
- cost-aware net returns: yes/no
- adaptive exits prior-only: yes/no
- quality coverage fixed: yes/no
- LLM overlay bounded: yes/no
- role zero-weight guard: yes/no
- threshold config: yes/no
- sector valuation: yes/no
- stress output hidden/flagged: yes/no
```

- [ ] **Step 5: Commit final integration if git is available**

```bash
git status --short
git commit --allow-empty -m "chore: verify p20-p22 pnl integrity integration"
```

If the workspace is not a git repository, skip this step and include the non-git status in final handoff.
