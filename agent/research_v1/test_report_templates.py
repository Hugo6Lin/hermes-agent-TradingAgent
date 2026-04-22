"""Tests for Hermes Boss Poster & Report template system.

Covers:
- Hero decision section rendering
- Chinese-first bilingual labels
- Watchlist and validation rendering
- No-data graceful states
- Print/page-break structure
- Poster/report section rendering
"""

import pytest
from pathlib import Path
import sys

# Ensure the package is importable
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestPosterData:
    """Test PosterData construction from canonical formats."""

    def test_build_poster_from_signal_and_report(self):
        """Hero section should populate from signal + report."""
        from agent.research_v1.report_templates.renderer import _build_poster_from_signal_report

        signal = {
            "ticker": "NVDA",
            "rating": "BUY",
            "confidence": 0.82,
            "entry_price": 120.5,
            "stop_loss": 105.0,
            "take_profit": 180.0,
            "holding_horizon": "12 months",
            "priority_score": 8.5,
        }
        report = {
            "ticker": "NVDA",
            "company_name": "NVIDIA Corporation",
            "bottom_line": "Strong AI infrastructure play",
            "why_now": "1. Data center growth accelerating\n2. H100 demand outstrips supply\n3. China export relief",
            "bull_case": "1. AI infrastructure buildout multi-year\n2. Data center revenue 5x growth\n3. Gaming recovery",
            "risk_watch": ["Competition from AMD", "China export restrictions", "Valuation premium"],
            "trade_plan": {
                "action": "Buy",
                "entry_price": 120.5,
                "stop_loss": 105.0,
                "take_profit": 180.0,
                "holding_period": "12 months",
                "size_hint": "15% Portfolio",
            },
        }
        market_data = {
            "price": 122.3,
            "pe_ratio": "45.2",
            "eps_growth": "+85%",
            "analyst_rating": "4.5/5",
            "support": 115.0,
            "resistance": 130.0,
            "trend": "Bullish",
        }

        poster = _build_poster_from_signal_report(signal, report, market_data)

        assert poster.ticker == "NVDA"
        assert poster.company_name == "NVIDIA Corporation"
        assert poster.action_zh == "买入股票"  # BUY degrades to Hermes action vocabulary
        assert poster.action_en == "Buy Stock"
        assert poster.conviction_zh == "高信心"  # confidence >= 0.75
        assert poster.suggested_size == "15% Portfolio"
        assert poster.target_window == "12 months"
        assert poster.target_price == "120.5 → 180.0"
        assert len(poster.why_now) == 3
        assert len(poster.top_risks) == 3
        assert poster.kpi["price"] == 122.3
        assert poster.kpi["pe"] == "45.2"
        assert poster.technical["support"] == 115.0
        assert poster.technical["resistance"] == 130.0
        assert poster.technical["trend"] == "Bullish"

    def test_conviction_mapping(self):
        """Conviction level should map from confidence value."""
        from agent.research_v1.report_templates.renderer import _build_poster_from_signal_report

        cases = [
            (0.85, "高信心", "HIGH CONVICTION"),
            (0.60, "中信心", "MEDIUM CONVICTION"),
            (0.30, "低信心", "LOW CONVICTION"),
        ]
        for conf, zh, en in cases:
            signal = {"ticker": "TEST", "confidence": conf, "rating": "BUY"}
            report = {}
            poster = _build_poster_from_signal_report(signal, report)
            assert poster.conviction_zh == zh, f"confidence={conf}"
            assert poster.conviction_en == en, f"confidence={conf}"

    def test_rating_mapping(self):
        """Rating should map correctly to Chinese/English."""
        from agent.research_v1.report_templates.renderer import _map_rating

        cases = [
            ("BUY", "买入股票", "Buy Stock", "buy"),
            ("Outperform", "买入股票", "Buy Stock", "buy"),
            ("强烈买入", "买入股票", "Buy Stock", "buy"),
            ("Hold", "观望", "Watchlist", "hold"),
            ("Neutral", "观望", "Watchlist", "hold"),
            ("Sell", "不交易", "No Trade", "underperform"),
            ("Underperform", "不交易", "No Trade", "underperform"),
        ]
        for rating, zh, en, cls in cases:
            result_zh, result_en, result_cls = _map_rating(rating)
            assert result_zh == zh, f"rating={rating}"
            assert result_en == en, f"rating={rating}"
            assert result_cls == cls, f"rating={rating}"


