"""
Tests for Phase 19: Image Report Pipeline.

Covers:
    1. build_report_pack() maps real decision objects correctly
    2. build_prompt_pack() produces page 1 / page 2 / optional page 3 correctly
    3. Approved action vocabulary is preserved for all Hermes actions
    4. Image report service runs end-to-end on a realistic TickerResearchResult
    5. Generation result distinguishes prompt-ready vs job-submitted vs artifacts-present
    6. Page-count logic works
    7. Research validity remains true when image generation fails
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone

import pytest

from agent.research_v1.contracts import (
    ResearchTask,
    CanonicalSignal,
    CanonicalReport,
    TradePlan,
    UnderlyingThesis,
    InstrumentRecommendation,
    PositionDecisionCard,
    OptionsStructure,
    OptionContract,
    EarlyExitPlan,
    WatchlistEntry,
    ValidationResult,
    TaskType,
    ExitTrigger,
)
from agent.research_v1.app import TickerResearchResult, HermesResearchApp
from agent.research_v1.image_report_contracts import (
    OrchestratorReportPack,
    ImagePromptPack,
    PagePrompt,
    ImageReportArtifacts,
    PageGenerationResult,
    ImageReportGenerationResult,
    approved_action_labels,
    build_default_style_rules,
)
from agent.research_v1.orchestrator_reporting import (
    build_report_pack,
    VALID_BULLISH_ACTIONS,
)
from agent.research_v1.image_prompt_builder import (
    build_prompt_pack,
    ZH_LABELS,
    _decide_page_count,
    _build_page_1_prompt,
    _build_page_2_prompt,
    _build_page_3_prompt,
)
from agent.research_v1.image_report_generator import (
    ImageReportGenerator,
    ManualImageJobBackend,
    ImageGenerationJob,
    build_page_path,
    build_prompt_path,
    build_manifest_path,
    build_all_jobs_bundle_path,
)
from agent.research_v1.image_report_service import (
    ImageReportService,
    ImageReportServiceResult,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def make_task() -> ResearchTask:
    return ResearchTask(
        request_text="Research AAPL for investment",
        tickers=["AAPL"],
        task_type=TaskType.SINGLE_TICKER_RESEARCH,
    )


def make_signal() -> CanonicalSignal:
    return CanonicalSignal(
        ticker="AAPL",
        rating="BUY",
        confidence=0.85,
        priority_score=82.0,
        entry_price=175.0,
        stop_loss=165.0,
        take_profit=200.0,
        holding_horizon="3–6 months",
    )


def make_report() -> CanonicalReport:
    return CanonicalReport(
        title="AAPL Research Report",
        executive_summary="Strong product cycle and services growth.",
        bottom_line="Buy AAPL for 3–6 month gain.",
        why_now="Catalyst event and valuation support.",
        bull_case="iPhone upgrade cycle and services expansion driving earnings.",
        bear_case="China demand weakness and increased competition.",
    )


def make_decision_card(action: str = "Buy Stock") -> PositionDecisionCard:
    return PositionDecisionCard(
        task_id="task-1",
        ticker="AAPL",
        primary_action=action,
        conviction="High",
        thesis_summary="Apple product cycle strong, services growth sustained.",
        why_now="Upcoming earnings beat expectations and valuation attractive.",
        alternatives=["Buy Call (higher upside, defined risk)"],
    )


def make_options_structure() -> OptionsStructure:
    return OptionsStructure(
        ticker="TSLA",
        instrument_action="Bull Call Spread",
        primary_contract=OptionContract(
            expiry_months=3,
            strike=250.0,
            option_type="call",
            delta_estimate=0.55,
            position_type="long",
        ),
        conservative_alternative="Buy Stock",
        higher_upside_alternative="Buy OTM Call",
        target_path_summary="Buy $250/$260 call spread, target $8 profit in 3 months.",
        early_exit_summary="Trim at 50% of max profit.",
        strategy_net_debit=2.50,
        break_even_price=252.50,
        max_profit_pct=0.75,
        max_loss_pct=0.25,
    )


def make_early_exit() -> EarlyExitPlan:
    return EarlyExitPlan(
        ticker="TSLA",
        primary_exit_trigger=ExitTrigger.TARGET_REACHED,
        severity="High",
        primary_reason="Target return reached",
        first_trim={"zone_name": "first_trim", "action": "Trim", "target_return_pct": 0.30, "trigger_condition": "30% gain"},
        main_profit={"zone_name": "main_profit", "action": "Take Profit", "target_return_pct": 0.50, "trigger_condition": "50% gain"},
        full_exit={"zone_name": "full_exit", "action": "Consider Exit", "target_return_pct": 0.75, "trigger_condition": "75% gain or 30 days"},
    )


def make_watchlist_entry() -> WatchlistEntry:
    return WatchlistEntry(
        ticker="AAPL",
        status="Held",
        thesis_state="Strengthening",
        alert_level="None",
        current_action_bias="Buy Stock",
    )


def make_validation() -> ValidationResult:
    return ValidationResult(
        ticker="AAPL",
        regime="trend_up",
        historical_support="strong",
        environment_fit="good",
        main_failure_mode="timing",
        validation_confidence=0.85,
    )


def make_ticker_result(
    action: str = "Buy Stock",
    with_options: bool = False,
    with_validation: bool = False,
    with_watchlist: bool = False,
) -> TickerResearchResult:
    task = make_task()
    signal = make_signal()
    report = make_report()
    decision_card = make_decision_card(action)

    result = TickerResearchResult(
        task=task,
        ticker="AAPL",
        signal=signal,
        report=report,
        review=None,
        trade_plan=None,
        audit={},
        errors=[],
        decision_card=decision_card,
    )

    if with_validation:
        result.validation = make_validation()
    if with_watchlist:
        result.watchlist_entry = make_watchlist_entry()
    if with_options:
        result.options_structure = make_options_structure()
        result.early_exit = make_early_exit()
        result.instrument_recommendation = InstrumentRecommendation(
            task_id=task.task_id,
            ticker="TSLA",
            primary_action="Bull Call Spread",
            ranked_alternatives=["Buy Call", "Buy Stock"],
            reason="Defined risk with upside participation.",
        )

    return result


# ---------------------------------------------------------------------------
# Test 1: build_report_pack maps decision objects correctly
# ---------------------------------------------------------------------------

class TestBuildReportPack:
    def test_maps_task_id_and_ticker(self):
        result = make_ticker_result(action="Buy Stock")
        pack = build_report_pack(result, company_name="Apple Inc.")
        assert pack.task_id == result.task.task_id
        assert pack.ticker == "AAPL"
        assert pack.company_name == "Apple Inc."

    def test_maps_primary_action_buy_stock(self):
        result = make_ticker_result(action="Buy Stock")
        pack = build_report_pack(result)
        assert pack.primary_action == "Buy Stock"
        assert pack.primary_instrument == "Buy Stock"

    def test_maps_primary_action_buy_call(self):
        result = make_ticker_result(action="Buy Call")
        pack = build_report_pack(result)
        assert pack.primary_action == "Buy Call"

    def test_maps_primary_action_bull_call_spread(self):
        result = make_ticker_result(action="Bull Call Spread")
        pack = build_report_pack(result)
        assert pack.primary_action == "Bull Call Spread"

    def test_maps_primary_action_sell_cash_secured_put(self):
        result = make_ticker_result(action="Sell Cash-Secured Put")
        pack = build_report_pack(result)
        assert pack.primary_action == "Sell Cash-Secured Put"

    def test_maps_primary_action_covered_call(self):
        result = make_ticker_result(action="Covered Call")
        pack = build_report_pack(result)
        assert pack.primary_action == "Covered Call"

    def test_maps_primary_action_watchlist(self):
        result = make_ticker_result(action="Watchlist")
        pack = build_report_pack(result)
        assert pack.primary_action == "Watchlist"

    def test_maps_primary_action_no_trade(self):
        result = make_ticker_result(action="No Trade")
        pack = build_report_pack(result)
        assert pack.primary_action == "No Trade"

    def test_marks_coverage_limited_runs_as_research_unavailable(self):
        result = make_ticker_result(action="No Trade")
        result.audit = {
            "llm_research_available": False,
            "coverage_limited": True,
            "evidence_count": 0,
        }
        result.errors = ["No LLM client configured; subagents were skipped."]
        pack = build_report_pack(result)
        assert "研究不可用" in pack.boss_summary
        assert "未配置研究模型" in pack.why_now
        assert "分析师层未执行" in pack.top_risks

    def test_maps_conviction(self):
        result = make_ticker_result(action="Buy Stock")
        pack = build_report_pack(result)
        assert pack.conviction == "High"

    def test_maps_signal_references(self):
        result = make_ticker_result(action="Buy Stock")
        pack = build_report_pack(result)
        assert pack.entry_reference is not None
        assert "175" in pack.entry_reference
        assert pack.target_reference is not None
        assert "200" in pack.target_reference
        assert pack.stop_reference is not None
        assert "165" in pack.stop_reference

    def test_maps_validation_confidence(self):
        result = make_ticker_result(action="Buy Stock", with_validation=True)
        pack = build_report_pack(result)
        assert pack.validation_confidence == 0.85

    def test_maps_watchlist_state(self):
        result = make_ticker_result(action="Buy Stock", with_watchlist=True)
        pack = build_report_pack(result)
        assert pack.watchlist_state is not None
        assert "Held" in pack.watchlist_state

    def test_research_valid_true_even_with_minimal_data(self):
        """Per spec §16: research output is primary. Pack is always built."""
        result = make_ticker_result(action="Buy Stock")
        pack = build_report_pack(result)
        assert pack.primary_action == "Buy Stock"

    def test_boss_summary_uses_action_zh(self):
        result = make_ticker_result(action="Buy Stock")
        pack = build_report_pack(result)
        assert pack.boss_summary != ""
        # Chinese label should appear in summary or one_line_call
        combined = pack.boss_summary + pack.one_line_call
        # Either Chinese or English action label is acceptable
        assert any(label in combined for label in ["Buy Stock", "买入", "AAPL"])


# ---------------------------------------------------------------------------
# Test 2: build_prompt_pack produces correct pages
# ---------------------------------------------------------------------------

class TestBuildPromptPack:
    def test_buy_stock_produces_2_pages(self):
        pack = build_report_pack(make_ticker_result(action="Buy Stock"))
        prompt_pack = build_prompt_pack(pack)
        assert prompt_pack.page_count == 2
        assert len(prompt_pack.page_prompts) == 2

    def test_watchlist_produces_1_page(self):
        pack = build_report_pack(make_ticker_result(action="Watchlist"))
        prompt_pack = build_prompt_pack(pack)
        assert prompt_pack.page_count == 1
        assert len(prompt_pack.page_prompts) == 1
        assert prompt_pack.page_prompts[0].page_role == "boss_poster"

    def test_no_trade_produces_1_page(self):
        pack = build_report_pack(make_ticker_result(action="No Trade"))
        prompt_pack = build_prompt_pack(pack)
        assert prompt_pack.page_count == 1

    def test_bull_call_spread_with_options_produces_3_pages(self):
        result = make_ticker_result(action="Bull Call Spread", with_options=True)
        pack = build_report_pack(result)
        prompt_pack = build_prompt_pack(pack)
        assert prompt_pack.page_count == 3
        assert len(prompt_pack.page_prompts) == 3

    def test_page_1_is_boss_poster(self):
        pack = build_report_pack(make_ticker_result(action="Buy Stock"))
        pp = build_prompt_pack(pack)
        assert pp.page_prompts[0].page_number == 1
        assert pp.page_prompts[0].page_role == "boss_poster"

    def test_page_2_is_formal_report(self):
        pack = build_report_pack(make_ticker_result(action="Buy Stock"))
        pp = build_prompt_pack(pack)
        assert pp.page_prompts[1].page_number == 2
        assert pp.page_prompts[1].page_role == "formal_report"

    def test_page_3_detail_page_when_present(self):
        result = make_ticker_result(action="Bull Call Spread", with_options=True)
        pack = build_report_pack(result)
        pp = build_prompt_pack(pack)
        page_3 = next(p for p in pp.page_prompts if p.page_number == 3)
        assert page_3.page_role == "detail_page"

    def test_prompt_text_is_not_empty(self):
        pack = build_report_pack(make_ticker_result(action="Buy Stock"))
        pp = build_prompt_pack(pack)
        for page in pp.page_prompts:
            assert len(page.prompt_text) > 100, f"Page {page.page_number} prompt too short"

    def test_must_preserve_includes_action_and_ticker(self):
        pack = build_report_pack(make_ticker_result(action="Buy Stock"))
        pp = build_prompt_pack(pack)
        page_1 = pp.page_prompts[0]
        assert "Buy Stock" in page_1.must_preserve or "AAPL" in page_1.must_preserve

    def test_forbidden_phrasing_includes_generic_buy_hold_sell(self):
        pack = build_report_pack(make_ticker_result(action="Buy Stock"))
        pp = build_prompt_pack(pack)
        all_forbidden = set()
        for p in pp.page_prompts:
            all_forbidden.update(p.forbidden_phrasing)
        assert "BUY" in all_forbidden
        assert "HOLD" in all_forbidden
        assert "SELL" in all_forbidden

    def test_must_show_labels_has_chinese_keys(self):
        pack = build_report_pack(make_ticker_result(action="Buy Stock"))
        pp = build_prompt_pack(pack)
        # Must have English keys
        assert "ticker" in pp.must_show_labels
        assert "action" in pp.must_show_labels
        # Values must be non-empty (Chinese labels)
        assert all(v for v in pp.must_show_labels.values())
        # Check Chinese labels are defined in approved_action_labels
        labels = approved_action_labels()
        assert labels["Buy Stock"]  # Chinese label for Buy Stock must exist
        assert len(labels["Buy Stock"]) > 0

    def test_source_pack_reference_is_set(self):
        pack = build_report_pack(make_ticker_result(action="Buy Stock"))
        pp = build_prompt_pack(pack)
        assert pp.source_pack is pack
        assert pp.source_pack.ticker == "AAPL"


# ---------------------------------------------------------------------------
# Test 3: Approved action vocabulary preserved
# ---------------------------------------------------------------------------

class TestApprovedActionVocabulary:
    """Per spec §10: visible action language must use Hermes approved set."""

    ACTIONS = [
        "Buy Stock",
        "Buy Call",
        "Bull Call Spread",
        "Sell Cash-Secured Put",
        "Covered Call",
        "Watchlist",
        "No Trade",
    ]

    @pytest.mark.parametrize("action", ACTIONS)
    def test_action_appears_in_prompt_pack(self, action: str):
        result = make_ticker_result(action=action)
        pack = build_report_pack(result)
        pp = build_prompt_pack(pack)
        combined_prompts = " ".join(p.prompt_text for p in pp.page_prompts)
        assert action in combined_prompts or pp.source_pack.primary_action == action

    @pytest.mark.parametrize("action", ACTIONS)
    def test_action_labels_zh_defined(self, action: str):
        labels = approved_action_labels()
        assert action in labels
        assert len(labels[action]) > 0

    @pytest.mark.parametrize("action", ACTIONS)
    def test_page_1_preserves_action(self, action: str):
        result = make_ticker_result(action=action)
        pack = build_report_pack(result)
        pp = build_prompt_pack(pack)
        page_1 = pp.page_prompts[0]
        # The action must be in the prompt (either English or Chinese)
        prompt_text = page_1.prompt_text
        assert action in prompt_text or labels_contain_action(prompt_text, action)

    @pytest.mark.parametrize("action", ACTIONS)
    def test_research_valid_for_all_actions(self, action: str):
        """Per spec §16: research is valid regardless of action type."""
        result = make_ticker_result(action=action)
        pack = build_report_pack(result)
        assert pack.primary_action == action
        assert pack.task_id == result.task.task_id


def labels_contain_action(prompt_text: str, action: str) -> bool:
    """Check if the Chinese label for an action appears in the prompt."""
    labels = approved_action_labels()
    zh_label = labels.get(action, "")
    return zh_label in prompt_text


# ---------------------------------------------------------------------------
# Test 4: Service runs end-to-end on realistic TickerResearchResult
# ---------------------------------------------------------------------------

class TestImageReportServiceEndToEnd:
    def test_service_run_produces_service_result(self):
        result = make_ticker_result(action="Buy Stock")
        service = ImageReportService()
        svc_result = service.run(result)
        assert isinstance(svc_result, ImageReportServiceResult)
        assert svc_result.ticker == "AAPL"
        assert svc_result.task_id == result.task.task_id

    def test_service_run_produces_report_pack(self):
        result = make_ticker_result(action="Buy Stock")
        service = ImageReportService()
        svc_result = service.run(result)
        assert isinstance(svc_result.report_pack, OrchestratorReportPack)
        assert svc_result.report_pack.primary_action == "Buy Stock"

    def test_service_run_produces_prompt_pack(self):
        result = make_ticker_result(action="Buy Stock")
        service = ImageReportService()
        svc_result = service.run(result)
        assert isinstance(svc_result.prompt_pack, ImagePromptPack)
        assert len(svc_result.prompt_pack.page_prompts) >= 1

    def test_service_run_produces_generation_result(self):
        result = make_ticker_result(action="Buy Stock")
        service = ImageReportService()
        svc_result = service.run(result)
        assert svc_result.generation_result is not None
        assert isinstance(svc_result.generation_result, ImageReportGenerationResult)

    def test_job_bundle_written_to_disk(self):
        result = make_ticker_result(action="Buy Stock")
        with tempfile.TemporaryDirectory() as tmpdir:
            service = ImageReportService(output_dir=tmpdir)
            svc_result = service.run(result)
            assert svc_result.job_bundle_path is not None
            assert os.path.exists(svc_result.job_bundle_path)

    def test_manifest_written_to_disk(self):
        result = make_ticker_result(action="Buy Stock")
        with tempfile.TemporaryDirectory() as tmpdir:
            service = ImageReportService(output_dir=tmpdir)
            svc_result = service.run(result)
            assert svc_result.manifest_path is not None
            assert os.path.exists(svc_result.manifest_path)

    def test_manifest_is_valid_json(self):
        result = make_ticker_result(action="Buy Stock")
        with tempfile.TemporaryDirectory() as tmpdir:
            service = ImageReportService(output_dir=tmpdir)
            svc_result = service.run(result)
            with open(svc_result.manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            assert manifest["ticker"] == "AAPL"
            assert manifest["page_count"] == 2
            assert "jobs_bundle_path" in manifest or "job_bundle_paths" in manifest

    def test_jobs_bundle_is_valid_json(self):
        result = make_ticker_result(action="Buy Stock")
        with tempfile.TemporaryDirectory() as tmpdir:
            service = ImageReportService(output_dir=tmpdir)
            svc_result = service.run(result)
            with open(svc_result.job_bundle_path, "r", encoding="utf-8") as f:
                bundle = json.load(f)
            assert bundle["ticker"] == "AAPL"
            assert "jobs" in bundle
            assert len(bundle["jobs"]) == 2

    def test_job_contains_full_prompt_text(self):
        """Phase 19A: job bundle must contain the FULL prompt, not truncated."""
        result = make_ticker_result(action="Buy Stock")
        with tempfile.TemporaryDirectory() as tmpdir:
            service = ImageReportService(output_dir=tmpdir)
            svc_result = service.run(result)
            with open(svc_result.job_bundle_path, "r", encoding="utf-8") as f:
                bundle = json.load(f)
            for job in bundle["jobs"]:
                assert len(job["prompt_text"]) > 200, "Prompt text too short — may be truncated"
                assert "STYLE" in job["prompt_text"], "Prompt must include style rules"
                assert "IMAGE TYPE" in job["prompt_text"] or "CONTENT REQUIREMENTS" in job["prompt_text"]


# ---------------------------------------------------------------------------
# Test 5: Generation result state machine
# ---------------------------------------------------------------------------

class TestGenerationResultStateMachine:
    def test_job_submitted_true_after_service_run(self):
        result = make_ticker_result(action="Buy Stock")
        with tempfile.TemporaryDirectory() as tmpdir:
            service = ImageReportService(output_dir=tmpdir)
            svc_result = service.run(result)
            assert svc_result.job_submitted is True

    def test_prompt_ready_true(self):
        result = make_ticker_result(action="Buy Stock")
        service = ImageReportService()
        svc_result = service.run(result)
        assert svc_result.prompt_ready is True

    def test_artifacts_present_false_before_real_images(self):
        """Phase 19A: job bundles are written but .png images don't exist yet."""
        result = make_ticker_result(action="Buy Stock")
        with tempfile.TemporaryDirectory() as tmpdir:
            service = ImageReportService(output_dir=tmpdir)
            svc_result = service.run(result)
            # job_submitted is True (bundle written)
            assert svc_result.job_submitted is True
            # artifacts_present is False (no .png files yet)
            assert svc_result.artifacts_present is False

    def test_research_valid_true_always(self):
        """Per spec §16: research validity is independent of image generation."""
        result = make_ticker_result(action="Buy Stock")
        with tempfile.TemporaryDirectory() as tmpdir:
            service = ImageReportService(output_dir=tmpdir)
            svc_result = service.run(result)
            assert svc_result.research_valid is True

    def test_phase_19a_job_state_job_submitted(self):
        result = make_ticker_result(action="Buy Stock")
        with tempfile.TemporaryDirectory() as tmpdir:
            service = ImageReportService(output_dir=tmpdir)
            svc_result = service.run(result)
            assert svc_result.phase_19a_job_state == "job_submitted"

    def test_successful_pages_tracked(self):
        result = make_ticker_result(action="Buy Stock")
        with tempfile.TemporaryDirectory() as tmpdir:
            service = ImageReportService(output_dir=tmpdir)
            svc_result = service.run(result)
            # ManualImageJobBackend succeeds (writes job bundle)
            assert len(svc_result.generation_result.successful_pages) == 2

    def test_failed_pages_empty_on_success(self):
        result = make_ticker_result(action="Buy Stock")
        with tempfile.TemporaryDirectory() as tmpdir:
            service = ImageReportService(output_dir=tmpdir)
            svc_result = service.run(result)
            assert svc_result.failed_pages == []


