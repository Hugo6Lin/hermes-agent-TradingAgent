"""Tests for P42 boss co-pilot daily brief."""

from __future__ import annotations

from pathlib import Path

from agent.research_v1.boss_copilot_daily_brief import (
    P42_ARTIFACT_DISCLAIMER,
    P42_SCHEMA_VERSION,
    build_boss_copilot_daily_brief,
    compute_boss_copilot_source_hash,
    write_boss_copilot_daily_brief_artifacts,
)


def _candidate(ticker: str = "AAPL", score: float = 0.82, rank: int = 1) -> dict:
    return {
        "item_id": f"item-{ticker}",
        "run_id": "run-1",
        "ticker": ticker,
        "sector": "technology",
        "rank": rank,
        "total_score": score,
        "candidate_category": "quality_momentum",
        "workflow_action": "research_candidate",
        "source_hash": f"cand-{ticker}",
        "missing_context_json": "[]",
        "risk_notes_json": "[]",
        "inclusion_reasons_json": '["high candidate score"]',
    }


def _regime() -> dict:
    return {
        "snapshot_id": "regime-1",
        "as_of_date": "2026-04-30",
        "regime_label": "risk_on_narrow",
        "confidence": 0.72,
        "data_source_hash": "regime-hash",
    }


def _quality(ticker: str = "AAPL", score: float = 0.76) -> dict:
    return {
        "report_id": f"quality-{ticker}",
        "ticker": ticker,
        "overall_quality_score": score,
        "quality_label": "strong",
        "confidence": 0.8,
        "red_flags": [],
        "missing_required_fields": [],
        "source_hash": f"quality-hash-{ticker}",
    }


def _memory(ticker: str = "AAPL") -> dict:
    return {
        "pack_id": f"memory-{ticker}",
        "ticker": ticker,
        "memory_status": "memory_available",
        "source_hash": f"memory-hash-{ticker}",
        "outcome_summary": {"win_rate": 0.6, "evaluated_rows": 3, "median_net_return_pct": 0.04},
        "missing_context": [],
        "risk_memory": [],
        "recurring_themes": ["prior_high_confidence_research"],
    }


def _journal(ticker: str = "AAPL", severity: str = "info") -> dict:
    return {
        "journal_id": f"journal-{ticker}",
        "ticker": ticker,
        "severity": severity,
        "cooling_off_suggestion": "none" if severity == "info" else "recheck_after_30_minutes",
        "source_hash": f"journal-hash-{ticker}-{severity}",
        "entry_json": "{}",
    }


def test_empty_candidate_context_returns_no_candidates():
    brief = build_boss_copilot_daily_brief(
        as_of_date="2026-04-30",
        candidate_run=None,
        candidate_items=[],
        regime_snapshot=_regime(),
        quality_by_ticker={},
        memory_by_ticker={},
        journal_by_ticker={},
        max_priorities=8,
    )

    assert brief["schema_version"] == P42_SCHEMA_VERSION
    assert brief["status"] == "brief_no_candidates"
    assert brief["summary"]["priority_count"] == 0


def test_complete_context_returns_ready_brief():
    brief = build_boss_copilot_daily_brief(
        as_of_date="2026-04-30",
        candidate_run={"run_id": "run-1", "source_hash": "run-hash", "created_at": "2026-04-30T12:00:00Z"},
        candidate_items=[_candidate()],
        regime_snapshot=_regime(),
        quality_by_ticker={"AAPL": _quality()},
        memory_by_ticker={"AAPL": _memory()},
        journal_by_ticker={"AAPL": _journal()},
        max_priorities=8,
    )

    assert brief["status"] == "brief_ready"
    assert brief["priorities"][0]["ticker"] == "AAPL"
    assert brief["priorities"][0]["priority_band"] in {"high_priority", "medium_priority", "low_priority"}


def test_missing_context_returns_limited_context():
    brief = build_boss_copilot_daily_brief(
        as_of_date="2026-04-30",
        candidate_run={"run_id": "run-1", "source_hash": "run-hash"},
        candidate_items=[_candidate()],
        regime_snapshot=None,
        quality_by_ticker={},
        memory_by_ticker={},
        journal_by_ticker={},
        max_priorities=8,
    )

    assert brief["status"] == "brief_limited_context"
    assert "missing_market_regime_context" in brief["priorities"][0]["missing_context"]


