"""Tests for P4 valuation and risk engine."""

from unittest.mock import Mock

from agent.research_v1.analysts.fundamentals import FundamentalsAnalyst
from agent.research_v1.risk_metrics import (
    calculate_historical_var,
    calculate_max_drawdown,
    calculate_sharpe_ratio,
)
from agent.research_v1.valuation_models import (
    calculate_dcf_value,
    calculate_ddm_value,
    calculate_relative_valuation,
)


def test_calculate_dcf_value_returns_discounted_intrinsic_value():
    """Discount projected free cash flows into an intrinsic value estimate."""
    result = calculate_dcf_value(
        free_cash_flows=[100.0, 110.0, 120.0],
        discount_rate=0.10,
        terminal_growth_rate=0.03,
    )

    assert result["enterprise_value"] > 0
    assert result["terminal_value"] > result["present_value_of_cash_flows"]


def test_calculate_ddm_value_returns_zero_for_non_payers():
    """Return no DDM value when dividend stream is not positive."""
    result = calculate_ddm_value(
        annual_dividend=0.0,
        cost_of_equity=0.09,
        dividend_growth_rate=0.03,
    )

    assert result["intrinsic_value"] is None


def test_calculate_relative_valuation_averages_multiple_method_targets():
    """Blend PE/PB/PS targets into a relative valuation estimate."""
    result = calculate_relative_valuation(
        market_data={"eps": 5.0, "book_value_per_share": 20.0, "sales_per_share": 25.0},
        benchmark_multiples={"pe": 18.0, "pb": 3.0, "ps": 4.0},
    )

    assert result["target_price"] > 0
    assert set(result["methods"].keys()) == {"pe", "pb", "ps"}


def test_calculate_sharpe_ratio_uses_excess_returns():
    """Compute Sharpe ratio from a return series and risk-free rate."""
    sharpe = calculate_sharpe_ratio(
        returns=[0.03, 0.01, -0.02, 0.04, 0.02],
        risk_free_rate=0.01,
    )

    assert sharpe > 0


def test_calculate_max_drawdown_from_equity_curve():
    """Measure largest peak-to-trough drawdown from an equity curve."""
    drawdown = calculate_max_drawdown([100.0, 120.0, 115.0, 90.0, 95.0])

    assert round(drawdown, 4) == -0.25


def test_calculate_historical_var_returns_percentile_loss():
    """Estimate historical VaR at the requested confidence level."""
    var = calculate_historical_var(
        returns=[-0.05, -0.02, 0.01, 0.03, -0.08, 0.02, -0.01, 0.04],
        confidence_level=0.95,
    )

    assert var <= 0


def test_fundamentals_analyst_calculate_metrics_includes_model_outputs():
    """Attach valuation model outputs to the metrics bundle when inputs are present."""
    analyst = FundamentalsAnalyst(llm_client=Mock(), valuation_config={})
    metrics = analyst.calculate_metrics(
        market_data={
            "price": 50.0,
            "market_cap": 5_000_000,
            "eps": 4.0,
            "book_value_per_share": 18.0,
            "sales_per_share": 30.0,
        },
        income_data={
            "eps": 4.0,
            "net_income": 100_000,
            "revenue": {"total": 1_000_000},
            "ebit": 150_000,
        },
        balance_data={
            "shareholders_equity": 500_000,
            "total_debt": 200_000,
            "cash_and_equivalents": 50_000,
        },
        cashflow_data={
            "operating_cash_flow": 80_000,
            "free_cash_flow_projection": [100.0, 110.0, 120.0],
            "annual_dividend": 1.5,
        },
    )

    assert "dcf_value" in metrics
    assert "relative_value" in metrics
    assert metrics["dcf_value"] is not None