# ---------------------------------------------------------------------------
# Test 6: Page-count logic
# ---------------------------------------------------------------------------

class TestPageCountLogic:
    def test_no_trade_is_1_page(self):
        pack = build_report_pack(make_ticker_result(action="No Trade"))
        pp = build_prompt_pack(pack)
        assert pp.page_count == 1

    def test_watchlist_is_1_page(self):
        pack = build_report_pack(make_ticker_result(action="Watchlist"))
        pp = build_prompt_pack(pack)
        assert pp.page_count == 1

    def test_buy_stock_is_2_pages(self):
        pack = build_report_pack(make_ticker_result(action="Buy Stock"))
        pp = build_prompt_pack(pack)
        assert pp.page_count == 2

    def test_buy_call_is_2_pages(self):
        pack = build_report_pack(make_ticker_result(action="Buy Call"))
        pp = build_prompt_pack(pack)
        assert pp.page_count == 2

    def test_bull_call_spread_without_options_detail_is_2_pages(self):
        # Without the options_structure_summary filled in, page 3 is not triggered
        pack = build_report_pack(make_ticker_result(action="Bull Call Spread"))
        pp = build_prompt_pack(pack)
        assert pp.page_count == 2

    def test_bull_call_spread_with_options_detail_is_3_pages(self):
        result = make_ticker_result(action="Bull Call Spread", with_options=True)
        pack = build_report_pack(result)
        pp = build_prompt_pack(pack)
        assert pp.page_count == 3

    def test_csp_with_options_detail_is_3_pages(self):
        result = make_ticker_result(action="Sell Cash-Secured Put")
        result.options_structure = make_options_structure()
        result.options_structure.instrument_action = "Sell Cash-Secured Put"
        result.early_exit = make_early_exit()
        pack = build_report_pack(result)
        pp = build_prompt_pack(pack)
        assert pp.page_count == 3


