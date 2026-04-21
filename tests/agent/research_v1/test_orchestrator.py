"""Tests for Orchestrator (Phase 4 full implementation)."""
import pytest

from agent.research_v1.orchestrator import Orchestrator, REQUIRED_ROLES_BY_TASK_TYPE
from agent.research_v1.contracts import (
    ResearchTask,
    SubagentTask,
    EvidenceBundle,
    EvidenceItem,
    JudgeInputPacket,
    AgentRole,
    TaskType,
    OutputMode,
    ResearchMode,
    Direction,
    ClaimType,
    EvidenceImportance,
    new_evidence_item,
)


class TestOrchestratorSkeleton:
    """Verify orchestrator skeleton interface without full logic."""

    def setup_method(self):
        self.orchestrator = Orchestrator()

    def test_decompose_single_ticker(self):
        task = ResearchTask(
            request_text="Analyze AAPL",
            tickers=["AAPL"],
            task_type=TaskType.SINGLE_TICKER_RESEARCH,
        )
        subtasks = self.orchestrator.decompose(task)
        assert len(subtasks) > 0
        assert all(s.task_id == task.task_id for s in subtasks)
        assert all(s.ticker == "AAPL" for s in subtasks)

    def test_decompose_multi_ticker(self):
        task = ResearchTask(
            request_text="Compare AAPL and MSFT",
            tickers=["AAPL", "MSFT"],
            task_type=TaskType.MULTI_TICKER_COMPARE,
        )
        subtasks = self.orchestrator.decompose(task)
        tickers = {s.ticker for s in subtasks}
        assert tickers == {"AAPL", "MSFT"}

    def test_decompose_returns_subagent_tasks(self):
        task = ResearchTask(
            request_text="Analyze AAPL",
            tickers=["AAPL"],
        )
        subtasks = self.orchestrator.decompose(task)
        assert all(isinstance(s, SubagentTask) for s in subtasks)

    def test_assemble_bundle_basic(self):
        evidence = [
            new_evidence_item(
                task_id="task-1",
                subtask_id="sub-1",
                ticker="AAPL",
                agent_role=AgentRole.FUNDAMENTALS,
                claim="Revenue up",
            ),
            new_evidence_item(
                task_id="task-1",
                subtask_id="sub-2",
                ticker="AAPL",
                agent_role=AgentRole.TECHNICAL,
                claim="Golden cross",
            ),
        ]
        bundle = self.orchestrator.assemble_bundle("task-1", "AAPL", evidence)
        assert bundle.task_id == "task-1"
        assert bundle.ticker == "AAPL"
        assert len(bundle.evidence_items) == 2
        assert bundle.coverage_summary["fundamentals"] == 1
        assert bundle.coverage_summary["technical"] == 1

    def test_audit_uses_bundle_ticker_not_first_task_ticker(self):
        """audit() ticker-scoped: MSFT-only evidence audited with MSFT bundle ticker."""
        task = ResearchTask(
            request_text="Compare AAPL and MSFT",
            tickers=["AAPL", "MSFT"],
            task_type=TaskType.MULTI_TICKER_COMPARE,
        )
        # Evidence is for MSFT only (second ticker)
        msft_evidence = [
            new_evidence_item(
                task_id=task.task_id,
                subtask_id="sub-1",
                ticker="MSFT",
                agent_role=AgentRole.FUNDAMENTALS,
                claim="MSFT revenue growing",
            ),
            new_evidence_item(
                task_id=task.task_id,
                subtask_id="sub-2",
                ticker="MSFT",
                agent_role=AgentRole.TECHNICAL,
                claim="MSFT golden cross",
            ),
            new_evidence_item(
                task_id=task.task_id,
                subtask_id="sub-3",
                ticker="MSFT",
                agent_role=AgentRole.INDUSTRY,
                claim="MSFT sector outperformance",
            ),
        ]
        # Audit with explicit MSFT bundle ticker (not AAPL)
        result = self.orchestrator.audit(task, msft_evidence, bundle_ticker="MSFT")
        assert result["is_ready"] is True
        # If it had used task.tickers[0] (AAPL), it would report missing roles
        assert result["missing_roles"] == []

    def test_assemble_judge_packet_uses_bundle_ticker_not_first_task_ticker(self):
        """packet.ticker comes from bundle.ticker, not task.tickers[0]."""
        task = ResearchTask(
            request_text="Compare AAPL and MSFT",
            tickers=["AAPL", "MSFT"],
            output_mode=OutputMode.SIGNAL_AND_REPORT,
        )
        # Assemble bundle for MSFT (second ticker)
        msft_evidence = [
            new_evidence_item(
                task_id=task.task_id,
                subtask_id="sub-1",
                ticker="MSFT",
                agent_role=AgentRole.FUNDAMENTALS,
                claim="MSFT revenue up",
            ),
            new_evidence_item(
                task_id=task.task_id,
                subtask_id="sub-2",
                ticker="MSFT",
                agent_role=AgentRole.TECHNICAL,
                claim="MSFT golden cross",
            ),
        ]
        bundle = self.orchestrator.assemble_bundle(task.task_id, "MSFT", msft_evidence)
        packet = self.orchestrator.assemble_judge_packet(task, bundle)
        # packet ticker must be MSFT (from bundle), not AAPL (first in task.tickers)
        assert packet.ticker == "MSFT", f"Expected 'MSFT', got '{packet.ticker}'"

    def test_assemble_judge_packet_basic(self):
        task = ResearchTask(
            request_text="Analyze AAPL",
            tickers=["AAPL"],
            output_mode=OutputMode.SIGNAL_AND_REPORT,
        )
        bundle = EvidenceBundle(task_id=task.task_id, ticker="AAPL")
        packet = self.orchestrator.assemble_judge_packet(task, bundle)
        assert isinstance(packet, JudgeInputPacket)
        assert packet.task_id == task.task_id
        assert packet.ticker == "AAPL"
        assert packet.evidence_bundle == bundle

    def test_check_readiness_returns_tuple(self):
        bundle = EvidenceBundle(
            task_id="task-1",
            ticker="AAPL",
            coverage_summary={"fundamentals": 1, "technical": 1, "news": 1},
        )
        is_ready, missing = self.orchestrator.check_readiness(
            bundle, "single_ticker_research"
        )
        assert isinstance(is_ready, bool)
        assert isinstance(missing, list)

    def test_check_readiness_single_ticker_ready(self):
        """Single ticker task needs only fundamentals, technical, news."""
        bundle = EvidenceBundle(
            task_id="task-1",
            ticker="AAPL",
            coverage_summary={
                "fundamentals": 1,
                "technical": 1,
                "news": 1,
            },
        )
        is_ready, missing = self.orchestrator.check_readiness(
            bundle, "single_ticker_research"
        )
        assert is_ready is True
        assert missing == []

    def test_check_readiness_single_ticker_missing_news(self):
        """Single ticker task with missing news role reports news as missing."""
        bundle = EvidenceBundle(
            task_id="task-1",
            ticker="AAPL",
            coverage_summary={
                "fundamentals": 1,
                "technical": 1,
                # news intentionally omitted
            },
        )
        is_ready, missing = self.orchestrator.check_readiness(
            bundle, "single_ticker_research"
        )
        assert is_ready is False
        assert "news" in missing

    def test_check_readiness_option_idea_not_blocked_by_fundamentals(self):
        """Option idea task should not require fundamentals role."""
        bundle = EvidenceBundle(
            task_id="task-1",
            ticker="AAPL",
            coverage_summary={
                "technical": 1,
                "options": 1,
                "risk": 1,
            },
        )
        is_ready, missing = self.orchestrator.check_readiness(
            bundle, "option_idea"
        )
        assert is_ready is True
        assert AgentRole.FUNDAMENTALS not in missing
        assert "fundamentals" not in missing

    def test_check_readiness_multi_ticker_requires_industry(self):
        """Multi-ticker compare requires industry role, not news."""
        bundle = EvidenceBundle(
            task_id="task-1",
            ticker="AAPL",
            coverage_summary={
                "fundamentals": 1,
                "technical": 1,
                "industry": 1,
            },
        )
        is_ready, missing = self.orchestrator.check_readiness(
            bundle, "multi_ticker_compare"
        )
        assert is_ready is True
        # News should NOT be required for multi_ticker_compare
        assert AgentRole.NEWS not in missing
        assert "news" not in missing


