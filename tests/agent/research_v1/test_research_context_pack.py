"""Tests for P47 read-only research context pack."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent.research_v1.research_context_pack import (
    P47_DISCLAIMER,
    P47_SCHEMA_VERSION,
    build_research_context_pack,
    normalize_tickers,
    render_research_context_pack_markdown,
    validate_request_inputs,
    write_research_context_pack,
)


def test_normalize_tickers_deduplicates_and_preserves_order():
    assert normalize_tickers([" aapl ", "MSFT", "AAPL"]) == ["AAPL", "MSFT"]


def test_invalid_ticker_rejected():
    result = validate_request_inputs("2026-05-01", ["AAPL;DROP"], 180, 8, governance_root_is_dir=True)
    assert result["status"] == "blocked_invalid_input"
    assert "invalid_ticker:AAPL;DROP" in result["warnings"]


def test_build_pack_limited_with_missing_ticker_context(tmp_path: Path):
    pack = build_research_context_pack(
        as_of_date="2026-05-01",
        tickers=["AAPL"],
        lookback_days=180,
        max_items_per_ticker=8,
        evidence={
            "system": {"provider_status": "provider_ready"},
            "tickers": {},
        },
    )
    assert pack["status"] == "context_pack_limited"
    assert pack["ticker_contexts"][0]["context_status"] == "context_missing"
    assert "missing_ticker_context:AAPL" in pack["missing_context"]
