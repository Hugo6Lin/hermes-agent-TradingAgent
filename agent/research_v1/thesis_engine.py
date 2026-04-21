"""
Phase 14: Underlying Thesis Engine.

Evaluates whether a stock is worth owning at all before any derivative instrument
selection begins.

Classification:
    - Investable: strong quality + credible upside + reasonable path
    - Watchlist: positive thesis but weak timing / weak current upside
    - No Trade: low quality or broken economics
"""

from __future__ import annotations

from dataclasses import dataclass

from agent.research_v1.contracts import UnderlyingThesis


class ThesisEngine:
    """
    Stock-thesis evaluation engine.

    Takes fundamental, valuation, and catalyst inputs and produces an
    UnderlyingThesis classification.
    """

    def evaluate(
        self,
        ticker: str,
        fundamentals: dict,
        valuation: dict,
        catalysts: dict,
        task_id: str = "",
    ) -> UnderlyingThesis:
        """
        Evaluate a stock's investment thesis.

        Args:
            ticker: Stock symbol.
            fundamentals: Dict with keys like 'profitability', 'balance_sheet', 'earnings_quality'.
            valuation: Dict with keys like 'upside_pct' (e.g. 0.22 = 22% upside).
            catalysts: Dict with keys like 'clarity' (0.0–1.0).
            task_id: Optional task ID for tracking.

        Returns:
            UnderlyingThesis with classification and scores.
        """
        quality = self._quality_score(fundamentals)
        valuation_score = float(valuation.get("upside_pct", 0.0))
        catalyst_score = float(catalysts.get("clarity", 0.0))
        thesis_risk = max(0.0, 1.0 - quality)

        classification = self._classify(quality, valuation_score, catalyst_score)
        summary = self._summarize(ticker, classification, quality, valuation_score, catalyst_score)

        return UnderlyingThesis(
            task_id=task_id,
            ticker=ticker,
            quality_score=quality,
            valuation_score=valuation_score,
            catalyst_score=catalyst_score,
            thesis_risk_score=thesis_risk,
            classification=classification,
            summary=summary,
        )

    def _quality_score(self, fundamentals: dict) -> float:
        """Average of available fundamental quality indicators."""
        keys = ["profitability", "balance_sheet", "earnings_quality", "capital_allocation", "industry_position"]
        scores = [fundamentals.get(k, 0.0) for k in keys]
        valid = [s for s in scores if s > 0.0]
        if not valid:
            return 0.0
        return sum(valid) / len(valid)

    def _classify(
        self,
        quality: float,
        valuation_score: float,
        catalyst_score: float,
    ) -> str:
        """Classify the stock based on quality, valuation, and catalyst scores."""
        if quality < 0.35:
            return "No Trade"
        if quality >= 0.65 and valuation_score >= 0.15 and catalyst_score >= 0.5:
            return "Investable"
        return "Watchlist"

    def _summarize(
        self,
        ticker: str,
        classification: str,
        quality: float,
        valuation_score: float,
        catalyst_score: float,
    ) -> str:
        parts = {
            "No Trade": f"{ticker} not suitable for investment: low quality ({quality:.0%})",
            "Watchlist": f"{ticker} worth monitoring: quality {quality:.0%}, upside {valuation_score:.0%}, catalyst {catalyst_score:.0%}",
            "Investable": f"{ticker} qualifies as Investable: quality {quality:.0%}, upside {valuation_score:.0%}, catalyst {catalyst_score:.0%}",
        }
        return parts[classification]
