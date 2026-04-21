"""Market-data provider abstraction with validation and fallback rules."""

from __future__ import annotations

from abc import ABC, abstractmethod

from agent.research_v1.data.quality import DataQualityValidator
from agent.research_v1.data.futu_opend import FutuQuoteClient
from agent.research_v1.data.yahoo_finance import YahooFinanceHistoricalDataSource


class MarketDataProvider(ABC):
    """Abstract market-data provider."""

    @abstractmethod
    def fetch_history(self, symbol: str, start_date: str, end_date: str) -> list[dict]:
        """Fetch normalized historical price points."""

    @abstractmethod
    def fetch_snapshot(self, symbols: list[str]) -> list[dict]:
        """Fetch real-time market snapshot for stock or option codes.

        Args:
            symbols: List of symbols (e.g. ["AAPL", "HK.00700"]).

        Returns:
            List of snapshot dicts with at least code, last_price, and open_price fields.
        """

    @abstractmethod
    def fetch_option_chain(
        self,
        symbol: str,
        start: str | None = None,
        end: str | None = None,
    ) -> list[dict]:
        """Fetch option chain rows for an underlying symbol.

        Args:
            symbol: Underlying ticker symbol.
            start: Option expiry start date (YYYY-MM-DD).
            end: Option expiry end date (YYYY-MM-DD).

        Returns:
            List of option row dicts with strike, expiration, call/put fields.
        """


class YahooMarketDataProvider(MarketDataProvider):
    """Yahoo-backed provider normalized through the quality validator."""

    def __init__(
        self,
        data_source: YahooFinanceHistoricalDataSource | None = None,
        validator: DataQualityValidator | None = None,
    ):
        self.data_source = data_source or YahooFinanceHistoricalDataSource()
        self.validator = validator or DataQualityValidator()

    def fetch_history(self, symbol: str, start_date: str, end_date: str) -> list[dict]:
        rows = self.data_source.fetch_history(symbol, start_date=start_date, end_date=end_date)
        cleaned, _issues = self.validator.validate_price_points(rows)
        return cleaned

    def fetch_snapshot(self, symbols: list[str]) -> list[dict]:
        raise NotImplementedError("YahooMarketDataProvider does not support snapshots")

    def fetch_option_chain(
        self,
        symbol: str,
        start: str | None = None,
        end: str | None = None,
    ) -> list[dict]:
        raise NotImplementedError("YahooMarketDataProvider does not support option chains")


class FutuMarketDataProvider(MarketDataProvider):
    """Futu OpenD-backed provider normalized through the quality validator."""

    def __init__(
        self,
        quote_client: FutuQuoteClient | None = None,
        validator: DataQualityValidator | None = None,
    ):
        self.quote_client = quote_client or FutuQuoteClient()
        self.validator = validator or DataQualityValidator()

    def fetch_history(self, symbol: str, start_date: str, end_date: str) -> list[dict]:
        rows = self.quote_client.fetch_history(symbol, start_date=start_date, end_date=end_date)
        cleaned, _issues = self.validator.validate_price_points(rows)
        return cleaned

    def fetch_snapshot(self, symbols: list[str]) -> list[dict]:
        return self.quote_client.fetch_snapshot(symbols)

    def fetch_option_chain(
        self,
        symbol: str,
        start: str | None = None,
        end: str | None = None,
    ) -> list[dict]:
        return self.quote_client.fetch_option_chain(symbol, start=start, end=end)


class AkShareMarketDataProvider(MarketDataProvider):
    """Optional AkShare provider for A-share contexts."""

    def fetch_history(self, symbol: str, start_date: str, end_date: str) -> list[dict]:
        try:
            import akshare as ak
        except Exception as exc:  # pragma: no cover - depends on optional package
            raise RuntimeError("AkShare provider unavailable") from exc

        df = ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start_date.replace("-", ""),
            end_date=end_date.replace("-", ""),
            adjust="qfq",
        )
        rows = []
        base_index = 0
        for index, row in df.reset_index(drop=True).iterrows():
            date_value = row.get("日期")
            close_value = row.get("收盘")
            if date_value is None or close_value is None:
                continue
            if base_index == 0:
                base_index = index
            rows.append({
                "day": index - base_index,
                "date": str(date_value),
                "close": float(close_value),
            })
        return rows

    def fetch_snapshot(self, symbols: list[str]) -> list[dict]:
        raise NotImplementedError("AkShareMarketDataProvider does not support snapshots")

    def fetch_option_chain(
        self,
        symbol: str,
        start: str | None = None,
        end: str | None = None,
    ) -> list[dict]:
        raise NotImplementedError("AkShareMarketDataProvider does not support option chains")


class FallbackMarketDataProvider(MarketDataProvider):
    """Try providers in order until one returns valid and fresh-enough rows."""

    # Fallback reasons from the last fetch_history call (cleared each call)
    _last_fallback_reasons: list[str]

    def __init__(self, providers: list[MarketDataProvider], validator: DataQualityValidator):
        self.providers = providers
        self.validator = validator
        self._last_fallback_reasons = []

    def fetch_history(self, symbol: str, start_date: str, end_date: str) -> list[dict]:
        self._last_fallback_reasons = []
        for provider in self.providers:
            provider_name = provider.__class__.__name__
            try:
                rows = provider.fetch_history(symbol, start_date=start_date, end_date=end_date)
            except Exception as exc:
                self._last_fallback_reasons.append(f"{provider_name}: {exc}")
                continue
            cleaned, _issues = self.validator.validate_price_points(rows)
            is_fresh, _freshness_issue = (
                self.validator.check_freshness(cleaned) if cleaned else (False, None)
            )
            if cleaned and is_fresh:
                return cleaned
            if cleaned and not is_fresh:
                self._last_fallback_reasons.append(
                    f"{provider_name}: data stale ({_freshness_issue})"
                )
        return []

    def fetch_snapshot(self, symbols: list[str]) -> list[dict]:
        self._last_fallback_reasons = []
        for provider in self.providers:
            provider_name = provider.__class__.__name__
            try:
                return provider.fetch_snapshot(symbols)
            except NotImplementedError:
                self._last_fallback_reasons.append(f"{provider_name}: not implemented")
                continue
            except Exception as exc:
                self._last_fallback_reasons.append(f"{provider_name}: {exc}")
                continue
        return []

    def fetch_option_chain(
        self,
        symbol: str,
        start: str | None = None,
        end: str | None = None,
    ) -> list[dict]:
        self._last_fallback_reasons = []
        for provider in self.providers:
            provider_name = provider.__class__.__name__
            try:
                return provider.fetch_option_chain(symbol, start=start, end=end)
            except NotImplementedError:
                self._last_fallback_reasons.append(f"{provider_name}: not implemented")
                continue
            except Exception as exc:
                self._last_fallback_reasons.append(f"{provider_name}: {exc}")
                continue
        return []

    def get_last_fallback_reasons(self) -> list[str]:
        """Return fallback reasons from the last fetch call."""
        return list(self._last_fallback_reasons)


def build_default_market_data_provider(
    validator: DataQualityValidator | None = None,
) -> FallbackMarketDataProvider:
    """Build the default provider chain with Futu first, then Yahoo."""
    active_validator = validator or DataQualityValidator()
    return FallbackMarketDataProvider(
        providers=[
            FutuMarketDataProvider(validator=active_validator),
            YahooMarketDataProvider(validator=active_validator),
        ],
        validator=active_validator,
    )
