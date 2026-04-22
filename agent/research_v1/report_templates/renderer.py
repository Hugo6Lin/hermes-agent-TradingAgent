"""Boss Poster & Report rendering for Hermes research system.

This module translates canonical research data into two visual surfaces:
1. Boss Poster - single-page decision board (poster-style, print-ready)
2. Boss Report - multi-page executive report (document-style, archival)

Both use the same color system: orange-red (#E85A3C) + teal-green (#2DD4A8)
and the same Chinese-first bilingual hierarchy.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# Allowlist for bullish instrument types (mirrors contracts.py VALID_BULLISH_ACTIONS)
VALID_BULLISH_ACTIONS = frozenset([
    "Buy Stock",
    "Buy Call",
    "Bull Call Spread",
    "Sell Cash-Secured Put",
    "Covered Call",
    "Watchlist",
    "No Trade",
])

# Human-readable Chinese names for each valid instrument action
ACTION_ZH_NAMES = {
    "Buy Stock": "买入股票",
    "Buy Call": "买入看涨",
    "Bull Call Spread": "牛市看涨价差",
    "Sell Cash-Secured Put": "卖出备兑看跌",
    "Covered Call": "备兑看涨",
    "Watchlist": "观望",
    "No Trade": "不交易",
}

ACTION_EN_NAMES = {
    "Buy Stock": "Buy Stock",
    "Buy Call": "Buy Call",
    "Bull Call Spread": "Bull Call Spread",
    "Sell Cash-Secured Put": "Sell Cash-Secured Put",
    "Covered Call": "Covered Call",
    "Watchlist": "Watchlist",
    "No Trade": "No Trade",
}

# String constants - imported lazily to avoid circular imports
_ZH: dict[str, str] = {}
_EN: dict[str, str] = {}


def _load_strings() -> tuple[dict[str, str], dict[str, str]]:
    """Load bilingual string constants on first use."""
    global _ZH, _EN
    if not _ZH:
        try:
            from agent.research_v1.report_templates import strings_zh, strings_en
            _ZH = strings_zh.STRINGS
            _EN = strings_en.STRINGS
        except ImportError:
            # Fallback if strings not available
            _ZH = _get_fallback_zh()
            _EN = _get_fallback_en()
    return _ZH, _EN


def _get_fallback_zh() -> dict[str, str]:
    return {
        "action_buy": "买入", "action_sell": "卖出", "action_watch": "观望",
        "action_hold": "持有", "label_action": "操作", "label_ticker": "代码",
        "label_company": "公司", "label_conviction": "信心度",
        "label_target_window": "目标窗口", "label_target_price": "目标价",
        "label_suggested_size": "建议仓位", "label_why_now": "为何此时",
        "label_top_risks": "主要风险", "label_current_price": "当前价",
        "label_pe_ratio": "市盈率", "label_eps_growth": "EPS增长",
        "label_analyst_rating": "分析师评级", "label_thesis": "投资逻辑",
        "label_technical_analysis": "技术分析", "label_support": "支撑位",
        "label_resistance": "阻力位", "label_trend": "趋势",
        "label_instrument_choice": "工具选择", "label_primary": "首选",
        "label_conservative": "保守方案", "label_alternative": "备选方案",
        "label_stock": "股票", "label_call": "买入看涨",
        "label_bull_call_spread": "牛市看涨价差",
        "label_cash_secured_put": "现金担保看跌",
        "label_covered_call": "备兑看涨", "label_options_structure": "期权结构",
        "label_expiry": "到期日", "label_strike": "行权价",
        "label_break_even": "盈亏平衡", "label_delta": "Delta",
        "label_early_exit": "提前退出", "label_watchlist_state": "监控状态",
        "label_validation_summary": "验证摘要", "label_regime": "市场状态",
        "label_confidence": "信心指数", "status_held": "持仓中",
        "status_high_priority": "重点关注", "thesis_strengthening": "逻辑强化",
        "thesis_stable": "逻辑稳定", "thesis_weakening": "逻辑弱化",
        "thesis_broken": "逻辑破坏", "alert_immediate": "立即关注",
        "alert_elevated": "需要关注", "alert_normal": "正常",
        "empty_kpi": "—", "empty_thesis": "暂无投资逻辑",
        "empty_technical": "暂无技术分析", "empty_risks": "暂无风险提示",
        "empty_watchlist": "暂无监控项目", "empty_validation": "暂无验证数据",
        "no_data": "暂无数据", "label_batch_overview": "批次总览",
        "label_executive_summary": "执行摘要", "label_bottom_line": "核心结论",
        "label_bull_case": "看多逻辑", "label_risk_watch": "风险观察",
        "label_research_summary": "研究摘要", "label_reports": "报告",
        "label_decision_board": "决策看板", "label_hermes_desk": "Hermes 研究台",
    }


def _get_fallback_en() -> dict[str, str]:
    return {
        "action_buy": "Buy Stock", "action_sell": "No Trade", "action_watch": "Watchlist",
        "action_hold": "Watchlist", "label_action": "Action", "label_ticker": "Ticker",
        "label_company": "Company", "label_conviction": "Conviction",
        "label_target_window": "Target Window", "label_target_price": "Target Price",
        "label_suggested_size": "Suggested Size", "label_why_now": "Why Now",
        "label_top_risks": "Top Risks", "label_current_price": "Price",
        "label_pe_ratio": "P/E Ratio", "label_eps_growth": "EPS Growth",
        "label_analyst_rating": "Analyst Rating", "label_thesis": "Thesis",
        "label_technical_analysis": "Technical Analysis", "label_support": "Support",
        "label_resistance": "Resistance", "label_trend": "Trend",
        "label_instrument_choice": "Instrument Choice", "label_primary": "Primary",
        "label_conservative": "Conservative", "label_alternative": "Alternative",
        "label_stock": "Stock", "label_call": "Call",
        "label_bull_call_spread": "Bull Call Spread",
        "label_cash_secured_put": "Cash-Secured Put",
        "label_covered_call": "Covered Call", "label_options_structure": "Options Structure",
        "label_expiry": "Expiry", "label_strike": "Strike",
        "label_break_even": "Break-Even", "label_delta": "Delta",
        "label_early_exit": "Early Exit", "label_watchlist_state": "Watchlist",
        "label_validation_summary": "Validation", "label_regime": "Regime",
        "label_confidence": "Confidence", "status_held": "Held",
        "status_high_priority": "High Priority", "thesis_strengthening": "Strengthening",
        "thesis_stable": "Stable", "thesis_weakening": "Weakening",
        "thesis_broken": "Broken", "alert_immediate": "Immediate",
        "alert_elevated": "Elevated", "alert_normal": "Normal",
        "empty_kpi": "—", "empty_thesis": "No thesis",
        "empty_technical": "No technical data", "empty_risks": "No risk watch",
        "empty_watchlist": "No watchlist entries", "empty_validation": "No validation",
        "no_data": "No data", "label_batch_overview": "Batch Overview",
        "label_executive_summary": "Executive Summary", "label_bottom_line": "Bottom Line",
        "label_bull_case": "Bull Case", "label_risk_watch": "Risk Watch",
        "label_research_summary": "Research Summary", "label_reports": "Reports",
        "label_decision_board": "Decision Board", "label_hermes_desk": "Hermes Research Desk",
    }


# =============================================================================
# Data Classes for Poster Data
# =============================================================================

@dataclass
class PosterData:
    """Data container for rendering a Boss Poster."""

    # Top Zone
    ticker: str = ""
    company_name: str = ""
    action_zh: str = "买入"
    action_en: str = "BUY"
    conviction_zh: str = "高信心"
    conviction_en: str = "HIGH CONVICTION"
    suggested_size: str = "—"
    target_window: str = "—"
    target_price: str = "—"
    why_now: list[dict] = field(default_factory=list)
    top_risks: list[dict] = field(default_factory=list)

    # Middle Zone - KPI
    kpi: dict = field(default_factory=lambda: {
        "price": "—", "pe": "—", "eps_growth": "—", "analyst_rating": "—"
    })

    # Middle Zone - Thesis & Catalysts
    thesis_catalysts: list[dict] = field(default_factory=list)

    # Middle Zone - Technical
    technical: dict = field(default_factory=lambda: {
        "support": "—", "resistance": "—", "trend": "—"
    })

    # Middle Zone - Instrument Choice
    instruments: list[dict] = field(default_factory=list)

    # Middle Zone - Options Structure
    options: dict = field(default_factory=lambda: {
        "expiry": "—", "strike": "—", "break_even": "—", "delta": "—", "early_exit": "—"
    })

    # Middle Zone - Early Exit Zones (Phase 15)
    early_exit_zones: list[dict] = field(default_factory=list)

    # Bottom Zone
    watchlist_state: dict = field(default_factory=lambda: {
        "status_zh": "—", "status_en": "—", "status_class": "passive", "action_bias": "—"
    })
    validation: dict = field(default_factory=lambda: {
        "regime": "—", "confidence": "—", "confidence_class": ""
    })

    # Metadata
    title: str = "Hermes 投资决策看板"
    generated_at: str = ""


@dataclass
class CompanyReportData:
    """Data container for a single company report in the multi-page report.

    Structure follows spec Section 六:
    1. Decision card summary (ticker, action, conviction, bottom_line)
    2. Instrument detail (primary, conservative, alternative with reasons)
    3. Options structure detail (only if applicable)
    4. Supporting data grid (legacy signal/report fields — clearly marked as supporting)
    5. Bull case
    6. Risk watch
    """

    # 1. Decision card summary
    ticker: str = ""
    company_name: str = ""
    action_zh: str = "—"
    action_en: str = "—"
    conviction_zh: str = "—"
    conviction_en: str = "—"
    bottom_line: str = ""

    # 2. Instrument detail
    instrument_primary: dict = field(default_factory=dict)   # {name_zh, name_en, reason, role}
    instrument_conservative: dict = field(default_factory=dict)
    instrument_alternative: dict = field(default_factory=dict)

    # 3. Options structure detail
    options_detail: dict = field(default_factory=dict)

    # Early exit zones
    early_exit_zones: list[dict] = field(default_factory=list)

    # 4. Supporting data grid (legacy — explicitly supporting-only)
    supporting_entry: str = "—"
    supporting_stop: str = "—"
    supporting_target: str = "—"
    supporting_horizon: str = "—"

    # 5. Thesis and risk
    why_now: str = ""
    bull_case: str = ""
    risk_watch: list[str] = field(default_factory=list)

    # Legacy fields (kept for backward compat, not used as primary structure)
    rating_zh: str = "—"
    rating_en: str = "—"
    rating_class: str = "hold"
    confidence: str = "—"
    trade_plan: dict = field(default_factory=lambda: {})
    research_summary: str = ""


@dataclass
class BatchReportData:
    """Data container for the multi-page batch report."""

    title: str = "Hermes 研究批次报告"
    batch_date: str = ""
    batch_count: int = 0
    executive_summary: str = ""
    batch_items: list[dict] = field(default_factory=list)
    company_reports: list[CompanyReportData] = field(default_factory=list)
    watchlist_entries: list[dict] = field(default_factory=list)
    validation_results: list[dict] = field(default_factory=list)


# =============================================================================
# Rating / Status Mapping Utilities
# =============================================================================

def _map_rating(rating: str) -> tuple[str, str, str]:
    """Map rating string to (zh, en, css_class).

    For Hermes-specific instrument actions (e.g. 'Sell Cash-Secured Put'),
    this preserves them for ACTION_ZH_NAMES translation at render time.
    Generic legacy ratings degrade into Hermes-approved visible actions.
    """
    if not rating:
        return "—", "—", "hold"
    if rating in VALID_BULLISH_ACTIONS:
        css_class = "underperform" if rating == "No Trade" else ("hold" if rating == "Watchlist" else "buy")
        return ACTION_ZH_NAMES.get(rating, rating), ACTION_EN_NAMES.get(rating, rating), css_class
    rating_lower = rating.lower()
    if rating_lower in ("buy", "outperform", "bullish", "强烈买入", "买入", "跑赢大市"):
        return ACTION_ZH_NAMES["Buy Stock"], ACTION_EN_NAMES["Buy Stock"], "buy"
    elif rating_lower in ("sell", "underperform", "bearish", "卖出", "跑输大市"):
        return ACTION_ZH_NAMES["No Trade"], ACTION_EN_NAMES["No Trade"], "underperform"
    elif rating_lower in ("hold", "neutral", "中性", "观望"):
        return ACTION_ZH_NAMES["Watchlist"], ACTION_EN_NAMES["Watchlist"], "hold"
    # Unknown rating remains visible as-is, but does not regress to generic BUY/HOLD text.
    return rating, rating, "hold"


def _map_watchlist_status(status: str) -> tuple[str, str, str]:
    """Map watchlist status to (zh, en, css_class)."""
    status_lower = status.lower() if status else ""
    if status_lower in ("held", "持仓中"):
        return "持仓中", "Held", "held"
    elif status_lower in ("high priority", "high_priority", "重点关注"):
        return "重点关注", "High Priority", "high-priority"
    elif status_lower in ("research", "research in progress", "研究进行中"):
        return "研究进行中", "In Research", "research"
    elif status_lower in ("passive", "被动跟踪"):
        return "被动跟踪", "Passive", "passive"
    return status or "—", status or "—", "passive"


def _map_thesis_state(state: str) -> tuple[str, str]:
    """Map thesis state to (zh, en)."""
    state_lower = state.lower() if state else ""
    if state_lower in ("strengthening", "逻辑强化"):
        return "逻辑强化", "Strengthening"
    elif state_lower in ("stable", "逻辑稳定"):
        return "逻辑稳定", "Stable"
    elif state_lower in ("weakening", "逻辑弱化"):
        return "逻辑弱化", "Weakening"
    elif state_lower in ("broken", "逻辑破坏"):
        return "逻辑破坏", "Broken"
    return state or "—", state or "—"


def _map_alert_level(level: str) -> tuple[str, str]:
    """Map alert level to (zh, en)."""
    level_lower = level.lower() if level else ""
    if level_lower in ("immediate", "立即关注"):
        return "立即关注", "Immediate"
    elif level_lower in ("elevated", "需要关注"):
        return "需要关注", "Elevated"
    elif level_lower in ("normal", "正常"):
        return "正常", "Normal"
    elif level_lower in ("low", "低优先级"):
        return "低优先级", "Low Priority"
    return level or "—", level or "—"


def _map_confidence_class(confidence: float | str) -> str:
    """Map confidence value to CSS class."""
    try:
        val = float(confidence) if isinstance(confidence, str) else confidence
        if val >= 0.7:
            return "high"
        elif val >= 0.4:
            return "medium"
        return ""
    except (ValueError, TypeError):
        return ""


# =============================================================================
# Data Extraction from Canonical Formats
# =============================================================================

def _extract_thesis_points(text: str, max_points: int = 4) -> list[dict]:
    """Extract numbered or bulleted thesis points from text."""
    if not text:
        return []
    points = []
    lines = re.split(r"[\n\r]+", text)
    for line in lines[:max_points]:
        line = line.strip()
        if not line:
            continue
        # Remove leading numbers or bullets
        cleaned = re.sub(r"^[\d\.\)\-\*\•]+\s*", "", line)
        if cleaned:
            points.append({"zh": cleaned, "en": ""})
    return points


def _build_instruments_list(
    primary_action: str,
    ranked_alternatives: Optional[list[str]] = None,
) -> list[dict]:
    """Build instrument boxes from primary_action and ranked alternatives.

    Shows PRIMARY for the primary action, CONSERVATIVE for the first alternative,
    ALTERNATIVE for the second, and REJECTED for the remaining valid actions
    not in the chosen set.
    """
    all_actions = ["Buy Stock", "Buy Call", "Bull Call Spread", "Sell Cash-Secured Put", "Covered Call"]
    chosen = {primary_action}
    if ranked_alternatives:
        for alt in ranked_alternatives:
            if alt in VALID_BULLISH_ACTIONS:
                chosen.add(alt)

    boxes = []
    primary_found = False
    conservative_found = False

    # First add the primary
    boxes.append({
        "name_zh": ACTION_ZH_NAMES.get(primary_action, primary_action),
        "name_en": ACTION_EN_NAMES.get(primary_action, primary_action),
        "reason": "首选 / Primary",
        "role": "primary",
    })
    primary_found = True

    # Then alternatives in order
    if ranked_alternatives:
        for alt in ranked_alternatives:
            if alt in VALID_BULLISH_ACTIONS and alt != primary_action:
                if not conservative_found:
                    boxes.append({
                        "name_zh": ACTION_ZH_NAMES.get(alt, alt),
                        "name_en": ACTION_EN_NAMES.get(alt, alt),
                        "reason": "保守方案 / Conservative",
                        "role": "conservative",
                    })
                    conservative_found = True
                else:
                    boxes.append({
                        "name_zh": ACTION_ZH_NAMES.get(alt, alt),
                        "name_en": ACTION_EN_NAMES.get(alt, alt),
                        "reason": "备选方案 / Alternative",
                        "role": "alternative",
                    })

    # Fill remaining slots with rejected valid instruments
    for action in all_actions:
        if action not in chosen:
            boxes.append({
                "name_zh": ACTION_ZH_NAMES.get(action, action),
                "name_en": ACTION_EN_NAMES.get(action, action),
                "reason": "—",
                "role": "rejected",
            })

    return boxes


def _build_early_exit_zones(early_exit_plan) -> list[dict]:
    """Build early exit zone list from EarlyExitPlan object or dict.

    Returns a list of zone dicts with keys:
    - zone_name_zh, zone_name_en
    - action_zh
    - target_return (formatted as XX%)
    - trigger
    """
    if early_exit_plan is None:
        return []

    zones = []
    zone_map = {
        "first_trim": ("首轮减仓区", "First Trim Zone"),
        "main_profit": ("主要利润区", "Main Profit Zone"),
        "full_exit": ("完全退出区", "Full Exit Zone"),
    }
    for attr, (zh, en) in zone_map.items():
        zone = None
        if hasattr(early_exit_plan, attr):
            zone = getattr(early_exit_plan, attr)
        elif isinstance(early_exit_plan, dict):
            zone = early_exit_plan.get(attr)

        if zone is None:
            continue

        # Get target_return_pct
        target_return = "—"
        if hasattr(zone, "target_return_pct") and zone.target_return_pct is not None:
            target_return = f"{zone.target_return_pct:.0%}"
        elif isinstance(zone, dict):
            tr = zone.get("target_return_pct")
            if tr is not None:
                target_return = f"{tr:.0%}"

        # Get action
        action = "—"
        if hasattr(zone, "action"):
            action = zone.action
        elif isinstance(zone, dict):
            action = zone.get("action", "—")

        # Get trigger
        trigger = "—"
        if hasattr(zone, "trigger_condition"):
            trigger = zone.trigger_condition
        elif isinstance(zone, dict):
            trigger = zone.get("trigger_condition", "—")

        zones.append({
            "zone_name_zh": zh,
            "zone_name_en": en,
            "action_zh": action,
            "target_return": target_return,
            "trigger": trigger,
        })

    return zones


def _build_instrument_detail(instrument_rec, primary_action: str) -> tuple[dict, dict, dict]:
    """Build instrument primary/conservative/alternative dicts from InstrumentRecommendation.

    Returns (primary_dict, conservative_dict, alternative_dict).
    Each dict has: name_zh, name_en, reason, role.
    """
    primary = {
        "name_zh": ACTION_ZH_NAMES.get(primary_action, primary_action),
        "name_en": ACTION_EN_NAMES.get(primary_action, primary_action),
        "reason": _get_attr(instrument_rec, "reason", "首选 / Primary") if instrument_rec else "首选 / Primary",
        "role": "primary",
    }

    conservative = {"name_zh": "—", "name_en": "—", "reason": "—", "role": "conservative"}
    alternative = {"name_zh": "—", "name_en": "—", "reason": "—", "role": "alternative"}

    if instrument_rec is not None:
        ranked = _get_attr(instrument_rec, "ranked_alternatives", []) or []
        for i, alt in enumerate(ranked):
            if alt in VALID_BULLISH_ACTIONS and alt != primary_action:
                if conservative["name_zh"] == "—":
                    conservative = {
                        "name_zh": ACTION_ZH_NAMES.get(alt, alt),
                        "name_en": ACTION_EN_NAMES.get(alt, alt),
                        "reason": "保守方案 / Conservative",
                        "role": "conservative",
                    }
                elif alternative["name_zh"] == "—":
                    alternative = {
                        "name_zh": ACTION_ZH_NAMES.get(alt, alt),
                        "name_en": ACTION_EN_NAMES.get(alt, alt),
                        "reason": "备选方案 / Alternative",
                        "role": "alternative",
                    }

    return primary, conservative, alternative


def _build_options_detail(options_structure, early_exit_plan) -> dict:
    """Build options detail dict from OptionsStructure object or dict.

    Returns a dict with all fields needed for the options structure card
    in the company report page.
    """
    if options_structure is None:
        return {}

    def g(obj, key, default="—"):
        if obj is None:
            return default
        if hasattr(obj, key):
            return getattr(obj, key, default)
        if isinstance(obj, dict):
            return obj.get(key, default)
        return default

    # Primary contract
    pc = g(options_structure, "primary_contract", None)
    expiry = "—"
    strike = "—"
    delta = "—"
    option_type_contract = "—"
    if pc is not None:
        expiry = str(g(pc, "expiry_months", "—"))
        strike = str(g(pc, "strike", "—"))
        delta = str(g(pc, "delta_estimate", "—"))
        option_type_contract = g(pc, "option_type", "—")

    # Net debit/credit
    net_debit = g(options_structure, "strategy_net_debit", None)
    net_credit = g(options_structure, "strategy_net_credit", None)
    net_debit_str = f"{net_debit:.2f}" if net_debit is not None else "—"
    net_credit_str = f"{net_credit:.2f}" if net_credit is not None else "—"

    # Break-even, max profit/loss
    break_even = str(g(options_structure, "break_even_price", "—"))
    max_profit = g(options_structure, "max_profit_pct", None)
    max_loss = g(options_structure, "max_loss_pct", None)
    max_profit_str = f"{max_profit:.0%}" if max_profit is not None else "—"
    max_loss_str = f"{max_loss:.0%}" if max_loss is not None else "—"

    # Short contract
    sc = g(options_structure, "short_contract", None)
    short_expiry = "—"
    short_strike = "—"
    if sc is not None:
        short_expiry = str(g(sc, "expiry_months", "—"))
        short_strike = str(g(sc, "strike", "—"))

    # Covered note
    covered_note = "Yes" if g(options_structure, "covered_by_shares", False) else "—"

    return {
        "option_type": g(options_structure, "instrument_action", "—"),
        "expiry": expiry,
        "strike": strike,
        "option_type_contract": option_type_contract,
        "short_expiry": short_expiry,
        "short_strike": short_strike,
        "net_debit": net_debit_str,
        "net_credit": net_credit_str,
        "break_even": break_even,
        "max_profit": max_profit_str,
        "max_loss": max_loss_str,
        "delta": delta,
        "covered_note": covered_note,
    }


def _get_attr(obj, name: str, default=""):
    """Get attribute or dict key value safely."""
    if hasattr(obj, name):
        return getattr(obj, name, default)
    if isinstance(obj, dict):
        return obj.get(name, default)
    return default


def _build_poster_from_signal_report(
    signal: dict,
    report: dict,
    market_data: Optional[dict] = None,
    watchlist_entry: Optional[dict] = None,
    validation_result: Optional[dict] = None,
    position_decision: Optional[Any] = None,
    instrument_rec: Optional[Any] = None,
    options_structure: Optional[Any] = None,
    early_exit_plan: Optional[Any] = None,
) -> PosterData:
    """Build PosterData from canonical signal and report dicts.

    Optionally accepts real Hermes decision objects (PositionDecisionCard,
    InstrumentRecommendation, OptionsStructure, EarlyExitPlan) for accurate
    instrument type display.
    """

    # Resolve primary action: prefer real decision object, fall back to signal dict
    if position_decision is not None:
        primary_action = _get_attr(position_decision, "primary_action", "Buy Stock")
        conviction = _get_attr(position_decision, "conviction", "Medium")
        thesis_summary = _get_attr(position_decision, "thesis_summary", "")
        why_now_text = _get_attr(position_decision, "why_now", "")
        alternatives = _get_attr(position_decision, "alternatives", [])
    else:
        # Legacy dict-based path
        primary_action = _get_attr(signal, "primary_action", None) or _get_attr(signal, "rating", "Hold")
        thesis_summary = ""
        why_now_text = _get_attr(report, "why_now", "") or _get_attr(report, "why_it_matters", "")
        alternatives = []
        # Derive conviction from signal confidence (not from dict field)
        confidence = _get_attr(signal, "confidence", 0.5)
        if confidence >= 0.75:
            conviction = "High"
        elif confidence >= 0.5:
            conviction = "Medium"
        else:
            conviction = "Low"

    # Map conviction to display strings
    if conviction in ("High", "高信心"):
        conviction_zh, conviction_en = "高信心", "HIGH CONVICTION"
    elif conviction in ("Medium", "中信心"):
        conviction_zh, conviction_en = "中信心", "MEDIUM CONVICTION"
    else:
        conviction_zh, conviction_en = "低信心", "LOW CONVICTION"

    # Map primary action to action display (BUY/SELL/HOLD → instrument-specific)
    if primary_action in VALID_BULLISH_ACTIONS:
        action_zh = ACTION_ZH_NAMES.get(primary_action, primary_action)
        action_en = ACTION_EN_NAMES.get(primary_action, primary_action)
        use_real_instruments = True
    elif not primary_action or primary_action in ("Hold", "hold", "—"):
        # Empty or non-specific action → show placeholder
        action_zh = "—"
        action_en = "—"
        use_real_instruments = False
    else:
        action_zh, action_en, _ = _map_rating(primary_action)
        use_real_instruments = False

    # Resolve ranked alternatives from InstrumentRecommendation
    if instrument_rec is not None:
        ranked_alts = _get_attr(instrument_rec, "ranked_alternatives", [])
        instrument_reason = _get_attr(instrument_rec, "reason", "")
    else:
        ranked_alts = []
        instrument_reason = ""

    # Build instrument boxes - use real instrument types when available
    if use_real_instruments:
        instruments = _build_instruments_list(primary_action, ranked_alts if ranked_alts else None)
    else:
        # Fallback default structure for non-instrument ratings (SELL, HOLD, etc.)
        instruments = [
            {"name_zh": "股票 / Stock", "name_en": "Stock", "reason": "直接持有", "role": "primary"},
            {"name_zh": "买入看涨 / Call", "name_en": "Call", "reason": "杠杆增强", "role": "conservative"},
            {"name_zh": "价差 / Spread", "name_en": "Spread", "reason": "成本优化", "role": "alternative"},
            {"name_zh": "看跌 / Put", "name_en": "Put", "reason": "—", "role": "rejected"},
            {"name_zh": "备兑 / Covered", "name_en": "Covered", "reason": "—", "role": "rejected"},
        ]

    # Build why_now from thesis
    if not why_now_text:
        why_now_text = _get_attr(report, "why_now", "") or _get_attr(report, "why_it_matters", "")
    why_now = _extract_thesis_points(why_now_text, max_points=3)

    # Build thesis_catalysts from bull_case or thesis_summary
    bull_case = _get_attr(report, "bull_case", "") or _get_attr(report, "research_summary", "")
    if thesis_summary and not bull_case:
        bull_case = thesis_summary
    thesis_catalysts = _extract_thesis_points(bull_case, max_points=4)

    # Build risks from risk_watch
    risk_watch = _get_attr(report, "risk_watch", [])
    if isinstance(risk_watch, str):
        try:
            risk_watch = json.loads(risk_watch)
        except (json.JSONDecodeError, TypeError):
            risk_watch = [risk_watch] if risk_watch else []
    top_risks = [{"zh": r, "en": ""} for r in risk_watch[:3]]

    # Options structure: use comprehensive _build_options_detail when available,
    # fall back to legacy trade_plan fields for backward compatibility
    if options_structure is not None:
        options = _build_options_detail(options_structure, early_exit_plan)
    else:
        trade_plan = _get_attr(report, "trade_plan", {}) or {}
        if isinstance(trade_plan, str):
            try:
                trade_plan = json.loads(trade_plan)
            except (json.JSONDecodeError, TypeError):
                trade_plan = {}
        options = {
            "option_type": "—",
            "expiry": trade_plan.get("expiry", "—"),
            "strike": trade_plan.get("strike", "—"),
            "break_even": trade_plan.get("break_even", "—"),
            "delta": trade_plan.get("delta", "—"),
            "net_debit": "—",
            "net_credit": "—",
            "max_profit": "—",
            "max_loss": "—",
            "covered_note": "—",
        }

    # KPI from market_data or signal snapshot
    confidence = _get_attr(signal, "confidence", 0.5)
    kpi = {
        "price": _get_attr(market_data, "price", None) if market_data else _get_attr(signal, "entry_price", "—"),
        "pe": _get_attr(market_data, "pe_ratio", "—") if market_data else "—",
        "eps_growth": _get_attr(market_data, "eps_growth", "—") if market_data else "—",
        "analyst_rating": _get_attr(signal, "rating", "—"),
    }

    # Technical from market_data
    technical = {
        "support": _get_attr(market_data, "support", "—") if market_data else "—",
        "resistance": _get_attr(market_data, "resistance", "—") if market_data else "—",
        "trend": _get_attr(market_data, "trend", "—") if market_data else "—",
    }

    # Watchlist state
    watchlist_state = {"status_zh": "—", "status_en": "—", "status_class": "passive", "action_bias": "—"}
    if watchlist_entry:
        status_zh, status_en, status_class = _map_watchlist_status(_get_attr(watchlist_entry, "status", ""))
        watchlist_state = {
            "status_zh": status_zh,
            "status_en": status_en,
            "status_class": status_class,
            "action_bias": _get_attr(watchlist_entry, "current_action_bias", "—"),
        }

    # Validation
    validation = {"regime": "—", "confidence": "—", "confidence_class": ""}
    if validation_result:
        val_conf = _get_attr(validation_result, "validation_confidence", 0)
        validation = {
            "regime": _get_attr(validation_result, "regime", "—"),
            "confidence": f"{val_conf:.0%}",
            "confidence_class": _map_confidence_class(val_conf),
        }

    # Entry price from trade plan or signal
    entry_price = _get_attr(signal, "entry_price", "—")
    stop_loss = _get_attr(signal, "stop_loss", "—")
    take_profit = _get_attr(signal, "take_profit", "—")
    holding_horizon = _get_attr(signal, "holding_horizon", "—")
    trade_plan = _get_attr(report, "trade_plan", {}) or {}
    if isinstance(trade_plan, dict):
        entry_price = trade_plan.get("entry_price", entry_price)
        stop_loss = trade_plan.get("stop_loss", stop_loss)
        take_profit = trade_plan.get("take_profit", take_profit)
        holding_horizon = trade_plan.get("holding_period", holding_horizon)

    # Suggested size
    suggested_size = _get_attr(signal, "suggested_size", "—")
    if suggested_size == "—" and _get_attr(signal, "priority_score"):
        ps = _get_attr(signal, "priority_score", 0)
        if ps >= 8:
            suggested_size = "15% Portfolio"
        elif ps >= 6:
            suggested_size = "10% Portfolio"
        else:
            suggested_size = "5% Portfolio"

    # Early exit zones (Phase 15)
    early_exit_zones = _build_early_exit_zones(early_exit_plan)

    return PosterData(
        ticker=_get_attr(signal, "ticker", "—"),
        company_name=_get_attr(report, "company_name", None) or _get_attr(signal, "company_name", "—"),
        action_zh=action_zh,
        action_en=action_en,
        conviction_zh=conviction_zh,
        conviction_en=conviction_en,
        suggested_size=str(suggested_size),
        target_window=str(holding_horizon) if holding_horizon != "—" else "—",
        target_price=f"{entry_price} → {take_profit}" if entry_price != "—" and take_profit != "—" else take_profit,
        why_now=why_now,
        top_risks=top_risks,
        kpi=kpi,
        thesis_catalysts=thesis_catalysts,
        technical=technical,
        instruments=instruments,
        options=options if any(v != "—" for v in options.values()) else {},
        early_exit_zones=early_exit_zones,
        watchlist_state=watchlist_state,
        validation=validation,
        title=f"{_get_attr(signal, 'ticker', '—')} 投资决策看板",
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


# =============================================================================
# Template Rendering
# =============================================================================

def _render_template(template_name: str, data: dict) -> str:
    """Render a Jinja2-style template with the given data dict.

    Handles basic {{variable}} and {% for %} {% endfor %} constructs.
    For full Jinja2, install jinja2 and use Environment.from_string.
    """
    try:
        from jinja2 import Environment, FileSystemLoader, select_autoescape
        template_dir = Path(__file__).parent
        env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(["html", "xml"]),
        )
        template = env.get_template(template_name)
        return template.render(**data)
    except ImportError:
        # Fallback: simple string replacement
        return _render_template_fallback(template_name, data)


def _render_template_fallback(template_name: str, data: dict) -> str:
    """Fallback template renderer using simple string substitution."""
    template_dir = Path(__file__).parent
    template_path = template_dir / template_name

    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")

    content = template_path.read_text(encoding="utf-8")

    # Simple variable replacement: {{var}} -> data.get(var, "")
    def replace_var(m):
        key = m.group(1).strip()
        val = data.get(key, "")
        if val is None:
            val = ""
        return str(val)

    # Handle conditional blocks {% if var %} ... {% endif %}
    def replace_if(m):
        block_content = m.group(1)
        var_name = block_content.split("%")[1].strip().split(" ")[-1]
        if data.get(var_name):
            return block_content
        return ""

    # Handle simple for loops {% for item in list %} ... {% endfor %}
    def replace_for(m):
        loop_content = m.group(2)
        # Very simplistic: just return the content once
        return loop_content

    # Process {% if %} blocks
    content = re.sub(r"\{%\s*if\s+(\w+)\s*%\}(.*?)\{%\s*endif\s*%\}",
                     lambda m: m.group(2) if data.get(m.group(1).split(".")[0]) else "", content, flags=re.DOTALL)

    # Process {% for %} blocks (simplified - single level only)
    for_loop_pattern = r"\{%\s*for\s+(\w+)\s+in\s+(\w+)\s*%\}(.*?)\{%\s*endfor\s*%\}"
    def process_for(match):
        item_name = match.group(1)
        list_name = match.group(2)
        loop_body = match.group(3)
        items = data.get(list_name, [])
        if not isinstance(items, list):
            items = []
        result = []
        for i, item in enumerate(items):
            if isinstance(item, dict):
                loop_result = loop_body
                # Replace {{loop.index}} with actual index
                loop_result = re.sub(r'\{\{\s*loop\.index\s*\}\}', str(i + 1), loop_result)
                # Replace simple {{key}} patterns
                for k, v in item.items():
                    loop_result = loop_result.replace('{{' + k + '}}', str(v))
                    loop_result = loop_result.replace('{{ ' + k + ' }}', str(v))
                # Replace {{item.attr}} and {{item.nested.attr}} style access
                attr_pattern = r'\{\{\s*' + re.escape(item_name) + r'\.([\w\.]+)\s*\}\}'
                def replace_loop_attr(pat):
                    def repl(m):
                        # pat captured group is the attribute name after the dot (e.g., 'rank' from 'item.rank')
                        attr_name = m.group(1).strip()
                        val = item.get(attr_name, '')
                        return str(val) if val is not None else ''
                    return repl
                loop_result = re.sub(attr_pattern, replace_loop_attr(re.compile(attr_pattern)), loop_result)
                result.append(loop_result)
            else:
                result.append(str(item))
        return "".join(result)

    content = re.sub(for_loop_pattern, process_for, content, flags=re.DOTALL)

    # Handle dotted attribute access {{var.attr}} and simple {{var}} in one pass
    def replace_attr_or_var(m):
        path = m.group(1).strip()
        parts = path.split(".")
        val = data
        for p in parts:
            if isinstance(val, dict):
                val = val.get(p, "")
            elif isinstance(val, list):
                try:
                    val = val[int(p)]
                except (ValueError, IndexError):
                    val = ""
            else:
                val = ""
        return str(val) if val is not None else ""

    # First: process dotted paths (must run BEFORE simple vars to avoid {{var}} in
    # {{var.attr}} being caught by the simple-var regex)
    content = re.sub(r"\{\{\s*([\w]+\.[\w\.]+)\s*\}\}", replace_attr_or_var, content)
    # Second: process simple vars (now safe since dotted paths are already consumed)
    content = re.sub(r"\{\{\s*(\w+)\s*\}\}", replace_attr_or_var, content)

    # Clean up remaining {% %} tags
    content = re.sub(r"\{%\s*.*?\s*%\}", "", content)

    return content


# =============================================================================
# Public Rendering API
# =============================================================================

def render_boss_poster(
    signal: dict,
    report: dict,
    market_data: Optional[dict] = None,
    watchlist_entry: Optional[dict] = None,
    validation_result: Optional[dict] = None,
    position_decision: Optional[Any] = None,
    instrument_rec: Optional[Any] = None,
    options_structure: Optional[Any] = None,
    early_exit_plan: Optional[Any] = None,
) -> str:
    """Render a single-page Boss Poster as HTML string.

    Args:
        signal: Canonical signal dict with ticker, rating, confidence, entry_price, etc.
        report: Canonical report dict with bottom_line, why_now, bull_case, risk_watch, trade_plan, etc.
        market_data: Optional dict with current price, P/E, EPS growth, analyst rating.
        watchlist_entry: Optional watchlist entry dict.
        validation_result: Optional validation result dict.
        position_decision: Optional PositionDecisionCard dataclass with primary_action, conviction, etc.
        instrument_rec: Optional InstrumentRecommendation dataclass with ranked_alternatives.
        options_structure: Optional OptionsStructure dataclass with primary_contract details.
        early_exit_plan: Optional EarlyExitPlan dataclass with exit zones.

    Returns:
        HTML string ready for PDF rendering or display.
    """
    _ZH, _EN = _load_strings()

    poster = _build_poster_from_signal_report(
        signal=signal,
        report=report,
        market_data=market_data,
        watchlist_entry=watchlist_entry,
        validation_result=validation_result,
        position_decision=position_decision,
        instrument_rec=instrument_rec,
        options_structure=options_structure,
        early_exit_plan=early_exit_plan,
    )

    # Convert PosterData to dict for template
    poster_strings = dict(_ZH)
    poster_strings.update({f"{k}_en": v for k, v in _EN.items()})

    data = {
        # Strings
        "strings": poster_strings,
        # Top zone
        "ticker": poster.ticker,
        "company_name": poster.company_name,
        "action_zh": poster.action_zh,
        "action_en": poster.action_en,
        "conviction_zh": poster.conviction_zh,
        "conviction_en": poster.conviction_en,
        "suggested_size": poster.suggested_size,
        "target_window": poster.target_window,
        "target_price": poster.target_price,
        "why_now": poster.why_now,
        "top_risks": poster.top_risks,
        # Middle zone
        "kpi": poster.kpi,
        "thesis_catalysts": poster.thesis_catalysts,
        "technical": poster.technical,
        "instruments": poster.instruments,
        "options": poster.options,
        "early_exit_zones": poster.early_exit_zones,
        # Bottom zone
        "watchlist_state": poster.watchlist_state,
        "validation": poster.validation,
        # Metadata
        "title": poster.title,
        "generated_at": poster.generated_at,
        # String helpers for template
        "label_action_en": _EN.get("label_action", "Action"),
        "label_suggested_size_en": _EN.get("label_suggested_size", "Suggested Size"),
        "label_target_window_en": _EN.get("label_target_window", "Target Window"),
        "label_target_price_en": _EN.get("label_target_price", "Target Price"),
        "label_why_now_en": _EN.get("label_why_now", "Why Now"),
        "label_current_price_en": _EN.get("label_current_price", "Price"),
        "label_pe_ratio_en": _EN.get("label_pe_ratio", "P/E"),
        "label_eps_growth_en": _EN.get("label_eps_growth", "EPS Growth"),
        "label_analyst_rating_en": _EN.get("label_analyst_rating", "Analyst"),
        "label_thesis_catalysts_en": _EN.get("label_thesis_catalysts", "Thesis & Catalysts"),
        "label_technical_analysis_en": _EN.get("label_technical_analysis", "Technical Analysis"),
        "label_support_en": _EN.get("label_support", "Support"),
        "label_resistance_en": _EN.get("label_resistance", "Resistance"),
        "label_trend_en": _EN.get("label_trend", "Trend"),
        "label_expiry_en": _EN.get("label_expiry", "Expiry"),
        "label_strike_en": _EN.get("label_strike", "Strike"),
        "label_break_even_en": _EN.get("label_break_even", "Break-Even"),
        "label_delta_en": _EN.get("label_delta", "Delta"),
        "label_early_exit_en": _EN.get("label_early_exit", "Early Exit"),
        "label_watchlist_state_en": _EN.get("label_watchlist_state", "Watchlist"),
        "label_validation_summary_en": _EN.get("label_validation_summary", "Validation"),
        "label_regime_en": _EN.get("label_regime", "Regime"),
        "label_confidence_en": _EN.get("label_confidence", "Confidence"),
        "label_action_bias_en": _EN.get("label_action_bias", "Bias"),
        "label_hermes_desk_en": _EN.get("label_hermes_desk", "Hermes Desk"),
        "label_decision_board_en": _EN.get("label_decision_board", "Decision Board"),
        "label_generated_at_en": _EN.get("label_generated_at", "Generated"),
        "label_primary": _ZH.get("label_primary", "首选"),
        "label_conservative": _ZH.get("label_conservative", "保守方案"),
        "label_alternative": _ZH.get("label_alternative", "备选方案"),
        # Early exit zone labels
        "label_first_trim_zone": _ZH.get("label_first_trim_zone", "首轮减仓区"),
        "label_main_profit_zone": _ZH.get("label_main_profit_zone", "主要利润区"),
        "label_full_exit_zone": _ZH.get("label_full_exit_zone", "完全退出区"),
        "label_trigger_condition": _ZH.get("label_trigger_condition", "触发条件"),
        "label_target_return": _ZH.get("label_target_return", "目标收益"),
        "label_first_trim_zone_en": _EN.get("label_first_trim_zone", "First Trim Zone"),
        "label_main_profit_zone_en": _EN.get("label_main_profit_zone", "Main Profit Zone"),
        "label_full_exit_zone_en": _EN.get("label_full_exit_zone", "Full Exit Zone"),
        "label_trigger_condition_en": _EN.get("label_trigger_condition", "Trigger Condition"),
        "label_target_return_en": _EN.get("label_target_return", "Target Return"),
        "empty_kpi": _ZH.get("empty_kpi", "—"),
        "empty_thesis": _ZH.get("empty_thesis", "暂无"),
        "empty_technical": _ZH.get("empty_technical", "暂无"),
        "empty_risks": _ZH.get("empty_risks", "暂无"),
        "empty_watchlist": _ZH.get("empty_watchlist", "暂无"),
        "empty_validation": _ZH.get("empty_validation", "暂无"),
        "empty_instrument": _ZH.get("empty_instrument", "—"),
    }

    return _render_template("boss_poster_base.html", data)


def render_batch_report(
    batch_items: list[dict],
    company_reports: list[dict],
    watchlist_entries: Optional[list[dict]] = None,
    validation_results: Optional[list[dict]] = None,
    executive_summary: str = "",
) -> str:
    """Render a multi-page batch report as HTML string.

    Args:
        batch_items: List of research batch item dicts with ticker, rating, confidence, action, etc.
        company_reports: List of company report dicts with bottom_line, bull_case, risk_watch, etc.
        watchlist_entries: Optional list of watchlist entry dicts.
        validation_results: Optional list of validation result dicts.
        executive_summary: Optional executive summary text.

    Returns:
        HTML string ready for PDF rendering or display.
    """
    _ZH, _EN = _load_strings()

    # Map batch items to table rows
    report_items = []
    for i, item in enumerate(batch_items):
        rating_zh, rating_en, rating_class = _map_rating(item.get("overall_rating", ""))
        report_items.append({
            "rank": item.get("display_rank", i + 1),
            "ticker": item.get("symbol", "—"),
            "company_name": item.get("company_name", "—"),
            "rating_zh": rating_zh,
            "rating_en": rating_en,
            "rating_class": rating_class,
            "confidence": f"{item.get('confidence', 0):.0%}",
            "action_bias": item.get("action", "—"),
            "target_price": f"{item.get('entry_price', '—')} → {item.get('take_profit', '—')}",
        })

    # Map company reports
    company_report_data = []
    for report in company_reports:
        # Extract decision objects if present
        position_decision = report.get("position_decision")
        instrument_rec = report.get("instrument_rec")
        options_structure = report.get("options_structure")
        early_exit_plan = report.get("early_exit")

        # Resolve primary action and conviction from decision objects
        if position_decision is not None:
            primary_action = _get_attr(position_decision, "primary_action", "Buy Stock")
            conviction_val = _get_attr(position_decision, "conviction", "Medium")
        else:
            primary_action = report.get("rating", "Hold") or "Hold"
            conf = report.get("confidence", 0.5)
            conviction_val = "High" if conf >= 0.75 else ("Medium" if conf >= 0.5 else "Low")

        # Map conviction to display strings
        conviction_zh = {"High": "高信心", "Medium": "中信心", "Low": "低信心"}.get(conviction_val, "中信心")
        conviction_en = {"High": "HIGH CONVICTION", "Medium": "MEDIUM CONVICTION", "Low": "LOW CONVICTION"}.get(conviction_val, "MEDIUM CONVICTION")

        # Map primary action to instrument display
        if primary_action in VALID_BULLISH_ACTIONS:
            action_zh = ACTION_ZH_NAMES.get(primary_action, primary_action)
            action_en = ACTION_EN_NAMES.get(primary_action, primary_action)
        else:
            action_zh, action_en, _ = _map_rating(primary_action)

        # Build instrument detail
        instr_primary, instr_conservative, instr_alternative = _build_instrument_detail(instrument_rec, primary_action)

        # Build options detail
        opts_detail = _build_options_detail(options_structure, early_exit_plan)

        # Build early exit zones
        ee_zones = _build_early_exit_zones(early_exit_plan)

        # Supporting data from legacy fields
        trade_plan = report.get("trade_plan") or {}
        if isinstance(trade_plan, str):
            try:
                trade_plan = json.loads(trade_plan)
            except (json.JSONDecodeError, TypeError):
                trade_plan = {}
        supporting_entry = str(trade_plan.get("entry_price", report.get("entry_price", "—")))
        supporting_stop = str(trade_plan.get("stop_loss", report.get("stop_loss", "—")))
        supporting_target = str(trade_plan.get("take_profit", report.get("take_profit", "—")))
        supporting_horizon = str(trade_plan.get("holding_period", report.get("holding_horizon", "—")))

        # Risk watch
        risk_watch = report.get("risk_watch", [])
        if isinstance(risk_watch, str):
            try:
                risk_watch = json.loads(risk_watch)
            except (json.JSONDecodeError, TypeError):
                risk_watch = [risk_watch] if risk_watch else []

        # Legacy rating fields
        rating_zh, rating_en, rating_class = _map_rating(report.get("rating", ""))

        company_report_data.append(CompanyReportData(
            # 1. Decision card summary
            ticker=report.get("ticker", "—"),
            company_name=report.get("company_name", report.get("title", "—")),
            action_zh=action_zh,
            action_en=action_en,
            conviction_zh=conviction_zh,
            conviction_en=conviction_en,
            bottom_line=report.get("bottom_line", ""),
            # 2. Instrument detail
            instrument_primary=instr_primary,
            instrument_conservative=instr_conservative,
            instrument_alternative=instr_alternative,
            # 3. Options detail + early exit
            options_detail=opts_detail,
            early_exit_zones=ee_zones,
            # 4. Supporting data (legacy — explicitly supporting-only)
            supporting_entry=supporting_entry,
            supporting_stop=supporting_stop,
            supporting_target=supporting_target,
            supporting_horizon=supporting_horizon,
            # 5. Thesis and risk
            why_now=report.get("why_now", ""),
            bull_case=report.get("bull_case", ""),
            risk_watch=risk_watch,
            # Legacy fields
            rating_zh=rating_zh,
            rating_en=rating_en,
            rating_class=rating_class,
            confidence=f"{report.get('confidence', 0):.0%}",
            trade_plan=trade_plan,
            research_summary=report.get("research_summary", ""),
        ))

    # Map watchlist entries
    mapped_watchlist = []
    for entry in (watchlist_entries or []):
        status_zh, status_en, status_class = _map_watchlist_status(entry.get("status", ""))
        thesis_zh, _ = _map_thesis_state(entry.get("thesis_state", ""))
        alert_zh, _ = _map_alert_level(entry.get("alert_level", ""))
        mapped_watchlist.append({
            "ticker": entry.get("ticker", "—"),
            "current_action_bias": entry.get("current_action_bias", "—"),
            "status_zh": status_zh,
            "status_en": status_en,
            "status_class": status_class,
            "thesis_state_zh": thesis_zh,
            "alert_level_zh": alert_zh,
        })

    # Map validation results
    mapped_validation = []
    for result in (validation_results or []):
        val_conf = result.get("validation_confidence", 0)
        mapped_validation.append({
            "ticker": result.get("ticker", "—"),
            "regime": result.get("regime", "—"),
            "historical_support": result.get("historical_support", "—"),
            "environment_fit": result.get("environment_fit", "—"),
            "main_failure_mode": result.get("main_failure_mode", "—"),
            "validation_confidence": val_conf,
            "confidence_pct": f"{val_conf:.0%}",
        })

    data = {
        # Flat string variables for batch report template
        "label_batch_overview": _ZH.get("label_batch_overview", "批次总览"),
        "label_batch_overview_en": _EN.get("label_batch_overview", "Batch Overview"),
        "label_executive_summary": _ZH.get("label_executive_summary", "执行摘要"),
        "label_executive_summary_en": _EN.get("label_executive_summary", "Executive Summary"),
        "label_research_date": _ZH.get("label_research_date", "研究日期"),
        "label_research_date_en": _EN.get("label_research_date", "Date"),
        "label_reports": _ZH.get("label_reports", "报告"),
        "label_reports_en": _EN.get("label_reports", "Reports"),
        "label_priority_rank": _ZH.get("label_priority_rank", "优先级"),
        "label_priority_rank_en": _EN.get("label_priority_rank", "Rank"),
        "label_ticker": _ZH.get("label_ticker", "代码"),
        "label_ticker_en": _EN.get("label_ticker", "Ticker"),
        "label_company": _ZH.get("label_company", "公司"),
        "label_company_en": _EN.get("label_company", "Company"),
        "label_rating": _ZH.get("label_rating", "评级"),
        "label_rating_en": _EN.get("label_rating", "Rating"),
        "label_confidence_pct": _ZH.get("label_confidence_pct", "信心%"),
        "label_confidence_pct_en": _EN.get("label_confidence_pct", "Conf %"),
        "label_action_bias": _ZH.get("label_action_bias", "操作倾向"),
        "label_action_bias_en": _EN.get("label_action_bias", "Bias"),
        "label_target_price": _ZH.get("label_target_price", "目标价"),
        "label_target_price_en": _EN.get("label_target_price", "Target"),
        "label_action": _ZH.get("label_action", "操作"),
        "label_action_en": _EN.get("label_action", "Action"),
        "label_entry_price": _ZH.get("label_entry_price", "入场价"),
        "label_entry_price_en": _EN.get("label_entry_price", "Entry"),
        "label_stop_loss": _ZH.get("label_stop_loss", "止损价"),
        "label_stop_loss_en": _EN.get("label_stop_loss", "Stop"),
        "label_holding_period": _ZH.get("label_holding_period", "持仓周期"),
        "label_holding_period_en": _EN.get("label_holding_period", "Horizon"),
        "label_why_now": _ZH.get("label_why_now", "为何此时"),
        "label_why_now_en": _EN.get("label_why_now", "Why Now"),
        "label_bottom_line": _ZH.get("label_bottom_line", "核心结论"),
        "label_bottom_line_en": _EN.get("label_bottom_line", "Bottom Line"),
        "label_bull_case": _ZH.get("label_bull_case", "看多逻辑"),
        "label_bull_case_en": _EN.get("label_bull_case", "Bull Case"),
        "label_risk_watch": _ZH.get("label_risk_watch", "风险观察"),
        "label_risk_watch_en": _EN.get("label_risk_watch", "Risk Watch"),
        "label_research_summary": _ZH.get("label_research_summary", "研究摘要"),
        "label_research_summary_en": _EN.get("label_research_summary", "Research Summary"),
        "label_confidence": _ZH.get("label_confidence", "信心指数"),
        "label_confidence_en": _EN.get("label_confidence", "Confidence"),
        "label_watchlist_state": _ZH.get("label_watchlist_state", "监控状态"),
        "label_watchlist_state_en": _EN.get("label_watchlist_state", "Watchlist"),
        "label_validation_summary": _ZH.get("label_validation_summary", "验证摘要"),
        "label_validation_summary_en": _EN.get("label_validation_summary", "Validation"),
        "label_regime": _ZH.get("label_regime", "市场状态"),
        "label_regime_en": _EN.get("label_regime", "Regime"),
        "label_historical_support": _ZH.get("label_historical_support", "历史支持"),
        "label_historical_support_en": _EN.get("label_historical_support", "Historical"),
        "label_environment_fit": _ZH.get("label_environment_fit", "环境匹配"),
        "label_environment_fit_en": _EN.get("label_environment_fit", "Env Fit"),
        "label_failure_mode": _ZH.get("label_failure_mode", "主要失效模式"),
        "label_failure_mode_en": _EN.get("label_failure_mode", "Failure Mode"),
        "empty_risks": _ZH.get("empty_risks", "暂无风险提示"),
        "no_data": _ZH.get("no_data", "暂无数据"),
        "no_data_en": _EN.get("no_data", "No data"),
        # Company report section headers
        "label_decision_card_summary": _ZH.get("label_decision_card_summary", "决策卡片摘要"),
        "label_decision_card_summary_en": _EN.get("label_decision_card_summary", "Decision Card Summary"),
        "label_instrument_detail": _ZH.get("label_instrument_detail", "工具选择详情"),
        "label_instrument_detail_en": _EN.get("label_instrument_detail", "Instrument Detail"),
        "label_options_structure_detail": _ZH.get("label_options_structure_detail", "期权结构详情"),
        "label_options_structure_detail_en": _EN.get("label_options_structure_detail", "Options Structure Detail"),
        "label_supporting_data_grid": _ZH.get("label_supporting_data_grid", "支撑数据网格"),
        "label_supporting_data_grid_en": _EN.get("label_supporting_data_grid", "Supporting Data Grid"),
        "label_supporting_only": _ZH.get("label_supporting_only", "仅供参考，不构成页面主结构"),
        "label_supporting_only_en": _EN.get("label_supporting_only", "For reference only"),
        "label_primary": _ZH.get("label_primary", "首选"),
        "label_primary_en": _EN.get("label_primary", "Primary"),
        "label_conservative": _ZH.get("label_conservative", "保守方案"),
        "label_conservative_en": _EN.get("label_conservative", "Conservative"),
        "label_alternative": _ZH.get("label_alternative", "备选方案"),
        "label_alternative_en": _EN.get("label_alternative", "Alternative"),
        "label_rejected": _ZH.get("label_rejected", "排除原因"),
        "label_rejected_en": _EN.get("label_rejected", "Rejected Because"),
        "label_first_trim_zone": _ZH.get("label_first_trim_zone", "首轮减仓区"),
        "label_first_trim_zone_en": _EN.get("label_first_trim_zone", "First Trim Zone"),
        "label_main_profit_zone": _ZH.get("label_main_profit_zone", "主要利润区"),
        "label_main_profit_zone_en": _EN.get("label_main_profit_zone", "Main Profit Zone"),
        "label_full_exit_zone": _ZH.get("label_full_exit_zone", "完全退出区"),
        "label_full_exit_zone_en": _EN.get("label_full_exit_zone", "Full Exit Zone"),
        "label_trigger_condition": _ZH.get("label_trigger_condition", "触发条件"),
        "label_trigger_condition_en": _EN.get("label_trigger_condition", "Trigger"),
        "label_target_return": _ZH.get("label_target_return", "目标收益"),
        "label_target_return_en": _EN.get("label_target_return", "Target"),
        "label_option_type": _ZH.get("label_option_type", "期权类型"),
        "label_option_type_en": _EN.get("label_option_type", "Option Type"),
        "label_expiry": _ZH.get("label_expiry", "到期日"),
        "label_expiry_en": _EN.get("label_expiry", "Expiry"),
        "label_strike": _ZH.get("label_strike", "行权价"),
        "label_strike_en": _EN.get("label_strike", "Strike"),
        "label_break_even": _ZH.get("label_break_even", "盈亏平衡"),
        "label_break_even_en": _EN.get("label_break_even", "Break-Even"),
        "label_delta": _ZH.get("label_delta", "Delta"),
        "label_delta_en": _EN.get("label_delta", "Delta"),
        "label_net_debit": _ZH.get("label_net_debit", "净Debit"),
        "label_net_debit_en": _EN.get("label_net_debit", "Net Debit"),
        "label_net_credit": _ZH.get("label_net_credit", "净Credit"),
        "label_net_credit_en": _EN.get("label_net_credit", "Net Credit"),
        "label_max_profit": _ZH.get("label_max_profit", "最大盈利"),
        "label_max_profit_en": _EN.get("label_max_profit", "Max Profit"),
        "label_max_loss": _ZH.get("label_max_loss", "最大亏损"),
        "label_max_loss_en": _EN.get("label_max_loss", "Max Loss"),
        "label_early_exit": _ZH.get("label_early_exit", "提前退出"),
        "label_early_exit_en": _EN.get("label_early_exit", "Early Exit"),
        # Batch overview
        "title": "Hermes 研究批次报告",
        "batch_date": datetime.now().strftime("%Y-%m-%d"),
        "batch_count": len(batch_items),
        "executive_summary": executive_summary,
        "batch_items": report_items,
        # Company reports — decision-object-first field mapping
        "company_reports": [
            {
                # Section 1: Decision card summary
                "ticker": cr.ticker,
                "company_name": cr.company_name,
                "action_zh": cr.action_zh,
                "action_en": cr.action_en,
                "conviction_zh": cr.conviction_zh,
                "conviction_en": cr.conviction_en,
                "confidence": cr.confidence,
                "bottom_line": cr.bottom_line,
                # Section 2: Instrument detail
                "instrument_primary": cr.instrument_primary,
                "instrument_conservative": cr.instrument_conservative,
                "instrument_alternative": cr.instrument_alternative,
                # Section 3: Options detail + early exit
                "options_detail": cr.options_detail,
                "early_exit_zones": cr.early_exit_zones,
                # Section 4: Supporting data (legacy — explicitly supporting-only)
                "supporting_entry": cr.supporting_entry,
                "supporting_stop": cr.supporting_stop,
                "supporting_target": cr.supporting_target,
                "supporting_horizon": cr.supporting_horizon,
                # Section 5-6: Thesis and risk
                "why_now": cr.why_now,
                "bull_case": cr.bull_case,
                "risk_watch": cr.risk_watch,
                # Legacy fields (still included for backward compat)
                "rating_zh": cr.rating_zh,
                "rating_en": cr.rating_en,
                "rating_class": cr.rating_class,
                "trade_plan": cr.trade_plan,
                "research_summary": cr.research_summary,
            }
            for cr in company_report_data
        ],
        # Watchlist & Validation
        "watchlist_entries": mapped_watchlist,
        "validation_results": mapped_validation,
    }

    return _render_template("boss_report_base.html", data)
