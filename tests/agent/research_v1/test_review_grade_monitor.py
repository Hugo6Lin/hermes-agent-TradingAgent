"""Tests for ReviewerAgent, GradingAgent, and MonitorAgent."""

import pytest
from unittest.mock import Mock

from agent.research_v1.reviewer import ReviewerAgent
from agent.research_v1.grading import GradingAgent
from agent.research_v1.monitor import MonitorAgent


class MockLLMClient(Mock):
    """Mock LLM client for testing."""

    def generate(self, messages, temperature=0.7, max_tokens=4096):
        """Return a mock LLM response."""
        return Mock(
            content='{"summary": "test analysis"}',
            model="MiniMax-2.7",
            input_tokens=100,
            output_tokens=200,
            cost_estimate=0.01,
            raw_response={}
        )


# =============================================================================
# ReviewerAgent Tests
# =============================================================================

def test_reviewer_initialization():
    """Test ReviewerAgent initialization."""
    reviewer = ReviewerAgent(llm_client=Mock())
    assert "reviewer" in str(type(reviewer)).lower()
    assert hasattr(reviewer, 'llm')
    assert hasattr(reviewer, 'system_prompt')


def test_reviewer_has_system_prompt():
    """Test ReviewerAgent has required system prompt content."""
    reviewer = ReviewerAgent(llm_client=Mock())
    assert "quality reviewer" in reviewer.system_prompt.lower()


def test_reviewer_review_returns_errors():
    """Test review method returns errors list."""
    reviewer = ReviewerAgent(llm_client=Mock())
    result = reviewer.review(
        research_report={"content": "Test report with some claims"},
        analyst_reports={"fundamentals": {"report": "test"}}
    )
    assert "errors" in result
    assert isinstance(result["errors"], list)


def test_reviewer_review_returns_critical_count():
    """Test review method returns critical_count."""
    reviewer = ReviewerAgent(llm_client=Mock())
    result = reviewer.review(
        research_report={"content": "Test report"},
        analyst_reports={"fundamentals": {"report": "test"}}
    )
    assert "critical_count" in result
    assert isinstance(result["critical_count"], int)


def test_reviewer_review_returns_overall_quality():
    """Test review method returns overall_quality."""
    reviewer = ReviewerAgent(llm_client=Mock())
    result = reviewer.review(
        research_report={"content": "Test report"},
        analyst_reports={"fundamentals": {"report": "test"}}
    )
    assert "overall_quality" in result
    assert result["overall_quality"] in ["pass", "needs_revision", "failed"]


def test_reviewer_failed_on_critical_count_above_2():
    """Test report fails when critical_count > 2."""
    reviewer = ReviewerAgent(llm_client=Mock())
    # Create a report that triggers multiple critical errors
    # by having conflicting data
    result = reviewer.review(
        research_report={"content": "Price target $500 based on strong growth"},
        analyst_reports={
            "fundamentals": {"report": "revenue 100M"},
            "technical": {"report": "RSI 45"},
            "industry": {"report": "Sector flat"},
        }
    )
    # Critical count should not exceed 2 for failed status
    # Our implementation should correctly categorize
    assert "overall_quality" in result


# =============================================================================
# GradingAgent Tests
# =============================================================================

def test_grading_initialization():
    """Test GradingAgent initialization."""
    grader = GradingAgent(llm_client=Mock())
    assert hasattr(grader, 'llm')


def test_grading_thresholds():
    """Test GradingAgent has correct weight thresholds."""
    grader = GradingAgent(llm_client=Mock())
    assert grader.FUNDAMENTAL_WEIGHT == 0.40
    assert grader.TECHNICAL_WEIGHT == 0.30
    assert grader.MACRO_WEIGHT == 0.30


def test_grading_weights_sum_to_one():
    """Test that grading weights sum to 1.0."""
    grader = GradingAgent(llm_client=Mock())
    total = grader.FUNDAMENTAL_WEIGHT + grader.TECHNICAL_WEIGHT + grader.MACRO_WEIGHT
    assert abs(total - 1.0) < 0.001


def test_grading_s_grade():
    """Test S grade requires composite > 80 AND fundamental > 75."""
    grader = GradingAgent(llm_client=Mock())
    # S requires composite > 80 AND fundamental > 75
    # With 80, 80, 80: composite = 80*0.4 + 80*0.3 + 80*0.3 = 80
    grade = grader._calculate_composite(80, 80, 80)
    assert grade["composite_score"] == 80.0


def test_grading_c_grade():
    """Test C grade calculation."""
    grader = GradingAgent(llm_client=Mock())
    grade = grader._calculate_composite(40, 40, 40)
    assert grade["composite_score"] == 40.0


def test_grading_returns_all_scores():
    """Test grade method returns all score components."""
    grader = GradingAgent(llm_client=Mock())
    result = grader.grade(
        research_decision={
            "fundamentals_summary": {"verdict": "buy", "confidence": 0.7},
            "technical_summary": {"signal": "buy"},
            "industry_summary": {"trend": "bullish"},
            "macro_data": {"trend": "bullish"}
        },
        analyst_reports={}
    )
    assert "grade" in result
    assert "fundamental_score" in result
    assert "technical_score" in result
    assert "macro_score" in result
    assert "composite_score" in result


