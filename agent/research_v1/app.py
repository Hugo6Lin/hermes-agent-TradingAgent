"""
Hermes Research Pipeline - Canonical Entry Point.

This module is the primary programmatic entry point for the Hermes research
pipeline. It wires together the canonical components:

    TaskRouter        - natural language -> ResearchTask
    Orchestrator      - ResearchTask -> SubagentTask[] -> EvidenceBundle
    EvidenceStore     - normalize subagent outputs -> EvidenceItem[]
    FinalJudge        - JudgeInputPacket -> CanonicalSignal + CanonicalReport
    Reviewer         - ReviewInputPacket -> CanonicalReview (optional quality gate)
    SignalPersistence - persist to database
    TradePlanGenerator - CanonicalSignal -> trade plan dict
    MarketDataService - Futu-first market data for subagent context

Usage::

    from agent.research_v1.app import run_research
    result = run_research("Research AAPL fundamentals deeply")
    # Single-ticker result:
    tr = result.ticker_results[0]
    print(tr.signal.rating, tr.signal.confidence)
    print(tr.report.bottom_line)
    print(tr.trade_plan)

The pipeline is model-agnostic: subagent execution is delegated to whatever
client is configured. This module only defines the orchestration contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agent.research_v1.task_router import TaskRouter
from agent.research_v1.orchestrator import Orchestrator
from agent.research_v1.final_judge import judge
from agent.research_v1.subagent_executor import SubagentExecutor
from agent.research_v1.evidence_store import EvidenceStore
from agent.research_v1.contracts import (
    ResearchTask,
    EvidenceItem,
    CanonicalSignal,
    CanonicalReport,
    CanonicalReview,
    EvidenceBundle,
    TaskType,
    OutputMode,
    new_evidence_item,
)
from agent.research_v1.signal_pipeline import SignalPersistencePipeline
from agent.research_v1.trade_plan import TradePlanGenerator
from agent.research_v1.market_data_service import MarketDataService
from agent.research_v1.thesis_engine import ThesisEngine
from agent.research_v1.instrument_selection import InstrumentSelectionEngine
from agent.research_v1.contracts import (
    UnderlyingThesis,
    InstrumentRecommendation,
    PositionDecisionCard,
    VALID_BULLISH_ACTIONS,
)


@dataclass
class TickerResearchResult:
    """
    Result of the canonical research pipeline for one ticker.

    When a multi-ticker request is made (e.g. "Compare AAPL and MSFT"),
    run() returns one TickerResearchResult per ticker, each with its own
    signal, report, review, trade_plan, and Phase 14 decision card correctly
    scoped to that ticker.
    """
    task: ResearchTask
    ticker: str                        # Which ticker this result is for
    signal: CanonicalSignal | None
    report: CanonicalReport | None
    review: CanonicalReview | None
    trade_plan: dict | None
    audit: dict[str, Any]
    errors: list[str]
    # Phase 14: bullish decision fields
    thesis: UnderlyingThesis | None = None
    instrument_recommendation: InstrumentRecommendation | None = None
    decision_card: PositionDecisionCard | None = None


@dataclass
class ResearchResult:
    """
    Result of a full canonical research pipeline run.

    Attributes:
        task: The original ResearchTask.
        ticker_results: List of per-ticker results (one per ticker in task.tickers).
            For single-ticker requests this list has one element.
        errors: List of errors not scoped to a specific ticker.
    """
    task: ResearchTask
    ticker_results: list[TickerResearchResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class HermesResearchApp:
    """
    Canonical research pipeline application.

    This class encapsulates the full pipeline from natural language request
    to final signal + report + optional review. It is designed to be
    straightforward to use, test, and swap components on.

    Subagent execution is handled by SubagentExecutor, which routes each
    AgentRole to its corresponding analyst using the provided LLM client.
    """

    def __init__(self, llm_client=None, database=None, market_data_service=None):
        """
        Initialize the research app.

        Args:
            llm_client: LLM client for subagent execution. If None, a
                SubagentExecutor is still created but will raise if
                execute_subagent() is called without a valid client.
            database: ResearchDatabase instance. If None, an in-memory DB is used.
            market_data_service: MarketDataService instance for fetching real market
                data. Defaults to a Futu-first service (Phase 12).
        """
        self._router = TaskRouter()
        self._orchestrator = Orchestrator()
        self._llm_client = llm_client
        # Futu-first by default (Phase 12); SubagentExecutor also uses it directly
        self._market_data_service = (
            market_data_service if market_data_service is not None
            else MarketDataService()
        )
        self._executor = SubagentExecutor(llm_client, self._market_data_service) if llm_client else None
        self._evidence_store = EvidenceStore()
        self._pipeline = SignalPersistencePipeline(database=database) if database else None
        self._trade_plan_generator = TradePlanGenerator()
        # Phase 14: bullish decision engines
        self._thesis_engine = ThesisEngine()
        self._instrument_selector = InstrumentSelectionEngine()

    def run(self, request: str) -> ResearchResult:
        """
        Run the full canonical research pipeline on a natural language request.

        For multi-ticker requests (e.g. "Compare AAPL and MSFT"), the pipeline
        runs per-ticker: each ticker's evidence is bundled, judged, and reviewed
        independently, producing one TickerResearchResult per ticker.

        Args:
            request: Natural language research request
                (e.g. "Research AAPL fundamentals deeply", "Compare TSLA and NVDA").

        Returns:
            ResearchResult with per-ticker results.
        """
        global_errors: list[str] = []

        # 1. Route natural language → ResearchTask
        try:
            task = self._router.route(request)
        except Exception as exc:
            global_errors.append(f"TaskRouter error: {exc}")
            from agent.research_v1.contracts import ResearchTask
            words = request.strip().split()
            tickers = [w for w in words if w.isupper() and len(w) <= 5]
            task = ResearchTask(
                request_text=request,
                tickers=tickers if tickers else ["UNKNOWN"],
            )

        # 2. Orchestrator decompose → SubagentTask[] (all roles × all tickers)
        try:
            all_subtasks = self._orchestrator.decompose(task)
        except Exception as exc:
            global_errors.append(f"Decompose error: {exc}")
            all_subtasks = []

        # 3. Execute all subagents → EvidenceItem[] (each item tagged with its ticker)
        # Pre-fetch market data per ticker to populate required_context (Futu-first)
        ticker_contexts: dict[str, dict] = {}
        if self._market_data_service:
            for ticker in task.tickers:
                ticker_contexts[ticker] = self._market_data_service.fetch_context_for_ticker(ticker)

        all_evidence: list[EvidenceItem] = []
        for subtask in all_subtasks:
            # Inject pre-fetched market data into required_context
            if self._market_data_service and subtask.ticker in ticker_contexts:
                fetched = ticker_contexts[subtask.ticker]
                # Merge fetched context; explicit context already on subtask takes precedence
                merged = dict(fetched)
                merged.update(subtask.required_context)
                # Strip internal fallback reasons before passing to executor
                merged.pop("_fallback_reasons", None)
                subtask.required_context = merged

            try:
                items = self.execute_subagent(subtask)
                all_evidence.extend(items)
            except Exception as exc:
                global_errors.append(
                    f"Subagent {subtask.agent_role.value}/{subtask.ticker} error: {exc}"
                )

        # 4. Run per-ticker pipeline
        ticker_results: list[TickerResearchResult] = []
        for ticker in task.tickers:
            ticker_evidence = [e for e in all_evidence if e.ticker == ticker]
            ticker_ctx = ticker_contexts.get(ticker, {})
            ticker_ticker_results = self._run_ticker_pipeline(
                task, ticker, ticker_evidence, ticker_ctx
            )
            # Errors during pipeline execution are included per-TickerResearchResult
            ticker_results.extend(ticker_ticker_results)

        return ResearchResult(
            task=task,
            ticker_results=ticker_results,
            errors=global_errors,
        )

    def _extract_thesis_inputs(
        self,
        bundle: EvidenceBundle,
        ticker_context: dict[str, Any],
    ) -> dict:
        """
        Extract inputs for ThesisEngine from evidence bundle and market context.

        Phase 14: pulls quality, valuation, and catalyst signals from the evidence
        items produced by the subagents. This is additive — it does not modify the
        canonical signal/report produced by FinalJudge.
        """
        fundamentals: dict = {}
        valuation: dict = {}
        catalysts: dict = {}
        option_context: dict = {}
        holding_context: dict = {"has_stock": False}

        # Extract from evidence items by role
        for item in bundle.evidence_items:
            val = item.value if isinstance(item.value, dict) else {}
            role = item.agent_role.value

            if role == "fundamentals":
                # Fundamentals evidence: extract quality signals
                conf = val.get("confidence", 0.0) if isinstance(val, dict) else 0.0
                fundamentals.setdefault("profitability", conf)
                fundamentals.setdefault("balance_sheet", conf)
            elif role == "valuation":
                # Valuation evidence: extract upside_pct
                upside = val.get("upside_pct", val.get("upside", 0.0))
                valuation.setdefault("upside_pct", float(upside))
            elif role == "news" or role == "sentiment":
                # News/sentiment as catalyst proxy
                conf = val.get("confidence", 0.5) if isinstance(val, dict) else 0.5
                catalysts.setdefault("clarity", conf)

        # Pull IV percentile and liquidity from market data context
        market_data = ticker_context.get("market_data", {})
        if isinstance(market_data, dict):
            option_context["iv_percentile"] = float(market_data.get("iv_percentile", 0.5))
            option_context["liquidity_ok"] = market_data.get("liquidity_ok", True)

        # Pull from bundle.context_snapshot if available (Phase 14+ extended context)
        ctx_snapshot = bundle.context_snapshot
        if isinstance(ctx_snapshot, dict):
            option_context.setdefault("iv_percentile", ctx_snapshot.get("iv_percentile", 0.5))
            option_context.setdefault("liquidity_ok", ctx_snapshot.get("liquidity_ok", True))
            holding_context = ctx_snapshot.get("holding_context", holding_context)

        return {
            "fundamentals": fundamentals,
            "valuation": valuation,
            "catalysts": catalysts,
            "option_context": option_context,
            "holding_context": holding_context,
        }

    def _run_ticker_pipeline(
        self,
        task: ResearchTask,
        ticker: str,
        evidence_items: list[EvidenceItem],
        ticker_context: dict[str, Any] | None = None,
    ) -> list[TickerResearchResult]:
        """
        Run steps 4-10 of the pipeline scoped to one ticker.

        Args:
            task: The parent ResearchTask.
            ticker: The specific ticker for this pipeline iteration.
            evidence_items: Evidence items for this specific ticker only.
            ticker_context: Market data context for this ticker, possibly containing
                _fallback_reasons from MarketDataService.

        Returns:
            List containing one TickerResearchResult (kept as list for API consistency).
        """
        errors: list[str] = []
        result_errors: list[str] = []
        ticker_context = ticker_context or {}

        # 4. Orchestrator audit — pass bundle_ticker to avoid first-ticker hardcoding
        try:
            audit = self._orchestrator.audit(task, evidence_items, bundle_ticker=ticker)
        except Exception as exc:
            errors.append(f"Audit error: {exc}")
            audit = {"is_ready": len(evidence_items) > 0, "orchestrator_notes": ""}

        # 5. Orchestrator assemble bundle scoped to this ticker
        try:
            bundle = self._orchestrator.assemble_bundle(task.task_id, ticker, evidence_items)
        except Exception as exc:
            errors.append(f"Bundle assembly error: {exc}")
            bundle = EvidenceBundle(
                task_id=task.task_id,
                ticker=ticker,
                evidence_items=evidence_items,
            )

        # Add coverage_summary from bundle to audit (workflow metadata)
        audit["coverage_summary"] = bundle.coverage_summary

        # Add fallback reasons from MarketDataService (Phase 12: Futu-first with tracing)
        audit["fallback_reasons"] = list(ticker_context.get("_fallback_reasons") or [])

        # 6. Orchestrator assemble judge packet
        try:
            packet = self._orchestrator.assemble_judge_packet(task, bundle, audit)
        except Exception as exc:
            errors.append(f"Judge packet assembly error: {exc}")
            from agent.research_v1.contracts import JudgeInputPacket
            packet = JudgeInputPacket(
                task_id=task.task_id,
                ticker=ticker,
                task_summary=task.request_text,
                evidence_bundle=bundle,
            )

        # 7. Final Judge → CanonicalSignal + CanonicalReport
        signal: CanonicalSignal | None = None
        report: CanonicalReport | None = None
        try:
            signal, report = judge(packet)
        except Exception as exc:
            errors.append(f"FinalJudge error: {exc}")

        # Phase 14: Underlying Thesis + Instrument Selection
        # Runs after FinalJudge to stay additive to the canonical pipeline.
        thesis: UnderlyingThesis | None = None
        instrument_rec: InstrumentRecommendation | None = None
        decision_card: PositionDecisionCard | None = None
        try:
            thesis_inputs = self._extract_thesis_inputs(bundle, ticker_context)
            thesis = self._thesis_engine.evaluate(
                ticker=ticker,
                fundamentals=thesis_inputs.get("fundamentals", {}),
                valuation=thesis_inputs.get("valuation", {}),
                catalysts=thesis_inputs.get("catalysts", {}),
                task_id=task.task_id,
            )
            option_ctx = thesis_inputs.get("option_context", {})
            holding_ctx = thesis_inputs.get("holding_context", {})
            instrument_rec = self._instrument_selector.choose(thesis, option_ctx, holding_ctx)
            conviction = "High" if thesis.classification == "Investable" else "Medium"
            decision_card = PositionDecisionCard(
                task_id=task.task_id,
                ticker=ticker,
                primary_action=instrument_rec.primary_action,
                conviction=conviction,
                thesis_summary=thesis.summary,
                why_now=f"Thesis: {thesis.classification}; instrument: {instrument_rec.primary_action}",
                alternatives=instrument_rec.ranked_alternatives,
            )
        except Exception as exc:
            errors.append(f"Phase14 thesis/instrument error: {exc}")

        # 8. Persist to database — first ensure the task row exists (FK prerequisite)
        if self._pipeline:
            try:
                self._pipeline.database.save_research_task(task)
            except Exception as exc:
                errors.append(f"Task persist error: {exc}")

            if signal is not None:
                try:
                    self._pipeline.persist_canonical_signal(task.task_id, signal)
                except Exception as exc:
                    errors.append(f"Signal persist error: {exc}")
            if report is not None:
                try:
                    self._pipeline.persist_canonical_report(task.task_id, report, ticker)
                except Exception as exc:
                    errors.append(f"Report persist error: {exc}")

        # 9. Generate trade plan
        trade_plan: dict | None = None
        if signal is not None:
            try:
                trade_plan = self._trade_plan_generator.generate(signal)
            except Exception as exc:
                errors.append(f"TradePlanGenerator error: {exc}")

        # 10. Optional: Reviewer
        review: CanonicalReview | None = None
        if signal is not None or report is not None:
            try:
                review_packet = self._orchestrator.assemble_review_packet(
                    task, bundle, signal, report, audit
                )
                review = self._orchestrator.review(review_packet)
            except Exception as exc:
                errors.append(f"Reviewer error: {exc}")

        result_errors.extend(errors)

        return [TickerResearchResult(
            task=task,
            ticker=ticker,
            signal=signal,
            report=report,
            review=review,
            trade_plan=trade_plan,
            audit=audit,
            errors=result_errors,
            thesis=thesis,
            instrument_recommendation=instrument_rec,
            decision_card=decision_card,
        )]

    def execute_subagent(self, subtask) -> list[EvidenceItem]:
        """
        Execute a single subagent and return all normalized EvidenceItems.

        Uses SubagentExecutor to route the subtask to the appropriate analyst
        based on agent_role, then normalizes the output through EvidenceStore.

        Args:
            subtask: SubagentTask from orchestrator.decompose().

        Returns:
            List of EvidenceItems from this subagent's research (may be empty
            if the subagent failed or produced no usable evidence).
        """
        if self._executor is None:
            return []

        raw_output = self._executor.execute(subtask)

        # Normalize through EvidenceStore — returns ALL evidence items, not just one
        items = self._evidence_store.normalize(
            task_id=subtask.task_id,
            subtask_id=subtask.subtask_id,
            ticker=subtask.ticker,
            agent_role=subtask.agent_role,
            raw_output=raw_output,
        )

        return items


def run_research(request: str, llm_client=None) -> ResearchResult:
    """
    Convenience function to run a research request through the canonical pipeline.

    Uses an in-memory database and returns a ResearchResult. For persistent
    results or custom database configuration, instantiate HermesResearchApp directly.

    Args:
        request: Natural language research request.
        llm_client: LLM client for subagent execution. Required for real research.

    Returns:
        ResearchResult with per-ticker results.
    """
    app = HermesResearchApp(llm_client=llm_client)
    return app.run(request)


# CLI entry point — enables: python -m agent.research_v1.app "Research AAPL..."
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m agent.research_v1.app \"<research request>\"")
        print("Example: python -m agent.research_v1.app \"Research AAPL fundamentals\"")
        sys.exit(1)

    request = " ".join(sys.argv[1:])

    # Try to get an LLM client from environment
    llm_client = None
    try:
        from agent.research_v1.llm_clients import MiniMaxClient
        llm_client = MiniMaxClient()
    except Exception:
        pass

    if llm_client is None:
        print("Warning: No LLM client configured. Subagents will be no-op.")
        print("Set MINIMAX_API_KEY environment variable to enable real research.\n")

    print(f"Running research: {request}")
    print("-" * 60)

    result = run_research(request, llm_client=llm_client)

    for tr in result.ticker_results:
        print(f"\n=== {tr.ticker} ===")
        if tr.signal:
            print(f"  Rating:    {tr.signal.rating}")
            print(f"  Confidence: {tr.signal.confidence:.0%}")
            print(f"  Priority:   {tr.signal.priority_score:.1f}")
            print(f"  Entry:     {tr.signal.entry_price}")
            print(f"  Stop Loss: {tr.signal.stop_loss}")
            print(f"  Take Profit: {tr.signal.take_profit}")
            print(f"  Horizon:   {tr.signal.holding_horizon}")
            print(f"  Reason:    {tr.signal.decision_reason[:80]}...")
        if tr.report:
            print(f"  Bottom Line: {tr.report.bottom_line}")
            print(f"  Executive:   {tr.report.executive_summary[:80]}...")
        if tr.trade_plan:
            tp = tr.trade_plan
            print(f"  Trade Plan: {tp.get('action')} | "
                  f"Entry zone: {tp.get('entry_zone')} | "
                  f"Size: {tp.get('suggested_position_size')}")
        if tr.review:
            print(f"  Review: {tr.review.verdict.value} "
                  f"(quality={tr.review.quality_score:.2f})")
            if tr.review.flags:
                print(f"  Flags: {', '.join(tr.review.flags)}")
        if tr.errors:
            print(f"  Errors: {tr.errors}")

    if result.errors:
        print(f"\n[Global errors: {'; '.join(result.errors)}]")