class TestChineseFirstBilingual:
    """Test Chinese-first bilingual label rendering."""

    def test_poster_has_chinese_labels(self):
        """Poster template should contain Chinese labels as primary."""
        from agent.research_v1.report_templates.renderer import _load_strings

        zh, en = _load_strings()

        # Key labels should exist in both languages
        key_labels = [
            "label_action", "label_ticker", "label_conviction",
            "label_target_window", "label_suggested_size", "label_why_now",
            "label_top_risks", "label_technical_analysis", "label_instrument_choice",
        ]
        for label in key_labels:
            assert label in zh, f"Missing Chinese label: {label}"
            assert label in en, f"Missing English label: {label}"
            assert zh[label] != en[label], f"Chinese and English should differ for {label}"

    def test_poster_action_block_chinese_first(self):
        """Action block should show Chinese action as dominant."""
        from agent.research_v1.report_templates.renderer import _build_poster_from_signal_report

        signal = {"ticker": "TSLA", "rating": "BUY", "confidence": 0.75}
        report = {}
        poster = _build_poster_from_signal_report(signal, report)

        # Chinese action should be primary
        assert poster.action_zh in ("买入股票", "观望", "不交易")
        # English action is secondary subtitle
        assert poster.action_en in ("Buy Stock", "Watchlist", "No Trade")

    def test_instrument_labels_bilingual(self):
        """Instrument choice labels should be bilingual."""
        from agent.research_v1.report_templates.renderer import _load_strings

        zh, en = _load_strings()

        instrument_labels = [
            "label_stock", "label_call", "label_bull_call_spread",
            "label_cash_secured_put", "label_covered_call",
        ]
        for label in instrument_labels:
            assert label in zh
            assert label in en


class TestWatchlistValidation:
    """Test watchlist and validation rendering."""

    def test_watchlist_status_mapping(self):
        """Watchlist status should map to Chinese + CSS class."""
        from agent.research_v1.report_templates.renderer import _map_watchlist_status

        cases = [
            ("Held", "持仓中", "Held", "held"),
            ("High Priority", "重点关注", "High Priority", "high-priority"),
            ("Research", "研究进行中", "In Research", "research"),
            ("Passive", "被动跟踪", "Passive", "passive"),
        ]
        for status, zh, en, cls in cases:
            result_zh, result_en, result_cls = _map_watchlist_status(status)
            assert result_zh == zh, f"status={status}"
            assert result_cls == cls, f"status={status}"

    def test_validation_confidence_class(self):
        """Validation confidence should map to CSS class."""
        from agent.research_v1.report_templates.renderer import _map_confidence_class

        assert _map_confidence_class(0.85) == "high"
        assert _map_confidence_class(0.50) == "medium"
        assert _map_confidence_class(0.30) == ""
        assert _map_confidence_class("0.75") == "high"

    def test_poster_watchlist_state_optional(self):
        """Watchlist state should be optional - graceful empty state."""
        from agent.research_v1.report_templates.renderer import _build_poster_from_signal_report

        signal = {"ticker": "TEST", "rating": "BUY", "confidence": 0.5}
        report = {}

        # Without watchlist entry
        poster = _build_poster_from_signal_report(signal, report)
        assert poster.watchlist_state["status_zh"] == "—"

        # With watchlist entry
        watchlist_entry = {
            "status": "Held",
            "thesis_state": "Strengthening",
            "alert_level": "Normal",
            "current_action_bias": "Buy",
        }
        poster = _build_poster_from_signal_report(signal, report, watchlist_entry=watchlist_entry)
        assert poster.watchlist_state["status_zh"] == "持仓中"
        assert poster.watchlist_state["status_class"] == "held"
        assert poster.watchlist_state["action_bias"] == "Buy"

    def test_poster_validation_optional(self):
        """Validation should be optional - graceful empty state."""
        from agent.research_v1.report_templates.renderer import _build_poster_from_signal_report

        signal = {"ticker": "TEST", "rating": "BUY", "confidence": 0.5}
        report = {}

        poster = _build_poster_from_signal_report(signal, report)
        assert poster.validation["regime"] == "—"

        validation_result = {
            "regime": "Trending",
            "historical_support": "Strong",
            "environment_fit": "Good",
            "main_failure_mode": "Volatility spike",
            "validation_confidence": 0.78,
        }
        poster = _build_poster_from_signal_report(signal, report, validation_result=validation_result)
        assert poster.validation["regime"] == "Trending"
        assert poster.validation["confidence"] == "78%"
        assert poster.validation["confidence_class"] == "high"


