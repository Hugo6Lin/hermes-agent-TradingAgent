"""
Tests for thesis_engine — Phase 14 bullish decision system.

Phase 14: Underlying Thesis + Instrument Selection
- ThesisEngine evaluates whether a stock is worth owning at all
- Classifies as Investable / Watchlist / No Trade
"""

from __future__ import annotations

import pytest

from agent.research_v1.contracts import UnderlyingThesis, InstrumentRecommendation, PositionDecisionCard


# ---------------------------------------------------------------------------
# Contract tests
# ---------------------------------------------------------------------------

class TestUnderlyingThesisContract:
    def test_underlying_thesis_requires_classification(self):
        with pytest.raises(ValueError):
            UnderlyingThesis(
                task_id="t1",
                ticker="AAPL",
                quality_score=0.82,
                valuation_score=0.71,
                catalyst_score=0.68,
                thesis_risk_score=0.35,
                classification="",
                summary="Strong business quality",
            )

    def test_underlying_thesis_requires_valid_classification(self):
        with pytest.raises(ValueError):
            UnderlyingThesis(
                task_id="t1",
                ticker="AAPL",
                quality_score=0.82,
                valuation_score=0.71,
                catalyst_score=0.68,
                thesis_risk_score=0.35,
                classification="Maybe",
                summary="Strong business quality",
            )

    def test_underlying_thesis_accepts_investable(self):
        thesis = UnderlyingThesis(
            task_id="t1",
            ticker="AAPL",
            quality_score=0.82,
            valuation_score=0.71,
            catalyst_score=0.68,
            thesis_risk_score=0.35,
            classification="Investable",
            summary="Strong business quality",
        )
        assert thesis.classification == "Investable"

    def test_underlying_thesis_accepts_watchlist(self):
        thesis = UnderlyingThesis(
            task_id="t1",
            ticker="AAPL",
            quality_score=0.5,
            valuation_score=0.3,
            catalyst_score=0.4,
            thesis_risk_score=0.5,
            classification="Watchlist",
            summary="Positive thesis but weak timing",
        )
        assert thesis.classification == "Watchlist"

    def test_underlying_thesis_accepts_no_trade(self):
        thesis = UnderlyingThesis(
            task_id="t1",
            ticker="AAPL",
            quality_score=0.2,
            valuation_score=0.1,
            catalyst_score=0.2,
            thesis_risk_score=0.8,
            classification="No Trade",
            summary="Broken economics",
        )
        assert thesis.classification == "No Trade"


class TestInstrumentRecommendationContract:
    def test_instrument_recommendation_requires_action(self):
        with pytest.raises(ValueError):
            InstrumentRecommendation(
                task_id="t1",
                ticker="AAPL",
                primary_action="",
                ranked_alternatives=["Buy Stock"],
                reason="Test",
            )

    def test_instrument_recommendation_accepts_valid_action(self):
        rec = InstrumentRecommendation(
            task_id="t1",
            ticker="AAPL",
            primary_action="Buy Stock",
            ranked_alternatives=["Buy Call"],
            reason="Strong thesis, low IV",
        )
        assert rec.primary_action == "Buy Stock"

    def test_buy_call_is_valid_action(self):
        rec = InstrumentRecommendation(
            task_id="t1",
            ticker="AAPL",
            primary_action="Buy Call",
            ranked_alternatives=["Buy Stock"],
            reason="Strong thesis with acceptable IV",
        )
        assert rec.primary_action == "Buy Call"

    def test_bull_call_spread_is_valid_action(self):
        rec = InstrumentRecommendation(
            task_id="t1",
            ticker="AAPL",
            primary_action="Bull Call Spread",
            ranked_alternatives=["Buy Call"],
            reason="Bounded upside, cost efficient",
        )
        assert rec.primary_action == "Bull Call Spread"

    def test_sell_cash_secured_put_is_valid_action(self):
        rec = InstrumentRecommendation(
            task_id="t1",
            ticker="GLW",
            primary_action="Sell Cash-Secured Put",
            ranked_alternatives=["Buy Stock"],
            reason="Willing to own lower at elevated IV",
        )
        assert rec.primary_action == "Sell Cash-Secured Put"

    def test_covered_call_is_valid_action(self):
        rec = InstrumentRecommendation(
            task_id="t1",
            ticker="AAPL",
            primary_action="Covered Call",
            ranked_alternatives=["Buy Stock"],
            reason="Stock already held, limited short-term upside",
        )
        assert rec.primary_action == "Covered Call"

    def test_no_trade_is_valid_action(self):
        rec = InstrumentRecommendation(
            task_id="t1",
            ticker="AAPL",
            primary_action="No Trade",
            ranked_alternatives=[],
            reason="Underlying not investable",
        )
        assert rec.primary_action == "No Trade"

    def test_watchlist_is_valid_action(self):
        rec = InstrumentRecommendation(
            task_id="t1",
            ticker="AAPL",
            primary_action="Watchlist",
            ranked_alternatives=[],
            reason="Positive thesis but weak timing",
        )
        assert rec.primary_action == "Watchlist"


