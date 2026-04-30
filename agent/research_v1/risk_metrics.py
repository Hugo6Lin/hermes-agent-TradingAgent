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


def calculate_sortino_ratio(returns: list[float], risk_free_rate: float = 0.0) -> float:
    """Compute Sortino ratio focusing on downside deviation."""
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
    """Compute Expected Shortfall (CVaR) as average loss in the tail beyond VaR."""
    if not returns:
        return 0.0
    sorted_returns = sorted(returns)
    tail_count = max(1, int((1 - confidence_level) * len(sorted_returns)))
    tail = sorted_returns[:tail_count]
    return sum(tail) / len(tail)


def calculate_calmar_ratio(annual_return: float, equity_curve: list[float]) -> float:
    """Compute Calmar ratio as annual return divided by max drawdown."""
    max_drawdown_val = abs(calculate_max_drawdown(equity_curve))
    if max_drawdown_val == 0:
        return 0.0
    return annual_return / max_drawdown_val


def annualize_return(period_return: float, periods_per_year: int) -> float:
    """Annualize a return over a given number of periods per year."""
    return ((1 + period_return) ** periods_per_year) - 1


def annualize_volatility(period_volatility: float, periods_per_year: int) -> float:
    """Annualize a volatility measure."""
    return period_volatility * (periods_per_year ** 0.5)