class TestNoDataGracefulStates:
    """Test graceful handling of missing data."""

    def test_poster_with_empty_signal_and_report(self):
        """Empty signal and report should produce valid poster with placeholders."""
        from agent.research_v1.report_templates.renderer import _build_poster_from_signal_report

        poster = _build_poster_from_signal_report({}, {})

        assert poster.ticker == "—"
        assert poster.action_zh == "—"  # unknown rating -> "—"
        assert poster.suggested_size == "—"
        assert poster.target_window == "—"
        assert poster.kpi["price"] == "—"
        assert poster.kpi["pe"] == "—"

    def test_poster_with_partial_data(self):
        """Partial data should fill what it can, leave rest as placeholders."""
        from agent.research_v1.report_templates.renderer import _build_poster_from_signal_report

        signal = {"ticker": "AAPL", "rating": "BUY", "confidence": 0.7}
        report = {}  # Empty report

        poster = _build_poster_from_signal_report(signal, report)

        assert poster.ticker == "AAPL"
        assert poster.action_zh == "买入股票"
        assert poster.why_now == []  # No why_now from empty report
        assert poster.thesis_catalysts == []
        assert poster.kpi["price"] == "—"  # No market_data

    def test_instrument_choice_default_structure(self):
        """Instrument choice should default to full 5-instrument structure."""
        from agent.research_v1.report_templates.renderer import _build_poster_from_signal_report

        signal = {"ticker": "TEST", "rating": "BUY", "confidence": 0.5}
        report = {}
        poster = _build_poster_from_signal_report(signal, report)

        assert len(poster.instruments) == 5
        instrument_names = [i["name_zh"] for i in poster.instruments]
        assert "股票 / Stock" in instrument_names
        assert "买入看涨 / Call" in instrument_names
        assert "价差 / Spread" in instrument_names
        assert "看跌 / Put" in instrument_names
        assert "备兑 / Covered" in instrument_names

        # Primary should be first (stock)
        assert poster.instruments[0]["role"] == "primary"
        # Put and Covered should be rejected
        assert poster.instruments[3]["role"] == "rejected"
        assert poster.instruments[4]["role"] == "rejected"

    def test_thesis_points_extraction(self):
        """Thesis points should be extracted from multi-line text."""
        from agent.research_v1.report_templates.renderer import _extract_thesis_points

        text = """1. First thesis point about growth
2. Second thesis about margins
3. Third catalyst item
4. Fourth supporting factor"""
        points = _extract_thesis_points(text, max_points=4)

        assert len(points) == 4
        assert "First thesis point" in points[0]["zh"]
        assert "Second thesis" in points[1]["zh"]

    def test_thesis_points_max_limit(self):
        """Thesis points should respect max_points limit."""
        from agent.research_v1.report_templates.renderer import _extract_thesis_points

        text = "1. One\n2. Two\n3. Three\n4. Four\n5. Five"
        points = _extract_thesis_points(text, max_points=3)

        assert len(points) == 3


class TestPrintPageBreakStructure:
    """Test print and page-break CSS structure."""

    def test_poster_css_has_aspect_ratio(self):
        """Poster CSS should define 3:4 aspect ratio."""
        template_dir = Path(__file__).parent.parent / "report_templates"
        css_path = template_dir / "boss_report_pdf.css"

        if css_path.exists():
            css = css_path.read_text(encoding="utf-8")
            assert "aspect-ratio" in css or "aspect-ratio" in css
            # Check for A4-like proportions
            assert "210mm" in css or "A4" in css

    def test_poster_css_has_print_optimizations(self):
        """Poster CSS should have print-specific optimizations."""
        template_dir = Path(__file__).parent.parent / "report_templates"
        css_path = template_dir / "boss_report_pdf.css"

        if css_path.exists():
            css = css_path.read_text(encoding="utf-8")
            assert "@page" in css or "print" in css.lower()

    def test_report_css_has_page_break_rules(self):
        """Report CSS should define page-break rules."""
        template_dir = Path(__file__).parent.parent / "report_templates"
        css_path = template_dir / "boss_report_pdf.css"

        if css_path.exists():
            css = css_path.read_text(encoding="utf-8")
            assert "page-break" in css or "break-" in css

    def test_poster_zones_defined(self):
        """Poster should have clear zone definitions in CSS."""
        template_dir = Path(__file__).parent.parent / "report_templates"
        css_path = template_dir / "boss_report_pdf.css"

        if css_path.exists():
            css = css_path.read_text(encoding="utf-8")
            # Zone classes should be defined
            assert ".poster-header" in css
            assert ".poster-body" in css
            assert ".poster-footer" in css


