"""Notification helpers for actionable Hermes events."""


class NotificationDispatcher:
    """Build user-facing notification payloads for alerts."""

    def build_alert_payload(self, symbol: str, alert_result: dict) -> dict:
        """Build a concise notification payload from an alert result."""
        alert_level = alert_result.get("alert_level", "none")
        alerts = alert_result.get("alerts", [])
        primary_alert = alerts[0] if alerts else {"metric": "signal", "description": "Action required"}
        message = f"{primary_alert['metric']}: {primary_alert['description']}"

        return {
            "title": f"{symbol} {alert_level} Alert",
            "message": message,
            "symbol": symbol,
            "alert_level": alert_level,
        }
