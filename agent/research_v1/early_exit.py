"""
Phase 15: Early Exit Engine.

Evaluates an options position for early-exit opportunities based on:
- thesis state (Strengthening / Stable / Weakening / Broken)
- option return vs thresholds
- structure efficiency (theta, IV, time-window fit)

Alert-only: produces ExitAlert signals but does not execute.

Three-zone model from spec:
  - first_trim_zone:  first opportunity to lock in partial gains
  - main_profit_zone: primary profit-taking window
  - full_exit_zone:   full position exit
"""

from __future__ import annotations

from agent.research_v1.contracts import (
    EarlyExitPlan,
    ExitZone,
    ExitTrigger,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _zone(
    name: str,
    action: str,
    target_return: float | None,
    trigger: str,
) -> ExitZone:
    return ExitZone(
        zone_name=name,
        action=action,
        target_return_pct=target_return,
        trigger_condition=trigger,
    )


# ---------------------------------------------------------------------------
# EarlyExitEngine
# ---------------------------------------------------------------------------

class EarlyExitEngine:
    """
    Phase 15 engine: evaluates an options position and recommends exit zones.

    Usage:
        engine = EarlyExitEngine()
        plan = engine.evaluate(
            instrument_action="Buy Call",
            thesis_state="Stable",         # Strengthening/Stable/Weakening/Broken
            thesis_state_reason="No material changes",
            current_price=52.0,
            entry_price=50.0,
            target_price=60.0,
            option_return_pct=0.40,       # current P&L as fraction (0.40 = +40%)
            iv_change=0.02,               # IV change since entry (positive = expanded)
            theta_burn_accelerating=False,
            expiry_months=3,
            months_remaining=1.5,
            iv_percentile=0.60,
        )
    """

    def evaluate(
        self,
        instrument_action: str,
        thesis_state: str,
        thesis_state_reason: str,
        current_price: float,
        entry_price: float,
        target_price: float,
        option_return_pct: float,
        iv_change: float = 0.0,
        theta_burn_accelerating: bool = False,
        expiry_months: int = 6,
        months_remaining: float = 3.0,
        iv_percentile: float = 0.50,
    ) -> EarlyExitPlan:
        """
        Evaluate position and return an EarlyExitPlan with three zones.

        Args:
            instrument_action: Phase 14 instrument (Buy Call, Bull Call Spread, etc.)
            thesis_state: Strengthening | Stable | Weakening | Broken
            thesis_state_reason: Human-readable reason for thesis state
            current_price: Current underlying price
            entry_price: Price at which position was entered
            target_price: Original thesis target price
            option_return_pct: Current option position return (e.g. 0.40 = +40%)
            iv_change: Change in IV since entry (positive = IV expanded)
            theta_burn_accelerating: Whether theta burn is increasing faster than expected
            expiry_months: Original option expiry in months
            months_remaining: Months until expiry
            iv_percentile: Current IV percentile
        """
        if instrument_action not in {
            "Buy Call", "Buy Put", "Bull Call Spread",
            "Sell Cash-Secured Put", "Covered Call",
        }:
            # Non-options instruments get a minimal plan
            return self._no_options_plan(instrument_action, thesis_state, thesis_state_reason)

        # ---- Thesis break check ----
        if thesis_state == "Broken":
            return self._thesis_break_plan(instrument_action, thesis_state_reason, option_return_pct)

        # ---- Structure break: theta / IV / timing ----
        if theta_burn_accelerating or months_remaining < 0.5:
            return self._structure_break_plan(
                instrument_action, option_return_pct, iv_change, iv_percentile, thesis_state_reason
            )

        # ---- IV collapse for short premium ----
        if instrument_action in ("Sell Cash-Secured Put", "Covered Call"):
            if iv_change <= -0.10:
                # IV collapsed — short premium position may need adjustment
                if option_return_pct >= 0.25:
                    return self._efficiency_breakdown_plan(
                        instrument_action, option_return_pct, "IV collapse reduces premium collection", iv_percentile
                    )

        # ---- Return threshold checks ----
        # P2 fix: TARGET_REACHED only when underlying has actually hit the thesis target
        # Return threshold (>60%) without underlying hitting target → RETURN_THRESHOLD
        target_reached = (
            current_price is not None and target_price is not None
            and target_price > 0 and current_price >= target_price
        )
        if target_reached:
            return self._target_reached_plan(
                instrument_action, option_return_pct, thesis_state_reason, iv_change, iv_percentile
            )

        if option_return_pct >= 0.60:
            return self._return_threshold_plan(
                instrument_action, option_return_pct, thesis_state_reason, iv_change, iv_percentile
            )

        if option_return_pct >= 0.30:
            return self._return_threshold_plan(
                instrument_action, option_return_pct, thesis_state_reason, iv_change, iv_percentile
            )

        # ---- Hold ----
        return self._hold_plan(instrument_action, thesis_state_reason, iv_percentile)

    # ------------------------------------------------------------------
    # Plan builders
    # ------------------------------------------------------------------

    def _thesis_break_plan(
        self,
        instrument_action: str,
        reason: str,
        current_return: float,
    ) -> EarlyExitPlan:
        # P1: all actions are advisory — "Consider Closing Position" not "Exit Now"
        action = "Consider Closing Position" if current_return > 0 else "Consider Closing Position"
        severity = "Critical"
        return EarlyExitPlan(
            ticker="",
            primary_exit_trigger=ExitTrigger.THESIS_BREAK,
            severity=severity,
            primary_reason=f"Thesis broken: {reason}",
            first_trim=_zone(
                "first_trim",
                action,
                0.0,
                "Thesis broken — advisory to close",
            ),
            main_profit=_zone(
                "main_profit",
                "Consider Closing Position",
                None,
                "Full exit recommended",
            ),
            full_exit=_zone(
                "full_exit",
                "Consider Closing Position",
                None,
                "Thesis invalidated",
            ),
        )

    def _structure_break_plan(
        self,
        instrument_action: str,
        current_return: float,
        iv_change: float,
        iv_percentile: float,
        reason: str,
    ) -> EarlyExitPlan:
        trigger = "theta_burn" if iv_change >= 0 else "timing"
        return EarlyExitPlan(
            ticker="",
            primary_exit_trigger=ExitTrigger.STRUCTURE_BREAK,
            severity="High",
            primary_reason=f"Structure break: {reason}",
            first_trim=_zone(
                "first_trim",
                "Consider Rolling" if current_return > 0 else "Hold",
                round(current_return, 2) if current_return > 0 else None,
                "Structure deteriorating but thesis intact",
            ),
            main_profit=_zone(
                "main_profit",
                "Consider Closing Position",
                round(current_return, 2),
                "Structure no longer fits thesis timing",
            ),
            full_exit=_zone(
                "full_exit",
                "Consider Closing Position",
                None,
                "Roll not possible or thesis weakened",
            ),
        )

    def _efficiency_breakdown_plan(
        self,
        instrument_action: str,
        current_return: float,
        reason: str,
        iv_percentile: float,
    ) -> EarlyExitPlan:
        # P1: advisory language — "Consider Buy to Close" not "Buy to Close"
        return EarlyExitPlan(
            ticker="",
            primary_exit_trigger=ExitTrigger.EFFICIENCY_BREAKDOWN,
            severity="Medium",
            primary_reason=f"Efficiency breakdown: {reason}",
            first_trim=_zone(
                "first_trim",
                "Consider Taking Profit",
                round(current_return, 2),
                "IV collapse on short premium — consider locking in gains",
            ),
            main_profit=_zone(
                "main_profit",
                "Consider Closing Position",
                None,
                "Remaining premium may not justify holding",
            ),
            full_exit=_zone(
                "full_exit",
                "Consider Buy to Close",
                None,
                "Advisory to close and realize gains",
            ),
        )

    def _target_reached_plan(
        self,
        instrument_action: str,
        current_return: float,
        thesis_state_reason: str,
        iv_change: float,
        iv_percentile: float,
    ) -> EarlyExitPlan:
        # P2: Only reached here when current_price >= target_price (underlying hit thesis target)
        primary_trigger = ExitTrigger.TARGET_REACHED
        iv_note = f" (IV elevated {iv_percentile:.0%})" if iv_percentile >= 0.70 else ""

        return EarlyExitPlan(
            ticker="",
            primary_exit_trigger=primary_trigger,
            severity="Medium",
            primary_reason=f"Target price reached. Return {current_return:.0%}. Thesis: {thesis_state_reason}{iv_note}",
            first_trim=_zone(
                "first_trim",
                "Consider Taking Profit",
                round(current_return, 2),
                f"+{current_return:.0%} return — strong gain, advisory to lock in",
            ),
            main_profit=_zone(
                "main_profit",
                "Consider Trim Half",
                round(min(0.80, current_return * 1.15), 2),
                "Partial exit, keep rest for further upside",
            ),
            full_exit=_zone(
                "full_exit",
                "Consider Closing Position" if current_return >= 0.80 else "Consider Holding",
                round(min(0.95, current_return * 1.20), 2),
                "At +80%+ consider closing position unless thesis still strengthening",
            ),
        )

    def _return_threshold_plan(
        self,
        instrument_action: str,
        current_return: float,
        thesis_state_reason: str,
        iv_change: float,
        iv_percentile: float,
    ) -> EarlyExitPlan:
        # P2: Underlying has NOT reached target price, but option return >= 60%
        # This is RETURN_THRESHOLD not TARGET_REACHED
        iv_note = f" (IV collapse risk)" if iv_change <= -0.05 else ""
        return EarlyExitPlan(
            ticker="",
            primary_exit_trigger=ExitTrigger.RETURN_THRESHOLD,
            severity="Low",
            primary_reason=f"+{current_return:.0%} return. Underlying below thesis target. Thesis: {thesis_state_reason}{iv_note}",
            first_trim=_zone(
                "first_trim",
                "No Action" if current_return < 0.25 else "Watch Trim",
                round(min(0.40, current_return), 2),
                "Below trim threshold — hold and monitor",
            ),
            main_profit=_zone(
                "main_profit",
                "Consider Trim at +50%",
                0.50,
                "Main profit zone — prepare to consider trimming half",
            ),
            full_exit=_zone(
                "full_exit",
                "Consider Full Exit at +70%",
                0.70,
                "Full exit advisory at +70% unless thesis materially strengthens",
            ),
        )

    def _hold_plan(
        self,
        instrument_action: str,
        thesis_state_reason: str,
        iv_percentile: float,
    ) -> EarlyExitPlan:
        iv_note = f" (IV {iv_percentile:.0%})" if iv_percentile >= 0.70 else ""
        return EarlyExitPlan(
            ticker="",
            primary_exit_trigger=ExitTrigger.PRICE_RISK_DISCIPLINE,
            severity="None",
            primary_reason=f"Hold — thesis intact ({thesis_state_reason}){iv_note}. No exit signal.",
            first_trim=_zone(
                "first_trim",
                "No Action",
                0.30,
                "Below trim threshold",
            ),
            main_profit=_zone(
                "main_profit",
                "No Action",
                0.60,
                "Main profit zone not yet reached",
            ),
            full_exit=_zone(
                "full_exit",
                "No Action",
                0.80,
                "Max exit threshold not triggered",
            ),
        )

    def _no_options_plan(
        self,
        instrument_action: str,
        thesis_state: str,
        reason: str,
    ) -> EarlyExitPlan:
        return EarlyExitPlan(
            ticker="",
            primary_exit_trigger=ExitTrigger.PRICE_RISK_DISCIPLINE,
            severity="None",
            primary_reason=f"{instrument_action} — no options early exit applicable. Thesis: {reason}",
            first_trim=_zone("first_trim", "No Action", None, "Stock position — use price discipline"),
            main_profit=_zone("main_profit", "No Action", None, "Stock position"),
            full_exit=_zone("full_exit", "No Action", None, "Stock position"),
        )
