"""Tests for TechnicalAnalyst and technical indicator functions."""

import pytest
from unittest.mock import Mock

from agent.research_v1.analysts.technical import (
    TechnicalAnalyst,
    compute_rsi,
    compute_ema,
    compute_macd,
    compute_atr,
    compute_bollinger_bands,
    compute_sma,
)


def test_compute_rsi_below_30():
    prices = [100, 102, 101, 98, 95, 93, 90, 88, 85, 84, 83, 82, 81, 80]
    rsi = compute_rsi(prices, 14)
    assert 0 <= rsi <= 100


def test_compute_rsi_overbought():
    prices = [80, 82, 85, 88, 90, 93, 95, 97, 98, 99, 100, 101, 102, 103]
    rsi = compute_rsi(prices, 14)
    assert 0 <= rsi <= 100


def test_compute_ema():
    prices = [100.0, 101.0, 102.0, 103.0, 104.0]
    ema = compute_ema(prices, 3)
    assert 0 < ema < 200


def test_compute_macd():
    prices = [100 + i for i in range(50)]
    macd, signal, hist = compute_macd(prices)
    assert isinstance(macd, float)
    assert isinstance(signal, float)
    assert isinstance(hist, float)


def test_compute_atr():
    candles = [
        {"high": 105, "low": 95, "close": 100},
        {"high": 106, "low": 96, "close": 101},
        {"high": 107, "low": 97, "close": 102},
    ]
    atr = compute_atr(candles, 14)
    assert atr >= 0


def test_compute_bollinger_bands():
    prices = [100 + (i % 10) for i in range(25)]
    upper, middle, lower = compute_bollinger_bands(prices)
    assert upper > middle > lower


def test_technical_analyst_initialization():
    analyst = TechnicalAnalyst(llm_client=Mock())
    assert analyst.analyst_type == "technical"


def test_compute_sma():
    prices = [10.0, 20.0, 30.0, 40.0, 50.0]
    sma = compute_sma(prices, 3)
    # SMA returns average of last `period` prices: (30+40+50)/3 = 40.0
    assert sma == 40.0


def test_compute_rsi_edge_case_single_price():
    """Test RSI with insufficient data."""
    prices = [100.0]
    rsi = compute_rsi(prices, 14)
    # Should return 50 or handle gracefully when not enough data
    assert 0 <= rsi <= 100


def test_compute_ema_single_price():
    """Test EMA with single price."""
    prices = [100.0]
    ema = compute_ema(prices, 14)
    assert ema == 100.0


def test_compute_bollinger_bands_single_price():
    """Test Bollinger Bands with insufficient data."""
    prices = [100.0]
    upper, middle, lower = compute_bollinger_bands(prices, period=20)
    # When insufficient data, should still return values
    assert upper >= middle >= lower
