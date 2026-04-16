"""Tests for ResearchDatabase."""
import tempfile
import os
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
