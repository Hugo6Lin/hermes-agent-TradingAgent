"""Tests for P48 research context prompt pack dry-run."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent.research_v1.research_context_prompt_pack import (
    P48_DISCLAIMER,
    build_research_context_prompt_pack,
    normalize_roles,
    render_research_context_prompt_pack_markdown,
    validate_prompt_pack_inputs,
    write_research_context_prompt_pack,
)


def _source_pack() -> dict:
    return {
        "pack_id": "p47-2026-05-01-source",
        "as_of_date": "2026-05-01",
        "source_hash": "p47-source-hash",
        "tickers": ["AAPL"],
        "system_context": {"provider_status": "provider_ready", "evidence_health_status": "monitor_green"},
        "ticker_contexts": [
            {
                "ticker": "AAPL",
                "context_status": "context_ready",
                "market_regime": {"regime_label": "neutral"},
                "fundamental_quality": {"quality_score": 82, "quality_label": "strong"},
                "candidate_context": {"candidate_status": "candidate"},
                "outcome_context": {"win_rate": 0.6},
                "memory_context": {"memory_status": "memory_ready"},
                "decision_guardrails": {"severity": "info"},
                "refresh_context": {"refresh_candidate_count": 1},
                "evidence_health": {"status": "monitor_green"},
                "source_refs": [{"phase_id": "P38", "artifact_type": "fundamental_quality", "source_hash": "q"}],
                "missing_context": [],
                "warnings": [],
            }
        ],
        "source_refs": [{"phase_id": "P47", "artifact_type": "research_context_pack", "source_hash": "p47-source-hash"}],
        "missing_context": [],
        "warnings": [],
    }


def test_normalize_roles_deduplicates_and_preserves_order():
    assert normalize_roles([" Risk ", "fundamentals", "risk"]) == ["risk", "fundamentals"]


def test_validate_prompt_pack_inputs_rejects_unknown_role():
    result = validate_prompt_pack_inputs("2026-05-01", ["AAPL"], ["wizard"], 1200, True)
    assert result["status"] == "blocked_invalid_input"
    assert "unknown_role:wizard" in result["warnings"]


def test_build_prompt_pack_creates_role_context_and_manifest():
    pack = build_research_context_prompt_pack(
        as_of_date="2026-05-01",
        tickers=["AAPL"],
        roles=["fundamentals", "risk"],
        max_block_chars=1200,
        source_pack=_source_pack(),
    )
    assert pack["status"] == "prompt_pack_ready"
    assert len(pack["role_contexts"]) == 2
    assert pack["dry_run_injection_manifest"][0]["dry_run_only"] is True
    assert pack["dry_run_injection_manifest"][0]["target_object"] == "SubagentTask.required_context"
    assert pack["role_contexts"][0]["required_context_preview"]["not_injected"] is True


def test_truncation_marks_limited_and_omitted_context():
    source = _source_pack()
    source["ticker_contexts"][0]["fundamental_quality"] = {"long": "x" * 500}
    pack = build_research_context_prompt_pack(
        as_of_date="2026-05-01",
        tickers=["AAPL"],
        roles=["fundamentals"],
        max_block_chars=80,
        source_pack=source,
    )
    assert pack["status"] == "prompt_pack_limited"
    assert pack["role_contexts"][0]["context_status"] == "role_context_limited"
    assert any(item.startswith("omitted_section:AAPL:fundamentals") for item in pack["omitted_context"])


def test_markdown_renderer_includes_required_sections():
    pack = build_research_context_prompt_pack(
        as_of_date="2026-05-01",
        tickers=["AAPL"],
        roles=["risk"],
        max_block_chars=1200,
        source_pack=_source_pack(),
    )
    md = render_research_context_prompt_pack_markdown(pack)
    assert "# P48 Research Context Prompt Pack" in md
    assert "## Dry-Run Injection Manifest" in md
    assert "## Disclaimer" in md
    assert P48_DISCLAIMER in md


def test_write_research_context_prompt_pack_creates_files(tmp_path: Path):
    pack = build_research_context_prompt_pack(
        as_of_date="2026-05-01",
        tickers=["AAPL"],
        roles=["risk"],
        max_block_chars=1200,
        source_pack=_source_pack(),
    )
    artifacts = write_research_context_prompt_pack(pack, tmp_path)
    assert len(artifacts) == 2
    loaded = json.loads((tmp_path / "2026-05-01" / "p48_research_context_prompt_pack.json").read_text())
    assert loaded["prompt_pack_id"] == pack["prompt_pack_id"]


# --- P48-B persistence and runtime tests ---

from agent.research_v1.data.database import ResearchDatabase
from agent.research_v1.research_context_prompt_pack import run_research_context_prompt_pack


def test_save_research_context_prompt_pack_is_idempotent(tmp_path: Path):
    db = ResearchDatabase(str(tmp_path / "test.db"))
    db.initialize()
    pack = build_research_context_prompt_pack(
        as_of_date="2026-05-01",
        tickers=["AAPL"],
        roles=["risk"],
        max_block_chars=1200,
        source_pack=_source_pack(),
        created_at="2026-05-01T00:00:00+00:00",
    )
    db.save_research_context_prompt_pack(pack)
    db.save_research_context_prompt_pack(pack)
    rows = db.list_research_context_prompt_packs(as_of_date="2026-05-01")
    assert len(rows) == 1
    assert rows[0]["source_hash"] == pack["source_hash"]


def test_run_prompt_pack_loads_p47_artifact_when_db_empty(tmp_path: Path):
    db = ResearchDatabase(str(tmp_path / "test.db"))
    db.initialize()
    governance_root = tmp_path / "governance"
    day_dir = governance_root / "2026-05-01"
    day_dir.mkdir(parents=True)
    (day_dir / "p47_research_context_pack.json").write_text(json.dumps(_source_pack()), encoding="utf-8")
    result = run_research_context_prompt_pack(db, governance_root, tmp_path / "out", "2026-05-01", ["AAPL"], ["risk"], 1200)
    assert result["status"] == "prompt_pack_ready"
    assert result["source_context_pack_id"] == "p47-2026-05-01-source"


def test_run_prompt_pack_blocks_when_p47_missing(tmp_path: Path):
    db = ResearchDatabase(str(tmp_path / "test.db"))
    db.initialize()
    governance_root = tmp_path / "governance"
    governance_root.mkdir()
    result = run_research_context_prompt_pack(db, governance_root, tmp_path / "out", "2026-05-01", ["AAPL"], ["risk"], 1200)
    assert result["status"] == "blocked_missing_context"
    assert not (tmp_path / "out" / "2026-05-01" / "p48_research_context_prompt_pack.json").exists()


def test_source_pack_selection_prefers_matching_tickers(tmp_path: Path):
    """P48 for AAPL should pick the AAPL pack even if a newer MSFT pack exists."""
    db = ResearchDatabase(str(tmp_path / "test.db"))
    db.initialize()
    msft_pack = {
        "pack_id": "p47-2026-05-01-msft",
        "as_of_date": "2026-05-01",
        "created_at": "2026-05-01T12:00:00+00:00",
        "status": "context_pack_ready",
        "source_hash": "msft-hash",
        "tickers": ["MSFT"],
        "system_context": {},
        "ticker_contexts": [{"ticker": "MSFT", "context_status": "context_ready", "market_regime": {"regime_label": "bullish"}}],
        "source_refs": [],
        "missing_context": [],
        "warnings": [],
    }
    aapl_pack = {
        "pack_id": "p47-2026-05-01-aapl",
        "as_of_date": "2026-05-01",
        "created_at": "2026-05-01T10:00:00+00:00",
        "status": "context_pack_ready",
        "source_hash": "aapl-hash",
        "tickers": ["AAPL"],
        "system_context": {},
        "ticker_contexts": [{"ticker": "AAPL", "context_status": "context_ready", "market_regime": {"regime_label": "neutral"}}],
        "source_refs": [],
        "missing_context": [],
        "warnings": [],
    }
    db.save_research_context_pack(msft_pack)
    db.save_research_context_pack(aapl_pack)
    governance_root = tmp_path / "governance"
    governance_root.mkdir()
    result = run_research_context_prompt_pack(db, governance_root, tmp_path / "out", "2026-05-01", ["AAPL"], ["technical"], 1200)
    assert result["status"] == "prompt_pack_ready"
    assert result["source_context_pack_id"] == "p47-2026-05-01-aapl"


def test_run_prompt_pack_limited_when_source_exists_but_ticker_missing(tmp_path: Path):
    """P47 pack exists for AAPL but P48 requests MSFT: should be limited, not blocked."""
    db = ResearchDatabase(str(tmp_path / "test.db"))
    db.initialize()
    aapl_pack = {
        "pack_id": "p47-2026-05-01-aapl",
        "as_of_date": "2026-05-01",
        "created_at": "2026-05-01T10:00:00+00:00",
        "status": "context_pack_ready",
        "source_hash": "aapl-hash",
        "tickers": ["AAPL"],
        "system_context": {},
        "ticker_contexts": [{"ticker": "AAPL", "context_status": "context_ready", "market_regime": {"regime_label": "neutral"}}],
        "source_refs": [],
        "missing_context": [],
        "warnings": [],
    }
    db.save_research_context_pack(aapl_pack)
    governance_root = tmp_path / "governance"
    governance_root.mkdir()
    result = run_research_context_prompt_pack(db, governance_root, tmp_path / "out", "2026-05-01", ["MSFT"], ["risk"], 1200)
    assert result["status"] == "prompt_pack_limited"
    assert all(ctx["context_status"] == "role_context_missing" for ctx in result["role_contexts"])
