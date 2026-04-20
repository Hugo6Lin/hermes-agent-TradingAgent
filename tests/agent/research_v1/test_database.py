"""Tests for ResearchDatabase."""
import tempfile
import os
import sqlite3
from pathlib import Path

import pytest

from agent.research_v1.data.database import ResearchDatabase


def test_research_database_creation():
    """Create temp dir, initialize db, verify it exists."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "research.db")
        db = ResearchDatabase(db_path)
        db.initialize()

        assert os.path.exists(db_path), "Database file should exist"


def test_analysis_tasks_crud():
    """Create task, get task, update task status."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "research.db")
        db = ResearchDatabase(db_path)
        db.initialize()

        # Create task
        task_id = db.create_task(symbol="AAPL", report_date="2024-01-15", session="test-session")
        assert task_id > 0, "Task ID should be positive"

        # Get task
        task = db.get_task(task_id)
        assert task is not None, "Task should exist"
        assert task["symbol"] == "AAPL"
        assert task["report_date"] == "2024-01-15"
        assert task["session"] == "test-session"
        assert task["status"] == "pending"

        # Update task status
        db.update_task_status(task_id, status="completed", grade="A", composite_score=0.85)
        updated_task = db.get_task(task_id)
        assert updated_task["status"] == "completed"
        assert updated_task["grade"] == "A"
        assert updated_task["composite_score"] == 0.85


def test_watchlist_operations():
    """Create watchlist, add items, get watchlist items."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "research.db")
        db = ResearchDatabase(db_path)
        db.initialize_watchlist()

        # Create watchlist
        list_id = db.create_watchlist(name="Tech Stocks", user_id="user123")
        assert list_id > 0, "List ID should be positive"

        # Add items to watchlist
        item1_id = db.add_to_watchlist(list_id, symbol="AAPL", notes="Apple Inc")
        item2_id = db.add_to_watchlist(list_id, symbol="GOOGL", notes="Alphabet")

        # Get watchlist items
        items = db.get_watchlist_items(list_id)
        assert len(items) == 2, "Should have 2 items"
        symbols = {item["symbol"] for item in items}
        assert "AAPL" in symbols
        assert "GOOGL" in symbols


def test_token_usage_tracking():
    """Record token usage and get summary."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "research.db")
        db = ResearchDatabase(db_path)
        db.initialize()

        # Create a task first
        task_id = db.create_task(symbol="AAPL", report_date="2024-01-15", session="test")

        # Record token usage
        db.record_token_usage(
            task_id=task_id,
            agent_type="fundamental",
            model="claude-sonnet-4-20250514",
            input_tokens=1000,
            output_tokens=500,
            cost=0.05
        )

        # Get summary
        summary = db.get_token_usage_summary(days=30)
        assert summary["total_tokens"] == 1500
        assert summary["total_cost"] == 0.05
        assert summary["total_input_tokens"] == 1000
        assert summary["total_output_tokens"] == 500


