"""Industry Analyst - Industry research and competitive analysis."""

import json
import re
from typing import Any

from agent.research_v1.llm_clients import BaseLLMClient


class IndustryAnalyst:
    """Industry research analyst."""

    analyst_type = "industry"

    def __init__(self, llm_client: BaseLLMClient):
        """Initialize IndustryAnalyst.

        Args:
            llm_client: LLM client for generating analysis.
        """
        self.llm = llm_client

    def run(
        self,
        symbol: str,
        industry: str,
        sector_etf_data: dict = None,
        competitor_data: list[dict] = None
    ) -> dict:
        """Analyze industry context.

        Args:
            symbol: Stock ticker symbol.
            industry: Industry name (e.g., "technology", "healthcare").
            sector_etf_data: Optional sector ETF data (XLF, XLK, etc.).
            competitor_data: Optional list of competitor data dicts.

        Returns:
            dict with 'report' (markdown) and 'summary_json' (dict).
        """
        sector_etf_data = sector_etf_data or {}
        competitor_data = competitor_data or []

        # Build industry summary
        industry_summary = self.build_industry_summary(
            industry, sector_etf_data, competitor_data
        )

        # Build prompt for LLM
        prompt = self.build_industry_prompt(symbol, industry, industry_summary)

        # Generate LLM response
        response = self.llm.generate(prompt, temperature=0.3, max_tokens=4096)

        # Parse summary
        summary_json = self._parse_json_summary(response.content)

        return {
            "report": response.content,
            "summary_json": summary_json
        }

    def build_industry_summary(
        self,
        industry: str,
        sector_etf_data: dict,
        competitor_data: list[dict]
    ) -> dict:
        """Build industry summary.

        Args:
            industry: Industry name.
            sector_etf_data: Sector ETF data.
            competitor_data: List of competitor data dicts.

        Returns:
            Dictionary of industry summary.
        """
        summary = {
            "industry": industry,
            "sector_etf": {},
            "competitors": []
        }

        # Sector ETF data
        if sector_etf_data:
            summary["sector_etf"] = {
                "name": sector_etf_data.get("name"),
                "price": sector_etf_data.get("price"),
                "change": sector_etf_data.get("change"),
                "volume": sector_etf_data.get("volume"),
            }

        # Competitor data
        for comp in competitor_data:
            summary["competitors"].append({
                "symbol": comp.get("symbol"),
                "name": comp.get("name"),
                "market_cap": comp.get("market_cap"),
                "revenue": comp.get("revenue"),
            })

        return summary

    def build_industry_prompt(
        self,
        symbol: str,
        industry: str,
        industry_summary: dict
    ) -> list:
        """Build prompt for LLM to generate industry analysis.

        Args:
            symbol: Stock ticker symbol.
            industry: Industry name.
            industry_summary: Summary of industry data.

        Returns:
            List of message dicts for LLM.
        """
        sector_etf = industry_summary.get("sector_etf", {})
        competitors = industry_summary.get("competitors", [])

        competitor_info = ""
        if competitors:
            competitor_lines = []
            for comp in competitors:
                line = f"- {comp.get('symbol')} ({comp.get('name')}): "
                line += f"Market Cap: {comp.get('market_cap', 'N/A')}"
                if comp.get('revenue'):
                    line += f", Revenue: {comp['revenue']}"
                competitor_lines.append(line)
            competitor_info = "\n".join(competitor_lines)
        else:
            competitor_info = "No competitor data available"

        prompt_content = f"""You are an industry research analyst analyzing {symbol}.

Industry: {industry}

Sector ETF Data:
- Name: {sector_etf.get('name', 'N/A')}
- Price: {sector_etf.get('price', 'N/A')}
- Change: {sector_etf.get('change', 'N/A')}
- Volume: {sector_etf.get('volume', 'N/A')}

Competitor Data:
{competitor_info}

Analyze the industry context and provide:
1. Industry outlook and trends
2. Competitive positioning of {symbol} vs competitors
3. Industry-specific opportunities and risks
4. Growth catalysts within the industry
5. Summary with outlook (bullish/bearish/neutral) and confidence (0-1)

Return your analysis in the following JSON format:
```json
{{
    "outlook": "bullish|bearish|neutral",
    "confidence": 0.XX,
    "industry_trends": ["trend1", "trend2"],
    "competitive_position": "positioning assessment",
    "opportunities": ["opportunity1", "opportunity2"],
    "risks": ["risk1", "risk2"]
}}
```
"""

        return [
            {"role": "system", "content": "You are a professional industry research analyst."},
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
            r'\{[^{}]*"outlook"[^{}]*\}',
            r'\{[^{}]*"industry_trends"[^{}]*\}',
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
            "outlook": "unknown",
            "confidence": 0.0,
            "error": "Failed to parse JSON summary"
        }