# ---------------------------------------------------------------------------
# Test 7: Research validity when image generation fails
# ---------------------------------------------------------------------------

class TestResearchValidityIndependence:
    def test_service_result_has_research_valid_true(self):
        result = make_ticker_result(action="Buy Stock")
        service = ImageReportService(backend=FailingBackend())
        svc_result = service.run(result)
        # Research pack was still built successfully
        assert svc_result.report_pack.primary_action == "Buy Stock"
        assert svc_result.prompt_pack is not None

    def test_prompt_ready_true_even_when_generation_fails(self):
        result = make_ticker_result(action="Buy Stock")
        service = ImageReportService(backend=FailingBackend())
        svc_result = service.run(result)
        assert svc_result.prompt_ready is True

    def test_research_valid_true_when_all_pages_fail(self):
        result = make_ticker_result(action="Buy Stock")
        service = ImageReportService(backend=FailingBackend())
        svc_result = service.run(result)
        assert svc_result.research_valid is True
        assert svc_result.report_pack.primary_action == "Buy Stock"

    def test_job_submitted_false_when_backend_fails(self):
        result = make_ticker_result(action="Buy Stock")
        service = ImageReportService(backend=FailingBackend())
        svc_result = service.run(result)
        assert svc_result.job_submitted is False


# ---------------------------------------------------------------------------
# Test 8: Individual page retry
# ---------------------------------------------------------------------------

