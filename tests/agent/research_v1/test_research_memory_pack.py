"""Tests for P40 research memory pack."""

from __future__ import annotations

import json
from pathlib import Path

from agent.research_v1.research_memory_pack import (
    P40_SCHEMA_VERSION,
    build_research_memory_pack,
    normalize_memory_tickers,
)


def test_normalize_memory_tickers_deduplicates_sorts_and_uppercases():
    assert normalize_memory_tickers([" msft ", "AAPL", "aapl"]) == ["AAPL", "MSFT"]


def test_build_memory_pack_no_prior_memory_records_missing_context():
    pack = build_research_memory_pack(
        ticker="AAPL",
        as_of_date="2026-04-30",
        lookback_days=180,
        records={},
    )

    assert pack["schema_version"] == P40_SCHEMA_VERSION
    assert pack["ticker"] == "AAPL"
    assert pack["memory_status"] == "no_prior_memory"
    assert "missing_research_context" in pack["missing_context"]
    assert "missing_outcome_context" in pack["missing_context"]


def test_latest_research_prefers_decision_card_action():
    report = {
        "report_id": "r1",
        "task_id": "t1",
        "ticker": "AAPL",
        "title": "AAPL report",
        "bottom_line": "Historical context.",
        "why_now": "Prior setup.",
        "created_at": "2026-04-29T10:00:00+00:00",
        "decision_card_json": '{"primary_action":"Buy Stock"}',
        "instrument_rec_json": '{"primary_action":"Watchlist"}',
        "trade_plan_json": '{"action":"BUY"}',
        "risk_watch_json": "[]",
    }
    signal = {"signal_id": "s1", "task_id": "t1", "ticker": "AAPL", "rating": "BULLISH", "confidence": 0.8, "priority_score": 0.7, "created_at": "2026-04-29T10:00:00+00:00", "risk_flags": []}
    pack = build_research_memory_pack("AAPL", "2026-04-30", 180, {"reports": [report], "signals": [signal]})

    assert pack["memory_status"] == "memory_available"
    assert pack["latest_research"]["visible_action"] == "Buy Stock"
    assert "legacy_action_fallback_used" not in pack["risk_memory"]


def test_outcome_summary_counts_and_median():
    signal = {"signal_id": "s1", "task_id": "t1", "ticker": "AAPL", "rating": "BULLISH", "confidence": 0.8, "priority_score": 0.7, "created_at": "2026-04-29T10:00:00+00:00", "risk_flags": []}
    records = {
        "signals": [signal],
        "outcomes_by_signal": {
            "s1": [
                {"status": "evaluated", "net_return_pct": 0.04, "win": True, "evaluated_for_date": "2026-04-30"},
                {"status": "evaluated", "net_return_pct": -0.02, "win": False, "evaluated_for_date": "2026-04-30"},
            ]
        },
    }
    pack = build_research_memory_pack("AAPL", "2026-04-30", 180, records)

    assert pack["outcome_summary"]["evaluated_rows"] == 2
    assert pack["outcome_summary"]["win_rate"] == 0.5
    assert pack["outcome_summary"]["median_net_return_pct"] == 0.01


def test_prior_signals_sorted_deterministically():
    records = {
        "signals": [
            {"signal_id": "s1", "task_id": "t1", "ticker": "AAPL", "rating": "BULLISH", "confidence": 0.7, "priority_score": 0.6, "created_at": "2026-04-28T10:00:00+00:00", "risk_flags": []},
            {"signal_id": "s2", "task_id": "t2", "ticker": "AAPL", "rating": "NEUTRAL", "confidence": 0.5, "priority_score": 0.4, "created_at": "2026-04-29T10:00:00+00:00", "risk_flags": []},
        ],
    }
    pack = build_research_memory_pack("AAPL", "2026-04-30", 180, records)

    assert len(pack["prior_signals"]) == 2
    assert pack["prior_signals"][0]["signal_id"] == "s2"
    assert pack["prior_signals"][1]["signal_id"] == "s1"


