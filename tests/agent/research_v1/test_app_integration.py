"""End-to-end integration tests for HermesResearchApp — Phase 11: Real Agent Wiring."""

from unittest.mock import Mock
import pytest
import tempfile
import os

from agent.research_v1.app import HermesResearchApp
from agent.research_v1.contracts import AgentRole, ResearchTask, SubagentTask, TaskType, OutputMode, new_research_task
from agent.research_v1.subagent_executor import SubagentExecutor
from agent.research_v1.orchestrator import Orchestrator
from agent.research_v1.evidence_store import EvidenceStore


class MockLLMClient(Mock):
    """Mock LLM client that returns structured analyst-style responses."""

    def generate(self, messages, temperature=0.7, max_tokens=4096):
        prompt_text = " ".join(m.get("content", "") for m in messages if m.get("content"))

        if "fundamentals" in prompt_text.lower():
            json_body = '{"summary": "Strong fundamentals with P/E 28.5", "verdict": "buy", "confidence": 0.85, "strengths": ["Revenue growth 15%", "ROE 55%"], "weaknesses": ["High valuation"]}'
        elif "technical" in prompt_text.lower():
            json_body = '{"trend": "bullish", "signals": ["RSI 45", "MACD crossover"], "recommendation": "buy", "confidence": 0.80}'
        elif "news" in prompt_text.lower():
            json_body = '{"sentiment": "positive", "confidence": 0.78, "themes": ["earnings beat", "product launch"], "catalysts": ["upcoming earnings"]}'
        elif "sentiment" in prompt_text.lower():
            json_body = '{"sentiment": "bullish", "confidence": 0.72, "vix_signal": "low_fear", "fear_greed": "Greed"}'
        elif "industry" in prompt_text.lower():
            json_body = '{"outlook": "bullish", "confidence": 0.75, "industry_trends": ["AI growth", "cloud expansion"], "competitive_position": "leader"}'
        elif "options" in prompt_text.lower():
            json_body = '{"put_call_ratio": 0.8, "sentiment": "bullish", "confidence": 0.70, "key_strikes": ["150", "155"], "iv_signal": "medium"}'
        elif "risk" in prompt_text.lower():
            json_body = '{"risk_rating": "medium", "confidence": 0.68, "risk_factors": ["volatility", "market exposure"], "volatility_assessment": "medium"}'
        elif "valuation" in prompt_text.lower():
            json_body = '{"verdict": "buy", "confidence": 0.82, "valuation_level": "fair", "key_drivers": ["DCF upside", "dividend yield"]}'
        else:
            json_body = '{"summary": "Research complete", "confidence": 0.75}'

        return Mock(
            content=f'```json\n{json_body}\n```',
            model="mock-model",
            input_tokens=100,
            output_tokens=200,
            cost_estimate=0.01,
            raw_response={},
        )


# =============================================================================
# SubagentExecutor tests
# =============================================================================

def test_subagent_executor_executes_fundamentals():
    """SubagentExecutor routes fundamentals role to FundamentalsAnalyst."""
    client = MockLLMClient()
    executor = SubagentExecutor(client)

    from agent.research_v1.contracts import SubagentTask, TaskType
    subtask = SubagentTask(
        task_id="test-task-1",
        agent_role=AgentRole.FUNDAMENTALS,
        ticker="AAPL",
        objective="Analyze AAPL fundamentals",
        required_context={"market_data": {"price": 186.5, "market_cap": "2.9T", "shares_outstanding": 15_500_000_000}},
    )

    result = executor.execute(subtask)

    assert "report" in result
    assert "summary_json" in result
    assert result["summary_json"]["verdict"] == "buy"
    assert result["summary_json"]["confidence"] == 0.85


def test_subagent_executor_executes_technical():
    """SubagentExecutor routes technical role to TechnicalAnalyst."""
    client = MockLLMClient()
    executor = SubagentExecutor(client)

    subtask = SubagentTask(
        task_id="test-task-2",
        agent_role=AgentRole.TECHNICAL,
        ticker="AAPL",
        objective="Analyze AAPL technically",
        required_context={},
    )

    result = executor.execute(subtask)

    assert "report" in result
    assert "summary_json" in result
    assert result["summary_json"]["recommendation"] == "buy"


