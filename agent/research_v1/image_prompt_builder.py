# -*- coding: utf-8 -*-
"""
Phase 19: Image Prompt Pack Builder.

Translates OrchestratorReportPack into page-specific prompts for the image model.

Per spec §12:
    - model: defaults to "gpt-image-2"
    - page_count: 1–3, derived from report complexity
    - global_style_rules: premium executive finance, institutional tone
    - page_prompts: one PagePrompt per page
    - must_show_labels: fixed Chinese label strings
    - forbidden_phrasing: phrases the image model must not produce
    - visual_priority_order: hierarchy of what to emphasize

Per spec §13 page responsibilities:
    - Page 1 (boss poster): primary action, conviction, ticker, size, target window, why now, top risks
    - Page 2 (formal report): thesis summary, catalysts, valuation, technical, must-show numbers
    - Page 3 (optional detail): options structure, early exit, validation/monitoring

Failure rules (spec §16):
    - image generation failure returns a generation error, NOT a research failure
    - individual page retry must be possible
    - page 2 or page 3 failure does NOT invalidate page 1
"""

from __future__ import annotations

from dataclasses import dataclass

from agent.research_v1.image_report_contracts import (
    OrchestratorReportPack,
    ImagePromptPack,
    PagePrompt,
    build_default_style_rules,
    approved_action_labels,
)


# ---------------------------------------------------------------------------
# Chinese label constants (spec §11, §10)
# ---------------------------------------------------------------------------

ZH_LABELS = {
    # Report identity
    "ticker": "股票代码",
    "company_name": "公司名称",
    "action": "操作建议",
    "conviction": "确信程度",
    "size": "建议仓位",
    "target_window": "目标周期",
    "entry": "入场参考",
    "target": "目标价位",
    "stop": "止损价位",
    # Boss narrative
    "boss_summary": "决策摘要",
    "why_now": "为何现在",
    "top_risks": "主要风险",
    "one_line_call": "一句话结论",
    # Research core
    "thesis_summary": "投资逻辑",
    "bull_case": "看涨理由",
    "bear_case": "看跌理由",
    "catalysts": "催化剂",
    "technical_summary": "技术面",
    "valuation_summary": "估值观点",
    "must_show_numbers": "关键数字",
    # Instrument plan
    "primary_instrument": "主要工具",
    "options_structure": "期权结构",
    "early_exit": "提前退出",
    "key_numbers": "关键数字",
    # Monitoring
    "watchlist_state": "观察状态",
    "alert_level": "警报级别",
    "validation_summary": "验证摘要",
    "regime": "市场环境",
    "historical_support": "历史支撑",
    "environment_fit": "环境匹配",
    "main_failure_mode": "主要失效模式",
    # Page labels
    "page_1_boss_poster": "投资决策海报",
    "page_2_formal_report": "正式研究报告",
    "page_3_detail": "详细说明页",
}

# Chinese conviction labels
ZH_CONVICTION = {
    "High": "高确信",
    "Medium": "中确信",
    "Low": "低确信",
}

# Alert level labels
ZH_ALERT = {
    "Critical": "严重警报",
    "High": "高警报",
    "Medium": "中警报",
    "Low": "低警报",
    "None": "无警报",
}

# Regime labels
ZH_REGIME = {
    "trend_up": "趋势向上",
    "range_bound": "区间震荡",
    "high_volatility": "高波动",
    "risk_off": "风险规避",
    "unknown": "环境不明",
}


# ---------------------------------------------------------------------------
# Per-page prompt builders
# ---------------------------------------------------------------------------


def _build_page_1_prompt(pack: OrchestratorReportPack) -> str:
    """
    Build Page 1 (boss poster) generation prompt.

    Per spec §13.1:
        Must emphasize: primary action, conviction, ticker, suggested size,
        target window, why now, top risks.
        Must feel like a decision board, not a web page.
    """
    action_zh = approved_action_labels().get(pack.primary_action, pack.primary_action)
    conviction_zh = ZH_CONVICTION.get(pack.conviction, pack.conviction)
    alert_zh = ZH_ALERT.get(pack.alert_level or "None", "无警报")

    # Format locked facts for the prompt
    entry_line = f"{pack.entry_reference}" if pack.entry_reference else ""
    target_line = f"{pack.target_reference}" if pack.target_reference else ""
    stop_line = f"{pack.stop_reference}" if pack.stop_reference else ""

    # Format key numbers for must-show
    must_show_block = ""
    if pack.must_show_numbers:
        numbers_str = " | ".join(pack.must_show_numbers)
        must_show_block = f"\n关键数字（必须保留原值）: {numbers_str}"

    prompt = f"""Create a premium executive finance decision poster image.

IMAGE TYPE: Boss-facing investment decision board (NOT a web page, NOT a slideshow)

CONTENT REQUIREMENTS (strict):
- 股票代码 (Ticker): {pack.ticker} — {pack.company_name}
- 操作建议 (Action): {action_zh}
- 确信程度 (Conviction): {conviction_zh}
- 建议仓位 (Size): {pack.suggested_size}
- 目标周期 (Target Window): {pack.target_window}
{entry_line}- 入场参考: {entry_line}
{target_line}- 目标价位: {target_line}
{stop_line}- 止损价位: {stop_line}

WHY NOW (3 bullets — use as-is):
{pack.why_now}

TOP RISKS (3 bullets — use as-is):
{pack.top_risks}

ONE LINE CALL: {pack.one_line_call}
ALERT LEVEL: {alert_zh}
{must_show_block}

STYLE (spec §14):
- Premium executive finance design, institutional tone
- Chinese-first hierarchy — Chinese is the main visible language
- Warm neutral background (cream, light warm gray)
- Orange-red for action emphasis (primary decision, conviction)
- Teal-green for positive support (targets, catalysts, upside)
- Restrained red for risk (stop, failure mode)
- Clean sans-serif typography feel
- High information density but clear visual hierarchy

FORBIDDEN (do NOT include):
- Marketing poster style or startup aesthetic
- Social media infographic look
- Crypto or cartoon finance style
- English-only labels as primary
- Generic BUY/HOLD/SELL language
- Any invented facts not in the content above"""
    return prompt


