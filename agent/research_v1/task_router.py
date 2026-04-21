"""
Task Router - Normalizes boss requests into ResearchTask objects.

Converts natural language requests, API requests, or CLI commands into
canonical ResearchTask objects for the orchestrator.
"""

from __future__ import annotations

import re
from typing import Any

from agent.research_v1.contracts import (
    ResearchTask,
    TaskType,
    OutputMode,
    ResearchMode,
    new_research_task,
)


# Regex patterns for ticker extraction
TICKER_PATTERN = r'\b([A-Z]{1,5})\b'
TICKER_WITH_DOT_PATTERN = r'\b([A-Z0-9]{1,5}\.[A-Z]{1,2})\b'  # e.g., BABA.K, 0700.HK


class TaskRouter:
    """
    Routes incoming requests to canonical ResearchTask objects.

    Accepts natural language, structured dict, or CLI-parsed input
    and produces deterministic ResearchTask instances.
    """

    # Keywords for task type classification
    TASK_TYPE_KEYWORDS = {
        TaskType.SINGLE_TICKER_RESEARCH: [
            'analyze', 'analysis', 'research', 'look at', 'check',
            '分析', '研究', '看看', '研究一下',
        ],
        TaskType.MULTI_TICKER_COMPARE: [
            'compare', 'comparison', '对比', '比较', 'vs', 'versus',
            'against', '对标', '相比',
        ],
        TaskType.OPTION_IDEA: [
            'option', 'call', 'put', 'strike', 'expiration',
            '期权', 'call', 'put', '行权',
        ],
        TaskType.PORTFOLIO_REVIEW: [
            'portfolio', 'holdings', 'positions', 'review',
            '持仓', '仓位', '组合', '回顾',
        ],
        TaskType.POSITION_MANAGEMENT: [
            'position', 'manage', 'adjust', 'trim', 'add',
            'position sizing', '仓位管理', '调整仓位',
        ],
    }

    # Keywords for research mode
    RESEARCH_MODE_KEYWORDS = {
        ResearchMode.FAST: ['quick', 'fast', 'brief', '速览', '快'],
        ResearchMode.DEEP: ['deep', 'thorough', 'comprehensive', '详细', '深度'],
    }

    # Keywords for output mode
    OUTPUT_MODE_KEYWORDS = {
        OutputMode.SIGNAL_ONLY: ['signal', 'rating', 'just signal', '结论'],
        OutputMode.SIGNAL_REPORT_PDF_VIEWER: ['pdf', '完整', '详细报告'],
        OutputMode.REPORT_ONLY: ['report', 'writeup', '报告', '分析报告'],
    }

    # Task types that don't require specific tickers
    TASK_TYPES_WITHOUT_TICKERS = {
        TaskType.PORTFOLIO_REVIEW,
        TaskType.POSITION_MANAGEMENT,
    }

    # Placeholder ticker for portfolio-level requests
    PORTFOLIO_PLACEHOLDER = "PORTFOLIO"

    def route(self, request: str | dict[str, Any]) -> ResearchTask:
        """
        Route a request to a ResearchTask.

        Args:
            request: Either a natural language string or a structured dict.

        Returns:
            ResearchTask with all fields populated.

        Raises:
            ValueError: If the request cannot be parsed.
        """
        if isinstance(request, str):
            return self._route_text(request)
        elif isinstance(request, dict):
            return self._route_structured(request)
        else:
            raise ValueError(f"Unsupported request type: {type(request)}")

    def _route_text(self, text: str) -> ResearchTask:
        """Route a natural language text request."""
        text = text.strip()
        if not text:
            raise ValueError("request text cannot be empty")

        # Determine task type first (before ticker extraction)
        task_type = self._classify_task_type(text)

        # Extract tickers
        tickers = self._extract_tickers(text)

        # For task types that don't require specific tickers, use placeholder
        if not tickers and task_type in self.TASK_TYPES_WITHOUT_TICKERS:
            tickers = [self.PORTFOLIO_PLACEHOLDER]

        # Determine research mode
        research_mode = self._classify_research_mode(text)

        # Determine output mode
        output_mode = self._classify_output_mode(text)

        return new_research_task(
            request_text=text,
            tickers=tickers,
            task_type=task_type,
            research_mode=research_mode,
            output_mode=output_mode,
        )

    def _route_structured(self, data: dict[str, Any]) -> ResearchTask:
        """Route a structured dict request."""
        required_fields = ['request_text', 'tickers']
        for field in required_fields:
            if field not in data:
                raise ValueError(f"structured request requires '{field}'")

        tickers = data['tickers']
        if isinstance(tickers, str):
            tickers = [tickers]

        task_type = data.get('task_type', TaskType.SINGLE_TICKER_RESEARCH)
        if isinstance(task_type, str):
            task_type = TaskType(task_type)

        research_mode = data.get('research_mode', ResearchMode.STANDARD)
        if isinstance(research_mode, str):
            research_mode = ResearchMode(research_mode)

        output_mode = data.get('output_mode', OutputMode.SIGNAL_AND_REPORT)
        if isinstance(output_mode, str):
            output_mode = OutputMode(output_mode)

        return new_research_task(
            request_text=data['request_text'],
            tickers=tickers,
            task_type=task_type,
            research_mode=research_mode,
            output_mode=output_mode,
            markets=data.get('markets', []),
            time_horizon=data.get('time_horizon', ''),
            constraints=data.get('constraints', {}),
        )

    def _extract_tickers(self, text: str) -> list[str]:
        """
        Extract stock tickers from text.

        Handles formats like:
        - AAPL
        - AAPL MSFT GOOG
        - AAPL, MSFT, GOOG
        - BABA.K (HK listing), 0700.HK (numeric-prefix HK codes)

        Dot-suffix tickers are returned as-is; their base and suffix components
        are excluded from plain ticker extraction to prevent duplicates.
        """
        # First try to find tickers with dot suffix
        tickers_with_dot = re.findall(TICKER_WITH_DOT_PATTERN, text)
        # Build set of all components from dot tickers to exclude from plain matches
        # e.g., "0700.HK" -> exclude both "0700" and "HK"; "BABA.K" -> exclude both "BABA" and "K"
        dot_components = set()
        for dot_ticker in tickers_with_dot:
            parts = dot_ticker.split('.')
            if len(parts) == 2:
                dot_components.add(parts[0])
                dot_components.add(parts[1])

        # Then find plain tickers, excluding common words and dot-suffix components
        plain_tickers = re.findall(TICKER_PATTERN, text)

        # Common English words that are 1-5 letters and look like tickers
        common_words = {
            'A', 'I', 'AN', 'AS', 'AT', 'BE', 'BY', 'DO', 'GO', 'HE', 'IF',
            'IN', 'IS', 'IT', 'ME', 'MY', 'NO', 'OF', 'ON', 'OR', 'OX', 'SO',
            'TO', 'UP', 'US', 'WE', 'CEO', 'IPO', 'ETF', 'SEC', 'FDA', 'GDP',
            'AI', 'ML', 'IT', 'FY', 'Q1', 'Q2', 'Q3', 'Q4', 'USD', 'EUR', 'GBP',
            'AND', 'THE', 'FOR', 'NOT', 'ARE', 'BUT', 'ALL', 'ANY', 'ONE',
            'OUT', 'THAN', 'THAT', 'THIS', 'WITH', 'FROM', 'HAVE', 'HAD',
            'WHAT', 'WHEN', 'WHERE', 'WHICH', 'THEIR', 'THERE', 'THESE', 'THOSE',
        }

        all_tickers = set(tickers_with_dot)
        for ticker in plain_tickers:
            if ticker not in common_words and ticker not in dot_components:
                all_tickers.add(ticker)

        # Sort for deterministic output
        return sorted(all_tickers)

    def _classify_task_type(self, text: str) -> TaskType:
        """Classify the task type based on text keywords."""
        text_lower = text.lower()

        for task_type, keywords in self.TASK_TYPE_KEYWORDS.items():
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    return task_type

        # Default to single ticker research
        return TaskType.SINGLE_TICKER_RESEARCH

    def _classify_research_mode(self, text: str) -> ResearchMode:
        """Classify the research mode based on text keywords."""
        text_lower = text.lower()

        for mode, keywords in self.RESEARCH_MODE_KEYWORDS.items():
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    return mode

        return ResearchMode.STANDARD

    def _classify_output_mode(self, text: str) -> OutputMode:
        """Classify the output mode based on text keywords."""
        text_lower = text.lower()

        for mode, keywords in self.OUTPUT_MODE_KEYWORDS.items():
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    return mode

        return OutputMode.SIGNAL_AND_REPORT


def route_request(request: str | dict[str, Any]) -> ResearchTask:
    """
    Convenience function for routing a single request.

    Args:
        request: Natural language string or structured dict.

    Returns:
        ResearchTask instance.
    """
    router = TaskRouter()
    return router.route(request)
