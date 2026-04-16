"""Tests for SentimentAnalyst, NewsAnalyst, and IndustryAnalyst."""

import pytest
from unittest.mock import Mock

from agent.research_v1.analysts.sentiment import SentimentAnalyst
from agent.research_v1.analysts.news import NewsAnalyst
from agent.research_v1.analysts.industry import IndustryAnalyst


class MockLLMClient(Mock):
    """Mock LLM client for testing."""

    def generate(self, messages, temperature=0.7, max_tokens=4096):
        """Return a mock LLM response."""
        return Mock(
            content='{"sentiment": "neutral", "confidence": 0.5}',
            model="MiniMax-2.7",
            input_tokens=100,
            output_tokens=200,
            cost_estimate=0.01,
            raw_response={}
        )


def test_sentiment_analyst_initialization():
    analyst = SentimentAnalyst(llm_client=Mock())
    assert analyst.analyst_type == "sentiment"


def test_news_analyst_initialization():
    analyst = NewsAnalyst(llm_client=Mock())
    assert analyst.analyst_type == "news"


def test_industry_analyst_initialization():
    analyst = IndustryAnalyst(llm_client=Mock())
    assert analyst.analyst_type == "industry"


def test_sentiment_analyst_run():
    analyst = SentimentAnalyst(llm_client=MockLLMClient())
    result = analyst.run("AAPL", {}, {}, {})
    assert "report" in result
    assert "summary_json" in result


def test_news_analyst_run():
    analyst = NewsAnalyst(llm_client=MockLLMClient())
    result = analyst.run("AAPL", [{"headline": "Test"}])
    assert "report" in result


def test_industry_analyst_run():
    analyst = IndustryAnalyst(llm_client=MockLLMClient())
    result = analyst.run("AAPL", "technology")
    assert "report" in result