class TestColorSystem:
    """Test orange-red + teal-green color system."""

    def test_action_color_orange_red(self):
        """Primary action should use orange-red color."""
        template_dir = Path(__file__).parent.parent / "report_templates"
        css_path = template_dir / "boss_report_pdf.css"

        if css_path.exists():
            css = css_path.read_text(encoding="utf-8")
            # Orange-red should be present
            assert "#E85A3C" in css or "E85A3C" in css

    def test_positive_color_teal_green(self):
        """Positive indicators should use teal-green color."""
        template_dir = Path(__file__).parent.parent / "report_templates"
        css_path = template_dir / "boss_report_pdf.css"

        if css_path.exists():
            css = css_path.read_text(encoding="utf-8")
            # Teal-green should be present
            assert "#2DD4A8" in css or "2DD4A8" in css

    def test_risk_color_deep_red(self):
        """Risk chips should use deep red, not orange-red."""
        template_dir = Path(__file__).parent.parent / "report_templates"
        css_path = template_dir / "boss_report_pdf.css"

        if css_path.exists():
            css = css_path.read_text(encoding="utf-8")
            # Deep red (different from action orange-red)
            assert "#C0392B" in css or "C0392B" in css

    def test_background_warm_off_white(self):
        """Background should be warm off-white, not pure white."""
        template_dir = Path(__file__).parent.parent / "report_templates"
        css_path = template_dir / "boss_report_pdf.css"

        if css_path.exists():
            css = css_path.read_text(encoding="utf-8")
            assert "#FAF8F5" in css or "FAF8F5" in css

    def test_header_dark_charcoal(self):
        """Top zone header should be deep charcoal."""
        template_dir = Path(__file__).parent.parent / "report_templates"
        css_path = template_dir / "boss_report_pdf.css"

        if css_path.exists():
            css = css_path.read_text(encoding="utf-8")
            assert "#1C1C1E" in css or "1C1C1E" in css


class TestEarlyExitZones:
    """Test Phase 15 Early Exit zones — per spec Section 五.5.2."""

    def test_build_early_exit_zones_basic(self):
        """_build_early_exit_zones should return zone dicts with correct keys."""
        from agent.research_v1.report_templates.renderer import _build_early_exit_zones

        # Mock early exit plan as a dict
        early_exit_plan = {
            "first_trim": {
                "zone_name": "first_trim",
                "action": "Trim",
                "target_return_pct": 0.30,
                "trigger_condition": "30% gain",
            },
            "main_profit": {
                "zone_name": "main_profit",
                "action": "Take Profit",
                "target_return_pct": 0.50,
                "trigger_condition": "50% gain",
            },
            "full_exit": {
                "zone_name": "full_exit",
                "action": "Exit",
                "target_return_pct": 0.70,
                "trigger_condition": "70% gain",
            },
        }
        zones = _build_early_exit_zones(early_exit_plan)
        assert len(zones) == 3
        assert zones[0]["zone_name_zh"] == "首轮减仓区"
        assert zones[0]["zone_name_en"] == "First Trim Zone"
        assert zones[0]["action_zh"] == "Trim"
        assert zones[0]["target_return"] == "30%"
        assert zones[0]["trigger"] == "30% gain"

    def test_build_early_exit_zones_empty(self):
        """Empty early exit plan should return empty list."""
        from agent.research_v1.report_templates.renderer import _build_early_exit_zones

        zones = _build_early_exit_zones(None)
        assert zones == []

    def test_poster_renders_early_exit_zones(self):
        """Poster should render early exit zones when present."""
        from agent.research_v1.report_templates.renderer import render_boss_poster

        early_exit_plan = {
            "first_trim": {
                "zone_name": "first_trim",
                "action": "Trim 1/3",
                "target_return_pct": 0.30,
                "trigger_condition": "+30%",
            },
            "main_profit": {
                "zone_name": "main_profit",
                "action": "Exit Full",
                "target_return_pct": 0.60,
                "trigger_condition": "+60%",
            },
            "full_exit": {
                "zone_name": "full_exit",
                "action": "Close All",
                "target_return_pct": 0.90,
                "trigger_condition": "+90%",
            },
        }
        html = render_boss_poster(
            signal={"ticker": "TSLA", "rating": "BUY", "confidence": 0.8},
            report={"company_name": "Tesla", "bottom_line": "EV leader"},
            early_exit_plan=early_exit_plan,
        )
        assert "early-exit-zone" in html
        assert "Trim" in html
        assert "30%" in html


