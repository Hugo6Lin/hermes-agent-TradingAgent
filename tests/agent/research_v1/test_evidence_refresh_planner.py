"""Tests for P46 controlled evidence refresh planner."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent.research_v1.evidence_refresh_planner import (
    P46_DISCLAIMER,
    P46_SCHEMA_VERSION,
    build_evidence_refresh_plan,
    write_evidence_refresh_plan_artifacts,
)


def _monitor(status: str = "monitor_yellow", phase_overrides: dict | None = None) -> dict:
    phase_overrides = phase_overrides or {}
    phases = []
    for phase_id, phase_name in [
        ("P36", "recommendation_outcomes"),
        ("P37", "market_regime"),
        ("P38", "fundamental_quality"),
        ("P39", "candidate_pool"),
        ("P40", "research_memory"),
        ("P41", "decision_journal"),
        ("P42", "boss_copilot_brief"),
        ("P43", "copilot_console_index"),
    ]:
        base = {
            "phase_id": phase_id,
            "phase_name": phase_name,
            "latest_evidence_date": "2026-04-30",
            "latest_source_hash": f"{phase_id}-hash",
            "freshness_status": "fresh",
            "coverage_status": "complete",
            "churn_status": "stable",
            "recommended_action": "none",
            "warnings": [],
        }
        base.update(phase_overrides.get(phase_id, {}))
        phases.append(base)
    return {
        "schema_version": "p44_evidence_freshness_drift_monitor.1",
        "report_id": "p44-report",
        "as_of_date": "2026-04-30",
        "status": status,
        "source_hash": "p44-hash",
        "phase_monitors": phases,
        "missing_context_patterns": [],
    }


def _provider(status: str = "provider_ready") -> dict:
    return {
        "schema_version": "p45_market_data_readiness.1",
        "report_id": "p45-report",
        "as_of_date": "2026-04-30",
        "status": status,
        "source_hash": f"p45-{status}",
        "recommended_actions": [],
    }


def _item(plan: dict, phase_id: str) -> dict:
    return next(item for item in plan["items"] if item["phase_id"] == phase_id)


def test_missing_monitor_blocks_plan(tmp_path: Path):
    plan = build_evidence_refresh_plan(
        as_of_date="2026-04-30",
        lookback_days=14,
        max_items=12,
        monitor_report=None,
        provider_report=_provider("provider_ready"),
    )

    assert plan["schema_version"] == P46_SCHEMA_VERSION
    assert plan["status"] == "refresh_plan_blocked"
    assert any(item["plan_status"] == "blocked_missing_monitor" for item in plan["items"])


def test_provider_unavailable_blocks_market_data_phases(tmp_path: Path):
    monitor = _monitor(phase_overrides={
        "P36": {"freshness_status": "stale", "coverage_status": "partial"},
        "P37": {"freshness_status": "stale", "coverage_status": "partial"},
    })
    plan = build_evidence_refresh_plan(
        as_of_date="2026-04-30",
        lookback_days=14,
        max_items=12,
        monitor_report=monitor,
        provider_report=_provider("provider_unavailable"),
    )

    assert _item(plan, "P36")["plan_status"] == "blocked_provider_unavailable"
    assert _item(plan, "P37")["plan_status"] == "blocked_provider_unavailable"


def test_provider_ready_allows_stale_market_data_refresh_candidate(tmp_path: Path):
    monitor = _monitor(phase_overrides={"P42": {"freshness_status": "stale", "coverage_status": "partial"}})
    plan = build_evidence_refresh_plan(
        as_of_date="2026-04-30",
        lookback_days=14,
        max_items=12,
        monitor_report=monitor,
        provider_report=_provider("provider_ready"),
    )

    item = _item(plan, "P42")
    assert item["plan_status"] == "refresh_candidate"
    assert item["priority"] in {"medium", "high", "critical"}
    assert "freshness_stale" in item["reason_codes"]


def test_provider_degraded_allows_candidate_with_warning(tmp_path: Path):
    monitor = _monitor(phase_overrides={"P37": {"freshness_status": "stale", "coverage_status": "partial"}})
    plan = build_evidence_refresh_plan(
        as_of_date="2026-04-30",
        lookback_days=14,
        max_items=12,
        monitor_report=monitor,
        provider_report=_provider("provider_degraded"),
    )

    item = _item(plan, "P37")
    assert item["plan_status"] == "refresh_candidate"
    assert "market_data_provider_degraded" in item["warnings"]


def test_invalid_phase_becomes_blocked_invalid_artifact(tmp_path: Path):
    monitor = _monitor(phase_overrides={"P42": {"freshness_status": "invalid", "coverage_status": "invalid"}})
    plan = build_evidence_refresh_plan(
        as_of_date="2026-04-30",
        lookback_days=14,
        max_items=12,
        monitor_report=monitor,
        provider_report=_provider("provider_ready"),
    )

    item = _item(plan, "P42")
    assert item["plan_status"] == "blocked_invalid_artifact"
    assert "freshness_invalid" in item["reason_codes"]


def test_non_market_phase_does_not_require_provider(tmp_path: Path):
    monitor = _monitor(phase_overrides={
        "P38": {"freshness_status": "stale", "coverage_status": "partial"},
        "P43": {"freshness_status": "stale", "coverage_status": "partial"},
    })
    plan = build_evidence_refresh_plan(
        as_of_date="2026-04-30",
        lookback_days=14,
        max_items=12,
        monitor_report=monitor,
        provider_report=_provider("provider_unavailable"),
    )

    assert _item(plan, "P43")["plan_status"] == "refresh_candidate"


def test_source_hash_changes_when_provider_hash_changes(tmp_path: Path):
    monitor = _monitor(phase_overrides={"P36": {"freshness_status": "stale", "coverage_status": "partial"}})
    first = build_evidence_refresh_plan(
        as_of_date="2026-04-30",
        lookback_days=14,
        max_items=12,
        monitor_report=monitor,
        provider_report=_provider("provider_ready"),
    )
    second_provider = _provider("provider_ready")
    second_provider["source_hash"] = "changed"
    second = build_evidence_refresh_plan(
        as_of_date="2026-04-30",
        lookback_days=14,
        max_items=12,
        monitor_report=monitor,
        provider_report=second_provider,
    )

    assert first["source_hash"] != second["source_hash"]


def test_writer_emits_json_and_markdown(tmp_path: Path):
    plan = build_evidence_refresh_plan(
        as_of_date="2026-04-30",
        lookback_days=14,
        max_items=12,
        monitor_report=_monitor(),
        provider_report=_provider("provider_ready"),
    )

    paths = write_evidence_refresh_plan_artifacts(plan, tmp_path / "output" / "governance" / "2026-04-30")

    assert paths["json"].name == "p46_evidence_refresh_plan.json"
    assert paths["md"].name == "p46_evidence_refresh_plan.md"
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert payload["schema_version"] == P46_SCHEMA_VERSION


def test_markdown_rejects_forbidden_language():
    from agent.research_v1.evidence_refresh_planner import _markdown

    plan = {
        "as_of_date": "2026-04-30",
        "status": "refresh_plan_ready",
        "items": [],
        "selected_monitor": {},
        "selected_provider_readiness": {},
        "summary": {},
        "disclaimer": "buy this now",
    }
    with pytest.raises(ValueError, match="forbidden"):
        _markdown(plan)


def test_disclaimer_contains_required_phrase():
    plan = build_evidence_refresh_plan(
        as_of_date="2026-04-30",
        lookback_days=14,
        max_items=12,
        monitor_report=_monitor(),
        provider_report=_provider("provider_ready"),
    )
    assert "dry-run evidence refresh planner only" in plan["disclaimer"]
    assert "dry-run evidence refresh planner only" in P46_DISCLAIMER


def test_high_churn_produces_churn_high_reason():
    monitor = _monitor(phase_overrides={
        "P42": {
            "freshness_status": "fresh",
            "coverage_status": "complete",
            "churn_status": "high_churn",
        },
    })
    plan = build_evidence_refresh_plan(
        as_of_date="2026-04-30",
        lookback_days=14,
        max_items=12,
        monitor_report=monitor,
        provider_report=_provider("provider_ready"),
    )

    item = _item(plan, "P42")
    assert "churn_high" in item["reason_codes"]
    assert item["priority"] in {"low", "medium"}


def test_missing_context_pattern_adds_reason():
    monitor = _monitor()
    monitor["missing_context_patterns"] = [{"key": "boss_copilot_brief", "count": 2, "sources": ["P40"]}]
    plan = build_evidence_refresh_plan(
        as_of_date="2026-04-30",
        lookback_days=14,
        max_items=12,
        monitor_report=monitor,
        provider_report=_provider("provider_ready"),
    )

    p42 = _item(plan, "P42")
    assert "missing_context_pattern" in p42["reason_codes"]


def test_p44_own_refresh_planned_when_monitor_yellow():
    monitor = _monitor(status="monitor_yellow")
    plan = build_evidence_refresh_plan(
        as_of_date="2026-04-30",
        lookback_days=14,
        max_items=12,
        monitor_report=monitor,
        provider_report=_provider("provider_ready"),
    )

    p44_items = [item for item in plan["items"] if item["phase_id"] == "P44"]
    assert len(p44_items) == 1
    assert p44_items[0]["plan_status"] == "refresh_candidate"


def test_p45_own_refresh_planned_when_provider_degraded():
    monitor = _monitor()
    plan = build_evidence_refresh_plan(
        as_of_date="2026-04-30",
        lookback_days=14,
        max_items=12,
        monitor_report=monitor,
        provider_report=_provider("provider_degraded"),
    )

    p45_items = [item for item in plan["items"] if item["phase_id"] == "P45"]
    assert len(p45_items) == 1


def test_source_hash_stable_for_identical_input():
    kwargs = dict(
        as_of_date="2026-04-30",
        lookback_days=14,
        max_items=12,
        monitor_report=_monitor(),
        provider_report=_provider("provider_ready"),
    )
    first = build_evidence_refresh_plan(**kwargs)
    second = build_evidence_refresh_plan(**kwargs)

    assert first["source_hash"] == second["source_hash"]


def test_markdown_includes_candidate_and_blocked_tables():
    from agent.research_v1.evidence_refresh_planner import _markdown

    monitor = _monitor(phase_overrides={
        "P36": {"freshness_status": "stale", "coverage_status": "partial"},
    })
    plan = build_evidence_refresh_plan(
        as_of_date="2026-04-30",
        lookback_days=14,
        max_items=12,
        monitor_report=monitor,
        provider_report=_provider("provider_unavailable"),
    )
    md = _markdown(plan)

    assert "Refresh Candidates" in md
    assert "Blocked Items" in md
    assert "blocked_provider_unavailable" in md


def test_missing_provider_blocks_market_data_phases():
    monitor = _monitor(phase_overrides={
        "P36": {"freshness_status": "stale", "coverage_status": "partial"},
    })
    plan = build_evidence_refresh_plan(
        as_of_date="2026-04-30",
        lookback_days=14,
        max_items=12,
        monitor_report=monitor,
        provider_report=None,
    )

    assert _item(plan, "P36")["plan_status"] == "blocked_provider_unavailable"


def test_plan_status_noop_when_all_fresh():
    monitor = _monitor(status="monitor_green")
    plan = build_evidence_refresh_plan(
        as_of_date="2026-04-30",
        lookback_days=14,
        max_items=12,
        monitor_report=monitor,
        provider_report=_provider("provider_ready"),
    )

    assert plan["status"] == "refresh_plan_noop"
    assert plan["summary"]["candidate_count"] == 0


def test_max_items_limits_output():
    monitor = _monitor(phase_overrides={
        "P36": {"freshness_status": "stale", "coverage_status": "partial"},
        "P37": {"freshness_status": "stale", "coverage_status": "partial"},
        "P38": {"freshness_status": "stale", "coverage_status": "partial"},
    })
    plan = build_evidence_refresh_plan(
        as_of_date="2026-04-30",
        lookback_days=14,
        max_items=2,
        monitor_report=monitor,
        provider_report=_provider("provider_ready"),
    )

    assert len(plan["items"]) <= 2


def test_hard_boundaries_are_explicit():
    import agent.research_v1.evidence_refresh_planner as p46

    forbidden_names = {
        "run_recommendation_outcome_tracking", "run_market_regime_context",
        "run_fundamental_quality", "run_candidate_pool", "run_research_memory_pack",
        "run_decision_journal_guardrails", "run_boss_copilot_daily_brief",
        "run_copilot_console_index", "run_evidence_freshness_drift_monitor",
        "run_market_data_readiness", "run_governance_runtime",
        "HermesResearchApp", "final_judge", "CanonicalSignal", "CanonicalReport",
        "OpenSecTradeContext", "OpenFutureTradeContext", "unlock_trade",
        "place_order", "modify_order", "cancel_order",
    }
    assert not (forbidden_names & set(p46.__dict__))
    assert "dry-run evidence refresh planner only" in p46.P46_DISCLAIMER


# ── P46-B persistence tests ─────────────────────────────────────────────

from agent.research_v1.data.database import ResearchDatabase
from agent.research_v1.evidence_refresh_planner import run_evidence_refresh_planner


def _db(tmp_path: Path) -> ResearchDatabase:
    db = ResearchDatabase(str(tmp_path / "research.db"))
    db.initialize()
    return db


def test_evidence_refresh_plan_persistence_is_idempotent(tmp_path: Path):
    db = _db(tmp_path)
    plan = build_evidence_refresh_plan(
        as_of_date="2026-04-30",
        lookback_days=14,
        max_items=12,
        monitor_report=_monitor(phase_overrides={"P36": {"freshness_status": "stale", "coverage_status": "partial"}}),
        provider_report=_provider("provider_ready"),
    )

    first = db.save_evidence_refresh_plan(plan)
    second = db.save_evidence_refresh_plan(plan)
    rows = db.list_evidence_refresh_plans(as_of_date="2026-04-30")

    assert first == second
    assert len(rows) == 1


def test_evidence_refresh_plan_revised_hash_appends(tmp_path: Path):
    db = _db(tmp_path)
    first = build_evidence_refresh_plan(
        as_of_date="2026-04-30",
        lookback_days=14,
        max_items=12,
        monitor_report=_monitor(phase_overrides={"P36": {"freshness_status": "stale", "coverage_status": "partial"}}),
        provider_report=_provider("provider_ready"),
    )
    second = dict(first)
    second["source_hash"] = "revised"
    second["plan_id"] = "revised-plan"

    db.save_evidence_refresh_plan(first)
    db.save_evidence_refresh_plan(second)
    rows = db.list_evidence_refresh_plans(as_of_date="2026-04-30")

    assert len(rows) == 2


def test_runtime_rejects_invalid_date(tmp_path: Path):
    db = _db(tmp_path)
    result = run_evidence_refresh_planner(
        db=db,
        governance_root=tmp_path / "output" / "governance",
        output_root=tmp_path / "output" / "governance",
        as_of_date="not-a-date",
        lookback_days=14,
        max_items=12,
    )

    assert result["status"] == "blocked_invalid_input"


def test_runtime_rejects_non_directory_governance_root(tmp_path: Path):
    db = _db(tmp_path)
    root = tmp_path / "governance"
    root.write_text("not-dir", encoding="utf-8")
    result = run_evidence_refresh_planner(
        db=db,
        governance_root=root,
        output_root=tmp_path / "output",
        as_of_date="2026-04-30",
        lookback_days=14,
        max_items=12,
    )

    assert result["status"] == "blocked_invalid_input"
    assert "governance_root_not_a_directory" in result["warnings"]


def test_runtime_writes_and_persists_from_latest_db_reports(tmp_path: Path):
    db = _db(tmp_path)
    monitor = _monitor(phase_overrides={"P36": {"freshness_status": "stale", "coverage_status": "partial"}})
    provider = _provider("provider_ready")
    db.save_evidence_freshness_drift_report({
        "report_id": monitor["report_id"],
        "schema_version": monitor["schema_version"],
        "as_of_date": monitor["as_of_date"],
        "created_at": "2026-04-30T12:00:00+00:00",
        "status": monitor["status"],
        "lookback_days": 14,
        "freshness_days": 3,
        "summary": {"phase_count": 8, "red_count": 0, "yellow_count": 1},
        "source_hash": monitor["source_hash"],
        **monitor,
    })
    db.save_market_data_readiness_report({
        "report_id": provider["report_id"],
        "schema_version": provider["schema_version"],
        "as_of_date": provider["as_of_date"],
        "created_at": "2026-04-30T12:00:00+00:00",
        "status": provider["status"],
        "host": "127.0.0.1",
        "port": 11111,
        "symbols": ["US.AAPL"],
        "history_days": 30,
        "option_symbol": "US.AAPL",
        "live": True,
        "source_hash": provider["source_hash"],
        **provider,
    })

    result = run_evidence_refresh_planner(
        db=db,
        governance_root=tmp_path / "output" / "governance",
        output_root=tmp_path / "output" / "governance",
        as_of_date="2026-04-30",
        lookback_days=14,
        max_items=12,
    )

    assert result["status"] == "refresh_plan_ready"
    assert Path(result["output_dir"]).joinpath("p46_evidence_refresh_plan.json").exists()
    assert len(db.list_evidence_refresh_plans(as_of_date="2026-04-30")) == 1


def test_runtime_falls_back_to_artifact_json(tmp_path: Path):
    db = _db(tmp_path)
    gov = tmp_path / "output" / "governance" / "2026-04-30"
    gov.mkdir(parents=True, exist_ok=True)
    monitor = _monitor(phase_overrides={"P36": {"freshness_status": "stale", "coverage_status": "partial"}})
    (gov / "p44_evidence_freshness_drift_monitor.json").write_text(json.dumps(monitor), encoding="utf-8")
    provider = _provider("provider_ready")
    (gov / "p45_market_data_readiness.json").write_text(json.dumps(provider), encoding="utf-8")

    result = run_evidence_refresh_planner(
        db=db,
        governance_root=tmp_path / "output" / "governance",
        output_root=tmp_path / "output" / "governance",
        as_of_date="2026-04-30",
        lookback_days=14,
        max_items=12,
    )

    assert result["status"] == "refresh_plan_ready"