def test_legacy_action_fallback_is_marked():
    report = {
        "report_id": "r1",
        "task_id": "t1",
        "ticker": "AAPL",
        "title": "AAPL report",
        "created_at": "2026-04-29T10:00:00+00:00",
        "trade_plan_json": '{"action":"BUY"}',
    }
    pack = build_research_memory_pack("AAPL", "2026-04-30", 180, {"reports": [report]})

    assert pack["latest_research"]["visible_action"] == "BUY"
    assert "legacy_action_fallback_used" in pack["risk_memory"]


def test_candidate_history_summarizes_p39_appearances():
    records = {
        "candidate_items": [
            {"item_id": "i1", "ticker": "AAPL", "created_at": "2026-04-29", "source_hash": "h1", "candidate_category": "quality_momentum", "workflow_action": "research_candidate", "total_score": 0.82, "inclusion_reasons_json": '["strong_momentum"]', "missing_context_json": "[]"},
            {"item_id": "i2", "ticker": "AAPL", "created_at": "2026-04-28", "source_hash": "h2", "candidate_category": "quality_momentum", "workflow_action": "monitor_candidate", "total_score": 0.75, "inclusion_reasons_json": '["strong_momentum"]', "missing_context_json": "[]"},
        ],
    }
    pack = build_research_memory_pack("AAPL", "2026-04-30", 180, records)

    assert pack["candidate_history"]["appearance_count"] == 2
    assert pack["candidate_history"]["best_total_score"] == 0.82
    assert "missing_candidate_history" not in pack["missing_context"]


def test_quality_context_includes_p38_report():
    records = {
        "quality_report": {
            "as_of_date": "2026-04-29",
            "quality_label": "compounder_quality",
            "overall_quality_score": 0.85,
            "confidence": 0.90,
            "red_flags": [],
            "missing_required_fields": [],
            "source_hash": "q1",
        },
    }
    pack = build_research_memory_pack("AAPL", "2026-04-30", 180, records)

    assert pack["quality_context"]["quality_label"] == "compounder_quality"
    assert pack["quality_context"]["source_hash"] == "q1"
    assert "missing_fundamental_quality" not in pack["missing_context"]


def test_regime_context_includes_p37_snapshot():
    records = {
        "regime_snapshot": {
            "as_of_date": "2026-04-29",
            "regime_label": "risk_on_broad",
            "confidence": 0.90,
            "data_source_hash": "r1",
        },
    }
    pack = build_research_memory_pack("AAPL", "2026-04-30", 180, records)

    assert pack["regime_context"]["regime_label"] == "risk_on_broad"
    assert "missing_market_regime_context" not in pack["missing_context"]


def test_missing_optional_tables_record_warnings():
    pack = build_research_memory_pack("AAPL", "2026-04-30", 180, {})

    assert "missing_research_context" in pack["missing_context"]
    assert "missing_outcome_context" in pack["missing_context"]
    assert "missing_candidate_history" in pack["missing_context"]
    assert "missing_fundamental_quality" in pack["missing_context"]
    assert "missing_market_regime_context" in pack["missing_context"]
    assert "missing_watchlist_context" in pack["missing_context"]
    assert "missing_validation_context" in pack["missing_context"]


def test_recurring_themes_are_deterministic():
    records = {
        "candidate_items": [
            {"item_id": "i1", "ticker": "AAPL", "created_at": "2026-04-29", "source_hash": "h1", "candidate_category": "quality_momentum", "workflow_action": "research_candidate", "total_score": 0.82, "inclusion_reasons_json": '["strong_momentum"]', "missing_context_json": "[]"},
        ],
        "quality_report": {
            "as_of_date": "2026-04-29",
            "quality_label": "compounder_quality",
            "overall_quality_score": 0.85,
            "confidence": 0.90,
            "red_flags": [],
            "missing_required_fields": [],
            "source_hash": "q1",
        },
    }
    pack1 = build_research_memory_pack("AAPL", "2026-04-30", 180, records)
    pack2 = build_research_memory_pack("AAPL", "2026-04-30", 180, records)

    assert pack1["recurring_themes"] == pack2["recurring_themes"]
    assert isinstance(pack1["recurring_themes"], list)


