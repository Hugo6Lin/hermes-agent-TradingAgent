"""
Phase 16: Watchlist & Alert Center tests.

Tests the WatchlistAlertCenter for watchlist lifecycle, monitoring cadence,
and thesis-state-aware alerts.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone
from agent.research_v1.contracts import WatchlistEntry, WatchlistAlert


# ---------------------------------------------------------------------------
# Contract validation tests
# ---------------------------------------------------------------------------

class TestWatchlistEntryContract:
    def test_requires_valid_status(self):
        """WatchlistEntry raises on invalid status."""
        with pytest.raises(ValueError, match="status"):
            WatchlistEntry(
                ticker="AAPL",
                status="Random",
                thesis_state="Stable",
                alert_level="None",
                current_action_bias="Buy Stock",
            )

    def test_requires_valid_thesis_state(self):
        """WatchlistEntry raises on invalid thesis_state."""
        with pytest.raises(ValueError, match="thesis_state"):
            WatchlistEntry(
                ticker="AAPL",
                status="Held",
                thesis_state="InvalidState",
                alert_level="None",
                current_action_bias="Buy Stock",
            )

    def test_accepts_held_state(self):
        """WatchlistEntry accepts Held status."""
        entry = WatchlistEntry(
            ticker="AAPL",
            status="Held",
            thesis_state="Stable",
            alert_level="None",
            current_action_bias="Buy Stock",
        )
        assert entry.status == "Held"

    def test_accepts_all_valid_statuses(self):
        """All valid statuses are accepted."""
        for status in ["Held", "High Priority Watch", "Research In Progress", "Passive Watch"]:
            entry = WatchlistEntry(
                ticker="AAPL",
                status=status,
                thesis_state="Stable",
                alert_level="None",
                current_action_bias="Buy Stock",
            )
            assert entry.status == status

    def test_accepts_all_valid_thesis_states(self):
        """All valid thesis_states are accepted."""
        for ts in ["Strengthening", "Stable", "Weakening", "Broken"]:
            entry = WatchlistEntry(
                ticker="AAPL",
                status="Held",
                thesis_state=ts,
                alert_level="None",
                current_action_bias="Buy Stock",
            )
            assert entry.thesis_state == ts


class TestWatchlistAlertContract:
    def test_requires_valid_alert_level(self):
        """WatchlistAlert raises on invalid alert_level."""
        with pytest.raises(ValueError, match="alert_level"):
            WatchlistAlert(
                ticker="AAPL",
                alert_level="MediumButNotReally",
                message="Test",
                thesis_state="Stable",
            )

    def test_accepts_all_valid_alert_levels(self):
        """All valid alert_levels are accepted."""
        for level in ["Critical", "High", "Medium", "Low", "None"]:
            alert = WatchlistAlert(
                ticker="AAPL",
                alert_level=level,
                message="Test alert",
                thesis_state="Stable",
            )
            assert alert.alert_level == level


# ---------------------------------------------------------------------------
# Persistence tests (run against real database)
# ---------------------------------------------------------------------------

class TestWatchlistPersistence:
    def test_watchlist_entry_round_trip(self, tmp_path):
        """WatchlistEntry can be saved and loaded from database."""
        from agent.research_v1.data.database import ResearchDatabase

        db = ResearchDatabase(str(tmp_path / "research.db"))
        db.initialize_research_core()
        db.initialize_watchlist()

        entry = WatchlistEntry(
            ticker="AAPL",
            status="Held",
            thesis_state="Stable",
            alert_level="None",
            current_action_bias="Buy Stock",
        )
        db.save_watchlist_entry(entry)
        rows = db.list_watchlist_entries()
        assert len(rows) == 1
        assert rows[0]["ticker"] == "AAPL"
        assert rows[0]["status"] == "Held"

    def test_update_thesis_state_persists(self, tmp_path):
        """Thesis state update persists to database."""
        from agent.research_v1.data.database import ResearchDatabase

        db = ResearchDatabase(str(tmp_path / "research.db"))
        db.initialize_research_core()
        db.initialize_watchlist()

        entry = WatchlistEntry(
            ticker="AMD",
            status="Held",
            thesis_state="Stable",
            alert_level="None",
            current_action_bias="Buy Stock",
        )
        db.save_watchlist_entry(entry)

        # Simulate update: change thesis_state and alert_level
        updated_entry = WatchlistEntry(
            ticker="AMD",
            status="Held",
            thesis_state="Broken",
            alert_level="Critical",
            current_action_bias="Buy Stock",
        )
        db.save_watchlist_entry(updated_entry)

        rows = db.list_watchlist_entries()
        broken = next(r for r in rows if r["ticker"] == "AMD")
        assert broken["thesis_state"] == "Broken"
        assert broken["alert_level"] == "Critical"


# ---------------------------------------------------------------------------
# WatchlistAlertCenter engine tests
# ---------------------------------------------------------------------------

from agent.research_v1.watchlist_alerts import WatchlistAlertCenter


class TestWatchlistCadence:
    def test_held_name_has_business_day_cadence(self):
        """Held status → business_day monitoring cadence."""
        center = WatchlistAlertCenter()
        entry = center.register("AAPL", status="Held", action_bias="Buy Stock")
        assert center.next_cadence(entry) == "business_day"

    def test_high_priority_watch_has_business_day_cadence(self):
        """High Priority Watch → business_day."""
        center = WatchlistAlertCenter()
        entry = center.register("AMD", status="High Priority Watch", action_bias="Buy Stock")
        assert center.next_cadence(entry) == "business_day"

    def test_research_in_progress_has_business_day_cadence(self):
        """Research In Progress → business_day."""
        center = WatchlistAlertCenter()
        entry = center.register("TSLA", status="Research In Progress", action_bias="Watchlist")
        assert center.next_cadence(entry) == "business_day"

    def test_passive_watch_defaults_to_weekly(self):
        """Passive Watch → weekly monitoring cadence."""
        center = WatchlistAlertCenter()
        entry = center.register("GLW", status="Passive Watch", action_bias="Watchlist")
        assert center.next_cadence(entry) == "weekly"

    def test_register_sets_thesis_state_stable(self):
        """New entry defaults to thesis_state=Stable."""
        center = WatchlistAlertCenter()
        entry = center.register("AAPL", status="Held", action_bias="Buy Stock")
        assert entry.thesis_state == "Stable"
        assert entry.alert_level == "None"

    def test_register_sets_initial_alert_level_none(self):
        """New entry starts with alert_level=None."""
        center = WatchlistAlertCenter()
        entry = center.register("AAPL", status="Passive Watch", action_bias="Watchlist")
        assert entry.alert_level == "None"


class TestThesisStateTransitions:
    def test_broken_thesis_emits_critical_alert(self):
        """Thesis broken → alert_level=Critical."""
        center = WatchlistAlertCenter()
        entry = center.register("AMD", status="Held", action_bias="Buy Stock")
        updated = center.update_thesis_state(
            entry, "Broken", "Guidance cut invalidates thesis"
        )
        assert updated.alert_level == "Critical"
        assert updated.thesis_state == "Broken"

    def test_weakening_thesis_emits_high_alert(self):
        """Thesis weakening → alert_level=High."""
        center = WatchlistAlertCenter()
        entry = center.register("AAPL", status="High Priority Watch", action_bias="Buy Stock")
        updated = center.update_thesis_state(entry, "Weakening", "Margins compressing")
        assert updated.alert_level == "High"
        assert updated.thesis_state == "Weakening"

    def test_strengthening_thesis_emits_medium_alert(self):
        """Thesis strengthening → alert_level=Medium."""
        center = WatchlistAlertCenter()
        entry = center.register("AAPL", status="Passive Watch", action_bias="Watchlist")
        updated = center.update_thesis_state(
            entry, "Strengthening", "New product cycle accelerating"
        )
        assert updated.alert_level == "Medium"
        assert updated.thesis_state == "Strengthening"

    def test_stable_thesis_returns_none_alert(self):
        """Stable thesis → alert_level=None."""
        center = WatchlistAlertCenter()
        entry = center.register("AAPL", status="Held", action_bias="Buy Stock")
        updated = center.update_thesis_state(entry, "Stable", "No material changes")
        assert updated.alert_level == "None"
        assert updated.thesis_state == "Stable"


class TestAlertGeneration:
    def test_builds_critical_alert_for_broken_thesis(self):
        """Broken thesis produces a Critical alert."""
        center = WatchlistAlertCenter()
        entry = center.register("AMD", status="Held", action_bias="Buy Stock")
        entry = center.update_thesis_state(entry, "Broken", "Guidance cut")
        alert = center.build_alert(entry, "THESIS BROKEN — review immediately")
        assert alert.alert_level == "Critical"
        assert "AMD" in alert.ticker

    def test_builds_low_alert_for_passive_watch(self):
        """Passive watch produces a low/none alert."""
        center = WatchlistAlertCenter()
        entry = center.register("GLW", status="Passive Watch", action_bias="Watchlist")
        alert = center.build_alert(entry, "Weekly review — no changes")
        assert alert.alert_level in {"None", "Low"}

    def test_summarize_groups_entries_correctly(self):
        """summarize() groups entries by status and alert level."""
        center = WatchlistAlertCenter()
        entries = [
            center.register("AAPL", status="Held", action_bias="Buy Stock"),
            center.register("AMD", status="Held", action_bias="Buy Stock"),
            center.register("GLW", status="Passive Watch", action_bias="Watchlist"),
        ]
        # Set one to broken
        entries[1] = center.update_thesis_state(entries[1], "Broken", "Moat eroded")
        summary = center.summarize(entries)
        assert summary["held_count"] == 2
        assert summary["watch_count"] == 1
        assert len(summary["critical_alerts"]) == 1
        assert summary["critical_alerts"][0].ticker == "AMD"
