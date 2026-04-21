"""Tests for TaskRouter."""
import pytest

from agent.research_v1.task_router import TaskRouter, route_request
from agent.research_v1.contracts import (
    ResearchTask,
    TaskType,
    OutputMode,
    ResearchMode,
)


class TestTaskRouter:
    def setup_method(self):
        self.router = TaskRouter()

    # --- Ticker extraction tests ---

    def test_extract_single_ticker(self):
        task = self.router.route("Analyze AAPL fundamentals")
        assert task.tickers == ["AAPL"]

    def test_extract_multiple_tickers(self):
        task = self.router.route("Compare AAPL MSFT GOOG")
        assert set(task.tickers) == {"AAPL", "MSFT", "GOOG"}

    def test_extract_ticker_with_dot_suffix(self):
        task = self.router.route("Research BABA.K")
        assert "BABA.K" in task.tickers

    def test_extract_hk_ticker_with_numeric_prefix(self):
        """HK stock codes like 0700.HK start with digits."""
        task = self.router.route("Research 0700.HK")
        assert "0700.HK" in task.tickers

    def test_hk_ticker_no_leaked_suffix(self):
        """0700.HK should not also emit a stray 'HK' ticker."""
        task = self.router.route("Research 0700.HK")
        assert task.tickers == ["0700.HK"], f"Expected ['0700.HK'], got {task.tickers}"
        assert "HK" not in task.tickers

    def test_baba_k_no_leaked_prefix(self):
        """BABA.K should not also emit a stray 'BABA' ticker."""
        task = self.router.route("Research BABA.K")
        assert task.tickers == ["BABA.K"], f"Expected ['BABA.K'], got {task.tickers}"
        assert "BABA" not in task.tickers

    def test_ticker_extraction_excludes_common_words(self):
        # Real tickers should be extracted, common words should be filtered
        task = self.router.route("Analyze AAPL THE company AND MSFT FOR you")
        assert set(task.tickers) == {"AAPL", "MSFT"}
        assert "THE" not in task.tickers
        assert "AND" not in task.tickers
        assert "FOR" not in task.tickers

    def test_ticker_extraction_deterministic(self):
        task1 = self.router.route("Analyze AAPL MSFT")
        task2 = self.router.route("Analyze AAPL MSFT")
        assert task1.tickers == task2.tickers

    # --- Task type classification tests ---

    def test_single_ticker_research(self):
        task = self.router.route("Analyze AAPL")
        assert task.task_type == TaskType.SINGLE_TICKER_RESEARCH

    def test_multi_ticker_compare(self):
        task = self.router.route("Compare AAPL vs MSFT")
        assert task.task_type == TaskType.MULTI_TICKER_COMPARE

    def test_multi_ticker_compare_chinese(self):
        task = self.router.route("对比 AAPL 和 MSFT")
        assert task.task_type == TaskType.MULTI_TICKER_COMPARE

    def test_option_idea(self):
        task = self.router.route("Find option ideas for AAPL")
        assert task.task_type == TaskType.OPTION_IDEA

    def test_portfolio_review(self):
        task = self.router.route("Review my portfolio")
        assert task.task_type == TaskType.PORTFOLIO_REVIEW

    def test_position_management(self):
        task = self.router.route("Manage my AAPL position")
        assert task.task_type == TaskType.POSITION_MANAGEMENT

    def test_default_task_type_is_single_ticker(self):
        task = self.router.route("Give me information on TSLA")
        assert task.task_type == TaskType.SINGLE_TICKER_RESEARCH

    # --- Research mode classification tests ---

    def test_fast_research_mode(self):
        task = self.router.route("Quick analysis of AAPL")
        assert task.research_mode == ResearchMode.FAST

    def test_deep_research_mode(self):
        task = self.router.route("Deep research on AAPL")
        assert task.research_mode == ResearchMode.DEEP

    def test_default_research_mode_is_standard(self):
        task = self.router.route("Analyze AAPL")
        assert task.research_mode == ResearchMode.STANDARD

    # --- Output mode classification tests ---

    def test_signal_only_output(self):
        task = self.router.route("Give me just the signal for AAPL")
        assert task.output_mode == OutputMode.SIGNAL_ONLY

    def test_report_only_output(self):
        task = self.router.route("Write a report on AAPL")
        assert task.output_mode == OutputMode.REPORT_ONLY

    def test_pdf_output_mode(self):
        task = self.router.route("Generate full PDF report for AAPL")
        assert task.output_mode == OutputMode.SIGNAL_REPORT_PDF_VIEWER

    def test_default_output_mode_is_signal_and_report(self):
        task = self.router.route("Analyze AAPL")
        assert task.output_mode == OutputMode.SIGNAL_AND_REPORT

    # --- Request text preservation ---

    def test_request_text_preserved(self):
        text = "Please analyze AAPL fundamentals for me"
        task = self.router.route(text)
        assert task.request_text == text

    # --- Structured dict input tests ---

    def test_structured_dict_single_ticker(self):
        data = {
            "request_text": "Analyze AAPL",
            "tickers": ["AAPL"],
            "task_type": "single_ticker_research",
        }
        task = self.router.route(data)
        assert task.tickers == ["AAPL"]
        assert task.task_type == TaskType.SINGLE_TICKER_RESEARCH

    def test_structured_dict_multi_ticker(self):
        data = {
            "request_text": "Compare AAPL and MSFT",
            "tickers": ["AAPL", "MSFT"],
            "task_type": "multi_ticker_compare",
        }
        task = self.router.route(data)
        assert set(task.tickers) == {"AAPL", "MSFT"}
        assert task.task_type == TaskType.MULTI_TICKER_COMPARE

    def test_structured_dict_with_research_mode(self):
        data = {
            "request_text": "Deep analysis",
            "tickers": ["AAPL"],
            "research_mode": "deep",
        }
        task = self.router.route(data)
        assert task.research_mode == ResearchMode.DEEP

    def test_structured_dict_with_string_ticker(self):
        data = {
            "request_text": "Analyze AAPL",
            "tickers": "AAPL",
        }
        task = self.router.route(data)
        assert task.tickers == ["AAPL"]

    def test_structured_dict_missing_request_text_raises(self):
        with pytest.raises(ValueError, match="structured request requires 'request_text'"):
            self.router.route({"tickers": ["AAPL"]})

    def test_structured_dict_missing_tickers_raises(self):
        with pytest.raises(ValueError, match="structured request requires 'tickers'"):
            self.router.route({"request_text": "Analyze"})

    # --- Error handling ---

    def test_empty_text_raises(self):
        with pytest.raises(ValueError, match="request text cannot be empty"):
            self.router.route("")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError, match="request text cannot be empty"):
            self.router.route("   ")

    def test_unsupported_request_type_raises(self):
        with pytest.raises(ValueError, match="Unsupported request type"):
            self.router.route(123)

    # --- Convenience function tests ---

    def test_route_request_convenience_function(self):
        task = route_request("Analyze AAPL")
        assert task.tickers == ["AAPL"]
        assert isinstance(task, ResearchTask)


class TestTaskRouterDeterminism:
    """Verify routing is deterministic regardless of order."""

    def setup_method(self):
        self.router = TaskRouter()

    def test_multiple_requests_same_output(self):
        requests = [
            "Analyze AAPL MSFT GOOG",
            "GOOG MSFT AAPL analyze",
            "MSFT GOOG AAPL analysis",
        ]
        tasks = [self.router.route(r) for r in requests]
        # All tickers should be the same set
        assert all(t.tickers == ["AAPL", "GOOG", "MSFT"] for t in tasks)
        # All task types should be the same
        assert all(t.task_type == TaskType.SINGLE_TICKER_RESEARCH for t in tasks)
