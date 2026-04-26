"""Trade plan generation from canonical signals."""

from __future__ import annotations

from agent.research_v1.contracts import CanonicalSignal
from agent.research_v1.calibration_config import PositionSizingConfig


class TradePlanGenerator:
    """Generate an executable trade plan from a CanonicalSignal."""

    def __init__(self, sizing_config: PositionSizingConfig | None = None):
        """Initialize with optional volatility-aware sizing config."""
        self.sizing_config = sizing_config or PositionSizingConfig()

    def generate(self, signal: CanonicalSignal) -> dict:
        """
        Build a deterministic trade plan from a CanonicalSignal.

        Args:
            signal: CanonicalSignal from the final judge.

        Returns:
            Trade plan dict with entry zone, stop/take, position size,
            and volatility-aware sizing metadata.
        """
        entry_price = float(signal.entry_price) if signal.entry_price else 0.0
        confidence = float(signal.confidence)
        priority_score = float(signal.priority_score)
        stop_loss = float(signal.stop_loss) if signal.stop_loss else 0.0
        take_profit = float(signal.take_profit) if signal.take_profit else 0.0

        band_pct = 0.01 if signal.rating == "BUY" else 0.015
        low = round(entry_price * (1 - band_pct), 2)
        high = round(entry_price * (1 + band_pct), 2)
        size_multiplier = (
            1.0 if signal.rating == "BUY"
            else 0.6 if signal.rating == "HOLD"
            else 0.4  # SELL
        )
        # Legacy integer size (reference only; do not override cap-derived units)
        legacy_size = max(
            1,
            round((confidence * priority_score / 10.0) * size_multiplier),
        )

        # Volatility-aware sizing
        signal_volatility = getattr(signal, "signal_volatility", None)
        portfolio_equity = getattr(signal, "portfolio_equity", None)
        adv_shares_20d = getattr(signal, "adv_shares_20d", None)
        sizing_flags: list[str] = []

        if not signal_volatility or signal_volatility <= 0:
            signal_volatility = 0.30
            sizing_flags.append("missing_signal_volatility")
        if not portfolio_equity or portfolio_equity <= 0:
            portfolio_equity = entry_price * max(legacy_size, 1)
            sizing_flags.append("missing_portfolio_equity")

        # Compute raw weight from volatility targeting
        raw_weight = self.sizing_config.target_position_volatility / signal_volatility
        confidence_scaled_weight = raw_weight * max(0.0, min(1.0, confidence))
        single_name_cap_applied = confidence_scaled_weight > self.sizing_config.max_single_name_weight
        suggested_position_weight = min(confidence_scaled_weight, self.sizing_config.max_single_name_weight)

        # ADV cap
        adv_cap_applied = False
        if adv_shares_20d and entry_price > 0 and portfolio_equity > 0:
            max_shares_by_adv = adv_shares_20d * self.sizing_config.max_position_as_pct_adv
            shares_by_weight = (portfolio_equity * suggested_position_weight) / entry_price
            if shares_by_weight > max_shares_by_adv:
                adv_cap_applied = True
                suggested_position_weight = (max_shares_by_adv * entry_price) / portfolio_equity

        # Final size: cap-derived units, with legacy as minimum floor (not ceiling)
        vol_position_units = round((portfolio_equity * suggested_position_weight) / entry_price) if entry_price > 0 else 0
        if adv_cap_applied and vol_position_units < self.sizing_config.min_position_units:
            # ADV cap allows fewer shares than minimum trade unit — do not violate the cap
            sizing_flags.append("adv_cap_below_min_position")
            suggested_position_size = 0
        else:
            suggested_position_size = max(self.sizing_config.min_position_units, vol_position_units)

        action = signal.rating
        invalidation_condition = (
            f"Exit if price closes below stop-loss {stop_loss} "
            f"or thesis expires after {signal.holding_horizon}."
        )

        return {
            "action": action,
            "symbol": signal.ticker,
            "entry_zone": {
                "low": low,
                "mid": entry_price,
                "high": high,
            },
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "holding_horizon": signal.holding_horizon,
            "suggested_position_size": suggested_position_size,
            "suggested_position_weight": round(suggested_position_weight, 6),
            "target_position_volatility": self.sizing_config.target_position_volatility,
            "input_signal_volatility": signal_volatility,
            "adv_cap_applied": adv_cap_applied,
            "single_name_cap_applied": single_name_cap_applied,
            "sizing_flags": sizing_flags,
            "calibration_status": self.sizing_config.calibration_status,
            "invalidation_condition": invalidation_condition,
            "confidence": confidence,
        }