def test_risk_memory_is_deterministic():
    report = {
        "report_id": "r1",
        "task_id": "t1",
        "ticker": "AAPL",
        "title": "AAPL report",
        "created_at": "2026-04-29T10:00:00+00:00",
        "trade_plan_json": '{"action":"BUY"}',
    }
    records = {"reports": [report]}
    pack1 = build_research_memory_pack("AAPL", "2026-04-30", 180, records)
    pack2 = build_research_memory_pack("AAPL", "2026-04-30", 180, records)

    assert pack1["risk_memory"] == pack2["risk_memory"]


def test_source_hash_changes_on_signal_change():
    base_records = {
        "signals": [
            {"signal_id": "s1", "task_id": "t1", "ticker": "AAPL", "rating": "BULLISH", "confidence": 0.8, "priority_score": 0.7, "created_at": "2026-04-29T10:00:00+00:00", "risk_flags": []},
        ],
    }
    changed_records = {
        "signals": [
            {"signal_id": "s1", "task_id": "t1", "ticker": "AAPL", "rating": "BULLISH", "confidence": 0.9, "priority_score": 0.7, "created_at": "2026-04-29T10:00:00+00:00", "risk_flags": []},
        ],
    }
    pack1 = build_research_memory_pack("AAPL", "2026-04-30", 180, base_records)
    pack2 = build_research_memory_pack("AAPL", "2026-04-30", 180, changed_records)

    assert pack1["source_hash"] != pack2["source_hash"]


def test_limited_memory_status_when_only_context_exists():
    records = {
        "quality_report": {
            "as_of_date": "2026-04-29",
            "quality_label": "solid_quality",
            "overall_quality_score": 0.65,
            "confidence": 0.80,
            "red_flags": [],
            "missing_required_fields": [],
            "source_hash": "q1",
        },
    }
    pack = build_research_memory_pack("AAPL", "2026-04-30", 180, records)

    assert pack["memory_status"] == "limited_memory"


def test_disclaimer_contains_required_phrase():
    pack = build_research_memory_pack("AAPL", "2026-04-30", 180, {})
    assert "research-memory evidence only" in pack["disclaimer"]


# ── P40-B persistence and artifact tests ─────────────────────────────────

from agent.research_v1.data.database import ResearchDatabase
from agent.research_v1.research_memory_pack import write_research_memory_artifacts


def _db(tmp_path: Path) -> ResearchDatabase:
    db = ResearchDatabase(str(tmp_path / "research.db"))
    db.initialize()
    db.initialize_memory_pack_schema()
    return db


def test_memory_pack_persistence_is_idempotent(tmp_path: Path):
    db = _db(tmp_path)
    pack = build_research_memory_pack("AAPL", "2026-04-30", 180, {})

    first = db.save_research_memory_pack(pack)
    second = db.save_research_memory_pack(pack)
    rows = db.list_research_memory_packs(ticker="AAPL", as_of_date="2026-04-30")

    assert first == second
    assert len(rows) == 1


def test_revised_memory_pack_source_hash_appends(tmp_path: Path):
    db = _db(tmp_path)
    first_pack = build_research_memory_pack("AAPL", "2026-04-30", 180, {})
    second_pack = build_research_memory_pack("AAPL", "2026-04-30", 180, {"candidate_items": [{"item_id": "i1", "source_hash": "changed", "created_at": "2026-04-29"}]})

    first = db.save_research_memory_pack(first_pack)
    second = db.save_research_memory_pack(second_pack)
    rows = db.list_research_memory_packs(ticker="AAPL", as_of_date="2026-04-30")

    assert first != second
    assert len(rows) == 2