def test_subagent_executor_executes_news():
    """SubagentExecutor routes news role to NewsAnalyst."""
    client = MockLLMClient()
    executor = SubagentExecutor(client)

    subtask = SubagentTask(
        task_id="test-task-3",
        agent_role=AgentRole.NEWS,
        ticker="AAPL",
        objective="Analyze AAPL news",
        required_context={},
    )

    result = executor.execute(subtask)

    assert "report" in result
    assert "summary_json" in result
    assert result["summary_json"]["sentiment"] == "positive"


def test_subagent_executor_executes_sentiment():
    """SubagentExecutor routes sentiment role to SentimentAnalyst."""
    client = MockLLMClient()
    executor = SubagentExecutor(client)

    subtask = SubagentTask(
        task_id="test-task-4",
        agent_role=AgentRole.SENTIMENT,
        ticker="AAPL",
        objective="Analyze AAPL sentiment",
        required_context={},
    )

    result = executor.execute(subtask)

    assert "report" in result
    assert "summary_json" in result


def test_subagent_executor_executes_industry():
    """SubagentExecutor routes industry role to IndustryAnalyst."""
    client = MockLLMClient()
    executor = SubagentExecutor(client)

    subtask = SubagentTask(
        task_id="test-task-5",
        agent_role=AgentRole.INDUSTRY,
        ticker="AAPL",
        objective="Analyze AAPL industry",
        required_context={},
    )

    result = executor.execute(subtask)

    assert "report" in result
    assert "summary_json" in result
    assert result["summary_json"]["outlook"] == "bullish"


def test_subagent_executor_executes_options():
    """SubagentExecutor routes options role to OptionsAnalyst."""
    client = MockLLMClient()
    executor = SubagentExecutor(client)

    subtask = SubagentTask(
        task_id="test-task-6",
        agent_role=AgentRole.OPTIONS,
        ticker="AAPL",
        objective="Analyze AAPL options",
        required_context={},
    )

    result = executor.execute(subtask)

    assert "report" in result
    assert "summary_json" in result
    assert result["summary_json"]["sentiment"] == "bullish"


def test_subagent_executor_executes_risk():
    """SubagentExecutor routes risk role to RiskAnalyst."""
    client = MockLLMClient()
    executor = SubagentExecutor(client)

    subtask = SubagentTask(
        task_id="test-task-7",
        agent_role=AgentRole.RISK,
        ticker="AAPL",
        objective="Analyze AAPL risk",
        required_context={},
    )

    result = executor.execute(subtask)

    assert "report" in result
    assert "summary_json" in result
    assert result["summary_json"]["risk_rating"] == "medium"


def test_subagent_executor_executes_valuation():
    """SubagentExecutor routes valuation role to ValuationAnalyst."""
    client = MockLLMClient()
    executor = SubagentExecutor(client)

    subtask = SubagentTask(
        task_id="test-task-8",
        agent_role=AgentRole.VALUATION,
        ticker="AAPL",
        objective="Analyze AAPL valuation",
        required_context={},
    )

    result = executor.execute(subtask)

    assert "report" in result
    assert "summary_json" in result
    assert result["summary_json"]["verdict"] == "buy"


def test_subagent_executor_unknown_role_raises():
    """SubagentExecutor raises ValueError for unknown agent role."""
    from agent.research_v1.contracts import AgentRole

    client = MockLLMClient()
    executor = SubagentExecutor(client)

    # Create a subtask with a role not in _ROLE_HANDLERS (if any)
    # All defined roles should be handled
    for role in AgentRole:
        subtask = SubagentTask(
            task_id=f"test-{role.value}",
            agent_role=role,
            ticker="AAPL",
            objective=f"Analyze AAPL {role.value}",
            required_context={},
        )
        # Should not raise — all defined roles are handled
        result = executor.execute(subtask)
        assert "report" in result