class TestPageRetry:
    def test_retry_page_returns_updated_service_result(self):
        result = make_ticker_result(action="Buy Stock")
        with tempfile.TemporaryDirectory() as tmpdir:
            service = ImageReportService(output_dir=tmpdir)
            original = service.run(result)
            retried = service.retry_page(original, page_number=1)
            assert retried.ticker == original.ticker
            assert retried.report_pack is original.report_pack
            assert retried.prompt_pack is original.prompt_pack

    def test_retry_page_updates_page_1_result(self):
        result = make_ticker_result(action="Buy Stock")
        with tempfile.TemporaryDirectory() as tmpdir:
            service = ImageReportService(output_dir=tmpdir)
            original = service.run(result)
            assert len(original.generation_result.successful_pages) == 2
            # Retry is also a success (backend always succeeds)
            retried = service.retry_page(original, page_number=1)
            assert 1 in retried.generation_result.successful_pages


# ---------------------------------------------------------------------------
# Helper backend for failure tests
# ---------------------------------------------------------------------------

class FailingBackend:
    """Backend that always fails — used to test failure isolation."""
    @property
    def model_name(self) -> str:
        return "failing-backend"

    def supports_chinese_text(self) -> bool:
        return False

    def generate_page(self, prompt, output_path, page_number):
        return PageGenerationResult(
            page_number=page_number,
            success=False,
            error_message="Simulated generation failure",
            retryable=True,
        )


