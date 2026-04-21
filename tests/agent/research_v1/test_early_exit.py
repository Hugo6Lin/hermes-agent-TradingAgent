"""
Phase 15 Early Exit Engine tests.

Tests the EarlyExitEngine for alert-only exit zone recommendations
and EarlyExitPlan contract validation.
"""

from __future__ import annotations

import pytest
from agent.research_v1.contracts import EarlyExitPlan, ExitTrigger, ExitZone
from agent.research_v1.early_exit import EarlyExitEngine


# ---------------------------------------------------------------------------
# Contract validation tests
# ---------------------------------------------------------------------------

class TestEarlyExitPlanContract:
    def test_requires_valid_severity(self):
        """EarlyExitPlan raises on invalid severity."""
        with pytest.raises(ValueError, match="severity"):
            EarlyExitPlan(
                ticker="AAPL",
                primary_exit_trigger=ExitTrigger.TARGET_REACHED,
                severity="MediumButNotReally",  # invalid
                primary_reason="Test",
                first_trim=ExitZone("first_trim", "No Action", 0.30, "test"),
                main_profit=ExitZone("main_profit", "No Action", 0.60, "test"),
                full_exit=ExitZone("full_exit", "No Action", 0.80, "test"),
            )

    def test_accepts_all_valid_severities(self):
        """EarlyExitPlan accepts Critical/High/Medium/Low/None."""
        for sev in ["Critical", "High", "Medium", "Low", "None"]:
            plan = EarlyExitPlan(
                ticker="AAPL",
                primary_exit_trigger=ExitTrigger.TARGET_REACHED,
                severity=sev,
                primary_reason="Test",
                first_trim=ExitZone("first_trim", "No Action", 0.30, "test"),
                main_profit=ExitZone("main_profit", "No Action", 0.60, "test"),
                full_exit=ExitZone("full_exit", "No Action", 0.80, "test"),
            )
            assert plan.severity == sev

    def test_all_zones_present(self):
        """EarlyExitPlan always has three named zones."""
        engine = EarlyExitEngine()
        plan = engine.evaluate(
            instrument_action="Buy Call",
            thesis_state="Stable",
            thesis_state_reason="No changes",
            current_price=52.0,
            entry_price=50.0,
            target_price=60.0,
            option_return_pct=0.0,
        )
        assert plan.first_trim.zone_name == "first_trim"
        assert plan.main_profit.zone_name == "main_profit"
        assert plan.full_exit.zone_name == "full_exit"


# ---------------------------------------------------------------------------
# Thesis break tests
# ---------------------------------------------------------------------------

class TestThesisBreakExit:
    def test_broken_thesis_returns_critical_severity(self):
        """Thesis break → severity=Critical."""
        engine = EarlyExitEngine()
        plan = engine.evaluate(
            instrument_action="Buy Call",
            thesis_state="Broken",
            thesis_state_reason="Guidance cut, thesis invalidated",
            current_price=40.0,
            entry_price=50.0,
            target_price=60.0,
            option_return_pct=-0.30,
        )
        assert plan.severity == "Critical"
        assert plan.primary_exit_trigger == ExitTrigger.THESIS_BREAK
        assert "broken" in plan.primary_reason.lower()

    def test_broken_thesis_full_exit(self):
        """Thesis break → full_exit action is advisory 'Consider Closing Position'."""
        engine = EarlyExitEngine()
        plan = engine.evaluate(
            instrument_action="Sell Cash-Secured Put",
            thesis_state="Broken",
            thesis_state_reason="Competitive moat eroded",
            current_price=35.0,
            entry_price=50.0,
            target_price=60.0,
            option_return_pct=0.10,
        )
        assert "Consider" in plan.full_exit.action


# ---------------------------------------------------------------------------
# Structure break tests
# ---------------------------------------------------------------------------

