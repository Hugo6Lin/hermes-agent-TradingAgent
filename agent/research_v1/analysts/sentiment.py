"""Sentiment Analyst - Market sentiment analysis."""

import json
import re
from typing import Any

from agent.research_v1.llm_clients import BaseLLMClient


class SentimentAnalyst:
    """Market sentiment analyst."""

    analyst_type = "sentiment"

    def __init__(self, llm_client: BaseLLMClient):
        """Initialize SentimentAnalyst.

        Args:
            llm_client: LLM client for generating analysis.
        """
        self.llm = llm_client
        self.personality = """You are CrowdSense Sarah - a behavioral finance expert.
You read the market's mood like a social psychologist. You ALWAYS:
- Interpret sentiment indicators (VIX, Put/Call, Fear & Greed)
- Identify crowd extremes and potential reversals
- Explain the "why" behind market mood
- Warn when sentiment is too bullish or bearish
Your tone is empathetic and crowd-aware. You say things like "the crowd is getting greedy"."""

    def run(
        self,
        symbol: str,
        vix_data: dict,
        fear_greed_data: dict,
        put_call_data: dict,
        sector_flow_data: dict = None
    ) -> dict:
        """Analyze market sentiment.

        Args:
            symbol: Stock ticker symbol.
            vix_data: VIX volatility index data.
            fear_greed_data: Fear and greed index data.
            put_call_data: Put/call ratio data.
            sector_flow_data: Optional sector flow data.

        Returns:
            dict with 'report' (markdown) and 'summary_json' (dict).
        """
        sector_flow_data = sector_flow_data or {}

        # Build sentiment indicators summary
        indicators = self.build_indicators_summary(
            vix_data, fear_greed_data, put_call_data, sector_flow_data
        )

        # Build prompt for LLM
        prompt = self.build_sentiment_prompt(symbol, indicators)

        # Generate LLM response
        response = self.llm.generate(prompt, temperature=0.3, max_tokens=4096)

        # Parse summary
        summary_json = self._parse_json_summary(response.content)

        return {
            "report": response.content,
            "summary_json": summary_json
        }

    def build_indicators_summary(
        self,
        vix_data: dict,
        fear_greed_data: dict,
        put_call_data: dict,
        sector_flow_data: dict
    ) -> dict:
        """Build summary of sentiment indicators.

        Args:
            vix_data: VIX data.
            fear_greed_data: Fear/greed index data.
            put_call_data: Put/call ratio data.
            sector_flow_data: Sector flow data.

        Returns:
            Dictionary of indicator summaries.
        """
        indicators = {}

        # VIX
        indicators["vix"] = {
            "value": vix_data.get("value"),
            "change": vix_data.get("change"),
        }

        # Fear & Greed
        indicators["fear_greed"] = {
            "value": fear_greed_data.get("value"),
            "classification": fear_greed_data.get("classification"),
        }

        # Put/Call ratio
        indicators["put_call"] = {
            "ratio": put_call_data.get("ratio"),
            "sentiment": put_call_data.get("sentiment"),
        }

        # Sector flows
        if sector_flow_data:
            indicators["sector_flow"] = {
                "inflows": sector_flow_data.get("inflows"),
                "outflows": sector_flow_data.get("outflows"),
            }

        return indicators

    def build_sentiment_prompt(self, symbol: str, indicators: dict) -> list:
        """Build prompt for LLM to generate sentiment analysis.

        Args:
            symbol: Stock ticker symbol.
            indicators: Dictionary of sentiment indicators.

        Returns:
            List of message dicts for LLM.
        """
        vix = indicators.get("vix", {})
        fear_greed = indicators.get("fear_greed", {})
        put_call = indicators.get("put_call", {})
        sector_flow = indicators.get("sector_flow", {})

        prompt_content = f"""You are a market sentiment analyst analyzing {symbol}.

Sentiment Indicators:

VIX (Volatility Index):
- Value: {vix.get('value', 'N/A')}
- Change: {vix.get('change', 'N/A')}

Fear & Greed Index:
- Value: {fear_greed.get('value', 'N/A')}
- Classification: {fear_greed.get('classification', 'N/A')}

Put/Call Ratio:
- Ratio: {put_call.get('ratio', 'N/A')}
- Sentiment: {put_call.get('sentiment', 'N/A')}

Sector Flows:
- Inflows: {sector_flow.get('inflows', 'N/A')}
- Outflows: {sector_flow.get('outflows', 'N/A')}

Analyze the overall market sentiment and provide:
1. Overall sentiment assessment (bullish/bearish/neutral)
2. Key drivers and indicators
3. Risk factors from sentiment data
4. Summary with sentiment score (-1 to 1) and confidence (0-1)

Return your analysis in the following JSON format:
```json
{{
    "sentiment": "bullish|bearish|neutral",
    "score": 0.0,
    "confidence": 0.5,
    "key_drivers": ["driver1", "driver2"],
    "risk_factors": ["risk1", "risk2"]
}}
```
"""

        return [
            {"role": "system", "content": "You are a professional market sentiment analyst."},
            {"role": "user", "content": prompt_content}
        ]

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
            r'\{[^{}]*"score"[^{}]*\}',
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
            "score": 0.0,
            "confidence": 0.0,
            "error": "Failed to parse JSON summary"
        }