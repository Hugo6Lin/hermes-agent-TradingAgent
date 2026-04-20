"""Market-data provider abstraction with validation and fallback rules."""

from abc import ABC, abstractmethod

from agent.research_v1.data.quality import DataQualityValidator
from agent.research_v1.data.yahoo_finance import YahooFinanceHistoricalDataSource


class MarketDataProvider(ABC):
    """Abstract market-data provider."""

    @abstractmethod
    def fetch_history(self, symbol: str, start_date: str, end_date: str) -> list[dict]:
        """Fetch normalized historical price points."""


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


class FallbackMarketDataProvider(MarketDataProvider):
    """Try providers in order until one returns valid and fresh-enough rows."""

    def __init__(self, providers: list[MarketDataProvider], validator: DataQualityValidator):
        self.providers = providers
        self.validator = validator

    def fetch_history(self, symbol: str, start_date: str, end_date: str) -> list[dict]:
        for provider in self.providers:
            rows = provider.fetch_history(symbol, start_date=start_date, end_date=end_date)
            cleaned, _issues = self.validator.validate_price_points(rows)
            is_fresh, _freshness_issue = self.validator.check_freshness(cleaned) if cleaned else (False, None)
            if cleaned and is_fresh:
                return cleaned
        return []
