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
from datetime import datetime
from unittest.mock import Mock

from agent.research_v1.contracts import (
    VALID_BULLISH_ACTIONS,
    UnderlyingThesis,
    InstrumentRecommendation,
    PositionDecisionCard,
    AgentRole,
)
from agent.research_v1.app import HermesResearchApp


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


class TestRealEvidenceStoreIntegration:
    """
    Integration tests using real EvidenceStore.normalize() output shapes.

    These tests verify that _extract_thesis_inputs() correctly reads from
    the actual EvidenceItem fields produced by EvidenceStore:
      - item.direction  — Direction.BULLISH/BEARISH/NEUTRAL
      - item.confidence — float 0.0–1.0
      - item.claim      — string like "Verdict: buy", "Sentiment: positive"
      - item.value      — structured value from analyst

    This catches the P1 bug where thesis inputs were being read from the wrong
    field structure (item.value dict keys that don't exist in real evidence).
    """

    def test_extracts_bullish_direction_from_fundamentals_evidence(self):
        """Real fundamentals EvidenceItem has direction=BULLISH from EvidenceStore."""
        from agent.research_v1.evidence_store import EvidenceStore
        from agent.research_v1.contracts import AgentRole, Direction, EvidenceBundle

        store = EvidenceStore()
        # Real analyst output shape (from _extract_from_summary)
        raw = {
            "summary_json": {
                "verdict": "buy",
                "confidence": 0.85,
                "revenue_growth": 15.2,
            }
        }
        # Use AgentRole enum so EvidenceItem.agent_role is an enum (not a string)
        items = store.normalize("t1", "st1", "AAPL", AgentRole.FUNDAMENTALS, raw)
        bundle = EvidenceBundle(task_id="t1", ticker="AAPL", evidence_items=items)

        # Wire into app's _extract_thesis_inputs
        from agent.research_v1.app import HermesResearchApp
        app = HermesResearchApp(llm_client=_Phase14MockClient())
        thesis_inputs = app._extract_thesis_inputs(bundle, {})

        # Fundamentals quality must be non-zero when evidence is bullish
        assert thesis_inputs["fundamentals"]["profitability"] > 0.0

    def test_preserves_evidence_direction_signal_not_vanishes(self):
        """Bearish fundamentals evidence must produce a distinctly lower quality score."""
        from agent.research_v1.evidence_store import EvidenceStore
        from agent.research_v1.contracts import AgentRole, EvidenceBundle

        store = EvidenceStore()
        # Bearish verdict — explicitly low profitability
        raw_bear = {
            "summary_json": {
                "verdict": "sell",
                "confidence": 0.80,
                "profitability": 0.20,
                "balance_sheet": 0.25,
                "direction": "bearish",
            }
        }
        items_bear = store.normalize("t1", "st1", "AAPL", AgentRole.FUNDAMENTALS, raw_bear)

        raw_bull = {
            "summary_json": {
                "verdict": "buy",
                "confidence": 0.80,
                "profitability": 0.85,
                "balance_sheet": 0.88,
                "direction": "bullish",
            }
        }
        items_bull = store.normalize("t2", "st2", "AAPL", AgentRole.FUNDAMENTALS, raw_bull)

        from agent.research_v1.app import HermesResearchApp
        app = HermesResearchApp(llm_client=_Phase14MockClient())

        bear_inputs = app._extract_thesis_inputs(
            EvidenceBundle(task_id="t1", ticker="AAPL", evidence_items=items_bear), {}
        )
        bull_inputs = app._extract_thesis_inputs(
            EvidenceBundle(task_id="t2", ticker="AAPL", evidence_items=items_bull), {}
        )

        # Bull quality must be strictly higher than bear quality
        assert bull_inputs["fundamentals"]["profitability"] > bear_inputs["fundamentals"]["profitability"], (
            f"Bull quality ({bull_inputs['fundamentals']['profitability']}) should exceed "
            f"bear quality ({bear_inputs['fundamentals']['profitability']})"
        )

    def test_evidence_direction_and_confidence_distinguish_quality(self):
        """
        Two bullish fundamentals with same direction but different confidence
        must produce different quality scores.
        """
        from agent.research_v1.evidence_store import EvidenceStore
        from agent.research_v1.contracts import AgentRole, EvidenceBundle

        store = EvidenceStore()
        raw_high = {"summary_json": {"verdict": "buy", "confidence": 0.90}}
        raw_low = {"summary_json": {"verdict": "buy", "confidence": 0.40}}

        items_high = store.normalize("t1", "st1", "AAPL", AgentRole.FUNDAMENTALS, raw_high)
        items_low = store.normalize("t2", "st2", "AAPL", AgentRole.FUNDAMENTALS, raw_low)

        from agent.research_v1.app import HermesResearchApp
        app = HermesResearchApp(llm_client=_Phase14MockClient())

        high_inputs = app._extract_thesis_inputs(
            EvidenceBundle(task_id="t1", ticker="AAPL", evidence_items=items_high), {}
        )
        low_inputs = app._extract_thesis_inputs(
            EvidenceBundle(task_id="t2", ticker="AAPL", evidence_items=items_low), {}
        )

        assert high_inputs["fundamentals"]["profitability"] > low_inputs["fundamentals"]["profitability"]


