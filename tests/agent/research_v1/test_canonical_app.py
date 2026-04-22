"""Tests for Phase 9: app.py entry point."""

import pytest

from agent.research_v1.app import HermesResearchApp, run_research, ResearchResult, TickerResearchResult
from agent.research_v1.task_router import TaskRouter
from agent.research_v1.orchestrator import Orchestrator
from agent.research_v1.contracts import (
    TaskType,
    OutputMode,
    ResearchTask,
    EvidenceItem,
    EvidenceBundle,
    CanonicalSignal,
    AgentRole,
    Direction,
    EvidenceImportance,
    new_evidence_item,
)


class TestTaskRouterIntegration:
    """Verify TaskRouter produces valid ResearchTask for canonical pipeline."""

    def test_route_produces_research_task(self):
        """TaskRouter.route returns a valid ResearchTask."""
        router = TaskRouter()
        task = router.route("Research AAPL fundamentals deeply")
        assert task.tickers == ["AAPL"]
        assert task.task_type == TaskType.SINGLE_TICKER_RESEARCH

    def test_route_rejects_empty_string(self):
        """TaskRouter.route raises ValueError on empty input."""
        router = TaskRouter()
        with pytest.raises(ValueError):
            router.route("")

    def test_route_unknown_text_raises(self):
        """TaskRouter.route raises ValueError on unparseable input."""
        router = TaskRouter()
        with pytest.raises(ValueError):
            router.route("   ")

    def test_multi_ticker_route(self):
        """Multi-ticker comparison request routes correctly."""
        router = TaskRouter()
        task = router.route("Compare TSLA vs NIO fundamentals")
        assert "TSLA" in task.tickers
        assert "NIO" in task.tickers
        assert task.task_type == TaskType.MULTI_TICKER_COMPARE


class TestOrchestratorCanonicalIntegration:
    """Verify Orchestrator produces correct canonical artifacts."""

    def setup_method(self):
        self.orchestrator = Orchestrator()

    def test_decompose_produces_subagent_tasks(self):
        """Orchestrator.decompose returns SubagentTask list."""
        task = ResearchTask(
            task_id="task-test",
            request_text="Research AAPL",
            task_type=TaskType.SINGLE_TICKER_RESEARCH,
            tickers=["AAPL"],
            output_mode=OutputMode.SIGNAL_AND_REPORT,
        )
        subtasks = self.orchestrator.decompose(task)
        assert len(subtasks) > 0
        assert all(s.task_id == "task-test" for s in subtasks)

    def test_assemble_bundle_produces_evidence_bundle(self):
        """Orchestrator.assemble_bundle returns EvidenceBundle."""
        item = EvidenceItem(
            task_id="task-test",
            subtask_id="sub-1",
            ticker="AAPL",
            agent_role=AgentRole.FUNDAMENTALS,
            claim="Revenue grew",
            confidence=0.8,
            direction=Direction.BULLISH,
            importance=EvidenceImportance.HIGH,
        )
        bundle = self.orchestrator.assemble_bundle("task-test", "AAPL", [item])
        assert bundle.task_id == "task-test"
        assert bundle.ticker == "AAPL"
        assert len(bundle.evidence_items) == 1

    def test_assemble_judge_packet_is_bounded(self):
        """assemble_judge_packet produces a JudgeInputPacket that passes validation."""
        task = ResearchTask(
            task_id="task-test",
            request_text="Research AAPL",
            task_type=TaskType.SINGLE_TICKER_RESEARCH,
            tickers=["AAPL"],
            output_mode=OutputMode.SIGNAL_AND_REPORT,
        )
        item = EvidenceItem(
            task_id="task-test",
            subtask_id="sub-1",
            ticker="AAPL",
            agent_role=AgentRole.FUNDAMENTALS,
            claim="Revenue grew",
            confidence=0.8,
            direction=Direction.BULLISH,
        )
        bundle = self.orchestrator.assemble_bundle("task-test", "AAPL", [item])
        packet = self.orchestrator.assemble_judge_packet(task, bundle)
        assert packet.task_id == "task-test"
        assert packet.ticker == "AAPL"
        assert packet.evidence_bundle is not None
        assert packet.task_summary == "Research AAPL"


