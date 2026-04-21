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
from agent.research_v1.options_decision import OptionsDecisionEngine
from agent.research_v1.early_exit import EarlyExitEngine
from agent.research_v1.watchlist_alerts import WatchlistAlertCenter
from agent.research_v1.validation_engine import ValidationEngine
from agent.research_v1.contracts import (
    UnderlyingThesis,
    InstrumentRecommendation,
    PositionDecisionCard,
    OptionsStructure,
    EarlyExitPlan,
    WatchlistEntry,
    ValidationResult,
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
    # Phase 15: options structure and early exit
    options_structure: OptionsStructure | None = None
    early_exit: EarlyExitPlan | None = None
    # Phase 16: watchlist entry
    watchlist_entry: WatchlistEntry | None = None
    # Phase 17: validation annotation
    validation: ValidationResult | None = None


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
        # Phase 15: options structure and early exit engines
        self._options_decision_engine = OptionsDecisionEngine()
        self._early_exit_engine = EarlyExitEngine()
        # Phase 16: watchlist and alert center
        self._watchlist_center = WatchlistAlertCenter()
        self._watchlist_initialized = False
        # Phase 17: validation engine
        self._validation_engine = ValidationEngine()

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

    def _instrument_action_to_trade_plan_action(self, primary_action: str) -> str:
        """
        Map Phase 14 instrument action names to trade_plan action names.

        Phase 14 instrument actions use human-friendly names
        (e.g. 'Sell Cash-Secured Put') while trade_plan uses simpler
        action names (BUY/SELL/etc). This maps between them.
        """
        return {
            "Buy Stock": "BUY",
            "Buy Call": "BUY",
            "Bull Call Spread": "BUY",
            "Sell Cash-Secured Put": "SELL",
            "Covered Call": "SELL",
            "Watchlist": "HOLD",
            "No Trade": "HOLD",
        }.get(primary_action, "HOLD")

    def _extract_thesis_inputs(
        self,
        bundle: EvidenceBundle,
        ticker_context: dict[str, Any],
    ) -> dict:
        """
        Extract inputs for ThesisEngine from evidence bundle and market context.

        Phase 14: pulls quality, valuation, and catalyst signals from real EvidenceItem
        fields produced by EvidenceStore normalization:
            - item.direction  — Direction.BULLISH/BEARISH/NEUTRAL/MIXED
            - item.confidence — float 0.0–1.0 (set by EvidenceStore from analyst output)
            - item.claim — string like "Verdict: buy", "upside_pct: 0.22"
            - item.value — analyst-structured value (may be dict, string, or numeric)

        This correctly handles the actual EvidenceStore._extract_from_summary() output
        shapes: verdict items, sentiment items, numeric metric items.
        """
        import re
        from agent.research_v1.contracts import Direction

        fundamentals_confidences: list[float] = []
        fundamentals_bullish_count: int = 0
        fundamentals_bearish_count: int = 0

        valuation_upside: float | None = None
        valuation_confidence: float = 0.5

        catalysts_confidences: list[float] = []
        catalysts_bullish_count: int = 0

        option_context: dict = {}
        holding_context: dict = {"has_stock": False}

        for item in bundle.evidence_items:
            role = item.agent_role.value
            item_val = item.value
            claim_lower = item.claim.lower() if item.claim else ""

            # ---- Fundamentals: quality = bullish evidence fraction × avg confidence ----
            if role == "fundamentals":
                conf = item.confidence if item.confidence else 0.5
                fundamentals_confidences.append(conf)
                if item.direction == Direction.BULLISH:
                    fundamentals_bullish_count += 1
                elif item.direction == Direction.BEARISH:
                    fundamentals_bearish_count += 1

            # ---- Valuation: extract upside_pct from claim or value ----
            elif role == "valuation":
                # Try claim text: "upside_pct: 0.22" or "upside: 22%"
                match = re.search(r"upside[_\s]?pct[:\s]+([0-9.]+)", claim_lower)
                if match:
                    try:
                        raw = float(match.group(1))
                        # Handle both decimal (0.22) and percentage (22.0) formats
                        valuation_upside = raw if raw <= 1.0 else raw / 100.0
                    except ValueError:
                        pass
                # Try value dict
                if valuation_upside is None and isinstance(item_val, dict):
                    for key in ("upside_pct", "upside", "upside_pct_real"):
                        if key in item_val:
                            try:
                                raw = float(item_val[key])
                                valuation_upside = raw if raw <= 1.0 else raw / 100.0
                                break
                            except (ValueError, TypeError):
                                pass
                # Try raw_payload (EvidenceStore stores full summary_json under 'summary_json' key)
                if valuation_upside is None and hasattr(item, "raw_payload") and isinstance(item.raw_payload, dict):
                    payload = item.raw_payload.get("summary_json", item.raw_payload)
                    for key in ("upside_pct", "upside", "upside_pct_real"):
                        if key in payload:
                            try:
                                raw = float(payload[key])
                                valuation_upside = raw if raw <= 1.0 else raw / 100.0
                                break
                            except (ValueError, TypeError):
                                pass
                if item.confidence:
                    valuation_confidence = item.confidence

            # ---- News / Sentiment: catalyst clarity proxy ----
            elif role in ("news", "sentiment"):
                conf = item.confidence if item.confidence else 0.5
                catalysts_confidences.append(conf)
                if item.direction == Direction.BULLISH:
                    catalysts_bullish_count += 1

        # ---- Compute fundamentals quality ----
        fundamentals: dict = {}
        if fundamentals_confidences:
            avg_conf = sum(fundamentals_confidences) / len(fundamentals_confidences)
            total = fundamentals_bullish_count + fundamentals_bearish_count
            if total > 0:
                # Quality = fraction of bullish evidence × average confidence
                quality = (fundamentals_bullish_count / total) * avg_conf
            else:
                quality = avg_conf * 0.5  # neutral evidence gets half weight
            fundamentals["profitability"] = quality
            fundamentals["balance_sheet"] = quality

        # ---- Compute valuation ----
        valuation: dict = {}
        if valuation_upside is not None:
            valuation["upside_pct"] = valuation_upside
        valuation["_confidence"] = valuation_confidence

        # ---- Compute catalysts ----
        catalysts: dict = {}
        if catalysts_confidences:
            catalysts["clarity"] = sum(catalysts_confidences) / len(catalysts_confidences)

        # ---- Pull IV percentile and liquidity from market data context ----
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
            # Phase 14 instrument flags derived from task type:
            # OPTION_IDEA → user wants option entry (CSP for discounted entry, spread for defined risk)
            # POSITION_MANAGEMENT → user holds stock and wants income (Covered Call)
            if task.task_type.value == "option_idea":
                option_ctx["wants_discounted_entry"] = True
            if task.task_type.value == "position_management" and holding_ctx.get("has_stock"):
                option_ctx["short_term_upside_limited"] = True
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

        # Phase 15: Options Structure + Early Exit
        # Runs after Phase 14 instrument selection; only applies to options-based instruments.
        options_structure: OptionsStructure | None = None
        early_exit: EarlyExitPlan | None = None
        if instrument_rec is not None and instrument_rec.primary_action in {
            "Buy Call", "Bull Call Spread", "Sell Cash-Secured Put", "Covered Call",
        }:
            try:
                # Pull market data for options structure decisions
                mkt_data = ticker_context.get("market_data", {}) if ticker_context else {}
                chain = ticker_context.get("option_chain", []) if ticker_context else []
                current_price = float(mkt_data.get("last_price", 0.0)) or (signal.entry_price if signal else 0.0)
                target_price = float(signal.take_profit) if signal and signal.take_profit else None
                iv_pct = float(mkt_data.get("iv_percentile", 0.50))

                # Thesis months from holding horizon or default
                horizon = signal.holding_horizon if signal else "3M"
                thesis_months_map = {"1M": 1, "2M": 2, "3M": 3, "6M": 6, "9M": 9, "12M": 12, "18M": 18, "2Y": 24}
                thesis_months = thesis_months_map.get(horizon.upper(), 6)

                options_structure = self._options_decision_engine.decide(
                    instrument_action=instrument_rec.primary_action,
                    current_price=current_price,
                    target_price=target_price,
                    thesis_months=thesis_months,
                    option_chain=chain,
                    iv_percentile=iv_pct,
                )
                options_structure.ticker = ticker

                # Early exit evaluation
                entry_price = float(signal.entry_price) if signal and signal.entry_price else current_price
                early_exit = self._early_exit_engine.evaluate(
                    instrument_action=instrument_rec.primary_action,
                    thesis_state="Stable",
                    thesis_state_reason=f"Initial evaluation — {thesis.classification}" if thesis else "Initial",
                    current_price=current_price,
                    entry_price=entry_price,
                    target_price=target_price if target_price else current_price * 1.20,
                    option_return_pct=0.0,  # No open position yet at initial recommendation
                    iv_change=0.0,
                    theta_burn_accelerating=False,
                    expiry_months=options_structure.primary_contract.expiry_months,
                    months_remaining=float(options_structure.primary_contract.expiry_months),
                    iv_percentile=iv_pct,
                )
                early_exit.ticker = ticker
            except Exception as exc:
                errors.append(f"Phase15 options/early-exit error: {exc}")

        # Phase 16: Watchlist entry — register the ticker in the watchlist
        watchlist_entry: WatchlistEntry | None = None
        if instrument_rec is not None:
            try:
                # Map instrument action to watchlist status
                action = instrument_rec.primary_action
                if action == "No Trade":
                    watchlist_status = "Passive Watch"
                elif action == "Watchlist":
                    watchlist_status = "Passive Watch"
                else:
                    watchlist_status = "Held"

                # Map thesis classification to thesis_state
                # Per Phase 16 spec: Investable→Strengthening, Watchlist→Stable, No Trade→Broken
                thesis_state_map = {
                    "Investable": "Strengthening",
                    "Watchlist": "Stable",
                    "No Trade": "Broken",
                }
                thesis_state = thesis_state_map.get(
                    thesis.classification if thesis else "", "Stable"
                )

                entry = self._watchlist_center.register(
                    ticker=ticker,
                    status=watchlist_status,
                    action_bias=action,
                )
                if thesis_state != "Stable":
                    entry = self._watchlist_center.update_thesis_state(
                        entry, thesis_state, f"Initial research: {thesis.classification if thesis else 'unknown'}"
                    )
                # Persist so viewer/PDF surfaces can see this entry
                if self._pipeline and self._pipeline.database:
                    if not self._watchlist_initialized:
                        self._pipeline.database.initialize_watchlist()
                        self._watchlist_initialized = True
                    self._pipeline.database.save_watchlist_entry(entry)
                watchlist_entry = entry
            except Exception as exc:
                errors.append(f"Phase16 watchlist error: {exc}")

        # Phase 17: Validation — annotate the result without overriding decisions
        validation: ValidationResult | None = None
        if instrument_rec is not None:
            try:
                validation = self._validation_engine.evaluate(
                    ticker=ticker,
                    thesis=thesis,
                    instrument_action=instrument_rec.primary_action,
                    ticker_context=ticker_context,
                    valuation=thesis_inputs.get("valuation", {}),
                    catalysts=thesis_inputs.get("catalysts", {}),
                )
                # Persist so viewer snapshot can surface validation data
                if self._pipeline and self._pipeline.database and validation is not None:
                    self._pipeline.database.save_validation_result(validation)
            except Exception as exc:
                errors.append(f"Phase17 validation error: {exc}")

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
        # Phase 14: when instrument is CSP or Covered Call, override action to match
        # the Phase 14 instrument selection (not just the generic BUY signal rating).
        trade_plan: dict | None = None
        if signal is not None and instrument_rec is not None:
            try:
                base_plan = self._trade_plan_generator.generate(signal)
                # Override action if Phase 14 selected a specific instrument
                override_action = self._instrument_action_to_trade_plan_action(
                    instrument_rec.primary_action
                )
                if override_action != base_plan.get("action"):
                    base_plan["action"] = override_action
                    base_plan["_instrument_override"] = True
                trade_plan = base_plan
            except Exception as exc:
                errors.append(f"TradePlanGenerator error: {exc}")
        elif signal is not None:
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
            options_structure=options_structure,
            early_exit=early_exit,
            watchlist_entry=watchlist_entry,
            validation=validation,
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
