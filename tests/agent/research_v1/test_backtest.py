"""Tests for P1 backtest outcome calculation and Yahoo history adapter."""

from unittest.mock import Mock

from agent.research_v1.backtest import (
    compute_signal_outcomes,
    summarize_signal_outcomes,
    summarize_signal_outcomes_by_grade,
)
from agent.research_v1.data.yahoo_finance import YahooFinanceHistoricalDataSource
from agent.research_v1.backtest_pipeline import BacktestPipeline
from agent.research_v1.data.database import ResearchDatabase

import tempfile
import os


def test_compute_signal_outcomes_for_standard_horizons():
    """Compute 5/20/60-day outcomes from ordered close prices."""
    outcomes = compute_signal_outcomes(
        signal={
            "symbol": "AAPL",
            "entry_price": 100.0,
        },
        price_points=[
            {"day": 0, "close": 100.0},
            {"day": 1, "close": 102.0},
            {"day": 5, "close": 110.0},
            {"day": 20, "close": 120.0},
            {"day": 60, "close": 90.0},
        ],
    )

    assert outcomes[5]["exit_price"] == 110.0
    assert round(outcomes[5]["return_pct"], 4) == 0.10
    assert outcomes[20]["win"] is True
    assert outcomes[60]["win"] is False


def test_compute_signal_outcomes_handles_missing_horizon_by_skipping_forward():
    """Use the next available price point when an exact horizon point is missing."""
    outcomes = compute_signal_outcomes(
        signal={
            "symbol": "AAPL",
            "entry_price": 100.0,
        },
        price_points=[
            {"day": 0, "close": 100.0},
            {"day": 6, "close": 109.0},
            {"day": 21, "close": 119.0},
            {"day": 63, "close": 95.0},
        ],
    )

    assert outcomes[5]["gap_handled"] is True
    assert outcomes[5]["exit_price"] == 109.0
    assert outcomes[20]["exit_price"] == 119.0


def test_summarize_signal_outcomes_computes_core_stats():
    """Summarize backtest outcomes into win rate and payoff stats."""
    summary = summarize_signal_outcomes([
        {"return_pct": 0.10, "max_drawdown_pct": -0.03, "win": True},
        {"return_pct": -0.05, "max_drawdown_pct": -0.07, "win": False},
        {"return_pct": 0.20, "max_drawdown_pct": -0.02, "win": True},
    ])

    assert round(summary["win_rate"], 4) == 0.6667
    assert round(summary["average_return"], 4) == 0.0833
    assert summary["max_drawdown"] == -0.07
    assert summary["profit_loss_ratio"] == 3.0


def test_yahoo_history_adapter_normalizes_closes():
    """Normalize Yahoo Finance history rows into sorted price points."""
    source = YahooFinanceHistoricalDataSource()

    rows = source._normalize_history([
        {"Date": "2026-04-01", "Close": 100.0},
        {"Date": "2026-04-02", "Close": 101.5},
    ])

    assert rows[0]["close"] == 100.0
    assert rows[1]["date"] == "2026-04-02"


def test_yahoo_history_adapter_fetches_chart_rows(monkeypatch):
    """Fetch chart data from Yahoo response and normalize to day offsets."""
    source = YahooFinanceHistoricalDataSource()

    fake_response = Mock()
    fake_response.raise_for_status.return_value = None
    fake_response.json.return_value = {
        "chart": {
            "result": [{
                "timestamp": [1711929600, 1712016000],
                "indicators": {
                    "quote": [{
                        "close": [100.0, 101.5],
                    }]
                }
            }]
        }
    }

    def fake_get(url, params, timeout):
        assert "finance/chart" in url
        assert params["symbol"] == "AAPL"
        return fake_response

    monkeypatch.setattr("agent.research_v1.data.yahoo_finance.requests.get", fake_get)
    rows = source.fetch_history("AAPL", start_date="2024-04-01", end_date="2024-04-10")

    assert rows[0]["day"] == 0
    assert rows[1]["close"] == 101.5