def test_initialize_creates_signal_tables():
    """Initialize main schema and verify signal persistence tables exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "research.db")
        db = ResearchDatabase(db_path)
        db.initialize()

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        table_names = {row[0] for row in cursor.fetchall()}
        conn.close()

        assert "signals" in table_names
        assert "price_snapshots" in table_names
        assert "signal_revisions" in table_names
        assert "signal_outcomes" in table_names
        assert "positions" in table_names
        assert "paper_trades" in table_names


def test_save_signal_persists_structured_signal():
    """Save a structured signal and verify it is stored correctly."""
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
                "confidence": 0.91,
                "entry_price": 150.0,
                "stop_loss": 139.5,
                "take_profit": 168.0,
                "holding_horizon": "20d",
                "signal_valid_until": "2026-04-23T00:00:00+00:00",
                "priority_score": 84.7,
            }
        )

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM signals WHERE signal_id = ?", (signal_id,))
        row = cursor.fetchone()
        conn.close()

        assert signal_id > 0
        assert row["task_id"] == task_id
        assert row["symbol"] == "AAPL"
        assert row["grade"] == "S"
        assert row["entry_price"] == 150.0


def test_save_price_snapshot_links_to_signal():
    """Save a price snapshot linked to a signal."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "research.db")
        db = ResearchDatabase(db_path)
        db.initialize()
        task_id = db.create_task(symbol="AAPL", report_date="2024-01-15", session="test")
        signal_id = db.save_signal(
            task_id=task_id,
            signal={
                "symbol": "AAPL",
                "grade": "A",
                "confidence": 0.72,
                "entry_price": 150.0,
                "stop_loss": 142.0,
                "take_profit": 162.0,
                "holding_horizon": "20d",
                "signal_valid_until": "2026-04-23T00:00:00+00:00",
                "priority_score": 72.3,
            }
        )

        snapshot_id = db.save_price_snapshot(
            signal_id=signal_id,
            symbol="AAPL",
            price=150.0,
            snapshot_type="signal_entry",
        )

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM price_snapshots WHERE snapshot_id = ?", (snapshot_id,))
        row = cursor.fetchone()
        conn.close()

        assert snapshot_id > 0
        assert row["signal_id"] == signal_id
        assert row["snapshot_type"] == "signal_entry"


def test_save_signal_revision_tracks_grade_change():
    """Save a signal revision and verify it records the grade change."""
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
                "confidence": 0.84,
                "entry_price": 150.0,
                "stop_loss": 140.0,
                "take_profit": 170.0,
                "holding_horizon": "20d",
                "signal_valid_until": "2026-04-23T00:00:00+00:00",
                "priority_score": 84.0,
            }
        )

        revision_id = db.save_signal_revision(
            signal_id=signal_id,
            previous_grade="S",
            new_grade="B",
            revision_reason="macro conditions deteriorated",
        )

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM signal_revisions WHERE revision_id = ?", (revision_id,))
        row = cursor.fetchone()
        conn.close()

        assert revision_id > 0
        assert row["signal_id"] == signal_id
        assert row["previous_grade"] == "S"
        assert row["new_grade"] == "B"


