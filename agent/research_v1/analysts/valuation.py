"""Valuation Analyst - DCF and relative valuation analysis using LLM."""

import json
import re
from typing import Any

from agent.research_v1.llm_clients import BaseLLMClient
from agent.research_v1.valuation_models import (
    calculate_dcf_value,
    calculate_ddm_value,
    calculate_relative_valuation,
)


class ValuationAnalyst:
    """Valuation model analyst using DCF, DDM, and relative valuation."""

    analyst_type = "valuation"

    def __init__(self, llm_client: BaseLLMClient):
        self.llm = llm_client

    def run(
        self,
        symbol: str,
        market_data: dict,
        income_data: dict = None,
        balance_data: dict = None,
        cashflow_data: dict = None,
    ) -> dict:
        """
        Run valuation analysis.

        Args:
            symbol: Stock ticker symbol.
            market_data: Market data including price and shares.
            income_data: Income statement data.
            balance_data: Balance sheet data.
            cashflow_data: Cash flow statement data.

        Returns:
            dict with 'report' (markdown) and 'summary_json' (dict).
        """
        income_data = income_data or {}
        balance_data = balance_data or {}
        cashflow_data = cashflow_data or {}

        metrics = self._calculate_valuation_metrics(market_data, income_data, balance_data, cashflow_data)
        prompt = self._build_valuation_prompt(symbol, metrics)
        response = self.llm.generate(prompt, temperature=0.3, max_tokens=4096)
        summary_json = self._parse_json_summary(response.content)

        return {
            "report": response.content,
            "summary_json": summary_json,
        }

    def _calculate_valuation_metrics(
        self, market_data: dict, income_data: dict, balance_data: dict, cashflow_data: dict
    ) -> dict:
        metrics = {}

        # PE
        price = market_data.get("price")
        eps = income_data.get("eps")
        if price and eps and eps > 0:
            metrics["pe"] = price / eps

        # PB
        book_value = balance_data.get("book_value_per_share")
        if price and book_value and book_value > 0:
            metrics["pb"] = price / book_value

        # DCF
        fcf = cashflow_data.get("free_cash_flow_projection")
        if fcf:
            dcf_result = calculate_dcf_value(
                free_cash_flows=fcf,
                discount_rate=cashflow_data.get("discount_rate", 0.10),
                terminal_growth_rate=cashflow_data.get("terminal_growth_rate", 0.03),
            )
            metrics["dcf_value"] = dcf_result.get("enterprise_value")

        # DDM
        dividend = cashflow_data.get("annual_dividend")
        if dividend:
            ddm_result = calculate_ddm_value(
                annual_dividend=dividend,
                cost_of_equity=cashflow_data.get("cost_of_equity", 0.09),
                dividend_growth_rate=cashflow_data.get("dividend_growth_rate", 0.03),
            )
            metrics["ddm_value"] = ddm_result.get("intrinsic_value")

        # Relative
        benchmark = market_data.get("benchmark_multiples", {"pe": 18.0, "pb": 3.0})
        rel_result = calculate_relative_valuation(market_data=market_data, benchmark_multiples=benchmark)
        metrics["relative_target"] = rel_result.get("target_price")

        metrics["market_price"] = price
        metrics["upside_potential"] = (
            round((metrics.get("dcf_value") or price) / price * 100 - 100, 1)
            if price and metrics.get("dcf_value")
            else None
        )

        return metrics

    def _build_valuation_prompt(self, symbol: str, metrics: dict) -> list:
        prompt_content = f"""You are a valuation analyst analyzing {symbol}.

Valuation Metrics:
- Market Price: {metrics.get('market_price', 'N/A')}
- P/E Ratio: {metrics.get('pe', 'N/A')}
- P/B Ratio: {metrics.get('pb', 'N/A')}
- DCF Value: {metrics.get('dcf_value', 'N/A')}
- DDM Intrinsic Value: {metrics.get('ddm_value', 'N/A')}
- Relative Valuation Target: {metrics.get('relative_target', 'N/A')}
- Upside Potential: {metrics.get('upside_potential', 'N/A')}%

Analyze the valuation and provide:
1. Is the stock overvalued, fairly valued, or undervalued?
2. Key valuation drivers
3. Valuation confidence (0-1)
4. Investment verdict (buy/hold/sell) based on valuation alone

Return in JSON format:
```json
{{
    "verdict": "buy|hold|sell",
    "confidence": 0.XX,
    "valuation_level": "undervalued|fair|overvalued",
    "key_drivers": ["driver1", "driver2"],
    "summary": "brief valuation interpretation"
}}
```
"""
        return [
            {"role": "system", "content": "You are a professional valuation analyst."},
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
            r'\{[^{}]*"verdict"[^{}]*\}',
            r'\{[^{}]*"valuation_level"[^{}]*\}',
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
            "verdict": "unknown",
            "confidence": 0.0,
            "error": "Failed to parse JSON",
        }
