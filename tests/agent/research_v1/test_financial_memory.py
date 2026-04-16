"""Tests for FinancialMemoryProvider."""
import tempfile
import os
import pytest

from agent.research_v1.memory.financial_provider import FinancialMemoryProvider


def test_financial_memory_provider_initialization():
    """Test that FinancialMemoryProvider can be initialized."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_memory.db")
        provider = FinancialMemoryProvider(db_path)
        assert provider.name == "financial"


def test_get_tool_schemas():
    """Test that get_tool_schemas returns correct schemas."""
    with tempfile.TemporaryDirectory() as tmpdir:
        provider = FinancialMemoryProvider(os.path.join(tmpdir, "test.db"))
        schemas = provider.get_tool_schemas()
        assert len(schemas) == 4
        tool_names = [s["name"] for s in schemas]
        assert "get_stock_profile" in tool_names
        assert "update_stock_profile" in tool_names
        assert "get_industry_memory" in tool_names
        assert "get_debate_learnings" in tool_names


def test_update_and_get_stock_profile():
    """Test updating and getting stock profile."""
    with tempfile.TemporaryDirectory() as tmpdir:
        provider = FinancialMemoryProvider(os.path.join(tmpdir, "test.db"))
        provider.update_stock_profile("AAPL", grade="A", summary="Strong buy")
        profile = provider.get_stock_profile("AAPL")
        assert profile["symbol"] == "AAPL"


def test_industry_memory():
    """Test getting industry memory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        provider = FinancialMemoryProvider(os.path.join(tmpdir, "test.db"))
        # Should return empty dict initially
        mem = provider.get_industry_memory("technology")
        assert isinstance(mem, dict)


def test_get_debate_learnings():
    """Test getting debate learnings for a symbol."""
    with tempfile.TemporaryDirectory() as tmpdir:
        provider = FinancialMemoryProvider(os.path.join(tmpdir, "test.db"))
        learnings = provider.get_debate_learnings("AAPL")
        assert isinstance(learnings, dict)


def test_handle_tool_call():
    """Test handle_tool_call routes correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        provider = FinancialMemoryProvider(os.path.join(tmpdir, "test.db"))

        # Update a profile first
        provider.update_stock_profile("AAPL", grade="B", summary="Hold")

        # Test get_stock_profile via handle_tool_call
        result = provider.handle_tool_call("get_stock_profile", {"symbol": "AAPL"})
        assert "AAPL" in result

        # Test update_stock_profile via handle_tool_call
        result = provider.handle_tool_call("update_stock_profile", {
            "symbol": "TSLA",
            "grade": "C",
            "summary": "Bearish"
        })
        assert "TSLA" in result


def test_prefetch_returns_empty():
    """Test that prefetch returns empty string by default."""
    with tempfile.TemporaryDirectory() as tmpdir:
        provider = FinancialMemoryProvider(os.path.join(tmpdir, "test.db"))
        result = provider.prefetch("AAPL analysis", session_id="test")
        assert result == ""


def test_system_prompt_block_returns_empty():
    """Test that system_prompt_block returns empty string."""
    with tempfile.TemporaryDirectory() as tmpdir:
        provider = FinancialMemoryProvider(os.path.join(tmpdir, "test.db"))
        result = provider.system_prompt_block()
        assert result == ""