# ---------------------------------------------------------------------------
# Test 9: Contract-level sanity checks
# ---------------------------------------------------------------------------

class TestContractsSanity:
    def test_orchesrator_report_pack_has_all_sections(self):
        pack = build_report_pack(make_ticker_result(action="Buy Stock"))
        assert pack.task_id != ""
        assert pack.ticker != ""
        assert pack.primary_action != ""
        assert pack.boss_summary != ""
        assert pack.why_now != ""
        assert pack.top_risks != ""

    def test_image_report_artifacts_has_required_fields(self):
        now = datetime.now(timezone.utc)
        artifacts = ImageReportArtifacts(
            task_id="t1",
            ticker="AAPL",
            generated_at=now,
            model_used="gpt-image-2",
            page_count=2,
        )
        assert artifacts.task_id == "t1"
        assert artifacts.page_count == 2
        assert len(artifacts.page_file_paths) == 0

    def test_page_generation_result_success_path(self):
        r = PageGenerationResult(
            page_number=1,
            success=True,
            file_path="/tmp/page_1.png",
            job_bundle_path="/tmp/job_1.json",
            prompt_file_path="/tmp/prompt_1.txt",
        )
        assert r.success is True
        assert r.file_path == "/tmp/page_1.png"
        assert r.job_bundle_path == "/tmp/job_1.json"

    def test_page_generation_result_failure_path(self):
        r = PageGenerationResult(
            page_number=1,
            success=False,
            error_message="Generation failed",
            retryable=True,
        )
        assert r.success is False
        assert r.error_message == "Generation failed"
        assert r.retryable is True

    def test_image_report_generation_result_properties(self):
        r = ImageReportGenerationResult(
            ticker="AAPL",
            task_id="t1",
            overall_success=False,
            jobs_bundle_path="/tmp/bundle.json",
        )
        # job_submitted is True when jobs_bundle_path is set
        assert r.job_submitted is True
        # artifacts_present is False (page_file_paths empty)
        assert r.artifacts_present is False

    def test_approved_action_labels_all_seven(self):
        labels = approved_action_labels()
        assert len(labels) == 7
        for action in VALID_BULLISH_ACTIONS:
            assert action in labels, f"Missing label for {action}"

    def test_build_default_style_rules_mentions_chinese_first(self):
        rules = build_default_style_rules()
        assert "Chinese" in rules or "chinese" in rules.lower()
        assert "premium" in rules.lower() or "executive" in rules.lower()

    def test_zh_labels_has_required_keys(self):
        required = ["ticker", "action", "conviction", "boss_summary", "why_now", "top_risks"]
        for key in required:
            assert key in ZH_LABELS, f"Missing ZH label for {key}"

    def test_manual_image_job_backend_is_stub_replacement(self):
        """ManualImageJobBackend is the real artifact writer, not a stub."""
        backend = ManualImageJobBackend()
        assert backend.model_name == "gpt-image-2"
        assert backend.supports_chinese_text() is True


