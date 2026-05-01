"""Tests for P47 read-only research context pack."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent.research_v1.research_context_pack import (
    P47_DISCLAIMER,
    P47_SCHEMA_VERSION,
    build_research_context_pack,
    collect_research_context_evidence,
    normalize_tickers,
    render_research_context_pack_markdown,
    run_research_context_pack,
    validate_request_inputs,
    write_research_context_pack,
)
from agent.research_v1.data.database import ResearchDatabase


def test_normalize_tickers_deduplicates_and_preserves_order():
    assert normalize_tickers([" aapl ", "MSFT", "AAPL"]) == ["AAPL", "MSFT"]


def test_invalid_ticker_rejected():
    result = validate_request_inputs("2026-05-01", ["AAPL;DROP"], 180, 8, governance_root_is_dir=True)
    assert result["status"] == "blocked_invalid_input"
    assert "invalid_ticker:AAPL;DROP" in result["warnings"]


def test_build_pack_limited_with_missing_ticker_context(tmp_path: Path):
    pack = build_research_context_pack(
        as_of_date="2026-05-01",
        tickers=["AAPL"],
        lookback_days=180,
        max_items_per_ticker=8,
        evidence={
            "system": {"provider_status": "provider_ready"},
            "tickers": {},
        },
    )
    assert pack["status"] == "context_pack_limited"
    assert pack["ticker_contexts"][0]["context_status"] == "context_missing"
    assert "missing_ticker_context:AAPL" in pack["missing_context"]


def test_build_pack_ready_with_sufficient_evidence():
    pack = build_research_context_pack(
        as_of_date="2026-05-01",
        tickers=["AAPL"],
        lookback_days=180,
        max_items_per_ticker=8,
        evidence={
            "system": {
                "provider_status": "provider_ready",
                "evidence_health_status": "monitor_green",
            },
            "tickers": {
                "AAPL": {
                    "market_regime": {"regime_label": "neutral"},
                    "fundamental_quality": {"quality_score": 80, "quality_label": "strong"},
                    "candidate_context": {"candidate_status": "active"},
                },
            },
        },
    )
    assert pack["status"] == "context_pack_ready"
    assert pack["ticker_contexts"][0]["context_status"] == "context_ready"
    assert pack["disclaimer"] == P47_DISCLAIMER


def test_markdown_renderer_includes_required_sections():
    pack = build_research_context_pack(
        as_of_date="2026-05-01",
        tickers=["AAPL"],
        lookback_days=180,
        max_items_per_ticker=8,
        evidence={"system": {}, "tickers": {}},
    )
    md = render_research_context_pack_markdown(pack)
    assert "# P47 Research Context Pack" in md
    assert "## System Context" in md
    assert "## Ticker Contexts" in md
    assert "## Disclaimer" in md
    assert P47_DISCLAIMER in md


def test_write_research_context_pack_creates_files(tmp_path: Path):
    pack = build_research_context_pack(
        as_of_date="2026-05-01",
        tickers=["AAPL"],
        lookback_days=180,
        max_items_per_ticker=8,
        evidence={"system": {}, "tickers": {}},
    )
    artifacts = write_research_context_pack(pack, tmp_path)
    assert len(artifacts) == 2
    json_path = tmp_path / "2026-05-01" / "p47_research_context_pack.json"
    md_path = tmp_path / "2026-05-01" / "p47_research_context_pack.md"
    assert json_path.exists()
    assert md_path.exists()
    loaded = json.loads(json_path.read_text())
    assert loaded["pack_id"] == pack["pack_id"]


def test_save_and_list_research_context_packs(tmp_path: Path):
    db = ResearchDatabase(str(tmp_path / "test.db"))
    db.initialize()
    pack = build_research_context_pack(
        as_of_date="2026-05-01",
        tickers=["AAPL", "MSFT"],
        lookback_days=180,
        max_items_per_ticker=8,
        evidence={"system": {}, "tickers": {}},
    )
    db.save_research_context_pack(pack)
    rows = db.list_research_context_packs(as_of_date="2026-05-01")
    assert len(rows) == 1
    assert rows[0]["pack_id"] == pack["pack_id"]
    assert rows[0]["tickers_key"] == "AAPL|MSFT"


def test_save_research_context_pack_idempotent(tmp_path: Path):
    db = ResearchDatabase(str(tmp_path / "test.db"))
    db.initialize()
    pack = build_research_context_pack(
        as_of_date="2026-05-01",
        tickers=["AAPL"],
        lookback_days=180,
        max_items_per_ticker=8,
        evidence={"system": {}, "tickers": {}},
    )
    db.save_research_context_pack(pack)
    db.save_research_context_pack(pack)
    rows = db.list_research_context_packs(as_of_date="2026-05-01")
    assert len(rows) == 1


def test_run_research_context_pack_with_empty_db(tmp_path: Path):
    db = ResearchDatabase(str(tmp_path / "test.db"))
    db.initialize()
    governance_root = tmp_path / "governance"
    governance_root.mkdir()
    output_root = tmp_path / "output"
    pack = run_research_context_pack(
        db=db,
        governance_root=governance_root,
        output_root=output_root,
        as_of_date="2026-05-01",
        tickers=["AAPL"],
    )
    assert pack["status"] == "context_pack_missing"
    assert (output_root / "2026-05-01" / "p47_research_context_pack.json").exists()


def test_run_research_context_pack_blocked_invalid_input(tmp_path: Path):
    db = ResearchDatabase(str(tmp_path / "test.db"))
    db.initialize()
    governance_root = tmp_path / "governance"
    governance_root.mkdir()
    result = run_research_context_pack(
        db=db,
        governance_root=governance_root,
        output_root=tmp_path / "output",
        as_of_date="bad-date",
        tickers=["AAPL"],
    )
    assert result["status"] == "blocked_invalid_input"


def test_system_context_falls_back_to_p45_artifact_when_db_empty(tmp_path: Path):
    db = ResearchDatabase(str(tmp_path / "test.db"))
    db.initialize()
    governance_root = tmp_path / "governance"
    governance_root.mkdir()
    day_dir = governance_root / "2026-05-01"
    day_dir.mkdir()
    (day_dir / "p45_market_data_readiness.json").write_text(json.dumps({
        "schema_version": "p45_market_data_readiness.1",
        "report_id": "p45-report",
        "as_of_date": "2026-05-01",
        "status": "provider_ready",
        "source_hash": "p45-hash",
        "recommended_actions": [],
    }), encoding="utf-8")
    pack = run_research_context_pack(
        db=db,
        governance_root=governance_root,
        output_root=tmp_path / "output",
        as_of_date="2026-05-01",
        tickers=["AAPL"],
    )
    assert pack["system_context"].get("provider_status") == "provider_ready"


def test_system_context_reads_p42_p43_from_db_without_artifact(tmp_path: Path):
    db = ResearchDatabase(str(tmp_path / "test.db"))
    db.initialize()
    db.save_boss_copilot_daily_brief({
        "brief_id": "brief-1",
        "schema_version": "p42_boss_copilot_daily_brief.1",
        "as_of_date": "2026-05-01",
        "created_at": "2026-05-01T10:00:00+00:00",
        "status": "brief_ready",
        "source_hash": "brief-hash",
        "brief_json": "{}",
    })
    db.save_copilot_console_index({
        "index_id": "index-1",
        "schema_version": "p43_copilot_console_index.1",
        "as_of_date": "2026-05-01",
        "created_at": "2026-05-01T10:00:00+00:00",
        "status": "index_ready",
        "source_hash": "index-hash",
        "index_json": "{}",
    })
    governance_root = tmp_path / "governance"
    governance_root.mkdir()
    pack = run_research_context_pack(
        db=db,
        governance_root=governance_root,
        output_root=tmp_path / "output",
        as_of_date="2026-05-01",
        tickers=["AAPL"],
    )
    assert pack["system_context"].get("latest_boss_brief_status") == "brief_ready"
    assert pack["system_context"].get("latest_console_index_status") == "index_ready"


def test_db_call_warning_captured_on_operational_error(tmp_path: Path):
    import sqlite3

    db = ResearchDatabase(str(tmp_path / "test.db"))
    db.initialize()
    governance_root = tmp_path / "governance"
    governance_root.mkdir()

    def broken_method(*args, **kwargs):
        raise sqlite3.OperationalError("no such table: fake_table")

    db.list_market_data_readiness_reports_as_of = broken_method
    pack = run_research_context_pack(
        db=db,
        governance_root=governance_root,
        output_root=tmp_path / "output",
        as_of_date="2026-05-01",
        tickers=["AAPL"],
    )
    assert any("db_call_failed" in w for w in pack["warnings"])
