"""English secondary string constants for Hermes report templates (used as subtitles)."""

STRINGS = {
    # Primary Action
    "action_buy": "BUY",
    "action_sell": "SELL",
    "action_watch": "WATCH",
    "action_hold": "HOLD",
    "action_outperform": "OUTPERFORM",
    "action_underperform": "UNDERPERFORM",

    # Labels
    "label_action": "Action",
    "label_ticker": "Ticker",
    "label_company": "Company",
    "label_conviction": "Conviction",
    "label_target_window": "Target Window",
    "label_target_price": "Target Price",
    "label_suggested_size": "Suggested Size",
    "label_why_now": "Why Now",
    "label_top_risks": "Top Risks",
    "label_entry_price": "Entry",
    "label_stop_loss": "Stop Loss",
    "label_holding_period": "Horizon",

    # Conviction levels
    "conviction_high": "HIGH CONVICTION",
    "conviction_medium": "MEDIUM CONVICTION",
    "conviction_low": "LOW CONVICTION",

    # =============================================================================
    # MIDDLE ZONE - KPI Cards
    # =============================================================================
    "label_current_price": "Price",
    "label_pe_ratio": "P/E Ratio",
    "label_eps_growth": "EPS Growth",
    "label_analyst_rating": "Analyst Rating",
    "label_market_cap": "Mkt Cap",
    "label_volume": "Volume",
    "label_52w_high": "52W High",
    "label_52w_low": "52W Low",

    # =============================================================================
    # MIDDLE ZONE - Thesis & Catalysts
    # =============================================================================
    "label_thesis": "Thesis",
    "label_thesis_catalysts": "Thesis & Catalysts",
    "label_bull_case": "Bull Case",
    "label_bear_case": "Bear Case",
    "label_key_catalysts": "Key Catalysts",
    "label_risk_watch": "Risk Watch",

    # =============================================================================
    # MIDDLE ZONE - Technical Analysis
    # =============================================================================
    "label_technical": "Technical",
    "label_technical_analysis": "Technical Analysis",
    "label_support": "Support",
    "label_resistance": "Resistance",
    "label_trend": "Trend",
    "label_moving_averages": "Moving Averages",
    "label_momentum": "Momentum",

    # Trend labels
    "trend_bullish": "Bullish",
    "trend_bearish": "Bearish",
    "trend_neutral": "Neutral",

    # =============================================================================
    # MIDDLE ZONE - Instrument Choice
    # =============================================================================
    "label_instrument_choice": "Instrument Choice",
    "label_primary": "Primary",
    "label_conservative": "Conservative",
    "label_alternative": "Alternative",
    "label_stock": "Stock",
    "label_call": "Long Call",
    "label_bull_call_spread": "Bull Call Spread",
    "label_cash_secured_put": "Cash-Secured Put",
    "label_covered_call": "Covered Call",
    "label_rejected": "Rejected Because",

    # Instrument descriptions
    "desc_stock": "Direct stock ownership",
    "desc_call": "Buy call options",
    "desc_spread": "Cost-efficient spread strategy",
    "desc_put": "Opportunity to buy at lower price",
    "desc_covered_call": "Income enhancement on held shares",

    # =============================================================================
    # MIDDLE ZONE - Options Structure
    # =============================================================================
    "label_options_structure": "Options Structure",
    "label_expiry": "Expiry",
    "label_strike": "Strike",
    "label_break_even": "Break-Even",
    "label_delta": "Delta",
    "label_theta": "Theta",
    "label_vega": "Vega",
    "label_gamma": "Gamma",
    "label_early_exit": "Early Exit",
    "label_first_trim": "First Trim",
    "label_profit_zone": "Profit Zone",
    "label_full_exit": "Full Exit",

    # =============================================================================
    # BOTTOM ZONE - Watchlist & Validation
    # =============================================================================
    "label_watchlist_state": "Watchlist State",
    "label_validation_summary": "Validation Summary",
    "label_regime": "Regime",
    "label_historical_support": "Historical Support",
    "label_environment_fit": "Environment Fit",
    "label_failure_mode": "Main Failure Mode",
    "label_confidence": "Confidence",

    # Watchlist statuses
    "status_held": "Held",
    "status_high_priority": "High Priority",
    "status_research": "In Research",
    "status_passive": "Passive Watch",

    # Thesis states
    "thesis_strengthening": "Strengthening",
    "thesis_stable": "Stable",
    "thesis_weakening": "Weakening",
    "thesis_broken": "Broken",

    # Alert levels
    "alert_immediate": "Immediate Review",
    "alert_elevated": "Elevated",
    "alert_normal": "Normal",
    "alert_low": "Low Priority",

    # Validation regimes
    "regime_trending": "Trending",
    "regime_choppy": "Choppy",
    "regime_volatile": "Volatile",

    # =============================================================================
    # FOOTER
    # =============================================================================
    "label_generated_at": "Generated",
    "label_hermes_desk": "Hermes Research Desk",
    "label_decision_board": "Decision Board",
    "label_page": "Page",

    # =============================================================================
    # EMPTY STATES
    # =============================================================================
    "empty_kpi": "—",
    "empty_thesis": "No thesis available",
    "empty_technical": "No technical data",
    "empty_risks": "No risk watch",
    "empty_watchlist": "No watchlist entries",
    "empty_validation": "No validation data",
    "empty_instrument": "No instrument recommendation",
    "empty_options": "No options structure",
    "no_data": "No data",

    # =============================================================================
    # REPORT TEMPLATE SPECIFIC
    # =============================================================================
    "label_executive_summary": "Executive Summary",
    "label_research_summary": "Research Summary",
    "label_action_plan": "Action Plan",
    "label_trade_plan": "Trade Plan",
    "label_bottom_line": "Bottom Line",
    "label_why_matters": "Why It Matters",
    "label_signals": "Signals",
    "label_reports": "Reports",
    "label_batch_overview": "Batch Overview",
    "label_research_date": "Date",
    "label_priority_rank": "Rank",
    "label_rating": "Rating",
    "label_confidence_pct": "Conf %",
    "label_priority_score": "Priority",
    "label_action_bias": "Bias",

    # =============================================================================
    # PHASE 15 - Early Exit Zone Labels
    # =============================================================================
    "label_first_trim_zone": "First Trim Zone",
    "label_main_profit_zone": "Main Profit Zone",
    "label_full_exit_zone": "Full Exit Zone",
    "label_trigger_condition": "Trigger Condition",
    "label_target_return": "Target Return",

    # =============================================================================
    # PHASE 15 - Options Structure Detail Fields
    # =============================================================================
    "label_option_type": "Option Type",
    "label_net_debit": "Net Debit",
    "label_net_credit": "Net Credit",
    "label_primary_contract": "Primary Contract",
    "label_short_contract": "Short Contract",
    "label_max_profit": "Max Profit",
    "label_max_loss": "Max Loss",
    "label_delta_estimate": "Delta Estimate",
    "label_covered_note": "Covered Call Note",
    "label_assignment_strike": "Assignment Strike",

    # =============================================================================
    # PHASE 17 - Regime Labels
    # =============================================================================
    "regime_trend_up": "Trend Up",
    "regime_range_bound": "Range Bound",
    "regime_high_volatility": "High Volatility",
    "regime_risk_off": "Risk Off",
    "regime_unknown": "Unknown",

    # =============================================================================
    # SUPPORTING-ONLY DISCLAIMER
    # =============================================================================
    "label_supporting_only": "For reference only, not the page primary structure",

    # =============================================================================
    # COMPANY REPORT SECTION HEADERS (PDF Pages 2+)
    # =============================================================================
    "label_decision_card_summary": "Decision Card Summary",
    "label_instrument_detail": "Instrument Detail",
    "label_options_structure_detail": "Options Structure Detail",
    "label_supporting_data_grid": "Supporting Data Grid",
}