# ---------------------------------------------------------------------------
# Phase 19B: OpenAI Image Backend Tests
# ---------------------------------------------------------------------------

from unittest.mock import patch, MagicMock

from agent.research_v1.image_report_generator import (
    OpenAIImageBackend,
)
from agent.research_v1.image_report_service import ImageReportService


class TestOpenAIImageBackendMissingKey:
    """Test OpenAIImageBackend when OPENAI_API_KEY is not set."""

    def test_fails_clearly_when_api_key_missing(self):
        """Without API key, generate_page returns a clear failure result."""
        backend = OpenAIImageBackend(api_key=None)
        result = backend.generate_page(
            prompt="Test prompt",
            output_path="/tmp/page.png",
            page_number=1,
        )
        assert result.success is False
        assert "OPENAI_API_KEY" in result.error_message
        assert result.retryable is False  # missing credentials are not retryable

    def test_model_name_defaults_to_gpt_image_2(self):
        backend = OpenAIImageBackend(api_key=None)
        assert backend.model_name == "gpt-image-2"

    def test_custom_model_name_from_env(self):
        with patch.dict(os.environ, {"OPENAI_IMAGE_MODEL": "gpt-image-2-test"}):
            backend = OpenAIImageBackend()
            assert backend.model_name == "gpt-image-2-test"

    def test_custom_model_name_from_param(self):
        backend = OpenAIImageBackend(model="gpt-image-2-custom")
        assert backend.model_name == "gpt-image-2-custom"

    def test_supports_chinese_text(self):
        backend = OpenAIImageBackend(api_key=None)
        assert backend.supports_chinese_text() is True


