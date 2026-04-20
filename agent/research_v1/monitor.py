"""Monitor Agent - Real-time portfolio monitoring and alerting."""

from typing import Any, Optional

from agent.research_v1.llm_clients import BaseLLMClient


class MonitorAgent:
    """Real-time portfolio monitoring."""

    # Default alert thresholds
    DEFAULT_ATR_MULTIPLIER = 2.5
    DEFAULT_VOLUME_MULTIPLIER = 3.0
    # Backward-compatible aliases expected by the current test suite.
    ATR_MULTIPLIER = DEFAULT_ATR_MULTIPLIER
    VOLUME_MULTIPLIER = DEFAULT_VOLUME_MULTIPLIER

    def __init__(
        self,
        llm_client: BaseLLMClient,
        atr_multiplier: float = None,
        volume_multiplier: float = None
    ):
        """Initialize MonitorAgent.

        Args:
            llm_client: LLM client for generating monitoring analysis.
            atr_multiplier: ATR multiplier for price change alerts. Defaults to 2.5.
            volume_multiplier: Volume multiplier for volume alerts. Defaults to 3.0.
        """
        self.llm = llm_client
        self.atr_multiplier = atr_multiplier or self.DEFAULT_ATR_MULTIPLIER
        self.volume_multiplier = volume_multiplier or self.DEFAULT_VOLUME_MULTIPLIER

    def check_alerts(
        self,
        symbol: str,
        current_data: dict,
        position_data: dict = None
    ) -> dict:
        """Check for trigger conditions.

        Trigger types:
        - technical: price_change > 2.5*ATR, volume > 3*avg, RSI extreme
        - fundamental: earnings surprise, analyst rating change
        - news: macro event impact

        Alert levels: RED (severe), ORANGE (moderate), YELLOW (mild)

        Args:
            symbol: Stock ticker symbol.
            current_data: Current market data including price, volume, ATR, etc.
            position_data: Optional position data for context.

        Returns:
            dict with keys:
                - alerts: list of alert dicts
                - alert_level: "RED" | "ORANGE" | "YELLOW" | "none"
        """
        alerts = []

        # Check technical triggers
        technical_alerts = self._check_technical_triggers(current_data)
        alerts.extend(technical_alerts)

        # Check decision triggers tied to an open position.
        decision_alerts = self._check_position_triggers(current_data, position_data)
        alerts.extend(decision_alerts)

        # Check fundamental triggers
        fundamental_alerts = self._check_fundamental_triggers(current_data)
        alerts.extend(fundamental_alerts)

        # Check news/macro triggers
        news_alerts = self._check_news_triggers(current_data)
        alerts.extend(news_alerts)

        # Determine overall alert level
        alert_level = self._determine_alert_level(alerts)

        return {
            "symbol": symbol,
            "alerts": alerts,
            "alert_level": alert_level
        }

    def _check_position_triggers(self, current_data: dict, position_data: dict | None) -> list:
        """Check take-profit and stop-loss thresholds for an open position."""
        if not position_data or position_data.get("status") != "open":
            return []

        current_price = current_data.get("price")
        if current_price is None:
            return []

        alerts = []
        stop_loss = position_data.get("stop_loss")
        take_profit = position_data.get("take_profit")

        if take_profit is not None and current_price >= take_profit:
            alerts.append({
                "type": "decision",
                "severity": "ORANGE",
                "description": f"Price {current_price:.2f} reached take-profit {take_profit:.2f}",
                "metric": "take_profit",
            })

        if stop_loss is not None and current_price <= stop_loss:
            alerts.append({
                "type": "decision",
                "severity": "RED",
                "description": f"Price {current_price:.2f} broke stop-loss {stop_loss:.2f}",
                "metric": "stop_loss",
            })

        return alerts

    def _check_technical_triggers(self, current_data: dict) -> list:
        """Check technical triggers.

        Args:
            current_data: Current market data.

        Returns:
            List of technical alert dicts.
        """
        alerts = []

        # Price change vs ATR
        price_change = current_data.get("price_change_pct", 0)
        atr = current_data.get("atr")
        current_price = current_data.get("price")

        if atr is not None and current_price is not None:
            atr_pct = (atr / current_price) * 100 if current_price > 0 else 0
            price_threshold = atr_pct * self.atr_multiplier

            if abs(price_change) > price_threshold:
                alerts.append({
                    "type": "technical",
                    "severity": "RED" if abs(price_change) > price_threshold * 1.5 else "ORANGE",
                    "description": f"Price change {price_change:.2f}% exceeds {self.atr_multiplier}x ATR threshold",
                    "metric": "price_atr"
                })

        # Volume spike
        volume = current_data.get("volume", 0)
        avg_volume = current_data.get("avg_volume", 0)

        if avg_volume > 0 and volume > avg_volume * self.volume_multiplier:
            alerts.append({
                "type": "technical",
                "severity": "ORANGE",
                "description": f"Volume {volume/avg_volume:.1f}x average - unusual activity",
                "metric": "volume_spike"
            })

        # RSI extreme
        rsi = current_data.get("rsi")
        if rsi is not None:
            if rsi > 80:
                alerts.append({
                    "type": "technical",
                    "severity": "ORANGE",
                    "description": f"RSI {rsi:.1f} indicates overbought conditions",
                    "metric": "rsi_overbought"
                })
            elif rsi < 20:
                alerts.append({
                    "type": "technical",
                    "severity": "ORANGE",
                    "description": f"RSI {rsi:.1f} indicates oversold conditions",
                    "metric": "rsi_oversold"
                })

        # Price momentum
        price_momentum = current_data.get("price_momentum", 0)
        if price_momentum is not None:
            if price_momentum > 0.1:  # 10% upward momentum
                alerts.append({
                    "type": "technical",
                    "severity": "YELLOW",
                    "description": f"Strong upward momentum {price_momentum:.2%}",
                    "metric": "momentum"
                })
            elif price_momentum < -0.1:  # 10% downward momentum
                alerts.append({
                    "type": "technical",
                    "severity": "YELLOW",
                    "description": f"Strong downward momentum {price_momentum:.2%}",
                    "metric": "momentum"
                })

        return alerts

    def _check_fundamental_triggers(self, current_data: dict) -> list:
        """Check fundamental triggers.

        Args:
            current_data: Current market data.

        Returns:
            List of fundamental alert dicts.
        """
        alerts = []

        # Earnings surprise
        earnings_surprise = current_data.get("earnings_surprise_pct")
        if earnings_surprise is not None:
            if earnings_surprise > 10:
                alerts.append({
                    "type": "fundamental",
                    "severity": "RED",
                    "description": f"Positive earnings surprise {earnings_surprise:.1f}%",
                    "metric": "earnings_surprise"
                })
            elif earnings_surprise < -10:
                alerts.append({
                    "type": "fundamental",
                    "severity": "RED",
                    "description": f"Negative earnings surprise {earnings_surprise:.1f}%",
                    "metric": "earnings_surprise"
                })
            elif earnings_surprise > 5:
                alerts.append({
                    "type": "fundamental",
                    "severity": "ORANGE",
                    "description": f"Modest positive earnings surprise {earnings_surprise:.1f}%",
                    "metric": "earnings_surprise"
                })

        # Analyst rating change
        rating_change = current_data.get("analyst_rating_change")
        if rating_change is not None:
            if abs(rating_change) >= 2:
                alerts.append({
                    "type": "fundamental",
                    "severity": "ORANGE",
                    "description": f"Major analyst rating change: {rating_change:+d} notches",
                    "metric": "rating_change"
                })
            elif rating_change != 0:
                alerts.append({
                    "type": "fundamental",
                    "severity": "YELLOW",
                    "description": f"Analyst rating adjusted {rating_change:+d} notches",
                    "metric": "rating_change"
                })

        # Guidance revision
        guidance_revision = current_data.get("guidance_revision")
        if guidance_revision is not None:
            if guidance_revision == "raised":
                alerts.append({
                    "type": "fundamental",
                    "severity": "ORANGE",
                    "description": "Company raised forward guidance",
                    "metric": "guidance"
                })
            elif guidance_revision == "lowered":
                alerts.append({
                    "type": "fundamental",
                    "severity": "ORANGE",
                    "description": "Company lowered forward guidance",
                    "metric": "guidance"
                })

        return alerts

    def _check_news_triggers(self, current_data: dict) -> list:
        """Check news and macro event triggers.

        Args:
            current_data: Current market data.

        Returns:
            List of news/macro alert dicts.
        """
        alerts = []

        # Macro event impact
        macro_impact = current_data.get("macro_impact")
        if macro_impact is not None:
            if macro_impact == "high":
                alerts.append({
                    "type": "news",
                    "severity": "RED",
                    "description": "High impact macro event detected",
                    "metric": "macro_event"
                })
            elif macro_impact == "medium":
                alerts.append({
                    "type": "news",
                    "severity": "ORANGE",
                    "description": "Medium impact macro event detected",
                    "metric": "macro_event"
                })

        # Sector rotation signal
        sector_rotation = current_data.get("sector_rotation")
        if sector_rotation is not None:
            alerts.append({
                "type": "news",
                "severity": "YELLOW",
                "description": f"Sector rotation signal: {sector_rotation}",
                "metric": "sector_rotation"
            })

        # News sentiment shift
        news_sentiment = current_data.get("news_sentiment_change")
        if news_sentiment is not None:
            if news_sentiment == "turning_negative":
                alerts.append({
                    "type": "news",
                    "severity": "ORANGE",
                    "description": "News sentiment shifting negative",
                    "metric": "sentiment"
                })
            elif news_sentiment == "turning_positive":
                alerts.append({
                    "type": "news",
                    "severity": "YELLOW",
                    "description": "News sentiment shifting positive",
                    "metric": "sentiment"
                })

        return alerts

    def _determine_alert_level(self, alerts: list) -> str:
        """Determine overall alert level from individual alerts.

        Args:
            alerts: List of alert dicts.

        Returns:
            Alert level as string: "RED" | "ORANGE" | "YELLOW" | "none".
        """
        if not alerts:
            return "none"

        # Check for any RED alerts
        if any(alert.get("severity") == "RED" for alert in alerts):
            return "RED"

        # Check for any ORANGE alerts
        if any(alert.get("severity") == "ORANGE" for alert in alerts):
            return "ORANGE"

        # Check for any YELLOW alerts
        if any(alert.get("severity") == "YELLOW" for alert in alerts):
            return "YELLOW"

        return "none"
