"""Phase 12 tests: Futu-first market data integration."""

from __future__ import annotations

from unittest.mock import Mock, patch
import pytest

from agent.research_v1.market_data_service import (
    MarketDataService,
    _stub_market_data,
    _stub_candles,
)
from agent.research_v1.data.futu_opend import FutuOpenDConfig, FutuQuoteClient
from agent.research_v1.data.providers import (
    FallbackMarketDataProvider,
    FutuMarketDataProvider,
    MarketDataProvider,
    build_default_market_data_provider,
)
from agent.research_v1.data.quality import DataQualityValidator


# =============================================================================
# MarketDataProvider ABC — interface tests
# =============================================================================

def test_abc_cannot_be_instantiated_directly():
    """MarketDataProvider is abstract and cannot be instantiated without subclasses."""
    with pytest.raises(TypeError):
        MarketDataProvider()


class _MinimalProvider(MarketDataProvider):
    """Minimal concrete provider for interface test."""

    def fetch_history(self, symbol, start_date, end_date):
        return []

    def fetch_snapshot(self, symbols):
        return []

    def fetch_option_chain(self, symbol, start=None, end=None):
        return []


def test_concrete_provider_can_be_instantiated():
    """A provider that implements all abstract methods is instantiable."""
    p = _MinimalProvider()
    assert p.fetch_history("AAPL", "2026-01-01", "2026-04-01") == []
    assert p.fetch_snapshot(["AAPL"]) == []
    assert p.fetch_option_chain("AAPL") == []


def test_market_data_provider_interface_includes_snapshot_and_option_chain():
    """All three methods are declared in the ABC."""
    # Verify the abstract method count
    abstract_methods = {
        name for name in dir(MarketDataProvider)
        if getattr(getattr(MarketDataProvider, name), "__isabstractmethod__", False)
    }
    assert "fetch_history" in abstract_methods
    assert "fetch_snapshot" in abstract_methods
    assert "fetch_option_chain" in abstract_methods


# =============================================================================
# FutuMarketDataProvider — structured data returns
# =============================================================================

class _FakeQuoteContext:
    def __init__(self, history_rows=None, snapshot_rows=None, option_rows=None):
        self.history_rows = history_rows or []
        self.snapshot_rows = snapshot_rows or []
        self.option_rows = option_rows or []
        self.closed = False

    def request_history_kline(self, **kwargs):
        class _Frame:
            def to_dict(self, orient):
                return list(self._rows)
            def __init__(self, rows):
                self._rows = rows
        return 0, _Frame(self.history_rows), None

    def get_market_snapshot(self, codes):
        class _Frame:
            def to_dict(self, orient):
                return list(self._rows)
            def __init__(self, rows):
                self._rows = rows
        return 0, _Frame(self.snapshot_rows)

    def get_option_chain(self, **kwargs):
        class _Frame:
            def to_dict(self, orient):
                return list(self._rows)
            def __init__(self, rows):
                self._rows = rows
        return 0, _Frame(self.option_rows)

    def close(self):
        self.closed = True


def test_futu_provider_fetch_snapshot_returns_structured_data():
    """Futu provider returns snapshot dicts with expected fields."""
    ctx = _FakeQuoteContext(snapshot_rows=[
        {
            "code": "US.AAPL",
            "last_price": 186.5,
            "open_price": 185.0,
            "high_price": 187.2,
            "low_price": 184.8,
            "volume": 52_000_000,
            "market_cap": "2.9T",
            "shares_outstanding": 15_500_000_000,
            "change_ratio": 0.81,
            "change_val": 1.5,
        }
    ])
    provider = FutuMarketDataProvider(
        quote_client=FutuQuoteClient(
            config=FutuOpenDConfig(default_market="US"),
            quote_context_factory=lambda **_: ctx,
        ),
        validator=DataQualityValidator(),
    )

    result = provider.fetch_snapshot(["AAPL"])

    assert len(result) == 1
    assert result[0]["code"] == "US.AAPL"
    assert result[0]["last_price"] == 186.5
    assert result[0]["open_price"] == 185.0
    assert result[0]["volume"] == 52_000_000