def test_backtest_pipeline_runs_and_persists_outcomes(monkeypatch):
    """Run the backtest pipeline from persisted signal to persisted outcomes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "research.db")
        db = ResearchDatabase(db_path)
        db.initialize()

        task_id = db.create_task(symbol="AAPL", report_date="2024-01-15", session="test")
        signal_id = db.save_signal(
            task_id=task_id,
            signal={
                "symbol": "AAPL",
                "grade": "S",
                "confidence": 0.9,
                "entry_price": 100.0,
                "stop_loss": 93.0,
                "take_profit": 112.0,
                "holding_horizon": "20d",
                "signal_valid_until": "2026-04-23T00:00:00+00:00",
                "priority_score": 84.7,
            }
        )

        source = YahooFinanceHistoricalDataSource()

        def fake_fetch_history(symbol, start_date, end_date):
            return [
                {"day": 0, "date": "2024-01-15", "close": 100.0},
                {"day": 5, "date": "2024-01-22", "close": 108.0},
                {"day": 20, "date": "2024-02-12", "close": 120.0},
                {"day": 60, "date": "2024-04-15", "close": 95.0},
            ]

        monkeypatch.setattr(source, "fetch_history", fake_fetch_history)
        pipeline = BacktestPipeline(database=db, historical_data_source=source)
        result = pipeline.backtest_signal(signal_id, start_date="2024-01-15", end_date="2024-04-15")

        assert result["signal"]["signal_id"] == signal_id
        assert len(result["persisted_outcomes"]) == 3
        assert round(result["summary_by_horizon"][5]["average_return"], 4) == 0.08
        assert result["summary_by_horizon"][20]["win_rate"] == 1.0


def test_summarize_signal_outcomes_by_grade_groups_metrics():
    """Aggregate outcome stats per grade bucket."""
    grouped = summarize_signal_outcomes_by_grade([
        {"grade": "S", "return_pct": 0.10, "max_drawdown_pct": -0.03, "win": True},
        {"grade": "S", "return_pct": -0.05, "max_drawdown_pct": -0.08, "win": False},
        {"grade": "C", "return_pct": -0.20, "max_drawdown_pct": -0.22, "win": False},
    ])

    assert "S" in grouped
    assert "C" in grouped
    assert grouped["S"]["sample_size"] == 2
    assert round(grouped["S"]["win_rate"], 4) == 0.5
    assert grouped["C"]["win_rate"] == 0.0


def test_backtest_pipeline_summarize_edge_by_grade(monkeypatch):
    """Summarize persisted outcomes by grade and horizon."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "research.db")
        db = ResearchDatabase(db_path)
        db.initialize()

        task_s = db.create_task(symbol="AAPL", report_date="2024-01-15", session="test")
        signal_s = db.save_signal(
            task_id=task_s,
            signal={
                "symbol": "AAPL",
                "grade": "S",
                "confidence": 0.9,
                "entry_price": 100.0,
                "stop_loss": 93.0,
                "take_profit": 112.0,
                "holding_horizon": "20d",
                "signal_valid_until": "2026-04-23T00:00:00+00:00",
                "priority_score": 84.7,
            }
        )
        db.save_signal_outcome(
            signal_id=signal_s,
            horizon_days=20,
            exit_price=120.0,
            return_pct=0.2,
            max_drawdown_pct=-0.03,
            win=True,
            gap_handled=False,
        )

        task_c = db.create_task(symbol="TSLA", report_date="2024-01-15", session="test")
        signal_c = db.save_signal(
            task_id=task_c,
            signal={
                "symbol": "TSLA",
                "grade": "C",
                "confidence": 0.4,
                "entry_price": 100.0,
                "stop_loss": 93.0,
                "take_profit": 112.0,
                "holding_horizon": "20d",
                "signal_valid_until": "2026-04-23T00:00:00+00:00",
                "priority_score": 40.0,
            }
        )
        db.save_signal_outcome(
            signal_id=signal_c,
            horizon_days=20,
            exit_price=90.0,
            return_pct=-0.1,
            max_drawdown_pct=-0.12,
            win=False,
            gap_handled=False,
        )

        source = YahooFinanceHistoricalDataSource()
        pipeline = BacktestPipeline(database=db, historical_data_source=source)
        summary = pipeline.summarize_edge_by_grade(horizon_days=20)

        assert "S" in summary
        assert "C" in summary
        assert summary["S"]["win_rate"] == 1.0
        assert summary["C"]["win_rate"] == 0.0
