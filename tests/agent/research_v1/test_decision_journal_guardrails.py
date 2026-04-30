"""Tests for P41 decision journal guardrails."""

from __future__ import annotations

import json
from pathlib import Path

from agent.research_v1.decision_journal_guardrails import (
    P41_SCHEMA_VERSION,
    build_decision_journal_entry,
    compute_decision_journal_source_hash,
    validate_decision_item,
)


def _decision(**overrides) -> dict:
    base = {
        "ticker": "AAPL",
        "contemplated_action": "research_candidate",
        "decision_intent": "review_before_action",
        "stated_reason": "Candidate score is high.",
        "boss_confidence": 0.82,
        "urgency": "high",
        "time_pressure": "same_day",
        "recent_pnl_state": "drawdown",
        "position_context": {
            "current_position_pct": 0.08,
            "sector_exposure_pct": 0.32,
            "cash_available_pct": 0.18,
        },
        "manual_notes": ["Review concentration first"],
    }
    base.update(overrides)
    return base


def test_valid_decision_builds_journal_entry():
    entry = build_decision_journal_entry(_decision(), "2026-04-30", memory_pack=None)

    assert entry["schema_version"] == P41_SCHEMA_VERSION
    assert entry["ticker"] == "AAPL"
    assert entry["contemplated_action"] == "research_candidate"
    assert entry["severity"] in {"info", "caution", "slow_down", "manual_review"}


def test_forbidden_trade_action_is_blocked():
    errors = validate_decision_item(_decision(contemplated_action="buy"))

    assert "forbidden_contemplated_action" in errors


def test_ticker_normalization_uppercases_and_trims():
    entry = build_decision_journal_entry(_decision(ticker=" aapl "), "2026-04-30", None)
    assert entry["ticker"] == "AAPL"


def test_high_urgency_high_confidence_slow_down():
    entry = build_decision_journal_entry(_decision(urgency="high", boss_confidence=0.90), "2026-04-30", None)
    flags = {f["flag_id"] for f in entry["guardrail_flags"]}
    assert "high_urgency_high_confidence" in flags
    assert entry["severity"] in {"slow_down", "manual_review"}


def test_same_day_time_pressure_emits_flag():
    entry = build_decision_journal_entry(_decision(time_pressure="same_day", urgency="low", boss_confidence=0.5), "2026-04-30", None)
    flags = {f["flag_id"] for f in entry["guardrail_flags"]}
    assert "time_pressure_same_day" in flags


def test_drawdown_state_emits_flag():
    entry = build_decision_journal_entry(_decision(recent_pnl_state="drawdown", urgency="low", boss_confidence=0.5), "2026-04-30", None)
    flags = {f["flag_id"] for f in entry["guardrail_flags"]}
    assert "recent_drawdown_context" in flags


def test_high_position_concentration_manual_review():
    entry = build_decision_journal_entry(_decision(position_context={"current_position_pct": 0.20, "sector_exposure_pct": 0.10}), "2026-04-30", None)
    assert entry["severity"] == "manual_review"
    assert entry["cooling_off_suggestion"] == "manual_review_before_action"


def test_high_sector_exposure_manual_review():
    entry = build_decision_journal_entry(_decision(position_context={"current_position_pct": 0.05, "sector_exposure_pct": 0.45}), "2026-04-30", None)
    assert entry["severity"] == "manual_review"


def test_missing_memory_pack_emits_flag():
    entry = build_decision_journal_entry(_decision(urgency="low", boss_confidence=0.5), "2026-04-30", None)
    flags = {f["flag_id"] for f in entry["guardrail_flags"]}
    assert "missing_memory_pack" in flags


def test_p40_risk_memory_propagates_quality_red_flags():
    memory = {"pack_id": "p1", "source_hash": "h1", "risk_memory": ["quality_red_flags_present"], "missing_context": [], "recurring_themes": []}
    entry = build_decision_journal_entry(_decision(urgency="low", boss_confidence=0.5), "2026-04-30", memory)
    flags = {f["flag_id"] for f in entry["guardrail_flags"]}
    assert "quality_red_flags_present" in flags
    assert entry["severity"] == "manual_review"


def test_p40_risk_memory_propagates_negative_outcome():
    memory = {"pack_id": "p1", "source_hash": "h1", "risk_memory": ["negative_outcome_history"], "missing_context": [], "recurring_themes": []}
    entry = build_decision_journal_entry(_decision(urgency="low", boss_confidence=0.5), "2026-04-30", memory)
    flags = {f["flag_id"] for f in entry["guardrail_flags"]}
    assert "negative_outcome_memory" in flags


def test_cooling_off_follows_severity():
    # slow_down with drawdown → recheck_next_session
    entry = build_decision_journal_entry(_decision(recent_pnl_state="drawdown", urgency="low", boss_confidence=0.5), "2026-04-30", None)
    assert entry["cooling_off_suggestion"] == "recheck_next_session"

    # slow_down without drawdown/time_pressure → recheck_after_30_minutes
    entry2 = build_decision_journal_entry(_decision(urgency="high", boss_confidence=0.90, time_pressure=None, recent_pnl_state=None), "2026-04-30", None)
    assert entry2["cooling_off_suggestion"] == "recheck_after_30_minutes"

    # info → none
    entry3 = build_decision_journal_entry(_decision(urgency="low", boss_confidence=0.3, time_pressure=None, recent_pnl_state=None, position_context={}), "2026-04-30", {"pack_id": "p1", "source_hash": "h1", "risk_memory": [], "missing_context": [], "recurring_themes": []})
    assert entry3["cooling_off_suggestion"] == "none"


def test_source_hash_changes_when_boss_input_changes():
    first = build_decision_journal_entry(_decision(stated_reason="first"), "2026-04-30", None)
    second = build_decision_journal_entry(_decision(stated_reason="second"), "2026-04-30", None)
    assert first["source_hash"] != second["source_hash"]


def test_source_hash_changes_when_memory_source_changes():
    decision = _decision()
    first = build_decision_journal_entry(decision, "2026-04-30", {"pack_id": "p1", "source_hash": "h1"})
    second = build_decision_journal_entry(decision, "2026-04-30", {"pack_id": "p1", "source_hash": "h2"})
    assert first["source_hash"] != second["source_hash"]


def test_disclaimer_contains_required_phrase():
    entry = build_decision_journal_entry(_decision(), "2026-04-30", None)
    assert "behavioral guardrail evidence only" in entry["disclaimer"]
