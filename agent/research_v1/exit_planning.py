"""Adaptive exit planning for P20 P&L integrity."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional

from agent.research_v1.calibration_config import ExitPlanConfig as CanonicalExitPlanConfig


@dataclass(frozen=True)
class ExitPlanConfig(CanonicalExitPlanConfig):
    """Re-exported from calibration_config for backward compatibility."""
    pass


@dataclass(frozen=True)
class ExitPlan:
    entry_price: float
    stop_loss: float
    take_profit: float
    atr_20: float
    realized_vol_20d: Optional[float]
    holding_horizon: str
    stop_multiple: float
    target_multiple: float
    calibration_status: str
    config_version: str

    def to_dict(self) -> dict:
        return asdict(self)


def _fallback_atr(entry_price: float, realized_vol_20d: Optional[float]) -> float:
    """Derive a fallback ATR from realized volatility when explicit ATR is unavailable."""
    if entry_price <= 0:
        return 0.0
    if realized_vol_20d and realized_vol_20d > 0:
        daily_vol = realized_vol_20d / (252 ** 0.5)
        return entry_price * min(max(daily_vol, 0.05), 1.0)
    return entry_price * 0.02


def build_exit_plan(
    entry_price: float,
    atr_20: Optional[float] = None,
    realized_vol_20d: Optional[float] = None,
    holding_horizon: str = "20d",
    config: Optional[ExitPlanConfig] = None,
) -> ExitPlan:
    """Build an ATR-adaptive exit plan.

    Args:
        entry_price: Entry price for the position.
        atr_20: 20-day Average True Range in price units.
        realized_vol_20d: 20-day realized volatility (annualized fraction).
        holding_horizon: Horizon hint (e.g. "5d", "20d").
        config: Exit plan configuration with stop/target multiples.

    Returns:
        ExitPlan with adaptive stop_loss and take_profit levels.
    """
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
        config_version=active_config.config_version,
    )
