"""Yahoo Finance historical data adapter."""

from datetime import datetime, timezone

import requests


class YahooFinanceHistoricalDataSource:
    """Minimal Yahoo Finance adapter for normalized historical closes."""

    CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart"

    def _normalize_history(self, rows: list[dict]) -> list[dict]:
        """Normalize raw rows into date/close dictionaries."""
        normalized = []
        for row in rows:
            normalized.append({
                "date": row["Date"],
                "close": row["Close"],
            })
        return sorted(normalized, key=lambda item: item["date"])

    def fetch_history(self, symbol: str, start_date: str, end_date: str) -> list[dict]:
        """Fetch historical close prices from Yahoo chart API."""
        response = requests.get(
            f"{self.CHART_URL}/{symbol}",
            params={
                "symbol": symbol,
                "period1": int(datetime.fromisoformat(start_date).timestamp()),
                "period2": int(datetime.fromisoformat(end_date).timestamp()),
                "interval": "1d",
                "includeAdjustedClose": "true",
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        result = data["chart"]["result"][0]
        timestamps = result.get("timestamp", [])
        closes = result.get("indicators", {}).get("quote", [{}])[0].get("close", [])

        rows = []
        if not timestamps:
            return rows

        base_timestamp = timestamps[0]
        for timestamp, close in zip(timestamps, closes):
            if close is None:
                continue
            rows.append({
                "day": int((timestamp - base_timestamp) / 86400),
                "date": datetime.fromtimestamp(timestamp, timezone.utc).strftime("%Y-%m-%d"),
                "close": close,
            })
        return rows