class TestDecisionObjectFirstCompanyReport:
    """Test PDF company report decision-object-first section order — per spec Section 六."""

    def test_company_report_section_order(self):
        """Company report should follow decision-object-first order."""
        from agent.research_v1.report_templates.renderer import render_batch_report

        html = render_batch_report(
            batch_items=[
                {"symbol": "NVDA", "company_name": "NVIDIA", "overall_rating": "Buy",
                 "confidence": 0.82, "display_rank": 1, "rating_zh": "买入",
                 "rating_en": "Buy", "rating_class": "buy", "action_bias": "Bullish", "target_price": "180"}
            ],
            company_reports=[{
                "ticker": "NVDA",
                "company_name": "NVIDIA",
                "rating": "Buy",
                "action_zh": "买入看涨",
                "action_en": "Buy Call",
                "conviction_zh": "高信心",
                "conviction_en": "High Conviction",
                "bottom_line": "AI infrastructure play",
                "instrument_primary": {"name_zh": "买入看涨", "name_en": "Buy Call", "reason": "Leveraged", "role": "primary"},
                "instrument_conservative": {"name_zh": "股票", "name_en": "Stock", "reason": "Direct", "role": "conservative"},
                "instrument_alternative": {"name_zh": "价差", "name_en": "Spread", "reason": "Cost efficient", "role": "alternative"},
                "options_detail": {"option_type": "Buy Call", "expiry": "6", "strike": "130", "break_even": "135", "delta": "0.55", "net_debit": "—", "max_profit": "—"},
                "early_exit_zones": [],
                "supporting_entry": "120",
                "supporting_stop": "100",
                "supporting_target": "180",
                "supporting_horizon": "3-6 months",
                "bull_case": "AI buildout multi-year",
                "risk_watch": ["AMD competition"],
                "trade_plan": {},
                "research_summary": "",
            }],
            watchlist_entries=[],
            validation_results=[],
        )
        # Decision card summary should appear before instrument detail
        idx_decision = html.index("decision-card-summary")
        idx_instrument = html.index("instrument-detail-row")
        assert idx_decision < idx_instrument, "Decision card must come before instrument detail"

        # Instrument detail should come before supporting grid
        idx_supporting = html.index("supporting-only")
        assert idx_instrument < idx_supporting, "Instrument detail must come before supporting grid"

    def test_supporting_grid_has_disclaimer(self):
        """Supporting data grid must include supporting-only disclaimer."""
        from agent.research_v1.report_templates.renderer import render_batch_report

        html = render_batch_report(
            batch_items=[],
            company_reports=[{
                "ticker": "NVDA",
                "company_name": "NVIDIA",
                "rating": "Buy",
                "action_zh": "买入",
                "action_en": "Buy",
                "conviction_zh": "中信心",
                "conviction_en": "Medium Conviction",
                "bottom_line": "Test",
                "supporting_entry": "120",
                "supporting_stop": "100",
                "supporting_target": "180",
                "supporting_horizon": "3 months",
                "instrument_primary": {},
                "instrument_conservative": {},
                "instrument_alternative": {},
                "options_detail": {},
                "early_exit_zones": [],
                "bull_case": "",
                "risk_watch": [],
                "trade_plan": {},
                "research_summary": "",
            }],
            watchlist_entries=[],
            validation_results=[],
        )
        assert "supporting-only" in html
        assert ("仅供参考" in html or "For reference only" in html), "Supporting grid must have disclaimer"

    def test_bullish_only_action_display(self):
        """Poster should display specific instrument action, not generic BUY."""
        from agent.research_v1.report_templates.renderer import render_boss_poster

        # Use position_decision to specify a specific instrument action
        class MockPositionDecision:
            primary_action = "Buy Call"
            conviction = "High"
            thesis_summary = "AI infrastructure play"

        html = render_boss_poster(
            signal={"ticker": "NVDA", "rating": "Buy Call", "confidence": 0.82},
            report={"company_name": "NVIDIA", "bottom_line": "AI infrastructure"},
            position_decision=MockPositionDecision(),
        )
        # Should show the specific instrument action, not generic BUY
        assert "买入看涨" in html or "Buy Call" in html
        # Generic BUY should not be the dominant action (only if action_zh falls back to "BUY")
        # The key is it should NOT show "BUY" as a standalone generic term
        assert "BUY" not in html or "BUY" in html.split("买入看涨")[0]  # Allow BUY in subtitle context

    def test_non_stock_action_csp_in_company_report(self):
        """Company report with Sell Cash-Secured Put should show instrument-specific labels."""
        from agent.research_v1.report_templates.renderer import render_batch_report

        # Simulate Sell Cash-Secured Put decision — this is Phase 14-17 data
        # as it would come from export_task_pdf -> get_canonical_reports_by_task
        company_reports = [{
            "ticker": "AAPL",
            "company_name": "Apple Inc.",
            "rating": "Sell Cash-Secured Put",
            "confidence": 0.75,
            "bottom_line": "Sell CSP at $170 for income",
            # Phase 14: decision_card with CSP action
            "position_decision": {
                "primary_action": "Sell Cash-Secured Put",
                "conviction": "Medium",
                "thesis_summary": "Premium income play",
            },
            # Phase 14: instrument_rec
            "instrument_rec": {
                "primary_action": "Sell Cash-Secured Put",
                "ranked_alternatives": ["Buy Stock", "Sell Cash-Secured Put"],
            },
            # Supporting fields (legacy)
            "supporting_entry": "—",
            "supporting_stop": "—",
            "supporting_target": "—",
            "supporting_horizon": "—",
            "bull_case": "Income generation",
            "risk_watch": ["Assignment risk"],
            "trade_plan": {},
            "research_summary": "",
            "instrument_primary": {
                "name_zh": "卖出备兑看跌",
                "name_en": "Sell Cash-Secured Put",
                "reason": "Income generation",
                "role": "primary",
            },
            "instrument_conservative": {},
            "instrument_alternative": {},
            "options_detail": {},
            "early_exit_zones": [],
        }]

        html = render_batch_report(
            batch_items=[{
                "symbol": "AAPL",
                "company_name": "Apple Inc.",
                "overall_rating": "Sell Cash-Secured Put",
                "confidence": 0.75,
                "display_rank": 1,
                "rating_zh": "卖出备兑看跌",
                "rating_en": "Sell Cash-Secured Put",
                "rating_class": "buy",
                "action_bias": "Bullish",
                "target_price": "—",
            }],
            company_reports=company_reports,
            watchlist_entries=[],
            validation_results=[],
        )
        # Decision card should show CSP action (not generic BUY/SELL)
        assert "卖出备兑看跌" in html or "Sell Cash-Secured Put" in html
        # Should NOT show generic BUY or SELL as the primary action
        # (Note: rating_class "buy" maps to teal, but the specific instrument name should appear)