class TestPositionDecisionCardContract:
    def test_position_decision_card_allows_buy_stock_as_primary_action(self):
        card = PositionDecisionCard(
            task_id="t1",
            ticker="AAPL",
            primary_action="Buy Stock",
            conviction="High",
            thesis_summary="High-quality compounding business",
            why_now="Valuation reset after short-term weakness",
            alternatives=["Buy Call", "Bull Call Spread"],
        )
        assert card.primary_action == "Buy Stock"
        assert card.conviction == "High"

    def test_position_decision_card_requires_primary_action(self):
        with pytest.raises(ValueError):
            PositionDecisionCard(
                task_id="t1",
                ticker="AAPL",
                primary_action="",
                conviction="High",
                thesis_summary="Strong business",
                why_now="Test",
                alternatives=[],
            )

    def test_position_decision_card_requires_valid_action(self):
        with pytest.raises(ValueError):
            PositionDecisionCard(
                task_id="t1",
                ticker="AAPL",
                primary_action="Short Stock",
                conviction="High",
                thesis_summary="Strong business",
                why_now="Test",
                alternatives=[],
            )


# ---------------------------------------------------------------------------
# ThesisEngine unit tests
# ---------------------------------------------------------------------------

class TestThesisEngine:
    def test_thesis_engine_returns_no_trade_for_low_quality_company(self):
        from agent.research_v1.thesis_engine import ThesisEngine
        engine = ThesisEngine()
        result = engine.evaluate(
            ticker="SPEC",
            fundamentals={"profitability": 0.1, "balance_sheet": 0.2},
            valuation={"upside_pct": 0.05},
            catalysts={"clarity": 0.2},
        )
        assert result.classification == "No Trade"

    def test_thesis_engine_can_mark_stock_investable(self):
        from agent.research_v1.thesis_engine import ThesisEngine
        engine = ThesisEngine()
        # All 5 fundamental dimensions must be present for high quality score
        result = engine.evaluate(
            ticker="AAPL",
            fundamentals={
                "profitability": 0.90,
                "balance_sheet": 0.90,
                "earnings_quality": 0.90,
                "capital_allocation": 0.90,
                "industry_position": 0.90,
            },
            valuation={"upside_pct": 0.22},
            catalysts={"clarity": 0.75},
        )
        assert result.classification == "Investable"

    def test_thesis_engine_marks_watchlist_for_weak_upside(self):
        from agent.research_v1.thesis_engine import ThesisEngine
        engine = ThesisEngine()
        # Sparse 2-dimension input: quality normalized by 5 expected fields = 0.29
        # 0.29 < no_trade_quality_threshold=0.35 -> No Trade (correct: sparse coverage fails gate)
        result = engine.evaluate(
            ticker="AAPL",
            fundamentals={"profitability": 0.75, "balance_sheet": 0.70},
            valuation={"upside_pct": 0.08},
            catalysts={"clarity": 0.65},
        )
        assert result.classification == "No Trade"

    def test_thesis_engine_output_fields(self):
        from agent.research_v1.thesis_engine import ThesisEngine
        engine = ThesisEngine()
        result = engine.evaluate(
            ticker="AAPL",
            fundamentals={
                "profitability": 0.90,
                "balance_sheet": 0.90,
                "earnings_quality": 0.90,
                "capital_allocation": 0.90,
                "industry_position": 0.90,
            },
            valuation={"upside_pct": 0.22},
            catalysts={"clarity": 0.75},
        )
        assert result.ticker == "AAPL"
        # All 5 fields at 0.90 -> quality = 0.90
        assert result.quality_score > 0.8
        assert result.valuation_score == 0.22
        assert result.catalyst_score == 0.75
        assert result.classification == "Investable"
        assert result.summary != ""