def test_save_signal_bundle_persists_signal_and_entry_snapshot():
    """Persist a grading result bundle into signals and price snapshots."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "research.db")
        db = ResearchDatabase(db_path)
        db.initialize()
        task_id = db.create_task(symbol="AAPL", report_date="2024-01-15", session="test")

        saved = db.save_signal_bundle(
            task_id=task_id,
            grade_result={
                "grade": "S",
                "signal": {
                    "symbol": "AAPL",
                    "entry_price": 150.0,
                    "stop_loss": 139.5,
                    "take_profit": 168.0,
                    "holding_horizon": "20d",
                    "signal_valid_until": "2026-04-23T00:00:00+00:00",
                    "priority_score": 84.7,
                    "confidence": 0.847,
                },
            },
        )

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM signals WHERE signal_id = ?", (saved["signal_id"],))
        signal_row = cursor.fetchone()
        cursor.execute(
            "SELECT * FROM price_snapshots WHERE snapshot_id = ?",
            (saved["snapshot_id"],)
        )
        snapshot_row = cursor.fetchone()
        conn.close()

        assert saved["signal_id"] > 0
        assert saved["snapshot_id"] > 0
        assert signal_row["grade"] == "S"
        assert snapshot_row["signal_id"] == saved["signal_id"]
        assert snapshot_row["snapshot_type"] == "signal_entry"


def test_save_signal_outcome_persists_backtest_result():
    """Save a signal outcome and verify backtest metrics are stored."""
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
                "entry_price": 150.0,
                "stop_loss": 139.5,
                "take_profit": 168.0,
                "holding_horizon": "20d",
                "signal_valid_until": "2026-04-23T00:00:00+00:00",
                "priority_score": 84.7,
            }
        )

        outcome_id = db.save_signal_outcome(
            signal_id=signal_id,
            horizon_days=20,
            exit_price=165.0,
            return_pct=0.10,
            max_drawdown_pct=-0.04,
            win=True,
            gap_handled=False,
        )

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM signal_outcomes WHERE outcome_id = ?", (outcome_id,))
        row = cursor.fetchone()
        conn.close()

        assert outcome_id > 0
        assert row["signal_id"] == signal_id
        assert row["horizon_days"] == 20
        assert row["win"] == 1


def test_get_signal_and_outcomes_returns_persisted_backtest_data():
    """Fetch signal and persisted outcomes for downstream backtest reporting."""
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
                "entry_price": 150.0,
                "stop_loss": 139.5,
                "take_profit": 168.0,
                "holding_horizon": "20d",
                "signal_valid_until": "2026-04-23T00:00:00+00:00",
                "priority_score": 84.7,
            }
        )
        db.save_signal_outcome(
            signal_id=signal_id,
            horizon_days=20,
            exit_price=165.0,
            return_pct=0.10,
            max_drawdown_pct=-0.04,
            win=True,
            gap_handled=False,
        )

        signal = db.get_signal(signal_id)
        outcomes = db.get_signal_outcomes(signal_id)

        assert signal["signal_id"] == signal_id
        assert signal["grade"] == "S"
        assert len(outcomes) == 1
        assert outcomes[0]["horizon_days"] == 20


def test_get_signal_outcomes_with_grade_returns_joined_rows():
    """Join persisted outcomes with signal grade for edge aggregation."""
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
                "entry_price": 150.0,
                "stop_loss": 139.5,
                "take_profit": 168.0,
                "holding_horizon": "20d",
                "signal_valid_until": "2026-04-23T00:00:00+00:00",
                "priority_score": 84.7,
            }
        )
        db.save_signal_outcome(
            signal_id=signal_id,
            horizon_days=20,
            exit_price=165.0,
            return_pct=0.10,
            max_drawdown_pct=-0.04,
            win=True,
            gap_handled=False,
        )

        rows = db.get_signal_outcomes_with_grade(horizon_days=20)
        assert len(rows) == 1
        assert rows[0]["grade"] == "S"
        assert rows[0]["horizon_days"] == 20


def test_open_and_get_position_persists_trade_plan_context():
    """Open a position and verify trade-plan fields are stored."""
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
                "entry_price": 150.0,
                "stop_loss": 139.5,
                "take_profit": 168.0,
                "holding_horizon": "20d",
                "signal_valid_until": "2026-04-23T00:00:00+00:00",
                "priority_score": 84.7,
            }
        )

        position_id = db.open_position(
            signal_id=signal_id,
            symbol="AAPL",
            entry_price=150.0,
            quantity=10,
            stop_loss=139.5,
            take_profit=168.0,
            status="open",
        )

        position = db.get_position(position_id)
        assert position["signal_id"] == signal_id
        assert position["symbol"] == "AAPL"
        assert position["quantity"] == 10
        assert position["status"] == "open"


def test_save_paper_trade_records_simulated_execution():
    """Persist a paper trade for pre-live validation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "research.db")
        db = ResearchDatabase(db_path)
        db.initialize()

        task_id = db.create_task(symbol="AAPL", report_date="2024-01-15", session="test")
        signal_id = db.save_signal(
            task_id=task_id,
            signal={
                "symbol": "AAPL",
                "grade": "A",
                "confidence": 0.8,
                "entry_price": 150.0,
                "stop_loss": 142.0,
                "take_profit": 162.0,
                "holding_horizon": "20d",
                "signal_valid_until": "2026-04-23T00:00:00+00:00",
                "priority_score": 72.3,
            }
        )

        paper_trade_id = db.save_paper_trade(
            signal_id=signal_id,
            symbol="AAPL",
            entry_price=150.0,
            quantity=5,
            status="open",
        )

        paper_trade = db.get_paper_trade(paper_trade_id)
        assert paper_trade["signal_id"] == signal_id
        assert paper_trade["symbol"] == "AAPL"
        assert paper_trade["quantity"] == 5
        assert paper_trade["status"] == "open"
