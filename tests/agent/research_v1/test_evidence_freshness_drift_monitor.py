"""Tests for P44 evidence freshness and drift monitor."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent.research_v1.evidence_freshness_drift_monitor import (
    P44_ARTIFACT_DISCLAIMER,
    P44_SCHEMA_VERSION,
    build_evidence_freshness_drift_report,
    write_evidence_freshness_drift_artifacts,
)


def _artifact(root: Path, day: str, name: str, payload: dict) -> Path:
    path = root / day
    path.mkdir(parents=True, exist_ok=True)
    target = path / name
    target.write_text(json.dumps(payload), encoding="utf-8")
    return target


def _phase_row(phase_id: str, as_of_date: str = "2026-04-30", source_hash: str = "h1") -> dict:
    return {
        "phase_id": phase_id,
        "as_of_date": as_of_date,
        "created_at": f"{as_of_date}T12:00:00+00:00",
        "source_hash": source_hash,
        "payload": {},
    }


def test_empty_window_returns_red_with_missing_phases(tmp_path: Path):
    report = build_evidence_freshness_drift_report(
        as_of_date="2026-04-30",
        lookback_days=14,
        freshness_days=3,
        phase_rows={},
        governance_root=tmp_path / "governance",
    )

    assert report["schema_version"] == P44_SCHEMA_VERSION
    assert report["status"] == "monitor_red"
    assert all(p["freshness_status"] == "missing" for p in report["phase_monitors"])


def test_complete_fresh_evidence_returns_green(tmp_path: Path):
    root = tmp_path / "governance"
    phase_rows = {}
    for phase in ("P36", "P37", "P38", "P39", "P40", "P41", "P42", "P43"):
        phase_rows[phase] = [_phase_row(phase)]
    for _, _, artifact_name in (
        ("P36", "recommendation_outcomes", "p36_recommendation_outcomes.json"),
        ("P37", "market_regime", "p37_market_regime_snapshot.json"),
        ("P38", "fundamental_quality", "p38_fundamental_quality.json"),
        ("P39", "candidate_pool", "p39_candidate_pool.json"),
        ("P40", "research_memory", "p40_research_memory_pack.json"),
        ("P41", "decision_journal", "p41_decision_journal.json"),
        ("P42", "boss_copilot_brief", "p42_boss_copilot_daily_brief.json"),
        ("P43", "copilot_console_index", "p43_copilot_console_index.json"),
    ):
        _artifact(root, "2026-04-30", artifact_name, {"schema_version": "x", "source_hash": artifact_name})

    report = build_evidence_freshness_drift_report(
        as_of_date="2026-04-30",
        lookback_days=14,
        freshness_days=3,
        phase_rows=phase_rows,
        governance_root=root,
    )

    assert report["status"] == "monitor_green"
    assert report["summary"]["red_count"] == 0


def test_stale_evidence_returns_yellow(tmp_path: Path):
    root = tmp_path / "governance"
    phase_rows = {}
    for phase in ("P36", "P37", "P38", "P39", "P40", "P41", "P43"):
        phase_rows[phase] = [_phase_row(phase)]
    phase_rows["P42"] = [_phase_row("P42", as_of_date="2026-04-20")]
    for _, _, artifact_name in (
        ("P36", "recommendation_outcomes", "p36_recommendation_outcomes.json"),
        ("P37", "market_regime", "p37_market_regime_snapshot.json"),
        ("P38", "fundamental_quality", "p38_fundamental_quality.json"),
        ("P39", "candidate_pool", "p39_candidate_pool.json"),
        ("P40", "research_memory", "p40_research_memory_pack.json"),
        ("P41", "decision_journal", "p41_decision_journal.json"),
        ("P43", "copilot_console_index", "p43_copilot_console_index.json"),
    ):
        _artifact(root, "2026-04-30", artifact_name, {"schema_version": "x", "source_hash": artifact_name})

    report = build_evidence_freshness_drift_report(
        as_of_date="2026-04-30",
        lookback_days=14,
        freshness_days=3,
        phase_rows=phase_rows,
        governance_root=root,
    )

    p42 = next(p for p in report["phase_monitors"] if p["phase_id"] == "P42")
    assert p42["freshness_status"] == "stale"
    assert report["status"] == "monitor_yellow"


def test_invalid_artifact_json_returns_red(tmp_path: Path):
    root = tmp_path / "governance"
    day = root / "2026-04-30"
    day.mkdir(parents=True, exist_ok=True)
    (day / "p42_boss_copilot_daily_brief.json").write_text("{bad json", encoding="utf-8")

    report = build_evidence_freshness_drift_report(
        as_of_date="2026-04-30",
        lookback_days=14,
        freshness_days=3,
        phase_rows={},
        governance_root=root,
    )

    p42 = next(p for p in report["phase_monitors"] if p["phase_id"] == "P42")
    assert p42["freshness_status"] == "invalid"
    assert p42["coverage_status"] == "invalid"
    assert report["status"] == "monitor_red"


def test_three_unique_source_hashes_produce_high_churn(tmp_path: Path):
    phase_rows = {
        "P42": [
            _phase_row("P42", source_hash="h1"),
            _phase_row("P42", source_hash="h2"),
            _phase_row("P42", source_hash="h3"),
        ],
    }
    report = build_evidence_freshness_drift_report(
        as_of_date="2026-04-30",
        lookback_days=14,
        freshness_days=3,
        phase_rows=phase_rows,
        governance_root=tmp_path / "governance",
    )

    p42 = next(p for p in report["phase_monitors"] if p["phase_id"] == "P42")
    assert p42["churn_status"] == "high_churn"


def test_missing_context_patterns_aggregate_from_p40_p42_p43(tmp_path: Path):
    phase_rows = {
        "P40": [
            {"phase_id": "P40", "as_of_date": "2026-04-30", "created_at": "", "source_hash": "h1",
             "payload": {"missing_context": ["missing_fundamental_quality", "missing_regime"]}},
        ],
        "P42": [
            {"phase_id": "P42", "as_of_date": "2026-04-30", "created_at": "", "source_hash": "h1",
             "payload": {"summary": {"missing_context_counts": {"missing_fundamental_quality": 1}}}},
        ],
        "P43": [
            {"phase_id": "P43", "as_of_date": "2026-04-30", "created_at": "", "source_hash": "h1",
             "payload": {"days": [{"missing_artifacts": ["p38_fundamental_quality.json"]}, {"missing_artifacts": ["p38_fundamental_quality.json"]}]}},
        ],
    }
    report = build_evidence_freshness_drift_report(
        as_of_date="2026-04-30",
        lookback_days=14,
        freshness_days=3,
        phase_rows=phase_rows,
        governance_root=tmp_path / "governance",
    )

    patterns = report["missing_context_patterns"]
    keys = {p["key"] for p in patterns}
    assert "missing_fundamental_quality" in keys
    assert "missing_regime" in keys
    assert "p38_fundamental_quality.json" in keys
    # Sorted by count descending
    assert patterns[0]["count"] >= patterns[-1]["count"]


def test_source_hash_changes_when_upstream_latest_changes(tmp_path: Path):
    first = build_evidence_freshness_drift_report(
        as_of_date="2026-04-30",
        lookback_days=14,
        freshness_days=3,
        phase_rows={"P42": [_phase_row("P42", source_hash="h1")]},
        governance_root=tmp_path / "governance",
    )
    second = build_evidence_freshness_drift_report(
        as_of_date="2026-04-30",
        lookback_days=14,
        freshness_days=3,
        phase_rows={"P42": [_phase_row("P42", source_hash="h2")]},
        governance_root=tmp_path / "governance",
    )

    assert first["source_hash"] != second["source_hash"]


def test_source_hash_is_stable_for_identical_input(tmp_path: Path):
    kwargs = dict(
        as_of_date="2026-04-30",
        lookback_days=14,
        freshness_days=3,
        phase_rows={"P42": [_phase_row("P42")]},
        governance_root=tmp_path / "governance",
    )
    first = build_evidence_freshness_drift_report(**kwargs)
    second = build_evidence_freshness_drift_report(**kwargs)

    assert first["source_hash"] == second["source_hash"]


def test_writer_emits_json_and_markdown(tmp_path: Path):
    report = build_evidence_freshness_drift_report(
        as_of_date="2026-04-30",
        lookback_days=14,
        freshness_days=3,
        phase_rows={},
        governance_root=tmp_path / "governance",
    )
    paths = write_evidence_freshness_drift_artifacts(report, tmp_path / "output" / "governance" / "2026-04-30")

    assert paths["json"].name == "p44_evidence_freshness_drift_monitor.json"
    assert paths["md"].name == "p44_evidence_freshness_drift_monitor.md"


def test_markdown_rejects_forbidden_trading_language():
    from agent.research_v1.evidence_freshness_drift_monitor import _markdown

    report = {
        "as_of_date": "2026-04-30",
        "status": "monitor_green",
        "phase_monitors": [],
        "missing_context_patterns": [],
        "disclaimer": "buy this now",
    }
    with pytest.raises(ValueError, match="forbidden"):
        _markdown(report)


def test_disclaimer_contains_required_phrase():
    report = build_evidence_freshness_drift_report(
        as_of_date="2026-04-30",
        lookback_days=14,
        freshness_days=3,
        phase_rows={},
        governance_root=Path("/nonexistent"),
    )
    assert "evidence freshness and drift monitoring only" in report["disclaimer"]
    assert "evidence freshness and drift monitoring only" in P44_ARTIFACT_DISCLAIMER


def test_markdown_includes_all_required_sections(tmp_path: Path):
    from agent.research_v1.evidence_freshness_drift_monitor import _markdown

    report = build_evidence_freshness_drift_report(
        as_of_date="2026-04-30",
        lookback_days=14,
        freshness_days=3,
        phase_rows={"P42": [_phase_row("P42")]},
        governance_root=tmp_path / "governance",
    )
    md = _markdown(report)

    assert "Phase Freshness" in md
    assert "Missing Context Patterns" in md
    assert "Recommended" in md or "Action" in md
    assert "disclaimer" in md.lower() or "monitoring only" in md.lower()


def test_report_id_changes_when_source_hash_changes(tmp_path: Path):
    first = build_evidence_freshness_drift_report(
        as_of_date="2026-04-30",
        lookback_days=14,
        freshness_days=3,
        phase_rows={"P42": [_phase_row("P42", source_hash="h1")]},
        governance_root=tmp_path / "governance",
    )
    second = build_evidence_freshness_drift_report(
        as_of_date="2026-04-30",
        lookback_days=14,
        freshness_days=3,
        phase_rows={"P42": [_phase_row("P42", source_hash="h2")]},
        governance_root=tmp_path / "governance",
    )

    assert first["report_id"] != second["report_id"]


def test_fresh_within_threshold(tmp_path: Path):
    phase_rows = {"P42": [_phase_row("P42", as_of_date="2026-04-29")]}
    report = build_evidence_freshness_drift_report(
        as_of_date="2026-04-30",
        lookback_days=14,
        freshness_days=3,
        phase_rows=phase_rows,
        governance_root=tmp_path / "governance",
    )

    p42 = next(p for p in report["phase_monitors"] if p["phase_id"] == "P42")
    assert p42["freshness_status"] == "fresh"


def test_stable_churn_with_single_hash(tmp_path: Path):
    phase_rows = {
        "P42": [_phase_row("P42", source_hash="same"), _phase_row("P42", source_hash="same")],
    }
    report = build_evidence_freshness_drift_report(
        as_of_date="2026-04-30",
        lookback_days=14,
        freshness_days=3,
        phase_rows=phase_rows,
        governance_root=tmp_path / "governance",
    )

    p42 = next(p for p in report["phase_monitors"] if p["phase_id"] == "P42")
    assert p42["churn_status"] == "stable"


def test_changed_churn_with_two_hashes(tmp_path: Path):
    phase_rows = {"P42": [_phase_row("P42", source_hash="h1"), _phase_row("P42", source_hash="h2")]}
    report = build_evidence_freshness_drift_report(
        as_of_date="2026-04-30",
        lookback_days=14,
        freshness_days=3,
        phase_rows=phase_rows,
        governance_root=tmp_path / "governance",
    )

    p42 = next(p for p in report["phase_monitors"] if p["phase_id"] == "P42")
    assert p42["churn_status"] == "changed"


def test_unknown_churn_with_no_hashes(tmp_path: Path):
    phase_rows = {"P42": [_phase_row("P42", source_hash="")]}
    report = build_evidence_freshness_drift_report(
        as_of_date="2026-04-30",
        lookback_days=14,
        freshness_days=3,
        phase_rows=phase_rows,
        governance_root=tmp_path / "governance",
    )

    p42 = next(p for p in report["phase_monitors"] if p["phase_id"] == "P42")
    assert p42["churn_status"] == "unknown"


# ── P44-B persistence tests ─────────────────────────────────────────────

from agent.research_v1.data.database import ResearchDatabase


def _db(tmp_path: Path) -> ResearchDatabase:
    db = ResearchDatabase(str(tmp_path / "research.db"))
    db.initialize()
    return db


def test_evidence_monitor_persistence_is_idempotent(tmp_path: Path):
    db = _db(tmp_path)
    report = build_evidence_freshness_drift_report(
        as_of_date="2026-04-30",
        lookback_days=14,
        freshness_days=3,
        phase_rows={},
        governance_root=tmp_path / "governance",
    )
    first = db.save_evidence_freshness_drift_report(report)
    second = db.save_evidence_freshness_drift_report(report)
    rows = db.list_evidence_freshness_drift_reports(as_of_date="2026-04-30")

    assert first == second
    assert len(rows) == 1


def test_revised_source_hash_appends(tmp_path: Path):
    db = _db(tmp_path)
    first = build_evidence_freshness_drift_report(
        as_of_date="2026-04-30",
        lookback_days=14,
        freshness_days=3,
        phase_rows={"P42": [_phase_row("P42", source_hash="h1")]},
        governance_root=tmp_path / "governance",
    )
    second = build_evidence_freshness_drift_report(
        as_of_date="2026-04-30",
        lookback_days=14,
        freshness_days=3,
        phase_rows={"P42": [_phase_row("P42", source_hash="h2")]},
        governance_root=tmp_path / "governance",
    )

    first_id = db.save_evidence_freshness_drift_report(first)
    second_id = db.save_evidence_freshness_drift_report(second)
    rows = db.list_evidence_freshness_drift_reports(as_of_date="2026-04-30")

    assert first_id != second_id
    assert len(rows) == 2


# ── P44-C runtime and hard-boundary tests ──────────────────────────────

from agent.research_v1.evidence_freshness_drift_monitor import run_evidence_freshness_drift_monitor


def test_runtime_rejects_invalid_date(tmp_path: Path):
    db = _db(tmp_path)
    result = run_evidence_freshness_drift_monitor(
        db=db,
        governance_root=tmp_path / "governance",
        output_root=tmp_path / "output",
        as_of_date="not-a-date",
        lookback_days=14,
        freshness_days=3,
    )

    assert result["status"] == "blocked_invalid_input"


def test_runtime_rejects_non_positive_lookback(tmp_path: Path):
    db = _db(tmp_path)
    result = run_evidence_freshness_drift_monitor(
        db=db,
        governance_root=tmp_path / "governance",
        output_root=tmp_path / "output",
        as_of_date="2026-04-30",
        lookback_days=0,
        freshness_days=3,
    )

    assert result["status"] == "blocked_invalid_input"


def test_runtime_rejects_non_positive_freshness(tmp_path: Path):
    db = _db(tmp_path)
    result = run_evidence_freshness_drift_monitor(
        db=db,
        governance_root=tmp_path / "governance",
        output_root=tmp_path / "output",
        as_of_date="2026-04-30",
        lookback_days=14,
        freshness_days=0,
    )

    assert result["status"] == "blocked_invalid_input"


def test_runtime_rejects_non_directory_governance_root(tmp_path: Path):
    db = _db(tmp_path)
    file_root = tmp_path / "governance"
    file_root.write_text("not a directory", encoding="utf-8")

    result = run_evidence_freshness_drift_monitor(
        db=db,
        governance_root=file_root,
        output_root=tmp_path / "output",
        as_of_date="2026-04-30",
        lookback_days=14,
        freshness_days=3,
    )

    assert result["status"] == "blocked_invalid_input"
    assert "governance_root_not_a_directory" in result["warnings"]


def test_runtime_writes_and_persists(tmp_path: Path):
    db = _db(tmp_path)
    result = run_evidence_freshness_drift_monitor(
        db=db,
        governance_root=tmp_path / "governance",
        output_root=tmp_path / "output" / "governance",
        as_of_date="2026-04-30",
        lookback_days=14,
        freshness_days=3,
    )

    assert Path(result["output_dir"]).joinpath("p44_evidence_freshness_drift_monitor.json").exists()
    assert Path(result["output_dir"]).joinpath("p44_evidence_freshness_drift_monitor.md").exists()
    assert len(db.list_evidence_freshness_drift_reports(as_of_date="2026-04-30")) == 1


def test_p44_hard_boundaries_are_explicit():
    from agent.research_v1 import evidence_freshness_drift_monitor as p44

    forbidden_names = {
        "broker", "order", "train_model", "scheduler", "notification",
        "HermesResearchApp", "run_research", "final_judge", "JudgeInputPacket",
        "CanonicalSignal", "CanonicalReport", "run_governance_runtime",
        "run_recommendation_outcome_tracking", "run_market_regime_context",
        "run_fundamental_quality", "run_candidate_pool", "run_research_memory_pack",
        "run_decision_journal_guardrails", "run_boss_copilot_daily_brief",
        "run_copilot_console_index", "_extract_thesis_inputs",
    }
    assert not (forbidden_names & set(p44.__dict__))
    assert "evidence freshness and drift monitoring only" in p44.P44_ARTIFACT_DISCLAIMER


def test_warning_appears_in_markdown(tmp_path: Path):
    from agent.research_v1.evidence_freshness_drift_monitor import _markdown

    root = tmp_path / "governance"
    day = root / "2026-04-30"
    day.mkdir(parents=True, exist_ok=True)
    (day / "p42_boss_copilot_daily_brief.json").write_text("{bad json", encoding="utf-8")

    report = build_evidence_freshness_drift_report(
        as_of_date="2026-04-30",
        lookback_days=14,
        freshness_days=3,
        phase_rows={},
        governance_root=root,
    )
    md = _markdown(report)

    assert "invalid_json:p42_boss_copilot_daily_brief.json" in md


def test_recommended_actions_in_markdown(tmp_path: Path):
    from agent.research_v1.evidence_freshness_drift_monitor import _markdown

    report = build_evidence_freshness_drift_report(
        as_of_date="2026-04-30",
        lookback_days=14,
        freshness_days=3,
        phase_rows={},
        governance_root=tmp_path / "governance",
    )
    md = _markdown(report)

    assert "collect_missing_evidence" in md


# ── Audit regression tests ──────────────────────────────────────────────

def test_artifact_content_revision_changes_source_hash(tmp_path: Path):
    """Same-date valid JSON artifact content changes while row inputs stay identical."""
    root = tmp_path / "governance"
    day = root / "2026-04-30"
    day.mkdir(parents=True, exist_ok=True)
    target = day / "p42_boss_copilot_daily_brief.json"
    target.write_text(json.dumps({"schema_version": "p42", "status": "v1"}), encoding="utf-8")
    first = build_evidence_freshness_drift_report(
        as_of_date="2026-04-30",
        lookback_days=14,
        freshness_days=3,
        phase_rows={},
        governance_root=root,
    )
    target.write_text(json.dumps({"schema_version": "p42", "status": "v2"}), encoding="utf-8")
    second = build_evidence_freshness_drift_report(
        as_of_date="2026-04-30",
        lookback_days=14,
        freshness_days=3,
        phase_rows={},
        governance_root=root,
    )

    assert first["source_hash"] != second["source_hash"]


def test_newer_valid_artifact_supersedes_older_invalid(tmp_path: Path):
    """Stale bad JSON from 2026-04-29 does not poison a valid 2026-04-30 artifact."""
    root = tmp_path / "governance"
    old_day = root / "2026-04-29"
    old_day.mkdir(parents=True, exist_ok=True)
    (old_day / "p42_boss_copilot_daily_brief.json").write_text("{bad json", encoding="utf-8")
    new_day = root / "2026-04-30"
    new_day.mkdir(parents=True, exist_ok=True)
    (new_day / "p42_boss_copilot_daily_brief.json").write_text(
        json.dumps({"schema_version": "p42", "status": "brief_ready"}), encoding="utf-8",
    )

    report = build_evidence_freshness_drift_report(
        as_of_date="2026-04-30",
        lookback_days=14,
        freshness_days=3,
        phase_rows={},
        governance_root=root,
    )

    p42 = next(p for p in report["phase_monitors"] if p["phase_id"] == "P42")
    assert p42["freshness_status"] != "invalid"
    assert p42["coverage_status"] != "invalid"
    assert not p42["warnings"]


def test_coverage_partial_when_artifact_older_than_latest_evidence(tmp_path: Path):
    """Fresh DB row for 2026-04-30 but artifact only from 2026-04-20 → partial."""
    root = tmp_path / "governance"
    old_day = root / "2026-04-20"
    old_day.mkdir(parents=True, exist_ok=True)
    (old_day / "p42_boss_copilot_daily_brief.json").write_text(
        json.dumps({"schema_version": "p42"}), encoding="utf-8",
    )
    phase_rows = {"P42": [_phase_row("P42", as_of_date="2026-04-30")]}

    report = build_evidence_freshness_drift_report(
        as_of_date="2026-04-30",
        lookback_days=14,
        freshness_days=3,
        phase_rows=phase_rows,
        governance_root=root,
    )

    p42 = next(p for p in report["phase_monitors"] if p["phase_id"] == "P42")
    assert p42["coverage_status"] == "partial"


def test_p40_missing_context_aggregated_from_db(tmp_path: Path):
    """P40 missing_context_json column maps to payload['missing_context']."""
    db = _db(tmp_path)
    db.initialize_memory_pack_schema()
    conn = db._get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR IGNORE INTO research_memory_packs
        (pack_id, schema_version, as_of_date, created_at, ticker, lookback_days,
         memory_status, source_hash, latest_research_json, outcome_summary_json,
         candidate_history_json, quality_context_json, regime_context_json,
         watchlist_context_json, validation_context_json, recurring_themes_json,
         risk_memory_json, missing_context_json, source_refs_json, summary)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "pk-test-1", "p40.1", "2026-04-30", "2026-04-30T12:00:00+00:00",
        "AAPL", 180, "memory_available", "hash1",
        "{}", "{}", "{}", "{}", "{}", "{}", "{}", "{}", "{}",
        json.dumps(["missing_fundamental_quality", "missing_regime"]),
        "{}", "test",
    ))
    conn.commit()
    conn.close()

    phase_rows = db.collect_evidence_phase_rows("2026-04-30", 14)
    report = build_evidence_freshness_drift_report(
        as_of_date="2026-04-30",
        lookback_days=14,
        freshness_days=3,
        phase_rows=phase_rows,
        governance_root=tmp_path / "governance",
    )

    keys = {p["key"] for p in report["missing_context_patterns"]}
    assert "missing_fundamental_quality" in keys
    assert "missing_regime" in keys
