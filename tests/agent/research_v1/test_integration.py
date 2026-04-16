"""Integration tests for the full research pipeline."""

from unittest.mock import Mock
import tempfile
import os

from agent.research_v1.analysts.fundamentals import FundamentalsAnalyst
from agent.research_v1.analysts.technical import TechnicalAnalyst
from agent.research_v1.analysts.sentiment import SentimentAnalyst
from agent.research_v1.analysts.news import NewsAnalyst
from agent.research_v1.analysts.industry import IndustryAnalyst
from agent.research_v1.researchers.bull_researcher import BullResearcher
from agent.research_v1.researchers.bear_researcher import BearResearcher
from agent.research_v1.researchers.research_manager import DebateManager
from agent.research_v1.grading import GradingAgent
from agent.research_v1.reviewer import ReviewerAgent
from agent.research_v1.monitor import MonitorAgent
from agent.research_v1.data.database import ResearchDatabase
from agent.research_v1.llm_clients import LLMResponse


def create_mock_llm_response(content: str) -> Mock:
    """Create a mock LLM client that returns a predictable response."""
    mock = Mock()
    mock.generate.return_value = LLMResponse(
        content=content,
        model="test-model",
        input_tokens=100,
        output_tokens=200,
        cost_estimate=0.01,
        raw_response={}
    )
    return mock


def test_full_pipeline_mock():
    """Test complete pipeline with mocked LLM calls."""

    # Create mock LLM clients
    mock_minimax = create_mock_llm_response(
        "Fundamental analysis complete. P/E=28.5, ROE=55%"
    )

    # Create analysts with mock clients
    fundamentals = FundamentalsAnalyst(
        llm_client=mock_minimax,
        valuation_config={"business_models": {}}
    )

    technical = TechnicalAnalyst(llm_client=mock_minimax)
    sentiment = SentimentAnalyst(llm_client=mock_minimax)
    news = NewsAnalyst(llm_client=mock_minimax)
    industry = IndustryAnalyst(llm_client=mock_minimax)

    # Test each analyst runs
    result = fundamentals.run("AAPL", {"price": 186.5}, {})
    assert "report" in result

    result = technical.run("AAPL", [
        {"date": "2026-04-01", "open": 185, "high": 188, "low": 184, "close": 187, "volume": 50000000}
    ])
    assert "report" in result

    result = sentiment.run("AAPL", {}, {}, {})
    assert "report" in result

    result = news.run("AAPL", [])
    assert "report" in result

    result = industry.run("AAPL", "technology")
    assert "report" in result


def test_debate_pipeline_mock():
    """Test bull/bear debate pipeline."""

    mock_gpt = create_mock_llm_response("Analysis complete.")

    bull = BullResearcher(llm_client=mock_gpt)
    bear = BearResearcher(llm_client=mock_gpt)

    bull_result = bull.run("AAPL", {"fundamentals": {"report": "..."}})
    assert "bull_points" in bull_result

    bear_result = bear.run("AAPL", {"fundamentals": {"report": "..."}})
    assert "bear_points" in bear_result


def test_grading_pipeline_mock():
    """Test grading pipeline."""

    mock_minimax = create_mock_llm_response("Grading complete.")
    grader = GradingAgent(llm_client=mock_minimax)

    # 80 * 0.40 + 75 * 0.30 + 70 * 0.30 = 32 + 22.5 + 21 = 75.5
    grade = grader._calculate_composite(80, 75, 70)
    assert grade["composite_score"] == 75.5


def test_database_integration():
    """Test database operations work together."""

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        db = ResearchDatabase(db_path)
        db.initialize()

        # Create task
        task_id = db.create_task("AAPL", "2026-04-17", "morning")
        assert task_id > 0

        # Save analyst report
        report_id = db.save_analyst_report(
            task_id, "fundamentals", "Report content", "{}", "MiniMax-2.7", 500
        )
        assert report_id > 0

        # Update status
        db.update_task_status(task_id, "completed", grade="A", composite_score=80.0)

        # Verify
        task = db.get_task(task_id)
        assert task["symbol"] == "AAPL"
        assert task["grade"] == "A"


def test_monitor_alert_logic():
    """Test monitor alert detection."""
    mock_minimax = create_mock_llm_response("Alert analysis complete.")
    monitor = MonitorAgent(llm_client=mock_minimax)

    # Normal price movement - no alert
    result = monitor.check_alerts("AAPL", {
        "price": 186.5,
        "price_change_pct": 1.0,
        "atr": 2.0,
        "volume": 50000000,
        "avg_volume": 50000000
    })
    assert result["alert_level"] in ["none", "YELLOW"]

    # Large price move - should trigger alert
    # Price change 8% vs ATR of 2% (atr_pct = 1.07%, threshold = 2.5*1.07 = 2.68%)
    # 8% > 2.68%, so triggers price alert
    result = monitor.check_alerts("AAPL", {
        "price": 186.5,
        "price_change_pct": 8.0,
        "atr": 2.0,
        "volume": 300000000,  # 6x avg volume, triggers volume spike
        "avg_volume": 50000000
    })
    assert result["alert_level"] in ["ORANGE", "RED"]


