"""Tests for FinalJudge."""
import pytest

from agent.research_v1.final_judge import FinalJudge, judge, ROLE_WEIGHTS
from agent.research_v1.contracts import (
    JudgeInputPacket,
    EvidenceBundle,
    EvidenceItem,
    CanonicalSignal,
    CanonicalReport,
    TradePlan,
    AgentRole,
    Direction,
    EvidenceImportance,
    new_evidence_item,
)


class TestFinalJudge:
    """Core FinalJudge tests."""

    def setup_method(self):
        self.judge = FinalJudge()

    def _make_packet(
        self,
        ticker: str,
        evidence_items: list[EvidenceItem],
        conflict_flags: list[str] | None = None,
        missing_steps: list[str] | None = None,
        task_summary: str = "Research on AAPL",
    ) -> JudgeInputPacket:
        bundle = EvidenceBundle(
            task_id="task-1",
            ticker=ticker,
            evidence_items=evidence_items,
            conflict_flags=conflict_flags or [],
        )
        return JudgeInputPacket(
            task_id="task-1",
            ticker=ticker,
            task_summary=task_summary,
            evidence_bundle=bundle,
            required_outputs=["signal", "report"],
            conflict_flags=conflict_flags or [],
            missing_steps=missing_steps or [],
            orchestrator_notes="",
        )

    def test_judge_returns_signal_and_report(self):
        """judge() returns a tuple of CanonicalSignal and CanonicalReport."""
        items = [
            new_evidence_item(
                task_id="task-1",
                subtask_id="sub-1",
                ticker="AAPL",
                agent_role=AgentRole.FUNDAMENTALS,
                claim="Revenue growing",
                direction=Direction.BULLISH,
                confidence=0.8,
            ),
            new_evidence_item(
                task_id="task-1",
                subtask_id="sub-2",
                ticker="AAPL",
                agent_role=AgentRole.TECHNICAL,
                claim="Golden cross",
                direction=Direction.BULLISH,
                confidence=0.75,
            ),
            new_evidence_item(
                task_id="task-1",
                subtask_id="sub-3",
                ticker="AAPL",
                agent_role=AgentRole.NEWS,
                claim="Positive earnings",
                direction=Direction.BULLISH,
                confidence=0.7,
            ),
        ]
        packet = self._make_packet("AAPL", items)
        signal, report = self.judge.make_judgment(packet)
        assert isinstance(signal, CanonicalSignal)
        assert isinstance(report, CanonicalReport)

    def test_signal_fields_match_spec(self):
        """CanonicalSignal has all required spec fields."""
        items = [
            new_evidence_item(
                task_id="task-1",
                subtask_id="sub-1",
                ticker="AAPL",
                agent_role=AgentRole.FUNDAMENTALS,
                claim="Revenue growing",
                direction=Direction.BULLISH,
                confidence=0.8,
            ),
        ]
        packet = self._make_packet("AAPL", items)
        signal, _ = self.judge.make_judgment(packet)
        assert signal.ticker == "AAPL"
        assert signal.rating in ("BUY", "HOLD", "SELL")
        assert 0.0 <= signal.confidence <= 1.0
        assert 0.0 <= signal.priority_score <= 100.0
        assert signal.decision_reason != ""

    def test_report_fields_match_spec(self):
        """CanonicalReport has all required spec fields."""
        items = [
            new_evidence_item(
                task_id="task-1",
                subtask_id="sub-1",
                ticker="AAPL",
                agent_role=AgentRole.FUNDAMENTALS,
                claim="Revenue growing",
                direction=Direction.BULLISH,
                confidence=0.8,
            ),
        ]
        packet = self._make_packet("AAPL", items)
        _, report = self.judge.make_judgment(packet)
        assert report.title != ""
        assert report.executive_summary != ""
        assert report.bottom_line != ""
        assert report.why_now != ""
        assert report.bull_case != ""
        assert report.bear_case != ""

    def test_report_has_trade_plan(self):
        """CanonicalReport includes a TradePlan."""
        items = [
            new_evidence_item(
                task_id="task-1",
                subtask_id="sub-1",
                ticker="AAPL",
                agent_role=AgentRole.FUNDAMENTALS,
                claim="Revenue growing",
                direction=Direction.BULLISH,
                confidence=0.8,
            ),
        ]
        packet = self._make_packet("AAPL", items)
        _, report = self.judge.make_judgment(packet)
        assert report.trade_plan is not None
        assert isinstance(report.trade_plan, TradePlan)

    def test_bearish_evidence_produces_sell_rating(self):
        """Bearish evidence results in SELL rating."""
        items = [
            new_evidence_item(
                task_id="task-1",
                subtask_id="sub-1",
                ticker="AAPL",
                agent_role=AgentRole.FUNDAMENTALS,
                claim="Revenue declining",
                direction=Direction.BEARISH,
                confidence=0.8,
            ),
            new_evidence_item(
                task_id="task-1",
                subtask_id="sub-2",
                ticker="AAPL",
                agent_role=AgentRole.TECHNICAL,
                claim="Head and shoulders",
                direction=Direction.BEARISH,
                confidence=0.75,
            ),
        ]
        packet = self._make_packet("AAPL", items)
        signal, _ = self.judge.make_judgment(packet)
        assert signal.rating == "SELL"

    def test_conflict_flags_produce_risk_flag(self):
        """Conflict flags in packet are reflected in signal risk_flags."""
        items = [
            new_evidence_item(
                task_id="task-1",
                subtask_id="sub-1",
                ticker="AAPL",
                agent_role=AgentRole.FUNDAMENTALS,
                claim="Revenue growing",
                direction=Direction.BULLISH,
                confidence=0.8,
            ),
            new_evidence_item(
                task_id="task-1",
                subtask_id="sub-2",
                ticker="AAPL",
                agent_role=AgentRole.TECHNICAL,
                claim="Breakdown",
                direction=Direction.BEARISH,
                confidence=0.75,
            ),
        ]
        packet = self._make_packet(
            "AAPL",
            items,
            conflict_flags=["fundamentals vs technical direction conflict"],
        )
        signal, _ = self.judge.make_judgment(packet)
        assert "direction_conflict_detected" in signal.risk_flags

    def test_missing_steps_produce_risk_flag(self):
        """Missing evidence coverage is reflected in signal risk_flags."""
        items = [
            new_evidence_item(
                task_id="task-1",
                subtask_id="sub-1",
                ticker="AAPL",
                agent_role=AgentRole.FUNDAMENTALS,
                claim="Revenue growing",
                direction=Direction.BULLISH,
                confidence=0.8,
            ),
        ]
        packet = self._make_packet(
            "AAPL",
            items,
            missing_steps=["technical", "news"],
        )
        signal, _ = self.judge.make_judgment(packet)
        assert "incomplete_evidence_coverage" in signal.risk_flags

    def test_decision_reason_is_populated(self):
        """CanonicalSignal.decision_reason is non-empty."""
        items = [
            new_evidence_item(
                task_id="task-1",
                subtask_id="sub-1",
                ticker="AAPL",
                agent_role=AgentRole.FUNDAMENTALS,
                claim="Revenue growing",
                direction=Direction.BULLISH,
                confidence=0.8,
            ),
        ]
        packet = self._make_packet("AAPL", items)
        signal, _ = self.judge.make_judgment(packet)
        assert len(signal.decision_reason) > 10

    def test_signal_valid_until_is_set(self):
        """signal_valid_until is populated."""
        items = [
            new_evidence_item(
                task_id="task-1",
                subtask_id="sub-1",
                ticker="AAPL",
                agent_role=AgentRole.FUNDAMENTALS,
                claim="Revenue growing",
                direction=Direction.BULLISH,
                confidence=0.8,
            ),
        ]
        packet = self._make_packet("AAPL", items)
        signal, _ = self.judge.make_judgment(packet)
        assert signal.signal_valid_until is not None

    def test_mixed_direction_produces_mixed_risk(self):
        """Mixed signals produce MIXED direction in report risk_watch."""
        items = [
            new_evidence_item(
                task_id="task-1",
                subtask_id="sub-1",
                ticker="AAPL",
                agent_role=AgentRole.FUNDAMENTALS,
                claim="Revenue growing",
                direction=Direction.BULLISH,
                confidence=0.6,
            ),
            new_evidence_item(
                task_id="task-1",
                subtask_id="sub-2",
                ticker="AAPL",
                agent_role=AgentRole.TECHNICAL,
                claim="Breakdown",
                direction=Direction.BEARISH,
                confidence=0.6,
            ),
        ]
        packet = self._make_packet("AAPL", items)
        _, report = self.judge.make_judgment(packet)
        assert "Mixed signals" in report.risk_watch or any(
            "mixed" in rw.lower() for rw in report.risk_watch
        )


