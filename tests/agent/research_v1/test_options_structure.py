"""
Phase 15 Options Structure tests.

Tests the OptionsDecisionEngine for expiry/strike selection and
OptionsStructure contract validation.
"""

from __future__ import annotations

import pytest
from agent.research_v1.contracts import OptionContract, OptionsStructure
from agent.research_v1.options_decision import OptionsDecisionEngine


# ---------------------------------------------------------------------------
# Contract validation tests
# ---------------------------------------------------------------------------

class TestOptionsStructureContract:
    def test_requires_instrument_action(self):
        """OptionsStructure raises if instrument_action is empty."""
        with pytest.raises(ValueError, match="instrument_action"):
            OptionsStructure(
                ticker="AAPL",
                instrument_action="",  # empty
                primary_contract=OptionContract(
                    expiry_months=6, strike=150.0, option_type="call",
                    delta_estimate=0.55, position_type="long",
                ),
                conservative_alternative=None,
                higher_upside_alternative=None,
                target_path_summary="3m target path",
                early_exit_summary="Exit at +50%",
            )

    def test_requires_valid_option_type(self):
        """OptionContract.option_type must be 'call' or 'put'."""
        with pytest.raises(ValueError, match="'call' or 'put'"):
            OptionContract(
                expiry_months=6, strike=150.0,
                option_type="futures",  # invalid
                delta_estimate=0.55,
                position_type="long",
            )

    def test_accepts_valid_call_contract(self):
        """OptionContract accepts valid call parameters."""
        c = OptionContract(
            expiry_months=6, strike=150.0,
            option_type="call",
            delta_estimate=0.55,
            position_type="long",
        )
        assert c.option_type == "call"
        assert c.position_type == "long"

    def test_accepts_valid_put_contract(self):
        """OptionContract accepts valid put parameters."""
        c = OptionContract(
            expiry_months=3, strike=145.0,
            option_type="put",
            delta_estimate=0.42,
            position_type="short",
        )
        assert c.option_type == "put"
        assert c.position_type == "short"


# ---------------------------------------------------------------------------
# Expiry selection tests
# ---------------------------------------------------------------------------

class TestExpirySelection:
    """Expiry selection must include safety buffer — never minimum window."""

    def test_selects_buffered_expiry_not_minimum(self):
        """With target=3m and available [3,6,9], selects 6m (not 3m)."""
        engine = OptionsDecisionEngine()
        result = engine.decide(
            instrument_action="Buy Call",
            current_price=50.0,
            target_price=60.0,
            thesis_months=3,
            option_chain=[
                {"expiry": "2027-07-19", "strike": 50, "option_type": "call", "delta": 0.55},
                {"expiry": "2027-10-15", "strike": 50, "option_type": "call", "delta": 0.52},
                {"expiry": "2027-01-16", "strike": 50, "option_type": "call", "delta": 0.48},
            ],
            iv_percentile=0.50,
        )
        assert result.primary_contract.expiry_months >= 5  # at least target+2

    def test_fallback_when_no_expiries(self):
        """With no option chain, uses thesis_months + 3 as default expiry."""
        engine = OptionsDecisionEngine()
        result = engine.decide(
            instrument_action="Buy Call",
            current_price=50.0,
            target_price=60.0,
            thesis_months=6,
            option_chain=[],
            iv_percentile=0.50,
        )
        assert result.primary_contract.expiry_months == 9  # 6 + 3 buffer


# ---------------------------------------------------------------------------
# Strike selection tests
# ---------------------------------------------------------------------------

class TestStrikeSelection:
    """Strike selection targets delta 0.35–0.70, avoids far OTM."""

    def test_avoids_far_otm_as_default(self):
        """Far OTM strike (delta < 0.20) must not be the primary recommendation."""
        engine = OptionsDecisionEngine()
        result = engine.decide(
            instrument_action="Buy Call",
            current_price=50.0,
            target_price=60.0,
            thesis_months=6,
            option_chain=[
                {"expiry": "2027-10-15", "strike": 30.0, "option_type": "call", "delta": 0.95},  # deep ITM
                {"expiry": "2027-10-15", "strike": 45.0, "option_type": "call", "delta": 0.70},  # ITM
                {"expiry": "2027-10-15", "strike": 50.0, "option_type": "call", "delta": 0.55},  # ATM
                {"expiry": "2027-10-15", "strike": 55.0, "option_type": "call", "delta": 0.40},  # OTM
                {"expiry": "2027-10-15", "strike": 70.0, "option_type": "call", "delta": 0.12},  # far OTM — should NOT be primary
            ],
            iv_percentile=0.50,
        )
        assert result.primary_contract.delta_estimate >= 0.30
        assert result.primary_contract.strike != 70.0

    def test_prefers_moderate_itm_over_atm_for_long_call(self):
        """Long call prefers slight ITM (delta ~0.45–0.65) over pure ATM."""
        engine = OptionsDecisionEngine()
        result = engine.decide(
            instrument_action="Buy Call",
            current_price=50.0,
            target_price=60.0,
            thesis_months=6,
            option_chain=[
                {"expiry": "2027-10-15", "strike": 48.0, "option_type": "call", "delta": 0.62},
                {"expiry": "2027-10-15", "strike": 50.0, "option_type": "call", "delta": 0.55},
                {"expiry": "2027-10-15", "strike": 52.0, "option_type": "call", "delta": 0.48},
            ],
            iv_percentile=0.50,
        )
        # Slight ITM (48) preferred over ATM (50)
        assert result.primary_contract.strike == 48.0


