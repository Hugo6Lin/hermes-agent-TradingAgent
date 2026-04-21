"""
Phase 15: Options Structure Engine.

Selects expiry and strike for bullish options instruments after InstrumentSelectionEngine
has chosen an options-based expression (Buy Call, Bull Call Spread, Sell CSP).

Key principles (from spec):
- expiry = thesis time window + safety buffer (never minimum window)
- strike selection targets delta 0.35–0.70 (moderate ITM to ATM)
- far OTM LEAPS are NOT the default recommendation
- output includes conservative and higher-upside alternatives
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# ---------------------------------------------------------------------------
# Option contract helpers
# ---------------------------------------------------------------------------

def _month_diff(date_str: str) -> int:
    """Approximate months from today to an expiry date string like '2025-09-19'."""
    from datetime import date, datetime
    try:
        exp = datetime.strptime(str(date_str), "%Y-%m-%d").date()
        today = date.today()
        return (exp.year - today.year) * 12 + (exp.month - today.month)
    except Exception:
        return 0


def _select_expiry(target_months: int, available_expiries: list[dict]) -> dict:
    """
    Select expiry with thesis buffer — never minimum window.

    Rule: choose the nearest available expiry that is at least (target_months + 2)
    months out, to give a safety buffer.
    """
    if not available_expiries:
        return {"expiry": None, "expiry_months": target_months + 3}

    # Sort by months until expiry
    sorted_exps = sorted(available_expiries, key=lambda r: _month_diff(r.get("expiry", "")))

    buffer = 2  # safety buffer months
    for row in sorted_exps:
        months = _month_diff(row.get("expiry", ""))
        if months >= target_months + buffer:
            return {"expiry": row.get("expiry"), "expiry_months": months}

    # Fallback: use longest available
    longest = sorted_exps[-1]
    return {"expiry": longest.get("expiry"), "expiry_months": _month_diff(longest.get("expiry", ""))}


def _select_strike(
    current_price: float,
    target_price: float | None,
    available_strikes: list[float],
    option_type: str,
    side: str = "long",
) -> dict:
    """
    Select strike using delta heuristic.

    For long calls / short puts: prefer moderate ITM (delta 0.40–0.65)
    For long puts / short calls: prefer moderate OTM (delta 0.35–0.60)

    Avoids far OTM (delta < 0.20) as the default recommendation.
    """
    if not available_strikes:
        atm = round(current_price, 2)
        return {"strike": atm, "delta_estimate": 0.50, "moneyness": "ATM"}

    sorted_strikes = sorted(available_strikes)

    # Group strikes by moneyness relative to current price
    atm_strike = min(sorted_strikes, key=lambda s: abs(s - current_price))
    itm_strikes = [s for s in sorted_strikes if s < atm_strike]
    otm_strikes = [s for s in sorted_strikes if s > atm_strike]

    if side in ("long", "sell_put"):
        # Prefer moderate ITM or ATM — delta 0.40–0.70
        preferred = [s for s in itm_strikes if 0.85 <= s / current_price <= 1.05]
        if not preferred:
            preferred = [atm_strike]
        # Pick strike closest to current_price * 0.95 (slight ITM)
        chosen = min(preferred, key=lambda s: abs(s - current_price * 0.95))
    elif side == "sell_call":
        # Covered call: ATM to slight OTM
        preferred = [s for s in (itm_strikes + [atm_strike]) if s >= atm_strike * 0.97]
        chosen = min(preferred, key=lambda s: abs(s - atm_strike))
    else:
        chosen = atm_strike

    # Estimate delta heuristically
    moneyness = chosen / current_price
    if moneyness < 0.90:
        delta_est = 0.25
        moneyness_label = "deep_ITM"
    elif moneyness < 0.97:
        delta_est = 0.45
        moneyness_label = "ITM"
    elif moneyness <= 1.03:
        delta_est = 0.55
        moneyness_label = "ATM"
    elif moneyness <= 1.10:
        delta_est = 0.35
        moneyness_label = "OTM"
    else:
        delta_est = 0.18
        moneyness_label = "deep_OTM"

    return {"strike": chosen, "delta_estimate": delta_est, "moneyness": moneyness_label}


def _break_even(
    strike: float,
    current_price: float,
    option_premium: float,
    side: str,
) -> float:
    """Compute break-even price for the position."""
    if side in ("long",):
        return strike + option_premium
    elif side in ("short",):
        return strike - option_premium
    return strike


# ---------------------------------------------------------------------------
# OptionsDecisionEngine
# ---------------------------------------------------------------------------

class OptionsDecisionEngine:
    """
    Phase 15 engine: selects expiry and strike for bullish options instruments.

    Usage after InstrumentSelectionEngine has chosen an options-based action:
        engine = OptionsDecisionEngine()
        structure = engine.decide(
            instrument_action="Buy Call",
            current_price=50.0,
            target_price=60.0,        # from thesis/signal
            thesis_months=6,
            option_chain=[...],        # rows with strike, expiry, iv, delta
            iv_percentile=0.55,
        )
    """

    def decide(
        self,
        instrument_action: str,
        current_price: float,
        target_price: float | None,
        thesis_months: int,
        option_chain: list[dict],
        iv_percentile: float = 0.50,
    ) -> OptionsStructure:
        """
        Select expiry and strike for the given instrument action.

        Args:
            instrument_action: one of VALID_BULLISH_ACTIONS that is options-based
            current_price: current underlying price
            target_price: price target from thesis/signal (used for return mapping)
            thesis_months: expected thesis realization window in months
            option_chain: list of option row dicts from MarketDataService;
                each row should have at least: strike, expiry, iv, delta (or implied_delta)
            iv_percentile: current IV percentile (0.0–1.0)

        Returns:
            OptionsStructure with primary contract and alternatives
        """
        from agent.research_v1.contracts import OptionContract, OptionsStructure

        # Filter chain by call vs put
        call_rows = [r for r in option_chain if str(r.get("option_type", "")).lower() in ("call", "c")]
        put_rows = [r for r in option_chain if str(r.get("option_type", "")).lower() in ("put", "p")]

        if instrument_action == "Buy Call":
            return self._buy_call(current_price, target_price, thesis_months, call_rows, iv_percentile)
        elif instrument_action == "Bull Call Spread":
            return self._bull_call_spread(current_price, target_price, thesis_months, call_rows, iv_percentile)
        elif instrument_action == "Sell Cash-Secured Put":
            return self._sell_csp(current_price, target_price, thesis_months, put_rows, iv_percentile)
        elif instrument_action == "Covered Call":
            return self._covered_call(current_price, target_price, thesis_months, call_rows, iv_percentile)
        else:
            raise ValueError(f"OptionsDecisionEngine cannot handle {instrument_action!r}")

    def _buy_call(
        self,
        current_price: float,
        target_price: float | None,
        thesis_months: int,
        call_rows: list[dict],
        iv_percentile: float,
    ) -> OptionsStructure:
        from agent.research_v1.contracts import OptionContract, OptionsStructure

        # Group by expiry
        by_expiry: dict[str, list[dict]] = {}
        for row in call_rows:
            exp = str(row.get("expiry", ""))
            if exp:
                by_expiry.setdefault(exp, []).append(row)

        available_expiries = [{"expiry": e} for e in by_expiry]
        expiry_result = _select_expiry(thesis_months, available_expiries)
        selected_expiry = expiry_result["expiry"]
        expiry_months = expiry_result["expiry_months"]

        # Available strikes for selected expiry
        exp_strikes = sorted(set(r.get("strike", 0) for r in by_expiry.get(selected_expiry, []) if r.get("strike")))
        strike_result = _select_strike(current_price, target_price, exp_strikes, "call", "long")
        chosen_strike = strike_result["strike"]

        # Build primary contract
        primary = OptionContract(
            expiry_months=expiry_months,
            strike=chosen_strike,
            option_type="call",
            delta_estimate=strike_result["delta_estimate"],
            position_type="long",
        )

        # Conservative: slightly deeper ITM (or Buy Stock if none available)
        conservative_strikes = [s for s in exp_strikes if s < chosen_strike]
        if conservative_strikes:
            conservative_strike = min(conservative_strikes, key=lambda s: abs(s - current_price * 0.92))
        else:
            conservative_strike = chosen_strike

        # Higher upside: slightly OTM
        upside_strikes = [s for s in exp_strikes if s > chosen_strike]
        upside_strike = min(upside_strikes, key=lambda s: abs(s - current_price * 1.05)) if upside_strikes else chosen_strike

        target_summary = self._build_target_path(current_price, target_price, chosen_strike, expiry_months, "call")
        early_exit = self._build_early_exit_summary("call", iv_percentile)

        return OptionsStructure(
            ticker="",
            instrument_action="Buy Call",
            primary_contract=primary,
            conservative_alternative="Buy Stock" if not conservative_strikes else f"{expiry_months}m {conservative_strike}C",
            higher_upside_alternative=f"{expiry_months}m {upside_strike}C" if upside_strike != chosen_strike else None,
            target_path_summary=target_summary,
            early_exit_summary=early_exit,
        )

    def _bull_call_spread(
        self,
        current_price: float,
        target_price: float | None,
        thesis_months: int,
        call_rows: list[dict],
        iv_percentile: float,
    ) -> OptionsStructure:
        from agent.research_v1.contracts import OptionContract, OptionsStructure

        by_expiry: dict[str, list[dict]] = {}
        for row in call_rows:
            exp = str(row.get("expiry", ""))
            if exp:
                by_expiry.setdefault(exp, []).append(row)

        available_expiries = [{"expiry": e} for e in by_expiry]
        expiry_result = _select_expiry(thesis_months, available_expiries)
        selected_expiry = expiry_result["expiry"]
        expiry_months = expiry_result["expiry_months"]

        exp_strikes = sorted(set(r.get("strike", 0) for r in by_expiry.get(selected_expiry, []) if r.get("strike")))

        # Long strike: moderate ITM/ATM
        long_result = _select_strike(current_price, target_price, exp_strikes, "call", "long")
        long_strike = long_result["strike"]

        # Short strike: higher strike, same expiry (OTM)
        short_candidates = [s for s in exp_strikes if s > long_strike]
        short_strike = min(short_candidates, key=lambda s: abs(s - current_price * 1.08)) if short_candidates else long_strike * 1.08

        primary = OptionContract(
            expiry_months=expiry_months,
            strike=long_strike,
            option_type="call",
            delta_estimate=long_result["delta_estimate"],
            position_type="long",
            short_contract=OptionContract(
                expiry_months=expiry_months,
                strike=short_strike,
                option_type="call",
                position_type="short",
            ),
        )

        target_summary = (
            f"Bull Call Spread: long {expiry_months}m {long_strike}C / short {short_strike}C. "
            f"Net debit ~${max(0, short_strike - long_strike):.2f}. "
            f"Max profit at/above {short_strike}. Max loss = net debit."
        )
        early_exit = self._build_early_exit_summary("spread", iv_percentile)

        return OptionsStructure(
            ticker="",
            instrument_action="Bull Call Spread",
            primary_contract=primary,
            conservative_alternative=f"{expiry_months}m {long_strike}C (no spread — full upside)",
            higher_upside_alternative=f"{expiry_months}m {short_strike}C (wider spread)",
            target_path_summary=target_summary,
            early_exit_summary=early_exit,
            strategy_net_debit=round(short_strike - long_strike, 2),
        )

    def _sell_csp(
        self,
        current_price: float,
        target_price: float | None,
        thesis_months: int,
        put_rows: list[dict],
        iv_percentile: float,
    ) -> OptionsStructure:
        from agent.research_v1.contracts import OptionContract, OptionsStructure

        by_expiry: dict[str, list[dict]] = {}
        for row in put_rows:
            exp = str(row.get("expiry", ""))
            if exp:
                by_expiry.setdefault(exp, []).append(row)

        available_expiries = [{"expiry": e} for e in by_expiry]
        expiry_result = _select_expiry(thesis_months, available_expiries)
        selected_expiry = expiry_result["expiry"]
        expiry_months = expiry_result["expiry_months"]

        exp_strikes = sorted(set(r.get("strike", 0) for r in by_expiry.get(selected_expiry, []) if r.get("strike")))
        strike_result = _select_strike(current_price, target_price, exp_strikes, "put", "sell_put")
        chosen_strike = strike_result["strike"]

        primary = OptionContract(
            expiry_months=expiry_months,
            strike=chosen_strike,
            option_type="put",
            delta_estimate=strike_result["delta_estimate"],
            position_type="short",
        )

        target_summary = (
            f"Sell Cash-Secured Put: {expiry_months}m {chosen_strike}P. "
            f"Premium received ~${max(0, current_price - chosen_strike) * 0.10:.2f} (est). "
            f"If assigned at {chosen_strike}, cost basis = strike - premium received."
        )
        early_exit = self._build_early_exit_summary("sell_put", iv_percentile)

        return OptionsStructure(
            ticker="",
            instrument_action="Sell Cash-Secured Put",
            primary_contract=primary,
            conservative_alternative="Buy Stock (own at current price)",
            higher_upside_alternative=f"Sell {expiry_months}m {int(chosen_strike * 0.95)}P (lower strike)",
            target_path_summary=target_summary,
            early_exit_summary=early_exit,
            strategy_net_credit=round(max(0, current_price - chosen_strike) * 0.10, 2),
            assignment_strike=chosen_strike,
        )

    def _covered_call(
        self,
        current_price: float,
        target_price: float | None,
        thesis_months: int,
        call_rows: list[dict],
        iv_percentile: float,
    ) -> OptionsStructure:
        from agent.research_v1.contracts import OptionContract, OptionsStructure

        by_expiry: dict[str, list[dict]] = {}
        for row in call_rows:
            exp = str(row.get("expiry", ""))
            if exp:
                by_expiry.setdefault(exp, []).append(row)

        available_expiries = [{"expiry": e} for e in by_expiry]
        expiry_result = _select_expiry(thesis_months, available_expiries)
        selected_expiry = expiry_result["expiry"]
        expiry_months = expiry_result["expiry_months"]

        exp_strikes = sorted(set(r.get("strike", 0) for r in by_expiry.get(selected_expiry, []) if r.get("strike")))
        strike_result = _select_strike(current_price, target_price, exp_strikes, "call", "sell_call")
        chosen_strike = strike_result["strike"]

        primary = OptionContract(
            expiry_months=expiry_months,
            strike=chosen_strike,
            option_type="call",
            delta_estimate=strike_result["delta_estimate"],
            position_type="short",
            covered_by_shares=True,
        )

        target_summary = (
            f"Covered Call: {expiry_months}m {chosen_strike}C against held shares. "
            f"Income ~${max(0, chosen_strike - current_price) * 0.05:.2f} (est). "
            f"If called away at {chosen_strike}, return = (strike - entry) + premium."
        )
        early_exit = self._build_early_exit_summary("sell_call", iv_percentile)

        return OptionsStructure(
            ticker="",
            instrument_action="Covered Call",
            primary_contract=primary,
            conservative_alternative="Sell shares (no covered call)",
            higher_upside_alternative=f"{expiry_months}m {int(chosen_strike * 1.05)}C (higher strike, less income)",
            target_path_summary=target_summary,
            early_exit_summary=early_exit,
            strategy_net_credit=round(max(0, chosen_strike - current_price) * 0.05, 2),
            assignment_strike=chosen_strike,
            covered_by_shares=True,
        )

    def _build_target_path(
        self,
        current_price: float,
        target_price: float | None,
        strike: float,
        expiry_months: int,
        option_type: str,
    ) -> str:
        if target_price is None:
            return f"{option_type.title()} {strike} expires in ~{expiry_months}m. Return depends on price at expiry."

        upside_pct = (target_price - current_price) / current_price
        if option_type == "call":
            return (
                f"If {current_price} → {target_price} (+{upside_pct:.0%}) by expiry: "
                f"{option_type} {strike} likely deeply ITM, high profit. "
                f"If thesis materializes early: consider rolling or taking profit at +30–50% of max."
            )
        elif option_type == "put":
            return (
                f"If assigned at {strike}: effective cost = strike - premium received. "
                f"Target {target_price} still valid. "
                f"Cover if price falls to strike — reassess thesis."
            )
        return f"Target path: {current_price} → {target_price} over {expiry_months}m window."

    def _build_early_exit_summary(self, option_type: str, iv_percentile: float) -> str:
        iv_note = f" (IV elevated {iv_percentile:.0%})" if iv_percentile >= 0.70 else " (IV normal)"
        if option_type in ("call", "spread"):
            return (
                "Exit zones: [1] Trim at +30% of max profit. "
                "[2] Main profit zone +50–70%. "
                "[3] Full exit at +80% or 2 weeks before expiry, whichever first. "
                f"If IV collapses{iv_note}: consider early exit or rolling."
            )
        elif option_type in ("sell_put", "sell_call"):
            return (
                "Exit triggers: [1] If assigned — hold stock. "
                "[2] If underlying breaks key support — review thesis. "
                "[3] If IV surges >15 pts — consider buyback to close. "
                f"Stay short until expiration or early assignment{iv_note}."
            )
        return "Review position monthly. Exit if thesis changes or structure no longer fits."