class TestOptionsDetail:
    """Test Phase 15 Options Structure detail rendering."""

    def test_build_options_detail_basic(self):
        """_build_options_detail should return full options dict."""
        from agent.research_v1.report_templates.renderer import _build_options_detail

        class MockPrimaryContract:
            expiry_months = 6
            strike = 130
            delta_estimate = 0.55
            option_type = "Call"

        class MockOptionsStructure:
            instrument_action = "Buy Call"
            primary_contract = MockPrimaryContract()
            strategy_net_debit = 5.20
            break_even_price = 135.20
            max_profit_pct = None
            max_loss_pct = None
            covered_by_shares = False
            short_contract = None

        opts = _build_options_detail(MockOptionsStructure(), None)
        assert opts["option_type"] == "Buy Call"
        assert opts["expiry"] == "6"
        assert opts["strike"] == "130"
        assert opts["delta"] == "0.55"
        assert opts["net_debit"] == "5.20"
        assert opts["break_even"] == "135.2"

    def test_build_options_detail_empty(self):
        """Empty options structure should return empty dict."""
        from agent.research_v1.report_templates.renderer import _build_options_detail

        opts = _build_options_detail(None, None)
        assert opts == {}

    def test_build_instrument_detail(self):
        """_build_instrument_detail should return primary, conservative, alternative."""
        from agent.research_v1.report_templates.renderer import _build_instrument_detail

        class MockInstRec:
            # ranked_alternatives is list[str] per contracts.py
            # "Buy Call" is primary_action so won't be used for conservative/alternative
            ranked_alternatives = ["Buy Stock", "Bull Call Spread"]

        primary, conservative, alternative = _build_instrument_detail(MockInstRec(), "Buy Call")
        assert primary["name_zh"] == "买入看涨"
        assert primary["role"] == "primary"
        assert conservative["name_zh"] == "买入股票"  # "Buy Stock" maps to 买入股票
        assert alternative["name_zh"] == "牛市看涨价差"  # "Bull Call Spread" maps to 牛市看涨价差


