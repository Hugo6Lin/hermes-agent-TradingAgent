"""
Phase 17 validation engine tests.

Tests the ValidationEngine module and its integration into the app pipeline.
"""

from __future__ import annotations

import pytest
from datetime import datetime
from unittest.mock import Mock

from agent.research_v1.validation_engine import (
    detect_regime,
    assess_historical_support,
    assess_environment_fit,
    infer_failure_mode,
    compute_validation_confidence,
    evaluate,
)
from agent.research_v1.contracts import ValidationResult


# ---------------------------------------------------------------------------
# Contract tests
# ---------------------------------------------------------------------------

class TestValidationResultContract:
    """ValidationResult must validate all enum and range constraints."""

    def test_valid_construction(self):
        """All valid fields produce a ValidationResult without error."""
        v = ValidationResult(
            ticker="AAPL",
            regime="trend_up",
            historical_support="strong",
            environment_fit="good",
            main_failure_mode="timing",
            validation_confidence=0.78,
            notes="Test",
        )
        assert v.ticker == "AAPL"
        assert v.regime == "trend_up"
        assert v.historical_support == "strong"
        assert v.environment_fit == "good"
        assert v.main_failure_mode == "timing"
        assert v.validation_confidence == 0.78
        assert v.notes == "Test"

    def test_rejects_invalid_regime(self):
        with pytest.raises(ValueError, match="regime"):
            ValidationResult(
                ticker="AAPL",
                regime="bull_market",  # invalid
                historical_support="strong",
                environment_fit="good",
                main_failure_mode="timing",
                validation_confidence=0.5,
            )

    def test_rejects_invalid_historical_support(self):
        with pytest.raises(ValueError, match="historical_support"):
            ValidationResult(
                ticker="AAPL",
                regime="trend_up",
                historical_support="very_strong",  # invalid
                environment_fit="good",
                main_failure_mode="timing",
                validation_confidence=0.5,
            )

    def test_rejects_invalid_environment_fit(self):
        with pytest.raises(ValueError, match="environment_fit"):
            ValidationResult(
                ticker="AAPL",
                regime="trend_up",
                historical_support="strong",
                environment_fit="excellent",  # invalid
                main_failure_mode="timing",
                validation_confidence=0.5,
            )

    def test_rejects_invalid_failure_mode(self):
        with pytest.raises(ValueError, match="main_failure_mode"):
            ValidationResult(
                ticker="AAPL",
                regime="trend_up",
                historical_support="strong",
                environment_fit="good",
                main_failure_mode="volatility",  # invalid
                validation_confidence=0.5,
            )

    def test_rejects_confidence_below_0(self):
        with pytest.raises(ValueError, match="validation_confidence"):
            ValidationResult(
                ticker="AAPL",
                regime="trend_up",
                historical_support="strong",
                environment_fit="good",
                main_failure_mode="timing",
                validation_confidence=-0.1,
            )

    def test_rejects_confidence_above_1(self):
        with pytest.raises(ValueError, match="validation_confidence"):
            ValidationResult(
                ticker="AAPL",
                regime="trend_up",
                historical_support="strong",
                environment_fit="good",
                main_failure_mode="timing",
                validation_confidence=1.2,
            )

    def test_notes_default_is_none(self):
        v = ValidationResult(
            ticker="AAPL",
            regime="trend_up",
            historical_support="strong",
            environment_fit="good",
            main_failure_mode="timing",
            validation_confidence=0.5,
        )
        assert v.notes is None


# ---------------------------------------------------------------------------
# Regime detection tests
# ---------------------------------------------------------------------------

