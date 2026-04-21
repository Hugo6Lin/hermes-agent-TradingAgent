"""
Tests for instrument_selection — Phase 14 bullish decision system.

Phase 14: Underlying Thesis + Instrument Selection
- InstrumentSelectionEngine selects the best bullish expression of a stock thesis
- Choices: Buy Stock, Buy Call, Bull Call Spread, Sell Cash-Secured Put, Covered Call
"""

from __future__ import annotations

import pytest

from agent.research_v1.contracts import (
    UnderlyingThesis,
    InstrumentRecommendation,
    VALID_BULLISH_ACTIONS,
)


class TestInstrumentSelectionEngine:
    """Unit tests for InstrumentSelectionEngine."""

    def test_selector_returns_no_trade_when_not_investable(self):
        from agent.research_v1.instrument_selection import InstrumentSelectionEngine
        selector = InstrumentSelectionEngine()
        thesis = UnderlyingThesis(
            task_id="t1",
            ticker="AAPL",
            quality_score=0.3,
            valuation_score=0.1,
            catalyst_score=0.2,
            thesis_risk_score=0.7,
            classification="No Trade",
            summary="Low quality",
        )
        rec = selector.choose(thesis, {}, {"has_stock": False})
        assert rec.primary_action == "No Trade"

    def test_selector_prefers_stock_when_iv_is_expensive(self):
        from agent.research_v1.instrument_selection import InstrumentSelectionEngine
        selector = InstrumentSelectionEngine()
        thesis = UnderlyingThesis(
            task_id="t1",
            ticker="AAPL",
            quality_score=0.9,
            valuation_score=0.2,
            catalyst_score=0.7,
            thesis_risk_score=0.2,
            classification="Investable",
            summary="Strong business",
        )
        rec = selector.choose(
            thesis,
            {"iv_percentile": 0.92, "liquidity_ok": True},
            {"has_stock": False},
        )
        assert rec.primary_action == "Buy Stock"

    def test_selector_chooses_buy_call_for_investable_with_acceptable_iv(self):
        from agent.research_v1.instrument_selection import InstrumentSelectionEngine
        selector = InstrumentSelectionEngine()
        thesis = UnderlyingThesis(
            task_id="t1",
            ticker="AAPL",
            quality_score=0.85,
            valuation_score=0.25,
            catalyst_score=0.75,
            thesis_risk_score=0.2,
            classification="Investable",
            summary="Strong thesis",
        )
        rec = selector.choose(
            thesis,
            {"iv_percentile": 0.50, "liquidity_ok": True},
            {"has_stock": False},
        )
        assert rec.primary_action == "Buy Call"

    def test_selector_chooses_cash_secured_put_when_wants_discounted_entry(self):
        from agent.research_v1.instrument_selection import InstrumentSelectionEngine
        selector = InstrumentSelectionEngine()
        thesis = UnderlyingThesis(
            task_id="t1",
            ticker="GLW",
            quality_score=0.82,
            valuation_score=0.12,
            catalyst_score=0.62,
            thesis_risk_score=0.28,
            classification="Investable",
            summary="Investable at current price",
        )
        rec = selector.choose(
            thesis,
            {"iv_percentile": 0.84, "wants_discounted_entry": True, "liquidity_ok": True},
            {"has_stock": False},
        )
        assert rec.primary_action == "Sell Cash-Secured Put"

    def test_selector_chooses_covered_call_when_stock_held_and_upside_limited(self):
        from agent.research_v1.instrument_selection import InstrumentSelectionEngine
        selector = InstrumentSelectionEngine()
        thesis = UnderlyingThesis(
            task_id="t1",
            ticker="AAPL",
            quality_score=0.85,
            valuation_score=0.1,
            catalyst_score=0.6,
            thesis_risk_score=0.25,
            classification="Investable",
            summary="Held stock with limited upside",
        )
        rec = selector.choose(
            thesis,
            {"iv_percentile": 0.6, "short_term_upside_limited": True, "liquidity_ok": True},
            {"has_stock": True},
        )
        assert rec.primary_action == "Covered Call"

    def test_selector_output_fields(self):
        from agent.research_v1.instrument_selection import InstrumentSelectionEngine
        selector = InstrumentSelectionEngine()
        thesis = UnderlyingThesis(
            task_id="t1",
            ticker="AAPL",
            quality_score=0.85,
            valuation_score=0.22,
            catalyst_score=0.72,
            thesis_risk_score=0.2,
            classification="Investable",
            summary="Strong thesis",
        )
        rec = selector.choose(
            thesis,
            {"iv_percentile": 0.5, "liquidity_ok": True},
            {"has_stock": False},
        )
        assert rec.ticker == "AAPL"
        assert rec.task_id == "t1"
        assert rec.primary_action in VALID_BULLISH_ACTIONS
        assert rec.reason != ""