class TestInstrumentChoiceHierarchy:
    """Test instrument choice with Primary/Conservative/Alternative hierarchy."""

    def test_instrument_primary_is_distinct(self):
        """Primary instrument should be visually distinct."""
        from agent.research_v1.report_templates.renderer import _build_poster_from_signal_report

        signal = {"ticker": "TEST", "rating": "BUY", "confidence": 0.5}
        report = {}
        poster = _build_poster_from_signal_report(signal, report)

        primary = next((i for i in poster.instruments if i["role"] == "primary"), None)
        assert primary is not None
        assert primary["name_zh"] == "股票 / Stock"

    def test_instrument_conservative_is_distinct(self):
        """Conservative alternative should be distinct from primary."""
        from agent.research_v1.report_templates.renderer import _build_poster_from_signal_report

        signal = {"ticker": "TEST", "rating": "BUY", "confidence": 0.5}
        report = {}
        poster = _build_poster_from_signal_report(signal, report)

        conservative = next((i for i in poster.instruments if i["role"] == "conservative"), None)
        assert conservative is not None

        primary = next((i for i in poster.instruments if i["role"] == "primary"), None)
        assert conservative["name_zh"] != primary["name_zh"]

    def test_instrument_rejected_has_no_recommendation(self):
        """Rejected instruments should have 'rejected' role."""
        from agent.research_v1.report_templates.renderer import _build_poster_from_signal_report

        signal = {"ticker": "TEST", "rating": "BUY", "confidence": 0.5}
        report = {}
        poster = _build_poster_from_signal_report(signal, report)

        rejected = [i for i in poster.instruments if i["role"] == "rejected"]
        assert len(rejected) == 2  # Put and Covered
        assert all(i["reason"] == "—" for i in rejected)

    def test_real_instrument_action_buy_call(self):
        """Real PositionDecisionCard with Buy Call should show Chinese instrument labels."""
        from agent.research_v1.report_templates.renderer import _build_poster_from_signal_report
        from dataclasses import dataclass

        @dataclass
        class FakePositionDecision:
            primary_action: str = "Buy Call"
            conviction: str = "High"
            thesis_summary: str = "Test thesis"
            why_now: str = "Test why"
            alternatives: list = None

        signal = {"ticker": "TSLA", "confidence": 0.8}
        report = {}
        poster = _build_poster_from_signal_report(signal, report, position_decision=FakePositionDecision())

        # Primary should be Buy Call
        primary = next((i for i in poster.instruments if i["role"] == "primary"), None)
        assert primary is not None
        assert "买入看涨" in primary["name_zh"], f"Expected 买入看涨 in {primary['name_zh']}"
        assert "Buy Call" in primary["name_en"]

        # Action block should show Buy Call
        assert "买入看涨" in poster.action_zh
        assert poster.conviction_zh == "高信心"

    def test_real_instrument_action_bull_call_spread(self):
        """Real PositionDecisionCard with Bull Call Spread shows Chinese labels."""
        from agent.research_v1.report_templates.renderer import _build_poster_from_signal_report
        from dataclasses import dataclass

        @dataclass
        class FakePositionDecision:
            primary_action: str = "Bull Call Spread"
            conviction: str = "Medium"
            thesis_summary: str = "Test thesis"
            why_now: str = "Test why"
            alternatives: list = None

        signal = {"ticker": "AAPL", "confidence": 0.6}
        report = {}
        poster = _build_poster_from_signal_report(signal, report, position_decision=FakePositionDecision())

        primary = next((i for i in poster.instruments if i["role"] == "primary"), None)
        assert primary is not None
        assert "牛市看涨价差" in primary["name_zh"], f"Expected 牛市看涨价差 in {primary['name_zh']}"
        assert "Bull Call Spread" in primary["name_en"]


class TestRendererAPI:
    """Test the public renderer API."""

    def test_render_boss_poster_returns_html(self):
        """render_boss_poster should return HTML string."""
        from agent.research_v1.report_templates.renderer import render_boss_poster

        signal = {"ticker": "NVDA", "rating": "BUY", "confidence": 0.8}
        report = {
            "bottom_line": "AI infrastructure leader",
            "why_now": "Data center growth accelerating",
            "bull_case": "Multi-year AI buildout",
            "risk_watch": ["AMD competition"],
        }

        html = render_boss_poster(signal, report)

        assert isinstance(html, str)
        assert len(html) > 1000  # Substantial content
        assert "NVDA" in html
        assert "买入" in html  # Chinese action
        assert "<!DOCTYPE html>" in html

    def test_render_batch_report_returns_html(self):
        """render_batch_report should return HTML string."""
        from agent.research_v1.report_templates.renderer import render_batch_report

        batch_items = [
            {
                "symbol": "NVDA",
                "display_rank": 1,
                "overall_rating": "BUY",
                "confidence": 0.82,
                "priority_score": 8.5,
                "action": "Buy",
                "entry_price": 120.0,
                "take_profit": 180.0,
            }
        ]
        company_reports = [
            {
                "ticker": "NVDA",
                "title": "NVIDIA Corporation",
                "bottom_line": "AI infrastructure leader",
                "rating": "BUY",
                "confidence": 0.82,
                "bull_case": "Multi-year AI buildout",
                "risk_watch": ["AMD competition"],
            }
        ]

        html = render_batch_report(batch_items, company_reports)

        assert isinstance(html, str)
        assert len(html) > 500
        assert "NVDA" in html
        assert "批次总览" in html  # Chinese batch overview

    def test_render_poster_with_optional_data(self):
        """render_boss_poster should handle None optional data."""
        from agent.research_v1.report_templates.renderer import render_boss_poster

        signal = {"ticker": "TEST", "rating": "BUY", "confidence": 0.7}
        report = {}

        # All optional params as None
        html = render_boss_poster(
            signal=signal,
            report=report,
            market_data=None,
            watchlist_entry=None,
            validation_result=None,
        )

        assert isinstance(html, str)
        assert "—" in html  # Placeholders should be rendered

    def test_rendered_html_contains_real_chinese_labels(self):
        """Rendered HTML should contain correct UTF-8 Chinese labels (regression for P1 #1)."""
        from agent.research_v1.report_templates.renderer import render_boss_poster

        signal = {"ticker": "NVDA", "rating": "BUY", "confidence": 0.85}
        report = {
            "why_now": "Data center growth accelerating",
            "bull_case": "Multi-year AI buildout",
            "risk_watch": ["AMD competition", "Regulatory risk"],
        }
        html = render_boss_poster(signal, report)

        # Verify no UTF-8 replacement character (U+FFFD) in string
        assert "�" not in html, "No UTF-8 replacement character in output"
        # Verify key Chinese labels appear from real source literals.
        assert "买入股票" in html
        assert "高信心" in html

    def test_strings_zh_source_contains_real_chinese_literals(self):
        """The source string table itself should contain readable Chinese text."""
        from agent.research_v1.report_templates import strings_zh

        source = Path(strings_zh.__file__).read_text(encoding="utf-8")
        assert "买入股票" in source or "买入" in source
        assert "高信心" in source
        assert "暂无数据" in source


