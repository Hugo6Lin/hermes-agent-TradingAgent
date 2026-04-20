"""Tests for P3 signal-quality and provider-layer upgrades."""

from datetime import datetime, timedelta, timezone

from unittest.mock import Mock

from agent.research_v1.grading import GradingAgent
from agent.research_v1.analyst_weighting import AnalystWeightEngine
from agent.research_v1.data.providers import (
    FallbackMarketDataProvider,
    MarketDataProvider,
)
from agent.research_v1.data.quality import DataQualityValidator
from agent.research_v1.signal_quality import (
    detect_evidence_conflicts,
    rank_signals_with_portfolio_context,
)


class _FakeProvider(MarketDataProvider):
    def __init__(self, rows):
        self.rows = rows

    def fetch_history(self, symbol: str, start_date: str, end_date: str) -> list[dict]:
        return list(self.rows)


def test_data_quality_validator_skips_rows_with_missing_fields():
    """Drop rows with missing required fields and keep valid points."""
    validator = DataQualityValidator()
    cleaned, issues = validator.validate_price_points([
        {"day": 0, "date": "2026-04-01", "close": 100.0},
        {"day": 1, "date": "2026-04-02"},
        {"day": 2, "date": "2026-04-03", "close": 102.0},
    ])

    assert len(cleaned) == 2
    assert any(issue["type"] == "missing_field" for issue in issues)


def test_data_quality_validator_reports_stale_series():
    """Mark stale data when latest point is beyond freshness threshold."""
    validator = DataQualityValidator(max_staleness_days=3)
    stale_date = (datetime.now(timezone.utc) - timedelta(days=10)).strftime("%Y-%m-%d")

    fresh, issue = validator.check_freshness([
        {"day": 0, "date": stale_date, "close": 100.0},
    ])

    assert fresh is False
    assert issue["type"] == "stale_data"


def test_fallback_provider_uses_secondary_source_when_primary_invalid():
    """Fallback to secondary provider when primary returns unusable rows."""
    fresh_day_1 = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
    fresh_day_2 = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    primary = _FakeProvider([{"date": "2026-04-01"}])  # missing close/day
    secondary = _FakeProvider([
        {"day": 0, "date": fresh_day_1, "close": 100.0},
        {"day": 1, "date": fresh_day_2, "close": 101.0},
    ])
    provider = FallbackMarketDataProvider(
        providers=[primary, secondary],
        validator=DataQualityValidator(),
    )

    rows = provider.fetch_history("AAPL", "2026-04-01", "2026-04-10")
    assert len(rows) == 2
    assert rows[0]["close"] == 100.0


def test_fallback_provider_skips_stale_primary_series():
    """Fallback to secondary provider when primary data is stale."""
    stale_date = (datetime.now() - timedelta(days=12)).strftime("%Y-%m-%d")
    fresh_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    primary = _FakeProvider([
        {"day": 0, "date": stale_date, "close": 100.0},
    ])
    secondary = _FakeProvider([
        {"day": 0, "date": fresh_date, "close": 101.0},
    ])
    provider = FallbackMarketDataProvider(
        providers=[primary, secondary],
        validator=DataQualityValidator(max_staleness_days=3),
    )

    rows = provider.fetch_history("AAPL", "2026-04-01", "2026-04-10")
    assert rows[0]["close"] == 101.0


def test_rank_signals_with_portfolio_context_penalizes_sector_overlap():
    """Penalize same-sector signals when current exposure is concentrated."""
    ranked = rank_signals_with_portfolio_context(
        signals=[
            {"symbol": "AAPL", "priority_score": 85.0, "sector": "Technology"},
            {"symbol": "JPM", "priority_score": 80.0, "sector": "Financials"},
        ],
        open_positions=[
            {"symbol": "MSFT", "sector": "Technology", "status": "open"},
            {"symbol": "NVDA", "sector": "Technology", "status": "open"},
        ],
    )

    assert ranked[0]["symbol"] == "JPM"
    assert ranked[0]["adjusted_priority"] > ranked[1]["adjusted_priority"]


def test_detect_evidence_conflicts_flags_cross_source_price_mismatch():
    """Detect conflicts and emit confidence penalty when sources disagree."""
    result = detect_evidence_conflicts(
        source_fields={
            "yahoo": {"price": 100.0, "volume": 10_000},
            "backup": {"price": 108.0, "volume": 10_100},
        },
        analyst_views={"technical_summary": {"signal": "buy"}},
    )

    assert result["has_conflict"] is True
    assert result["confidence_penalty"] > 0
    assert any(conflict["field"] == "price" for conflict in result["conflicts"])


def test_analyst_weight_engine_rebalances_toward_higher_usefulness():
    """Reweight analyst contributions from historical usefulness metrics."""
    engine = AnalystWeightEngine(
        base_weights={"fundamental": 0.4, "technical": 0.3, "macro": 0.3}
    )
    weights = engine.rebalance(
        usefulness={
            "fundamental": 0.9,
            "technical": 0.2,
            "macro": 0.6,
        }
    )

    assert round(sum(weights.values()), 6) == 1.0
    assert weights["fundamental"] > weights["technical"]
    assert weights["macro"] > 0


def test_grading_uses_dynamic_weights_and_conflict_penalty():
    """Apply dynamic weights and evidence penalty to signal confidence."""
    grader = GradingAgent(
        llm_client=Mock(),
        dynamic_weights={"fundamental": 0.7, "technical": 0.2, "macro": 0.1},
    )
    result = grader.grade(
        research_decision={
            "symbol": "AAPL",
            "market_data": {"price": 100.0},
            "fundamentals_summary": {"verdict": "buy", "confidence": 0.8},
            "technical_summary": {"signal": "buy"},
            "industry_summary": {"trend": "bullish"},
            "macro_data": {"trend": "bullish"},
            "evidence_conflict": {"confidence_penalty": 0.1},
        },
        analyst_reports={},
    )

    assert round(grader.fundamental_weight, 2) == 0.7
    assert result["signal"]["confidence"] < round(result["composite_score"] / 100, 4)