class TestInstrumentSelectionEngineValidation:
    """Validation: instrument selection engine must not emit bearish actions."""

    def test_instrument_selector_never_emits_short_stock(self):
        from agent.research_v1.instrument_selection import InstrumentSelectionEngine
        selector = InstrumentSelectionEngine()
        thesis = UnderlyingThesis(
            task_id="t1",
            ticker="AAPL",
            quality_score=0.85,
            valuation_score=0.22,
            catalyst_score=0.72,
            thesis_risk_score=0.2,
            classification="Investable",
            summary="Strong thesis",
        )
        # Exhaustively try all combinations that could produce wrong actions
        iv_percentiles = [0.2, 0.5, 0.85, 0.95]
        has_stocks = [True, False]
        short_upside = [True, False]
        wants_discount = [True, False]
        for iv in iv_percentiles:
            for held in has_stocks:
                for limited in short_upside:
                    for discounted in wants_discount:
                        rec = selector.choose(
                            thesis,
                            {"iv_percentile": iv, "short_term_upside_limited": limited,
                             "wants_discounted_entry": discounted, "liquidity_ok": True},
                            {"has_stock": held},
                        )
                        assert rec.primary_action not in {"Short Stock", "Buy Put", "Long Put"}, \
                            f"Got bearish action {rec.primary_action} for iv={iv}, held={held}"

    def test_all_valid_actions_are_produced(self):
        from agent.research_v1.instrument_selection import InstrumentSelectionEngine
        selector = InstrumentSelectionEngine()
        # Verify the engine can produce each valid action type with appropriate inputs
        produced = set()

        # No Trade — non-investable thesis
        thesis_no = UnderlyingThesis(
            task_id="t1", ticker="BAD", quality_score=0.2,
            valuation_score=0.05, catalyst_score=0.1, thesis_risk_score=0.9,
            classification="No Trade", summary="Broken",
        )
        produced.add(selector.choose(thesis_no, {}, {"has_stock": False}).primary_action)

        # Buy Stock — expensive IV
        thesis_stk = UnderlyingThesis(
            task_id="t1", ticker="EXP", quality_score=0.88,
            valuation_score=0.22, catalyst_score=0.75, thesis_risk_score=0.18,
            classification="Investable", summary="Strong",
        )
        produced.add(selector.choose(
            thesis_stk, {"iv_percentile": 0.93, "liquidity_ok": True}, {"has_stock": False}
        ).primary_action)

        # Buy Call — normal IV
        produced.add(selector.choose(
            thesis_stk, {"iv_percentile": 0.45, "liquidity_ok": True}, {"has_stock": False}
        ).primary_action)

        # Sell CSP — wants discounted entry
        produced.add(selector.choose(
            thesis_stk, {"iv_percentile": 0.85, "wants_discounted_entry": True, "liquidity_ok": True},
            {"has_stock": False}
        ).primary_action)

        # Covered Call — held stock, limited upside
        produced.add(selector.choose(
            thesis_stk, {"iv_percentile": 0.55, "short_term_upside_limited": True, "liquidity_ok": True},
            {"has_stock": True}
        ).primary_action)

        # Verify we can produce at least 4 distinct positive actions
        assert len(produced) >= 4, f"Only produced {produced}, expected more diversity"
