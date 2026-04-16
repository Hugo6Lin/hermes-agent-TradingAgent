"""News Analyst - News and events analysis."""

import json
import re
from typing import Any

from agent.research_v1.llm_clients import BaseLLMClient


class NewsAnalyst:
    """News and events analyst."""

    analyst_type = "news"

    def __init__(self, llm_client: BaseLLMClient):
        """Initialize NewsAnalyst.

        Args:
            llm_client: LLM client for generating analysis.
        """
        self.llm = llm_client

    def run(
        self,
        symbol: str,
        news_items: list[dict],
        earnings_data: dict = None
    ) -> dict:
        """Analyze news impact.

        Args:
            symbol: Stock ticker symbol.
            news_items: List of news items with headline, source, date, sentiment.
            earnings_data: Optional upcoming earnings data.

        Returns:
            dict with 'report' (markdown) and 'summary_json' (dict).
        """
        earnings_data = earnings_data or {}

        # Build news summary
        news_summary = self.summarize_news_items(news_items)

        # Build prompt for LLM
        prompt = self.build_news_prompt(symbol, news_items, news_summary, earnings_data)

        # Generate LLM response
        response = self.llm.generate(prompt, temperature=0.3, max_tokens=4096)

        # Parse summary
        summary_json = self._parse_json_summary(response.content)

        return {
            "report": response.content,
            "summary_json": summary_json
        }

    def summarize_news_items(self, news_items: list[dict]) -> dict:
        """Summarize news items.

        Args:
            news_items: List of news item dicts.

        Returns:
            Dictionary with news summary.
        """
        if not news_items:
            return {"count": 0, "sentiment_breakdown": {}}

        sentiment_breakdown = {"positive": 0, "negative": 0, "neutral": 0}
        sources = set()
        headlines = []

        for item in news_items:
            sentiment = item.get("sentiment", "neutral").lower()
            if sentiment in sentiment_breakdown:
                sentiment_breakdown[sentiment] += 1
            if item.get("source"):
                sources.add(item.get("source"))
            if item.get("headline"):
                headlines.append(item.get("headline"))

        return {
            "count": len(news_items),
            "sentiment_breakdown": sentiment_breakdown,
            "sources": list(sources),
            "headlines": headlines[:5]  # First 5 headlines
        }

    def build_news_prompt(
        self,
        symbol: str,
        news_items: list[dict],
        news_summary: dict,
        earnings_data: dict
    ) -> list:
        """Build prompt for LLM to generate news analysis.

        Args:
            symbol: Stock ticker symbol.
            news_items: List of news items.
            news_summary: Summary of news items.
            earnings_data: Upcoming earnings data.

        Returns:
            List of message dicts for LLM.
        """
        earnings_info = ""
        if earnings_data:
            earnings_info = f"""
Upcoming Earnings:
- Date: {earnings_data.get('date', 'N/A')}
- Expected EPS: {earnings_data.get('expected_eps', 'N/A')}
"""

        prompt_content = f"""You are a news analyst analyzing {symbol}.

News Summary:
- Total Articles: {news_summary.get('count', 0)}
- Sentiment Breakdown: {news_summary.get('sentiment_breakdown', {})}
- Sources: {', '.join(news_summary.get('sources', ['N/A']))}

Latest Headlines:
{self._format_headlines(news_summary.get('headlines', []))}

{earnings_info}

Analyze the news impact and provide:
1. Overall news sentiment assessment
2. Key news themes and catalysts
3. Potential impact on stock price
4. Risk and opportunity identification
5. Summary with sentiment (positive/negative/neutral) and confidence (0-1)

Return your analysis in the following JSON format:
```json
{{
    "sentiment": "positive|negative|neutral",
    "confidence": 0.XX,
    "themes": ["theme1", "theme2"],
    "catalysts": ["catalyst1", "catalyst2"],
    "risks": ["risk1", "risk2"],
    "opportunities": ["opportunity1", "opportunity2"]
}}
```
"""

        return [
            {"role": "system", "content": "You are a professional news analyst."},
            {"role": "user", "content": prompt_content}
        ]

    def _format_headlines(self, headlines: list[str]) -> str:
        """Format headlines for prompt.

        Args:
            headlines: List of headline strings.

        Returns:
            Formatted string of headlines.
        """
        if not headlines:
            return "- No headlines available"
        return "\n".join(f"- {h}" for h in headlines)

    def _parse_json_summary(self, text: str) -> dict:
        """Parse JSON summary from LLM response.

        Args:
            text: LLM response text.

        Returns:
            Parsed summary dictionary.
        """
        # Try to find JSON block in the response
        json_match = re.search(
            r'```(?:json)?\s*\n(.*?)\n```',
            text,
            re.DOTALL
        )

        if json_match:
            json_str = json_match.group(1)
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass

        # Try to find raw JSON
        json_patterns = [
            r'\{[^{}]*"sentiment"[^{}]*\}',
            r'\{[^{}]*"themes"[^{}]*\}',
        ]

        for pattern in json_patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass

        # Return default if parsing fails
        return {
            "summary": text[:500] if len(text) > 500 else text,
            "sentiment": "unknown",
            "confidence": 0.0,
            "error": "Failed to parse JSON summary"
        }