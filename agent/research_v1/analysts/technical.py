"""Technical Analyst - Technical analysis using indicators."""

import json
import re
from typing import Any

from agent.research_v1.llm_clients import BaseLLMClient


def compute_rsi(prices: list[float], period: int = 14) -> float:
    """RSI = 100 - (100 / (1 + RS)) where RS = avg_gain/avg_loss"""
    if len(prices) < 2:
        return 50.0  # Neutral when insufficient data

    # Calculate price changes
    changes = []
    for i in range(1, len(prices)):
        changes.append(prices[i] - prices[i - 1])

    if len(changes) < period:
        # Not enough data for full period RSI
        return 50.0

    # Separate gains and losses
    gains = [c for c in changes[-period:] if c > 0]
    losses = [-c for c in changes[-period:] if c < 0]

    # Calculate average gain and loss
    avg_gain = sum(gains) / period if gains else 0.0
    avg_loss = sum(losses) / period if losses else 0.0

    # Handle edge case where avg_loss is 0
    if avg_loss == 0:
        if avg_gain == 0:
            return 50.0
        return 100.0

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return float(rsi)


def compute_ema(prices: list[float], period: int) -> float:
    """EMA = α × Price + (1-α) × EMA_prev, α = 2/(period+1)"""
    if not prices:
        return 0.0

    if len(prices) == 1:
        return prices[0]

    if period <= 0:
        return prices[-1]

    alpha = 2 / (period + 1)

    # Start with SMA for first EMA value
    sma = sum(prices[:period]) / min(period, len(prices))
    if len(prices) < period:
        return sma

    ema = sma
    for price in prices[period:]:
        ema = alpha * price + (1 - alpha) * ema

    return float(ema)


def compute_macd(prices: list[float], fast: int = 12, slow: int = 26, signal_period: int = 9) -> tuple:
    """Returns (macd_line, signal_line, histogram)"""
    if len(prices) < slow:
        return 0.0, 0.0, 0.0

    # Calculate EMAs
    ema_fast = compute_ema(prices, fast)
    ema_slow = compute_ema(prices, slow)

    # MACD line = Fast EMA - Slow EMA
    macd_line = ema_fast - ema_slow

    # Calculate signal line using MACD values
    # We need to build MACD values over time
    macd_values = []
    for i in range(slow, len(prices) + 1):
        fast_ema = compute_ema(prices[:i], fast)
        slow_ema = compute_ema(prices[:i], slow)
        macd_values.append(fast_ema - slow_ema)

    if len(macd_values) < signal_period:
        signal_line = macd_line
    else:
        # Compute EMA of MACD values for signal line
        signal_line = compute_ema(macd_values, signal_period)

    histogram = macd_line - signal_line

    return float(macd_line), float(signal_line), float(histogram)


def compute_atr(candles: list[dict], period: int = 14) -> float:
    """ATR = Average of True Range over period
    True Range = max(H-L, |H-PC|, |L-PC|)"""
    if not candles:
        return 0.0

    true_ranges = []

    for i, candle in enumerate(candles):
        high = candle.get("high", 0)
        low = candle.get("low", 0)

        if i == 0:
            # First candle: TR = High - Low
            tr = high - low
        else:
            prev_close = candles[i - 1].get("close", 0)
            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )

        true_ranges.append(tr)

    if len(true_ranges) < period:
        # Return average of available data
        return sum(true_ranges) / len(true_ranges) if true_ranges else 0.0

    # Return average of True Range over period
    atr = sum(true_ranges[-period:]) / period
    return float(atr)


def compute_bollinger_bands(prices: list[float], period: int = 20, num_std: int = 2) -> tuple:
    """Returns (upper, middle, lower)"""
    if len(prices) < 2:
        # Return same value for all bands if insufficient data
        if prices:
            return prices[0], prices[0], prices[0]
        return 0.0, 0.0, 0.0

    # Calculate SMA (middle band)
    if len(prices) < period:
        middle = sum(prices) / len(prices)
    else:
        middle = sum(prices[-period:]) / period

    # Calculate standard deviation
    variance = sum((p - middle) ** 2 for p in (prices[-period:] if len(prices) >= period else prices)) / len(prices[-period:] if len(prices) >= period else prices)
    std_dev = variance ** 0.5

    upper = middle + (num_std * std_dev)
    lower = middle - (num_std * std_dev)

    return float(upper), float(middle), float(lower)