def _build_page_2_prompt(pack: OrchestratorReportPack) -> str:
    """
    Build Page 2 (formal research summary) generation prompt.

    Per spec §13.2:
        Must emphasize: thesis summary, catalysts, valuation view,
        technical summary, must-show numbers.
    """
    must_show_block = ""
    if pack.must_show_numbers:
        numbers_str = " | ".join(pack.must_show_numbers)
        must_show_block = f"\n关键数字（必须保留原值）: {numbers_str}"

    bull_lines = pack.bull_case.split("\n")[:3]
    bull_bullets = "\n".join(f"- {b.strip()}" for b in bull_lines if b.strip())

    bear_lines = pack.bear_case.split("\n")[:2]
    bear_bullets = "\n".join(f"- {b.strip()}" for b in bear_lines if b.strip())

    prompt = f"""Create a formal research summary report page image.

IMAGE TYPE: Professional equity research page (NOT a memo, NOT a slide deck)

CONTENT REQUIREMENTS:

INVESTMENT THESIS:
{pack.thesis_summary or "研究进行中..."}

CATALYSTS (看涨理由):
{bull_bullets or pack.bull_case[:200]}

RISK VIEW (看跌风险):
{bear_bullets or pack.bear_case[:200]}

VALUATION VIEW:
{pack.valuation_summary or "估值分析进行中..."}

TECHNICAL SUMMARY:
{pack.technical_summary or "技术面分析进行中..."}

CATALYST SUMMARY:
{pack.catalysts or "催化剂分析进行中..."}
{must_show_block}

STYLE (spec §14):
- Premium executive finance design, institutional tone
- Chinese-first hierarchy — Chinese is the main visible language
- Warm neutral background
- Teal-green for positive support sections
- Restrained red for risk/bear case sections
- Clean, readable body text
- High information density in organized layout

FORBIDDEN:
- Marketing or startup aesthetic
- Social media infographic style
- English-only as primary language
- Invented numbers not in the source above"""
    return prompt


def _build_page_3_prompt(pack: OrchestratorReportPack) -> str:
    """
    Build Page 3 (optional detail page) generation prompt.

    Per spec §13.3 — used when options structure or validation is complex:
        - options structure detail
        - early exit detail
        - validation and monitoring detail
    """
    options_detail = pack.options_structure_summary or "期权结构待定"
    early_exit_detail = pack.early_exit_summary or "提前退出策略待定"
    instrument_reason = pack.instrument_choice_reason or "工具选择理由待定"

    conservative_alt = pack.conservative_alternative or "无"
    alt_instrument = pack.alternative_instrument or "无"
    key_numbers_block = ""
    if pack.options_key_numbers:
        key_numbers_block = "关键数字:\n" + "\n".join(f"- {n}" for n in pack.options_key_numbers)

    # Monitoring block
    regime_zh = ZH_REGIME.get(pack.regime, pack.regime)
    env_fit_zh = {"good": "良好", "mixed": "一般", "poor": "差"}.get(pack.environment_fit, pack.environment_fit)
    hist_sup_zh = {"strong": "强", "moderate": "中", "weak": "弱"}.get(pack.historical_support, pack.historical_support)
    fail_mode_zh = {
        "direction": "方向错误",
        "timing": "时机错误",
        "iv": "波动率风险",
        "liquidity": "流动性风险",
        "none": "无",
    }.get(pack.main_failure_mode, pack.main_failure_mode)

    watchlist_line = pack.watchlist_summary or "无观察状态"
    validation_line = pack.validation_summary or "验证信息待定"

    prompt = f"""Create an optional detail page for complex investment analysis.

IMAGE TYPE: Detailed supporting analysis page

OPTIONS STRATEGY DETAIL:
{instrument_reason}
主要工具: {pack.primary_instrument_label}
保守替代: {conservative_alt}
更高上限替代: {alt_instrument}

{options_detail}

EARLY EXIT PLAN:
{early_exit_detail}

{key_numbers_block}

MONITORING & VALIDATION:
观察状态: {watchlist_line}
验证摘要: {validation_line}
市场环境: {regime_zh}
环境匹配: {env_fit_zh}
历史支撑: {hist_sup_zh}
主要失效模式: {fail_mode_zh}

STYLE (spec §14):
- Premium executive finance design
- Chinese-first hierarchy
- Clean organized layout for detailed information
- Teal-green for positive indicators
- Restrained red for risk indicators
- High information density, readable

FORBIDDEN:
- Marketing poster style
- Social media infographic style
- English-only as primary"""
    return prompt


