"""Chinese-first bilingual string constants for Hermes report templates."""

# =============================================================================
# TOP ZONE - Decision Hero Section
# =============================================================================

STRINGS = {
    # Primary Action
    "action_buy": "买入",
    "action_sell": "卖出",
    "action_watch": "观望",
    "action_hold": "持有",
    "action_outperform": "跑赢大市",
    "action_underperform": "跑输大市",

    # Labels
    "label_action": "操作",
    "label_ticker": "代码",
    "label_company": "公司",
    "label_conviction": "信心度",
    "label_target_window": "目标窗口",
    "label_target_price": "目标价",
    "label_suggested_size": "建议仓位",
    "label_why_now": "为何此时",
    "label_top_risks": "主要风险",
    "label_entry_price": "入场价",
    "label_stop_loss": "止损价",
    "label_holding_period": "持仓周期",

    # Conviction levels
    "conviction_high": "高信心",
    "conviction_medium": "中信心",
    "conviction_low": "低信心",

    # =============================================================================
    # MIDDLE ZONE - KPI Cards
    # =============================================================================
    "label_current_price": "当前价",
    "label_pe_ratio": "市盈率",
    "label_eps_growth": "EPS增长",
    "label_analyst_rating": "分析师评级",
    "label_market_cap": "市值",
    "label_volume": "成交量",
    "label_52w_high": "52周高点",
    "label_52w_low": "52周低点",

    # =============================================================================
    # MIDDLE ZONE - Thesis & Catalysts
    # =============================================================================
    "label_thesis": "投资逻辑",
    "label_thesis_catalysts": "投资逻辑与催化剂",
    "label_bull_case": "看多逻辑",
    "label_bear_case": "看空逻辑",
    "label_key_catalysts": "关键催化剂",
    "label_risk_watch": "风险观察",

    # =============================================================================
    # MIDDLE ZONE - Technical Analysis
    # =============================================================================
    "label_technical": "技术面",
    "label_technical_analysis": "技术分析",
    "label_support": "支撑位",
    "label_resistance": "阻力位",
    "label_trend": "趋势",
    "label_moving_averages": "均线",
    "label_momentum": "动能",

    # Trend labels
    "trend_bullish": "看涨",
    "trend_bearish": "看跌",
    "trend_neutral": "中性",

    # =============================================================================
    # MIDDLE ZONE - Instrument Choice
    # =============================================================================
    "label_instrument_choice": "工具选择",
    "label_primary": "首选",
    "label_conservative": "保守方案",
    "label_alternative": "备选方案",
    "label_stock": "股票",
    "label_call": "买入看涨",
    "label_bull_call_spread": "牛市看涨价差",
    "label_cash_secured_put": "现金担保看跌",
    "label_covered_call": "备兑看涨",
    "label_rejected": "排除原因",

    # Instrument descriptions
    "desc_stock": "直接持有股票",
    "desc_call": "买入看涨期权",
    "desc_spread": "降低成本的价差策略",
    "desc_put": "以更低价格买入的机会",
    "desc_covered_call": "持股增强收益",

    # =============================================================================
    # MIDDLE ZONE - Options Structure
    # =============================================================================
    "label_options_structure": "期权结构",
    "label_expiry": "到期日",
    "label_strike": "行权价",
    "label_break_even": "盈亏平衡",
    "label_delta": "Delta",
    "label_theta": "Theta",
    "label_vega": "Vega",
    "label_gamma": "Gamma",
    "label_early_exit": "提前退出",
    "label_first_trim": "首次减仓",
    "label_profit_zone": "主要盈利区",
    "label_full_exit": "全部退出",

    # =============================================================================
    # BOTTOM ZONE - Watchlist & Validation
    # =============================================================================
    "label_watchlist_state": "监控状态",
    "label_validation_summary": "验证摘要",
    "label_regime": "市场状态",
    "label_historical_support": "历史支持",
    "label_environment_fit": "环境匹配",
    "label_failure_mode": "主要失效模式",
    "label_confidence": "信心指数",

    # Watchlist statuses
    "status_held": "持仓中",
    "status_high_priority": "重点关注",
    "status_research": "研究进行中",
    "status_passive": "被动跟踪",

    # Thesis states
    "thesis_strengthening": "逻辑强化",
    "thesis_stable": "逻辑稳定",
    "thesis_weakening": "逻辑弱化",
    "thesis_broken": "逻辑破坏",

    # Alert levels
    "alert_immediate": "立即关注",
    "alert_elevated": "需要关注",
    "alert_normal": "正常",
    "alert_low": "低优先级",

    # Validation regimes
    "regime_trending": "趋势市场",
    "regime_choppy": "震荡市场",
    "regime_volatile": "高波动",

    # =============================================================================
    # FOOTER
    # =============================================================================
    "label_generated_at": "生成时间",
    "label_hermes_desk": "Hermes 研究台",
    "label_decision_board": "决策看板",
    "label_page": "页",

    # =============================================================================
    # EMPTY STATES
    # =============================================================================
    "empty_kpi": "—",
    "empty_thesis": "暂无投资逻辑",
    "empty_technical": "暂无技术分析",
    "empty_risks": "暂无风险提示",
    "empty_watchlist": "暂无监控项目",
    "empty_validation": "暂无验证数据",
    "empty_instrument": "暂无工具建议",
    "empty_options": "暂无期权结构",
    "no_data": "暂无数据",

    # =============================================================================
    # REPORT TEMPLATE SPECIFIC
    # =============================================================================
    "label_executive_summary": "执行摘要",
    "label_research_summary": "研究摘要",
    "label_action_plan": "行动计划",
    "label_trade_plan": "交易计划",
    "label_bottom_line": "核心结论",
    "label_why_matters": "为何重要",
    "label_signals": "信号",
    "label_reports": "报告",
    "label_batch_overview": "批次总览",
    "label_research_date": "研究日期",
    "label_priority_rank": "优先级",
    "label_rating": "评级",
    "label_confidence_pct": "信心%",
    "label_priority_score": "优先级得分",
    "label_action_bias": "操作倾向",

    # =============================================================================
    # PHASE 15 - Early Exit Zone Labels
    # =============================================================================
    "label_first_trim_zone": "首轮减仓区",
    "label_main_profit_zone": "主要利润区",
    "label_full_exit_zone": "完全退出区",
    "label_trigger_condition": "触发条件",
    "label_target_return": "目标收益",

    # =============================================================================
    # PHASE 15 - Options Structure Detail Fields
    # =============================================================================
    "label_option_type": "期权类型",
    "label_net_debit": "净Debit",
    "label_net_credit": "净Credit",
    "label_primary_contract": "标的合约",
    "label_short_contract": "配对合约",
    "label_max_profit": "最大盈利",
    "label_max_loss": "最大亏损",
    "label_delta_estimate": "Delta估值",
    "label_covered_note": "备兑看涨备注",
    "label_assignment_strike": "配对行权价",

    # =============================================================================
    # PHASE 17 - Regime Labels
    # =============================================================================
    "regime_trend_up": "趋势向上",
    "regime_range_bound": "区间震荡",
    "regime_high_volatility": "高波动",
    "regime_risk_off": "风险规避",
    "regime_unknown": "未知",

    # =============================================================================
    # SUPPORTING-ONLY DISCLAIMER
    # =============================================================================
    "label_supporting_only": "仅供参考，不构成页面主结构",

    # =============================================================================
    # COMPANY REPORT SECTION HEADERS (PDF Pages 2+)
    # =============================================================================
    "label_decision_card_summary": "决策卡片摘要",
    "label_instrument_detail": "工具选择详情",
    "label_options_structure_detail": "期权结构详情",
    "label_supporting_data_grid": "支撑数据网格",
}
