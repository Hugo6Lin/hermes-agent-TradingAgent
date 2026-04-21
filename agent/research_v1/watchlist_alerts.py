"""
Phase 16: Watchlist & Alert Center.

Boss-centric monitored watchlists with business-day checks, weekend refresh,
and thesis-state-aware alerts.

Alert-only: produces WatchlistAlert signals but does not execute trading.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from agent.research_v1.contracts import WatchlistEntry, WatchlistAlert


# ---------------------------------------------------------------------------
# WatchlistAlertCenter
# ---------------------------------------------------------------------------

class WatchlistAlertCenter:
    """
    Phase 16 engine: manages watchlist lifecycle and generates alerts.

    Usage:
        center = WatchlistAlertCenter()
        entry = center.register("AAPL", status="Held", action_bias="Buy Stock")
        alert = center.build_alert(entry, "Weekly review — no changes")
    """

    def register(
        self,
        ticker: str,
        status: str,
        action_bias: str,
    ) -> WatchlistEntry:
        """
        Register a new ticker on the watchlist.

        Args:
            ticker: Stock ticker symbol
            status: One of Held / High Priority Watch / Research In Progress / Passive Watch
            action_bias: Current action recommendation (e.g. "Buy Stock", "Buy Call", "Watchlist")

        Returns:
            WatchlistEntry with default thesis_state=Stable, alert_level=None
        """
        return WatchlistEntry(
            ticker=ticker,
            status=status,
            thesis_state="Stable",
            alert_level="None",
            current_action_bias=action_bias,
        )

    def next_cadence(self, entry: WatchlistEntry) -> str:
        """
        Return the monitoring cadence for a watchlist entry.

        - Held / High Priority Watch / Research In Progress → "business_day"
        - Passive Watch → "weekly"
        """
        if entry.status in {"Held", "High Priority Watch", "Research In Progress"}:
            return "business_day"
        return "weekly"

    def update_thesis_state(
        self,
        entry: WatchlistEntry,
        new_state: str,
        reason: str,
    ) -> WatchlistEntry:
        """
        Update the thesis_state of a watchlist entry and adjust alert_level.

        State transitions:
            Stable       → Strengthening → Weakening → Broken
            Stable       → Strengthening → Weakening
            Any state    → Stable (alert clears)

        Alert levels:
            Broken       → Critical
            Weakening    → High
            Strengthening → Medium
            Stable       → None
        """
        if new_state not in {"Strengthening", "Stable", "Weakening", "Broken"}:
            raise ValueError(f"Invalid thesis_state: {new_state!r}")

        alert_map = {
            "Broken": "Critical",
            "Weakening": "High",
            "Strengthening": "Medium",
            "Stable": "None",
        }
        return WatchlistEntry(
            ticker=entry.ticker,
            status=entry.status,
            thesis_state=new_state,
            alert_level=alert_map[new_state],
            current_action_bias=entry.current_action_bias,
            last_user_interest_at=entry.last_user_interest_at,
            last_research_at=datetime.now(timezone.utc).isoformat(),
            next_review_date=entry.next_review_date,
        )

    def build_alert(
        self,
        entry: WatchlistEntry,
        message: str,
    ) -> WatchlistAlert:
        """
        Build an alert for a watchlist entry.

        Args:
            entry: The watchlist entry to alert on
            message: Human-readable alert message

        Returns:
            WatchlistAlert (alert_only — advisory, not execution)
        """
        return WatchlistAlert(
            ticker=entry.ticker,
            alert_level=entry.alert_level,
            message=message,
            thesis_state=entry.thesis_state,
            triggered_at=datetime.now(timezone.utc).isoformat(),
        )

    def summarize(
        self,
        entries: list[WatchlistEntry],
    ) -> dict[str, Any]:
        """
        Build a summary dict of all watchlist entries for the viewer.

        Returns:
            Dict with keys: held_count, watch_count, critical_alerts, high_alerts,
            medium_alerts, entries
        """
        held = [e for e in entries if e.status == "Held"]
        watch = [e for e in entries if e.status != "Held"]
        critical = [e for e in entries if e.alert_level == "Critical"]
        high = [e for e in entries if e.alert_level == "High"]
        medium = [e for e in entries if e.alert_level == "Medium"]

        return {
            "held_count": len(held),
            "watch_count": len(watch),
            "critical_alerts": [self.build_alert(e, "THESIS BROKEN — review immediately") for e in critical],
            "high_alerts": [self.build_alert(e, "Thesis weakening — monitor closely") for e in high],
            "medium_alerts": [self.build_alert(e, "Thesis strengthening") for e in medium],
            "entries": entries,
        }
