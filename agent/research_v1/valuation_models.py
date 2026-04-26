"""Standalone valuation models for Hermes P4."""

from __future__ import annotations

from agent.research_v1.calibration_config import SectorBenchmarkConfig


def calculate_dcf_value(
    free_cash_flows: list[float],
    discount_rate: float,
    terminal_growth_rate: float,
) -> dict:
    """Discount projected cash flows and terminal value into enterprise value."""
    if not free_cash_flows or discount_rate <= terminal_growth_rate:
        return {
            "present_value_of_cash_flows": None,
            "terminal_value": None,
            "enterprise_value": None,
        }

    present_value = 0.0
    for period, cash_flow in enumerate(free_cash_flows, start=1):
        present_value += cash_flow / ((1 + discount_rate) ** period)

    terminal_cash_flow = free_cash_flows[-1] * (1 + terminal_growth_rate)
    terminal_value = terminal_cash_flow / (discount_rate - terminal_growth_rate)
    discounted_terminal = terminal_value / ((1 + discount_rate) ** len(free_cash_flows))
    enterprise_value = present_value + discounted_terminal

    return {
        "present_value_of_cash_flows": round(present_value, 4),
        "terminal_value": round(discounted_terminal, 4),
        "enterprise_value": round(enterprise_value, 4),
    }


def calculate_ddm_value(
    annual_dividend: float,
    cost_of_equity: float,
    dividend_growth_rate: float,
) -> dict:
    """Calculate Gordon Growth dividend discount model value."""
    if annual_dividend <= 0 or cost_of_equity <= dividend_growth_rate:
        return {
            "intrinsic_value": None,
        }

    next_dividend = annual_dividend * (1 + dividend_growth_rate)
    intrinsic_value = next_dividend / (cost_of_equity - dividend_growth_rate)
    return {
        "intrinsic_value": round(intrinsic_value, 4),
    }


def calculate_relative_valuation(
    market_data: dict,
    benchmark_multiples: dict,
) -> dict:
    """Estimate target price from peer multiples.

    Args:
        market_data: Dict with eps, book_value_per_share, sales_per_share keys.
        benchmark_multiples: Dict with pe/pb/ps multiples, or a 'sector' key to
            trigger sector-indexed benchmark lookup via SectorBenchmarkConfig.

    Returns:
        Dict with 'methods' (per-multiple target prices), 'target_price',
        and 'benchmark_metadata'.
    """
    benchmark_metadata = {
        "calibration_status": "prior_only",
        "config_version": "p21.0",
        "sector": None,
        "resolved_sector": None,
        "used_fallback": False,
    }

    multiples = dict(benchmark_multiples)

    # If benchmark_multiples contains sector but no direct multiples, look up via config
    if "sector" in benchmark_multiples and not any(k in benchmark_multiples for k in ("pe", "pb", "ps")):
        payload = SectorBenchmarkConfig().get(benchmark_multiples["sector"])
        multiples = payload["multiples"]
        benchmark_metadata = {k: v for k, v in payload.items() if k != "multiples"}

    methods = {}

    eps = market_data.get("eps")
    if eps is not None and multiples.get("pe") is not None:
        methods["pe"] = eps * multiples["pe"]

    book_value_per_share = market_data.get("book_value_per_share")
    if book_value_per_share is not None and multiples.get("pb") is not None:
        methods["pb"] = book_value_per_share * multiples["pb"]

    sales_per_share = market_data.get("sales_per_share")
    if sales_per_share is not None and multiples.get("ps") is not None:
        methods["ps"] = sales_per_share * multiples["ps"]

    if not methods:
        return {"methods": {}, "target_price": None, "benchmark_metadata": benchmark_metadata}

    target_price = sum(methods.values()) / len(methods)
    rounded_methods = {name: round(value, 4) for name, value in methods.items()}
    return {
        "methods": rounded_methods,
        "target_price": round(target_price, 4),
        "benchmark_metadata": benchmark_metadata,
    }


def get_sector_benchmark_multiples(sector: str | None) -> dict:
    """Return benchmark multiples for a given sector, delegating to SectorBenchmarkConfig."""
    return SectorBenchmarkConfig().get(sector)["multiples"]