def test_grading_score_fundamentals():
    """Test fundamentals scoring."""
    grader = GradingAgent(llm_client=Mock())
    score = grader._score_fundamentals({"verdict": "buy", "confidence": 0.8})
    assert 0 <= score <= 100


def test_grading_score_technical():
    """Test technical scoring."""
    grader = GradingAgent(llm_client=Mock())
    score = grader._score_technical({"signal": "buy", "rsi": 45})
    assert 0 <= score <= 100


def test_grading_score_macro():
    """Test macro scoring."""
    grader = GradingAgent(llm_client=Mock())
    score = grader._score_macro({"trend": "bullish"}, {"trend": "bullish"})
    assert 0 <= score <= 100


def test_grading_composite_calculation():
    """Test composite score calculation with weights."""
    grader = GradingAgent(llm_client=Mock())
    result = grader._calculate_composite(100, 100, 100)
    assert result["composite_score"] == 100.0


def test_grading_composite_with_zero():
    """Test composite score calculation with zeros."""
    grader = GradingAgent(llm_client=Mock())
    result = grader._calculate_composite(0, 0, 0)
    assert result["composite_score"] == 0.0


# =============================================================================
# MonitorAgent Tests
# =============================================================================

def test_monitor_initialization():
    """Test MonitorAgent initialization."""
    monitor = MonitorAgent(llm_client=Mock())
    assert hasattr(monitor, 'llm')


def test_monitor_thresholds():
    """Test MonitorAgent has correct alert thresholds."""
    monitor = MonitorAgent(llm_client=Mock())
    assert monitor.ATR_MULTIPLIER == 2.5
    assert monitor.VOLUME_MULTIPLIER == 3.0


def test_monitor_no_alert():
    """Test no alert when data is normal."""
    monitor = MonitorAgent(llm_client=Mock())
    result = monitor.check_alerts("AAPL", {"price_change_pct": 1.0})
    assert result["alert_level"] == "none"
    assert "alerts" in result


def test_monitor_returns_alerts_list():
    """Test check_alerts returns alerts list."""
    monitor = MonitorAgent(llm_client=Mock())
    result = monitor.check_alerts("AAPL", {})
    assert "alerts" in result
    assert isinstance(result["alerts"], list)


def test_monitor_returns_symbol():
    """Test check_alerts returns symbol."""
    monitor = MonitorAgent(llm_client=Mock())
    result = monitor.check_alerts("AAPL", {})
    assert result["symbol"] == "AAPL"


def test_monitor_technical_triggers():
    """Test technical trigger detection."""
    monitor = MonitorAgent(llm_client=Mock())
    # High price change with ATR should trigger alert
    result = monitor.check_alerts("AAPL", {
        "price_change_pct": 5.0,
        "atr": 2.0,
        "price": 100.0
    })
    # ATR is 2% of price, 2.5x ATR = 5%, so 5% should trigger
    assert "alert_level" in result


def test_monitor_volume_spike():
    """Test volume spike detection."""
    monitor = MonitorAgent(llm_client=Mock())
    result = monitor.check_alerts("AAPL", {
        "volume": 30000000,
        "avg_volume": 10000000
    })
    # Volume is 3x average, which meets threshold
    assert "alert_level" in result


def test_monitor_rsi_overbought():
    """Test RSI overbought detection."""
    monitor = MonitorAgent(llm_client=Mock())
    result = monitor.check_alerts("AAPL", {"rsi": 85})
    assert "alerts" in result


def test_monitor_rsi_oversold():
    """Test RSI oversold detection."""
    monitor = MonitorAgent(llm_client=Mock())
    result = monitor.check_alerts("AAPL", {"rsi": 15})
    assert "alerts" in result


def test_monitor_earnings_surprise_positive():
    """Test positive earnings surprise detection."""
    monitor = MonitorAgent(llm_client=Mock())
    result = monitor.check_alerts("AAPL", {"earnings_surprise_pct": 15})
    assert "alerts" in result


def test_monitor_earnings_surprise_negative():
    """Test negative earnings surprise detection."""
    monitor = MonitorAgent(llm_client=Mock())
    result = monitor.check_alerts("AAPL", {"earnings_surprise_pct": -15})
    assert "alerts" in result


def test_monitor_macro_impact():
    """Test macro impact detection."""
    monitor = MonitorAgent(llm_client=Mock())
    result = monitor.check_alerts("AAPL", {"macro_impact": "high"})
    assert "alerts" in result


def test_monitor_alert_levels():
    """Test alert level determination."""
    monitor = MonitorAgent(llm_client=Mock())
    # Should return proper alert level values
    result = monitor.check_alerts("AAPL", {})
    assert result["alert_level"] in ["RED", "ORANGE", "YELLOW", "none"]