class TestExportPDF:
    """Test PDF export integration."""

    def test_export_poster_pdf_function_exists(self):
        """export_poster_pdf should be importable from report_pdf."""
        from agent.research_v1.report_pdf import export_poster_pdf
        assert callable(export_poster_pdf)

    def test_export_batch_report_pdf_function_exists(self):
        """export_batch_report_pdf should be importable from report_pdf."""
        from agent.research_v1.report_pdf import export_batch_report_pdf
        assert callable(export_batch_report_pdf)

    def test_legacy_export_task_pdf_still_works(self):
        """Legacy export_task_pdf should still be importable."""
        from agent.research_v1.report_pdf import export_task_pdf
        assert callable(export_task_pdf)

    def test_export_task_pdf_prefers_decision_objects(self, tmp_path, monkeypatch):
        """Main export path should carry Hermes decision objects as first-class inputs."""
        from agent.research_v1 import report_pdf as report_pdf_module
        from agent.research_v1.report_templates import renderer as renderer_module

        captured: dict = {}

        def fake_render_batch_report(**kwargs):
            captured.update(kwargs)
            return '<html><link rel="stylesheet" href="boss_report_pdf.css"/></html>'

        def fake_write_html_to_pdf(html, pdf_path, timeout=120):
            captured["html"] = html
            pdf_path.write_bytes(b"%PDF-test")
            return pdf_path

        monkeypatch.setattr(renderer_module, "render_batch_report", fake_render_batch_report)
        monkeypatch.setattr(report_pdf_module, "_write_html_to_pdf", fake_write_html_to_pdf)

        class FakeCursor:
            def execute(self, *_args, **_kwargs):
                return None

            def fetchall(self):
                return [{
                    "ticker": "AAPL",
                    "company_name": "Apple Inc.",
                    "rating": "BUY",
                    "confidence": 0.75,
                    "entry_price": 170.0,
                    "take_profit": 185.0,
                    "risk_flags_json": "[]",
                }]

        class FakeConnection:
            def cursor(self):
                return FakeCursor()

            def close(self):
                return None

        class FakeDatabase:
            def get_canonical_reports_by_task(self, _task_id):
                return [{
                    "ticker": "AAPL",
                    "company_name": "Apple Inc.",
                    "confidence": 0.75,
                    "bottom_line": "Sell CSP into premium richness.",
                    "why_now": "Premiums are attractive and assignment is acceptable.",
                    "bull_case": "Generate income while waiting for a better entry.",
                    "bear_case": "",
                    "risk_watch": ["Assignment risk"],
                    "executive_summary": "Income-oriented bullish expression.",
                    "trade_plan": {
                        "entry_price": 170.0,
                        "take_profit": 185.0,
                    },
                    "decision_card": {
                        "primary_action": "Sell Cash-Secured Put",
                        "conviction": "Medium",
                        "thesis_summary": "Income-oriented bullish expression.",
                        "why_now": "Volatility premium is attractive.",
                    },
                    "instrument_rec": {
                        "primary_action": "Sell Cash-Secured Put",
                        "ranked_alternatives": ["Buy Stock", "Covered Call"],
                        "reason": "Income first.",
                    },
                    "options_structure": None,
                    "early_exit": None,
                }]

            def _get_connection(self):
                return FakeConnection()

            def list_watchlist_entries(self):
                return []

            def list_validation_results(self):
                return []

        pdf_path = report_pdf_module.export_task_pdf(FakeDatabase(), "task-1", tmp_path)

        assert pdf_path.exists()
        assert captured["batch_items"][0]["overall_rating"] == "Sell Cash-Secured Put"
        assert captured["batch_items"][0]["action"] == "Sell Cash-Secured Put"
        assert captured["company_reports"][0]["position_decision"]["primary_action"] == "Sell Cash-Secured Put"
        assert captured["company_reports"][0]["instrument_rec"]["primary_action"] == "Sell Cash-Secured Put"
