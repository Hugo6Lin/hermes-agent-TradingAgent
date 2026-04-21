"""Tests for canonical contracts."""
import pytest
from datetime import datetime

from agent.research_v1.contracts import (
    ResearchTask,
    SubagentTask,
    EvidenceItem,
    EvidenceBundle,
    JudgeInputPacket,
    CanonicalSignal,
    CanonicalReport,
    TradePlan,
    TaskType,
    OutputMode,
    ResearchMode,
    AgentRole,
    ClaimType,
    Direction,
    EvidenceImportance,
    TaskStatus,
    new_research_task,
    new_subagent_task,
    new_evidence_item,
)


class TestResearchTask:
    def test_create_minimal_task(self):
        task = ResearchTask(
            request_text="Research AAPL fundamentals",
            tickers=["AAPL"],
        )
        assert task.request_text == "Research AAPL fundamentals"
        assert task.tickers == ["AAPL"]
        assert task.task_type == TaskType.SINGLE_TICKER_RESEARCH
        assert task.status == TaskStatus.PENDING

    def test_create_full_task(self):
        task = ResearchTask(
            request_text="Compare AAPL vs MSFT",
            tickers=["AAPL", "MSFT"],
            task_type=TaskType.MULTI_TICKER_COMPARE,
            markets=["US"],
            research_mode=ResearchMode.DEEP,
            time_horizon="3months",
            output_mode=OutputMode.SIGNAL_AND_REPORT,
        )
        assert task.tickers == ["AAPL", "MSFT"]
        assert task.task_type == TaskType.MULTI_TICKER_COMPARE
        assert task.research_mode == ResearchMode.DEEP

    def test_task_requires_request_text(self):
        with pytest.raises(ValueError, match="request_text is required"):
            ResearchTask(request_text="", tickers=["AAPL"])

    def test_task_requires_tickers(self):
        with pytest.raises(ValueError, match="at least one ticker is required"):
            ResearchTask(request_text="Test", tickers=[])

    def test_factory_function(self):
        task = new_research_task(
            request_text="Quick research",
            tickers=["TSLA"],
            task_type=TaskType.SINGLE_TICKER_RESEARCH,
        )
        assert task.tickers == ["TSLA"]


class TestSubagentTask:
    def test_create_subagent_task(self):
        task = SubagentTask(
            task_id="task-123",
            agent_role=AgentRole.FUNDAMENTALS,
            ticker="AAPL",
            objective="Analyze revenue growth",
        )
        assert task.task_id == "task-123"
        assert task.agent_role == AgentRole.FUNDAMENTALS
        assert task.ticker == "AAPL"

    def test_subagent_task_requires_task_id(self):
        with pytest.raises(ValueError, match="task_id is required"):
            SubagentTask(
                task_id="",
                agent_role=AgentRole.FUNDAMENTALS,
                ticker="AAPL",
                objective="Test",
            )

    def test_subagent_task_requires_ticker(self):
        with pytest.raises(ValueError, match="ticker is required"):
            SubagentTask(
                task_id="task-123",
                agent_role=AgentRole.FUNDAMENTALS,
                ticker="",
                objective="Test",
            )

    def test_subagent_task_requires_objective(self):
        with pytest.raises(ValueError, match="objective is required"):
            SubagentTask(
                task_id="task-123",
                agent_role=AgentRole.FUNDAMENTALS,
                ticker="AAPL",
                objective="",
            )

    def test_factory_function(self):
        task = new_subagent_task(
            task_id="task-456",
            agent_role=AgentRole.TECHNICAL,
            ticker="MSFT",
            objective="Analyze chart patterns",
        )
        assert task.agent_role == AgentRole.TECHNICAL


class TestEvidenceItem:
    def test_create_evidence_item(self):
        item = EvidenceItem(
            task_id="task-123",
            subtask_id="subtask-456",
            ticker="AAPL",
            agent_role=AgentRole.FUNDAMENTALS,
            claim="Revenue grew 8% YoY",
            confidence=0.85,
            direction=Direction.BULLISH,
        )
        assert item.claim == "Revenue grew 8% YoY"
        assert item.confidence == 0.85
        assert item.direction == Direction.BULLISH
        assert item.subtask_id == "subtask-456"

    def test_evidence_item_requires_task_id(self):
        with pytest.raises(ValueError, match="task_id is required"):
            EvidenceItem(
                task_id="",
                subtask_id="subtask-456",
                ticker="AAPL",
                agent_role=AgentRole.FUNDAMENTALS,
                claim="Test",
            )

    def test_evidence_item_requires_subtask_id(self):
        with pytest.raises(ValueError, match="subtask_id is required"):
            EvidenceItem(
                task_id="task-123",
                subtask_id="",
                ticker="AAPL",
                agent_role=AgentRole.FUNDAMENTALS,
                claim="Test",
            )

    def test_evidence_item_requires_ticker(self):
        with pytest.raises(ValueError, match="ticker is required"):
            EvidenceItem(
                task_id="task-123",
                subtask_id="subtask-456",
                ticker="",
                agent_role=AgentRole.FUNDAMENTALS,
                claim="Test",
            )

    def test_evidence_item_requires_claim(self):
        with pytest.raises(ValueError, match="claim is required"):
            EvidenceItem(
                task_id="task-123",
                subtask_id="subtask-456",
                ticker="AAPL",
                agent_role=AgentRole.FUNDAMENTALS,
                claim="",
            )

    def test_evidence_item_confidence_bounds(self):
        with pytest.raises(ValueError, match="confidence must be between"):
            EvidenceItem(
                task_id="task-123",
                subtask_id="subtask-456",
                ticker="AAPL",
                agent_role=AgentRole.FUNDAMENTALS,
                claim="Test",
                confidence=1.5,
            )

    def test_factory_function(self):
        item = new_evidence_item(
            task_id="task-789",
            subtask_id="subtask-001",
            ticker="GOOG",
            agent_role=AgentRole.TECHNICAL,
            claim="Golden cross detected",
            confidence=0.75,
        )
        assert item.claim == "Golden cross detected"

    def test_evidence_item_raw_payload_preserved(self):
        raw = {"原始数据": "test", "nested": {"key": "value"}}
        item = EvidenceItem(
            task_id="task-123",
            subtask_id="subtask-456",
            ticker="AAPL",
            agent_role=AgentRole.NEWS,
            claim="News event detected",
            raw_payload=raw,
        )
        assert item.raw_payload == raw


