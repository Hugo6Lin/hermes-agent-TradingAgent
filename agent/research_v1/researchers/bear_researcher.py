"""Bear Researcher - Pessimistic analyst that finds sell arguments."""

from typing import Any

from agent.research_v1.llm_clients import BaseLLMClient


class BearResearcher:
    """Bearish researcher - finds sell arguments."""

    analyst_type = "bear_researcher"

    def __init__(self, llm_client: BaseLLMClient):
        """Initialize BearResearcher.

        Args:
            llm_client: LLM client for generating analysis.
        """
        self.llm = llm_client
        self.system_prompt = """You are Bear Researcher - a pessimistic analyst.
Your job is to find compelling SELL/avoid arguments for a stock.
You MUST:
- Find at least 3 bear points with specific numbers
- Directly counter Bull's arguments with data
- Focus on: risks, competition, regulatory issues, valuation concerns"""

    def run(
        self,
        symbol: str,
        analyst_reports: dict,
        debate_history: list = None
    ) -> dict:
        """Run bear analysis.

        Args:
            symbol: Stock ticker symbol.
            analyst_reports: Dictionary of analyst reports.
            debate_history: Optional list of previous debate rounds.

        Returns:
            dict with 'bear_points' (list) and 'content' (str).
        """
        debate_history = debate_history or []

        # Build context from analyst reports
        reports_summary = self._summarize_reports(analyst_reports)

        # Build context from debate history (include Bull's arguments)
        debate_context = self._build_debate_context(debate_history)

        prompt = self._build_bear_prompt(symbol, reports_summary, debate_context)

        response = self.llm.generate(prompt, temperature=0.7, max_tokens=4096)

        bear_points = self._extract_bear_points(response.content)

        return {
            "bear_points": bear_points,
            "content": response.content
        }

    def _summarize_reports(self, analyst_reports: dict) -> str:
        """Summarize analyst reports for context.

        Args:
            analyst_reports: Dictionary of analyst reports.

        Returns:
            String summary of reports.
        """
        if not analyst_reports:
            return "No analyst reports available."

        summaries = []
        for analyst_type, report in analyst_reports.items():
            if isinstance(report, dict):
                summary = report.get("summary_json", {}).get("summary", str(report))
            else:
                summary = str(report)
            summaries.append(f"{analyst_type}: {summary}")

        return "\n".join(summaries)

    def _build_debate_context(self, debate_history: list) -> str:
        """Build context from debate history including Bull's arguments.

        Args:
            debate_history: List of previous debate rounds.

        Returns:
            String context for debate.
        """
        if not debate_history:
            return "No previous debate rounds."

        context_parts = []
        for i, round_data in enumerate(debate_history[-2:], 1):
            bull_content = round_data.get("bull", {}).get("content", "")
            context_parts.append(f"Previous Bull argument: {bull_content}")

        return "\n".join(context_parts)

    def _build_bear_prompt(
        self,
        symbol: str,
        reports_summary: str,
        debate_context: str
    ) -> list:
        """Build prompt for bear analysis.

        Args:
            symbol: Stock ticker symbol.
            reports_summary: Summary of analyst reports.
            debate_context: Context from previous debate rounds.

        Returns:
            List of message dicts for LLM.
        """
        prompt_content = f"""You are Bear Researcher - a pessimistic analyst analyzing {symbol}.

Analyst Reports Summary:
{reports_summary}

Previous Debate Context:
{debate_context}

Your task:
1. Find at least 3 compelling SELL/avoid arguments with specific numbers
2. Directly counter Bull's arguments with data and risks
3. Focus on: risks, competition, regulatory issues, valuation concerns

Return your analysis in the following JSON format:
```json
{{
    "bear_points": ["Point 1 with specific numbers", "Point 2 with specific numbers", "Point 3 with specific numbers"],
    "content": "Your detailed bear case analysis"
}}
```
"""

        return [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt_content}
        ]

    def _extract_bear_points(self, text: str) -> list:
        """Extract bear points from LLM response.

        Args:
            text: LLM response text.

        Returns:
            List of bear points.
        """
        import re
        import json

        # Try to find JSON block in the response
        json_match = re.search(
            r'```(?:json)?\s*\n(.*?)\n```',
            text,
            re.DOTALL
        )

        if json_match:
            json_str = json_match.group(1)
            try:
                data = json.loads(json_str)
                points = data.get("bear_points", [])
                if points:
                    return points
            except json.JSONDecodeError:
                pass

        # Fallback: extract lines starting with bullet points or numbers
        lines = text.split('\n')
        points = []
        for line in lines:
            line = line.strip()
            if line.startswith(('- ', '* ', '+ ')) or re.match(r'^\d+\.', line):
                point = re.sub(r'^[\-\*\+]\s*|^\d+\.\s*', '', line)
                if point:
                    points.append(point)

        return points if points else [text[:500]]