class TestStructureBreakExit:
    def test_theta_burn_accelerating_triggers_structure_break(self):
        """Accelerating theta burn → High severity, structure_break trigger."""
        engine = EarlyExitEngine()
        plan = engine.evaluate(
            instrument_action="Buy Call",
            thesis_state="Stable",
            thesis_state_reason="No changes",
            current_price=52.0,
            entry_price=50.0,
            target_price=60.0,
            option_return_pct=0.10,
            theta_burn_accelerating=True,
            expiry_months=3,
            months_remaining=0.4,  # < 0.5 months — near expiry
        )
        assert plan.severity == "High"
        assert plan.primary_exit_trigger == ExitTrigger.STRUCTURE_BREAK

    def test_expiry_mismatch_triggers_structure_break(self):
        """Near-expiry without thesis realization → structure_break."""
        engine = EarlyExitEngine()
        plan = engine.evaluate(
            instrument_action="Bull Call Spread",
            thesis_state="Stable",
            thesis_state_reason="No material change",
            current_price=52.0,
            entry_price=50.0,
            target_price=60.0,
            option_return_pct=0.05,
            theta_burn_accelerating=True,  # triggered
        )
        assert "structure" in plan.primary_reason.lower()

    def test_iv_collapse_short_premium_profit_zone(self):
        """IV collapse on Sell CSP at +25% return → efficiency_breakdown."""
        engine = EarlyExitEngine()
        plan = engine.evaluate(
            instrument_action="Sell Cash-Secured Put",
            thesis_state="Stable",
            thesis_state_reason="No changes",
            current_price=52.0,
            entry_price=50.0,
            target_price=60.0,
            option_return_pct=0.28,  # good return
            iv_change=-0.12,  # IV collapsed
            expiry_months=6,
            months_remaining=3.0,
        )
        assert plan.primary_exit_trigger == ExitTrigger.EFFICIENCY_BREAKDOWN


# ---------------------------------------------------------------------------
# Return threshold tests
# ---------------------------------------------------------------------------

class TestReturnThresholdExit:
    def test_target_reached_60pct_returns_target_reached_trigger(self):
        """Underlying at target price with +60% return → TARGET_REACHED trigger."""
        engine = EarlyExitEngine()
        plan = engine.evaluate(
            instrument_action="Buy Call",
            thesis_state="Stable",
            thesis_state_reason="Bullish thesis intact",
            current_price=60.0,   # P2 fix: underlying hit thesis target
            entry_price=50.0,
            target_price=60.0,
            option_return_pct=0.65,
            iv_change=-0.02,
            expiry_months=6,
            months_remaining=3.0,
        )
        assert plan.primary_exit_trigger == ExitTrigger.TARGET_REACHED
        assert plan.severity == "Medium"

    def test_target_reached_main_profit_zone_has_trim_action(self):
        """Target reached plan → main_profit zone action is advisory 'Consider Trim Half'."""
        engine = EarlyExitEngine()
        plan = engine.evaluate(
            instrument_action="Buy Call",
            thesis_state="Stable",
            thesis_state_reason="Intact",
            current_price=60.0,   # P2 fix: underlying hit thesis target
            entry_price=50.0,
            target_price=60.0,
            option_return_pct=0.68,
            iv_change=0.0,
            expiry_months=6,
            months_remaining=3.0,
        )
        assert "Consider Trim Half" in plan.main_profit.action

    def test_first_trim_zone_at_30pct(self):
        """+30% return → first trim zone is 'Watch Trim'."""
        engine = EarlyExitEngine()
        plan = engine.evaluate(
            instrument_action="Buy Call",
            thesis_state="Stable",
            thesis_state_reason="No changes",
            current_price=55.0,
            entry_price=50.0,
            target_price=60.0,
            option_return_pct=0.35,
            iv_change=0.0,
            expiry_months=6,
            months_remaining=4.0,
        )
        assert plan.primary_exit_trigger == ExitTrigger.RETURN_THRESHOLD
        assert "Trim" in plan.first_trim.action or "Watch" in plan.first_trim.action


# ---------------------------------------------------------------------------
# Hold tests
# ---------------------------------------------------------------------------