def test_reviewer_agent():
    """Test reviewer agent quality checks."""
    mock_client = create_mock_llm_response("Review complete.")
    reviewer = ReviewerAgent(llm_client=mock_client)

    research_report = {
        "content": "AAPL is a great company with strong fundamentals."
    }
    analyst_reports = {
        "fundamentals": {
            "report": "AAPL shows strong fundamentals."
        }
    }

    result = reviewer.review(research_report, analyst_reports)
    assert "errors" in result
    assert "overall_quality" in result


def test_researcher_run_methods():
    """Test that researchers return expected keys."""
    mock_client = create_mock_llm_response('{"bull_points": ["Point 1", "Point 2"]}')

    bull = BullResearcher(llm_client=mock_client)
    bear = BearResearcher(llm_client=mock_client)

    bull_result = bull.run("AAPL", {})
    bear_result = bear.run("AAPL", {})

    assert "bull_points" in bull_result or "content" in bull_result
    assert "bear_points" in bear_result or "content" in bear_result


def test_sentiment_analyst_run():
    """Test sentiment analyst with mock data."""
    mock_client = create_mock_llm_response("Sentiment analysis complete.")
    sentiment = SentimentAnalyst(llm_client=mock_client)

    vix_data = {"value": 15.5, "change": -0.5}
    fear_greed_data = {"value": 65, "classification": "Greed"}
    put_call_data = {"ratio": 0.8, "sentiment": "bullish"}

    result = sentiment.run("AAPL", vix_data, fear_greed_data, put_call_data)
    assert "report" in result
    assert "summary_json" in result


def test_industry_analyst_run():
    """Test industry analyst with mock data."""
    mock_client = create_mock_llm_response("Industry analysis complete.")
    industry = IndustryAnalyst(llm_client=mock_client)

    sector_etf_data = {"name": "XLK", "price": 185.0, "change": 1.5}
    competitor_data = [
        {"symbol": "MSFT", "name": "Microsoft", "market_cap": "2.5T", "revenue": "200B"}
    ]

    result = industry.run("AAPL", "technology", sector_etf_data, competitor_data)
    assert "report" in result
    assert "summary_json" in result


def test_news_analyst_run():
    """Test news analyst with mock data."""
    mock_client = create_mock_llm_response("News analysis complete.")
    news = NewsAnalyst(llm_client=mock_client)

    news_items = [
        {"headline": "AAPL launches new product", "source": "Reuters", "sentiment": "positive"},
        {"headline": "AAPL faces scrutiny", "source": "Bloomberg", "sentiment": "negative"}
    ]

    result = news.run("AAPL", news_items)
    assert "report" in result
    assert "summary_json" in result


def test_grading_agent_grade():
    """Test grading agent with sample decision."""
    mock_client = create_mock_llm_response("Grading complete.")
    grader = GradingAgent(llm_client=mock_client)

    research_decision = {
        "fundamentals_summary": {"verdict": "buy", "confidence": 0.8},
        "technical_summary": {"signal": "buy"},
        "industry_summary": {"trend": "bullish"},
        "macro_data": {"trend": "bullish"}
    }

    result = grader.grade(research_decision, {})
    assert "grade" in result
    assert "composite_score" in result


def test_monitor_technical_triggers():
    """Test monitor detects technical triggers correctly."""
    mock_client = create_mock_llm_response("Monitor complete.")
    monitor = MonitorAgent(llm_client=mock_client)

    # RSI overbought
    result = monitor.check_alerts("AAPL", {"rsi": 85})
    assert result["alert_level"] in ["YELLOW", "ORANGE", "RED"]

    # RSI oversold
    result = monitor.check_alerts("AAPL", {"rsi": 15})
    assert result["alert_level"] in ["YELLOW", "ORANGE", "RED"]


def test_debate_manager_integration():
    """Test debate manager orchestrates bull/bear debate."""
    mock_client = create_mock_llm_response("Debate complete.")

    bull = BullResearcher(llm_client=mock_client)
    bear = BearResearcher(llm_client=mock_client)
    manager = DebateManager(llm_client=mock_client, bull_researcher=bull, bear_researcher=bear)

    result = manager.run_debate("AAPL", {"fundamentals": {"report": "Strong fundamentals"}})

    assert "decision" in result
    assert "debate_rounds" in result


def test_technical_analyst_with_full_candles():
    """Test technical analyst with complete candle data."""
    mock_client = create_mock_llm_response('{"trend": "bullish", "recommendation": "buy"}')
    technical = TechnicalAnalyst(llm_client=mock_client)

    candles = [
        {"date": "2026-04-01", "open": 185, "high": 188, "low": 184, "close": 187, "volume": 50000000},
        {"date": "2026-04-02", "open": 187, "high": 190, "low": 186, "close": 189, "volume": 55000000},
        {"date": "2026-04-03", "open": 189, "high": 192, "low": 188, "close": 191, "volume": 60000000},
    ]

    result = technical.run("AAPL", candles)
    assert "report" in result
    assert "summary_json" in result
