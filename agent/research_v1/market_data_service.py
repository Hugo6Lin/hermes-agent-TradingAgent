"""Market data service — Futu-first context fetcher for SubagentExecutor.

Provides a single entry point for all market data needed by the research pipeline:
snapshot, candles, and option chain. Falls back gracefully with recorded reasons.

Usage::

    service = MarketDataService()
    ctx = service.fetch_context_for_ticker("AAPL")
    # ctx = {
    #     "market_data": {...},   # snapshot fields
    #     "candles": [...],        # 60-day daily candles
    #     "option_chain": [...],    # option chain rows (if available)
    #     "_fallback_reasons": [],  # why Futu was bypassed (if any)
    # }
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from agent.research_v1.data.futu_opend import FutuOpenDConfig, FutuOpenDError
from agent.research_v1.data.providers import (
    FallbackMarketDataProvider,
    FutuMarketDataProvider,
    MarketDataProvider,
    build_default_market_data_provider,
)


class MarketDataService:
    """
    Futu-first market data fetcher that populates required_context for analysts.

    Fetches snapshot, candles, and option chain data. When Futu is unavailable,
    falls back to secondary providers (or stub data) and records the reasons.
    """

    def __init__(
        self,
        provider: MarketDataProvider | None = None,
        default_market: str = "US",
    ):
        """
        Initialize the market data service.

        Args:
            provider: Market data provider chain. Defaults to
                build_default_market_data_provider() (Futu first, then Yahoo).
            default_market: Market prefix when normalizing symbols (US/HK).
        """
        self._provider = provider or build_default_market_data_provider()
        self._default_market = default_market

    def fetch_context_for_ticker(
        self,
        ticker: str,
        history_days: int = 60,
    ) -> dict[str, Any]:
        """
        Fetch all market data needed by SubagentExecutor for one ticker.

        Args:
            ticker: Stock ticker symbol (e.g. "AAPL", "HK.00700").
            history_days: Number of days of historical candles to fetch (default 60).

        Returns:
            Dict with keys:
            - market_data: dict with snapshot fields (price, market_cap, shares, etc.)
            - candles: list of candle dicts (date, open, high, low, close, volume)
            - option_chain: list of option row dicts (strike, expiration, OI, volume)
            - _fallback_reasons: list of str reasons why Futu was bypassed
        """
        fallback_reasons: list[str] = []

        # Snapshot
        market_data, snapshot_reasons = self._fetch_market_data(ticker)
        fallback_reasons.extend(snapshot_reasons)

        # Candles (60 days)
        candles, history_reasons = self._fetch_candles(ticker, history_days)
        fallback_reasons.extend(history_reasons)

        # Option chain
        option_chain, chain_reasons = self._fetch_option_chain(ticker)
        fallback_reasons.extend(chain_reasons)

        return {
            "market_data": market_data,
            "candles": candles,
            "option_chain": option_chain,
            "_fallback_reasons": fallback_reasons,
        }

    def _fetch_market_data(self, ticker: str) -> tuple[dict[str, Any], list[str]]:
        """Fetch snapshot and build market_data dict."""
        reasons: list[str] = []
        snapshots = []
        try:
            snapshots = self._provider.fetch_snapshot([ticker])
        except Exception as exc:
            reasons.append(f"snapshot: {exc}")

        if not snapshots:
            return _stub_market_data(ticker), reasons

        snap = snapshots[0]
        return {
            "symbol": snap.get("code", ticker),
            "price": snap.get("last_price") or snap.get("close_price"),
            "open_price": snap.get("open_price"),
            "high_price": snap.get("high_price"),
            "low_price": snap.get("low_price"),
            "volume": snap.get("volume"),
            "market_cap": str(snap.get("market_cap", "")),
            "shares_outstanding": snap.get("shares_outstanding"),
            "change": snap.get("change_ratio"),
            "change_pct": snap.get("change_val"),
        }, reasons

    def _fetch_candles(
        self,
        ticker: str,
        days: int,
    ) -> tuple[list[dict], list[str]]:
        """Fetch historical daily candles."""
        reasons: list[str] = []
        end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        start_date = (
            datetime.now(timezone.utc) - timedelta(days=days)
        ).strftime("%Y-%m-%d")

        try:
            rows = self._provider.fetch_history(ticker, start_date=start_date, end_date=end_date)
        except Exception as exc:
            reasons.append(f"candles: {exc}")
            return _stub_candles(ticker), reasons

        if not rows:
            reasons.append("candles: empty result")
            return _stub_candles(ticker), reasons

        return rows, reasons

    def _fetch_option_chain(
        self,
        ticker: str,
        start: str | None = None,
        end: str | None = None,
    ) -> tuple[list[dict], list[str]]:
        """Fetch option chain rows."""
        reasons: list[str] = []
        # Default: next 2 months
        if not start:
            start = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if not end:
            end = (datetime.now(timezone.utc) + timedelta(days=60)).strftime("%Y-%m-%d")

        try:
            rows = self._provider.fetch_option_chain(ticker, start=start, end=end)
        except Exception as exc:
            reasons.append(f"option_chain: {exc}")
            return [], reasons

        return rows, reasons


def _stub_market_data(ticker: str) -> dict[str, Any]:
    return {
        "symbol": ticker,
        "price": 150.0,
        "open_price": 149.5,
        "high_price": 152.0,
        "low_price": 148.0,
        "volume": 50_000_000,
        "market_cap": "2.5T",
        "shares_outstanding": 15_000_000_000,
        "change": None,
        "change_pct": None,
    }


def _stub_candles(ticker: str) -> list[dict]:
    """Generate stub candles for offline use."""
    import random

    base_price = 150.0
    candles = []
    today = datetime.now(timezone.utc)
    for i in range(60):
        date = today - timedelta(days=59 - i)
        change = random.uniform(-0.03, 0.04)
        open_price = base_price * (1 + change)
        close_price = open_price * (1 + random.uniform(-0.02, 0.025))
        high_price = max(open_price, close_price) * (1 + random.uniform(0, 0.01))
        low_price = min(open_price, close_price) * (1 - random.uniform(0, 0.01))
        candles.append({
            "date": date.strftime("%Y-%m-%d"),
            "open": round(open_price, 2),
            "high": round(high_price, 2),
            "low": round(low_price, 2),
            "close": round(close_price, 2),
            "volume": int(random.uniform(40_000_000, 80_000_000)),
        })
        base_price = close_price
    return candles