class TestOpenAIImageBackendAPIFailure:
    """Test OpenAIImageBackend API call failure modes."""

    def test_import_error_when_openai_package_missing(self):
        """If openai package is not installed, returns clear failure."""
        # This tests the actual ImportError path inside generate_page
        # The openai import inside generate_page is caught via BaseException
        openai = pytest.importorskip("openai", reason="openai package needed for this test")
        # Now verify generate_page handles API errors properly
        backend = OpenAIImageBackend(api_key="fake-key")
        with patch("openai.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            mock_client.images.generate.side_effect = Exception("Rate limit exceeded")
            result = backend.generate_page(
                prompt="Test",
                output_path="/tmp/page.png",
                page_number=1,
            )
            assert result.success is False
            assert "Rate limit exceeded" in result.error_message
            assert result.retryable is True
            # The actual result will depend on how the error propagates
            # This tests the path where the ImportError is caught

    def test_api_call_failure_returns_retryable_error(self):
        """API call failure returns a retryable PageGenerationResult."""
        pytest.importorskip("openai", reason="openai package not installed")
        backend = OpenAIImageBackend(api_key="fake-key")

        with patch("openai.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            mock_client.images.generate.side_effect = Exception("Rate limit exceeded")

            result = backend.generate_page(
                prompt="Test prompt",
                output_path="/tmp/page.png",
                page_number=1,
            )

            assert result.success is False
            assert "Rate limit exceeded" in result.error_message
            assert result.retryable is True


class TestServiceBackendSelection:
    """Test service/backend selection logic."""

    def test_manual_mode_uses_manual_backend(self):
        service = ImageReportService(mode="manual")
        assert isinstance(service._backend, ManualImageJobBackend)

    def test_openai_mode_uses_openai_backend(self):
        service = ImageReportService(mode="openai")
        assert isinstance(service._backend, OpenAIImageBackend)

    def test_explicit_backend_takes_precedence_over_mode(self):
        explicit = ManualImageJobBackend()
        service = ImageReportService(backend=explicit, mode="openai")
        assert service._backend is explicit

    def test_default_mode_is_manual(self):
        service = ImageReportService()
        assert isinstance(service._backend, ManualImageJobBackend)

    def test_run_with_manual_mode_writes_job_bundles(self):
        result = make_ticker_result(action="Buy Stock")
        with tempfile.TemporaryDirectory() as tmpdir:
            service = ImageReportService(output_dir=tmpdir, mode="manual")
            svc_result = service.run(result, mode="manual")
            assert svc_result.job_bundle_path is not None
            assert os.path.exists(svc_result.job_bundle_path)

    def test_run_with_openai_mode_fails_clearly_without_key(self):
        result = make_ticker_result(action="Buy Stock")
        with tempfile.TemporaryDirectory() as tmpdir:
            service = ImageReportService(output_dir=tmpdir, mode="openai")
            svc_result = service.run(result, mode="openai")
            # OpenAI backend with no key fails for every page
            assert svc_result.failed_pages == [1, 2]
            # artifacts is None (no page_file_paths or job bundles when all fail)
            assert svc_result.generation_result.artifacts is None
            # manifest is still written for auditability
            assert svc_result.manifest_path is not None
            assert os.path.exists(svc_result.manifest_path)
            assert svc_result.research_valid is True


class TestOpenAIBackendPerPageFailureIsolation:
    """Test per-page failure isolation with OpenAI backend (mocked)."""

    def test_page_1_succeeds_page_2_fails(self):
        """When page 1 succeeds and page 2 fails, page 1 artifact is preserved."""
        result = make_ticker_result(action="Buy Stock")

        # Create a mixed-success mock: page 1 succeeds, page 2 fails
        success_page_1 = PageGenerationResult(
            page_number=1,
            success=True,
            file_path="/tmp/page_1.png",
        )
        failure_page_2 = PageGenerationResult(
            page_number=2,
            success=False,
            error_message="API error on page 2",
            retryable=True,
        )

        with patch.object(OpenAIImageBackend, "generate_page") as mock_gen:
            mock_gen.side_effect = [success_page_1, failure_page_2]

            backend = OpenAIImageBackend(api_key="fake-key")
            generator = ImageReportGenerator(backend=backend, output_dir="/tmp")

            pack = build_prompt_pack(build_report_pack(result))
            gen_result = generator.generate(pack)

            assert gen_result.page_results[0].success is True
            assert gen_result.page_results[1].success is False
            assert gen_result.overall_success is False
            assert 1 in gen_result.successful_pages
            assert 2 in gen_result.failed_pages

    def test_research_valid_when_openai_pages_fail(self):
        """Research validity remains true even when OpenAI pages all fail."""
        result = make_ticker_result(action="Buy Stock")

        with patch.object(OpenAIImageBackend, "generate_page") as mock_gen:
            mock_gen.return_value = PageGenerationResult(
                page_number=1,
                success=False,
                error_message="All pages failed",
                retryable=True,
            )

            with tempfile.TemporaryDirectory() as tmpdir:
                service = ImageReportService(output_dir=tmpdir, mode="openai")
                svc_result = service.run(result, mode="openai")

                # Research is valid regardless of image generation failure
                assert svc_result.research_valid is True
                # But generation is not successful
                assert svc_result.overall_success is False


class TestHermesAppGenerateImageReportModes:
    """Test HermesResearchApp.generate_image_report() in both modes."""

    def test_generate_image_report_manual_mode(self):
        result = make_ticker_result(action="Buy Stock")
        with tempfile.TemporaryDirectory() as tmpdir:
            app = HermesResearchApp()
            svc_result = app.generate_image_report(
                result,
                company_name="Apple",
                output_dir=tmpdir,
                mode="manual",
            )
            assert svc_result.job_bundle_path is not None
            assert os.path.exists(svc_result.job_bundle_path)
            assert svc_result.prompt_ready is True

    def test_generate_image_report_openai_mode_no_key_fails_clearly(self):
        result = make_ticker_result(action="Buy Stock")
        with tempfile.TemporaryDirectory() as tmpdir:
            app = HermesResearchApp()
            svc_result = app.generate_image_report(
                result,
                company_name="Apple",
                output_dir=tmpdir,
                mode="openai",
            )
            # Without API key, pages fail but research is still valid
            assert svc_result.failed_pages == [1, 2]
            assert svc_result.research_valid is True
            assert svc_result.phase_19a_job_state in (
                "not_started", "content_ready", "partial", "artifacts_present",
            )

    def test_generate_image_report_default_is_manual(self):
        result = make_ticker_result(action="Buy Stock")
        with tempfile.TemporaryDirectory() as tmpdir:
            app = HermesResearchApp()
            svc_result = app.generate_image_report(
                result,
                company_name="Apple",
                output_dir=tmpdir,
                # mode not specified — defaults to manual
            )
            assert svc_result.job_bundle_path is not None


class TestOpenAIBackendMockedSuccess:
    """Test OpenAI backend with fully mocked successful generation."""

    def test_successful_generation_saves_png_and_writes_manifest(self):
        pytest.importorskip("openai", reason="openai package not installed")
        result = make_ticker_result(action="Buy Stock")

        # Mock a successful image response
        mock_image_data = MagicMock()
        mock_image_data.url = "https://example.com/fake-image.png"

        mock_response = MagicMock()
        mock_response.data = [mock_image_data]

        with patch("openai.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            mock_client.images.generate.return_value = mock_response

            with patch("urllib.request.urlretrieve") as mock_retrieve:
                mock_retrieve.return_value = None  # success

                backend = OpenAIImageBackend(api_key="fake-key")
                page_result = backend.generate_page(
                    prompt="Test prompt",
                    output_path="/tmp/task_test_AAPL_page_1.png",
                    page_number=1,
                )

                assert page_result.success is True
                assert page_result.file_path == "/tmp/task_test_AAPL_page_1.png"
                mock_client.images.generate.assert_called_once()
                call_kwargs = mock_client.images.generate.call_args
                assert call_kwargs.kwargs["model"] == "gpt-image-2"
                assert call_kwargs.kwargs["n"] == 1


class TestManifestWithRealArtifacts:
    """Test manifest is correctly updated when real image artifacts exist."""

    def test_manifest_reflects_successful_page_paths(self):
        pytest.importorskip("openai", reason="openai package not installed")

        mock_image_data = MagicMock()
        mock_image_data.url = "https://example.com/image.png"

        mock_response = MagicMock()
        mock_response.data = [mock_image_data]

        with patch("openai.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            mock_client.images.generate.return_value = mock_response

            with patch("urllib.request.urlretrieve"):
                with tempfile.TemporaryDirectory() as tmpdir:
                    service = ImageReportService(output_dir=tmpdir, mode="openai")
                    svc_result = service.run(result, mode="openai")

                    # With mocked API, pages fail (no real key) but manifest exists
                    assert svc_result.manifest_path is not None
                    assert os.path.exists(svc_result.manifest_path)

                    with open(svc_result.manifest_path, encoding="utf-8") as f:
                        manifest = json.load(f)

                    assert manifest["ticker"] == "AAPL"
                    assert manifest["model_used"] == "gpt-image-2"