# ---------------------------------------------------------------------------
# Page-count decision
# ---------------------------------------------------------------------------


def _decide_page_count(pack: OrchestratorReportPack) -> int:
    """
    Decide how many pages this report needs.

    Per spec §2: adaptive, usually 1–3 pages.
        - 1 page: No Trade, Watchlist
        - 2 pages: standard instrument (Buy Stock, Buy Call)
        - 3 pages: complex options structure (Bull Call Spread, CSP with detail)
    """
    action = pack.primary_action
    if action in {"No Trade", "Watchlist"}:
        return 1
    if action in {"Bull Call Spread", "Sell Cash-Secured Put", "Covered Call"}:
        # Complex options — benefit from detail page
        if pack.options_structure_summary or pack.early_exit_summary:
            return 3
        return 2
    return 2


# ---------------------------------------------------------------------------
# Forbidden phrasing
# ---------------------------------------------------------------------------


def _build_forbidden_phrasing() -> list[str]:
    """Phrases the image model must not produce (spec §10, §14)."""
    return [
        "BUY",
        "HOLD",
        "SELL",
        "GenericBuy",
        "GenericSell",
        "StrongBuy",
        "MustBuy",
        "MoonShot",
        "Moon",
        "To the moon",
        "Lamborghini",
        "100x",
        "Guaranteed",
        "NoRisk",
    ]


# ---------------------------------------------------------------------------
# Visual priority order (spec §12)
# ---------------------------------------------------------------------------


def _build_visual_priority_order(pack: OrchestratorReportPack) -> list[str]:
    """Hierarchy of what to emphasize per page."""
    base = [
        "primary_action",
        "conviction",
        "ticker",
        "suggested_size",
        "target_window",
        "boss_summary",
        "entry_reference",
        "target_reference",
        "stop_reference",
    ]
    if pack.options_key_numbers:
        base.append("options_key_numbers")
    return base


# ---------------------------------------------------------------------------
# Main factory
# ---------------------------------------------------------------------------


def build_prompt_pack(pack: OrchestratorReportPack) -> ImagePromptPack:
    """
    Build a complete ImagePromptPack from an OrchestratorReportPack.

    Per spec §12:
        - Derives page_count from complexity
        - Builds one PagePrompt per page
        - Applies global style rules
        - Sets must_show_labels and forbidden_phrasing

    Args:
        pack: OrchestratorReportPack from orchestrator_reporting.

    Returns:
        Fully populated ImagePromptPack ready for image generation.
    """
    page_count = _decide_page_count(pack)
    global_style = build_default_style_rules()

    page_prompts: list[PagePrompt] = []

    # Page 1 — always present
    page_1 = PagePrompt(
        page_number=1,
        page_role="boss_poster",
        prompt_text=_build_page_1_prompt(pack),
        content_section_keys=[
            "report_identity",
            "decision_locked",
            "boss_narrative",
        ],
        must_preserve=[
            pack.primary_action,
            pack.conviction,
            pack.ticker,
            pack.suggested_size,
            pack.target_window,
            pack.one_line_call,
        ],
        forbidden_phrasing=_build_forbidden_phrasing(),
    )
    page_prompts.append(page_1)

    # Page 2 — always present (spec §13.2: "usually emphasize")
    page_2 = PagePrompt(
        page_number=2,
        page_role="formal_report",
        prompt_text=_build_page_2_prompt(pack),
        content_section_keys=[
            "research_core",
            "instrument_plan",
        ],
        must_preserve=pack.must_show_numbers.copy() if pack.must_show_numbers else [],
        forbidden_phrasing=_build_forbidden_phrasing(),
    )
    page_prompts.append(page_2)

    # Page 3 — only when needed
    if page_count >= 3:
        page_3 = PagePrompt(
            page_number=3,
            page_role="detail_page",
            prompt_text=_build_page_3_prompt(pack),
            content_section_keys=[
                "instrument_plan",
                "monitoring_state",
            ],
            must_preserve=pack.options_key_numbers.copy() if pack.options_key_numbers else [],
            forbidden_phrasing=_build_forbidden_phrasing(),
        )
        page_prompts.append(page_3)

    # Respect the page_count derived from pack complexity
    page_prompts = page_prompts[:page_count]

    return ImagePromptPack(
        model="gpt-image-2",
        page_count=page_count,
        global_style_rules=global_style,
        page_prompts=page_prompts,
        must_show_labels=ZH_LABELS.copy(),
        forbidden_phrasing=_build_forbidden_phrasing(),
        visual_priority_order=_build_visual_priority_order(pack),
        source_pack=pack,
    )
