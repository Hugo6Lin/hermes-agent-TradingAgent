# -*- coding: utf-8 -*-
"""
Phase 19: Orchestrator Report Pack Builder.

Builds OrchestratorReportPack from TickerResearchResult (and related Phase 14-17
objects) after the research pipeline completes.

Per spec §7.1:
    - OrchestratorReportPack is the content truth consumed by the image pipeline
    - Built after TickerResearchResult is available
    - Must NOT be derived primarily from old generic rating/trade-plan presentation shells

Authority:
    - OrchestratorReportPack is the content authority
    - decision_locked fields must NOT be creatively rewritten
    - If narrative conflicts with locked facts, locked facts win
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from agent.research_v1.image_report_contracts import (
    OrchestratorReportPack,
    build_default_style_rules,
)

if TYPE_CHECKING:
    from agent.research_v1.app import TickerResearchResult
    from agent.research_v1.contracts import (
        CanonicalSignal,
        CanonicalReport,
        PositionDecisionCard,
        InstrumentRecommendation,
        OptionsStructure,
        EarlyExitPlan,
        WatchlistEntry,
        ValidationResult,
    )


# ---------------------------------------------------------------------------
# Approved action vocabulary (spec §10)
# ---------------------------------------------------------------------------

VALID_BULLISH_ACTIONS = frozenset([
    "Buy Stock",
    "Buy Call",
    "Bull Call Spread",
    "Sell Cash-Secured Put",
    "Covered Call",
    "Watchlist",
    "No Trade",
])


def _is_research_unavailable(result: "TickerResearchResult") -> bool:
    """Return True when the analyst layer did not run and output is fallback-only."""
    audit = result.audit or {}
    return bool(audit.get("coverage_limited")) and not bool(audit.get("llm_research_available"))


def _coerce_action(action: str | None) -> str:
    """Normalize action to approved vocabulary or 'No Trade' as safe default."""
    if action and action in VALID_BULLISH_ACTIONS:
        return action
    return "No Trade"


def _safe_str(val) -> str:
    """Convert anything to a safe string, '' if None."""
    if val is None:
        return ""
    return str(val)


def _safe_float(val) -> float | None:
    """Convert to float or None."""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Decision-locked mapping helpers
# ---------------------------------------------------------------------------


def _map_primary_action(
    decision_card: "PositionDecisionCard | None",
    instrument_rec: "InstrumentRecommendation | None",
    watchlist_entry: "WatchlistEntry | None",
) -> str:
    """
    Derive the locked primary action.

    Priority:
        1. decision_card.primary_action (Phase 14 explicit decision)
        2. instrument_rec.primary_action (Phase 14 instrument selection)
        3. watchlist_entry.current_action_bias (Phase 16 monitoring)
        4. CanonicalReport trade plan action
    """
    if decision_card and decision_card.primary_action:
        return _coerce_action(decision_card.primary_action)
    if instrument_rec and instrument_rec.primary_action:
        return _coerce_action(instrument_rec.primary_action)
    if watchlist_entry and watchlist_entry.current_action_bias:
        return _coerce_action(watchlist_entry.current_action_bias)
    return "No Trade"


def _map_conviction(decision_card: "PositionDecisionCard | None") -> str:
    """Extract conviction level."""
    if decision_card and decision_card.conviction:
        conviction = decision_card.conviction.strip()
        if conviction in {"High", "Medium", "Low"}:
            return conviction
    return "Medium"


def _map_suggested_size(signal: "CanonicalSignal | None") -> str:
    """Extract position size hint from signal or use a safe default."""
    if signal and signal.rating:
        # size_hint is stored in trade_plan, signal itself carries rating
        return _safe_str(getattr(signal, "size_hint", None) or "5% of portfolio")
    return "5% of portfolio"


def _map_target_window(signal: "CanonicalSignal | None") -> str:
    """Extract holding horizon / target window."""
    if signal and signal.holding_horizon:
        return signal.holding_horizon
    return "3–6 months"


def _map_references(signal: "CanonicalSignal | None") -> tuple[str | None, str | None, str | None]:
    """Extract entry / target / stop references."""
    entry_ref = None
    target_ref = None
    stop_ref = None
    if signal:
        if signal.entry_price is not None:
            entry_ref = f"entry ~${signal.entry_price:.2f}"
        if signal.take_profit is not None:
            target_ref = f"target ~${signal.take_profit:.2f}"
        if signal.stop_loss is not None:
            stop_ref = f"stop ~${signal.stop_loss:.2f}"
    return entry_ref, target_ref, stop_ref


def _map_primary_instrument(
    instrument_rec: "InstrumentRecommendation | None",
    options_structure: "OptionsStructure | None",
) -> str:
    """Map the primary instrument label."""
    if instrument_rec and instrument_rec.primary_action:
        return instrument_rec.primary_action
    if options_structure and options_structure.instrument_action:
        return options_structure.instrument_action
    return "Buy Stock"


def _map_validation_confidence(validation: "ValidationResult | None") -> float | None:
    """Extract validation confidence 0.0–1.0."""
    if validation:
        return _safe_float(validation.validation_confidence)
    return None


def _map_watchlist_state(watchlist_entry: "WatchlistEntry | None") -> str | None:
    """Extract watchlist state string."""
    if not watchlist_entry:
        return None
    return f"{watchlist_entry.status} — {watchlist_entry.thesis_state}"


def _map_alert_level(watchlist_entry: "WatchlistEntry | None") -> str | None:
    """Extract alert level."""
    if watchlist_entry:
        return watchlist_entry.alert_level
    return None


# ---------------------------------------------------------------------------
# Boss narrative helpers
# ---------------------------------------------------------------------------


def _build_boss_summary(
    primary_action: str,
    ticker: str,
    company_name: str,
    decision_card: "PositionDecisionCard | None",
    report: "CanonicalReport | None",
) -> str:
    """
    Build boss_summary per spec §9.1:
        - 2–4 short sentences
        - sentence 1 gives the action
        - sentence 2 gives the thesis
        - sentence 3 gives the time horizon or payoff framing
        - sentence 4, if used, states the biggest limiting condition
    """
    action_zh = {
        "Buy Stock": "买入股票",
        "Buy Call": "买入看涨期权",
        "Bull Call Spread": "牛市看涨价差",
        "Sell Cash-Secured Put": "卖出现金担保看跌期权",
        "Covered Call": "覆盖买入期权",
        "Watchlist": "加入观察名单",
        "No Trade": "不交易",
    }.get(primary_action, primary_action)

    thesis = ""
    if decision_card and decision_card.thesis_summary:
        thesis = decision_card.thesis_summary
    elif report and report.bull_case:
        thesis = report.bull_case.split(".")[0].strip()

    horizon = ""
    if report and report.trade_plan and report.trade_plan.holding_period:
        horizon = f"持仓周期约{report.trade_plan.holding_period}。"

    company = company_name or ticker
    if primary_action == "No Trade":
        return f"{company} 维持观察。{thesis} 当前不适合建仓。"
    if primary_action == "Watchlist":
        return f"{company} 进入观察名单。{thesis} 等待更好时机。"
    return f"{company} 建议{action_zh}。{thesis} {horizon}".strip()


def _build_why_now(
    report: "CanonicalReport | None",
    decision_card: "PositionDecisionCard | None",
) -> str:
    """
    Build why_now per spec §9.2:
        - exactly 3 bullets by default
        - each bullet is one short sentence
        - covers thesis/earnings direction, catalyst/valuation support, timing/instrument fit
    """
    bullets = []

    # Bullet 1: thesis / earnings direction
    if decision_card and decision_card.why_now:
        bullets.append(decision_card.why_now)
    elif report and report.why_now:
        bullets.append(report.why_now)

    # Bullet 2: catalyst / valuation
    if report and report.bull_case:
        bullets.append(f"催化因素：{report.bull_case.split('.')[0].strip()}")

    # Bullet 3: timing / instrument fit
    if report and report.executive_summary:
        bullets.append(f"估值支撑：{report.executive_summary[:80].strip()}")

    # Ensure exactly 3 bullets
    while len(bullets) < 3:
        bullets.append("当前市场环境支持此投资决策。")
    return "\n".join(f"- {b}" for b in bullets[:3])


def _build_top_risks(
    report: "CanonicalReport | None",
    decision_card: "PositionDecisionCard | None",
) -> str:
    """
    Build top_risks per spec §9.3:
        - 3 bullets ordered by severity
        - covers thesis risk, timing/market risk, instrument/execution risk
    """
    risks = []

    if report and report.bear_case:
        risks.append(f"基本面风险：{report.bear_case.split('.')[0].strip()}")
    if decision_card and hasattr(decision_card, "alternatives") and decision_card.alternatives:
        # Rejected alternatives often highlight what could go wrong
        risks.append(f"替代方案风险：{'；'.join(decision_card.alternatives[:2])}")

    risks.append("市场时机风险：短期波动可能影响建仓成本。")

    return "\n".join(f"- {r}" for r in risks[:3])


def _build_one_line_call(
    primary_action: str,
    ticker: str,
    conviction: str,
) -> str:
    """Build the single-sentence decision board call."""
    action_zh = {
        "Buy Stock": "买入",
        "Buy Call": "买入看涨期权",
        "Bull Call Spread": "牛市价差",
        "Sell Cash-Secured Put": "卖出看跌期权",
        "Covered Call": "覆盖期权",
        "Watchlist": "观察",
        "No Trade": "不交易",
    }.get(primary_action, primary_action)

    conviction_zh = {"High": "高确信", "Medium": "中确信", "Low": "低确信"}.get(conviction, conviction)
    return f"{ticker} {action_zh} — {conviction_zh}"


# ---------------------------------------------------------------------------
# Research core helpers
# ---------------------------------------------------------------------------


def _map_thesis_summary(
    decision_card: "PositionDecisionCard | None",
    report: "CanonicalReport | None",
) -> str:
    """Extract thesis summary."""
    if decision_card and decision_card.thesis_summary:
        return decision_card.thesis_summary
    if report and report.executive_summary:
        return report.executive_summary
    return ""


def _map_bull_case(report: "CanonicalReport | None") -> str:
    """Extract bull case."""
    if report and report.bull_case:
        return report.bull_case
    return ""


def _map_bear_case(report: "CanonicalReport | None") -> str:
    """Extract bear case."""
    if report and report.bear_case:
        return report.bear_case
    return ""


def _map_catalysts(report: "CanonicalReport | None") -> str:
    """Extract catalysts from report or thesis."""
    if report and hasattr(report, "catalysts"):
        return _safe_str(report.catalysts)
    # Fall back to bull_case as it often contains catalysts
    if report and report.bull_case:
        return report.bull_case
    return ""


def _map_technical_summary(report: "CanonicalReport | None") -> str:
    """Extract technical summary from report appendix."""
    if report and report.appendix:
        tech = report.appendix.get("technical_summary", "")
        if tech:
            return tech
    return ""


def _map_valuation_summary(report: "CanonicalReport | None") -> str:
    """Extract valuation summary from report."""
    if report and report.appendix:
        val = report.appendix.get("valuation_summary", "")
        if val:
            return val
    if report and report.executive_summary:
        return report.executive_summary
    return ""


def _collect_must_show_numbers(
    signal: "CanonicalSignal | None",
    options_structure: "OptionsStructure | None",
    report: "CanonicalReport | None",
) -> list[str]:
    """Collect all numeric facts that must be preserved visually."""
    numbers = []
    if signal:
        if signal.entry_price is not None:
            numbers.append(f"entry_price={signal.entry_price}")
        if signal.take_profit is not None:
            numbers.append(f"take_profit={signal.take_profit}")
        if signal.stop_loss is not None:
            numbers.append(f"stop_loss={signal.stop_loss}")
    if options_structure:
        if options_structure.break_even_price is not None:
            numbers.append(f"break_even={options_structure.break_even_price}")
        if options_structure.max_profit_pct is not None:
            numbers.append(f"max_profit_pct={options_structure.max_profit_pct}")
        if options_structure.max_loss_pct is not None:
            numbers.append(f"max_loss_pct={options_structure.max_loss_pct}")
    if report and report.trade_plan:
        tp = report.trade_plan
        if tp.entry_price is not None:
            numbers.append(f"trade_entry={tp.entry_price}")
        if tp.take_profit is not None:
            numbers.append(f"trade_tp={tp.take_profit}")
        if tp.stop_loss is not None:
            numbers.append(f"trade_sl={tp.stop_loss}")
    return numbers


# ---------------------------------------------------------------------------
# Instrument plan helpers
# ---------------------------------------------------------------------------


def _map_instrument_plan(
    instrument_rec: "InstrumentRecommendation | None",
    options_structure: "OptionsStructure | None",
) -> tuple[str, str | None, str | None, str, str, str, list[str]]:
    """Returns (primary_label, conservative_alt, alt_instrument, reason, options_summary, early_exit_summary, key_numbers)."""
    primary_label = ""
    conservative_alt = None
    alt_instrument = None
    reason = ""
    options_summary = ""
    early_exit_summary = ""
    key_numbers: list[str] = []

    if instrument_rec:
        primary_label = instrument_rec.primary_action
        conservative_alt = (
            instrument_rec.ranked_alternatives[1]
            if len(instrument_rec.ranked_alternatives) > 1
            else None
        )
        reason = instrument_rec.reason

    if options_structure:
        primary_label = options_structure.instrument_action
        options_summary = options_structure.target_path_summary
        early_exit_summary = options_structure.early_exit_summary
        if options_structure.break_even_price is not None:
            key_numbers.append(f"盈亏平衡=${options_structure.break_even_price:.2f}")
        if options_structure.max_profit_pct is not None:
            key_numbers.append(f"最大盈利={options_structure.max_profit_pct:.0%}")
        if options_structure.max_loss_pct is not None:
            key_numbers.append(f"最大亏损={options_structure.max_loss_pct:.0%}")
        if options_structure.strategy_net_debit is not None:
            key_numbers.append(f"净 debit=${options_structure.strategy_net_debit:.2f}")
        if options_structure.strategy_net_credit is not None:
            key_numbers.append(f"净 credit=${options_structure.strategy_net_credit:.2f}")

    if not primary_label:
        primary_label = "Buy Stock"
    if not reason:
        reason = "基于基本面和技术面综合评估。"

    return primary_label, conservative_alt, alt_instrument, reason, options_summary, early_exit_summary, key_numbers


# ---------------------------------------------------------------------------
# Monitoring state helpers
# ---------------------------------------------------------------------------


def _map_monitoring_state(
    watchlist_entry: "WatchlistEntry | None",
    validation: "ValidationResult | None",
) -> tuple[str, str, str, str, str, str]:
    """Returns (watchlist_summary, validation_summary, main_failure_mode, environment_fit, historical_support, regime)."""
    watchlist_summary = ""
    validation_summary = ""
    main_failure_mode = "none"
    environment_fit = "good"
    historical_support = "moderate"
    regime = "unknown"

    if watchlist_entry:
        watchlist_summary = f"{watchlist_entry.status} — {watchlist_entry.thesis_state}"
    if validation:
        validation_summary = (
            f"regime={validation.regime}, "
            f"environment_fit={validation.environment_fit}, "
            f"historical_support={validation.historical_support}"
        )
        main_failure_mode = validation.main_failure_mode
        environment_fit = validation.environment_fit
        historical_support = validation.historical_support
        regime = validation.regime

    return watchlist_summary, validation_summary, main_failure_mode, environment_fit, historical_support, regime


# ---------------------------------------------------------------------------
# Main factory function
# ---------------------------------------------------------------------------


def build_report_pack(
    result: "TickerResearchResult",
    company_name: str = "",
) -> OrchestratorReportPack:
    """
    Build an OrchestratorReportPack from a TickerResearchResult.

    This is the primary factory — it maps all Phase 14-17 objects into the
    content truth consumed by the image pipeline.

    Args:
        result: TickerResearchResult from the research pipeline.
        company_name: Optional company name for display; falls back to ticker.

    Returns:
        Fully populated OrchestratorReportPack.

    Per spec §8 rules:
        - decision_locked fields must NOT be creatively rewritten
        - boss_narrative may be reformatted but must stay faithful to locked facts
        - If narrative conflicts with locked facts, locked facts win
    """
    ticker = result.ticker
    task_id = result.task.task_id
    generated_at = datetime.utcnow()
    research_unavailable = _is_research_unavailable(result)

    # Derive locked fields
    primary_action = _map_primary_action(
        result.decision_card, result.instrument_recommendation, result.watchlist_entry
    )
    conviction = _map_conviction(result.decision_card)
    suggested_size = _map_suggested_size(result.signal)
    target_window = _map_target_window(result.signal)
    entry_ref, target_ref, stop_ref = _map_references(result.signal)
    primary_instrument = _map_primary_instrument(result.instrument_recommendation, result.options_structure)
    validation_confidence = _map_validation_confidence(result.validation)
    watchlist_state = _map_watchlist_state(result.watchlist_entry)
    alert_level = _map_alert_level(result.watchlist_entry)

    # Derive boss narrative
    boss_summary = _build_boss_summary(
        primary_action, ticker, company_name, result.decision_card, result.report
    )
    why_now = _build_why_now(result.report, result.decision_card)
    top_risks = _build_top_risks(result.report, result.decision_card)
    one_line_call = _build_one_line_call(primary_action, ticker, conviction)

    if research_unavailable:
        company = company_name or ticker
        boss_summary = (
            f"{company} 研究不可用。当前运行未配置研究模型，因此分析师层未执行。"
            "当前结论仅为覆盖受限的回退输出，不应视为正式投资结论。"
        )
        why_now = "\n".join([
            "- 未配置研究模型，无法生成 analyst-level why-now。",
            "- 可能已获取市场数据，但尚未形成完整研究综合判断。",
            "- 在恢复研究提供方之前，不应基于本次输出做投资动作。",
        ])
        top_risks = "\n".join([
            "- 分析师层未执行：当前内容不代表完整研究结论。",
            "- 回退输出可能将不同标的压成相似结论，失去区分度。",
            "- 在研究提供方恢复前，任何动作建议都存在较高误导风险。",
        ])
        one_line_call = f"{ticker} 研究不可用 - 需配置研究模型"

    # Derive research core
    thesis_summary = _map_thesis_summary(result.decision_card, result.report)
    bull_case = _map_bull_case(result.report)
    bear_case = _map_bear_case(result.report)
    catalysts = _map_catalysts(result.report)
    technical_summary = _map_technical_summary(result.report)
    valuation_summary = _map_valuation_summary(result.report)
    must_show_numbers = _collect_must_show_numbers(
        result.signal, result.options_structure, result.report
    )

    # Derive instrument plan
    (
        primary_instrument_label,
        conservative_alternative,
        alt_instrument,
        instrument_choice_reason,
        options_structure_summary,
        early_exit_summary,
        options_key_numbers,
    ) = _map_instrument_plan(result.instrument_recommendation, result.options_structure)

    # Derive monitoring state
    (
        watchlist_summary,
        validation_summary,
        main_failure_mode,
        environment_fit,
        historical_support,
        regime,
    ) = _map_monitoring_state(result.watchlist_entry, result.validation)

    # Determine recommended page count (per spec: 1–3, usually 2)
    # Logic matches _decide_page_count() in image_prompt_builder
    action = primary_action
    if action in {"No Trade", "Watchlist"}:
        recommended_page_count = 1
    elif action in {"Bull Call Spread", "Sell Cash-Secured Put", "Covered Call"}:
        if result.options_structure and (
            result.options_structure.target_path_summary
            or result.options_structure.early_exit_summary
        ):
            recommended_page_count = 3
        else:
            recommended_page_count = 2
    else:
        recommended_page_count = 2

    return OrchestratorReportPack(
        # §8.1 report_identity
        task_id=task_id,
        ticker=ticker,
        company_name=company_name or ticker,
        generated_at=generated_at,
        language="zh-CN",
        report_type="boss_image_report",
        recommended_page_count=recommended_page_count,
        # §8.2 decision_locked
        primary_action=primary_action,
        conviction=conviction,
        suggested_size=suggested_size,
        target_window=target_window,
        entry_reference=entry_ref,
        target_reference=target_ref,
        stop_reference=stop_ref,
        primary_instrument=primary_instrument,
        validation_confidence=validation_confidence,
        watchlist_state=watchlist_state,
        alert_level=alert_level,
        # §8.3 boss_narrative
        boss_summary=boss_summary,
        why_now=why_now,
        top_risks=top_risks,
        one_line_call=one_line_call,
        # §8.4 research_core
        thesis_summary=thesis_summary,
        bull_case=bull_case,
        bear_case=bear_case,
        catalysts=catalysts,
        technical_summary=technical_summary,
        valuation_summary=valuation_summary,
        must_show_numbers=must_show_numbers,
        # §8.5 instrument_plan
        primary_instrument_label=primary_instrument_label,
        conservative_alternative=conservative_alternative,
        alternative_instrument=alt_instrument,
        instrument_choice_reason=instrument_choice_reason,
        options_structure_summary=options_structure_summary,
        early_exit_summary=early_exit_summary,
        options_key_numbers=options_key_numbers,
        # §8.6 monitoring_state
        watchlist_summary=watchlist_summary,
        validation_summary=validation_summary,
        main_failure_mode=main_failure_mode,
        environment_fit=environment_fit,
        historical_support=historical_support,
        regime=regime,
    )
