"""Risk metrics for Hermes P4."""


def calculate_sharpe_ratio(returns: list[float], risk_free_rate: float = 0.0) -> float:
    """Compute Sharpe ratio from a return series."""
    if not returns:
        return 0.0

    average_return = sum(returns) / len(returns)
    excess_return = average_return - risk_free_rate
    variance = sum((ret - average_return) ** 2 for ret in returns) / len(returns)
    volatility = variance ** 0.5
    if volatility == 0:
        return 0.0
    return excess_return / volatility


def calculate_max_drawdown(equity_curve: list[float]) -> float:
    """Compute the worst peak-to-trough drawdown from an equity curve."""
    if not equity_curve:
        return 0.0

    peak = equity_curve[0]
    max_drawdown = 0.0
    for value in equity_curve:
        peak = max(peak, value)
        drawdown = (value - peak) / peak if peak else 0.0
        max_drawdown = min(max_drawdown, drawdown)
    return max_drawdown


def calculate_historical_var(returns: list[float], confidence_level: float = 0.95) -> float:
    """Estimate historical VaR using the lower-tail percentile."""
    if not returns:
        return 0.0

    sorted_returns = sorted(returns)
    tail_index = max(0, int((1 - confidence_level) * len(sorted_returns)))
    return sorted_returns[tail_index]
