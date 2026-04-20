"""Grading Agent - Assigns S/A/B/C grades to research decisions."""

from datetime import datetime, timedelta, timezone

from typing import Any

from agent.research_v1.llm_clients import BaseLLMClient


class GradingAgent:
    """Grading agent - assigns S/A/B/C grades."""

    # Weights for composite score calculation
    FUNDAMENTAL_WEIGHT = 0.40
    TECHNICAL_WEIGHT = 0.30
    MACRO_WEIGHT = 0.30

    def __init__(self, llm_client: BaseLLMClient, dynamic_weights: dict[str, float] | None = None):
        """Initialize GradingAgent.

        Args:
            llm_client: LLM client for generating grading analysis.
        """
        self.llm = llm_client
        self.dynamic_weights = dynamic_weights or {}
        self.fundamental_weight, self.technical_weight, self.macro_weight = self._resolve_weights()

    def grade(self, research_decision: dict, analyst_reports: dict) -> dict:
        """Calculate composite score and grade.

        Args:
            research_decision: Research decision containing fundamentals_summary,
                               technical_summary, industry_summary, and macro_data.
            analyst_reports: Dictionary of analyst reports for reference.

        Returns:
            dict with keys:
                - grade: "S" | "A" | "B" | "C"
                - fundamental_score: float 0-100
                - technical_score: float 0-100
                - macro_score: float 0-100
                - composite_score: float 0-100
        """
        # Extract summaries
        fundamentals_summary = research_decision.get("fundamentals_summary", {})
        technical_summary = research_decision.get("technical_summary", {})
        industry_summary = research_decision.get("industry_summary", {})
        macro_data = research_decision.get("macro_data", {})

        # Calculate individual scores
        fundamental_score = self._score_fundamentals(fundamentals_summary)
        technical_score = self._score_technical(technical_summary)
        macro_score = self._score_macro(industry_summary, macro_data)

        # Calculate composite score
        composite_result = self._calculate_composite(
            fundamental_score, technical_score, macro_score
        )
        composite_score = composite_result["composite_score"]

        # Determine grade
        grade = self._determine_grade(composite_score, fundamental_score)
        signal = self._build_signal(research_decision, grade, composite_score)

        return {
            "grade": grade,
            "fundamental_score": fundamental_score,
            "technical_score": technical_score,
            "macro_score": macro_score,
            "composite_score": composite_score,
            "signal": signal
        }

    def _score_fundamentals(self, fundamentals_summary: dict) -> float:
        """Score fundamentals 0-100.

        Args:
            fundamentals_summary: Summary dict with verdict and confidence.

        Returns:
            Score from 0-100.
        """
        if not fundamentals_summary:
            return 50.0  # Default neutral score

        verdict = fundamentals_summary.get("verdict", "unknown")
        confidence = fundamentals_summary.get("confidence", 0.5)

        # Map verdict to base score
        verdict_scores = {
            "strong_buy": 95,
            "buy": 80,
            "hold": 60,
            "sell": 40,
            "strong_sell": 20,
            "unknown": 50
        }

        base_score = verdict_scores.get(verdict.lower(), 50)

        # Adjust by confidence (0-1 scale mapped to +/- 10 points)
        confidence_adjustment = (confidence - 0.5) * 20

        return max(0, min(100, base_score + confidence_adjustment))

    def _score_technical(self, technical_summary: dict) -> float:
        """Score technicals 0-100.

        Args:
            technical_summary: Summary dict with signal and indicators.

        Returns:
            Score from 0-100.
        """
        if not technical_summary:
            return 50.0  # Default neutral score

        signal = technical_summary.get("signal", "neutral")
        rsi = technical_summary.get("rsi")
        # TechnicalAnalyst returns macd as tuple (macd_line, signal_line, histogram)
        macd_data = technical_summary.get("macd")
        macd_signal = None
        if macd_data is not None and isinstance(macd_data, (list, tuple)) and len(macd_data) >= 2:
            # macd_data[1] is signal_line: positive = bullish, negative = bearish
            signal_line = macd_data[1]
            if signal_line > 0:
                macd_signal = "bullish"
            elif signal_line < 0:
                macd_signal = "bearish"

        # Map signal to base score
        signal_scores = {
            "strong_buy": 90,
            "buy": 75,
            "neutral": 50,
            "sell": 25,
            "strong_sell": 10
        }

        base_score = signal_scores.get(signal.lower(), 50)

        # RSI adjustment (overbought/oversold indicators)
        rsi_adjustment = 0
        if rsi is not None:
            if rsi < 30:  # Oversold - potential buy signal
                rsi_adjustment = 10
            elif rsi > 70:  # Overbought - potential sell signal
                rsi_adjustment = -10

        # MACD adjustment
        macd_adjustment = 0
        if macd_signal is not None:
            if macd_signal == "bullish":
                macd_adjustment = 5
            elif macd_signal == "bearish":
                macd_adjustment = -5

        return max(0, min(100, base_score + rsi_adjustment + macd_adjustment))

    def _score_macro(self, industry_summary: dict, macro_data: dict) -> float:
        """Score macro match 0-100.

        Args:
            industry_summary: Industry summary with trends and outlook.
            macro_data: Macro economic data.

        Returns:
            Score from 0-100.
        """
        if not industry_summary and not macro_data:
            return 50.0  # Default neutral score

        # Check industry trend alignment
        industry_trend = industry_summary.get("trend", "neutral")
        macro_trend = macro_data.get("trend", "neutral")

        # Alignment scoring
        aligned_trends = {
            ("bullish", "bullish"): 90,
            ("bullish", "neutral"): 70,
            ("neutral", "bullish"): 70,
            ("neutral", "neutral"): 50,
            ("bearish", "bearish"): 30,
            ("bearish", "neutral"): 40,
            ("neutral", "bearish"): 40,
            ("bullish", "bearish"): 45,
            ("bearish", "bullish"): 45
        }

        base_score = aligned_trends.get(
            (industry_trend.lower(), macro_trend.lower()),
            50
        )

        # Sector performance adjustment
        sector_performance = industry_summary.get("sector_performance")
        if sector_performance is not None:
            if sector_performance > 0.05:  # Sector outperforming
                base_score = min(100, base_score + 10)
            elif sector_performance < -0.05:  # Sector underperforming
                base_score = max(0, base_score - 10)

        return max(0, min(100, base_score))

    def _calculate_composite(
        self,
        fundamental_score: float,
        technical_score: float,
        macro_score: float
    ) -> dict:
        """Calculate weighted composite score.

        Args:
            fundamental_score: Score from 0-100.
            technical_score: Score from 0-100.
            macro_score: Score from 0-100.

        Returns:
            dict with composite_score.
        """
        composite = (
            fundamental_score * self.fundamental_weight +
            technical_score * self.technical_weight +
            macro_score * self.macro_weight
        )

        return {
            "composite_score": composite,
            "fundamental_score": fundamental_score,
            "technical_score": technical_score,
            "macro_score": macro_score
        }

    def _resolve_weights(self) -> tuple[float, float, float]:
        """Resolve optional dynamic weights while preserving normalization."""
        f = float(self.dynamic_weights.get("fundamental", self.FUNDAMENTAL_WEIGHT))
        t = float(self.dynamic_weights.get("technical", self.TECHNICAL_WEIGHT))
        m = float(self.dynamic_weights.get("macro", self.MACRO_WEIGHT))
        total = f + t + m
        if total <= 0:
            return self.FUNDAMENTAL_WEIGHT, self.TECHNICAL_WEIGHT, self.MACRO_WEIGHT
        return f / total, t / total, m / total

    def _determine_grade(self, composite_score: float, fundamental_score: float) -> str:
        """Determine letter grade from scores.

        Grade thresholds:
        - S: composite > 80 AND fundamental > 75
        - A: composite 65-80
        - B: composite 50-65
        - C: composite < 50

        Args:
            composite_score: Weighted composite score.
            fundamental_score: Fundamental analysis score.

        Returns:
            Letter grade as string.
        """
        if composite_score > 80 and fundamental_score > 75:
            return "S"
        elif composite_score >= 65:
            return "A"
        elif composite_score >= 50:
            return "B"
        else:
            return "C"

    def _build_signal(
        self,
        research_decision: dict,
        grade: str,
        composite_score: float
    ) -> dict:
        """Build a minimal executable signal from grading output."""
        symbol = research_decision.get("symbol", "UNKNOWN")
        market_data = research_decision.get("market_data", {})
        current_price = market_data.get("price")
        if current_price is None:
            current_price = 0.0

        holding_horizon = self._determine_holding_horizon(grade)
        validity_days = {"5d": 1, "20d": 3, "60d": 5}.get(holding_horizon, 1)
        signal_valid_until = (
            datetime.now(timezone.utc) + timedelta(days=validity_days)
        ).isoformat()
        conflict_penalty = float(
            research_decision.get("evidence_conflict", {}).get("confidence_penalty", 0.0)
        )
        stress_evaluation = research_decision.get("stress_evaluation", {})
        stress_penalty = float(stress_evaluation.get("confidence_penalty", 0.0))
        total_penalty = conflict_penalty + stress_penalty
        confidence = max(0.0, min(1.0, round((composite_score / 100) - total_penalty, 4)))
        priority_score = max(0.0, round(composite_score - (stress_penalty * 100), 2))
        warnings = []
        warning_summary = stress_evaluation.get("warning_summary")
        if warning_summary:
            warnings.append(warning_summary)

        return {
            "symbol": symbol,
            "entry_price": current_price,
            "stop_loss": round(current_price * 0.93, 2) if current_price else 0.0,
            "take_profit": round(current_price * 1.12, 2) if current_price else 0.0,
            "holding_horizon": holding_horizon,
            "signal_valid_until": signal_valid_until,
            "priority_score": priority_score,
            "confidence": confidence,
            "warnings": warnings,
        }

    def _determine_holding_horizon(self, grade: str) -> str:
        """Map a grade to a minimal default holding horizon."""
        return {
            "S": "20d",
            "A": "20d",
            "B": "5d",
            "C": "5d",
        }.get(grade, "5d")
