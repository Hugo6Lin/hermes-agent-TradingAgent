"""Futu OpenD market-data and quote adapter."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable, Iterable


@dataclass(slots=True)
class FutuOpenDConfig:
    """Connection settings for a local Futu OpenD gateway."""

    host: str = "127.0.0.1"
    port: int = 11111
    default_market: str = "US"

    @classmethod
    def from_env(cls) -> "FutuOpenDConfig":
        """Build config from environment variables."""
        return cls(
            host=os.getenv("FUTU_OPEND_HOST", "127.0.0.1"),
            port=int(os.getenv("FUTU_OPEND_PORT", "11111")),
            default_market=os.getenv("FUTU_DEFAULT_MARKET", "US").upper(),
        )


class FutuOpenDError(RuntimeError):
    """Raised when the local Futu OpenD gateway call fails."""


def normalize_futu_code(symbol: str, default_market: str = "US") -> str:
    """Normalize user-facing symbols into Futu market-prefixed codes."""
    cleaned = symbol.strip().upper()
    if "." in cleaned:
        return cleaned
    return f"{default_market.upper()}.{cleaned}"


class FutuQuoteClient:
    """Minimal Futu OpenD quote client for stocks and options."""

    def __init__(
        self,
        config: FutuOpenDConfig | None = None,
        quote_context_factory: Callable[..., object] | None = None,
    ) -> None:
        self.config = config or FutuOpenDConfig.from_env()
        self._quote_context_factory = quote_context_factory

    def _create_quote_context(self):
        if self._quote_context_factory is not None:
            return self._quote_context_factory(host=self.config.host, port=self.config.port)

        from futu import OpenQuoteContext

        return OpenQuoteContext(host=self.config.host, port=self.config.port)

    @staticmethod
    def _ensure_ok(ret_code, payload):
        from futu import RET_OK

        if ret_code != RET_OK:
            raise FutuOpenDError(str(payload))

    def fetch_history(self, symbol: str, start_date: str, end_date: str) -> list[dict]:
        """Fetch normalized daily history through OpenD."""
        code = normalize_futu_code(symbol, self.config.default_market)
        quote_ctx = self._create_quote_context()
        try:
            response = quote_ctx.request_history_kline(
                code=code,
                start=start_date,
                end=end_date,
                ktype="K_DAY",
                autype="qfq",
                max_count=1000,
            )
            ret_code, data, *_rest = response
            self._ensure_ok(ret_code, data)

            rows = []
            for day_index, row in enumerate(data.to_dict("records")):
                time_key = str(row.get("time_key", ""))
                date_value = time_key.split(" ", 1)[0] if time_key else row.get("date", "")
                close_value = row.get("close")
                if not date_value or close_value is None:
                    continue
                rows.append({
                    "day": day_index,
                    "date": date_value,
                    "open": float(row["open"]) if row.get("open") is not None else None,
                    "high": float(row["high"]) if row.get("high") is not None else None,
                    "low": float(row["low"]) if row.get("low") is not None else None,
                    "close": float(close_value),
                    "price_adjustment": "adjusted",
                })
            return rows
        finally:
            quote_ctx.close()

    def fetch_snapshot(self, symbols: Iterable[str]) -> list[dict]:
        """Fetch real-time market snapshot for stock or option codes."""
        codes = [normalize_futu_code(symbol, self.config.default_market) for symbol in symbols]
        quote_ctx = self._create_quote_context()
        try:
            ret_code, data = quote_ctx.get_market_snapshot(codes)
            self._ensure_ok(ret_code, data)
            return data.to_dict("records")
        finally:
            quote_ctx.close()

    def fetch_option_chain(
        self,
        symbol: str,
        start: str | None = None,
        end: str | None = None,
        option_type: str = "ALL",
        option_cond_type: str = "ALL",
        data_filter=None,
    ) -> list[dict]:
        """Fetch static option chain rows for an underlying symbol."""
        code = normalize_futu_code(symbol, self.config.default_market)
        quote_ctx = self._create_quote_context()
        try:
            ret_code, data = quote_ctx.get_option_chain(
                code=code,
                start=start,
                end=end,
                option_type=option_type,
                option_cond_type=option_cond_type,
                data_filter=data_filter,
            )
            self._ensure_ok(ret_code, data)
            return data.to_dict("records")
        finally:
            quote_ctx.close()
