"""Tests for P52 Futu market visualization assets."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent.research_v1.market_visual_assets import (
    P52_SCHEMA_VERSION,
    build_market_visual_report,
    normalize_history_rows,
    render_heatmap_svg,
    render_kline_svg,
    run_market_visual_assets,
    validate_market_visual_inputs,
)


class FakeProvider:
    data_source = "fake_futu"
    price_adjustment = "adjusted"

    def __init__(self, histories=None, snapshots=None):
        self.histories = histories or {}
        self.snapshots = snapshots or []
        self.history_calls = []
        self.snapshot_calls = []

    def fetch_history(self, symbol, start_date, end_date):
        self.history_calls.append((symbol, start_date, end_date))
        return list(self.histories.get(symbol, []))

    def fetch_snapshot(self, symbols):
        self.snapshot_calls.append(list(symbols))
        return list(self.snapshots)


def _rows(closes):
    rows = []
    for idx, close in enumerate(closes, start=1):
        rows.append({
            "date": f"2026-04-{idx:02d}",
            "open": close - 0.5,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": 1000 + idx,
            "price_adjustment": "adjusted",
        })
    return rows


def test_validate_blocks_invalid_inputs():
    warnings = validate_market_visual_inputs(
        tickers=[],
        as_of_date="not-a-date",
        history_days=5,
        heatmap_metric="bad_metric",
        port=70000,
    )
    assert "tickers_required" in warnings
    assert "invalid_date_format" in warnings
    assert "history_days_minimum_20" in warnings
    assert "invalid_heatmap_metric:bad_metric" in warnings
    assert "invalid_port" in warnings


def test_normalize_history_rows_sorts_dedupes_and_warns():
    rows, warnings = normalize_history_rows("ZETA", [
        {"date": "2026-04-02", "open": 11, "high": 12, "low": 10, "close": 11},
        {"date": "2026-04-01", "open": 10, "high": 11, "low": 9, "close": 10},
        {"date": "2026-04-02", "open": 12, "high": 13, "low": 11, "close": 12},
        {"date": "2026-04-03", "open": 13, "high": 14, "low": 12},
    ])
    assert [row["date"] for row in rows] == ["2026-04-01", "2026-04-02"]
    assert rows[-1]["close"] == 12.0
    assert "duplicate_history_date:ZETA:2026-04-02" in warnings


def test_build_report_with_provider_creates_ready_metrics():
    provider = FakeProvider(histories={"ZETA": _rows([10 + i for i in range(60)])})
    report = build_market_visual_report(
        tickers=["ZETA"],
        as_of_date="2026-05-01",
        history_days=60,
        heatmap_metric="return_20d",
        provider=provider,
        live=True,
    )
    assert report["schema_version"] == P52_SCHEMA_VERSION
    assert report["status"] == "visual_assets_ready"
    assert report["ticker_visuals"][0]["data_status"] == "visual_ready"
    assert report["ticker_visuals"][0]["metrics"]["return_20d"] > 0
    assert provider.history_calls


def test_offline_runtime_does_not_need_provider_and_writes_limited_artifacts(tmp_path: Path):
    result = run_market_visual_assets(
        tickers=["ZETA"],
        as_of_date="2026-05-01",
        output_root=tmp_path,
        history_days=60,
        live=False,
    )
    assert result["status"] == "visual_assets_missing_data"
    assert (tmp_path / "2026-05-01" / "p52_market_visual_snapshot.json").exists()
    assert result["provider_status"] == "provider_not_used_offline"


def test_svg_renderers_escape_labels_and_avoid_forbidden_terms():
    visual = {
        "ticker": "ZETA<script>",
        "data_status": "visual_ready",
        "history": _rows([10 + i for i in range(30)]),
        "metrics": {"return_1d": 0.01, "return_5d": 0.04, "return_20d": 0.12, "drawdown_20d": -0.02},
    }
    kline = render_kline_svg(visual)
    heatmap = render_heatmap_svg([visual], metric="return_20d")
    assert "<script>" not in kline
    assert "&lt;script&gt;" in kline
    for term in ["buy this now", "place order", "submit order"]:
        assert term not in kline.lower()
        assert term not in heatmap.lower()


def test_middle_row_revision_changes_source_hash():
    base = _rows([10 + i for i in range(60)])
    revised = _rows([10 + i for i in range(60)])
    revised[30]["close"] = revised[30]["close"] + 5
    first = build_market_visual_report(
        tickers=["ZETA"],
        as_of_date="2026-05-01",
        history_days=60,
        heatmap_metric="return_20d",
        provider=FakeProvider(histories={"ZETA": base}),
        live=True,
    )
    second = build_market_visual_report(
        tickers=["ZETA"],
        as_of_date="2026-05-01",
        history_days=60,
        heatmap_metric="return_20d",
        provider=FakeProvider(histories={"ZETA": revised}),
        live=True,
    )
    assert first["source_hash"] != second["source_hash"]


def test_partial_missing_history_yields_limited_status():
    provider = FakeProvider(histories={"ZETA": _rows([10 + i for i in range(60)]), "NVDA": []})
    report = build_market_visual_report(
        tickers=["ZETA", "NVDA"],
        as_of_date="2026-05-01",
        history_days=60,
        heatmap_metric="return_20d",
        provider=provider,
        live=True,
    )
    assert report["status"] == "visual_assets_limited"
    statuses = {item["ticker"]: item["data_status"] for item in report["ticker_visuals"]}
    assert statuses["ZETA"] == "visual_ready"
    assert statuses["NVDA"] == "visual_missing_data"


def test_market_visual_report_persistence_is_idempotent(tmp_path: Path):
    from agent.research_v1.data.database import ResearchDatabase

    db = ResearchDatabase(str(tmp_path / "research.db"))
    db.initialize()
    report = build_market_visual_report(
        tickers=["ZETA"],
        as_of_date="2026-05-01",
        history_days=60,
        heatmap_metric="return_20d",
        provider=FakeProvider(histories={"ZETA": _rows([10 + i for i in range(60)])}),
        live=True,
    )
    first = db.save_market_visual_asset_report(report)
    second = db.save_market_visual_asset_report(report)
    rows = db.list_market_visual_asset_reports_as_of("2026-05-01", tickers=["ZETA"])
    assert first == second
    assert len(rows) == 1
    assert rows[0]["source_hash"] == report["source_hash"]


def test_market_visual_same_day_revision_appends_new_row(tmp_path: Path):
    from agent.research_v1.data.database import ResearchDatabase

    db = ResearchDatabase(str(tmp_path / "research.db"))
    db.initialize()
    base = build_market_visual_report(
        tickers=["ZETA"],
        as_of_date="2026-05-01",
        history_days=60,
        heatmap_metric="return_20d",
        provider=FakeProvider(histories={"ZETA": _rows([10 + i for i in range(60)])}),
        live=True,
    )
    revised_rows = _rows([10 + i for i in range(60)])
    revised_rows[30]["close"] += 5
    revised = build_market_visual_report(
        tickers=["ZETA"],
        as_of_date="2026-05-01",
        history_days=60,
        heatmap_metric="return_20d",
        provider=FakeProvider(histories={"ZETA": revised_rows}),
        live=True,
    )
    db.save_market_visual_asset_report(base)
    db.save_market_visual_asset_report(revised)
    rows = db.list_market_visual_asset_reports_as_of("2026-05-01", tickers=["ZETA"])
    assert len(rows) == 2
    assert {row["source_hash"] for row in rows} == {base["source_hash"], revised["source_hash"]}