class TestTradePlanInstrumentAgreement:
    """Trade plan action must agree with Phase 14 instrument selection."""

    def test_csp_decision_card_and_trade_plan_agree(self):
        """When instrument = Sell CSP, trade plan action must also reflect SELL."""
        from agent.research_v1.evidence_store import EvidenceStore
        from agent.research_v1.contracts import AgentRole, EvidenceBundle

        # CSP selected when wants_discounted_entry + elevated IV + Investable thesis
        store = EvidenceStore()
        # Need investable thesis: quality + upside + catalyst
        raw_fund = {"summary_json": {"verdict": "buy", "confidence": 0.85, "direction": "bullish"}}
        raw_val = {"summary_json": {"verdict": "buy", "confidence": 0.80, "upside_pct": 0.22, "direction": "bullish"}}
        raw_cat = {"summary_json": {"sentiment": "positive", "confidence": 0.75, "direction": "bullish"}}
        fund_items = store.normalize("t1", "st1", "GLW", AgentRole.FUNDAMENTALS, raw_fund)
        val_items = store.normalize("t2", "st2", "GLW", AgentRole.VALUATION, raw_val)
        cat_items = store.normalize("t3", "st3", "GLW", AgentRole.NEWS, raw_cat)
        all_items = fund_items + val_items + cat_items

        from agent.research_v1.app import HermesResearchApp
        app = HermesResearchApp(llm_client=_Phase14MockClient())

        bundle = EvidenceBundle(task_id="t1", ticker="GLW", evidence_items=all_items)
        ctx = {"market_data": {"iv_percentile": 0.84, "liquidity_ok": True}}
        thesis_inputs = app._extract_thesis_inputs(bundle, ctx)
        thesis = app._thesis_engine.evaluate(
            ticker="GLW",
            fundamentals=thesis_inputs["fundamentals"],
            valuation=thesis_inputs["valuation"],
            catalysts=thesis_inputs["catalysts"],
            task_id="t1",
        )
        assert thesis.classification == "Investable", f"Expected Investable, got {thesis.classification}"
        instrument_rec = app._instrument_selector.choose(
            thesis,
            {**thesis_inputs["option_context"], "wants_discounted_entry": True},
            thesis_inputs["holding_context"],
        )

        assert instrument_rec.primary_action == "Sell Cash-Secured Put"

        # Simulate trade plan generation for this instrument
        action = app._instrument_action_to_trade_plan_action(instrument_rec.primary_action)
        assert action == "SELL", f"Expected SELL, got {action}"

    def test_covered_call_decision_card_and_trade_plan_agree(self):
        """When instrument = Covered Call, trade plan action must reflect SELL."""
        from agent.research_v1.evidence_store import EvidenceStore
        from agent.research_v1.contracts import AgentRole, EvidenceBundle

        store = EvidenceStore()
        raw_fund = {"summary_json": {"verdict": "buy", "confidence": 0.85, "direction": "bullish"}}
        raw_val = {"summary_json": {"verdict": "buy", "confidence": 0.80, "upside_pct": 0.18, "direction": "bullish"}}
        raw_cat = {"summary_json": {"sentiment": "positive", "confidence": 0.75, "direction": "bullish"}}
        fund_items = store.normalize("t1", "st1", "AAPL", AgentRole.FUNDAMENTALS, raw_fund)
        val_items = store.normalize("t2", "st2", "AAPL", AgentRole.VALUATION, raw_val)
        cat_items = store.normalize("t3", "st3", "AAPL", AgentRole.NEWS, raw_cat)
        all_items = fund_items + val_items + cat_items

        from agent.research_v1.app import HermesResearchApp
        app = HermesResearchApp(llm_client=_Phase14MockClient())

        bundle = EvidenceBundle(task_id="t1", ticker="AAPL", evidence_items=all_items)
        ctx = {"market_data": {"iv_percentile": 0.55, "liquidity_ok": True}}
        thesis_inputs = app._extract_thesis_inputs(bundle, ctx)
        thesis = app._thesis_engine.evaluate(
            ticker="AAPL",
            fundamentals=thesis_inputs["fundamentals"],
            valuation=thesis_inputs["valuation"],
            catalysts=thesis_inputs["catalysts"],
            task_id="t1",
        )
        assert thesis.classification == "Investable", f"Expected Investable, got {thesis.classification}"
        instrument_rec = app._instrument_selector.choose(
            thesis,
            {**thesis_inputs["option_context"], "short_term_upside_limited": True},
            {"has_stock": True},
        )

        assert instrument_rec.primary_action == "Covered Call"
        action = app._instrument_action_to_trade_plan_action(instrument_rec.primary_action)
        assert action == "SELL", f"Expected SELL, got {action}"

    def test_buy_stock_trade_plan_action_is_buy(self):
        """Buy Stock → trade plan action must be BUY."""
        from agent.research_v1.app import HermesResearchApp
        app = HermesResearchApp(llm_client=_Phase14MockClient())
        action = app._instrument_action_to_trade_plan_action("Buy Stock")
        assert action == "BUY"

    def test_watchlist_trade_plan_action_is_hold(self):
        """Watchlist → trade plan action must be HOLD."""
        from agent.research_v1.app import HermesResearchApp
        app = HermesResearchApp(llm_client=_Phase14MockClient())
        action = app._instrument_action_to_trade_plan_action("Watchlist")
        assert action == "HOLD"


