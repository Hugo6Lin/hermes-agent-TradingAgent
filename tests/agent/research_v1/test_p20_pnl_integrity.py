"""P20 P&L integrity tests for drawdown, cost model, adaptive exits, coverage, overlays, and config."""

from agent.research_v1.backtest import compute_signal_outcomes
from agent.research_v1.cost_model import CostModel
from agent.research_v1.exit_planning import ExitPlanConfig, build_exit_plan
from agent.research_v1.grading import GradingAgent
from agent.research_v1.calibration_config import ThesisThresholdConfig, RoleWeight, RoleWeightConfig
from agent.research_v1.thesis_engine import ThesisEngine
from agent.research_v1.risk_metrics import (
    calculate_calmar_ratio,
    calculate_expected_shortfall,
    calculate_sortino_ratio,
)
from agent.research_v1.valuation_models import get_sector_benchmark_multiples, calculate_relative_valuation
from agent.research_v1.stress_testing import evaluate_stress_scenarios
from agent.research_v1.backtest_pipeline import BacktestPipeline
from agent.research_v1.calibration_config import GradingWeightConfig


def test_backtest_uses_peak_to_trough_drawdown_for_winning_path():
    """Peak-to-trough drawdown from entry, not floor-from-entire-series."""
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


# ---------------------------------------------------------------------------
# Task 2: Adaptive exit planning
# ---------------------------------------------------------------------------

def test_exit_plan_uses_atr_and_marks_prior_only_calibration():
    """Exit plan adapts stop/target based on ATR and marks calibration status."""
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
    """Grading signal must use ATR-based exits, not fixed -7%/+12% magic constants."""
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


# ---------------------------------------------------------------------------
# Task 3: Thesis coverage and configurable thresholds
# ---------------------------------------------------------------------------

def test_thesis_quality_penalizes_missing_expected_fields():
    """Quality scoring must normalize by expected field count, not just present fields."""
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
    """Thesis classification must use ThesisThresholdConfig, not hardcoded literals."""
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


# ---------------------------------------------------------------------------
# Task 4: Bounded LLM overlays and zero-weight role guards
# ---------------------------------------------------------------------------

def test_llm_verdict_overlay_is_bounded_and_does_not_set_base_score_directly():
    """LLM verdict overlay must be bounded and cannot override base score arbitrarily."""
    grader = GradingAgent(llm_client=None)

    score = grader._score_fundamentals({
        "base_score": 50,
        "verdict": "strong_buy",
        "confidence": 1.0,
    })

    assert score <= 65
    assert score != 95


def test_zero_role_weight_requires_disabled_reason():
    """Zero-weight roles must have disabled_with_reason set."""
    config = RoleWeightConfig(weights={"risk": RoleWeight(0.0)})

    try:
        config.as_plain_weights()
    except ValueError as exc:
        assert "disabled_with_reason" in str(exc)
    else:
        raise AssertionError("zero role weight without reason should fail")


# ---------------------------------------------------------------------------
# Task 5: Sector-aware valuation and stronger risk metrics
# ---------------------------------------------------------------------------

def test_sector_benchmark_multiples_differ_by_sector():
    """Sector benchmark multiples must differ by sector (financials vs tech)."""
    bank = get_sector_benchmark_multiples("financials")
    tech = get_sector_benchmark_multiples("technology")

    assert bank != tech
    assert bank["pb"] < tech["pb"]


def test_expected_shortfall_uses_average_tail_loss():
    """Expected Shortfall must compute average loss in the tail, not just VaR."""
    result = calculate_expected_shortfall([-0.10, -0.05, 0.01, 0.02], confidence_level=0.75)

    assert result == -0.10


def test_sortino_and_calmar_are_defined_for_positive_series_with_drawdown():
    """Sortino and Calmar ratios must be defined for return series with drawdowns."""
    returns = [0.05, -0.02, 0.03, -0.01]
    equity_curve = [100.0, 105.0, 102.0, 108.0, 106.0]

    assert calculate_sortino_ratio(returns) > 0
    assert calculate_calmar_ratio(annual_return=0.12, equity_curve=equity_curve) > 0


# ---------------------------------------------------------------------------
# Task 6: Feature-flag cosmetic stress testing disclosure
# ---------------------------------------------------------------------------

def test_stress_testing_discloses_disabled_resimulation_status_by_default():
    """Stress testing output must disclose resimulation_status and boss_facing_enabled."""
    result = evaluate_stress_scenarios({
        "2008_crisis": {"max_drawdown": -0.30, "average_return": -0.10, "win_rate": 0.20}
    })

    assert result["resimulation_status"] == "disabled"
    assert result["boss_facing_enabled"] is False


# ---------------------------------------------------------------------------
# Reviewer fixes: targeted接入路径验证
# ---------------------------------------------------------------------------

def test_calculate_relative_valuation_consumes_sector_benchmark():
    """sector-only benchmark_multiples must produce non-null target_price."""
    result = calculate_relative_valuation(
        market_data={"eps": 5.0, "book_value_per_share": 20.0, "sales_per_share": 15.0},
        benchmark_multiples={"sector": "financials"},
    )

    assert result["target_price"] is not None
    assert len(result["methods"]) > 0


def test_grading_weight_config_validates_sum():
    """GradingWeightConfig must reject weights that don't sum to ~1.0."""
    import pytest
    with pytest.raises(ValueError, match="sum to 1.0"):
        GradingWeightConfig(fundamental=0.5, technical=0.5, macro=0.5)


def test_grading_agent_accepts_grading_weight_config():
    """GradingAgent must accept GradingWeightConfig and use it for weighting."""
    import pytest
    config = GradingWeightConfig(fundamental=0.60, technical=0.30, macro=0.10)
    grader = GradingAgent(llm_client=None, grading_weights=config)

    assert grader.grading_weights.fundamental == 0.60
    assert grader.grading_weights.technical == 0.30
    assert grader.grading_weights.macro == 0.10
    assert grader.fundamental_weight == pytest.approx(0.60)
    assert grader.technical_weight == pytest.approx(0.30)
    assert grader.macro_weight == pytest.approx(0.10)
