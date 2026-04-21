"""Trade plan generation from canonical signals."""

from agent.research_v1.contracts import CanonicalSignal


class TradePlanGenerator:
    """Generate an executable trade plan from a CanonicalSignal."""

    def generate(self, signal: CanonicalSignal) -> dict:
        """
        Build a deterministic trade plan from a CanonicalSignal.

        Args:
            signal: CanonicalSignal from the final judge.

        Returns:
            Trade plan dict with entry zone, stop/take, position size.
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
        suggested_position_size = max(
            1,
            round((confidence * priority_score / 10.0) * size_multiplier),
        )

        action = signal.rating  # CanonicalSignal.rating is already BUY/SELL/HOLD
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
            "invalidation_condition": invalidation_condition,
            "confidence": confidence,
        }