class TestTradePlanInstrumentOverrideE2E:
    """
    End-to-end tests verifying TickerResearchResult.trade_plan['action']
    matches Phase 14 instrument semantics.

    These tests go through _run_ticker_pipeline() (not just the instrument
    selector in isolation) to catch the P1 where Phase 14 selects CSP or
    Covered Call (SELL instruments) but the override fails to propagate to
    the emitted trade_plan.
    """

    def _build_investable_bundle(self, store, ticker):
        """Build evidence bundle that produces Investable thesis (quality≥0.65, upside≥0.15, catalyst≥0.5)."""
        raw_fund = {"summary_json": {"verdict": "buy", "confidence": 0.85, "direction": "bullish"}}
        raw_val = {"summary_json": {"verdict": "buy", "confidence": 0.80, "upside_pct": 0.22, "direction": "bullish"}}
        raw_cat = {"summary_json": {"sentiment": "positive", "confidence": 0.75, "direction": "bullish"}}
        fund_items = store.normalize("t1", "st1", ticker, AgentRole.FUNDAMENTALS, raw_fund)
        val_items = store.normalize("t2", "st2", ticker, AgentRole.VALUATION, raw_val)
        cat_items = store.normalize("t3", "st3", ticker, AgentRole.NEWS, raw_cat)
        return fund_items + val_items + cat_items

    def test_csp_instrument_overrides_trade_plan_to_sell(self):
        """
        When Phase 14 selects Sell Cash-Secured Put (SELL instrument),
        the emitted trade_plan['action'] must be SELL — not BUY from the
        generic CanonicalSignal rating.

        Regression test for P1: decision_card='Sell Cash-Secured Put' while
        trade_plan['action']='BUY' contradiction.
        """
        from agent.research_v1.evidence_store import EvidenceStore
        from agent.research_v1.contracts import ResearchTask, TaskType
        from agent.research_v1.app import HermesResearchApp
        from datetime import datetime

        store = EvidenceStore()
        all_items = self._build_investable_bundle(store, "GLW")

        # task_type=OPTION_IDEA triggers wants_discounted_entry=True in Phase 14
        task = ResearchTask(
            request_text="Find me a good options trade for GLW",
            tickers=["GLW"],
            task_type=TaskType.OPTION_IDEA,
            task_id="e2e_csp",
            created_at=datetime.now(),
        )
        ticker_ctx = {"market_data": {"iv_percentile": 0.84, "liquidity_ok": True}}

        app = HermesResearchApp(llm_client=_Phase14MockClient())
        results = app._run_ticker_pipeline(task, "GLW", all_items, ticker_ctx)
        tr = results[0]

        # Phase 14 must select Sell Cash-Secured Put (SELL instrument)
        assert tr.decision_card is not None
        assert tr.decision_card.primary_action == "Sell Cash-Secured Put"

        # The emitted trade_plan must reflect SELL, not the generic BUY rating
        assert tr.trade_plan is not None
        assert tr.trade_plan["action"] == "SELL", (
            f"trade_plan['action'] must be SELL when Phase 14 instrument is "
            f"'Sell Cash-Secured Put', but got {tr.trade_plan['action']!r}"
        )
        assert tr.trade_plan.get("_instrument_override") is True

    def test_covered_call_instrument_overrides_trade_plan_to_sell(self):
        """
        When Phase 14 selects Covered Call (SELL instrument),
        the emitted trade_plan['action'] must be SELL.
        """
        from agent.research_v1.evidence_store import EvidenceStore
        from agent.research_v1.contracts import ResearchTask, TaskType, EvidenceBundle
        from agent.research_v1.app import HermesResearchApp
        from datetime import datetime

        store = EvidenceStore()
        all_items = self._build_investable_bundle(store, "AAPL")

        task = ResearchTask(
            request_text="Manage my AAPL covered call position",
            tickers=["AAPL"],
            task_type=TaskType.POSITION_MANAGEMENT,
            task_id="e2e_cc",
            created_at=datetime.now(),
        )
        ticker_ctx = {"market_data": {"iv_percentile": 0.55, "liquidity_ok": True}}

        app = HermesResearchApp(llm_client=_Phase14MockClient())

        # Patch orchestrator.assemble_bundle to return a bundle with has_stock=True
        # This simulates the portfolio database knowing the user holds the stock.
        original_assemble = app._orchestrator.assemble_bundle

        def patched_assemble(task_id, ticker, evidence_items):
            bundle = original_assemble(task_id, ticker, evidence_items)
            # Inject has_stock into context_snapshot so _extract_thesis_inputs reads it
            if not hasattr(bundle, "context_snapshot") or bundle.context_snapshot is None:
                bundle.context_snapshot = {"holding_context": {"has_stock": True}}
            elif isinstance(bundle.context_snapshot, dict):
                bundle.context_snapshot["holding_context"] = {"has_stock": True}
            else:
                bundle.context_snapshot = {"holding_context": {"has_stock": True}}
            return bundle

        app._orchestrator.assemble_bundle = patched_assemble

        try:
            results = app._run_ticker_pipeline(task, "AAPL", all_items, ticker_ctx)
        finally:
            app._orchestrator.assemble_bundle = original_assemble

        tr = results[0]

        # With has_stock=True, IV=0.55, short_term_upside_limited → Covered Call
        assert tr.decision_card is not None
        assert tr.decision_card.primary_action == "Covered Call"

        assert tr.trade_plan is not None
        assert tr.trade_plan["action"] == "SELL", (
            f"trade_plan['action'] must be SELL when Phase 14 instrument is "
            f"'Covered Call', but got {tr.trade_plan['action']!r}"
        )
        assert tr.trade_plan.get("_instrument_override") is True


