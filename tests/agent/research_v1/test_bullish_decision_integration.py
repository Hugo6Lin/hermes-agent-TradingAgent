"""
Phase 14 bullish decision integration tests.

Tests that the full app pipeline correctly produces bullish decision outputs:
- thesis evaluation
- instrument selection
- PositionDecisionCard

Phase 14 scope only — does not test options structure (Phase 15).
"""

from __future__ import annotations

import pytest
from unittest.mock import Mock

from agent.research_v1.contracts import (
    VALID_BULLISH_ACTIONS,
    UnderlyingThesis,
    InstrumentRecommendation,
    PositionDecisionCard,
)


# ---------------------------------------------------------------------------
# Helper: Mock LLM client for Phase 14 tests
# ---------------------------------------------------------------------------

class _Phase14MockClient(Mock):
    """Mock LLM client that returns structured bullish evidence."""

    def generate(self, messages, temperature=0.7, max_tokens=4096):
        from agent.research_v1.llm_clients import LLMResponse

        prompt_text = " ".join(m.get("content", "") for m in messages if m.get("content"))

        if "fundamentals" in prompt_text.lower():
            json_body = '{"summary": "High-quality compounding business", "verdict": "buy", "confidence": 0.88, "direction": "bullish"}'
        elif "technical" in prompt_text.lower():
            json_body = '{"trend": "bullish", "signals": ["RSI 42"], "recommendation": "buy", "confidence": 0.82}'
        elif "news" in prompt_text.lower():
            json_body = '{"sentiment": "positive", "confidence": 0.80, "themes": ["product launch"]}'
        elif "sentiment" in prompt_text.lower():
            json_body = '{"sentiment": "bullish", "confidence": 0.75}'
        elif "industry" in prompt_text.lower():
            json_body = '{"outlook": "bullish", "confidence": 0.78}'
        elif "options" in prompt_text.lower():
            json_body = '{"put_call_ratio": 0.7, "sentiment": "bullish", "confidence": 0.72}'
        elif "risk" in prompt_text.lower():
            json_body = '{"risk_rating": "medium", "confidence": 0.70}'
        elif "valuation" in prompt_text.lower():
            json_body = '{"verdict": "buy", "confidence": 0.85, "upside_pct": 0.22}'
        else:
            json_body = '{"summary": "Bullish research complete", "confidence": 0.80}'

        return LLMResponse(
            content=f"```json\n{json_body}\n```",
            model="mock-model",
            input_tokens=100,
            output_tokens=200,
            cost_estimate=0.01,
            raw_response={},
        )


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------

class TestBullishDecisionIntegration:
    """Phase 14 integration: app produces bullish decision outputs correctly."""

    def test_app_result_has_bullish_decision_fields(self):
        """App result includes thesis, instrument_recommendation, and decision_card."""
        from agent.research_v1.app import HermesResearchApp

        app = HermesResearchApp(llm_client=_Phase14MockClient())
        result = app.run("Research AAPL")

        assert len(result.ticker_results) == 1
        tr = result.ticker_results[0]

        # Phase 14 fields must be present
        assert tr.thesis is not None, "thesis field must be populated"
        assert tr.instrument_recommendation is not None, "instrument_recommendation field must be populated"
        assert tr.decision_card is not None, "decision_card field must be populated"

    def test_decision_card_primary_action_is_valid_bullish(self):
        """Primary action is always one of the VALID_BULLISH_ACTIONS."""
        from agent.research_v1.app import HermesResearchApp

        app = HermesResearchApp(llm_client=_Phase14MockClient())
        result = app.run("Research AAPL")

        tr = result.ticker_results[0]
        assert tr.decision_card.primary_action in VALID_BULLISH_ACTIONS, (
            f"Got invalid action: {tr.decision_card.primary_action!r}"
        )

    def test_app_never_emits_bearish_primary_actions(self):
        """Primary action is never bearish (Short Stock, Buy Put, Long Put)."""
        from agent.research_v1.app import HermesResearchApp

        app = HermesResearchApp(llm_client=_Phase14MockClient())
        result = app.run("Research AAPL")

        tr = result.ticker_results[0]
        bearish_actions = {"Short Stock", "Buy Put", "Long Put"}
        assert tr.decision_card.primary_action not in bearish_actions, (
            f"Bearish action leaked into primary output: {tr.decision_card.primary_action!r}"
        )

    def test_thesis_has_valid_classification(self):
        """Thesis classification is always Investable, Watchlist, or No Trade."""
        from agent.research_v1.app import HermesResearchApp

        app = HermesResearchApp(llm_client=_Phase14MockClient())
        result = app.run("Research AAPL")

        tr = result.ticker_results[0]
        assert tr.thesis.classification in {"Investable", "Watchlist", "No Trade"}

    def test_decision_card_has_buy_stock_as_available_option(self):
        """Buy Stock is a first-class answer in the bullish action space."""
        from agent.research_v1.app import HermesResearchApp

        app = HermesResearchApp(llm_client=_Phase14MockClient())
        result = app.run("Research AAPL")

        tr = result.ticker_results[0]
        # Buy Stock must be in VALID_BULLISH_ACTIONS
        assert "Buy Stock" in VALID_BULLISH_ACTIONS

    def test_decision_card_lists_rejected_alternatives(self):
        """PositionDecisionCard.alternatives lists other instruments that were considered."""
        from agent.research_v1.app import HermesResearchApp

        app = HermesResearchApp(llm_client=_Phase14MockClient())
        result = app.run("Research AAPL")

        tr = result.ticker_results[0]
        # When instrument is selected (not No Trade), alternatives should be a list
        if tr.decision_card.primary_action not in {"No Trade", "Watchlist"}:
            assert isinstance(tr.decision_card.alternatives, list)

    def test_instrument_recommendation_has_reason(self):
        """InstrumentRecommendation.reason explains why this instrument was chosen."""
        from agent.research_v1.app import HermesResearchApp

        app = HermesResearchApp(llm_client=_Phase14MockClient())
        result = app.run("Research AAPL")

        tr = result.ticker_results[0]
        assert tr.instrument_recommendation.reason != ""
        assert len(tr.instrument_recommendation.reason) > 10

    def test_multi_ticker_has_bullish_decision_per_ticker(self):
        """Multi-ticker research produces bullish decision fields for each ticker."""
        from agent.research_v1.app import HermesResearchApp

        app = HermesResearchApp(llm_client=_Phase14MockClient())
        result = app.run("Compare AAPL and MSFT")

        assert len(result.ticker_results) == 2
        for tr in result.ticker_results:
            assert tr.thesis is not None
            assert tr.instrument_recommendation is not None
            assert tr.decision_card is not None
            assert tr.decision_card.primary_action in VALID_BULLISH_ACTIONS


