"""Minimal P1 backtest helpers for signal outcome calculation."""

from __future__ import annotations

from statistics import median
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent.research_v1.cost_model import CostModel


def _max_drawdown_until(points: list[dict], entry_price: float) -> float:
    """Peak-to-trough drawdown from entry price through the given points."""
    if not points or entry_price <= 0:
        return 0.0
    peak = float(entry_price)
    max_drawdown = 0.0
    for point in points:
        close = float(point["close"])
        peak = max(peak, close)
        drawdown = (close - peak) / peak if peak else 0.0
        max_drawdown = min(max_drawdown, drawdown)
    return max_drawdown


def compute_signal_outcomes(
    signal: dict,
    price_points: list[dict],
    horizons: tuple[int, ...] = (5, 20, 60),
    cost_model: "CostModel | None" = None,
) -> dict[int, dict]:
    """Compute forward outcomes from ordered price points.

    Args:
        signal: Dict with entry_price, and optionally adv_shares_20d and position_shares.
        price_points: Ordered list of dicts with 'day' and 'close' keys.
        horizons: Tuple of horizon day counts to evaluate.
        cost_model: Optional CostModel for net-return calculation.

    Returns:
        Dict mapping horizon -> outcome dict with schema_version, gross/net returns,
        drawdown, win flag, and cost fields.
    """
    entry_price = float(signal.get("entry_price") or 0.0)
    normalized = sorted(price_points, key=lambda item: item["day"])

    outcomes = {}
    for horizon in horizons:
        target_point = next((point for point in normalized if point["day"] >= horizon), None)
        if target_point is None:
            continue
        gap_handled = target_point["day"] != horizon
        exit_price = float(target_point["close"])
        gross_return_pct = (exit_price - entry_price) / entry_price if entry_price else 0.0

        # Cost payload
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

        # Peak-to-trough drawdown through path up to and including target
        path_points = [point for point in normalized if point["day"] <= target_point["day"]]
        max_drawdown_pct = _max_drawdown_until(path_points, entry_price)

        outcomes[horizon] = {
            "exit_price": exit_price,
            "return_pct": return_pct,
            "max_drawdown_pct": max_drawdown_pct,
            "win": return_pct > 0,
            "gap_handled": gap_handled,
            "schema_version": "p20.1",
            "gross_return_pct": cost_payload["gross_return_pct"],
            "net_return_pct": cost_payload["net_return_pct"],
            "transaction_cost_pct": cost_payload["transaction_cost_pct"],
            "cost_source": cost_payload["cost_source"],
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