class TestConflictPenalty:
    """Regression tests for conflict counting semantics."""

    def setup_method(self):
        self.judge = FinalJudge()

    def _conf(self, items: list[EvidenceItem], missing_steps: list[str] | None = None) -> float:
        """Helper: compute confidence from items."""
        # Use the internal method directly for isolation
        composite = 70.0
        return self.judge._compute_confidence(composite, items, missing_steps)

    def test_conflict_penalty_counts_unique_pairs_only(self):
        """2 bullish + 2 bearish = 4 unique cross pairs, not 8 (no double count)."""
        items = [
            new_evidence_item(task_id="t", subtask_id="s1", ticker="AAPL", agent_role=AgentRole.FUNDAMENTALS, claim="c1", direction=Direction.BULLISH, confidence=0.8),
            new_evidence_item(task_id="t", subtask_id="s2", ticker="AAPL", agent_role=AgentRole.TECHNICAL, claim="c2", direction=Direction.BULLISH, confidence=0.8),
            new_evidence_item(task_id="t", subtask_id="s3", ticker="AAPL", agent_role=AgentRole.NEWS, claim="c3", direction=Direction.BEARISH, confidence=0.8),
            new_evidence_item(task_id="t", subtask_id="s4", ticker="AAPL", agent_role=AgentRole.SENTIMENT, claim="c4", direction=Direction.BEARISH, confidence=0.8),
        ]
        # 2x2 = 4 unique bullish-vs-bearish pairs
        # penalty = 4 * 0.05 = 0.20
        # confidence = 0.70 - 0.20 = 0.50
        conf = self._conf(items)
        assert conf == 0.50, f"Expected 0.50 (4 pairs × 0.05), got {conf}"

    def test_neutral_does_not_create_conflict(self):
        """NEUTRAL items should not count toward conflict penalty."""
        items = [
            new_evidence_item(task_id="t", subtask_id="s1", ticker="AAPL", agent_role=AgentRole.FUNDAMENTALS, claim="c1", direction=Direction.BULLISH, confidence=0.8),
            new_evidence_item(task_id="t", subtask_id="s2", ticker="AAPL", agent_role=AgentRole.TECHNICAL, claim="c2", direction=Direction.NEUTRAL, confidence=0.5),
            new_evidence_item(task_id="t", subtask_id="s3", ticker="AAPL", agent_role=AgentRole.NEWS, claim="c3", direction=Direction.BEARISH, confidence=0.8),
        ]
        # Only 1 BULL-BEAR pair (BULL vs BEAR), NEUTRAL excluded
        # penalty = 1 * 0.05 = 0.05
        # confidence = 0.70 - 0.05 = 0.65
        conf = self._conf(items)
        assert conf == 0.65, f"Expected 0.65 (1 BULL-BEAR pair), got {conf}"

    def test_more_items_with_same_direction_no_conflict(self):
        """More items in same direction should not inflate penalty."""
        items = [
            new_evidence_item(task_id="t", subtask_id="s1", ticker="AAPL", agent_role=AgentRole.FUNDAMENTALS, claim="c1", direction=Direction.BULLISH, confidence=0.8),
            new_evidence_item(task_id="t", subtask_id="s2", ticker="AAPL", agent_role=AgentRole.TECHNICAL, claim="c2", direction=Direction.BULLISH, confidence=0.8),
            new_evidence_item(task_id="t", subtask_id="s3", ticker="AAPL", agent_role=AgentRole.NEWS, claim="c3", direction=Direction.BULLISH, confidence=0.8),
        ]
        # All same direction = 0 conflicts
        # confidence = 0.70 - 0 = 0.70
        conf = self._conf(items)
        assert conf == 0.70, f"Expected 0.70 (0 conflicts), got {conf}"


