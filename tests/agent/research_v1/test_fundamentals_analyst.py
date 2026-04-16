"""Tests for FundamentalsAnalyst."""

import pytest
from unittest.mock import Mock

from agent.research_v1.analysts.fundamentals import FundamentalsAnalyst


class MockLLMClient(Mock):
    """Mock LLM client for testing."""

    def generate(self, messages, temperature=0.7, max_tokens=4096):
        """Return a mock LLM response."""
        return Mock(
            content='{"summary": "test", "verdict": "buy", "confidence": 0.7}',
            model="MiniMax-2.7",
            input_tokens=100,
            output_tokens=200,
            cost_estimate=0.01,
            raw_response={}
        )


def test_fundamentals_analyst_initialization():
    """Test FundamentalsAnalyst initialization."""
    analyst = FundamentalsAnalyst(
        llm_client=Mock(),
        valuation_config={"business_models": {}}
    )
    assert analyst.analyst_type == "fundamentals"


def test_detect_business_model():
    """Test neo_bank detection from keywords."""
    analyst = FundamentalsAnalyst(
        llm_client=Mock(),
        valuation_config={
            "business_models": {
                "neo_bank": ["digital bank", "online banking", "fintech"]
            }
        }
    )

    # Test neo bank detection - include fintech keyword in description
    income_data = {
        "revenue": {"total": 1000000},
        "net_income": 100000,
        "description": "A fintech digital bank offering online banking services"
    }
    result = analyst.detect_business_model(income_data, "NEO")
    assert result == "neo_bank"


def test_detect_business_model_default():
    """Test default business model detection."""
    analyst = FundamentalsAnalyst(
        llm_client=Mock(),
        valuation_config={"business_models": {}}
    )

    income_data = {
        "revenue": {"total": 1000000},
        "net_income": 100000
    }
    result = analyst.detect_business_model(income_data, "UNKNOWN")
    assert result == "standard"


def test_calculate_pe():
    """Test PE calculation."""
    analyst = FundamentalsAnalyst(
        llm_client=Mock(),
        valuation_config={}
    )

    market_data = {"price": 50.0}
    income_data = {"eps": 2.5}

    pe = analyst.calculate_pe(market_data, income_data)
    assert pe == 20.0


def test_calculate_pe_negative_eps():
    """Test PE calculation with negative EPS returns None."""
    analyst = FundamentalsAnalyst(
        llm_client=Mock(),
        valuation_config={}
    )

    market_data = {"price": 50.0}
    income_data = {"eps": -2.5}

    pe = analyst.calculate_pe(market_data, income_data)
    assert pe is None


def test_calculate_roe():
    """Test ROE calculation."""
    analyst = FundamentalsAnalyst(
        llm_client=Mock(),
        valuation_config={}
    )

    income_data = {"net_income": 100000}
    balance_data = {"shareholders_equity": 500000}

    roe = analyst.calculate_roe(income_data, balance_data)
    assert roe == 0.2


def test_calculate_roe_zero_equity():
    """Test ROE calculation with zero equity returns None."""
    analyst = FundamentalsAnalyst(
        llm_client=Mock(),
        valuation_config={}
    )

    income_data = {"net_income": 100000}
    balance_data = {"shareholders_equity": 0}

    roe = analyst.calculate_roe(income_data, balance_data)
    assert roe is None


def test_cash_flow_match():
    """Test cash flow match calculation."""
    analyst = FundamentalsAnalyst(
        llm_client=Mock(),
        valuation_config={}
    )

    cashflow_data = {"operating_cash_flow": 80000}
    income_data = {"net_income": 100000}

    match = analyst.calculate_cash_flow_match(cashflow_data, income_data)
    assert match == 0.8


def test_cash_flow_match_low():
    """Test cash flow match below threshold."""
    analyst = FundamentalsAnalyst(
        llm_client=Mock(),
        valuation_config={}
    )

    cashflow_data = {"operating_cash_flow": 50000}
    income_data = {"net_income": 100000}

    match = analyst.calculate_cash_flow_match(cashflow_data, income_data)
    assert match == 0.5


def test_calculate_metrics():
    """Test complete metrics calculation."""
    analyst = FundamentalsAnalyst(
        llm_client=Mock(),
        valuation_config={}
    )

    market_data = {
        "price": 50.0,
        "market_cap": 5000000,
        "book_value_per_share": 10.0
    }
    income_data = {
        "eps": 2.5,
        "net_income": 100000,
        "revenue": {"total": 1000000},
        "ebit": 150000
    }
    balance_data = {
        "shareholders_equity": 500000,
        "total_debt": 200000,
        "cash_and_equivalents": 50000
    }
    cashflow_data = {
        "operating_cash_flow": 80000
    }

    metrics = analyst.calculate_metrics(
        market_data, income_data, balance_data, cashflow_data
    )

    assert metrics["pe"] == 20.0
    assert metrics["roe"] == 0.2
    assert metrics["cash_flow_match"] == 0.8


def test_parse_json_summary():
    """Test JSON summary parsing."""
    analyst = FundamentalsAnalyst(
        llm_client=Mock(),
        valuation_config={}
    )

    text = '''
    Here is the analysis:

    ```json
    {
        "summary": "Company shows strong fundamentals",
        "verdict": "buy",
        "confidence": 0.85
    }
    ```
    '''

    result = analyst._parse_json_summary(text)
    assert result["summary"] == "Company shows strong fundamentals"
    assert result["verdict"] == "buy"
    assert result["confidence"] == 0.85


def test_build_valuation_prompt():
    """Test valuation prompt building."""
    analyst = FundamentalsAnalyst(
        llm_client=Mock(),
        valuation_config={
            "business_models": {
                "standard": ["manufacturing", "services"]
            }
        }
    )

    metrics = {
        "pe": 20.0,
        "pb": 2.5,
        "ps": 3.0,
        "roe": 0.15,
        "roic": 0.12
    }

    prompt = analyst.build_valuation_prompt("AAPL", metrics, "standard")

    assert isinstance(prompt, list)
    assert len(prompt) > 0
    # AAPL should be in the user message (prompt[1]), not the system message (prompt[0])
    assert "AAPL" in prompt[1]["content"]


def test_run_method():
    """Test the run method returns expected structure."""
    mock_client = MockLLMClient()

    analyst = FundamentalsAnalyst(
        llm_client=mock_client,
        valuation_config={"business_models": {}}
    )

    market_data = {"price": 50.0}
    income_data = {"eps": 2.5, "net_income": 100000, "revenue": {"total": 1000000}, "ebit": 150000}
    balance_data = {"shareholders_equity": 500000}
    cashflow_data = {"operating_cash_flow": 80000}

    result = analyst.run(
        symbol="TEST",
        market_data=market_data,
        income_data=income_data,
        balance_data=balance_data,
        cashflow_data=cashflow_data
    )

    assert "report" in result
    assert "summary_json" in result
    assert isinstance(result["report"], str)
    assert isinstance(result["summary_json"], dict)
