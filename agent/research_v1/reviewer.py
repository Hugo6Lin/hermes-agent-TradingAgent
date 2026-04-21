"""
Reviewer Extension Point — Quality reviewer for canonical research outputs.

The reviewer is an OPTIONAL extension to the research pipeline:
- It is NEVER the decision authority (Final Judge holds that role)
- It annotates signal/report quality and flags concerns
- Its verdict is a recommendation only — product surface decides how to use it
- When not configured, the pipeline proceeds without review

The reviewer consumes ONLY the bounded ReviewInputPacket and produces a
CanonicalReview. It does NOT read arbitrary upstream state.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent.research_v1.contracts import (
        CanonicalSignal,
        CanonicalReport,
        ReviewInputPacket,
        CanonicalReview,
        ReviewVerdict,
    )


class Reviewer:
    """
    Quality reviewer extension for canonical research outputs.

    The reviewer inspects the final judge's output (CanonicalSignal,
    CanonicalReport) and the orchestrator's evidence bundle for quality
    signals. It does NOT override or re-judge — it only annotates.

    This class is the canonical reviewer implementation. It is designed to
    be replaced/extended by a more sophisticated LLM-powered reviewer in
    production deployments. The extension point contract (ReviewInputPacket
    → CanonicalReview) is stable; only the implementation changes.
    """

    def review(self, packet: ReviewInputPacket) -> CanonicalReview:
        """
        Perform a quality review of the final judge's output.

        Args:
            packet: Bounded ReviewInputPacket from orchestrator.

        Returns:
            CanonicalReview annotation (verdict + flags + annotations).

        Raises:
            ValueError: If the packet fails validation.
        """
        from agent.research_v1.contracts import CanonicalReview, ReviewVerdict

        flags: list[str] = []
        annotations: list[str] = []

        signal = packet.signal
        report = packet.report

        # --- Signal quality checks ---
        if signal is not None:
            # Flag very low confidence signals
            if signal.confidence < 0.5:
                flags.append("low_confidence")
                annotations.append(
                    f"Signal confidence {signal.confidence:.0%} is below 50%; "
                    "verify evidence quality before acting."
                )

            # Flag very low priority scores
            if signal.priority_score < 40:
                flags.append("low_priority_score")
                annotations.append(
                    f"Priority score {signal.priority_score:.1f} is below 40; "
                    "signal may not meet minimum quality threshold."
                )

            # Flag conflicting orchestrator flags
            if "direction_conflict_detected" in signal.risk_flags:
                flags.append("conflict_in_signal")
                annotations.append(
                    "Direction conflict was detected by orchestrator and "
                    "carried into signal risk_flags. Verify resolution."
                )

        # --- Report quality checks ---
        if report is not None:
            # Flag very short executive summary
            if len(report.executive_summary) < 50:
                flags.append("thin_executive_summary")
                annotations.append(
                    "Executive summary is unusually brief; "
                    "verify adequate evidence was provided."
                )

            # Flag missing bull/bear case content
            if len(report.bull_case) < 20:
                flags.append("weak_bull_case")
                annotations.append("Bull case summary is thin; verify bullish evidence coverage.")
            if len(report.bear_case) < 20:
                flags.append("weak_bear_case")
                annotations.append("Bear case summary is thin; verify bearish evidence coverage.")

        # --- Orchestrator flag passthrough ---
        for flag in packet.orchestrator_flags:
            if flag not in flags:
                flags.append(f"orchestrator:{flag}")

        # --- Derive verdict ---
        verdict = self._derive_verdict(flags, signal, report)

        # --- Recommended action ---
        recommended_action = {
            ReviewVerdict.PASS: "proceed",
            ReviewVerdict.NEEDS_REVISION: "escalate",
            ReviewVerdict.REJECTED: "block",
        }[verdict]

        # --- Quality score ---
        quality_score = self._compute_quality_score(flags, signal, report)

        return CanonicalReview(
            task_id=packet.task_id,
            ticker=packet.ticker,
            verdict=verdict,
            quality_score=quality_score,
            flags=flags,
            annotations=annotations,
            recommended_action=recommended_action,
            review_reason=self._summarize_review(verdict, flags, signal, report),
        )

    def _derive_verdict(
        self,
        flags: list[str],
        signal: CanonicalSignal | None,
        report: CanonicalReport | None,
    ) -> ReviewVerdict:
        """Determine the review verdict from quality signals."""
        from agent.research_v1.contracts import ReviewVerdict

        # Any hard blockers → rejected
        if signal is not None and signal.confidence < 0.35:
            return ReviewVerdict.REJECTED

        critical_flags = {"conflict_in_signal", "low_priority_score"}
        if any(f in critical_flags for f in flags):
            return ReviewVerdict.NEEDS_REVISION

        if len(flags) > 2:
            return ReviewVerdict.NEEDS_REVISION

        return ReviewVerdict.PASS

    def _compute_quality_score(
        self,
        flags: list[str],
        signal: CanonicalSignal | None,
        report: CanonicalReport | None,
    ) -> float:
        """Compute a 0.0–1.0 quality score."""
        score = 1.0

        # Penalize per flag
        score -= len(flags) * 0.05

        # Penalize low confidence
        if signal is not None and signal.confidence < 0.6:
            score -= (0.6 - signal.confidence) * 0.3

        # Penalize thin narrative
        if report is not None:
            if len(report.executive_summary) < 80:
                score -= 0.05
            if len(report.bull_case) < 40 or len(report.bear_case) < 40:
                score -= 0.05

        return max(0.0, min(1.0, round(score, 3)))

    def _summarize_review(
        self,
        verdict: ReviewVerdict,
        flags: list[str],
        signal: CanonicalSignal | None,
        report: CanonicalReport | None,
    ) -> str:
        """Build a brief human-readable review summary."""
        parts = [f"Verdict: {verdict.value}."]
        if flags:
            parts.append(f"Flags ({len(flags)}): {', '.join(flags[:3])}.")
        else:
            parts.append("No quality flags raised.")
        if signal is not None:
            parts.append(f"Signal confidence {signal.confidence:.0%}, priority {signal.priority_score:.1f}.")
        return " ".join(parts)


def review(packet: ReviewInputPacket) -> CanonicalReview:
    """
    Convenience function for quality review.

    Args:
        packet: Bounded ReviewInputPacket from orchestrator.

    Returns:
        CanonicalReview annotation.
    """
    reviewer = Reviewer()
    return reviewer.review(packet)