def test_memory_artifacts_are_written_and_safe(tmp_path: Path):
    pack = build_research_memory_pack("AAPL", "2026-04-30", 180, {})
    payload = {
        "schema_version": P40_SCHEMA_VERSION,
        "as_of_date": "2026-04-30",
        "created_at": pack["created_at"],
        "status": "completed",
        "packs": [pack],
        "summary": {"ticker_count": 1, "memory_available": 0, "limited_memory": 0, "no_prior_memory": 1},
        "warnings": [],
        "disclaimer": pack["disclaimer"],
    }
    paths = write_research_memory_artifacts(payload, tmp_path / "output" / "governance" / "2026-04-30")
    text = paths["md"].read_text(encoding="utf-8").lower()

    assert paths["json"].name == "p40_research_memory_pack.json"
    assert "p40 is research-memory evidence only" in text
    assert "trade now" not in text


# ── P40-C run orchestration and hard-boundary tests ──────────────────────

from agent.research_v1.research_memory_pack import run_research_memory_pack


def test_run_research_memory_pack_persists_and_writes_artifacts(tmp_path: Path):
    db = _db(tmp_path)
    result = run_research_memory_pack(
        db=db,
        tickers=["AAPL"],
        as_of_date="2026-04-30",
        lookback_days=180,
        output_root=tmp_path / "output" / "governance",
    )

    assert result["ticker_count"] == 1
    assert (Path(result["output_dir"]) / "p40_research_memory_pack.json").exists()


def test_p40_hard_boundaries_are_explicit():
    from agent.research_v1 import research_memory_pack as p40

    forbidden_names = {
        "broker", "order", "train_model", "scheduler", "notification",
        "HermesResearchApp", "run_research", "final_judge", "JudgeInputPacket",
        "CanonicalSignal", "CanonicalReport", "run_governance_runtime",
        "run_recommendation_outcome_tracking", "run_market_regime_context",
        "run_fundamental_quality", "run_candidate_pool", "_extract_thesis_inputs",
    }
    assert not (forbidden_names & set(p40.__dict__))
    assert "research-memory evidence only" in p40.P40_ARTIFACT_DISCLAIMER


# ── As-of semantics regression tests ─────────────────────────────────────

def test_future_outcome_excluded_from_as_of_memory_pack():
    """P1: outcomes with evaluated_for_date > as_of_date must be filtered out."""
    signal = {"signal_id": "s1", "task_id": "t1", "ticker": "AAPL", "rating": "BULLISH", "confidence": 0.8, "priority_score": 0.7, "created_at": "2026-04-29T10:00:00+00:00", "risk_flags": []}
    records = {
        "signals": [signal],
        "outcomes_by_signal": {
            "s1": [
                {"status": "evaluated", "net_return_pct": 0.04, "win": True, "evaluated_for_date": "2026-04-30"},
                {"status": "evaluated", "net_return_pct": 0.10, "win": True, "evaluated_for_date": "2026-05-30"},
            ]
        },
    }
    pack = build_research_memory_pack("AAPL", "2026-04-30", 180, records)

    assert pack["outcome_summary"]["total_outcome_rows"] == 1
    assert pack["outcome_summary"]["evaluated_rows"] == 1
    assert pack["outcome_summary"]["win_rate"] == 1.0
    assert pack["outcome_summary"]["latest_outcome_date"] == "2026-04-30"


def test_stale_theme_uses_as_of_date_not_wall_clock():
    """P2: stale_research_context must depend on as_of_date, not when the command runs."""
    report = {
        "report_id": "r1",
        "task_id": "t1",
        "ticker": "AAPL",
        "title": "AAPL report",
        "created_at": "2026-01-01T10:00:00+00:00",
        "decision_card_json": '{"primary_action":"Buy Stock"}',
    }
    records = {"reports": [report]}

    # as_of 2026-02-01: only 31 days, not stale
    pack_not_stale = build_research_memory_pack("AAPL", "2026-02-01", 180, records)
    assert "stale_research_context" not in pack_not_stale["recurring_themes"]

    # as_of 2026-04-30: 119 days, stale
    pack_stale = build_research_memory_pack("AAPL", "2026-04-30", 180, records)
    assert "stale_research_context" in pack_stale["recurring_themes"]