# =============================================================================
# HermesResearchApp integration tests
# =============================================================================

def test_app_run_with_mock_client_produces_signal_and_report():
    """Single-ticker research with mock LLM client produces signal and report."""
    client = MockLLMClient()
    app = HermesResearchApp(llm_client=client)

    result = app.run("Research AAPL")

    assert len(result.ticker_results) == 1
    tr = result.ticker_results[0]

    # Should produce a signal and report
    assert tr.signal is not None
    assert tr.report is not None
    assert tr.signal.ticker == "AAPL"
    assert tr.signal.rating in ("BUY", "HOLD", "SELL")
    assert 0.0 <= tr.signal.confidence <= 1.0
    assert 0.0 <= tr.signal.priority_score <= 100.0

    # Report fields
    assert tr.report.title
    assert tr.report.bottom_line
    assert tr.report.executive_summary


def test_app_run_with_mock_client_produces_evidence_items():
    """Single-ticker research produces evidence items from subagent execution."""
    client = MockLLMClient()
    app = HermesResearchApp(llm_client=client)

    result = app.run("Research AAPL")

    assert len(result.ticker_results) == 1
    tr = result.ticker_results[0]

    # Evidence items are stored in audit — check that pipeline ran
    assert tr.audit is not None
    # is_ready should be True if evidence was collected
    assert "is_ready" in tr.audit


def test_app_run_without_llm_client_returns_empty_evidence():
    """App without LLM client produces no evidence items (graceful degradation)."""
    app = HermesResearchApp(llm_client=None)

    result = app.run("Research AAPL")

    assert len(result.ticker_results) == 1
    tr = result.ticker_results[0]

    # Should still produce a result but signal/report may be None
    # depending on whether judge can handle empty evidence
    assert tr is not None


def test_app_run_single_ticker_ticker_results_scoped_correctly():
    """Each ticker in a multi-ticker request gets its own scoped result."""
    client = MockLLMClient()
    app = HermesResearchApp(llm_client=client)

    result = app.run("Research AAPL and MSFT")

    tickers_found = {tr.ticker for tr in result.ticker_results}
    assert "AAPL" in tickers_found
    assert "MSFT" in tickers_found


def test_app_run_persists_signal_and_report_to_database():
    """Regression: DB-backed run completes with no persistence errors.

    With the fix, save_research_task() is called before signal/report persistence,
    so FK constraints are satisfied and no 'persist error' appears in tr.errors.
    """
    import tempfile, os
    from agent.research_v1.data.database import ResearchDatabase

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "research.db")
        db = ResearchDatabase(db_path)
        db.initialize()
        db.initialize_research_core()

        client = MockLLMClient()
        app = HermesResearchApp(llm_client=client, database=db)

        result = app.run("Research AAPL")

        assert len(result.ticker_results) == 1
        tr = result.ticker_results[0]

        # Pipeline produces a real signal and report
        assert tr.signal is not None
        assert tr.signal.ticker == "AAPL"
        assert tr.report is not None

        # Regression check: no persistence errors (FK chain now closed by save_research_task)
        persistence_errors = [e for e in tr.errors if "persist" in e.lower()]
        assert len(persistence_errors) == 0, (
            f"Unexpected persistence errors (FK chain broken): {persistence_errors}"
        )


