"""Tests for P43 read-only co-pilot console index."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent.research_v1.copilot_console_index import (
    P43_ARTIFACT_DISCLAIMER,
    P43_SCHEMA_VERSION,
    build_copilot_console_index,
    scan_governance_day,
    write_copilot_console_index_artifacts,
)


def _day(root: Path, day: str) -> Path:
    path = root / day
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_empty_governance_root_returns_no_artifacts(tmp_path: Path):
    index = build_copilot_console_index(tmp_path / "governance", "2026-04-30", lookback_days=14)

    assert index["schema_version"] == P43_SCHEMA_VERSION
    assert index["status"] == "console_no_artifacts"
    assert index["summary"]["day_count"] == 0


def test_latest_day_with_p42_json_and_markdown_returns_ready(tmp_path: Path):
    root = tmp_path / "governance"
    day = _day(root, "2026-04-30")
    _write(day / "p42_boss_copilot_daily_brief.json", {"schema_version": "p42", "status": "brief_ready", "source_hash": "h42"})
    (day / "p42_boss_copilot_daily_brief.md").write_text("# P42", encoding="utf-8")

    index = build_copilot_console_index(root, "2026-04-30", lookback_days=14)

    assert index["status"] == "console_ready"
    assert index["summary"]["latest_day"] == "2026-04-30"


def test_latest_day_missing_p42_returns_limited_context(tmp_path: Path):
    root = tmp_path / "governance"
    day = _day(root, "2026-04-30")
    _write(day / "p39_candidate_pool.json", {"schema_version": "p39", "status": "candidate_pool_ready"})

    index = build_copilot_console_index(root, "2026-04-30", lookback_days=14)

    assert index["status"] == "console_limited_context"
    assert "p42_boss_copilot_daily_brief.json" in index["days"][0]["missing_artifacts"]


def test_day_coverage_classifies_present_and_missing(tmp_path: Path):
    root = tmp_path / "governance"
    day = _day(root, "2026-04-30")
    _write(day / "p36_recommendation_outcomes.json", {"schema_version": "p36"})
    _write(day / "p37_market_regime_snapshot.json", {"schema_version": "p37"})

    entry = scan_governance_day(day, root)

    assert "p36_recommendation_outcomes.json" in entry["present_artifacts"]
    assert "p37_market_regime_snapshot.json" in entry["present_artifacts"]
    assert "p42_boss_copilot_daily_brief.json" in entry["missing_artifacts"]
    assert entry["coverage_status"] == "partial"


def test_invalid_json_is_recorded_and_does_not_crash(tmp_path: Path):
    root = tmp_path / "governance"
    day = _day(root, "2026-04-30")
    (day / "p42_boss_copilot_daily_brief.json").write_text("{bad json", encoding="utf-8")

    index = build_copilot_console_index(root, "2026-04-30", lookback_days=14)

    assert index["days"][0]["coverage_status"] == "invalid"
    assert "invalid_json:p42_boss_copilot_daily_brief.json" in index["days"][0]["warnings"]


def test_source_hash_changes_when_artifact_changes(tmp_path: Path):
    root = tmp_path / "governance"
    day = _day(root, "2026-04-30")
    target = day / "p42_boss_copilot_daily_brief.json"
    _write(target, {"schema_version": "p42", "source_hash": "first"})
    first = build_copilot_console_index(root, "2026-04-30", lookback_days=14)
    _write(target, {"schema_version": "p42", "source_hash": "second"})
    second = build_copilot_console_index(root, "2026-04-30", lookback_days=14)

    assert first["source_hash"] != second["source_hash"]


def test_source_hash_changes_when_lookback_window_changes(tmp_path: Path):
    root = tmp_path / "governance"
    day = _day(root, "2026-04-30")
    _write(day / "p42_boss_copilot_daily_brief.json", {"schema_version": "p42", "source_hash": "h42"})
    first = build_copilot_console_index(root, "2026-04-30", lookback_days=14)
    second = build_copilot_console_index(root, "2026-04-30", lookback_days=7)

    assert first["source_hash"] != second["source_hash"]


def test_writers_emit_json_markdown_and_html(tmp_path: Path):
    root = tmp_path / "governance"
    day = _day(root, "2026-04-30")
    _write(day / "p42_boss_copilot_daily_brief.json", {"schema_version": "p42", "status": "brief_ready"})
    (day / "p42_boss_copilot_daily_brief.md").write_text("# P42", encoding="utf-8")
    index = build_copilot_console_index(root, "2026-04-30", lookback_days=14)
    paths = write_copilot_console_index_artifacts(index, root / "2026-04-30")

    assert paths["json"].name == "p43_copilot_console_index.json"
    assert paths["md"].name == "p43_copilot_console_index.md"
    assert paths["html"].name == "p43_copilot_console_index.html"


def test_html_uses_only_relative_links(tmp_path: Path):
    root = tmp_path / "governance"
    day = _day(root, "2026-04-30")
    _write(day / "p42_boss_copilot_daily_brief.json", {"schema_version": "p42", "status": "brief_ready"})
    (day / "p42_boss_copilot_daily_brief.md").write_text("# P42", encoding="utf-8")
    index = build_copilot_console_index(root, "2026-04-30", lookback_days=14)
    paths = write_copilot_console_index_artifacts(index, root / "2026-04-30")
    html_text = paths["html"].read_text(encoding="utf-8")

    assert "http://" not in html_text
    assert "https://" not in html_text
    assert "src=" not in html_text
    assert "<script" not in html_text


def test_markdown_rejects_forbidden_trading_language():
    from agent.research_v1.copilot_console_index import _markdown
    index = {
        "as_of_date": "2026-04-30",
        "status": "console_ready",
        "summary": {"day_count": 1},
        "days": [],
        "disclaimer": "buy this now",
    }
    with pytest.raises(ValueError, match="forbidden"):
        _markdown(index)


def test_html_rejects_forbidden_trading_language():
    from agent.research_v1.copilot_console_index import _html
    index = {
        "as_of_date": "2026-04-30",
        "status": "console_ready",
        "summary": {"day_count": 1},
        "days": [],
        "disclaimer": "trade now",
    }
    with pytest.raises(ValueError, match="forbidden"):
        _html(index)


def test_disclaimer_contains_required_phrase():
    index = build_copilot_console_index(Path("/nonexistent"), "2026-04-30", lookback_days=14)
    assert "static read-only evidence index" in index["disclaimer"]
    assert "static read-only evidence index" in P43_ARTIFACT_DISCLAIMER


# ── P43-B persistence tests ─────────────────────────────────────────────

from agent.research_v1.data.database import ResearchDatabase


def _db(tmp_path: Path) -> ResearchDatabase:
    db = ResearchDatabase(str(tmp_path / "research.db"))
    db.initialize()
    return db


def test_console_index_persistence_is_idempotent(tmp_path: Path):
    db = _db(tmp_path)
    root = tmp_path / "governance"
    day = _day(root, "2026-04-30")
    _write(day / "p42_boss_copilot_daily_brief.json", {"schema_version": "p42", "source_hash": "h42"})
    index = build_copilot_console_index(root, "2026-04-30", lookback_days=14)

    first = db.save_copilot_console_index(index)
    second = db.save_copilot_console_index(index)
    rows = db.list_copilot_console_indexes(as_of_date="2026-04-30")

    assert first == second
    assert len(rows) == 1


def test_revised_console_index_source_hash_appends(tmp_path: Path):
    db = _db(tmp_path)
    root = tmp_path / "governance"
    day = _day(root, "2026-04-30")
    target = day / "p42_boss_copilot_daily_brief.json"
    _write(target, {"schema_version": "p42", "source_hash": "first"})
    first = build_copilot_console_index(root, "2026-04-30", lookback_days=14)
    _write(target, {"schema_version": "p42", "source_hash": "second"})
    second = build_copilot_console_index(root, "2026-04-30", lookback_days=14)

    first_id = db.save_copilot_console_index(first)
    second_id = db.save_copilot_console_index(second)
    rows = db.list_copilot_console_indexes(as_of_date="2026-04-30")

    assert first_id != second_id
    assert len(rows) == 2


# ── P43-C run orchestration and hard-boundary tests ─────────────────────

from agent.research_v1.copilot_console_index import run_copilot_console_index


def test_run_copilot_console_index_writes_and_persists(tmp_path: Path):
    root = tmp_path / "governance"
    day = _day(root, "2026-04-30")
    _write(day / "p42_boss_copilot_daily_brief.json", {"schema_version": "p42", "source_hash": "h42"})
    (day / "p42_boss_copilot_daily_brief.md").write_text("# P42", encoding="utf-8")
    db = _db(tmp_path)

    result = run_copilot_console_index(
        governance_root=root,
        output_root=root,
        as_of_date="2026-04-30",
        lookback_days=14,
        db=db,
    )

    assert result["status"] == "console_ready"
    assert (Path(result["output_dir"]) / "p43_copilot_console_index.html").exists()
    assert len(db.list_copilot_console_indexes(as_of_date="2026-04-30")) == 1


def test_p43_hard_boundaries_are_explicit():
    from agent.research_v1 import copilot_console_index as p43

    forbidden_names = {
        "broker", "order", "train_model", "scheduler", "notification",
        "HermesResearchApp", "run_research", "final_judge", "JudgeInputPacket",
        "CanonicalSignal", "CanonicalReport", "run_governance_runtime",
        "run_recommendation_outcome_tracking", "run_market_regime_context",
        "run_fundamental_quality", "run_candidate_pool", "run_research_memory_pack",
        "run_decision_journal_guardrails", "run_boss_copilot_daily_brief",
        "_extract_thesis_inputs",
    }
    assert not (forbidden_names & set(p43.__dict__))
    assert "static read-only evidence index" in p43.P43_ARTIFACT_DISCLAIMER
