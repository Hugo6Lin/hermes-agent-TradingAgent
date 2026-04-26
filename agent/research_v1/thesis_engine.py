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
from agent.research_v1.calibration_config import ThesisThresholdConfig


class ThesisEngine:
    """
    Stock-thesis evaluation engine.

    Takes fundamental, valuation, and catalyst inputs and produces an
    UnderlyingThesis classification.
    """

    def __init__(self, thresholds: ThesisThresholdConfig | None = None):
        """Initialize ThesisEngine with optional threshold config."""
        self.thresholds = thresholds or ThesisThresholdConfig()

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
        """Quality score normalized by expected field count, penalizing missing dimensions."""
        keys = ["profitability", "balance_sheet", "earnings_quality", "capital_allocation", "industry_position"]
        if not keys:
            return 0.0
        scores = [float(fundamentals.get(k, 0.0) or 0.0) for k in keys]
        return max(0.0, min(1.0, sum(scores) / len(keys)))

    def _classify(
        self,
        quality: float,
        valuation_score: float,
        catalyst_score: float,
    ) -> str:
        """Classify the stock based on quality, valuation, and catalyst scores."""
        if quality < self.thresholds.no_trade_quality_threshold:
            return "No Trade"
        if (
            quality >= self.thresholds.investable_quality_threshold
            and valuation_score >= self.thresholds.investable_valuation_threshold
            and catalyst_score >= self.thresholds.investable_catalyst_threshold
        ):
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
