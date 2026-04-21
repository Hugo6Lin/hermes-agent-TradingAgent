"""Tests for Futu OpenD provider integration."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from agent.research_v1.data.futu_opend import (
    FutuOpenDConfig,
    FutuQuoteClient,
    normalize_futu_code,
)
from agent.research_v1.data.providers import (
    FallbackMarketDataProvider,
    FutuMarketDataProvider,
    MarketDataProvider,
)
from agent.research_v1.data.quality import DataQualityValidator


class _FakeFrame:
    def __init__(self, rows):
        self._rows = rows

    def to_dict(self, orient: str):
        assert orient == "records"
        return list(self._rows)


class _FakeQuoteContext:
    def __init__(self, history_rows=None, snapshot_rows=None, option_rows=None):
        self.history_rows = history_rows or []
        self.snapshot_rows = snapshot_rows or []
        self.option_rows = option_rows or []
        self.closed = False

    def request_history_kline(self, **kwargs):
        self.history_kwargs = kwargs
        return 0, _FakeFrame(self.history_rows), None

    def get_market_snapshot(self, codes):
        self.snapshot_codes = codes
        return 0, _FakeFrame(self.snapshot_rows)

    def get_option_chain(self, **kwargs):
        self.option_kwargs = kwargs
        return 0, _FakeFrame(self.option_rows)

    def close(self):
        self.closed = True


class _FailingProvider(MarketDataProvider):
    def fetch_history(self, symbol: str, start_date: str, end_date: str) -> list[dict]:
        raise RuntimeError("provider offline")

    def fetch_snapshot(self, symbols: list[str]) -> list[dict]:
        raise RuntimeError("provider offline")

    def fetch_option_chain(
        self,
        symbol: str,
        start: str | None = None,
        end: str | None = None,
    ) -> list[dict]:
        raise RuntimeError("provider offline")


def test_normalize_futu_code_adds_default_us_prefix():
    assert normalize_futu_code("aapl") == "US.AAPL"
    assert normalize_futu_code("HK.00700") == "HK.00700"


def test_futu_quote_client_fetch_history_normalizes_rows_and_closes_context():
    context = _FakeQuoteContext(history_rows=[
        {"time_key": "2026-04-18 09:30:00", "close": 101.5},
        {"time_key": "2026-04-21 09:30:00", "close": 103.0},
    ])
    client = FutuQuoteClient(
        config=FutuOpenDConfig(host="127.0.0.1", port=11111, default_market="US"),
        quote_context_factory=lambda **_: context,
    )

    rows = client.fetch_history("AAPL", "2026-04-18", "2026-04-21")

    assert rows == [
        {"day": 0, "date": "2026-04-18", "close": 101.5},
        {"day": 1, "date": "2026-04-21", "close": 103.0},
    ]
    assert context.history_kwargs["code"] == "US.AAPL"
    assert context.closed is True


def test_futu_quote_client_fetches_snapshot_and_option_chain():
    context = _FakeQuoteContext(
        snapshot_rows=[{"code": "US.AAPL", "last_price": 200.0}],
        option_rows=[{"code": "US.AAPL260117C200000", "strike_price": 200.0}],
    )
    client = FutuQuoteClient(
        config=FutuOpenDConfig(default_market="US"),
        quote_context_factory=lambda **_: context,
    )

    snapshot = client.fetch_snapshot(["AAPL"])
    option_chain = client.fetch_option_chain("AAPL", start="2027-01-01", end="2027-01-31")

    assert snapshot[0]["code"] == "US.AAPL"
    assert context.snapshot_codes == ["US.AAPL"]
    assert option_chain[0]["code"] == "US.AAPL260117C200000"
    assert context.option_kwargs["code"] == "US.AAPL"


def test_fallback_provider_skips_failing_futu_and_uses_secondary_source():
    fresh_date = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    secondary = FutuMarketDataProvider(
        quote_client=FutuQuoteClient(
            config=FutuOpenDConfig(default_market="US"),
            quote_context_factory=lambda **_: _FakeQuoteContext(history_rows=[
                {"time_key": f"{fresh_date} 09:30:00", "close": 120.0},
            ]),
        ),
        validator=DataQualityValidator(max_staleness_days=3),
    )
    provider = FallbackMarketDataProvider(
        providers=[_FailingProvider(), secondary],
        validator=DataQualityValidator(max_staleness_days=3),
    )

    rows = provider.fetch_history("AAPL", "2026-04-01", "2026-04-21")

    assert rows[0]["close"] == 120.0