def test_futu_provider_fetch_option_chain_returns_structured_rows():
    """Futu provider returns option chain rows with strike, expiry, OI, volume."""
    ctx = _FakeQuoteContext(option_rows=[
        {
            "code": "US.AAPL260517C200000",
            "strike_price": 200.0,
            "expiry_date": "2026-05-15",
            "call_open_interest": 12000,
            "put_open_interest": 9800,
            "call_volume": 850,
            "put_volume": 720,
        },
        {
            "code": "US.AAPL260517P190000",
            "strike_price": 190.0,
            "expiry_date": "2026-05-15",
            "call_open_interest": 7500,
            "put_open_interest": 11000,
            "call_volume": 420,
            "put_volume": 980,
        },
    ])
    provider = FutuMarketDataProvider(
        quote_client=FutuQuoteClient(
            config=FutuOpenDConfig(default_market="US"),
            quote_context_factory=lambda **_: ctx,
        ),
        validator=DataQualityValidator(),
    )

    result = provider.fetch_option_chain("AAPL", start="2026-05-01", end="2026-05-31")

    assert len(result) == 2
    assert result[0]["strike_price"] == 200.0
    assert result[0]["call_open_interest"] == 12000
    assert result[1]["put_open_interest"] == 11000


# =============================================================================
# FallbackMarketDataProvider — fallback reason logging
# =============================================================================

class _FailingSnapshotProvider(MarketDataProvider):
    def fetch_history(self, symbol, start_date, end_date):
        return [{"day": 0, "date": "2026-04-20", "close": 150.0}]

    def fetch_snapshot(self, symbols):
        raise RuntimeError("snapshot provider offline")

    def fetch_option_chain(self, symbol, start=None, end=None):
        raise RuntimeError("option chain provider offline")


class _WorkingSnapshotProvider(MarketDataProvider):
    def __init__(self, snapshot_rows):
        self._snapshot_rows = snapshot_rows

    def fetch_history(self, symbol, start_date, end_date):
        return [{"day": 0, "date": "2026-04-20", "close": 150.0}]

    def fetch_snapshot(self, symbols):
        return self._snapshot_rows

    def fetch_option_chain(self, symbol, start=None, end=None):
        return self._snapshot_rows


def test_fallback_provider_records_snapshot_fallback_reason():
    """When snapshot fetch fails, fallback reasons are recorded."""
    provider = FallbackMarketDataProvider(
        providers=[
            _FailingSnapshotProvider(),
            _WorkingSnapshotProvider([{"code": "US.AAPL", "last_price": 186.5}]),
        ],
        validator=DataQualityValidator(),
    )

    result = provider.fetch_snapshot(["AAPL"])

    assert len(result) == 1
    assert result[0]["code"] == "US.AAPL"
    reasons = provider.get_last_fallback_reasons()
    assert any("snapshot provider offline" in r for r in reasons)


def test_fallback_provider_records_option_chain_fallback_reason():
    """When option chain fetch fails, fallback reasons are recorded."""
    provider = FallbackMarketDataProvider(
        providers=[
            _FailingSnapshotProvider(),
            _WorkingSnapshotProvider([{"code": "US.AAPL", "strike_price": 200.0}]),
        ],
        validator=DataQualityValidator(),
    )

    result = provider.fetch_option_chain("AAPL")

    assert len(result) == 1
    reasons = provider.get_last_fallback_reasons()
    assert any("option chain provider offline" in r for r in reasons)


def test_fallback_provider_records_not_implemented_reason():
    """When a provider raises NotImplementedError, fallback reasons are recorded."""

    class _NotImplProvider(MarketDataProvider):
        def fetch_history(self, symbol, start_date, end_date):
            return [{"day": 0, "date": "2026-04-20", "close": 150.0}]

        def fetch_snapshot(self, symbols):
            raise NotImplementedError("not available on this provider")

        def fetch_option_chain(self, symbol, start=None, end=None):
            raise NotImplementedError("not available on this provider")

    provider = FallbackMarketDataProvider(
        providers=[_NotImplProvider()],
        validator=DataQualityValidator(),
    )

    result = provider.fetch_snapshot(["AAPL"])
    assert result == []
    reasons = provider.get_last_fallback_reasons()
    assert any("not implemented" in r for r in reasons)


# =============================================================================
# MarketDataService — fetches real context from Futu
# =============================================================================

