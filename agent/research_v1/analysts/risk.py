"""Risk Analyst - Portfolio and market risk analysis using LLM."""

import json
import re
from typing import Any

from agent.research_v1.llm_clients import BaseLLMClient


class RiskAnalyst:
    """Risk analysis for positions and market exposure."""

    analyst_type = "risk"

    def __init__(self, llm_client: BaseLLMClient):
        self.llm = llm_client

    def run(self, symbol: str, market_data: dict, positions: list[dict]) -> dict:
        """
        Run risk analysis.

        Args:
            symbol: Stock ticker symbol.
            market_data: Market data dict with price, atr, etc.
            positions: List of position dicts (can be empty for single-ticker research).

        Returns:
            dict with 'report' (markdown) and 'summary_json' (dict).
        """
        prompt = self._build_risk_prompt(symbol, market_data, positions)
        response = self.llm.generate(prompt, temperature=0.3, max_tokens=4096)
        summary_json = self._parse_json_summary(response.content)

        return {
            "report": response.content,
            "summary_json": summary_json,
        }

    def _build_risk_prompt(
        self, symbol: str, market_data: dict, positions: list[dict]
    ) -> list:
        position_lines = []
        for pos in (positions or []):
            position_lines.append(
                f"- {pos.get('symbol', symbol)} | Qty: {pos.get('quantity', 0)} | "
                f"Entry: {pos.get('entry_price', 'N/A')} | "
                f"Stop: {pos.get('stop_loss', 'N/A')}"
            )

        prompt_content = f"""You are a risk analyst reviewing {symbol}.

Market Data:
- Price: {market_data.get('price', 'N/A')}
- ATR: {market_data.get('atr', 'N/A')}
- Volatility: {market_data.get('volatility', 'N/A')}

Positions:
{chr(10).join(position_lines) if position_lines else "- No open positions"}

Analyze the risk profile and provide:
1. Key risk factors for {symbol}
2. Position risk if holding (or N/A for no positions)
3. Volatility and drawdown risk assessment
4. Risk rating (low/medium/high) with confidence (0-1)

Return in JSON format:
```json
{{
    "risk_rating": "low|medium|high",
    "confidence": 0.XX,
    "risk_factors": ["factor1", "factor2"],
    "volatility_assessment": "low|medium|high",
    "summary": "brief risk interpretation"
}}
```
"""
        return [
            {"role": "system", "content": "You are a professional risk analyst."},
            {"role": "user", "content": prompt_content},
        ]

    def _parse_json_summary(self, text: str) -> dict:
        json_match = re.search(r'```(?:json)?\s*\n(.*?)\n```', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        json_patterns = [
            r'\{[^{}]*"risk_rating"[^{}]*\}',
            r'\{[^{}]*"risk_factors"[^{}]*\}',
        ]
        for pattern in json_patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass

        return {
            "summary": text[:500] if len(text) > 500 else text,
            "risk_rating": "unknown",
            "confidence": 0.0,
            "error": "Failed to parse JSON",
        }