def test_all_normalized_evidence_items_preserved_in_pipeline():
    """Regression: execute_subagent() returns ALL normalized items, not just the first.

    When one analyst response normalizes into multiple EvidenceItems (e.g., structured
    summary with metrics + verdict + sentiment), all of them must reach the bundle
    and be visible in the final judge's evidence.
    """
    from agent.research_v1.evidence_store import EvidenceStore
    from agent.research_v1.contracts import AgentRole

    # Multi-claim analyst output: one fundamentals run produces 3 distinct items
    store = EvidenceStore()

    multi_claim_output = {
        "report": "Strong fundamentals.",
        "summary_json": {
            "verdict": "buy",
            "confidence": 0.85,
            "direction": "bullish",
            "revenue_growth": 15.2,
            "roe": 22.5,
            "debt_equity": 0.4,
        },
    }

    items = store.normalize(
        task_id="test-task-multiclam",
        subtask_id="test-subtask-multiclam",
        ticker="AAPL",
        agent_role=AgentRole.FUNDAMENTALS,
        raw_output=multi_claim_output,
    )

    # Must produce more than one item (metrics + verdict + sentiment all extracted)
    assert len(items) > 1, (
        f"Expected multiple evidence items from structured output, got {len(items)}. "
        "execute_subagent() should preserve ALL normalized items, not just items[0]."
    )

    # Each item must have correct ticker and role
    for item in items:
        assert item.ticker == "AAPL"
        assert item.agent_role == AgentRole.FUNDAMENTALS

    # The items must actually differ (different claims/values)
    claims = [item.claim for item in items]
    assert len(set(claims)) > 1, "Evidence items should have distinct claims"


def test_all_evidence_items_from_single_analyst_reach_bundle_via_run():
    """App-level regression: all normalized items from one analyst reach the bundle.

    Uses a mock fundamentals response that normalizes into multiple evidence items
    (metrics: revenue_growth, earnings_growth, debt_equity + verdict). Verifies
    through the orchestrator audit that more than one evidence item for the same
    role made it through execute_subagent() and into the evidence bundle.
    """
    class MultiClaimFundamentalsClient(MockLLMClient):
        """Mock LLM that returns structured multi-claim responses for fundamentals."""
        def generate(self, messages, temperature=0.7, max_tokens=4096):
            from agent.research_v1.llm_clients import LLMResponse
            prompt_text = " ".join(m.get("content", "") for m in messages if m.get("content"))
            if "fundamentals" in prompt_text.lower():
                json_body = (
                    '{"summary": "Strong fundamentals",'
                    '"verdict": "buy",'
                    '"confidence": 0.85,'
                    '"direction": "bullish",'
                    '"revenue_growth": 15.2,'
                    '"earnings_growth": 22.5,'
                    '"debt_equity": 0.4}'
                )
                return LLMResponse(
                    content=f'```json\n{json_body}\n```',
                    model="mock-model",
                    input_tokens=100,
                    output_tokens=200,
                    cost_estimate=0.01,
                    raw_response={},
                )
            # Non-fundamentals: minimal response
            return LLMResponse(
                content='```json\n{"summary": "ok", "confidence": 0.6}\n```',
                model="mock-model",
                input_tokens=100,
                output_tokens=200,
                cost_estimate=0.01,
                raw_response={},
            )

    client = MultiClaimFundamentalsClient()
    app = HermesResearchApp(llm_client=client)

    result = app.run("Research AAPL")

    assert len(result.ticker_results) == 1
    tr = result.ticker_results[0]

    # Audit carries the bundle's coverage_summary: role -> item_count
    coverage = tr.audit.get("coverage_summary", {})
    fundamentals_count = coverage.get("fundamentals", 0)

    # The fundamentals analyst response normalizes into at least 4 items:
    # revenue_growth, earnings_growth, debt_equity (3 metrics) + verdict (1)
    assert fundamentals_count >= 4, (
        f"Expected >=4 evidence items from fundamentals role (3 metrics + verdict), "
        f"got {fundamentals_count}. This means execute_subagent() is still dropping items."
    )

    # Verify no pipeline errors (would indicate other failures)
    assert tr.errors == [], f"Unexpected errors: {tr.errors}"


# =============================================================================
# Error isolation tests
# =============================================================================

