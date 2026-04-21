"""
Subagent Executor — Wires AgentRole to analyst instances and returns structured output.

This module is the core of Phase 11's real agent wiring. It replaces the no-op
execute_subagent() in HermesResearchApp with real LLM-powered research execution.

The executor is model-agnostic: it accepts any LLM client conforming to the
BaseLLMClient interface and routes each AgentRole to its corresponding analyst.

Responsibilities:
- Instantiate the correct analyst for each AgentRole
- Pass role-appropriate data to each analyst
- Return a structured dict compatible with EvidenceStore.normalize()
- Fetch real market data via MarketDataService when required_context is empty

The executor does NOT:
- Produce final judgment (that's FinalJudge)
- Normalize evidence (that's EvidenceStore)
- Route tasks (that's TaskRouter/Orchestrator)
"""

from __future__ import annotations

from typing import Any

from agent.research_v1.llm_clients import BaseLLMClient
from agent.research_v1.contracts import AgentRole, SubagentTask


class SubagentExecutor:
    """
    Wires AgentRole to analyst instances and returns structured output.

    Accepts any LLM client and routes each role to its corresponding analyst.
    Produces output compatible with EvidenceStore.normalize().
    Uses MarketDataService to fetch real market data when required_context
    is not pre-populated (Phase 12: Futu-first market data).
    """

    # Maps AgentRole → method name on this class
    _ROLE_HANDLERS: dict[AgentRole, str] = {
        AgentRole.FUNDAMENTALS: "_run_fundamentals",
        AgentRole.TECHNICAL: "_run_technical",
        AgentRole.NEWS: "_run_news",
        AgentRole.SENTIMENT: "_run_sentiment",
        AgentRole.INDUSTRY: "_run_industry",
        AgentRole.OPTIONS: "_run_options",
        AgentRole.RISK: "_run_risk",
        AgentRole.VALUATION: "_run_valuation",
    }

    def __init__(
        self,
        llm_client: BaseLLMClient,
        market_data_service: Any = None,
    ):
        """
        Initialize the executor with an LLM client and optional market data service.

        Args:
            llm_client: LLM client for all analyst calls.
            market_data_service: MarketDataService for fetching real market data
                when required_context is not pre-populated. If None, stub data
                is used (legacy behavior for tests without live market data).
        """
        self._llm = llm_client
        self._market_data_service = market_data_service

    def execute(self, subtask: SubagentTask) -> dict[str, Any]:
        """
        Execute a single subtask and return structured output.

        Args:
            subtask: SubagentTask from orchestrator.decompose().

        Returns:
            Dict with 'report' (str) and 'summary_json' (dict) keys,
            compatible with EvidenceStore.normalize().

        Raises:
            ValueError: If the agent_role is not supported.
        """
        handler_name = self._ROLE_HANDLERS.get(subtask.agent_role)
        if handler_name is None:
            raise ValueError(f"Unsupported agent role: {subtask.agent_role}")

        handler = getattr(self, handler_name, None)
        if handler is None:
            raise ValueError(f"No handler for role: {subtask.agent_role}")

        return handler(subtask)

    # -------------------------------------------------------------------------
    # Role-specific handlers
    # -------------------------------------------------------------------------

    def _run_fundamentals(self, subtask: SubagentTask) -> dict[str, Any]:
        """Run fundamentals analyst."""
        from agent.research_v1.analysts.fundamentals import FundamentalsAnalyst

        analyst = FundamentalsAnalyst(
            llm_client=self._llm,
            valuation_config={"business_models": {}},
        )

        ctx = subtask.required_context or {}
        market_data = ctx.get("market_data")
        if not market_data and self._market_data_service:
            market_data = self._fetch_via_service(subtask.ticker, "market_data")
        market_data = market_data or _stub_market_data(subtask.ticker)
        income_data = ctx.get("income_data", {})
        balance_data = ctx.get("balance_data", {})
        cashflow_data = ctx.get("cashflow_data", {})

        return analyst.run(
            symbol=subtask.ticker,
            market_data=market_data,
            income_data=income_data,
            balance_data=balance_data,
            cashflow_data=cashflow_data,
        )

    def _run_technical(self, subtask: SubagentTask) -> dict[str, Any]:
        """Run technical analyst."""
        from agent.research_v1.analysts.technical import TechnicalAnalyst

        analyst = TechnicalAnalyst(llm_client=self._llm)

        ctx = subtask.required_context or {}
        candles = ctx.get("candles")
        if not candles and self._market_data_service:
            candles = self._fetch_via_service(subtask.ticker, "candles")
        candles = candles or _stub_candles(subtask.ticker)

        return analyst.run(symbol=subtask.ticker, candles=candles)

    def _run_news(self, subtask: SubagentTask) -> dict[str, Any]:
        """Run news analyst."""
        from agent.research_v1.analysts.news import NewsAnalyst

        analyst = NewsAnalyst(llm_client=self._llm)

        ctx = subtask.required_context or {}
        news_items = ctx.get("news_items", _stub_news_items(subtask.ticker))
        earnings_data = ctx.get("earnings_data")

        return analyst.run(
            symbol=subtask.ticker,
            news_items=news_items,
            earnings_data=earnings_data,
        )

    def _run_sentiment(self, subtask: SubagentTask) -> dict[str, Any]:
        """Run sentiment analyst."""
        from agent.research_v1.analysts.sentiment import SentimentAnalyst

        analyst = SentimentAnalyst(llm_client=self._llm)

        ctx = subtask.required_context or {}
        vix_data = ctx.get("vix_data", _stub_vix_data())
        fear_greed_data = ctx.get("fear_greed_data", _stub_fear_greed_data())
        put_call_data = ctx.get("put_call_data", _stub_put_call_data())

        return analyst.run(
            symbol=subtask.ticker,
            vix_data=vix_data,
            fear_greed_data=fear_greed_data,
            put_call_data=put_call_data,
        )

    def _run_industry(self, subtask: SubagentTask) -> dict[str, Any]:
        """Run industry analyst."""
        from agent.research_v1.analysts.industry import IndustryAnalyst

        analyst = IndustryAnalyst(llm_client=self._llm)

        ctx = subtask.required_context or {}
        industry = ctx.get("industry", "technology")
        sector_etf_data = ctx.get("sector_etf_data", _stub_sector_etf_data())
        competitor_data = ctx.get("competitor_data", [])

        return analyst.run(
            symbol=subtask.ticker,
            industry=industry,
            sector_etf_data=sector_etf_data,
            competitor_data=competitor_data,
        )

    def _run_options(self, subtask: SubagentTask) -> dict[str, Any]:
        """Run options analyst."""
        from agent.research_v1.analysts.options import OptionsAnalyst

        analyst = OptionsAnalyst(llm_client=self._llm)

        ctx = subtask.required_context or {}
        option_chain = ctx.get("option_chain")
        if not option_chain and self._market_data_service:
            option_chain = self._fetch_via_service(subtask.ticker, "option_chain")
        option_chain = option_chain or _stub_option_chain(subtask.ticker)

        return analyst.run(symbol=subtask.ticker, option_chain=option_chain)

    def _run_risk(self, subtask: SubagentTask) -> dict[str, Any]:
        """Run risk analyst."""
        from agent.research_v1.analysts.risk import RiskAnalyst

        analyst = RiskAnalyst(llm_client=self._llm)

        ctx = subtask.required_context or {}
        market_data = ctx.get("market_data")
        if not market_data and self._market_data_service:
            market_data = self._fetch_via_service(subtask.ticker, "market_data")
        market_data = market_data or _stub_market_data(subtask.ticker)
        positions = ctx.get("positions", [])

        return analyst.run(
            symbol=subtask.ticker,
            market_data=market_data,
            positions=positions,
        )

    def _run_valuation(self, subtask: SubagentTask) -> dict[str, Any]:
        """Run valuation analyst."""
        from agent.research_v1.analysts.valuation import ValuationAnalyst

        analyst = ValuationAnalyst(llm_client=self._llm)

        ctx = subtask.required_context or {}
        market_data = ctx.get("market_data")
        if not market_data and self._market_data_service:
            market_data = self._fetch_via_service(subtask.ticker, "market_data")
        market_data = market_data or _stub_market_data(subtask.ticker)
        income_data = ctx.get("income_data", {})
        balance_data = ctx.get("balance_data", {})
        cashflow_data = ctx.get("cashflow_data", {})

        return analyst.run(
            symbol=subtask.ticker,
            market_data=market_data,
            income_data=income_data,
            balance_data=balance_data,
            cashflow_data=cashflow_data,
        )

    def _fetch_via_service(self, ticker: str, data_key: str) -> Any:
        """Fetch a specific data field via MarketDataService (lazy, per-ticker)."""
        if self._market_data_service is None:
            return None
        ctx = self._market_data_service.fetch_context_for_ticker(ticker)
        return ctx.get(data_key)


