"""Options Analyst - Options market structure analysis using LLM."""

import json
import re
from typing import Any

from agent.research_v1.llm_clients import BaseLLMClient


class OptionsAnalyst:
    """Options market structure analyst."""

    analyst_type = "options"

    def __init__(self, llm_client: BaseLLMClient):
        self.llm = llm_client

    def run(self, symbol: str, option_chain: list[dict]) -> dict:
        """
        Run options market structure analysis.

        Args:
            symbol: Stock ticker symbol.
            option_chain: List of option chain dicts with expiration, strike,
                call/put open interest and volume.

        Returns:
            dict with 'report' (markdown) and 'summary_json' (dict).
        """
        prompt = self._build_options_prompt(symbol, option_chain)
        response = self.llm.generate(prompt, temperature=0.3, max_tokens=4096)
        summary_json = self._parse_json_summary(response.content)

        return {
            "report": response.content,
            "summary_json": summary_json,
        }

    def _build_options_prompt(self, symbol: str, option_chain: list[dict]) -> list:
        chain_lines = []
        for opt in option_chain[:10]:
            chain_lines.append(
                f"- Expiry: {opt.get('expiration')} | Strike: {opt.get('strike')} | "
                f"Call OI: {opt.get('call_open_interest', 'N/A')} | "
                f"Put OI: {opt.get('put_open_interest', 'N/A')} | "
                f"Call Vol: {opt.get('call_volume', 'N/A')} | "
                f"Put Vol: {opt.get('put_volume', 'N/A')}"
            )

        prompt_content = f"""You are an options market structure analyst analyzing {symbol}.

Option Chain Sample:
{chr(10).join(chain_lines)}

Analyze the options market structure and provide:
1. Put/call ratio interpretation
2. Key strike levels with unusual activity
3. Implied volatility signals
4. Support/resistance derived from options data
5. Overall options sentiment (bullish/bearish/neutral) with confidence (0-1)

Return in JSON format:
```json
{{
    "put_call_ratio": 0.XX,
    "sentiment": "bullish|bearish|neutral",
    "confidence": 0.XX,
    "key_strikes": ["strike1", "strike2"],
    "iv_signal": "high|medium|low",
    "summary": "brief interpretation"
}}
```
"""
        return [
            {"role": "system", "content": "You are a professional options analyst."},
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
            r'\{[^{}]*"sentiment"[^{}]*\}',
            r'\{[^{}]*"put_call_ratio"[^{}]*\}',
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
            "sentiment": "unknown",
            "confidence": 0.0,
            "error": "Failed to parse JSON",
        }