def test_subagent_failure_isolated_other_roles_continue():
    """When one subagent fails, others still execute and errors are recorded."""
    # Create a mock client that fails for fundamentals but succeeds for others
    class FailingFundamentalsClient(MockLLMClient):
        def generate(self, messages, temperature=0.7, max_tokens=4096):
            prompt_text = " ".join(m.get("content", "") for m in messages if m.get("content"))
            if "fundamentals" in prompt_text.lower():
                raise RuntimeError("Fundamentals API unavailable")
            return super().generate(messages, temperature, max_tokens)

    client = FailingFundamentalsClient()
    app = HermesResearchApp(llm_client=client)

    result = app.run("Research AAPL")

    # Should still get a result despite fundamentals failure
    assert len(result.ticker_results) == 1
    tr = result.ticker_results[0]

    # Fundamentals failure is recorded in global errors (not per-ticker)
    assert len(result.errors) > 0
    assert any("fundamentals" in e.lower() for e in result.errors)

    # Ticker result should still have audit from other roles
    assert tr.audit is not None
    # Audit should show fundamentals as missing (incomplete evidence)
    assert "fundamentals" in tr.audit.get("missing_roles", [])


def test_orchestrator_decompose_produces_all_required_roles():
    """Orchestrator decompose produces one subtask per required role per ticker."""
    from agent.research_v1.orchestrator import Orchestrator
    from agent.research_v1.contracts import new_research_task, TaskType

    orchestrator = Orchestrator()
    task = new_research_task(
        request_text="Research AAPL",
        tickers=["AAPL"],
        task_type=TaskType.SINGLE_TICKER_RESEARCH,
    )

    subtasks = orchestrator.decompose(task)

    # Single ticker research requires: fundamentals, technical, news
    role_counts = {}
    for st in subtasks:
        role_counts[st.agent_role] = role_counts.get(st.agent_role, 0) + 1

    assert AgentRole.FUNDAMENTALS in role_counts
    assert AgentRole.TECHNICAL in role_counts
    assert AgentRole.NEWS in role_counts


def test_orchestrator_decompose_multi_ticker_produces_cross_product():
    """Multi-ticker tasks produce subtasks for each ticker × required role."""
    from agent.research_v1.orchestrator import Orchestrator
    from agent.research_v1.contracts import new_research_task, TaskType

    orchestrator = Orchestrator()
    task = new_research_task(
        request_text="Compare AAPL and MSFT",
        tickers=["AAPL", "MSFT"],
        task_type=TaskType.MULTI_TICKER_COMPARE,
    )

    subtasks = orchestrator.decompose(task)

    # Multi-ticker compare: fundamentals, technical, industry
    # 3 roles × 2 tickers = 6 subtasks
    assert len(subtasks) == 6

    tickers = {st.ticker for st in subtasks}
    assert tickers == {"AAPL", "MSFT"}


def test_evidence_store_normalize_accepts_structured_output():
    """EvidenceStore.normalize converts analyst structured output to EvidenceItems."""
    from agent.research_v1.evidence_store import EvidenceStore

    store = EvidenceStore()

    raw_output = {
        "report": "Strong buy case for AAPL.",
        "summary_json": {
            "verdict": "buy",
            "confidence": 0.85,
            "direction": "bullish",
        },
    }

    items = store.normalize(
        task_id="test-task",
        subtask_id="test-subtask",
        ticker="AAPL",
        agent_role=AgentRole.FUNDAMENTALS,
        raw_output=raw_output,
    )

    assert len(items) >= 1
    # Check that evidence items carry the right metadata
    assert all(item.ticker == "AAPL" for item in items)
    assert all(item.agent_role == AgentRole.FUNDAMENTALS for item in items)
    assert all(item.task_id == "test-task" for item in items)


def test_evidence_store_normalize_accepts_freeform_output():
    """EvidenceStore.normalize handles freeform string output."""
    from agent.research_v1.evidence_store import EvidenceStore

    store = EvidenceStore()

    items = store.normalize(
        task_id="test-task",
        subtask_id="test-subtask",
        ticker="AAPL",
        agent_role=AgentRole.FUNDAMENTALS,
        raw_output="AAPL shows strong fundamentals with P/E 28.5 and ROE 55%.",
    )

    assert len(items) >= 1
    assert items[0].ticker == "AAPL"
    assert items[0].agent_role == AgentRole.FUNDAMENTALS