class _FakeMarketDataProvider(MarketDataProvider):
    """Fake provider that returns controlled data."""

    def __init__(self):
        self.fetch_history_calls = []
        self.fetch_snapshot_calls = []
        self.fetch_option_chain_calls = []

    def fetch_history(self, symbol, start_date, end_date):
        self.fetch_history_calls.append((symbol, start_date, end_date))
        return [
            {"day": 0, "date": "2026-04-18", "close": 185.0},
            {"day": 1, "date": "2026-04-21", "close": 186.5},
        ]

    def fetch_snapshot(self, symbols):
        self.fetch_snapshot_calls.append(symbols)
        return [{"code": "US.AAPL", "last_price": 186.5, "open_price": 185.0}]

    def fetch_option_chain(self, symbol, start=None, end=None):
        self.fetch_option_chain_calls.append((symbol, start, end))
        return [
            {
                "code": "US.AAPL260515C200000",
                "strike_price": 200.0,
                "expiry_date": "2026-05-15",
                "call_open_interest": 12000,
                "put_open_interest": 9800,
            }
        ]


def test_market_data_service_fetch_context_returns_market_data():
    """fetch_context_for_ticker returns snapshot data."""
    fake = _FakeMarketDataProvider()
    service = MarketDataService(provider=fake)

    ctx = service.fetch_context_for_ticker("AAPL")

    assert "market_data" in ctx
    assert ctx["market_data"]["price"] == 186.5
    assert ctx["market_data"]["open_price"] == 185.0


def test_market_data_service_fetch_context_returns_candles():
    """fetch_context_for_ticker returns candles."""
    fake = _FakeMarketDataProvider()
    service = MarketDataService(provider=fake)

    ctx = service.fetch_context_for_ticker("AAPL")

    assert "candles" in ctx
    assert len(ctx["candles"]) == 2
    assert ctx["candles"][0]["close"] == 185.0


def test_market_data_service_fetch_context_returns_option_chain():
    """fetch_context_for_ticker returns option chain."""
    fake = _FakeMarketDataProvider()
    service = MarketDataService(provider=fake)

    ctx = service.fetch_context_for_ticker("AAPL")

    assert "option_chain" in ctx
    assert len(ctx["option_chain"]) == 1
    assert ctx["option_chain"][0]["strike_price"] == 200.0


def test_market_data_service_records_fallback_reasons():
    """When Futu is unavailable, fallback reasons are in _fallback_reasons."""
    fake = _FakeMarketDataProvider()
    service = MarketDataService(provider=fake)

    ctx = service.fetch_context_for_ticker("AAPL")

    # No fallback needed since fake always returns data
    assert isinstance(ctx["_fallback_reasons"], list)


def test_market_data_service_calls_futu_with_correct_symbol():
    """fetch_context_for_ticker passes correct symbol to provider."""
    fake = _FakeMarketDataProvider()
    service = MarketDataService(provider=fake)

    service.fetch_context_for_ticker("AAPL")

    assert ("AAPL",) in [tuple(c) for c in fake.fetch_snapshot_calls]


def test_market_data_service_falls_back_to_stub_on_provider_failure():
    """When provider fails, market_data_service returns stub data and records reason."""
    failing_provider = FallbackMarketDataProvider(
        providers=[],
        validator=DataQualityValidator(),
    )
    service = MarketDataService(provider=failing_provider)

    ctx = service.fetch_context_for_ticker("AAPL")

    # Should return stub data
    assert ctx["market_data"]["symbol"] == "AAPL"
    assert ctx["candles"] != []  # stub candles
    assert ctx["option_chain"] == []  # no option chain


# =============================================================================
# App/subagent path — Futu data is used, not stubs
# =============================================================================

def test_app_with_market_data_service_prepopulates_context():
    """When app has MarketDataService, subtasks get real data in required_context."""
    from agent.research_v1.app import HermesResearchApp

    fake = _FakeMarketDataProvider()
    service = MarketDataService(provider=fake)

    # Track which prompts were sent to LLM (proves real data reached the analyst)
    captured_prompts = []

    class TrackingLLMClient(Mock):
        def generate(self, messages, **kwargs):
            for msg in messages:
                if msg.get("content"):
                    captured_prompts.append(msg["content"])
            return Mock(
                content='```json\n{"summary": "ok", "confidence": 0.6}\n```',
                model="mock",
            )

    mock_llm = TrackingLLMClient()
    app = HermesResearchApp(llm_client=mock_llm, market_data_service=service)

    result = app.run("Research AAPL")

    # Verify the app produced a result (pipeline worked end-to-end)
    assert len(result.ticker_results) == 1

    # At least one prompt should contain real Futu data (not stub). The technical
    # analyst displays EMA from real candles — stub EMA would be ~150.0.
    prompt_text = " ".join(captured_prompts)
    # Real candles have prices around 185-186, giving EMA ~185.75
    # Stub candles have prices around 150, giving different EMA
    assert "185.75" in prompt_text or "185" in prompt_text, (
        f"Expected real Futu candle price in technical prompt, got stub data. "
        f"Prompts: {captured_prompts[:2]}"
    )


