"""Research Manager - Manages bull/bear debate and makes final decision."""

from typing import Any

from agent.research_v1.llm_clients import BaseLLMClient
from agent.research_v1.researchers.bull_researcher import BullResearcher
from agent.research_v1.researchers.bear_researcher import BearResearcher


class DebateManager:
    """Manages bull/bear debate and makes final decision."""

    MAX_ROUNDS = 3

    def __init__(
        self,
        llm_client: BaseLLMClient,
        bull_researcher: BullResearcher,
        bear_researcher: BearResearcher
    ):
        """Initialize DebateManager.

        Args:
            llm_client: LLM client for generating final decision.
            bull_researcher: BullResearcher instance.
            bear_researcher: BearResearcher instance.
        """
        self.llm = llm_client
        self.bull = bull_researcher
        self.bear = bear_researcher

    def run_debate(
        self,
        symbol: str,
        analyst_reports: dict
    ) -> dict:
        """Run debate between bull and bear researchers.

        Args:
            symbol: Stock ticker symbol.
            analyst_reports: Dictionary of analyst reports.

        Returns:
            dict with:
            - decision: "BUY|SELL|HOLD"
            - confidence: "high|medium|low"
            - key_reasons: list of key reasons
            - remaining_concerns: list of remaining concerns
            - debate_rounds: list of debate round data
        """
        debate_rounds = []
        debate_history = []

        for round_num in range(1, self.MAX_ROUNDS + 1):
            # Run bull analysis
            bull_result = self.bull.run(
                symbol=symbol,
                analyst_reports=analyst_reports,
                debate_history=debate_history
            )

            # Run bear analysis
            bear_result = self.bear.run(
                symbol=symbol,
                analyst_reports=analyst_reports,
                debate_history=debate_history
            )

            round_data = {
                "round": round_num,
                "bull": bull_result,
                "bear": bear_result
            }
            debate_rounds.append(round_data)

            # Update debate history for next round
            debate_history.append(round_data)

            # Check for stalemate
            if self._detect_stalemate(debate_history):
                break

        # Make final decision
        final_decision = self._final_decision(debate_rounds)

        return {
            "decision": final_decision["decision"],
            "confidence": final_decision["confidence"],
            "key_reasons": final_decision["key_reasons"],
            "remaining_concerns": final_decision["remaining_concerns"],
            "debate_rounds": debate_rounds
        }

    def _detect_stalemate(self, history: list) -> bool:
        """Detect if debate is stuck in a loop.

        Uses novelty scoring to detect if new arguments are genuinely novel
        or just rehashing of previous points.

        Args:
            history: List of debate round data.

        Returns:
            True if stalemate detected, False otherwise.
        """
        if len(history) < 2:
            return False

        # Quick check: exact content hash match
        if hash(history[-1]["bull"]["content"]) == hash(history[-2]["bull"]["content"]) and \
           hash(history[-1]["bear"]["content"]) == hash(history[-2]["bear"]["content"]):
            return True

        # Novelty scoring: check if new arguments bring anything new
        bull_novelty = self._compute_novelty(history)
        bear_novelty = self._compute_novelty(history, side="bear")

        # If both sides show low novelty (< 0.2), we're in a stalemate
        if bull_novelty < 0.2 and bear_novelty < 0.2:
            return True

        return False

    def _compute_novelty(self, history: list, side: str = "bull") -> float:
        """Compute novelty score for a side's latest argument.

        Compares the latest argument against all previous arguments
        to see how much new content is introduced.

        Args:
            history: List of debate round data.
            side: "bull" or "bear".

        Returns:
            Novelty score from 0.0 (identical) to 1.0 (completely novel).
        """
        if len(history) < 2:
            return 1.0

        latest = history[-1][side].get("content", "")
        latest_lower = latest.lower()

        # Extract key phrases from latest (nouns, important terms)
        import re
        latest_words = set(re.findall(r'\b[a-z]{4,}\b', latest_lower))

        # Compare against all previous rounds
        total_overlap = 0.0
        num_previous = len(history) - 1

        for prev_round in history[:-1]:
            prev_content = prev_round[side].get("content", "")
            prev_lower = prev_content.lower()
            prev_words = set(re.findall(r'\b[a-z]{4,}\b', prev_lower))

            if prev_words:
                # Jaccard similarity
                intersection = latest_words & prev_words
                union = latest_words | prev_words
                similarity = len(intersection) / len(union) if union else 0
                total_overlap += similarity

        avg_overlap = total_overlap / num_previous if num_previous > 0 else 0

        # Novelty is inverse of overlap
        return max(0.0, min(1.0, 1.0 - avg_overlap))

    def _final_decision(self, debate_rounds: list) -> dict:
        """Make final decision using Research Manager (Claude Opus).

        Args:
            debate_rounds: List of debate round data.

        Returns:
            dict with decision, confidence, key_reasons, remaining_concerns.
        """
        # Build summary of debate
        debate_summary = self._build_debate_summary(debate_rounds)

        prompt = self._make_final_decision_prompt(debate_summary)

        response = self.llm.generate(prompt, temperature=0.3, max_tokens=4096)

        decision_data = self._parse_decision(response.content)

        return decision_data

    def _build_debate_summary(self, debate_rounds: list) -> str:
        """Build summary of debate rounds.

        Args:
            debate_rounds: List of debate round data.

        Returns:
            String summary of debate.
        """
        if not debate_rounds:
            return "No debate rounds completed."

        summaries = []
        for round_data in debate_rounds:
            round_num = round_data["round"]
            bull_points = round_data["bull"].get("bull_points", [])
            bear_points = round_data["bear"].get("bear_points", [])

            summaries.append(
                f"Round {round_num}:\n"
                f"  Bull: {bull_points}\n"
                f"  Bear: {bear_points}"
            )

        return "\n".join(summaries)

    def _make_final_decision_prompt(self, debate_summary: str) -> list:
        """Build prompt for final decision.

        Args:
            debate_summary: Summary of debate rounds.

        Returns:
            List of message dicts for LLM.
        """
        prompt_content = f"""You are the Research Manager - responsible for making the final investment decision.

Debate Summary:
{debate_summary}

Your task:
1. Analyze the bull and bear arguments carefully
2. Make a final decision: BUY, SELL, or HOLD
3. Assess your confidence in the decision
4. Identify key reasons supporting the decision
5. Note any remaining concerns

Return your decision in the following JSON format:
```json
{{
    "decision": "BUY|SELL|HOLD",
    "confidence": "high|medium|low",
    "key_reasons": ["reason1", "reason2", "reason3"],
    "remaining_concerns": ["concern1", "concern2"]
}}
```
"""

        return [
            {"role": "system", "content": "You are a Research Manager responsible for making final investment decisions."},
            {"role": "user", "content": prompt_content}
        ]

    def _parse_decision(self, text: str) -> dict:
        """Parse decision from LLM response.

        Args:
            text: LLM response text.

        Returns:
            dict with decision, confidence, key_reasons, remaining_concerns.
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
                if "decision" in data:
                    return {
                        "decision": data.get("decision", "HOLD"),
                        "confidence": data.get("confidence", "medium"),
                        "key_reasons": data.get("key_reasons", []),
                        "remaining_concerns": data.get("remaining_concerns", [])
                    }
            except json.JSONDecodeError:
                pass

        # Fallback parsing
        decision = "HOLD"
        confidence = "medium"
        key_reasons = []
        remaining_concerns = []

        # Try to extract decision
        if "BUY" in text.upper():
            decision = "BUY"
        elif "SELL" in text.upper():
            decision = "SELL"

        # Try to extract confidence
        if "high" in text.lower():
            confidence = "high"
        elif "low" in text.lower():
            confidence = "low"

        # Try to extract bullet points
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith(('- ', '* ', '+ ')) or re.match(r'^\d+\.', line):
                point = re.sub(r'^[\-\*\+]\s*|^\d+\.\s*', '', line)
                if "concern" in point.lower():
                    remaining_concerns.append(point)
                else:
                    key_reasons.append(point)

        return {
            "decision": decision,
            "confidence": confidence,
            "key_reasons": key_reasons if key_reasons else [text[:500]],
            "remaining_concerns": remaining_concerns
        }
