"""
Evidence Store - Normalizes subagent outputs into canonical EvidenceItem objects.

The evidence store is the primary internal language layer. It transforms
subagent outputs (structured or freeform) into atomic EvidenceItem objects
for consumption by the orchestrator and final judge.

Key principles:
- Evidence items are atomic and role-scoped
- Raw payload is always preserved for audit
- Normalization does NOT invent unsupported fields
- Conflict tagging and missing-step signaling are hook-based
"""

from __future__ import annotations

from typing import Any

from agent.research_v1.contracts import (
    EvidenceItem,
    EvidenceBundle,
    AgentRole,
    ClaimType,
    Direction,
    EvidenceImportance,
    new_evidence_item,
)


class EvidenceStore:
    """
    Normalizes subagent outputs into EvidenceItem collections.

    Supports:
    - Structured payloads (dict with known schema fields)
    - Partially freeform payloads (text with structured hints)
    - Mixed evidence batches from multiple agents
    """

    def __init__(self):
        """Initialize the evidence store."""
        self._items: list[EvidenceItem] = []

    def normalize(
        self,
        task_id: str,
        subtask_id: str,
        ticker: str,
        agent_role: AgentRole,
        raw_output: dict[str, Any] | str,
    ) -> list[EvidenceItem]:
        """
        Normalize a subagent output into EvidenceItem objects.

        Args:
            task_id: Parent task ID.
            subtask_id: This subtask's ID.
            ticker: Ticker symbol.
            agent_role: Which agent produced this output.
            raw_output: Raw output from the subagent (dict or string).

        Returns:
            List of EvidenceItem objects extracted from the output.

        Raises:
            ValueError: If the output cannot be normalized.
        """
        if isinstance(raw_output, dict):
            return self._normalize_structured(
                task_id, subtask_id, ticker, agent_role, raw_output
            )
        elif isinstance(raw_output, str):
            return self._normalize_freeform(
                task_id, subtask_id, ticker, agent_role, raw_output
            )
        else:
            raise ValueError(f"Unsupported output type: {type(raw_output)}")

    def _normalize_structured(
        self,
        task_id: str,
        subtask_id: str,
        ticker: str,
        agent_role: AgentRole,
        payload: dict[str, Any],
    ) -> list[EvidenceItem]:
        """
        Normalize a structured dict payload.

        Expected dict shape (flexible - missing fields are allowed):
        {
            "report": "...",           # optional freeform text
            "summary_json": {...},     # optional structured data
            "claims": [...],           # optional list of structured claims
            "confidence": 0.85,       # optional overall confidence
            "direction": "bullish",    # optional overall direction
        }
        """
        items: list[EvidenceItem] = []

        # If the payload has a summary_json with structured fields, extract them
        summary = payload.get("summary_json") or payload.get("summary") or {}
        if isinstance(summary, dict):
            claim_items = self._extract_from_summary(
                task_id, subtask_id, ticker, agent_role, summary, payload
            )
            items.extend(claim_items)

        # If the payload has explicit claims list, extract those
        claims = payload.get("claims", [])
        if isinstance(claims, list):
            for claim_data in claims:
                if isinstance(claim_data, dict):
                    item = self._claim_dict_to_evidence(
                        task_id, subtask_id, ticker, agent_role, claim_data, payload
                    )
                    items.append(item)

        # If no structured claims found, try to extract from the report text
        if not items and payload.get("report"):
            freeform_items = self._normalize_freeform(
                task_id, subtask_id, ticker, agent_role, payload["report"]
            )
            items.extend(freeform_items)

        # If still no items, create one item from the whole payload (raw capture)
        if not items:
            item = new_evidence_item(
                task_id=task_id,
                subtask_id=subtask_id,
                ticker=ticker,
                agent_role=agent_role,
                claim=f"{agent_role.value} analysis completed",
                value=payload,
                confidence=payload.get("confidence", 0.5),
                direction=self._direction_from_string(
                    payload.get("direction", "neutral")
                ),
                raw_payload=payload,
            )
            items.append(item)

        return items

    def _normalize_freeform(
        self,
        task_id: str,
        subtask_id: str,
        ticker: str,
        agent_role: AgentRole,
        text: str,
    ) -> list[EvidenceItem]:
        """
        Normalize a freeform text payload.

        Attempts to extract structured hints from text, but falls back
        to a single evidence item capturing the raw text if no structure found.
        """
        items: list[EvidenceItem] = []

        # Try to extract direction signals from text
        direction = self._infer_direction_from_text(text)

        # Try to extract confidence signals
        confidence = self._infer_confidence_from_text(text)

        # Try to extract key claims (simple heuristic: numbered/bulleted points)
        claims = self._extract_claims_from_text(text)

        if claims:
            for i, claim_text in enumerate(claims):
                item = new_evidence_item(
                    task_id=task_id,
                    subtask_id=subtask_id,
                    ticker=ticker,
                    agent_role=agent_role,
                    claim=claim_text.strip(),
                    confidence=confidence,
                    direction=direction,
                    importance=EvidenceImportance.MEDIUM,
                    raw_payload={"original_text": text, "claim_index": i},
                )
                items.append(item)
        else:
            # Fallback: capture the whole text as one evidence item
            item = new_evidence_item(
                task_id=task_id,
                subtask_id=subtask_id,
                ticker=ticker,
                agent_role=agent_role,
                claim=text[:200] if len(text) > 200 else text,
                value=None,
                confidence=confidence,
                direction=direction,
                importance=EvidenceImportance.MEDIUM,
                raw_payload={"original_text": text},
            )
            items.append(item)

        return items

    def _extract_from_summary(
        self,
        task_id: str,
        subtask_id: str,
        ticker: str,
        agent_role: AgentRole,
        summary: dict[str, Any],
        full_payload: dict[str, Any],
    ) -> list[EvidenceItem]:
        """Extract evidence items from a structured summary dict."""
        items: list[EvidenceItem] = []

        # Direction and confidence may be top-level in summary
        direction = self._direction_from_string(summary.get("direction", "neutral"))
        confidence = self._safe_confidence(summary.get("confidence", summary.get("confidence_score", 0.5)))

        # Extract key metrics as individual evidence items
        numeric_metrics = [
            "revenue_growth", "earnings_growth", "pe_ratio", "peg_ratio",
            "debt_equity", "roe", "roa", "margin", "growth_rate",
            "rsi", "macd", "signal_line", "bollinger_position",
            "put_call_ratio", "fear_greed_index", "vix_level",
        ]

        for metric_key in numeric_metrics:
            if metric_key in summary:
                value = summary[metric_key]
                try:
                    numeric_value = float(value)
                except (TypeError, ValueError):
                    numeric_value = value

                # Infer direction from metric key context
                claim_text = f"{metric_key}: {value}"
                item = new_evidence_item(
                    task_id=task_id,
                    subtask_id=subtask_id,
                    ticker=ticker,
                    agent_role=agent_role,
                    claim=claim_text,
                    value=numeric_value,
                    confidence=confidence,
                    direction=direction,
                    importance=EvidenceImportance.MEDIUM,
                    raw_payload=full_payload,
                )
                items.append(item)

        # Extract verdict/recommendation if present
        if "verdict" in summary:
            verdict = str(summary["verdict"])
            item = new_evidence_item(
                task_id=task_id,
                subtask_id=subtask_id,
                ticker=ticker,
                agent_role=agent_role,
                claim=f"Verdict: {verdict}",
                value=verdict,
                confidence=confidence,
                direction=direction,
                importance=EvidenceImportance.HIGH,
                raw_payload=full_payload,
            )
            items.append(item)

        # Extract sentiment score if present
        if "sentiment" in summary:
            sentiment = str(summary["sentiment"])
            item = new_evidence_item(
                task_id=task_id,
                subtask_id=subtask_id,
                ticker=ticker,
                agent_role=agent_role,
                claim=f"Sentiment: {sentiment}",
                value=sentiment,
                confidence=confidence,
                direction=direction,
                importance=EvidenceImportance.MEDIUM,
                raw_payload=full_payload,
            )
            items.append(item)

        return items

    def _claim_dict_to_evidence(
        self,
        task_id: str,
        subtask_id: str,
        ticker: str,
        agent_role: AgentRole,
        claim_data: dict[str, Any],
        full_payload: dict[str, Any],
    ) -> EvidenceItem:
        """Convert a structured claim dict to an EvidenceItem."""
        claim = claim_data.get("claim", claim_data.get("description", ""))
        if not claim:
            claim = str(claim_data)

        return new_evidence_item(
            task_id=task_id,
            subtask_id=subtask_id,
            ticker=ticker,
            agent_role=agent_role,
            claim=str(claim),
            value=claim_data.get("value"),
            confidence=self._safe_confidence(claim_data.get("confidence", 0.5)),
            direction=self._direction_from_string(claim_data.get("direction", "neutral")),
            importance=self._importance_from_string(claim_data.get("importance", "medium")),
            source_refs=claim_data.get("sources", []),
            raw_payload=full_payload,
        )

    def _extract_claims_from_text(self, text: str) -> list[str]:
        """
        Extract individual claims from freeform text.

        Looks for bullet points, numbered lists, or sentence-level claims.
        """
        claims: list[str] = []

        # Split on numbered points (1. 2. etc)
        import re
        numbered = re.split(r'\n\s*\d+[.)]\s*', text)
        for segment in numbered:
            segment = segment.strip()
            if segment and len(segment) > 10:
                claims.append(segment)

        # Split on bullet points
        bullet_segments: list[str] = []
        for segment in numbered:
            bullets = re.split(r'\n\s*[-*•]\s*', segment)
            bullet_segments.extend([b.strip() for b in bullets if b.strip()])

        # Deduplicate while preserving order
        seen: set[str] = set()
        unique_claims: list[str] = []
        for claim in bullet_segments:
            # Normalize for dedup
            normalized = claim.lower().strip()
            if normalized and normalized not in seen and len(claim) > 10:
                seen.add(normalized)
                unique_claims.append(claim)

        return unique_claims[:10]  # Cap at 10 claims per output

    def _safe_confidence(self, value: Any, default: float = 0.5) -> float:
        """
        Parse a confidence value that may be numeric or qualitative.

        Args:
            value: The value to parse (float, int, str, or None).
            default: Fallback value if parsing fails.

        Returns:
            float confidence between 0.0 and 1.0.
        """
        if value is None:
            return default
        if isinstance(value, (int, float)):
            try:
                return float(value)
            except (TypeError, ValueError):
                return default
        if isinstance(value, str):
            v = value.lower().strip()
            if v in ("high", "strong", "confident", "certain"):
                return 0.85
            if v in ("medium", "moderate", "mid", "reasonable"):
                return 0.65
            if v in ("low", "weak", "uncertain", "unclear"):
                return 0.35
            if v in ("very low", "very uncertain"):
                return 0.2
            try:
                return float(v)
            except ValueError:
                return default
        return default

    def _direction_from_string(self, direction: str | None) -> Direction:
        """Convert a string direction to Direction enum."""
        if not direction:
            return Direction.NEUTRAL
        d = direction.lower().strip()
        if d in ("bullish", "positive", "buy", "long", "up", "bull"):
            return Direction.BULLISH
        elif d in ("bearish", "negative", "sell", "short", "down", "bear"):
            return Direction.BEARISH
        elif d in ("mixed", "uncertain", "unclear"):
            return Direction.MIXED
        return Direction.NEUTRAL

    def _importance_from_string(self, importance: str | None) -> EvidenceImportance:
        """Convert a string importance to EvidenceImportance enum."""
        if not importance:
            return EvidenceImportance.MEDIUM
        i = importance.lower().strip()
        if i in ("critical", "high", "important"):
            return EvidenceImportance.HIGH
        elif i in ("low", "minor", "negligible"):
            return EvidenceImportance.LOW
        return EvidenceImportance.MEDIUM

    def _infer_direction_from_text(self, text: str) -> Direction:
        """Infer direction from text keywords."""
        text_lower = text.lower()
        bullish_signals = ["buy", "bullish", "positive", "growth", "upside", "outperform", "accumulate"]
        bearish_signals = ["sell", "bearish", "negative", "decline", "downside", "underperform"]

        bullish_count = sum(1 for s in bullish_signals if s in text_lower)
        bearish_count = sum(1 for s in bearish_signals if s in text_lower)

        if bullish_count > bearish_count:
            return Direction.BULLISH
        elif bearish_count > bullish_count:
            return Direction.BEARISH
        return Direction.NEUTRAL

    def _infer_confidence_from_text(self, text: str) -> float:
        """Infer confidence from text signals."""
        text_lower = text.lower()
        high_confidence_signals = ["confirmed", "strongly", "clearly", "definitely", "high confidence"]
        low_confidence_signals = ["possibly", "maybe", "uncertain", "might", "could be", "unclear"]

        for signal in high_confidence_signals:
            if signal in text_lower:
                return 0.8
        for signal in low_confidence_signals:
            if signal in text_lower:
                return 0.4
        return 0.6  # default

    def detect_conflicts(
        self,
        items: list[EvidenceItem],
    ) -> list[tuple[EvidenceItem, EvidenceItem]]:
        """
        Detect conflicting evidence items.

        Args:
            items: List of evidence items to check.

        Returns:
            List of (item_a, item_b) tuples where direction conflicts exist.
        """
        conflicts: list[tuple[EvidenceItem, EvidenceItem]] = []

        # Group by ticker and claim type
        from collections import defaultdict
        by_ticker_claim: dict[tuple[str, str], list[EvidenceItem]] = defaultdict(list)
        for item in items:
            key = (item.ticker, item.claim_type.value)
            by_ticker_claim[key].append(item)

        # Within each group, check for direction conflicts
        for group_items in by_ticker_claim.values():
            if len(group_items) < 2:
                continue
            for i, item_a in enumerate(group_items):
                for item_b in group_items[i + 1:]:
                    if item_a.direction != item_b.direction:
                        if item_a.direction != Direction.NEUTRAL and item_b.direction != Direction.NEUTRAL:
                            conflicts.append((item_a, item_b))

        return conflicts

    def detect_missing_fields(
        self,
        items: list[EvidenceItem],
        required_fields: list[str],
    ) -> list[str]:
        """
        Detect which required fields are missing from the evidence set.

        Args:
            items: List of evidence items.
            required_fields: List of field names that should be present.

        Returns:
            List of missing field names.
        """
        # Presence of any evidence item for a role means that role is covered
        present_roles: set[str] = {item.agent_role.value for item in items}

        # Check which required roles are missing evidence
        missing: list[str] = []
        for field in required_fields:
            if field not in present_roles:
                missing.append(field)
        return missing


def normalize_subagent_output(
    task_id: str,
    subtask_id: str,
    ticker: str,
    agent_role: AgentRole,
    raw_output: dict[str, Any] | str,
) -> list[EvidenceItem]:
    """
    Convenience function to normalize a single subagent output.

    Args:
        task_id: Parent task ID.
        subtask_id: This subtask's ID.
        ticker: Ticker symbol.
        agent_role: Which agent produced this output.
        raw_output: Raw output from the subagent.

    Returns:
        List of EvidenceItem objects.
    """
    store = EvidenceStore()
    return store.normalize(task_id, subtask_id, ticker, agent_role, raw_output)