class TestOrchestratorPhase4:
    """Phase 4: Full orchestrator workflow audit and boundary tests."""

    def setup_method(self):
        self.orchestrator = Orchestrator()

    def test_audit_returns_audit_dict(self):
        """audit() returns expected keys without producing judgment."""
        task = ResearchTask(
            request_text="Analyze AAPL",
            tickers=["AAPL"],
            task_type=TaskType.SINGLE_TICKER_RESEARCH,
        )
        evidence = [
            new_evidence_item(
                task_id=task.task_id,
                subtask_id="sub-1",
                ticker="AAPL",
                agent_role=AgentRole.FUNDAMENTALS,
                claim="Revenue up 8%",
                direction=Direction.BULLISH,
            ),
            new_evidence_item(
                task_id=task.task_id,
                subtask_id="sub-2",
                ticker="AAPL",
                agent_role=AgentRole.TECHNICAL,
                claim="Golden cross",
                direction=Direction.BULLISH,
            ),
            new_evidence_item(
                task_id=task.task_id,
                subtask_id="sub-3",
                ticker="AAPL",
                agent_role=AgentRole.NEWS,
                claim="Positive earnings",
                direction=Direction.BULLISH,
            ),
        ]
        result = self.orchestrator.audit(task, evidence)
        assert "is_ready" in result
        assert "missing_roles" in result
        assert "conflict_pairs" in result
        assert "orchestrator_notes" in result

    def test_audit_reports_missing_roles(self):
        """audit() reports missing roles when evidence is incomplete."""
        task = ResearchTask(
            request_text="Analyze AAPL",
            tickers=["AAPL"],
            task_type=TaskType.SINGLE_TICKER_RESEARCH,
        )
        evidence = [
            new_evidence_item(
                task_id=task.task_id,
                subtask_id="sub-1",
                ticker="AAPL",
                agent_role=AgentRole.FUNDAMENTALS,
                claim="Revenue up",
            ),
            # technical and news intentionally missing
        ]
        result = self.orchestrator.audit(task, evidence)
        assert result["is_ready"] is False
        assert "technical" in result["missing_roles"] or "news" in result["missing_roles"]

    def test_audit_reports_conflicts(self):
        """audit() detects and describes direction conflicts."""
        task = ResearchTask(
            request_text="Analyze AAPL",
            tickers=["AAPL"],
            task_type=TaskType.SINGLE_TICKER_RESEARCH,
        )
        evidence = [
            new_evidence_item(
                task_id=task.task_id,
                subtask_id="sub-1",
                ticker="AAPL",
                agent_role=AgentRole.FUNDAMENTALS,
                claim="Revenue growing",
                direction=Direction.BULLISH,
            ),
            new_evidence_item(
                task_id=task.task_id,
                subtask_id="sub-2",
                ticker="AAPL",
                agent_role=AgentRole.TECHNICAL,
                claim="RSI breakdown",
                direction=Direction.BEARISH,
            ),
            new_evidence_item(
                task_id=task.task_id,
                subtask_id="sub-3",
                ticker="AAPL",
                agent_role=AgentRole.NEWS,
                claim="Positive news",
                direction=Direction.NEUTRAL,
            ),
        ]
        result = self.orchestrator.audit(task, evidence)
        assert len(result["conflict_pairs"]) >= 1

    def test_audit_notes_are_workflow_observations_not_judgment(self):
        """orchestrator_notes contain workflow state, not final rating or report."""
        task = ResearchTask(
            request_text="Analyze AAPL",
            tickers=["AAPL"],
            task_type=TaskType.SINGLE_TICKER_RESEARCH,
        )
        evidence = [
            new_evidence_item(
                task_id=task.task_id,
                subtask_id="sub-1",
                ticker="AAPL",
                agent_role=AgentRole.FUNDAMENTALS,
                claim="Revenue up",
            ),
            new_evidence_item(
                task_id=task.task_id,
                subtask_id="sub-2",
                ticker="AAPL",
                agent_role=AgentRole.TECHNICAL,
                claim="Golden cross",
            ),
            new_evidence_item(
                task_id=task.task_id,
                subtask_id="sub-3",
                ticker="AAPL",
                agent_role=AgentRole.NEWS,
                claim="Positive news",
            ),
        ]
        result = self.orchestrator.audit(task, evidence)
        notes = result["orchestrator_notes"]
        # Notes must NOT contain final rating words
        rating_words = ["BUY", "SELL", "HOLD", "grade", "score"]
        for word in rating_words:
            assert word not in notes, f"Notes should not contain rating word '{word}'"

    def test_assemble_bundle_populates_conflict_flags(self):
        """assemble_bundle() now populates conflict_flags on the bundle."""
        evidence = [
            new_evidence_item(
                task_id="task-1",
                subtask_id="sub-1",
                ticker="AAPL",
                agent_role=AgentRole.FUNDAMENTALS,
                claim="Revenue growing",
                direction=Direction.BULLISH,
            ),
            new_evidence_item(
                task_id="task-1",
                subtask_id="sub-2",
                ticker="AAPL",
                agent_role=AgentRole.TECHNICAL,
                claim="RSI breakdown",
                direction=Direction.BEARISH,
            ),
        ]
        bundle = self.orchestrator.assemble_bundle("task-1", "AAPL", evidence)
        assert hasattr(bundle, "conflict_flags")
        assert len(bundle.conflict_flags) >= 1

    def test_assemble_judge_packet_with_audit_result(self):
        """assemble_judge_packet() incorporates audit_result orchestrator_notes."""
        task = ResearchTask(
            request_text="Analyze AAPL",
            tickers=["AAPL"],
            output_mode=OutputMode.SIGNAL_AND_REPORT,
        )
        evidence = [
            new_evidence_item(
                task_id=task.task_id,
                subtask_id="sub-1",
                ticker="AAPL",
                agent_role=AgentRole.FUNDAMENTALS,
                claim="Revenue up",
            ),
            new_evidence_item(
                task_id=task.task_id,
                subtask_id="sub-2",
                ticker="AAPL",
                agent_role=AgentRole.TECHNICAL,
                claim="Golden cross",
            ),
            new_evidence_item(
                task_id=task.task_id,
                subtask_id="sub-3",
                ticker="AAPL",
                agent_role=AgentRole.NEWS,
                claim="Positive news",
            ),
        ]
        audit_result = self.orchestrator.audit(task, evidence)
        bundle = self.orchestrator.assemble_bundle(task.task_id, "AAPL", evidence)
        packet = self.orchestrator.assemble_judge_packet(task, bundle, audit_result)
        assert packet.orchestrator_notes == audit_result["orchestrator_notes"]
        assert len(packet.conflict_flags) >= 0  # may or may not have conflicts
        assert len(packet.missing_steps) >= 0

    def test_orchestrator_does_not_produce_rating(self):
        """Orchestrator must never produce a final rating in any output."""
        task = ResearchTask(
            request_text="Analyze AAPL",
            tickers=["AAPL"],
        )
        evidence = [
            new_evidence_item(
                task_id=task.task_id,
                subtask_id="sub-1",
                ticker="AAPL",
                agent_role=AgentRole.FUNDAMENTALS,
                claim="Revenue up",
                direction=Direction.BULLISH,
            ),
            new_evidence_item(
                task_id=task.task_id,
                subtask_id="sub-2",
                ticker="AAPL",
                agent_role=AgentRole.TECHNICAL,
                claim="Golden cross",
                direction=Direction.BULLISH,
            ),
            new_evidence_item(
                task_id=task.task_id,
                subtask_id="sub-3",
                ticker="AAPL",
                agent_role=AgentRole.NEWS,
                claim="Positive news",
                direction=Direction.BULLISH,
            ),
        ]
        audit_result = self.orchestrator.audit(task, evidence)
        bundle = self.orchestrator.assemble_bundle(task.task_id, "AAPL", evidence)
        packet = self.orchestrator.assemble_judge_packet(task, bundle, audit_result)

        # Check all orchestrator outputs for rating words
        rating_words = ["BUY", "SELL", "HOLD", "grade", "score"]
        for word in rating_words:
            assert word not in audit_result["orchestrator_notes"]
            assert word not in bundle.conflict_flags
            assert word not in packet.orchestrator_notes

    def test_orchestrator_does_not_produce_canonical_report(self):
        """Orchestrator must never produce CanonicalReport fields."""
        task = ResearchTask(
            request_text="Analyze AAPL",
            tickers=["AAPL"],
        )
        evidence = [
            new_evidence_item(
                task_id=task.task_id,
                subtask_id="sub-1",
                ticker="AAPL",
                agent_role=AgentRole.FUNDAMENTALS,
                claim="Revenue up",
            ),
        ]
        audit_result = self.orchestrator.audit(task, evidence)
        bundle = self.orchestrator.assemble_bundle(task.task_id, "AAPL", evidence)
        packet = self.orchestrator.assemble_judge_packet(task, bundle, audit_result)

        report_words = [
            "executive_summary", "bottom_line", "bull_case",
            "bear_case", "trade_plan", "risk_watch",
        ]
        notes = audit_result["orchestrator_notes"] + " " + packet.orchestrator_notes
        for word in report_words:
            assert word not in notes.lower()


class TestRequiredRolesMapping:
    """Verify required roles are defined for all task types."""

    def test_all_task_types_have_required_roles(self):
        for task_type in TaskType:
            assert task_type.value in REQUIRED_ROLES_BY_TASK_TYPE
            roles = REQUIRED_ROLES_BY_TASK_TYPE[task_type.value]
            assert len(roles) > 0
            assert all(isinstance(r, AgentRole) for r in roles)