def test_manual_review_guardrail_forces_context_blocked():
    brief = build_boss_copilot_daily_brief(
        as_of_date="2026-04-30",
        candidate_run={"run_id": "run-1", "source_hash": "run-hash"},
        candidate_items=[_candidate()],
        regime_snapshot=_regime(),
        quality_by_ticker={"AAPL": _quality()},
        memory_by_ticker={"AAPL": _memory()},
        journal_by_ticker={"AAPL": _journal(severity="manual_review")},
        max_priorities=8,
    )

    assert brief["priorities"][0]["priority_band"] == "context_blocked"
    assert brief["priorities"][0]["suggested_research_action"] == "manual_review_before_any_action"


def test_slow_down_guardrail_lowers_score():
    brief_info = build_boss_copilot_daily_brief(
        as_of_date="2026-04-30",
        candidate_run={"run_id": "run-1", "source_hash": "run-hash"},
        candidate_items=[_candidate()],
        regime_snapshot=_regime(),
        quality_by_ticker={"AAPL": _quality()},
        memory_by_ticker={"AAPL": _memory()},
        journal_by_ticker={"AAPL": _journal(severity="info")},
        max_priorities=8,
    )
    brief_slow = build_boss_copilot_daily_brief(
        as_of_date="2026-04-30",
        candidate_run={"run_id": "run-1", "source_hash": "run-hash"},
        candidate_items=[_candidate()],
        regime_snapshot=_regime(),
        quality_by_ticker={"AAPL": _quality()},
        memory_by_ticker={"AAPL": _memory()},
        journal_by_ticker={"AAPL": _journal(severity="slow_down")},
        max_priorities=8,
    )

    assert brief_slow["priorities"][0]["priority_score"] < brief_info["priorities"][0]["priority_score"]
    assert brief_slow["priorities"][0]["priority_band"] != "context_blocked"


def test_priority_sorting_is_deterministic():
    items = [_candidate(ticker="MSFT", score=0.90, rank=2), _candidate(ticker="AAPL", score=0.82, rank=1)]
    brief = build_boss_copilot_daily_brief(
        as_of_date="2026-04-30",
        candidate_run={"run_id": "run-1", "source_hash": "run-hash"},
        candidate_items=items,
        regime_snapshot=_regime(),
        quality_by_ticker={"AAPL": _quality("AAPL"), "MSFT": _quality("MSFT")},
        memory_by_ticker={"AAPL": _memory("AAPL"), "MSFT": _memory("MSFT")},
        journal_by_ticker={"AAPL": _journal("AAPL"), "MSFT": _journal("MSFT")},
        max_priorities=8,
    )

    scores = [p["priority_score"] for p in brief["priorities"]]
    assert scores == sorted(scores, reverse=True)


def test_source_hash_changes_when_candidate_source_hash_changes():
    first = build_boss_copilot_daily_brief(
        as_of_date="2026-04-30",
        candidate_run={"run_id": "run-1", "source_hash": "run-hash"},
        candidate_items=[_candidate()],
        regime_snapshot=_regime(),
        quality_by_ticker={"AAPL": _quality()},
        memory_by_ticker={"AAPL": _memory()},
        journal_by_ticker={"AAPL": _journal()},
        max_priorities=8,
    )
    changed = _candidate()
    changed["source_hash"] = "changed"
    second = build_boss_copilot_daily_brief(
        as_of_date="2026-04-30",
        candidate_run={"run_id": "run-1", "source_hash": "run-hash"},
        candidate_items=[changed],
        regime_snapshot=_regime(),
        quality_by_ticker={"AAPL": _quality()},
        memory_by_ticker={"AAPL": _memory()},
        journal_by_ticker={"AAPL": _journal()},
        max_priorities=8,
    )

    assert first["source_hash"] != second["source_hash"]


def test_source_hash_changes_when_memory_source_hash_changes():
    first = build_boss_copilot_daily_brief(
        as_of_date="2026-04-30",
        candidate_run={"run_id": "run-1", "source_hash": "run-hash"},
        candidate_items=[_candidate()],
        regime_snapshot=_regime(),
        quality_by_ticker={"AAPL": _quality()},
        memory_by_ticker={"AAPL": _memory()},
        journal_by_ticker={"AAPL": _journal()},
        max_priorities=8,
    )
    changed_mem = _memory()
    changed_mem["source_hash"] = "changed-memory"
    second = build_boss_copilot_daily_brief(
        as_of_date="2026-04-30",
        candidate_run={"run_id": "run-1", "source_hash": "run-hash"},
        candidate_items=[_candidate()],
        regime_snapshot=_regime(),
        quality_by_ticker={"AAPL": _quality()},
        memory_by_ticker={"AAPL": changed_mem},
        journal_by_ticker={"AAPL": _journal()},
        max_priorities=8,
    )

    assert first["source_hash"] != second["source_hash"]