class TestRegimeDetection:
    """detect_regime must classify candles into correct regime."""

    def _candles(self, closes, highs=None, lows=None):
        """Build simple candle dicts from close prices."""
        out = []
        for i, c in enumerate(closes):
            out.append({
                "close": c,
                "high": highs[i] if highs else c * 1.01,
                "low": lows[i] if lows else c * 0.99,
            })
        return out

    def test_trend_up_when_price_above_sma_and_low_vol(self):
        """Price 5% above 20-day SMA + low vol → trend_up."""
        ctx = {
            "candles": self._candles([100, 102, 104, 106, 108, 110]),
            "market_data": {"last_price": 115.0, "iv_percentile": 0.3},
        }
        assert detect_regime(ctx) == "trend_up"

    def test_range_bound_when_price_near_sma(self):
        """Price oscillating around SMA → range_bound."""
        ctx = {
            "candles": self._candles([100, 101, 99, 100.5, 99.5, 100]),
            "market_data": {"last_price": 100.3, "iv_percentile": 0.4},
        }
        assert detect_regime(ctx) == "range_bound"

    def test_high_volatility_when_realized_vol_high(self):
        """High daily ranges → high_volatility."""
        ctx = {
            "candles": self._candles(
                [100, 108, 96, 110, 98, 112],
                highs=[110, 114, 112, 116, 114, 118],
                lows=[90, 94, 92, 96, 94, 98],
            ),
            "market_data": {"last_price": 105.0, "iv_percentile": 0.5},
        }
        assert detect_regime(ctx) == "high_volatility"

    def test_risk_off_when_price_down_and_high_vol(self):
        """Price below SMA and high vol → risk_off."""
        ctx = {
            "candles": self._candles(
                [100, 95, 92, 88, 85, 82],
                highs=[102, 97, 94, 90, 87, 84],
                lows=[98, 93, 90, 86, 83, 80],
            ),
            "market_data": {"last_price": 80.0, "iv_percentile": 0.5},
        }
        assert detect_regime(ctx) == "risk_off"

    def test_unknown_when_insufficient_candles(self):
        """Fewer than 5 candles → unknown."""
        ctx = {
            "candles": self._candles([100, 102]),
            "market_data": {"last_price": 105.0, "iv_percentile": 0.4},
        }
        assert detect_regime(ctx) == "unknown"

    def test_high_iv_very_high_leads_to_high_volatility_regime(self):
        """Very high IV percentile (>=0.88) → high_volatility regardless of price."""
        ctx = {
            "candles": self._candles([100, 101, 102, 103, 104]),
            "market_data": {"last_price": 104.5, "iv_percentile": 0.90},
        }
        assert detect_regime(ctx) == "high_volatility"


# ---------------------------------------------------------------------------
# Historical support tests
# ---------------------------------------------------------------------------

class TestHistoricalSupport:
    """assess_historical_support must classify correctly."""

    def test_investable_plus_good_regime_plus_catalyst_yields_strong(self):
        thesis = Mock(quality_score=0.80, classification="Investable")
        valuation = {"upside_pct": 0.22}
        catalysts = {"clarity": 0.7}
        assert assess_historical_support(thesis, valuation, catalysts, "trend_up") == "strong"

    def test_watchlist_classification_yields_moderate(self):
        thesis = Mock(quality_score=0.55, classification="Watchlist")
        valuation = {"upside_pct": 0.12}
        catalysts = {"clarity": 0.5}
        assert assess_historical_support(thesis, valuation, catalysts, "trend_up") == "moderate"

    def test_no_trade_yields_weak(self):
        thesis = Mock(quality_score=0.20, classification="No Trade")
        valuation = {"upside_pct": 0.02}
        catalysts = {"clarity": 0.2}
        assert assess_historical_support(thesis, valuation, catalysts, "trend_up") == "weak"

    def test_high_volatility_regime_yields_weak_even_for_investable(self):
        thesis = Mock(quality_score=0.75, classification="Investable")
        valuation = {"upside_pct": 0.20}
        catalysts = {"clarity": 0.7}
        assert assess_historical_support(thesis, valuation, catalysts, "high_volatility") == "weak"

    def test_risk_off_regime_yields_weak(self):
        thesis = Mock(quality_score=0.70, classification="Investable")
        valuation = {"upside_pct": 0.18}
        catalysts = {"clarity": 0.6}
        assert assess_historical_support(thesis, valuation, catalysts, "risk_off") == "weak"

    def test_low_quality_yields_weak(self):
        thesis = Mock(quality_score=0.30, classification="Investable")
        valuation = {"upside_pct": 0.20}
        catalysts = {"clarity": 0.7}
        assert assess_historical_support(thesis, valuation, catalysts, "trend_up") == "weak"


