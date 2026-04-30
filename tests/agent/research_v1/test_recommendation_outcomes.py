"""Tests for P36 recommendation outcome tracking."""

from __future__ import annotations

from pathlib import Path

from agent.research_v1.contracts import CanonicalSignal, ResearchMode, ResearchTask
from agent.research_v1.data.database import ResearchDatabase


def _db(tmp_path: Path) -> ResearchDatabase:
    db = ResearchDatabase(str(tmp_path / "research.db"))
    db.initialize()
    db.initialize_research_core()
    db.initialize_canonical_outcome_schema()
    return db


def _task() -> ResearchTask:
    return ResearchTask(
        task_id="task_p36_aapl",
        request_text="Research AAPL",
        tickers=["AAPL"],
        research_mode=ResearchMode.STANDARD,
    )


def _signal() -> CanonicalSignal:
    return CanonicalSignal(
        ticker="AAPL",
        rating="BUY",
        confidence=0.82,
        priority_score=88.0,
        entry_price=100.0,
        stop_loss=92.0,
        take_profit=115.0,
        holding_horizon="60d",
        decision_reason="P36 fixture",
    )


def _seed_signal(db: ResearchDatabase) -> str:
    task = _task()
    signal = _signal()
    db.save_research_task(task)
    return db.save_canonical_signal(signal, task.task_id)


def _outcome_payload(signal_id: str, data_hash: str = "hash_a") -> dict:
    return {
        "schema_version": "p36_recommendation_outcome.1",
        "signal_id": signal_id,
        "task_id": "task_p36_aapl",
        "ticker": "AAPL",
        "action": "Buy Stock",
        "rating": "BUY",
        "horizon_days": 5,
        "calendar": "XNYS",
        "entry_rule": "next_open",
        "entry_price": 101.0,
        "entry_date": "2026-04-01",
        "exit_price": 110.0,
        "exit_date": "2026-04-08",
        "target_reached": False,
        "stop_breached": False,
        "target_reached_before_stop": False,
        "benchmark_return_pct": None,
        "gross_return_pct": 0.0891089109,
        "net_return_pct": 0.0891089109,
        "max_drawdown_pct": -0.01,
        "win": True,
        "win_definition": "net_return_positive",
        "status": "evaluated",
        "evaluation_proxy": "none",
        "cost_basis": "none",
        "cost_bps": 0.0,
        "data_source": "fake_provider",
        "price_adjustment": "adjusted",
        "data_source_hash": data_hash,
        "path_precision": "ohlc",
        "evaluated_for_date": "2026-04-30",
        "evaluated_at": "2026-04-30T12:00:00Z",
    }


def test_canonical_outcome_schema_persists_rows(tmp_path: Path):
    db = _db(tmp_path)
    signal_id = _seed_signal(db)

    outcome_id = db.save_canonical_outcome(_outcome_payload(signal_id=signal_id))
    rows = db.list_canonical_outcomes_by_signal(signal_id)

    assert outcome_id
    assert len(rows) == 1
    assert rows[0]["schema_version"] == "p36_recommendation_outcome.1"
    assert rows[0]["status"] == "evaluated"
    assert rows[0]["action"] == "Buy Stock"
    assert rows[0]["evaluated_for_date"] == "2026-04-30"
    assert rows[0]["evaluated_at"] == "2026-04-30T12:00:00Z"


def test_canonical_outcome_natural_key_noops_same_data(tmp_path: Path):
    db = _db(tmp_path)
    signal_id = _seed_signal(db)

    first = db.save_canonical_outcome(_outcome_payload(signal_id=signal_id, data_hash="same_hash"))
    second = db.save_canonical_outcome(_outcome_payload(signal_id=signal_id, data_hash="same_hash"))
    rows = db.list_canonical_outcomes_by_signal(signal_id)

    assert first == second
    assert len(rows) == 1


def test_canonical_outcome_revised_data_hash_appends_row(tmp_path: Path):
    db = _db(tmp_path)
    signal_id = _seed_signal(db)

    first = db.save_canonical_outcome(_outcome_payload(signal_id=signal_id, data_hash="hash_a"))
    second = db.save_canonical_outcome(_outcome_payload(signal_id=signal_id, data_hash="hash_b"))
    rows = db.list_canonical_outcomes_by_signal(signal_id)

    assert first != second
    assert len(rows) == 2


def test_canonical_outcome_summaries_group_by_action_rating_ticker_and_horizon(tmp_path: Path):
    db = _db(tmp_path)
    signal_id = _seed_signal(db)
    db.save_canonical_outcome(_outcome_payload(signal_id=signal_id, data_hash="hash_a"))

    assert db.summarize_outcomes_by("action")[0]["group"] == "Buy Stock"
    assert db.summarize_outcomes_by("rating")[0]["group"] == "BUY"
    assert db.summarize_outcomes_by("ticker")[0]["group"] == "AAPL"
    assert db.summarize_outcomes_by("horizon")[0]["group"] == 5