class TestEvidenceBundle:
    def test_create_evidence_bundle(self):
        bundle = EvidenceBundle(
            task_id="task-123",
            ticker="AAPL",
        )
        assert bundle.task_id == "task-123"
        assert bundle.ticker == "AAPL"
        assert bundle.evidence_items == []

    def test_bundle_requires_task_id(self):
        with pytest.raises(ValueError, match="task_id is required"):
            EvidenceBundle(task_id="", ticker="AAPL")

    def test_bundle_requires_ticker(self):
        with pytest.raises(ValueError, match="ticker is required"):
            EvidenceBundle(task_id="task-123", ticker="")

    def test_bundle_with_evidence_items(self):
        item1 = EvidenceItem(
            task_id="task-123",
            subtask_id="subtask-001",
            ticker="AAPL",
            agent_role=AgentRole.FUNDAMENTALS,
            claim="Claim 1",
        )
        item2 = EvidenceItem(
            task_id="task-123",
            subtask_id="subtask-002",
            ticker="AAPL",
            agent_role=AgentRole.TECHNICAL,
            claim="Claim 2",
        )
        bundle = EvidenceBundle(
            task_id="task-123",
            ticker="AAPL",
            evidence_items=[item1, item2],
            coverage_summary={"fundamentals": 1, "technical": 1},
        )
        assert len(bundle.evidence_items) == 2


class TestJudgeInputPacket:
    def test_create_judge_input_packet(self):
        bundle = EvidenceBundle(task_id="task-123", ticker="AAPL")
        packet = JudgeInputPacket(
            task_id="task-123",
            ticker="AAPL",
            task_summary="Research on AAPL",
            evidence_bundle=bundle,
            required_outputs=["signal", "report"],
        )
        assert packet.task_id == "task-123"
        assert packet.evidence_bundle == bundle

    def test_packet_requires_task_id(self):
        with pytest.raises(ValueError, match="task_id is required"):
            JudgeInputPacket(task_id="", ticker="AAPL", task_summary="summary", evidence_bundle=EvidenceBundle(task_id="x", ticker="AAPL"))

    def test_packet_requires_ticker(self):
        with pytest.raises(ValueError, match="ticker is required"):
            JudgeInputPacket(task_id="task-123", ticker="", task_summary="summary", evidence_bundle=EvidenceBundle(task_id="x", ticker="x"))

    def test_packet_requires_task_summary(self):
        with pytest.raises(ValueError, match="task_summary is required"):
            JudgeInputPacket(task_id="task-123", ticker="AAPL", task_summary="", evidence_bundle=EvidenceBundle(task_id="x", ticker="AAPL"))

    def test_packet_requires_evidence_bundle(self):
        with pytest.raises(ValueError, match="evidence_bundle is required"):
            JudgeInputPacket(task_id="task-123", ticker="AAPL", task_summary="summary", evidence_bundle=None)


class TestCanonicalSignal:
    def test_create_canonical_signal(self):
        signal = CanonicalSignal(
            ticker="AAPL",
            rating="BUY",
            confidence=0.80,
            priority_score=75.0,
            decision_reason="Strong fundamentals, bullish technicals",
        )
        assert signal.ticker == "AAPL"
        assert signal.rating == "BUY"
        assert signal.confidence == 0.80

    def test_signal_requires_ticker(self):
        with pytest.raises(ValueError, match="ticker is required"):
            CanonicalSignal(ticker="", rating="BUY")

    def test_signal_requires_rating(self):
        with pytest.raises(ValueError, match="rating is required"):
            CanonicalSignal(ticker="AAPL", rating="")

    def test_signal_confidence_bounds(self):
        with pytest.raises(ValueError, match="confidence must be between"):
            CanonicalSignal(ticker="AAPL", rating="BUY", confidence=-0.1)

    def test_signal_priority_score_bounds(self):
        with pytest.raises(ValueError, match="priority_score must be between"):
            CanonicalSignal(ticker="AAPL", rating="BUY", priority_score=150.0)

    def test_signal_with_risk_flags(self):
        signal = CanonicalSignal(
            ticker="AAPL",
            rating="BUY",
            risk_flags=["earnings_volatility", "sector_headwinds"],
        )
        assert "earnings_volatility" in signal.risk_flags