# ---------------------------------------------------------------------------
# Failure mode tests
# ---------------------------------------------------------------------------

class TestFailureMode:
    """infer_failure_mode must map instrument + context to correct mode."""

    def test_buy_stock_yields_direction(self):
        assert infer_failure_mode("Buy Stock", "trend_up", 0.40, True) == "direction"

    def test_buy_call_with_high_iv_yields_iv(self):
        assert infer_failure_mode("Buy Call", "high_volatility", 0.82, True) == "iv"

    def test_buy_call_with_low_iv_yields_timing(self):
        assert infer_failure_mode("Buy Call", "trend_up", 0.40, True) == "timing"

    def test_bull_call_spread_yields_timing(self):
        assert infer_failure_mode("Bull Call Spread", "trend_up", 0.50, True) == "timing"

    def test_sell_csp_yields_direction(self):
        assert infer_failure_mode("Sell Cash-Secured Put", "trend_up", 0.50, True) == "direction"

    def test_covered_call_yields_timing(self):
        assert infer_failure_mode("Covered Call", "trend_up", 0.50, True) == "timing"

    def test_liquidity_problem_yields_liquidity_first(self):
        assert infer_failure_mode("Buy Call", "trend_up", 0.50, False) == "liquidity"


# ---------------------------------------------------------------------------
# Validation confidence tests
# ---------------------------------------------------------------------------

class TestValidationConfidence:
    """compute_validation_confidence must stay within [0.3, 0.95]."""

    def test_confidence_in_valid_range(self):
        thesis = Mock(quality_score=0.80, classification="Investable")
        for regime in ["trend_up", "range_bound", "high_volatility", "risk_off"]:
            for iv in [0.30, 0.60, 0.90]:
                for liq in [True, False]:
                    conf = compute_validation_confidence(
                        thesis, "Buy Call", regime, iv, liq, 0.7
                    )
                    assert 0.3 <= conf <= 0.95, f"Confidence {conf} out of range for {regime}/{iv}/{liq}"

    def test_strong_thesis_investable_in_trend_up_gives_high_confidence(self):
        thesis = Mock(quality_score=0.82, classification="Investable")
        conf = compute_validation_confidence(
            thesis, "Buy Stock", "trend_up", 0.40, True, 0.75
        )
        assert conf > 0.70

    def test_risk_off_high_iv_gives_lower_confidence(self):
        thesis = Mock(quality_score=0.82, classification="Investable")
        conf = compute_validation_confidence(
            thesis, "Buy Call", "risk_off", 0.90, True, 0.3
        )
        assert conf < 0.70

    def test_illiquid_reduces_confidence(self):
        thesis = Mock(quality_score=0.75, classification="Investable")
        conf_liq = compute_validation_confidence(
            thesis, "Buy Stock", "trend_up", 0.40, True, 0.7
        )
        conf_illiq = compute_validation_confidence(
            thesis, "Buy Stock", "trend_up", 0.40, False, 0.7
        )
        assert conf_illiq < conf_liq


# ---------------------------------------------------------------------------
# Full evaluate() entry point tests
# ---------------------------------------------------------------------------