class TestConfidenceMonotonicity:
    """Regression tests: more/better evidence should not reduce confidence."""

    def setup_method(self):
        self.judge = FinalJudge()

    def _conf(self, items: list[EvidenceItem], missing_steps: list[str] | None = None) -> float:
        composite = 70.0
        return self.judge._compute_confidence(composite, items, missing_steps)

    def test_more_items_same_direction_never_hurts_confidence(self):
        """Adding items with the same direction should not lower confidence."""
        base_items = [
            new_evidence_item(task_id="t", subtask_id="s1", ticker="AAPL", agent_role=AgentRole.FUNDAMENTALS, claim="c1", direction=Direction.BULLISH, confidence=0.8),
        ]
        richer_items = [
            new_evidence_item(task_id="t", subtask_id="s1", ticker="AAPL", agent_role=AgentRole.FUNDAMENTALS, claim="c1", direction=Direction.BULLISH, confidence=0.8),
            new_evidence_item(task_id="t", subtask_id="s2", ticker="AAPL", agent_role=AgentRole.TECHNICAL, claim="c2", direction=Direction.BULLISH, confidence=0.8),
            new_evidence_item(task_id="t", subtask_id="s3", ticker="AAPL", agent_role=AgentRole.NEWS, claim="c3", direction=Direction.BULLISH, confidence=0.8),
        ]
        conf_base = self._conf(base_items)
        conf_richer = self._conf(richer_items)
        assert conf_richer >= conf_base, (
            f"More same-direction items should not lower confidence: "
            f"{conf_richer} < {conf_base}"
        )

    def test_missing_steps_penalizes_not_item_count(self):
        """Confidence should be penalized by missing coverage, not by number of items."""
        # Sparse evidence
        sparse = [
            new_evidence_item(task_id="t", subtask_id="s1", ticker="AAPL", agent_role=AgentRole.FUNDAMENTALS, claim="c1", direction=Direction.BULLISH, confidence=0.8),
        ]
        # Rich evidence (same composite)
        rich = [
            new_evidence_item(task_id="t", subtask_id="s1", ticker="AAPL", agent_role=AgentRole.FUNDAMENTALS, claim="c1", direction=Direction.BULLISH, confidence=0.8),
            new_evidence_item(task_id="t", subtask_id="s2", ticker="AAPL", agent_role=AgentRole.TECHNICAL, claim="c2", direction=Direction.BULLISH, confidence=0.8),
            new_evidence_item(task_id="t", subtask_id="s3", ticker="AAPL", agent_role=AgentRole.NEWS, claim="c3", direction=Direction.BULLISH, confidence=0.8),
        ]
        # Both should have same base confidence (no conflicts, no missing steps)
        conf_sparse = self._conf(sparse)
        conf_rich = self._conf(rich)
        assert conf_rich == conf_sparse, (
            f"Item count should not affect confidence: rich={conf_rich}, sparse={conf_sparse}"
        )
        # Now test missing steps penalty
        conf_with_missing = self._conf(sparse, missing_steps=["technical", "news"])
        # penalty = 2 * 0.05 = 0.10
        # conf = 0.70 - 0.10 = 0.60
        assert conf_with_missing == 0.60, f"Expected 0.60, got {conf_with_missing}"