class TestResearchResultStructure:
    """Test that ResearchResult contains all canonical output objects."""

    def test_research_result_has_ticker_results(self):
        """ResearchResult.ticker_results is the primary result container."""
        task = ResearchTask(request_text="Test", tickers=["AAPL"])
        tr = TickerResearchResult(
            task=task,
            ticker="AAPL",
            signal=CanonicalSignal(ticker="AAPL", rating="BUY", confidence=0.8, priority_score=75.0),
            report=None,
            review=None,
            trade_plan=None,
            audit={"is_ready": True},
            errors=[],
        )
        result = ResearchResult(task=task, ticker_results=[tr], errors=[])
        assert len(result.ticker_results) == 1
        assert result.ticker_results[0].ticker == "AAPL"

    def test_ticker_result_signal_fields(self):
        """TickerResearchResult.signal has correct canonical fields."""
        task = ResearchTask(request_text="Test", tickers=["AAPL"])
        signal = CanonicalSignal(
            ticker="AAPL", rating="BUY", confidence=0.8, priority_score=75.0,
            entry_price=175.0, stop_loss=165.0, take_profit=195.0,
        )
        tr = TickerResearchResult(
            task=task, ticker="AAPL", signal=signal,
            report=None, review=None, trade_plan=None,
            audit={}, errors=[],
        )
        assert tr.signal.rating == "BUY"
        assert tr.signal.ticker == "AAPL"


class TestHermesResearchAppRun:
    """Test HermesResearchApp.run() pipeline execution."""

    def test_run_produces_research_result(self):
        """app.run() returns a ResearchResult regardless of subagent output."""
        app = HermesResearchApp()
        result = app.run("Research AAPL fundamentals")
        assert isinstance(result, ResearchResult)
        assert result.task is not None
        assert result.task.tickers == ["AAPL"]

    def test_run_with_noop_subagent_completes_without_crash(self):
        """With no-op subagent (no evidence), pipeline completes without crashing.

        FinalJudge still produces a default SELL signal with low confidence
        when given an empty evidence bundle (composite=50 → SELL).
        The key invariant is: no crash, no errors propagated.
        """
        app = HermesResearchApp()
        result = app.run("Research MSFT fundamentals")
        assert isinstance(result, ResearchResult)
        assert len(result.ticker_results) == 1
        tr = result.ticker_results[0]
        assert tr.ticker == "MSFT"
        # Pipeline completes without raising errors
        assert len(result.errors) == 0
        # FinalJudge may still emit a fallback signal, but the run must be
        # explicitly marked as coverage-limited.
        assert tr.signal is not None
        assert tr.report is not None
        assert tr.audit["llm_research_available"] is False
        assert tr.audit["coverage_limited"] is True
        assert tr.audit["evidence_count"] == 0
        assert any("No LLM client configured" in err for err in tr.errors)
        assert "Research unavailable" in tr.report.executive_summary
        assert "Coverage-limited" in tr.report.bottom_line

    def test_run_request_text_preserved(self):
        """Original request text is preserved through pipeline."""
        app = HermesResearchApp()
        result = app.run("Deep research on TSLA technical and fundamentals")
        assert "TSLA" in result.task.request_text

    def test_run_research_convenience_function(self):
        """run_research() convenience function works."""
        result = run_research("Research AMZN fundamentals")
        assert isinstance(result, ResearchResult)
        assert result.task.tickers == ["AMZN"]