class TestCanonicalReport:
    def test_create_canonical_report(self):
        report = CanonicalReport(
            title="AAPL Research Report",
            bottom_line="BUY AAPL based on strong fundamentals",
            executive_summary="Strong buy based on revenue growth and technical breakout.",
            why_now="Recent earnings beat and bullish chart pattern.",
            bull_case="Revenue growth accelerating, new product cycle ahead.",
            bear_case="Valuation stretched, sector headwinds remain.",
        )
        assert report.title == "AAPL Research Report"
        assert report.bottom_line == "BUY AAPL based on strong fundamentals"
        assert report.executive_summary.startswith("Strong buy")

    def test_report_requires_title(self):
        with pytest.raises(ValueError, match="title is required"):
            CanonicalReport(
                title="",
                bottom_line="Test",
                executive_summary="Summary",
                why_now="Why",
                bull_case="Bull",
                bear_case="Bear",
            )

    def test_report_requires_bottom_line(self):
        with pytest.raises(ValueError, match="bottom_line is required"):
            CanonicalReport(
                title="Test",
                bottom_line="",
                executive_summary="Summary",
                why_now="Why",
                bull_case="Bull",
                bear_case="Bear",
            )

    def test_report_requires_executive_summary(self):
        with pytest.raises(ValueError, match="executive_summary is required"):
            CanonicalReport(
                title="Test",
                bottom_line="Bottom",
                executive_summary="",
                why_now="Why",
                bull_case="Bull",
                bear_case="Bear",
            )

    def test_report_requires_why_now(self):
        with pytest.raises(ValueError, match="why_now is required"):
            CanonicalReport(
                title="Test",
                bottom_line="Bottom",
                executive_summary="Summary",
                why_now="",
                bull_case="Bull",
                bear_case="Bear",
            )

    def test_report_requires_bull_case(self):
        with pytest.raises(ValueError, match="bull_case is required"):
            CanonicalReport(
                title="Test",
                bottom_line="Bottom",
                executive_summary="Summary",
                why_now="Why",
                bull_case="",
                bear_case="Bear",
            )

    def test_report_requires_bear_case(self):
        with pytest.raises(ValueError, match="bear_case is required"):
            CanonicalReport(
                title="Test",
                bottom_line="Bottom",
                executive_summary="Summary",
                why_now="Why",
                bull_case="Bull",
                bear_case="",
            )

    def test_report_with_trade_plan(self):
        trade_plan = TradePlan(
            action="BUY",
            entry_price=175.00,
            stop_loss=165.00,
            take_profit=195.00,
        )
        report = CanonicalReport(
            title="AAPL Report",
            bottom_line="BUY",
            executive_summary="Summary",
            why_now="Why",
            bull_case="Bull",
            bear_case="Bear",
            trade_plan=trade_plan,
        )
        assert report.trade_plan.action == "BUY"
        assert report.trade_plan.entry_price == 175.00

    def test_report_with_risk_watch(self):
        report = CanonicalReport(
            title="Test",
            bottom_line="HOLD",
            executive_summary="Summary",
            why_now="Why",
            bull_case="Bull",
            bear_case="Bear",
            risk_watch=["interest_rate", "consumer_spending"],
        )
        assert len(report.risk_watch) == 2


class TestTradePlan:
    def test_create_trade_plan(self):
        plan = TradePlan(
            action="BUY",
            entry_price=150.00,
            stop_loss=140.00,
            take_profit=170.00,
            holding_period="3months",
        )
        assert plan.action == "BUY"
        assert plan.entry_price == 150.00

    def test_trade_plan_optional_fields(self):
        plan = TradePlan(action="HOLD")
        assert plan.action == "HOLD"
        assert plan.entry_price is None


class TestEnums:
    def test_task_types(self):
        assert TaskType.SINGLE_TICKER_RESEARCH.value == "single_ticker_research"
        assert TaskType.OPTION_IDEA.value == "option_idea"

    def test_agent_roles(self):
        assert AgentRole.FUNDAMENTALS.value == "fundamentals"
        assert AgentRole.TECHNICAL.value == "technical"
        assert AgentRole.RISK.value == "risk"

    def test_directions(self):
        assert Direction.BULLISH.value == "bullish"
        assert Direction.BEARISH.value == "bearish"
        assert Direction.NEUTRAL.value == "neutral"

    def test_claim_types(self):
        assert ClaimType.FACTUAL.value == "factual"
        assert ClaimType.DIRECTIONAL.value == "directional"

    def test_evidence_importance(self):
        assert EvidenceImportance.CRITICAL.value == "critical"
        assert EvidenceImportance.HIGH.value == "high"
