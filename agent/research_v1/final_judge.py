"""
Final Judge - Final synthesis and decision maker.

The final judge is the ONLY role that produces final investment judgment.
It consumes ONLY the bounded JudgeInputPacket prepared by the orchestrator.
It does NOT own workflow control and does NOT read arbitrary upstream runtime state.

The final judge:
- synthesizes across evidence classes
- resolves direction conflicts
- produces CanonicalSignal
- produces CanonicalReport
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from agent.research_v1.contracts import (
    JudgeInputPacket,
    CanonicalSignal,
    CanonicalReport,
    TradePlan,
    EvidenceItem,
    Direction,
    EvidenceImportance,
)


from agent.research_v1.calibration_config import RoleWeightConfig

# Weights for role-based score aggregation (via config for zero-weight guards)
ROLE_WEIGHTS = RoleWeightConfig().as_plain_weights()


class FinalJudge:
    """
    Final synthesis and decision maker.

    Consumes ONLY the bounded JudgeInputPacket and produces canonical outputs.
    Does NOT read arbitrary upstream state.
    """

    def __init__(self, role_weight_config: RoleWeightConfig | None = None):
        """Initialize the final judge.

        Args:
            role_weight_config: Optional injected role weight config.
                Defaults to module-level ROLE_WEIGHTS if not provided.
        """
        self.role_weight_config = role_weight_config or RoleWeightConfig()
        self.role_weights = self.role_weight_config.as_plain_weights()

    def make_judgment(self, packet: JudgeInputPacket) -> tuple[CanonicalSignal, CanonicalReport]:
        """
        Form final investment judgment from a bounded judge input packet.

        Args:
            packet: JudgeInputPacket prepared by the orchestrator.

        Returns:
            Tuple of (CanonicalSignal, CanonicalReport).

        Raises:
            ValueError: If the packet is missing required fields.
        """
        if packet.evidence_bundle is None:
            raise ValueError("evidence_bundle is required")

        evidence_items = packet.evidence_bundle.evidence_items
        ticker = packet.ticker

        # Aggregate evidence into per-role summaries
        role_scores = self._aggregate_role_scores(evidence_items)
        composite = self._compute_composite_score(role_scores)

        # Resolve direction from evidence
        direction = self._resolve_direction(evidence_items)

        # Compute confidence with conflict penalty
        confidence = self._compute_confidence(composite, evidence_items, packet.missing_steps)

        # Determine rating from composite score
        rating = self._rating_from_score(composite)

        # Generate signal
        signal = self._build_signal(
            ticker=ticker,
            rating=rating,
            composite=composite,
            confidence=confidence,
            direction=direction,
            conflict_flags=packet.conflict_flags,
            missing_steps=packet.missing_steps,
        )

        # Generate report
        report = self._build_report(
            ticker=ticker,
            rating=rating,
            composite=composite,
            direction=direction,
            evidence_items=evidence_items,
            conflict_flags=packet.conflict_flags,
            missing_steps=packet.missing_steps,
            packet=packet,
        )

        return signal, report

    def _aggregate_role_scores(self, items: list[EvidenceItem]) -> dict[str, float]:
        """
        Aggregate evidence items into per-role directional scores.

        Each evidence item with a non-neutral direction contributes to its role's score.
        Returns role -> score dict where positive = bullish, negative = bearish (0 = neutral).
        """
        role_directions: dict[str, list[float]] = {}
        for item in items:
            role = item.agent_role.value
            if role not in role_directions:
                role_directions[role] = []
            role_directions[role].append(item.confidence * self._direction_sign(item.direction))

        role_scores: dict[str, float] = {}
        for role, directions in role_directions.items():
            if directions:
                role_scores[role] = sum(directions) / len(directions)
            else:
                role_scores[role] = 0.0

        return role_scores

    def _direction_sign(self, direction: Direction) -> float:
        """Map Direction enum to numeric sign: bullish=+1, bearish=-1, neutral/mixed=0."""
        if direction == Direction.BULLISH:
            return 1.0
        elif direction == Direction.BEARISH:
            return -1.0
        return 0.0

    def _compute_composite_score(self, role_scores: dict[str, float]) -> float:
        """Compute weighted composite score (0-100) from role scores."""
        total_weight = 0.0
        weighted_sum = 0.0
        for role, score in role_scores.items():
            weight = self.role_weights.get(role, 0.05)
            weighted_sum += (score * 0.5 + 0.5) * weight  # shift [-1,1] -> [0,1]
            total_weight += weight

        if total_weight <= 0:
            return 50.0

        # weighted_sum is now in [0, 1] space; scale to [0, 100]
        return min(100.0, max(0.0, weighted_sum / total_weight * 100.0))

    def _resolve_direction(self, items: list[EvidenceItem]) -> Direction:
        """Resolve overall direction from evidence items."""
        bullish = sum(1 for i in items if i.direction == Direction.BULLISH)
        bearish = sum(1 for i in items if i.direction == Direction.BEARISH)
        neutral = sum(1 for i in items if i.direction == Direction.NEUTRAL)

        total = bullish + bearish + neutral
        if total == 0:
            return Direction.NEUTRAL

        if bullish > bearish and bullish > neutral:
            return Direction.BULLISH
        elif bearish > bullish and bearish > neutral:
            return Direction.BEARISH
        elif bullish == bearish:
            return Direction.MIXED
        return Direction.NEUTRAL

    def _compute_confidence(
        self,
        composite: float,
        items: list[EvidenceItem],
        missing_steps: list[str] | None = None,
    ) -> float:
        """Compute final confidence with conflict penalty.

        Args:
            composite: Composite score (0-100).
            items: Evidence items.
            missing_steps: Missing coverage steps from packet (not item count).
        """
        # Base confidence from composite score
        base_confidence = composite / 100.0

        # Penalty for conflicts: use same semantics as EvidenceStore.detect_conflicts
        # which finds unique BULLISH vs BEARISH pairs only (no NEUTRAL/MIXED)
        from agent.research_v1.evidence_store import EvidenceStore
        store = EvidenceStore()
        conflicts = store.detect_conflicts(items)
        conflict_penalty = min(0.3, len(conflicts) * 0.05)

        # Penalize for missing evidence coverage (NOT item count)
        steps = missing_steps if missing_steps is not None else []
        missing_penalty = min(0.1, len(steps) * 0.05)

        confidence = max(0.1, min(0.99, base_confidence - conflict_penalty - missing_penalty))
        return round(confidence, 4)

    def _rating_from_score(self, composite: float) -> str:
        """Map composite score to rating string."""
        if composite >= 75:
            return "BUY"
        elif composite >= 55:
            return "HOLD"
        else:
            return "SELL"

    def _build_signal(
        self,
        ticker: str,
        rating: str,
        composite: float,
        confidence: float,
        direction: Direction,
        conflict_flags: list[str],
        missing_steps: list[str],
    ) -> CanonicalSignal:
        """Build a CanonicalSignal from computed judgment."""
        risk_flags = []

        if conflict_flags:
            risk_flags.append("direction_conflict_detected")
        if missing_steps:
            risk_flags.append("incomplete_evidence_coverage")
        if direction == Direction.BEARISH:
            risk_flags.append("negative_momentum")

        # Decision reason summarizes the judgment basis
        direction_str = direction.value
        decision_reason = (
            f"Final judgment: {rating} based on composite score {composite:.1f}/100. "
            f"Overall direction: {direction_str}. "
            f"Confidence: {confidence:.0%}."
        )
        if conflict_flags:
            decision_reason += f" {len(conflict_flags)} direction conflict(s) noted."
        if missing_steps:
            decision_reason += f" Missing coverage: {', '.join(missing_steps)}."

        return CanonicalSignal(
            ticker=ticker,
            rating=rating,
            confidence=confidence,
            priority_score=round(composite, 2),
            holding_horizon=self._horizon_from_rating(rating),
            signal_valid_until=datetime.now(timezone.utc) + timedelta(days=self._days_from_rating(rating)),
            risk_flags=risk_flags,
            decision_reason=decision_reason,
        )

    def _horizon_from_rating(self, rating: str) -> str:
        """Map rating to holding horizon hint."""
        return {"BUY": "1month", "HOLD": "2weeks", "SELL": "1week"}.get(rating, "1week")

    def _days_from_rating(self, rating: str) -> int:
        """Map rating to validity days."""
        return {"BUY": 30, "HOLD": 14, "SELL": 7}.get(rating, 7)

    def _build_report(
        self,
        ticker: str,
        rating: str,
        composite: float,
        direction: Direction,
        evidence_items: list[EvidenceItem],
        conflict_flags: list[str],
        missing_steps: list[str],
        packet: JudgeInputPacket,
    ) -> CanonicalReport:
        """Build a CanonicalReport from computed judgment."""
        direction_str = direction.value

        # Build bull/bear cases from evidence
        bull_items = [i for i in evidence_items if i.direction == Direction.BULLISH]
        bear_items = [i for i in evidence_items if i.direction == Direction.BEARISH]

        bull_case = self._summarize_evidence(bull_items, "bullish")
        bear_case = self._summarize_evidence(bear_items, "bearish")

        # Why now: combines task summary with current direction assessment
        why_now = (
            f"Research request: {packet.task_summary}. "
            f"Evidence direction is {direction_str} with composite score {composite:.1f}/100. "
            f"Rating: {rating}."
        )

        # Executive summary
        executive_summary = (
            f"{rating} {ticker} with {direction_str} overall sentiment. "
            f"Composite score: {composite:.1f}/100. "
            f"Evidence from {len(evidence_items)} items across {len(set(i.agent_role for i in evidence_items))} roles. "
            f"Confidence: {self._compute_confidence(composite, evidence_items, missing_steps):.0%}."
        )

        # Bottom line
        bottom_line = f"{rating} {ticker} — {direction_str} bias based on current evidence."

        # Key evidence references
        key_evidence = [
            i.evidence_id for i in evidence_items
            if i.importance in (EvidenceImportance.HIGH, EvidenceImportance.CRITICAL)
        ]

        # Risk watch
        risk_watch = []
        if conflict_flags:
            risk_watch.append(f"Direction conflict: {'; '.join(conflict_flags[:3])}")
        if missing_steps:
            risk_watch.append(f"Incomplete coverage: {', '.join(missing_steps)}")
        if direction == Direction.MIXED:
            risk_watch.append("Mixed signals — confirm with additional research")

        # Appendix
        appendix = {
            "composite_score": composite,
            "rating": rating,
            "direction": direction_str,
            "evidence_count": len(evidence_items),
            "roles_covered": sorted(set(i.agent_role.value for i in evidence_items)),
        }

        # Trade plan
        trade_plan = TradePlan(
            action=rating,
            holding_period=self._horizon_from_rating(rating),
        )

        return CanonicalReport(
            title=f"{ticker} Research Report",
            executive_summary=executive_summary,
            bottom_line=bottom_line,
            why_now=why_now,
            bull_case=bull_case or f"No strong bullish evidence found.",
            bear_case=bear_case or f"No strong bearish evidence found.",
            trade_plan=trade_plan,
            risk_watch=risk_watch,
            key_evidence=key_evidence,
            appendix=appendix,
        )

    def _summarize_evidence(self, items: list[EvidenceItem], bias: str) -> str:
        """Summarize a list of evidence items into a paragraph."""
        if not items:
            return f"No {bias} evidence items found."

        # Sort by importance descending
        sorted_items = sorted(items, key=lambda i: i.importance.value if hasattr(i.importance, 'value') else str(i.importance), reverse=True)
        top_claims = [f"[{i.agent_role.value}] {i.claim}" for i in sorted_items[:5]]
        return " ".join(top_claims)


def judge(packet: JudgeInputPacket) -> tuple[CanonicalSignal, CanonicalReport]:
    """
    Convenience function for final judgment.

    Args:
        packet: JudgeInputPacket from orchestrator.

    Returns:
        Tuple of (CanonicalSignal, CanonicalReport).
    """
    judge_instance = FinalJudge()
    return judge_instance.make_judgment(packet)