class TestEvaluateEntryPoint:
    """evaluate() must return a valid ValidationResult."""

    def test_evaluate_returns_validation_result(self):
        thesis = Mock(quality_score=0.80, classification="Investable")
        ctx = {
            "candles": [
                {"close": 100, "high": 101, "low": 99},
                {"close": 102, "high": 103, "low": 101},
                {"close": 104, "high": 105, "low": 103},
                {"close": 106, "high": 107, "low": 105},
                {"close": 108, "high": 109, "low": 107},
            ],
            "market_data": {"last_price": 110.0, "iv_percentile": 0.40, "liquidity_ok": True},
        }
        result = evaluate(
            ticker="AAPL",
            thesis=thesis,
            instrument_action="Buy Call",
            ticker_context=ctx,
            valuation={"upside_pct": 0.22},
            catalysts={"clarity": 0.75},
        )
        assert isinstance(result, ValidationResult)
        assert result.ticker == "AAPL"
        assert result.regime == "trend_up"
        assert result.historical_support == "strong"
        assert result.environment_fit == "good"
        assert result.main_failure_mode == "timing"
        assert 0.3 <= result.validation_confidence <= 0.95
        assert result.notes is not None

    def test_evaluate_with_no_trade_classification(self):
        thesis = Mock(quality_score=0.20, classification="No Trade")
        ctx = {
            "candles": [{"close": 100, "high": 101, "low": 99}] * 5,
            "market_data": {"last_price": 98.0, "iv_percentile": 0.30, "liquidity_ok": True},
        }
        result = evaluate(
            ticker="RDBD",
            thesis=thesis,
            instrument_action="No Trade",
            ticker_context=ctx,
            valuation={"upside_pct": 0.02},
            catalysts={"clarity": 0.2},
        )
        assert result.historical_support == "weak"
        assert result.environment_fit == "good"  # low IV is good env
        assert result.main_failure_mode == "none"  # No Trade has no instrument


# ---------------------------------------------------------------------------
# App integration tests
# ---------------------------------------------------------------------------

class TestValidationAppIntegration:
    """TickerResearchResult must include validation field populated by the pipeline."""

    def test_app_result_includes_validation_field(self):
        """TickerResearchResult has a validation field."""
        from agent.research_v1.app import HermesResearchApp, TickerResearchResult
        import dataclasses

        # Verify the field exists on the class
        fields = {f.name for f in dataclasses.fields(TickerResearchResult)}
        assert "validation" in fields, f"validation field not found. Fields: {fields}"

    def test_validation_engine_is_instantiated_in_app(self):
        """HermesResearchApp.__init__ creates a ValidationEngine instance."""
        from agent.research_v1.app import HermesResearchApp
        from agent.research_v1.validation_engine import ValidationEngine

        app = HermesResearchApp(llm_client=None)
        assert hasattr(app, "_validation_engine")
        assert isinstance(app._validation_engine, ValidationEngine)


# ---------------------------------------------------------------------------
# Viewer surface test
# ---------------------------------------------------------------------------

class TestValidationViewerSurface:
    """Viewer snapshot must include validation_results."""

    def test_viewer_snapshot_includes_validation_results(self):
        """build_viewer_snapshot adds validation_results key to the snapshot."""
        from agent.research_v1.viewer import build_viewer_snapshot
        from agent.research_v1.data.database import ResearchDatabase
        from unittest.mock import patch

        db = ResearchDatabase(db_path=":memory:")
        db.initialize()
        db.initialize_research_core()

        # Mock legacy table methods that need tables we haven't created
        with patch.object(db, "list_recent_signals", return_value=[]):
            with patch.object(db, "list_positions", return_value=[]):
                with patch.object(db, "list_paper_trades", return_value=[]):
                    with patch.object(db, "list_recent_alerts", return_value=[]):
                        snapshot = build_viewer_snapshot(db)

        assert "validation_results" in snapshot, (
            "validation_results not found in viewer snapshot. "
            f"Keys: {list(snapshot.keys())}"
        )
        assert isinstance(snapshot["validation_results"], list)