def test_source_hash_is_stable_for_identical_input():
    first = build_boss_copilot_daily_brief(
        as_of_date="2026-04-30",
        candidate_run={"run_id": "run-1", "source_hash": "run-hash"},
        candidate_items=[_candidate()],
        regime_snapshot=_regime(),
        quality_by_ticker={"AAPL": _quality()},
        memory_by_ticker={"AAPL": _memory()},
        journal_by_ticker={"AAPL": _journal()},
        max_priorities=8,
    )
    second = build_boss_copilot_daily_brief(
        as_of_date="2026-04-30",
        candidate_run={"run_id": "run-1", "source_hash": "run-hash"},
        candidate_items=[_candidate()],
        regime_snapshot=_regime(),
        quality_by_ticker={"AAPL": _quality()},
        memory_by_ticker={"AAPL": _memory()},
        journal_by_ticker={"AAPL": _journal()},
        max_priorities=8,
    )

    assert first["source_hash"] == second["source_hash"]


def test_artifact_writer_outputs_safe_markdown(tmp_path: Path):
    brief = build_boss_copilot_daily_brief(
        as_of_date="2026-04-30",
        candidate_run={"run_id": "run-1", "source_hash": "run-hash"},
        candidate_items=[_candidate()],
        regime_snapshot=_regime(),
        quality_by_ticker={"AAPL": _quality()},
        memory_by_ticker={"AAPL": _memory()},
        journal_by_ticker={"AAPL": _journal()},
        max_priorities=8,
    )
    paths = write_boss_copilot_daily_brief_artifacts(brief, tmp_path / "output" / "governance" / "2026-04-30")

    assert paths["json"].name == "p42_boss_copilot_daily_brief.json"
    assert paths["md"].name == "p42_boss_copilot_daily_brief.md"
    assert "daily research-priority evidence only" in paths["md"].read_text(encoding="utf-8")


def test_markdown_rejects_forbidden_trading_language():
    brief = build_boss_copilot_daily_brief(
        as_of_date="2026-04-30",
        candidate_run={"run_id": "run-1", "source_hash": "run-hash"},
        candidate_items=[_candidate()],
        regime_snapshot=_regime(),
        quality_by_ticker={"AAPL": _quality()},
        memory_by_ticker={"AAPL": _memory()},
        journal_by_ticker={"AAPL": _journal()},
        max_priorities=8,
    )
    brief["disclaimer"] = "buy this now disclaimer"
    import pytest
    with pytest.raises(ValueError, match="forbidden"):
        write_boss_copilot_daily_brief_artifacts(brief, Path("/tmp/test_p42_forbidden"))


def test_disclaimer_contains_required_phrase():
    brief = build_boss_copilot_daily_brief(
        as_of_date="2026-04-30",
        candidate_run={"run_id": "run-1", "source_hash": "run-hash"},
        candidate_items=[_candidate()],
        regime_snapshot=_regime(),
        quality_by_ticker={"AAPL": _quality()},
        memory_by_ticker={"AAPL": _memory()},
        journal_by_ticker={"AAPL": _journal()},
        max_priorities=8,
    )
    assert "daily research-priority evidence only" in brief["disclaimer"]
    assert "P42 is daily research-priority evidence only" in P42_ARTIFACT_DISCLAIMER


def test_missing_p38_context_surfaced():
    brief = build_boss_copilot_daily_brief(
        as_of_date="2026-04-30",
        candidate_run={"run_id": "run-1", "source_hash": "run-hash"},
        candidate_items=[_candidate()],
        regime_snapshot=_regime(),
        quality_by_ticker={},
        memory_by_ticker={"AAPL": _memory()},
        journal_by_ticker={"AAPL": _journal()},
        max_priorities=8,
    )

    assert "missing_fundamental_quality" in brief["priorities"][0]["missing_context"]
    assert brief["status"] == "brief_limited_context"


def test_missing_p40_context_surfaced():
    brief = build_boss_copilot_daily_brief(
        as_of_date="2026-04-30",
        candidate_run={"run_id": "run-1", "source_hash": "run-hash"},
        candidate_items=[_candidate()],
        regime_snapshot=_regime(),
        quality_by_ticker={"AAPL": _quality()},
        memory_by_ticker={},
        journal_by_ticker={"AAPL": _journal()},
        max_priorities=8,
    )

    assert "missing_research_memory" in brief["priorities"][0]["missing_context"]


