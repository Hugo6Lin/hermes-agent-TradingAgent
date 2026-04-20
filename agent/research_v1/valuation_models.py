"""Standalone valuation models for Hermes P4."""


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
    """Estimate target price from peer multiples."""
    methods = {}

    eps = market_data.get("eps")
    if eps is not None and benchmark_multiples.get("pe") is not None:
        methods["pe"] = eps * benchmark_multiples["pe"]

    book_value_per_share = market_data.get("book_value_per_share")
    if book_value_per_share is not None and benchmark_multiples.get("pb") is not None:
        methods["pb"] = book_value_per_share * benchmark_multiples["pb"]

    sales_per_share = market_data.get("sales_per_share")
    if sales_per_share is not None and benchmark_multiples.get("ps") is not None:
        methods["ps"] = sales_per_share * benchmark_multiples["ps"]

    if not methods:
        return {"methods": {}, "target_price": None}

    target_price = sum(methods.values()) / len(methods)
    rounded_methods = {name: round(value, 4) for name, value in methods.items()}
    return {
        "methods": rounded_methods,
        "target_price": round(target_price, 4),
    }
