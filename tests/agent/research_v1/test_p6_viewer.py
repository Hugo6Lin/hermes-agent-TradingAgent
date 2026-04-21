"""Tests for P6 minimal viewer and end-of-day summary."""

import json
import os
import tempfile
import threading
import time
from pathlib import Path
from urllib.request import urlopen

from agent.research_v1.data.database import ResearchDatabase
from agent.research_v1.research_batch_service import save_batch_research
from agent.research_v1.viewer import (
    build_end_of_day_summary,
    build_viewer_snapshot,
    render_dashboard_html,
    serve_viewer,
)


def test_build_viewer_snapshot_collects_signals_positions_and_paper_trades():
    """Aggregate the minimal dashboard snapshot from persisted tables."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "research.db")
        db = ResearchDatabase(db_path)
        db.initialize()
        db.initialize_watchlist()

        task_id = db.create_task(symbol="AAPL", report_date="2026-04-20", session="test")
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
            },
        )
        db.open_position(
            signal_id=signal_id,
            symbol="AAPL",
            entry_price=150.0,
            quantity=10,
            stop_loss=139.5,
            take_profit=168.0,
            status="open",
        )
        db.save_paper_trade(
            signal_id=signal_id,
            symbol="AAPL",
            entry_price=150.0,
            quantity=5,
            status="open",
        )

        watchlist_id = db.create_watchlist("Default")
        conn = db._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO alert_history (list_id, symbol, alert_type, message, is_read)
            VALUES (?, ?, ?, ?, ?)
            """,
            (watchlist_id, "AAPL", "stop_loss", "Price broke stop-loss", 0),
        )
        conn.commit()
        conn.close()

        snapshot = build_viewer_snapshot(db)

        assert len(snapshot["signals"]) == 1
        assert len(snapshot["positions"]) == 1
        assert len(snapshot["paper_trades"]) == 1
        assert len(snapshot["alerts"]) == 1


def test_render_dashboard_html_contains_core_sections():
    """Render a narrow dashboard page with core trading sections."""
    html = render_dashboard_html(
        {
            "signals": [{"symbol": "AAPL", "grade": "S", "priority_score": 84.7, "confidence": 0.91}],
            "positions": [{"symbol": "AAPL", "status": "open", "quantity": 10}],
            "paper_trades": [{"symbol": "AAPL", "status": "open", "quantity": 5}],
            "alerts": [{"symbol": "AAPL", "message": "Price broke stop-loss"}],
        }
    )

    assert "Legacy Signals" in html
    assert "Canonical Signals" in html
    assert "Canonical Reports" in html
    assert "Open Positions" in html
    assert "Paper Trades" in html
    assert "Alerts" in html
    assert "AAPL" in html


def test_build_end_of_day_summary_reports_priority_signal_and_alert_count():
    """Generate a lightweight end-of-day summary from dashboard data."""
    summary = build_end_of_day_summary(
        {
            "signals": [
                {"symbol": "AAPL", "grade": "S", "priority_score": 84.7},
                {"symbol": "JPM", "grade": "A", "priority_score": 72.0},
            ],
            "positions": [{"symbol": "AAPL", "status": "open", "quantity": 10}],
            "paper_trades": [{"symbol": "AAPL", "status": "open", "quantity": 5}],
            "alerts": [{"symbol": "AAPL", "message": "Price broke stop-loss"}],
        }
    )

    assert "Top signal: AAPL" in summary
    assert "Open positions: 1" in summary
    assert "Unread alerts: 1" in summary


def test_serve_viewer_builds_http_server():
    """Construct the minimal HTTP server without launching a framework stack."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "research.db")
        db = ResearchDatabase(db_path)
        db.initialize()
        server = serve_viewer(db, host="127.0.0.1", port=0)
        try:
            assert server.server_address[0] == "127.0.0.1"
        finally:
            server.server_close()


def test_build_viewer_snapshot_tolerates_missing_watchlist_tables():
    """Viewer should remain readable even when watchlist tables were never initialized."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "research.db")
        db = ResearchDatabase(db_path)
        db.initialize()

        snapshot = build_viewer_snapshot(db)
        assert snapshot["alerts"] == []


def test_viewer_routes_latest_batch_overview_and_ticker_detail_from_persisted_batch():
    """Serve the latest research batch overview and ticker detail from persisted data."""
    fixture_path = Path(__file__).parent / "fixtures" / "sample_batch_payload.json"
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "research.db")
        db = ResearchDatabase(db_path)
        db.initialize()

        result = save_batch_research(db, payload)
        server = serve_viewer(db, host="127.0.0.1", port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            time.sleep(0.05)
            port = server.server_address[1]
            overview = urlopen(f"http://127.0.0.1:{port}/").read().decode("utf-8")
            latest = urlopen(f"http://127.0.0.1:{port}/batches/latest").read().decode("utf-8")
            detail = urlopen(f"http://127.0.0.1:{port}/ticker/{result['item_ids'][0]}").read().decode("utf-8")
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()

        assert "Executive Summary" in overview
        assert "NVDA" in overview
        assert "Top Risk" in overview
        assert "Executive Summary" in latest
        assert "Bottom Line" in detail
        assert "Risk Watch" in detail


def test_ticker_detail_page_uses_owning_batch_even_after_newer_batch_is_saved():
    """Older batch ticker pages should remain addressable after later batches are persisted."""
    fixture_path = Path(__file__).parent / "fixtures" / "sample_batch_payload.json"
    first_payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    second_payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    second_payload["title"] = "US AI Leaders - Follow Up"
    second_payload["boss_summary"] = "Follow-up batch for later coverage."

    with tempfile.TemporaryDirectory() as tmpdir:
        db = ResearchDatabase(os.path.join(tmpdir, "research.db"))
        db.initialize()

        first_result = save_batch_research(db, first_payload)
        second_result = save_batch_research(db, second_payload)
        server = serve_viewer(db, host="127.0.0.1", port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            time.sleep(0.05)
            port = server.server_address[1]
            detail = urlopen(f"http://127.0.0.1:{port}/ticker/{first_result['item_ids'][0]}").read().decode("utf-8")
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()

        assert "NVDA" in detail
        assert "NVDA is the strongest setup in the batch." in detail
        assert "Follow-up batch for later coverage." not in detail
        assert second_result["batch_id"] > first_result["batch_id"]


def test_overview_uses_one_canonical_report_per_batch_item():
    """Overview cards should not duplicate when an item has multiple reports."""
    fixture_path = Path(__file__).parent / "fixtures" / "sample_batch_payload.json"
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))

    with tempfile.TemporaryDirectory() as tmpdir:
        db = ResearchDatabase(os.path.join(tmpdir, "research.db"))
        db.initialize()

        result = save_batch_research(db, payload)
        item_id = result["item_ids"][0]
        conn = db._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO company_reports (
                batch_item_id, bottom_line, why_it_matters, action_plan,
                bull_case, risk_watch, research_summary, signal_snapshot_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item_id,
                "NVDA canonical report should win.",
                "This second report should become the canonical overview text.",
                "Watch the later note.",
                "Later report bull case.",
                "Later report risk watch.",
                "Later report summary.",
                "{\"grade\": \"S\"}",
            ),
        )
        conn.commit()
        conn.close()

        snapshot = build_viewer_snapshot(db)
        overview = render_dashboard_html(snapshot)

        assert overview.count(f'/ticker/{item_id}') == 1
        assert "NVDA canonical report should win." in overview
        assert "NVDA is the strongest setup in the batch." not in overview