class TestBuyStockIsFirstClassAnswer:
    """Buy Stock is a formal, first-class candidate answer — not a fallback."""

    def test_buy_stock_is_in_valid_actions(self):
        """Buy Stock is explicitly in VALID_BULLISH_ACTIONS."""
        assert "Buy Stock" in VALID_BULLISH_ACTIONS

    def test_instrument_selector_can_choose_buy_stock(self):
        """InstrumentSelectionEngine can return Buy Stock as primary action."""
        from agent.research_v1.instrument_selection import InstrumentSelectionEngine
        from agent.research_v1.contracts import UnderlyingThesis

        selector = InstrumentSelectionEngine()
        thesis = UnderlyingThesis(
            task_id="t1",
            ticker="AAPL",
            quality_score=0.9,
            valuation_score=0.25,
            catalyst_score=0.8,
            thesis_risk_score=0.15,
            classification="Investable",
            summary="Strong thesis",
        )
        # High IV → prefers Buy Stock
        rec = selector.choose(
            thesis,
            {"iv_percentile": 0.92, "liquidity_ok": True},
            {"has_stock": False},
        )
        assert rec.primary_action == "Buy Stock"

    def test_buy_stock_appears_in_alternatives_when_options_selected(self):
        """When Buy Call is chosen, Buy Stock should appear in alternatives."""
        from agent.research_v1.instrument_selection import InstrumentSelectionEngine
        from agent.research_v1.contracts import UnderlyingThesis

        selector = InstrumentSelectionEngine()
        thesis = UnderlyingThesis(
            task_id="t1",
            ticker="AAPL",
            quality_score=0.88,
            valuation_score=0.22,
            catalyst_score=0.75,
            thesis_risk_score=0.2,
            classification="Investable",
            summary="Strong thesis",
        )
        # Normal IV → Buy Call
        rec = selector.choose(
            thesis,
            {"iv_percentile": 0.45, "liquidity_ok": True},
            {"has_stock": False},
        )
        assert rec.primary_action == "Buy Call"
        assert "Buy Stock" in rec.ranked_alternatives


class TestNoBearishLeakage:
    """Verify the system never emits bearish actions as primary recommendations."""

    def test_no_short_stock_in_any_action(self):
        """Short Stock is not in VALID_BULLISH_ACTIONS."""
        assert "Short Stock" not in VALID_BULLISH_ACTIONS

    def test_no_buy_put_in_any_action(self):
        """Buy Put is not in VALID_BULLISH_ACTIONS."""
        assert "Buy Put" not in VALID_BULLISH_ACTIONS

    def test_no_long_put_in_any_action(self):
        """Long Put is not in VALID_BULLISH_ACTIONS."""
        assert "Long Put" not in VALID_BULLISH_ACTIONS

    def test_position_decision_card_rejects_bearish_primary_action(self):
        """PositionDecisionCard raises ValueError if initialized with a bearish action."""
        with pytest.raises(ValueError) as exc_info:
            PositionDecisionCard(
                task_id="t1",
                ticker="AAPL",
                primary_action="Short Stock",
                conviction="High",
                thesis_summary="Strong business",
                why_now="Test",
                alternatives=[],
            )
        assert "primary_action" in str(exc_info.value).lower()