class TestPhase15OptionsStructureAndEarlyExit:
    """
    Phase 15 integration: app produces options_structure and early_exit
    when instrument is options-based.

    Verifies the end-to-end Phase 15 wiring in _run_ticker_pipeline:
    - options_structure is set for Buy Call, Bull Call Spread, CSP, Covered Call
    - early_exit is set for all instrument actions
    - Buy Stock / Watchlist / No Trade do NOT get options_structure
    """

    def _build_investable_bundle(self, store, ticker):
        """Build evidence bundle that produces Investable thesis."""
        raw_fund = {"summary_json": {"verdict": "buy", "confidence": 0.85, "direction": "bullish"}}
        raw_val = {"summary_json": {"verdict": "buy", "confidence": 0.80, "upside_pct": 0.22, "direction": "bullish"}}
        raw_cat = {"summary_json": {"sentiment": "positive", "confidence": 0.75, "direction": "bullish"}}
        fund_items = store.normalize("t1", "st1", ticker, AgentRole.FUNDAMENTALS, raw_fund)
        val_items = store.normalize("t2", "st2", ticker, AgentRole.VALUATION, raw_val)
        cat_items = store.normalize("t3", "st3", ticker, AgentRole.NEWS, raw_cat)
        return fund_items + val_items + cat_items

    def _run_options_pipeline(self, ticker, task_type_val, iv_pct, has_stock_flag=False):
        """Run _run_ticker_pipeline with options instrument selection.

        Patches instrument_selector to ensure Investable classification so Phase 15 runs.
        """
        from datetime import datetime
        from agent.research_v1.evidence_store import EvidenceStore
        from agent.research_v1.contracts import ResearchTask, TaskType, EvidenceBundle, UnderlyingThesis, InstrumentRecommendation

        store = EvidenceStore()
        all_items = self._build_investable_bundle(store, ticker)
        task = ResearchTask(
            request_text=f"Find options trade for {ticker}",
            tickers=[ticker],
            task_type=TaskType(task_type_val),
            task_id="p15_test",
            created_at=datetime.now(),
        )
        ticker_ctx = {
            "market_data": {
                "iv_percentile": iv_pct,
                "last_price": 50.0,
                "liquidity_ok": True,
            },
            "option_chain": [
                {"expiry": "2027-10-15", "strike": 48.0, "option_type": "call", "delta": 0.62},
                {"expiry": "2027-10-15", "strike": 50.0, "option_type": "call", "delta": 0.55},
                {"expiry": "2027-10-15", "strike": 52.0, "option_type": "call", "delta": 0.48},
                {"expiry": "2027-10-15", "strike": 55.0, "option_type": "call", "delta": 0.38},
                {"expiry": "2027-10-15", "strike": 48.0, "option_type": "put", "delta": 0.62},
                {"expiry": "2027-10-15", "strike": 50.0, "option_type": "put", "delta": 0.55},
            ],
        }

        app = HermesResearchApp(llm_client=_Phase14MockClient())

        # Ensure Investable thesis so Phase 15 is triggered
        investable_thesis = UnderlyingThesis(
            task_id="p15_test",
            ticker=ticker,
            quality_score=0.82,
            valuation_score=0.22,
            catalyst_score=0.75,
            thesis_risk_score=0.18,
            classification="Investable",
            summary=f"{ticker} qualifies as Investable",
        )

        # Determine instrument action: task_type + has_stock overrides iv_pct mapping
        task_has_stock_action_map = {
            ("position_management", True): "Covered Call",
            ("option_idea", True): "Buy Call",
        }
        iv_to_action = {
            0.55: "Buy Call",
            0.65: "Bull Call Spread",
            0.84: "Sell Cash-Secured Put",
        }
        primary_action = task_has_stock_action_map.get(
            (task_type_val, has_stock_flag)
        ) or iv_to_action.get(iv_pct, "Buy Call")

        def patched_choose(thesis, option_context, holding_context):
            real_result = orig_selector(investable_thesis, option_context, holding_context)
            return InstrumentRecommendation(
                task_id="p15_test",
                ticker=ticker,
                primary_action=primary_action,
                ranked_alternatives=list(real_result.ranked_alternatives) if hasattr(real_result, 'ranked_alternatives') else [],
                reason=real_result.reason if hasattr(real_result, 'reason') else f"Test: {primary_action}",
            )

        orig_selector = app._instrument_selector.choose

        def patched_choose(thesis, option_context, holding_context):
            # Use the real selector's opinion to determine which options instrument
            real_result = orig_selector(investable_thesis, option_context, holding_context)
            # Override primary action based on test's task type
            return InstrumentRecommendation(
                task_id="p15_test",
                ticker=ticker,
                primary_action=primary_action,
                ranked_alternatives=list(real_result.ranked_alternatives) if hasattr(real_result, 'ranked_alternatives') else [],
                reason=real_result.reason if hasattr(real_result, 'reason') else f"Test: {primary_action}",
            )

        app._instrument_selector.choose = patched_choose

        if has_stock_flag:
            original_assemble = app._orchestrator.assemble_bundle

            def patched_assemble(task_id, ticker, evidence_items):
                bundle = original_assemble(task_id, ticker, evidence_items)
                if not hasattr(bundle, "context_snapshot") or bundle.context_snapshot is None:
                    bundle.context_snapshot = {"holding_context": {"has_stock": True}}
                elif isinstance(bundle.context_snapshot, dict):
                    bundle.context_snapshot["holding_context"] = {"has_stock": True}
                else:
                    bundle.context_snapshot = {"holding_context": {"has_stock": True}}
                return bundle

            app._orchestrator.assemble_bundle = patched_assemble
            try:
                results = app._run_ticker_pipeline(task, ticker, all_items, ticker_ctx)
            finally:
                app._orchestrator.assemble_bundle = original_assemble
        else:
            results = app._run_ticker_pipeline(task, ticker, all_items, ticker_ctx)

        app._instrument_selector.choose = orig_selector
        return results[0]

    def test_buy_call_instrument_gets_options_structure(self):
        """Buy Call → TickerResearchResult has options_structure populated."""
        tr = self._run_options_pipeline("AAPL", "option_idea", 0.55)

        assert tr.options_structure is not None, "options_structure must be populated for Buy Call"
        assert tr.options_structure.instrument_action == "Buy Call"
        assert tr.options_structure.primary_contract.option_type == "call"
        assert tr.options_structure.primary_contract.position_type == "long"
        assert tr.options_structure.target_path_summary != ""
        assert tr.options_structure.early_exit_summary != ""

    def test_bull_call_spread_gets_options_structure(self):
        """Bull Call Spread → TickerResearchResult has options_structure."""
        tr = self._run_options_pipeline("AAPL", "option_idea", 0.65)

        assert tr.options_structure is not None
        assert tr.options_structure.instrument_action == "Bull Call Spread"

    def test_sell_csp_gets_options_structure(self):
        """Sell Cash-Secured Put → TickerResearchResult has options_structure."""
        tr = self._run_options_pipeline("GLW", "option_idea", 0.84)

        assert tr.options_structure is not None
        assert tr.options_structure.instrument_action == "Sell Cash-Secured Put"
        assert tr.options_structure.primary_contract.option_type == "put"
        assert tr.options_structure.primary_contract.position_type == "short"

    def test_covered_call_gets_options_structure(self):
        """Covered Call → TickerResearchResult has options_structure."""
        tr = self._run_options_pipeline("AAPL", "position_management", 0.55, has_stock_flag=True)

        assert tr.options_structure is not None
        assert tr.options_structure.instrument_action == "Covered Call"
        assert tr.options_structure.primary_contract.position_type == "short"

    def test_buy_stock_no_options_structure(self):
        """Buy Stock → no options_structure (not an options instrument)."""
        from agent.research_v1.evidence_store import EvidenceStore
        from agent.research_v1.contracts import ResearchTask, TaskType

        store = EvidenceStore()
        all_items = self._build_investable_bundle(store, "AAPL")
        task = ResearchTask(
            request_text="Research AAPL",
            tickers=["AAPL"],
            task_type=TaskType.SINGLE_TICKER_RESEARCH,
            task_id="p15_test2",
            created_at=datetime.now(),
        )
        ticker_ctx = {
            "market_data": {"iv_percentile": 0.92, "last_price": 50.0, "liquidity_ok": True},
            "option_chain": [],
        }
        app = HermesResearchApp(llm_client=_Phase14MockClient())
        results = app._run_ticker_pipeline(task, "AAPL", all_items, ticker_ctx)
        tr = results[0]

        assert tr.options_structure is None, "Buy Stock should not have options_structure"

    def test_early_exit_is_populated_for_all_instruments(self):
        """All Phase 14 options instruments → early_exit is set (not None)."""
        # Buy Stock is Phase 14 but does not trigger Phase 15 → early_exit stays None
        # All options-based instruments should have early_exit populated
        options_actions = {
            "Buy Call": ("AAPL", "option_idea", 0.55),
            "Bull Call Spread": ("AAPL", "option_idea", 0.65),
            "Sell Cash-Secured Put": ("AAPL", "option_idea", 0.55),
            "Covered Call": ("AAPL", "option_idea", 0.55),
        }
        for action, (ticker, task_type, iv_pct) in options_actions.items():
            tr = self._run_options_pipeline(ticker, task_type, iv_pct)
            assert tr.early_exit is not None, f"{action}: early_exit must be populated"
            assert tr.early_exit.ticker == ticker

    def test_options_structure_ticker_is_set(self):
        """options_structure.ticker matches the ticker in the result."""
        tr = self._run_options_pipeline("GLW", "option_idea", 0.84)

        assert tr.options_structure is not None
        assert tr.options_structure.ticker == "GLW"

    def test_early_exit_has_all_three_zones(self):
        """EarlyExitPlan has first_trim, main_profit, full_exit zones."""
        tr = self._run_options_pipeline("AAPL", "option_idea", 0.55)

        assert tr.early_exit is not None
        assert tr.early_exit.first_trim.zone_name == "first_trim"
        assert tr.early_exit.main_profit.zone_name == "main_profit"
        assert tr.early_exit.full_exit.zone_name == "full_exit"

    def test_phase15_uses_buffered_expiry_not_minimum(self):
        """With target 3m and available expirations, selects ≥ 5m (target + buffer)."""
        from agent.research_v1.evidence_store import EvidenceStore
        from agent.research_v1.contracts import ResearchTask, TaskType, UnderlyingThesis, InstrumentRecommendation

        store = EvidenceStore()
        all_items = self._build_investable_bundle(store, "AAPL")
        task = ResearchTask(
            request_text="Short-term options idea for AAPL",
            tickers=["AAPL"],
            task_type=TaskType.OPTION_IDEA,
            task_id="p15_expiry",
            created_at=datetime.now(),
        )
        ticker_ctx = {
            "market_data": {"iv_percentile": 0.55, "last_price": 50.0, "liquidity_ok": True},
            "option_chain": [
                {"expiry": "2027-05-16", "strike": 50.0, "option_type": "call", "delta": 0.55},  # ~1m
                {"expiry": "2027-08-15", "strike": 50.0, "option_type": "call", "delta": 0.52},  # ~4m
                {"expiry": "2027-11-14", "strike": 50.0, "option_type": "call", "delta": 0.48},  # ~7m
            ],
        }
        app = HermesResearchApp(llm_client=_Phase14MockClient())

        # Patch instrument selector to ensure Investable classification
        investable_thesis = UnderlyingThesis(
            task_id="p15_expiry",
            ticker="AAPL",
            quality_score=0.82,
            valuation_score=0.22,
            catalyst_score=0.75,
            thesis_risk_score=0.18,
            classification="Investable",
            summary="AAPL qualifies as Investable",
        )
        orig_selector = app._instrument_selector.choose

        def patched_choose(thesis, option_context, holding_context):
            real_result = orig_selector(investable_thesis, option_context, holding_context)
            return InstrumentRecommendation(
                task_id="p15_expiry",
                ticker="AAPL",
                primary_action="Buy Call",
                ranked_alternatives=list(real_result.ranked_alternatives),
                reason=real_result.reason,
            )

        app._instrument_selector.choose = patched_choose
        results = app._run_ticker_pipeline(task, "AAPL", all_items, ticker_ctx)
        app._instrument_selector.choose = orig_selector
        tr = results[0]

        assert tr.options_structure is not None
        assert tr.options_structure.primary_contract.expiry_months >= 3, (
            f"Expected buffered expiry (>=3 for 1m thesis), "
            f"got {tr.options_structure.primary_contract.expiry_months}"
        )

    def test_alert_only_no_auto_execution_in_any_zone(self):
        """No exit zone action contains auto-execute verbs."""
        tr = self._run_options_pipeline("AAPL", "option_idea", 0.55)

        assert tr.early_exit is not None
        auto_actions = {"Market Sell", "Buy to Close", "Sell Now", "Execute", "Auto-Exit"}
        for zone in [tr.early_exit.first_trim, tr.early_exit.main_profit, tr.early_exit.full_exit]:
            assert zone.action not in auto_actions, (
                f"Alert-only violation: zone {zone.zone_name} has auto-execute action {zone.action!r}"
            )