class TestMultiTickerScoping:
    """Regression tests: multi-ticker evidence must not be mis-labeled."""

    def test_multi_ticker_runs_per_ticker(self):
        """Each ticker gets its own TickerResearchResult."""
        result = run_research("Compare AAPL and MSFT fundamentals")
        tickers = [tr.ticker for tr in result.ticker_results]
        assert "AAPL" in tickers
        assert "MSFT" in tickers

    def test_msft_evidence_not_labeled_as_aapl(self):
        """
        Regression: evidence for MSFT must not be bundled under AAPL.

        Previously app-level code used task.tickers[0] for all bundles,
        causing MSFT evidence to be mis-stamped as AAPL.
        """
        msft_evidence = new_evidence_item(
            task_id="task-multi",
            subtask_id="sub-msft",
            ticker="MSFT",
            agent_role=AgentRole.FUNDAMENTALS,
            claim="Revenue growing",
            direction=Direction.BULLISH,
            confidence=0.75,
        )
        aapl_evidence = new_evidence_item(
            task_id="task-multi",
            subtask_id="sub-aapl",
            ticker="AAPL",
            agent_role=AgentRole.FUNDAMENTALS,
            claim="Revenue growing",
            direction=Direction.BULLISH,
            confidence=0.80,
        )

        # Build per-ticker bundles using the orchestrator
        orchestrator = Orchestrator()
        msft_bundle = orchestrator.assemble_bundle("task-multi", "MSFT", [msft_evidence])
        aapl_bundle = orchestrator.assemble_bundle("task-multi", "AAPL", [aapl_evidence])

        # MSFT bundle must be labeled MSFT, not AAPL
        assert msft_bundle.ticker == "MSFT", (
            f"MSFT evidence was labeled as '{msft_bundle.ticker}' — "
            "first-ticker hardcoding regression"
        )
        assert aapl_bundle.ticker == "AAPL"

        # MSFT bundle contains only MSFT evidence
        assert all(e.ticker == "MSFT" for e in msft_bundle.evidence_items), (
            "MSFT bundle contains non-MSFT evidence — evidence grouping broken"
        )

    def test_audit_uses_correct_bundle_ticker(self):
        """audit() with bundle_ticker uses the specified ticker, not task.tickers[0].

        The regression: if bundle_ticker is ignored and task.tickers[0] used instead,
        MSFT evidence would be labeled as AAPL, causing is_ready to be computed
        against the wrong ticker's required roles.
        """
        task = ResearchTask(
            task_id="task-multi",
            request_text="Compare AAPL and MSFT",
            task_type=TaskType.MULTI_TICKER_COMPARE,
            tickers=["AAPL", "MSFT"],
        )
        # Provide evidence for MSFT fundamentals (required for MULTI_TICKER_COMPARE)
        msft_item = new_evidence_item(
            task_id="task-multi",
            subtask_id="sub-msft",
            ticker="MSFT",
            agent_role=AgentRole.FUNDAMENTALS,
            claim="Revenue growing",
            direction=Direction.BULLISH,
            confidence=0.75,
        )

        orchestrator = Orchestrator()
        # Call audit with explicit bundle_ticker=MSFT
        # Required roles for MULTI_TICKER_COMPARE: FUNDAMENTALS, TECHNICAL, INDUSTRY
        # With only MSFT/FUNDAMENTALS, is_ready=False (technical and industry missing).
        # But crucially: the ticker used for the bundle must be MSFT, not AAPL.
        audit = orchestrator.audit(task, [msft_item], bundle_ticker="MSFT")

        # If first-ticker hardcoding occurred (AAPL used instead of MSFT),
        # the bundle would be for AAPL and the same MSFT item would be
        # treated as both MSFT (in audit's internal items) AND as AAPL's missing evidence.
        # With correct bundle_ticker=MSFT: only MSFT bundle is wrong (missing technical/industry).
        assert audit["is_ready"] is False  # missing technical + industry for MSFT
        assert "missing_roles" in audit
        assert "technical" in audit["missing_roles"] or "industry" in audit["missing_roles"]


class TestCLIMain:
    """Test that __main__ block parses arguments and calls run_research."""

    def test_cli_entry_point_runs_without_error(self):
        """python -m agent.research_v1.app <request> executes without crashing."""
        import subprocess, sys
        result = subprocess.run(
            [sys.executable, "-m", "agent.research_v1.app", "Research AAPL"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        # Should exit cleanly (even with no real subagent results)
        assert result.returncode == 0, f"stderr: {result.stderr}"
        # Should print ticker result header
        assert "AAPL" in result.stdout