# -----------------------------------------------------------------------------
# Stub data generators — used when required_context provides no data.
# These allow the pipeline to run end-to-end without live market data feeds.
# -----------------------------------------------------------------------------

def _stub_market_data(ticker: str) -> dict[str, Any]:
    return {
        "symbol": ticker,
        "price": 150.0,
        "market_cap": "2.5T",
        "shares_outstanding": 15_000_000_000,
    }


def _stub_candles(ticker: str) -> list[dict]:
    """Generate 60 days of stub candle data."""
    import random
    base_price = 150.0
    candles = []
    for i in range(60):
        change = random.uniform(-0.03, 0.04)
        open_price = base_price * (1 + change)
        close_price = open_price * (1 + random.uniform(-0.02, 0.025))
        high_price = max(open_price, close_price) * (1 + random.uniform(0, 0.01))
        low_price = min(open_price, close_price) * (1 - random.uniform(0, 0.01))
        candles.append({
            "date": f"2026-04-{21 - (59 - i):02d}",
            "open": round(open_price, 2),
            "high": round(high_price, 2),
            "low": round(low_price, 2),
            "close": round(close_price, 2),
            "volume": int(random.uniform(40_000_000, 80_000_000)),
        })
        base_price = close_price
    return candles


def _stub_news_items(ticker: str) -> list[dict]:
    return [
        {
            "headline": f"{ticker} reports strong quarterly earnings",
            "source": "Reuters",
            "date": "2026-04-18",
            "sentiment": "positive",
        },
        {
            "headline": f"Analysts upgrade {ticker} price target",
            "source": "Bloomberg",
            "date": "2026-04-17",
            "sentiment": "positive",
        },
        {
            "headline": f"{ticker} announces strategic partnership",
            "source": "CNBC",
            "date": "2026-04-15",
            "sentiment": "neutral",
        },
    ]


def _stub_vix_data() -> dict[str, Any]:
    return {"value": 18.5, "change": -1.2}


def _stub_fear_greed_data() -> dict[str, Any]:
    return {"value": 62, "classification": "Greed"}


def _stub_put_call_data() -> dict[str, Any]:
    return {"ratio": 0.75, "sentiment": "bullish"}


def _stub_sector_etf_data() -> dict[str, Any]:
    return {"name": "XLK", "price": 185.0, "change": 1.5, "volume": 10_000_000}


def _stub_option_chain(ticker: str) -> list[dict]:
    return [
        {
            "expiration": "2026-05-15",
            "strike": 150.0,
            "call_open_interest": 12000,
            "put_open_interest": 9800,
            "call_volume": 850,
            "put_volume": 720,
        },
        {
            "expiration": "2026-05-15",
            "strike": 155.0,
            "call_open_interest": 9800,
            "put_open_interest": 11500,
            "call_volume": 620,
            "put_volume": 890,
        },
    ]
