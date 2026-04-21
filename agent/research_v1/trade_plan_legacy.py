"""Trade plan generation from persisted Hermes signals."""


class TradePlanGenerator:
    """Generate an executable trade plan from a signal."""

    BUY_GRADES = {"S", "A"}

    def generate(self, signal: dict, grade: str) -> dict:
        """Build a deterministic trade plan from the structured signal."""
        entry_price = float(signal["entry_price"])
        confidence = float(signal.get("confidence", 0.5))
        priority_score = float(signal.get("priority_score", 50.0))
        band_pct = 0.01 if grade == "S" else 0.015

        low = round(entry_price * (1 - band_pct), 2)
        high = round(entry_price * (1 + band_pct), 2)
        size_multiplier = 1.0 if grade == "S" else 0.6 if grade == "A" else 0.25
        suggested_position_size = max(
            1,
            round((confidence * priority_score / 10.0) * size_multiplier),
        )

        action = "BUY" if grade in self.BUY_GRADES else "WATCH"
        invalidation_condition = (
            f"Exit if price closes below stop-loss {signal['stop_loss']} "
            f"or thesis expires after {signal['holding_horizon']}."
        )

        return {
            "action": action,
            "symbol": signal["symbol"],
            "entry_zone": {
                "low": low,
                "mid": entry_price,
                "high": high,
            },
            "stop_loss": signal["stop_loss"],
            "take_profit": signal["take_profit"],
            "holding_horizon": signal["holding_horizon"],
            "suggested_position_size": suggested_position_size,
            "invalidation_condition": invalidation_condition,
            "confidence": confidence,
        }