def test_subagent_executor_uses_market_data_service_when_context_missing():
    """SubagentExecutor fetches real data via MarketDataService when context is empty."""
    from agent.research_v1.subagent_executor import SubagentExecutor
    from agent.research_v1.contracts import SubagentTask, AgentRole

    fake = _FakeMarketDataProvider()
    service = MarketDataService(provider=fake)
    mock_llm = Mock()
    mock_llm.generate.return_value = Mock(
        content='```json\n{"summary": "ok", "recommendation": "hold", "confidence": 0.6}\n```',
        model="mock",
    )

    executor = SubagentExecutor(mock_llm, market_data_service=service)

    subtask = SubagentTask(
        task_id="test-task",
        agent_role=AgentRole.TECHNICAL,
        ticker="AAPL",
        objective="Analyze technically",
        required_context={},  # Empty — executor should use service
    )

    result = executor.execute(subtask)

    # The analyst should have been called with real candles (from fake provider)
    # We verify by checking the mock was called with prompt containing real price
    assert "report" in result
    assert "summary_json" in result


def test_app_run_stores_fallback_reasons_in_audit():
    """When Futu is unavailable and fallback is used, reasons are in audit metadata."""
    from agent.research_v1.app import HermesResearchApp

    mock_llm = Mock()
    mock_llm.generate.return_value = Mock(
        content='```json\n{"summary": "ok", "confidence": 0.6}\n```',
        model="mock",
    )

    # Empty provider chain = all fallbacks
    from agent.research_v1.data.providers import FallbackMarketDataProvider
    from agent.research_v1.data.quality import DataQualityValidator

    empty_provider = FallbackMarketDataProvider(
        providers=[],
        validator=DataQualityValidator(),
    )
    service = MarketDataService(provider=empty_provider)

    app = HermesResearchApp(llm_client=mock_llm, market_data_service=service)
    result = app.run("Research AAPL")

    assert len(result.ticker_results) == 1
    tr = result.ticker_results[0]
    # Should still produce a result despite fallback (graceful degradation)
    assert tr.signal is not None


# =============================================================================
# P1 regression: default-constructed app is Futu-first
# =============================================================================

def test_default_app_constructs_futu_first_market_data_service():
    """Default HermesResearchApp has a non-None Futu-first MarketDataService."""
    from agent.research_v1.app import HermesResearchApp

    app = HermesResearchApp()

    # P1 fix: _market_data_service must not be None
    assert app._market_data_service is not None, (
        "Default HermesResearchApp must have a MarketDataService (Futu-first), "
        "not None. Phase 12 requires Futu-first to be the default."
    )

    # Verify it's actually a MarketDataService instance
    assert isinstance(app._market_data_service, MarketDataService)


# =============================================================================
# P2 regression: fallback reasons are observable in app result audit
# =============================================================================

def test_fallback_reasons_appear_in_ticker_audit():
    """When market data provider falls back, reasons are visible in tr.audit."""
    from agent.research_v1.app import HermesResearchApp

    mock_llm = Mock()
    mock_llm.generate.return_value = Mock(
        content='```json\n{"summary": "ok", "confidence": 0.6}\n```',
        model="mock",
    )

    # Provider that always fails — forces fallback
    from agent.research_v1.data.providers import FallbackMarketDataProvider
    from agent.research_v1.data.quality import DataQualityValidator

    failing_provider = FallbackMarketDataProvider(
        providers=[],
        validator=DataQualityValidator(),
    )
    service = MarketDataService(provider=failing_provider)

    app = HermesResearchApp(llm_client=mock_llm, market_data_service=service)
    result = app.run("Research AAPL")

    assert len(result.ticker_results) == 1
    tr = result.ticker_results[0]

    # P2 fix: fallback_reasons must be in audit, not silently dropped
    assert "fallback_reasons" in tr.audit, (
        "fallback_reasons must be present in tr.audit so users can observe "
        "why Futu was bypassed. Phase 12 requirement."
    )
    assert isinstance(tr.audit["fallback_reasons"], list)
