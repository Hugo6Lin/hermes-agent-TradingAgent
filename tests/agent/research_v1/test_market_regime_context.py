"""Tests for P37 market regime context."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from agent.research_v1.market_regime_context import (
    DEFAULT_MARKET_PROXIES,
    P37_ARTIFACT_DISCLAIMER,
    build_market_regime_snapshot,
    compute_data_source_hash,
    compute_proxy_metrics,
    normalize_history_rows,
    write_market_regime_artifacts,
)


class FakeMarketProvider:
    data_source = "fake_market_provider"
    price_adjustment = "adjusted"

    def __init__(self, histories: dict[str, list[dict]]):
        self.histories = histories
        self.calls: list[tuple[str, date, date]] = []

    def fetch_history(self, symbol, start_date, end_date):
        self.calls.append((symbol, start_date, end_date))
        return self.histories.get(symbol, [])


def _history(start_price: float, days: int = 90, daily_step: float = 1.0) -> list[dict]:
    start = date(2026, 1, 1)
    rows = []
    for idx in range(days):
        close = start_price + idx * daily_step
        rows.append({
            "date": str(start + timedelta(days=idx)),
            "open": close - 0.25,
            "high": close + 0.50,
            "low": close - 0.50,
            "close": close,
            "volume": 1_000_000 + idx,
            "price_adjustment": "adjusted",
        })
    return rows


def _histories(step: float = 1.0) -> dict[str, list[dict]]:
    return {symbol: _history(100.0 + i, daily_step=step) for i, symbol in enumerate(DEFAULT_MARKET_PROXIES)}


def test_proxy_metrics_compute_returns_vol_drawdown_and_sma_flags():
    rows = normalize_history_rows(_history(100.0, days=90, daily_step=1.0))
    metrics = compute_proxy_metrics("SPY", "us_equity_large_cap", rows)

    assert metrics["symbol"] == "SPY"
    assert metrics["return_1d"] > 0
    assert metrics["return_5d"] > 0
    assert metrics["return_20d"] > 0
    assert metrics["realized_vol_20d"] >= 0
    assert metrics["drawdown_20d"] <= 0
    assert metrics["above_sma_20"] is True
    assert metrics["above_sma_50"] is True


def test_data_source_hash_is_deterministic():
    histories = _histories()
    first = compute_data_source_hash(histories)
    second = compute_data_source_hash(dict(reversed(list(histories.items()))))

    assert first == second


def test_risk_on_broad_classification_from_positive_broad_market():
    provider = FakeMarketProvider(_histories(step=1.0))
    snapshot = build_market_regime_snapshot(provider, as_of_date=date(2026, 4, 30))

    assert snapshot["regime_label"] == "risk_on_broad"
    assert snapshot["coverage_ratio"] == 1.0
    assert snapshot["confidence"] > 0.5
    assert snapshot["classification_reasons"]


def test_degraded_when_required_inputs_missing():
    histories = _histories(step=1.0)
    histories["SPY"] = []
    provider = FakeMarketProvider(histories)

    snapshot = build_market_regime_snapshot(provider, as_of_date=date(2026, 4, 30))

    assert snapshot["status"] == "degraded_missing_inputs"
    assert snapshot["regime_label"] == "degraded_unknown"
    assert "SPY" in snapshot["missing_symbols"]


def test_sector_rotation_ranks_relative_strength_against_spy():
    histories = _histories(step=0.2)
    histories["XLK"] = _history(100.0, daily_step=2.0)
    histories["XLP"] = _history(100.0, daily_step=-0.1)
    provider = FakeMarketProvider(histories)

    snapshot = build_market_regime_snapshot(provider, as_of_date=date(2026, 4, 30))

    ranked = snapshot["sector_rotation"]["ranked_sectors"]
    assert ranked[0]["symbol"] == "XLK"
    assert ranked[-1]["symbol"] == "XLP"


# ── P37-B persistence and artifact tests ─────────────────────────────────────

from agent.research_v1.data.database import ResearchDatabase


def _db(tmp_path: Path) -> ResearchDatabase:
    db = ResearchDatabase(str(tmp_path / "research.db"))
    db.initialize()
    db.initialize_market_regime_schema()
    return db


def test_market_regime_snapshot_persistence_is_idempotent(tmp_path: Path):
    db = _db(tmp_path)
    snapshot = build_market_regime_snapshot(FakeMarketProvider(_histories()), as_of_date=date(2026, 4, 30))

    first = db.save_market_regime_snapshot(snapshot)
    second = db.save_market_regime_snapshot(snapshot)
    rows = db.list_market_regime_snapshots(as_of_date="2026-04-30")

    assert first == second
    assert len(rows) == 1


def test_revised_market_regime_hash_appends(tmp_path: Path):
    db = _db(tmp_path)
    first_snapshot = build_market_regime_snapshot(FakeMarketProvider(_histories(step=1.0)), as_of_date=date(2026, 4, 30))
    second_snapshot = build_market_regime_snapshot(FakeMarketProvider(_histories(step=2.0)), as_of_date=date(2026, 4, 30))

    first = db.save_market_regime_snapshot(first_snapshot)
    second = db.save_market_regime_snapshot(second_snapshot)
    rows = db.list_market_regime_snapshots(as_of_date="2026-04-30")

    assert first != second
    assert len(rows) == 2


def test_market_regime_artifact_writer_outputs_json_and_markdown(tmp_path: Path):
    snapshot = build_market_regime_snapshot(FakeMarketProvider(_histories()), as_of_date=date(2026, 4, 30))

    paths = write_market_regime_artifacts(snapshot, tmp_path / "output" / "governance" / "2026-04-30")

    assert paths["json"].name == "p37_market_regime_snapshot.json"
    assert paths["md"].name == "p37_market_regime_snapshot.md"
    assert paths["json"].exists()
    assert paths["md"].exists()
    assert "P37 is market-context evidence only" in paths["md"].read_text()


# ── P37-C hard-boundary test ─────────────────────────────────────────────────

def test_p37_hard_boundaries_are_explicit():
    from agent.research_v1 import market_regime_context as p37

    forbidden_names = {
        "broker",
        "order",
        "train_model",
        "scheduler",
        "notification",
        "final_judge",
        "run_governance_runtime",
        "run_recommendation_outcome_tracking",
    }

    assert not (forbidden_names & set(p37.__dict__))
    assert "does not approve production" in p37.P37_ARTIFACT_DISCLAIMER