class TestFinalJudgeBoundedInput:
    """Verify final judge respects bounded input contract."""

    def setup_method(self):
        self.judge = FinalJudge()

    def test_judge_consumes_only_packet_fields(self):
        """Judge only reads packet fields, not arbitrary upstream state."""
        items = [
            new_evidence_item(
                task_id="task-1",
                subtask_id="sub-1",
                ticker="AAPL",
                agent_role=AgentRole.FUNDAMENTALS,
                claim="Revenue growing",
                direction=Direction.BULLISH,
                confidence=0.8,
            ),
        ]
        bundle = EvidenceBundle(
            task_id="task-1",
            ticker="AAPL",
            evidence_items=items,
            conflict_flags=["conflict1"],
        )
        packet = JudgeInputPacket(
            task_id="task-1",
            ticker="AAPL",
            task_summary="Custom summary text",
            evidence_bundle=bundle,
            required_outputs=["signal"],
            conflict_flags=["conflict1"],
            missing_steps=["news"],
            orchestrator_notes="Some workflow notes",
        )
        signal, report = self.judge.make_judgment(packet)
        # Judge should incorporate conflict/missing info from packet into risk_flags
        assert "direction_conflict_detected" in signal.risk_flags
        assert "incomplete_evidence_coverage" in signal.risk_flags

    def test_judge_raises_on_none_bundle(self):
        """Judge raises ValueError if evidence_bundle is None (enforced at packet construction)."""
        # JudgeInputPacket.__post_init__ enforces evidence_bundle is required,
        # so construction itself raises when bundle is None.
        with pytest.raises(ValueError, match="evidence_bundle is required"):
            JudgeInputPacket(
                task_id="task-1",
                ticker="AAPL",
                task_summary="summary",
                evidence_bundle=None,
            )


class TestConvenienceFunction:
    """Tests for the judge() convenience function."""

    def test_judge_convenience_function(self):
        """judge() returns (CanonicalSignal, CanonicalReport)."""
        items = [
            new_evidence_item(
                task_id="task-1",
                subtask_id="sub-1",
                ticker="AAPL",
                agent_role=AgentRole.FUNDAMENTALS,
                claim="Revenue growing",
                direction=Direction.BULLISH,
                confidence=0.8,
            ),
        ]
        bundle = EvidenceBundle(
            task_id="task-1",
            ticker="AAPL",
            evidence_items=items,
        )
        packet = JudgeInputPacket(
            task_id="task-1",
            ticker="AAPL",
            task_summary="summary",
            evidence_bundle=bundle,
        )
        signal, report = judge(packet)
        assert isinstance(signal, CanonicalSignal)
        assert isinstance(report, CanonicalReport)


class TestRoleWeights:
    """Verify role weight configuration."""

    def test_role_weights_are_defined(self):
        """ROLE_WEIGHTS covers all major agent roles."""
        for role in AgentRole:
            assert role.value in ROLE_WEIGHTS, f"Missing weight for {role.value}"
