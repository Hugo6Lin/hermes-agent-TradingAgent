"""Tests for Bull/Bear Researchers and DebateManager."""

import pytest
from unittest.mock import Mock

from agent.research_v1.researchers.bull_researcher import BullResearcher
from agent.research_v1.researchers.bear_researcher import BearResearcher
from agent.research_v1.researchers.research_manager import DebateManager


class MockLLMClient(Mock):
    """Mock LLM client for testing."""

    def generate(self, messages, temperature=0.7, max_tokens=4096):
        """Return a mock LLM response."""
        return Mock(
            content='{"bull_points": ["Point 1", "Point 2", "Point 3"]}',
            model="MiniMax-2.7",
            input_tokens=100,
            output_tokens=200,
            cost_estimate=0.01,
            raw_response={}
        )


def test_bull_researcher_initialization():
    """Test BullResearcher initialization."""
    bull = BullResearcher(llm_client=Mock())
    assert bull.analyst_type == "bull_researcher"
    assert bull.llm is not None
    assert "Bull Researcher" in bull.system_prompt


def test_bear_researcher_initialization():
    """Test BearResearcher initialization."""
    bear = BearResearcher(llm_client=Mock())
    assert bear.analyst_type == "bear_researcher"
    assert bear.llm is not None
    assert "Bear Researcher" in bear.system_prompt


def test_debate_manager_stalemate_detection():
    """Test stalemate detection in DebateManager."""
    manager = DebateManager(Mock(), BullResearcher(Mock()), BearResearcher(Mock()))

    # No stalemate with < 2 rounds
    assert manager._detect_stalemate([]) == False
    assert manager._detect_stalemate([{"bull": {"content": "a"}, "bear": {"content": "b"}}]) == False

    # Stalemate when content hashes match
    assert manager._detect_stalemate([
        {"bull": {"content": "a"}, "bear": {"content": "b"}},
        {"bull": {"content": "a"}, "bear": {"content": "b"}}
    ]) == True

    # No stalemate when content differs
    assert manager._detect_stalemate([
        {"bull": {"content": "a"}, "bear": {"content": "b"}},
        {"bull": {"content": "c"}, "bear": {"content": "d"}}
    ]) == False


def test_debate_manager_max_rounds():
    """Test DebateManager MAX_ROUNDS constant."""
    manager = DebateManager(Mock(), BullResearcher(Mock()), BearResearcher(Mock()))
    assert manager.MAX_ROUNDS == 3


def test_bull_researcher_run_returns_structure():
    """Test BullResearcher.run returns expected structure."""
    mock_client = MockLLMClient()
    bull = BullResearcher(llm_client=mock_client)

    result = bull.run(symbol="AAPL", analyst_reports={}, debate_history=[])

    assert "bull_points" in result
    assert "content" in result
    assert isinstance(result["bull_points"], list)
    assert isinstance(result["content"], str)


def test_bear_researcher_run_returns_structure():
    """Test BearResearcher.run returns expected structure."""
    mock_client = MockLLMClient()
    bear = BearResearcher(llm_client=mock_client)

    result = bear.run(symbol="AAPL", analyst_reports={}, debate_history=[])

    assert "bear_points" in result
    assert "content" in result
    assert isinstance(result["bear_points"], list)
    assert isinstance(result["content"], str)


def test_debate_manager_run_returns_structure():
    """Test DebateManager.run_debate returns expected structure."""
    mock_client = MockLLMClient()
    bull = BullResearcher(llm_client=mock_client)
    bear = BearResearcher(llm_client=mock_client)
    manager = DebateManager(llm_client=mock_client, bull_researcher=bull, bear_researcher=bear)

    result = manager.run_debate(symbol="AAPL", analyst_reports={})

    assert "decision" in result
    assert "confidence" in result
    assert "key_reasons" in result
    assert "remaining_concerns" in result
    assert "debate_rounds" in result
    assert result["decision"] in ["BUY", "SELL", "HOLD"]
    assert result["confidence"] in ["high", "medium", "low"]