# ---------------------------------------------------------------------------
# Instrument action routing tests
# ---------------------------------------------------------------------------

class TestInstrumentRouting:
    def test_routes_buy_call(self):
        """Buy Call routes to _buy_call and returns call option."""
        engine = OptionsDecisionEngine()
        result = engine.decide(
            instrument_action="Buy Call",
            current_price=50.0,
            target_price=60.0,
            thesis_months=6,
            option_chain=[
                {"expiry": "2027-10-15", "strike": 50.0, "option_type": "call", "delta": 0.55},
            ],
            iv_percentile=0.50,
        )
        assert result.instrument_action == "Buy Call"
        assert result.primary_contract.option_type == "call"
        assert result.primary_contract.position_type == "long"

    def test_routes_bull_call_spread(self):
        """Bull Call Spread produces spread target summary."""
        engine = OptionsDecisionEngine()
        result = engine.decide(
            instrument_action="Bull Call Spread",
            current_price=50.0,
            target_price=60.0,
            thesis_months=6,
            option_chain=[
                {"expiry": "2027-10-15", "strike": 48.0, "option_type": "call", "delta": 0.62},
                {"expiry": "2027-10-15", "strike": 55.0, "option_type": "call", "delta": 0.38},
            ],
            iv_percentile=0.50,
        )
        assert result.instrument_action == "Bull Call Spread"
        assert "spread" in result.target_path_summary.lower()
        assert result.primary_contract.option_type == "call"

    def test_routes_sell_csp(self):
        """Sell Cash-Secured Put returns put option, short position."""
        engine = OptionsDecisionEngine()
        result = engine.decide(
            instrument_action="Sell Cash-Secured Put",
            current_price=50.0,
            target_price=45.0,
            thesis_months=6,
            option_chain=[
                {"expiry": "2027-10-15", "strike": 50.0, "option_type": "put", "delta": 0.55},
            ],
            iv_percentile=0.50,
        )
        assert result.instrument_action == "Sell Cash-Secured Put"
        assert result.primary_contract.option_type == "put"
        assert result.primary_contract.position_type == "short"

    def test_routes_covered_call(self):
        """Covered Call returns short call position."""
        engine = OptionsDecisionEngine()
        result = engine.decide(
            instrument_action="Covered Call",
            current_price=50.0,
            target_price=55.0,
            thesis_months=3,
            option_chain=[
                {"expiry": "2027-07-19", "strike": 52.0, "option_type": "call", "delta": 0.52},
            ],
            iv_percentile=0.55,
        )
        assert result.instrument_action == "Covered Call"
        assert result.primary_contract.option_type == "call"
        assert result.primary_contract.position_type == "short"

    def test_raises_on_unknown_instrument(self):
        """Unknown instrument_action raises ValueError."""
        engine = OptionsDecisionEngine()
        with pytest.raises(ValueError):
            engine.decide(
                instrument_action="Short Straddle",  # not in allowed set
                current_price=50.0,
                target_price=60.0,
                thesis_months=6,
                option_chain=[],
                iv_percentile=0.50,
            )


# ---------------------------------------------------------------------------
# Output completeness tests
# ---------------------------------------------------------------------------

class TestOptionsStructureOutput:
    def test_buy_call_includes_all_required_fields(self):
        """OptionsStructure for Buy Call has target_path and early_exit summaries."""
        engine = OptionsDecisionEngine()
        result = engine.decide(
            instrument_action="Buy Call",
            current_price=50.0,
            target_price=60.0,
            thesis_months=6,
            option_chain=[
                {"expiry": "2027-10-15", "strike": 48.0, "option_type": "call", "delta": 0.62},  # ITM
                {"expiry": "2027-10-15", "strike": 50.0, "option_type": "call", "delta": 0.55},  # ATM
                {"expiry": "2027-10-15", "strike": 52.0, "option_type": "call", "delta": 0.48},  # OTM
            ],
            iv_percentile=0.50,
        )
        assert result.target_path_summary != ""
        assert len(result.target_path_summary) > 10
        assert result.early_exit_summary != ""
        assert len(result.early_exit_summary) > 10
        assert result.conservative_alternative is not None

    def test_early_exit_zones_defined_for_all_instruments(self):
        """Early exit summary mentions all three zones for every instrument."""
        engine = OptionsDecisionEngine()
        for action in ["Buy Call", "Bull Call Spread", "Sell Cash-Secured Put", "Covered Call"]:
            option_t = "call" if "Call" in action else "put"
            chain = [
                {"expiry": "2027-10-15", "strike": 48.0, "option_type": option_t, "delta": 0.62},
                {"expiry": "2027-10-15", "strike": 50.0, "option_type": option_t, "delta": 0.55},
                {"expiry": "2027-10-15", "strike": 52.0, "option_type": option_t, "delta": 0.48},
            ]
            result = engine.decide(
                instrument_action=action,
                current_price=50.0,
                target_price=60.0,
                thesis_months=6,
                option_chain=chain,
                iv_percentile=0.55,
            )
            assert "[1]" in result.early_exit_summary  # Zone 1 marker must be present
            assert "exit" in result.early_exit_summary.lower()