class TestHoldZone:
    def test_hold_returns_none_severity(self):
        """Below all thresholds → severity=None, 'No Action' across zones."""
        engine = EarlyExitEngine()
        plan = engine.evaluate(
            instrument_action="Buy Call",
            thesis_state="Stable",
            thesis_state_reason="No material changes",
            current_price=52.0,
            entry_price=50.0,
            target_price=60.0,
            option_return_pct=0.10,
            iv_change=0.0,
            theta_burn_accelerating=False,
            expiry_months=6,
            months_remaining=4.0,
        )
        assert plan.severity == "None"
        assert plan.primary_exit_trigger == ExitTrigger.PRICE_RISK_DISCIPLINE
        assert plan.first_trim.action == "No Action"

    def test_hold_iv_elevated_included_in_reason(self):
        """Elevated IV is noted in primary reason even when holding."""
        engine = EarlyExitEngine()
        plan = engine.evaluate(
            instrument_action="Buy Call",
            thesis_state="Stable",
            thesis_state_reason="No changes",
            current_price=52.0,
            entry_price=50.0,
            target_price=60.0,
            option_return_pct=0.10,
            iv_change=0.0,
            expiry_months=6,
            months_remaining=4.0,
            iv_percentile=0.75,
        )
        assert "IV" in plan.primary_reason or "iv" in plan.primary_reason


# ---------------------------------------------------------------------------
# Instrument routing tests
# ---------------------------------------------------------------------------

class TestInstrumentRouting:
    def test_buy_call_gets_call_plan(self):
        """Buy Call routes to call-specific exit logic."""
        engine = EarlyExitEngine()
        plan = engine.evaluate(
            instrument_action="Buy Call",
            thesis_state="Broken",
            thesis_state_reason="Invalidated",
            current_price=40.0,
            entry_price=50.0,
            target_price=60.0,
            option_return_pct=-0.40,
        )
        assert plan.primary_exit_trigger == ExitTrigger.THESIS_BREAK

    def test_bull_call_spread_gets_spread_plan(self):
        """Bull Call Spread routes to spread exit logic."""
        engine = EarlyExitEngine()
        plan = engine.evaluate(
            instrument_action="Bull Call Spread",
            thesis_state="Stable",
            thesis_state_reason="No changes",
            current_price=52.0,
            entry_price=50.0,
            target_price=60.0,
            option_return_pct=0.70,
            theta_burn_accelerating=True,
        )
        assert plan.primary_exit_trigger == ExitTrigger.STRUCTURE_BREAK

    def test_sell_csp_gets_put_plan(self):
        """Sell CSP routes to put/short-premium logic."""
        engine = EarlyExitEngine()
        plan = engine.evaluate(
            instrument_action="Sell Cash-Secured Put",
            thesis_state="Broken",
            thesis_state_reason="Invalidated",
            current_price=35.0,
            entry_price=50.0,
            target_price=45.0,
            option_return_pct=0.15,
        )
        assert plan.primary_exit_trigger == ExitTrigger.THESIS_BREAK

    def test_covered_call_gets_call_plan(self):
        """Covered Call routes to short-call logic (Weakening ≠ Broken thesis break)."""
        engine = EarlyExitEngine()
        plan = engine.evaluate(
            instrument_action="Covered Call",
            thesis_state="Weakening",
            thesis_state_reason="Thesis deteriorating",
            current_price=48.0,
            entry_price=50.0,
            target_price=55.0,
            option_return_pct=0.20,
        )
        # Weakening (not Broken) → falls to hold / price discipline
        assert plan.primary_exit_trigger == ExitTrigger.PRICE_RISK_DISCIPLINE
        assert "Weakening" in plan.primary_reason or "deteriorating" in plan.primary_reason


# ---------------------------------------------------------------------------
# Alert-only enforcement
# ---------------------------------------------------------------------------

class TestAlertOnlyEnforcement:
    def test_no_auto_execute_action_in_any_plan(self):
        """No zone recommends auto-execution — all are Consider/Take/No actions."""
        engine = EarlyExitEngine()
        auto_actions = {"Market Sell", "Buy to Close", "Sell Now", "Execute"}
        for pct in [0.0, 0.10, 0.30, 0.60, 0.80]:
            plan = engine.evaluate(
                instrument_action="Buy Call",
                thesis_state="Stable",
                thesis_state_reason="OK",
                current_price=52.0,
                entry_price=50.0,
                target_price=60.0,
                option_return_pct=pct,
            )
            for zone in [plan.first_trim, plan.main_profit, plan.full_exit]:
                assert zone.action not in auto_actions, f"Auto-action {zone.action!r} leaked into alert-only system"