def compute_sma(prices: list[float], period: int) -> float:
    """Simple moving average"""
    if not prices:
        return 0.0

    if period <= 0:
        return 0.0

    if len(prices) < period:
        # Return average of available prices
        return sum(prices) / len(prices)

    sma = sum(prices[-period:]) / period
    return float(sma)


class TechnicalAnalyst:
    """Technical analysis using price/volume data."""

    analyst_type = "technical"

    def __init__(self, llm_client: BaseLLMClient):
        """Initialize TechnicalAnalyst.

        Args:
            llm_client: LLM client for generating analysis.
        """
        self.llm = llm_client

    def run(self, symbol: str, candles: list[dict]) -> dict:
        """Run technical analysis on candle data.

        Args:
            symbol: Stock ticker symbol.
            candles: List of candle dicts with date, open, high, low, close, volume.

        Returns:
            dict with 'report' (markdown) and 'summary_json' (dict).
        """
        # Extract prices
        prices = [c.get("close", 0) for c in candles]

        # Compute indicators
        indicators = {
            "rsi": compute_rsi(prices, 14),
            "ema_12": compute_ema(prices, 12),
            "ema_26": compute_ema(prices, 26),
            "macd": compute_macd(prices),
            "atr": compute_atr(candles, 14),
            "bollinger_bands": compute_bollinger_bands(prices, 20, 2),
            "sma_20": compute_sma(prices, 20),
            "sma_50": compute_sma(prices, 50) if len(prices) >= 50 else None,
        }

        # Build prompt for LLM
        prompt = self._build_report_prompt(symbol, indicators)

        # Generate LLM response
        response = self.llm.generate(prompt, temperature=0.3, max_tokens=4096)

        # Parse summary
        summary_json = self._parse_json_summary(response.content)

        return {
            "report": response.content,
            "summary_json": summary_json
        }

    def _build_report_prompt(self, symbol: str, indicators: dict) -> list:
        """Build prompt for LLM to generate markdown report.

        Args:
            symbol: Stock ticker symbol.
            indicators: Dictionary of computed technical indicators.

        Returns:
            List of message dicts for LLM.
        """
        macd_line, signal_line, histogram = indicators["macd"]
        bb_upper, bb_middle, bb_lower = indicators["bollinger_bands"]

        prompt_content = f"""You are a technical analyst analyzing {symbol}.

Technical Indicators:
- RSI (14): {indicators['rsi']:.2f}
- EMA (12): {indicators['ema_12']:.2f}
- EMA (26): {indicators['ema_26']:.2f}
- MACD Line: {macd_line:.2f}
- MACD Signal: {signal_line:.2f}
- MACD Histogram: {histogram:.2f}
- ATR (14): {indicators['atr']:.2f}
- Bollinger Bands: Upper={bb_upper:.2f}, Middle={bb_middle:.2f}, Lower={bb_lower:.2f}
- SMA (20): {indicators['sma_20']:.2f}
- SMA (50): {indicators['sma_50'] if indicators['sma_50'] else 'N/A'}

Analyze the technical indicators and provide:
1. Trend interpretation (bullish/bearish/neutral)
2. Key signals from indicators
3. Support and resistance levels from Bollinger Bands
4. Summary with recommendation and confidence score (0-1)

Return your analysis in the following JSON format:
```json
{{
    "trend": "bullish|bearish|neutral",
    "signals": ["signal1", "signal2"],
    "support": "price_level",
    "resistance": "price_level",
    "recommendation": "buy|sell|hold",
    "confidence": 0.XX
}}
```
"""

        return [
            {"role": "system", "content": "You are a professional technical analyst."},
            {"role": "user", "content": prompt_content}
        ]

    def _parse_json_summary(self, text: str) -> dict:
        """Parse JSON summary from LLM response.

        Args:
            text: LLM response text.

        Returns:
            Parsed summary dictionary.
        """
        # Try to find JSON block in the response
        json_match = re.search(
            r'```(?:json)?\s*\n(.*?)\n```',
            text,
            re.DOTALL
        )

        if json_match:
            json_str = json_match.group(1)
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass

        # Try to find raw JSON
        json_patterns = [
            r'\{[^{}]*"trend"[^{}]*\}',
            r'\{[^{}]*"recommendation"[^{}]*\}',
        ]

        for pattern in json_patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass

        # Return default if parsing fails
        return {
            "summary": text[:500] if len(text) > 500 else text,
            "recommendation": "unknown",
            "confidence": 0.0,
            "error": "Failed to parse JSON summary"
        }