def test_missing_p41_context_surfaced():
    brief = build_boss_copilot_daily_brief(
        as_of_date="2026-04-30",
        candidate_run={"run_id": "run-1", "source_hash": "run-hash"},
        candidate_items=[_candidate()],
        regime_snapshot=_regime(),
        quality_by_ticker={"AAPL": _quality()},
        memory_by_ticker={"AAPL": _memory()},
        journal_by_ticker={},
        max_priorities=8,
    )

    assert "missing_decision_journal" in brief["priorities"][0]["missing_context"]


# ── P42-B persistence tests ─────────────────────────────────────────────

from agent.research_v1.data.database import ResearchDatabase


def _db(tmp_path: Path) -> ResearchDatabase:
    db = ResearchDatabase(str(tmp_path / "research.db"))
    db.initialize()
    return db


def test_boss_copilot_brief_persistence_is_idempotent(tmp_path: Path):
    db = _db(tmp_path)
    brief = build_boss_copilot_daily_brief(
        as_of_date="2026-04-30",
        candidate_run={"run_id": "run-1", "source_hash": "run-hash"},
        candidate_items=[_candidate()],
        regime_snapshot=_regime(),
        quality_by_ticker={"AAPL": _quality()},
        memory_by_ticker={"AAPL": _memory()},
        journal_by_ticker={"AAPL": _journal()},
        max_priorities=8,
    )

    first = db.save_boss_copilot_daily_brief(brief)
    second = db.save_boss_copilot_daily_brief(brief)
    rows = db.list_boss_copilot_daily_briefs(as_of_date="2026-04-30")

    assert first == second
    assert len(rows) == 1


def test_revised_boss_copilot_hash_appends(tmp_path: Path):
    db = _db(tmp_path)
    first = build_boss_copilot_daily_brief(
        as_of_date="2026-04-30",
        candidate_run={"run_id": "run-1", "source_hash": "run-hash"},
        candidate_items=[_candidate()],
        regime_snapshot=_regime(),
        quality_by_ticker={"AAPL": _quality()},
        memory_by_ticker={"AAPL": _memory()},
        journal_by_ticker={"AAPL": _journal()},
        max_priorities=8,
    )
    changed_memory = _memory()
    changed_memory["source_hash"] = "changed-memory"
    second = build_boss_copilot_daily_brief(
        as_of_date="2026-04-30",
        candidate_run={"run_id": "run-1", "source_hash": "run-hash"},
        candidate_items=[_candidate()],
        regime_snapshot=_regime(),
        quality_by_ticker={"AAPL": _quality()},
        memory_by_ticker={"AAPL": changed_memory},
        journal_by_ticker={"AAPL": _journal()},
        max_priorities=8,
    )

    first_id = db.save_boss_copilot_daily_brief(first)
    second_id = db.save_boss_copilot_daily_brief(second)
    rows = db.list_boss_copilot_daily_briefs(as_of_date="2026-04-30")

    assert first_id != second_id
    assert len(rows) == 2


# ── P42-C run orchestration and hard-boundary tests ─────────────────────

from agent.research_v1.boss_copilot_daily_brief import run_boss_copilot_daily_brief


def test_run_boss_copilot_daily_brief_no_candidates_writes_artifacts(tmp_path: Path):
    db = _db(tmp_path)
    result = run_boss_copilot_daily_brief(
        db=db,
        as_of_date="2026-04-30",
        output_root=tmp_path / "output" / "governance",
        max_priorities=8,
    )

    assert result["status"] == "brief_no_candidates"
    assert (Path(result["output_dir"]) / "p42_boss_copilot_daily_brief.json").exists()


def test_p42_hard_boundaries_are_explicit():
    from agent.research_v1 import boss_copilot_daily_brief as p42

    forbidden_names = {
        "broker", "order", "train_model", "scheduler", "notification",
        "HermesResearchApp", "run_research", "final_judge", "JudgeInputPacket",
        "CanonicalSignal", "CanonicalReport", "run_governance_runtime",
        "run_recommendation_outcome_tracking", "run_market_regime_context",
        "run_fundamental_quality", "run_candidate_pool", "run_research_memory_pack",
        "run_decision_journal_guardrails", "_extract_thesis_inputs",
    }
    assert not (forbidden_names & set(p42.__dict__))
    assert "daily research-priority evidence only" in p42.P42_ARTIFACT_DISCLAIMER
