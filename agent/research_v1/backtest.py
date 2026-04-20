"""Minimal P1 backtest helpers for signal outcome calculation."""

from statistics import median


def compute_signal_outcomes(
    signal: dict,
    price_points: list[dict],
    horizons: tuple[int, ...] = (5, 20, 60),
) -> dict[int, dict]:
    """Compute forward outcomes from ordered price points."""
    entry_price = signal["entry_price"]
    normalized = sorted(price_points, key=lambda item: item["day"])
    drawdown_floor = min(point["close"] for point in normalized) if normalized else entry_price

    outcomes = {}
    for horizon in horizons:
        target_point = next((point for point in normalized if point["day"] >= horizon), None)
        if target_point is None:
            continue
        gap_handled = target_point["day"] != horizon
        exit_price = target_point["close"]
        return_pct = (exit_price - entry_price) / entry_price if entry_price else 0.0
        max_drawdown_pct = (drawdown_floor - entry_price) / entry_price if entry_price else 0.0
        outcomes[horizon] = {
            "exit_price": exit_price,
            "return_pct": return_pct,
            "max_drawdown_pct": max_drawdown_pct,
            "win": return_pct > 0,
            "gap_handled": gap_handled,
        }
    return outcomes


def summarize_signal_outcomes(outcomes: list[dict]) -> dict:
    """Summarize outcomes into win-rate and payoff stats."""
    if not outcomes:
        return {
            "win_rate": 0.0,
            "average_return": 0.0,
            "median_return": 0.0,
            "max_drawdown": 0.0,
            "profit_loss_ratio": 0.0,
        }

    returns = [item["return_pct"] for item in outcomes]
    wins = [value for value in returns if value > 0]
    losses = [abs(value) for value in returns if value < 0]
    profit_loss_ratio = (sum(wins) / len(wins)) / (sum(losses) / len(losses)) if wins and losses else 0.0

    return {
        "win_rate": sum(1 for item in outcomes if item["win"]) / len(outcomes),
        "average_return": sum(returns) / len(returns),
        "median_return": median(returns),
        "max_drawdown": min(item["max_drawdown_pct"] for item in outcomes),
        "profit_loss_ratio": round(profit_loss_ratio, 10),
    }


def summarize_signal_outcomes_by_grade(outcomes: list[dict]) -> dict[str, dict]:
    """Summarize outcomes by signal grade."""
    grouped: dict[str, list[dict]] = {}
    for item in outcomes:
        grade = item.get("grade", "UNKNOWN")
        grouped.setdefault(grade, []).append(item)

    summary = {}
    for grade, grade_outcomes in grouped.items():
        grade_summary = summarize_signal_outcomes(grade_outcomes)
        grade_summary["sample_size"] = len(grade_outcomes)
        summary[grade] = grade_summary
    return summary
