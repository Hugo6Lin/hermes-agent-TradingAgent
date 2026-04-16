"""Fundamentals Analyst - Financial fundamentals analysis using MiniMax 2.7."""

import json
import re
from typing import Any

from agent.research_v1.llm_clients import BaseLLMClient


class FundamentalsAnalyst:
    """Financial fundamentals analyst using MiniMax 2.7."""

    analyst_type = "fundamentals"

    def __init__(self, llm_client: BaseLLMClient, valuation_config: dict):
        """Initialize FundamentalsAnalyst.

        Args:
            llm_client: LLM client for generating analysis.
            valuation_config: Configuration including business model keywords.
        """
        self.llm = llm_client
        self.valuation_config = valuation_config
        self.personality = """You are Warren Analyst - a meticulous value investor.
You speak in precise financial language. You ALWAYS:
- Cite specific metrics (P/E, ROE, Debt/Equity, etc.)
- Compare against industry benchmarks
- Flag any data inconsistencies or red flags
- Prefer conservative assumptions
Your tone is professional and data-driven. You rarely get excited."""

    def run(
        self,
        symbol: str,
        market_data: dict,
        income_data: dict = None,
        balance_data: dict = None,
        cashflow_data: dict = None
    ) -> dict:
        """Run fundamental analysis.

        Args:
            symbol: Stock ticker symbol.
            market_data: Market data including price, market_cap, etc.
            income_data: Income statement data.
            balance_data: Balance sheet data.
            cashflow_data: Cash flow statement data.

        Returns:
            dict with 'report' (markdown) and 'summary_json' (dict).
        """
        income_data = income_data or {}
        balance_data = balance_data or {}
        cashflow_data = cashflow_data or {}

        # Detect business model
        business_model = self.detect_business_model(income_data, symbol)

        # Calculate financial metrics
        metrics = self.calculate_metrics(market_data, income_data, balance_data, cashflow_data)

        # Build valuation prompt
        prompt = self.build_valuation_prompt(symbol, metrics, business_model)

        # Generate LLM response
        response = self.llm.generate(prompt, temperature=0.3, max_tokens=4096)

        # Parse summary
        summary_json = self._parse_json_summary(response.content)

        return {
            "report": response.content,
            "summary_json": summary_json
        }

    def detect_business_model(self, income_data: dict, symbol: str) -> str:
        """Detect business model from income data and keywords.

        Args:
            income_data: Income statement data.
            symbol: Stock ticker symbol.

        Returns:
            Detected business model string.
        """
        business_models = self.valuation_config.get("business_models", {})

        # Build searchable text from income data
        searchable_text = f"{symbol} ".encode('utf-8', errors='ignore').decode('utf-8')
        if income_data:
            searchable_text += f" {json.dumps(income_data)}"

        searchable_text_lower = searchable_text.lower()

        # Check each business model for keyword matches
        for model_name, keywords in business_models.items():
            for keyword in keywords:
                if keyword.lower() in searchable_text_lower:
                    return model_name

        return "standard"

    def calculate_pe(self, market_data: dict, income_data: dict) -> float | None:
        """Calculate Price-to-Earnings ratio.

        Args:
            market_data: Market data including price.
            income_data: Income data including EPS.

        Returns:
            PE ratio or None if EPS <= 0.
        """
        price = market_data.get("price")
        eps = income_data.get("eps")

        if price is None or eps is None or eps <= 0:
            return None

        return price / eps

    def calculate_pb(self, market_data: dict, balance_data: dict) -> float | None:
        """Calculate Price-to-Book ratio.

        Args:
            market_data: Market data including price.
            balance_data: Balance sheet data including book_value_per_share.

        Returns:
            PB ratio or None if book_value_per_share is not available or <= 0.
        """
        price = market_data.get("price")
        book_value_per_share = balance_data.get("book_value_per_share")

        if price is None or book_value_per_share is None or book_value_per_share <= 0:
            return None

        return price / book_value_per_share

    def calculate_ps(self, market_data: dict, income_data: dict) -> float | None:
        """Calculate Price-to-Sales ratio.

        Args:
            market_data: Market data including price.
            income_data: Income data including revenue and shares.

        Returns:
            PS ratio or None if revenue_per_share cannot be calculated.
        """
        price = market_data.get("price")
        revenue = income_data.get("revenue", {}).get("total")
        shares = market_data.get("shares_outstanding") or income_data.get("shares")

        if price is None or revenue is None or not shares or shares <= 0:
            return None

        revenue_per_share = revenue / shares
        if revenue_per_share <= 0:
            return None

        return price / revenue_per_share

    def calculate_roe(self, income_data: dict, balance_data: dict) -> float | None:
        """Calculate Return on Equity.

        Args:
            income_data: Income data including net_income.
            balance_data: Balance sheet data including shareholders_equity.

        Returns:
            ROE ratio or None if shareholders_equity is 0 or negative.
        """
        net_income = income_data.get("net_income")
        shareholders_equity = balance_data.get("shareholders_equity")

        if net_income is None or shareholders_equity is None or shareholders_equity <= 0:
            return None

        return net_income / shareholders_equity

    def calculate_roic(
        self,
        income_data: dict,
        balance_data: dict
    ) -> float | None:
        """Calculate Return on Invested Capital.

        ROIC = EBIT / (Debt + Equity - Cash)

        Args:
            income_data: Income data including EBIT.
            balance_data: Balance sheet data including debt, equity, cash.

        Returns:
            ROIC ratio or None if calculation not possible.
        """
        ebit = income_data.get("ebit")
        total_debt = balance_data.get("total_debt", 0)
        shareholders_equity = balance_data.get("shareholders_equity", 0)
        cash = balance_data.get("cash_and_equivalents", 0)

        if ebit is None:
            return None

        invested_capital = total_debt + shareholders_equity - cash
        if invested_capital <= 0:
            return None

        return ebit / invested_capital

    def calculate_debt_to_equity(self, balance_data: dict) -> float | None:
        """Calculate Debt-to-Equity ratio.

        Args:
            balance_data: Balance sheet data.

        Returns:
            Debt-to-Equity ratio or None if equity is 0 or negative.
        """
        total_debt = balance_data.get("total_debt", 0)
        total_equity = balance_data.get("shareholders_equity") or balance_data.get("total_equity", 0)

        if total_equity is None or total_equity <= 0:
            return None

        return total_debt / total_equity

    def calculate_cash_flow_match(
        self,
        cashflow_data: dict,
        income_data: dict
    ) -> float | None:
        """Calculate cash flow match ratio.

        现金流匹配度 = Operating Cash Flow / Net Income

        Args:
            cashflow_data: Cash flow data including operating_cash_flow.
            income_data: Income data including net_income.

        Returns:
            Cash flow match ratio or None if net_income is 0 or negative.
        """
        operating_cash_flow = cashflow_data.get("operating_cash_flow")
        net_income = income_data.get("net_income")

        if operating_cash_flow is None or net_income is None or net_income <= 0:
            return None

        return operating_cash_flow / net_income

    def calculate_metrics(
        self,
        market_data: dict,
        income_data: dict,
        balance_data: dict,
        cashflow_data: dict
    ) -> dict:
        """Calculate financial metrics.

        Args:
            market_data: Market data.
            income_data: Income statement data.
            balance_data: Balance sheet data.
            cashflow_data: Cash flow statement data.

        Returns:
            Dictionary of calculated metrics.
        """
        metrics = {}

        # PE ratio
        metrics["pe"] = self.calculate_pe(market_data, income_data)

        # PB ratio
        metrics["pb"] = self.calculate_pb(market_data, balance_data)

        # PS ratio
        metrics["ps"] = self.calculate_ps(market_data, income_data)

        # ROE
        metrics["roe"] = self.calculate_roe(income_data, balance_data)

        # ROIC
        metrics["roic"] = self.calculate_roic(income_data, balance_data)

        # Debt to Equity
        metrics["debt_to_equity"] = self.calculate_debt_to_equity(balance_data)

        # Cash flow match
        metrics["cash_flow_match"] = self.calculate_cash_flow_match(
            cashflow_data, income_data
        )

        # Additional useful metrics
        metrics["market_cap"] = market_data.get("market_cap")
        metrics["price"] = market_data.get("price")

        return metrics

    def build_valuation_prompt(
        self,
        symbol: str,
        metrics: dict,
        business_model: str
    ) -> list:
        """Build prompt for LLM to generate valuation analysis.

        Args:
            symbol: Stock ticker symbol.
            metrics: Calculated financial metrics.
            business_model: Detected business model.

        Returns:
            List of message dicts for LLM.
        """
        prompt_content = f"""You are a financial fundamentals analyst analyzing {symbol}.

Business Model: {business_model}

Key Financial Metrics:
- PE (Price-to-Earnings): {metrics.get('pe', 'N/A')}
- PB (Price-to-Book): {metrics.get('pb', 'N/A')}
- PS (Price-to-Sales): {metrics.get('ps', 'N/A')}
- ROE (Return on Equity): {metrics.get('roe', 'N/A')}
- ROIC (Return on Invested Capital): {metrics.get('roic', 'N/A')}
- Debt/Equity: {metrics.get('debt_to_equity', 'N/A')}
- Cash Flow Match: {metrics.get('cash_flow_match', 'N/A')}

Analyze the fundamentals and provide:
1. A brief valuation assessment (1-2 sentences)
2. Key strengths and weaknesses
3. Investment summary with a clear verdict (buy/hold/sell) and confidence score (0-1)

Return your analysis in the following JSON format:
```json
{{
    "summary": "Your brief valuation summary here",
    "verdict": "buy|hold|sell",
    "confidence": 0.XX,
    "strengths": ["strength1", "strength2"],
    "weaknesses": ["weakness1", "weakness2"]
}}
```
"""

        return [
            {"role": "system", "content": "You are a professional financial analyst."},
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

        # Try to find raw JSON at the start or anywhere
        json_patterns = [
            r'\{[^{}]*"summary"[^{}]*\}',
            r'\{[^{}]*"verdict"[^{}]*\}',
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
            "verdict": "unknown",
            "confidence": 0.0,
            "error": "Failed to parse JSON summary"
        }
