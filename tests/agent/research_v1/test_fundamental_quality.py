"""Tests for P38 fundamental quality engine."""

from __future__ import annotations

from pathlib import Path

from agent.research_v1.fundamental_quality import (
    P38_SCHEMA_VERSION,
    build_fundamental_quality_report,
    compute_source_hash,
    normalize_financial_rows,
)


def _row(
    period_end: str,
    source_date: str,
    revenue: float = 100.0,
    gross_profit: float = 50.0,
    operating_income: float = 25.0,
    net_income: float = 20.0,
    cfo: float = 24.0,
    capex: float = -5.0,
    total_debt: float = 20.0,
    cash: float = 10.0,
    equity: float = 80.0,
    shares: float = 10.0,
    eps: float = 2.0,
    ebit: float = 25.0,
) -> dict:
    return {
        "period_end": period_end,
        "filing_date": source_date,
        "source_date": source_date,
        "revenue": revenue,
        "gross_profit": gross_profit,
        "operating_income": operating_income,
        "net_income": net_income,
        "cfo": cfo,
        "capex": capex,
        "free_cash_flow": cfo + capex,
        "total_debt": total_debt,
        "cash_and_equivalents": cash,
        "shareholders_equity": equity,
        "shares_outstanding": shares,
        "eps": eps,
        "ebit": ebit,
        "current_assets": 50.0,
        "current_liabilities": 25.0,
    }


def _rows() -> list[dict]:
    return [
        _row("2025-03-31", "2025-05-01", revenue=100.0, gross_profit=48.0, operating_income=22.0, net_income=18.0, cfo=22.0, eps=1.8),
        _row("2025-06-30", "2025-08-01", revenue=110.0, gross_profit=54.0, operating_income=26.0, net_income=21.0, cfo=25.0, eps=2.1),
        _row("2025-09-30", "2025-11-01", revenue=120.0, gross_profit=60.0, operating_income=30.0, net_income=24.0, cfo=29.0, eps=2.4),
        _row("2025-12-31", "2026-02-01", revenue=132.0, gross_profit=67.0, operating_income=34.0, net_income=27.0, cfo=33.0, eps=2.7),
        _row("2026-03-31", "2026-04-25", revenue=145.0, gross_profit=75.0, operating_income=39.0, net_income=31.0, cfo=38.0, eps=3.1),
    ]


# ── P38-A metric and scoring tests ──────────────────────────────────────────

def test_normalized_rows_compute_latest_margins_roic_leverage_and_fcf():
    normalized = normalize_financial_rows(_rows(), as_of_date="2026-04-30")

    assert len(normalized.usable_rows) == 5
    latest = normalized.usable_rows[-1]
    assert latest["gross_margin"] > 0
    assert latest["operating_margin"] > 0
    assert latest["net_margin"] > 0
    assert latest["roic"] > 0
    assert latest["debt_to_equity"] >= 0
    assert latest["free_cash_flow"] == latest["cfo"] + latest["capex"]


def test_report_computes_growth_scores_and_compounder_label():
    report = build_fundamental_quality_report({
        "ticker": "AAPL",
        "sector": "technology",
        "currency": "USD",
        "rows": _rows(),
    }, as_of_date="2026-04-30")

    assert report["schema_version"] == P38_SCHEMA_VERSION
    assert report["ticker"] == "AAPL"
    assert report["overall_quality_score"] >= 0.65
    assert report["quality_label"] in {"compounder_quality", "solid_quality"}
    assert report["dimension_scores"]["profitability_score"] > 0.5
    assert report["trend_metrics"]["revenue_growth_yoy"] is not None


def test_future_source_rows_are_ignored_and_warned():
    rows = _rows() + [_row("2026-06-30", "2026-08-01", revenue=999.0)]
    report = build_fundamental_quality_report({
        "ticker": "AAPL",
        "sector": "technology",
        "currency": "USD",
        "rows": rows,
    }, as_of_date="2026-04-30")

    assert report["ignored_future_row_count"] == 1
    assert "future_source_date_ignored" in report["warnings"]
    assert report["latest_metrics"]["revenue"] != 999.0


def test_blocked_missing_fundamentals_when_fewer_than_two_usable_rows():
    report = build_fundamental_quality_report({
        "ticker": "AAPL",
        "sector": "technology",
        "currency": "USD",
        "rows": [_row("2025-03-31", "2025-05-01")],
    }, as_of_date="2026-04-30")

    assert report["status"] == "blocked_missing_fundamentals"
    assert report["quality_label"] == "blocked_missing_fundamentals"


def test_degraded_insufficient_history_with_two_or_three_rows():
    report = build_fundamental_quality_report({
        "ticker": "AAPL",
        "sector": "technology",
        "currency": "USD",
        "rows": _rows()[:3],
    }, as_of_date="2026-04-30")

    assert report["status"] == "degraded_insufficient_history"
    assert "insufficient_history" in report["red_flags"]


def test_high_dilution_leverage_and_negative_fcf_trigger_flags():
    rows = _rows()
    rows[-1]["shares_outstanding"] = 20.0
    rows[-1]["total_debt"] = 500.0
    rows[-1]["cfo"] = -10.0
    rows[-1]["capex"] = -5.0
    rows[-1].pop("free_cash_flow", None)

    report = build_fundamental_quality_report({
        "ticker": "DILUTE",
        "sector": "technology",
        "currency": "USD",
        "rows": rows,
    }, as_of_date="2026-04-30")

    assert "share_dilution_high" in report["red_flags"]
    assert "debt_to_equity_high" in report["red_flags"]
    assert "negative_fcf" in report["red_flags"]
    assert report["overall_quality_score"] < 0.8


def test_source_hash_changes_on_middle_row_revision():
    base = {"ticker": "AAPL", "sector": "technology", "currency": "USD", "rows": _rows()}
    revised = {"ticker": "AAPL", "sector": "technology", "currency": "USD", "rows": [dict(r) for r in _rows()]}
    revised["rows"][2]["revenue"] = 777.0

    assert compute_source_hash(base, "2026-04-30") != compute_source_hash(revised, "2026-04-30")
