"""
Phase 14: Instrument Selection Engine.

Selects the best bullish expression of an Investable stock thesis.

Allowed instruments:
    - Buy Stock: prefer when thesis is strong, IV is high, time window is long
    - Buy Call: prefer when thesis is strong, timing clear, IV not excessive
    - Bull Call Spread: prefer when upside is positive but bounded, long calls expensive
    - Sell Cash-Secured Put: prefer when willing to own lower, elevated IV
    - Covered Call: prefer when stock is held, long thesis intact, short-term upside limited
    - Watchlist / No Trade: when underlying is not Investable
"""

from __future__ import annotations

from agent.research_v1.contracts import UnderlyingThesis, InstrumentRecommendation


class InstrumentSelectionEngine:
    """
    Selects the best bullish instrument for an Investable stock thesis.

    Rules (from spec):
      Buy Stock       — strong thesis, high IV, long/uncertain time window
      Buy Call        — strong thesis, acceptable IV, reasonably clear timing
      Bull Call Spread — positive but bounded upside, expensive long calls
      Sell CSP        — investable, willing to own lower, elevated IV
      Covered Call    — stock already held, long thesis intact, limited short-term upside
      No Trade        — underlying not Investable
    """

    def choose(
        self,
        thesis: UnderlyingThesis,
        option_context: dict,
        holding_context: dict,
    ) -> InstrumentRecommendation:
        """
        Choose the best instrument for the given thesis and context.

        Args:
            thesis: UnderlyingThesis result (must be Investable for any instrument).
            option_context: Dict with keys:
                - iv_percentile: 0.0–1.0 (high = expensive for buyers)
                - wants_discounted_entry: bool
                - short_term_upside_limited: bool
                - liquidity_ok: bool
            holding_context: Dict with keys:
                - has_stock: bool

        Returns:
            InstrumentRecommendation with primary_action and ranked_alternatives.
        """
        if thesis.classification != "Investable":
            return InstrumentRecommendation(
                task_id=thesis.task_id,
                ticker=thesis.ticker,
                primary_action="No Trade",
                ranked_alternatives=[],
                reason=f"Underlying {thesis.ticker} is {thesis.classification}, not Investable",
            )

        iv = option_context.get("iv_percentile", 0.5)
        has_stock = holding_context.get("has_stock", False)
        short_upside_limited = option_context.get("short_term_upside_limited", False)
        wants_discounted = option_context.get("wants_discounted_entry", False)

        # Covered Call: stock held + limited short-term upside + income preferred
        if has_stock and short_upside_limited:
            return InstrumentRecommendation(
                task_id=thesis.task_id,
                ticker=thesis.ticker,
                primary_action="Covered Call",
                ranked_alternatives=["Buy Stock", "Buy Call"],
                reason="Stock held; long thesis intact but short-term upside limited; prefer income over full upside capture",
            )

        # Sell Cash-Secured Put: wants discounted entry + elevated IV
        if wants_discounted and iv >= 0.70:
            return InstrumentRecommendation(
                task_id=thesis.task_id,
                ticker=thesis.ticker,
                primary_action="Sell Cash-Secured Put",
                ranked_alternatives=["Buy Stock"],
                reason="Willing to own lower; elevated IV makes put selling attractive",
            )

        # Buy Stock: IV too expensive for buyers
        if iv >= 0.85:
            return InstrumentRecommendation(
                task_id=thesis.task_id,
                ticker=thesis.ticker,
                primary_action="Buy Stock",
                ranked_alternatives=["Sell Cash-Secured Put"],
                reason="Options are too expensive for buyers; prefer stock ownership",
            )

        # Bull Call Spread: IV moderately high (spread is cost-efficient)
        if iv >= 0.65:
            return InstrumentRecommendation(
                task_id=thesis.task_id,
                ticker=thesis.ticker,
                primary_action="Bull Call Spread",
                ranked_alternatives=["Buy Call", "Buy Stock"],
                reason="Moderately elevated IV; spread is more cost-efficient than naked long call",
            )

        # Default: Buy Call (strong thesis, acceptable IV, some leverage desired)
        return InstrumentRecommendation(
            task_id=thesis.task_id,
            ticker=thesis.ticker,
            primary_action="Buy Call",
            ranked_alternatives=["Buy Stock", "Bull Call Spread"],
            reason="Bullish thesis with acceptable option pricing; long call provides leverage",
        )
