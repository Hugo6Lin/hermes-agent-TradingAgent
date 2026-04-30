# P42 Boss Co-Pilot Daily Brief Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone daily boss co-pilot brief that aggregates existing P36-P41 evidence into deterministic research priorities without changing recommendations or issuing trade instructions.

**Architecture:** Add `boss_copilot_daily_brief.py` as a pure aggregation module with scoring, source hashing, artifact writing, and run orchestration. Extend `ResearchDatabase` with as-of-safe read helpers and append-only P42 persistence, then expose a `boss-copilot-brief-run` CLI command.

**Tech Stack:** Python 3.11, sqlite3, pathlib, json, hashlib, datetime, argparse, pytest.

---

## File Structure

- Create: `agent/research_v1/boss_copilot_daily_brief.py`
  - Constants, validation, context normalization, priority scoring, source hashing, artifact writer, run orchestration.
- Modify: `agent/research_v1/data/database.py`
  - Add P42 table and helpers for latest P39/P40/P41 evidence.
- Modify: `agent/research_v1/batch_cli.py`
  - Add `boss-copilot-brief-run`.
- Create: `tests/agent/research_v1/test_boss_copilot_daily_brief.py`
  - Focused P42 tests.
- Modify: `tests/agent/research_v1/test_batch_cli.py`
  - P42 CLI tests.
- Modify: `README.md`
  - Root overview and verification counts.
- Modify: `agent/research_v1/README.md`
  - Data Flow section.

Do not modify `app.py`, `final_judge.py`, `orchestrator.py`, `contracts.py`, `recommendation_outcomes.py`, `market_regime_context.py`, `fundamental_quality.py`, `candidate_pool.py`, `research_memory_pack.py`, or `decision_journal_guardrails.py`.

## Constants

Use these constants in `boss_copilot_daily_brief.py`:

```python
P42_SCHEMA_VERSION = "p42_boss_copilot_daily_brief.1"

P42_STATUS_READY = "brief_ready"
P42_STATUS_LIMITED_CONTEXT = "brief_limited_context"
P42_STATUS_NO_CANDIDATES = "brief_no_candidates"
P42_STATUS_BLOCKED_INVALID_INPUT = "blocked_invalid_input"

P42_BANDS = ("high_priority", "medium_priority", "low_priority", "context_blocked")

P42_RESEARCH_ACTIONS = (
    "review_research_pack",
    "refresh_missing_context",
    "compare_with_watchlist",
    "defer_until_context_improves",
    "manual_review_before_any_action",
)

P42_ARTIFACT_DISCLAIMER = (
    "P42 is daily research-priority evidence only. It summarizes existing "
    "Hermes evidence and does not recommend trades, place orders, approve "
    "production adoption, train models, schedule jobs, or mutate research decisions."
)

P42_FORBIDDEN_TERMS = (
    "buy this now",
    "sell this now",
    "follow this trade",
    "guaranteed edge",
    "production approved",
    "model promoted",
    "trade now",
    "order ticket",
    "place order",
    "execute trade",
)
```

## Task 1: P42-A Brief Builder

**Files:**
- Create: `agent/research_v1/boss_copilot_daily_brief.py`
- Create: `tests/agent/research_v1/test_boss_copilot_daily_brief.py`

- [ ] **Step 1: Write initial builder tests**

Add:

```python
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
        "inclusion_reasons_json": "[\"high candidate score\"]",
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
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_boss_copilot_daily_brief.py -q
```

Expected: import fails because `boss_copilot_daily_brief.py` does not exist.

- [ ] **Step 3: Implement builder skeleton**

Create `agent/research_v1/boss_copilot_daily_brief.py`:

```python
"""P42 Boss Co-Pilot Daily Brief - deterministic research-priority evidence."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

P42_SCHEMA_VERSION = "p42_boss_copilot_daily_brief.1"
P42_STATUS_READY = "brief_ready"
P42_STATUS_LIMITED_CONTEXT = "brief_limited_context"
P42_STATUS_NO_CANDIDATES = "brief_no_candidates"
P42_STATUS_BLOCKED_INVALID_INPUT = "blocked_invalid_input"

P42_ARTIFACT_DISCLAIMER = (
    "P42 is daily research-priority evidence only. It summarizes existing "
    "Hermes evidence and does not recommend trades, place orders, approve "
    "production adoption, train models, schedule jobs, or mutate research decisions."
)

P42_FORBIDDEN_TERMS = (
    "buy this now", "sell this now", "follow this trade", "guaranteed edge",
    "production approved", "model promoted", "trade now", "order ticket",
    "place order", "execute trade",
)

GUARDRAIL_PENALTY = {"info": 0.0, "caution": 0.03, "slow_down": 0.08, "manual_review": 0.15}


def _clamp(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, number))


def _loads(value: Any, fallback: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if value in (None, ""):
        return fallback
    try:
        return json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return fallback


def _ticker(value: Any) -> str:
    return str(value or "").strip().upper()


def _source_hash_payload(brief_seed: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(brief_seed, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()
```

- [ ] **Step 4: Add priority scoring implementation**

Append:

```python
def _quality_score(report: dict | None) -> float:
    if not report:
        return 0.0
    return _clamp(report.get("overall_quality_score"))


def _memory_score(pack: dict | None) -> float:
    if not pack:
        return 0.0
    if pack.get("memory_status") == "memory_available":
        return 0.75
    if pack.get("memory_status") == "limited_memory":
        return 0.45
    return 0.2


def _outcome_score(pack: dict | None) -> float:
    if not pack:
        return 0.0
    summary = pack.get("outcome_summary") or {}
    evaluated = int(summary.get("evaluated_rows", 0) or 0)
    if evaluated <= 0:
        return 0.25
    return _clamp(summary.get("win_rate", 0.0))


def _regime_fit_score(candidate: dict, regime_snapshot: dict | None) -> float:
    if not regime_snapshot:
        return 0.0
    confidence = _clamp(regime_snapshot.get("confidence"))
    return round(0.5 + (0.5 * confidence), 6)


def _journal_severity(journal: dict | None) -> str:
    if not journal:
        return "caution"
    return str(journal.get("severity", "info"))


def _priority_band(score: float, severity: str) -> str:
    if severity == "manual_review" or score < 0.35:
        return "context_blocked"
    if score >= 0.75:
        return "high_priority"
    if score >= 0.55:
        return "medium_priority"
    return "low_priority"


def _suggested_action(band: str, missing_context: list[str], severity: str) -> str:
    if severity == "manual_review":
        return "manual_review_before_any_action"
    if missing_context:
        return "refresh_missing_context"
    if band == "context_blocked":
        return "defer_until_context_improves"
    return "review_research_pack"


def _build_priority(candidate: dict, regime_snapshot: dict | None, quality: dict | None, memory: dict | None, journal: dict | None) -> dict[str, Any]:
    ticker = _ticker(candidate.get("ticker"))
    missing_context: list[str] = []
    if not regime_snapshot:
        missing_context.append("missing_market_regime_context")
    if not quality:
        missing_context.append("missing_fundamental_quality")
    if not memory:
        missing_context.append("missing_research_memory")
    if not journal:
        missing_context.append("missing_decision_journal")

    candidate_score = _clamp(candidate.get("total_score"))
    q_score = _quality_score(quality)
    mem_score = _memory_score(memory)
    regime_score = _regime_fit_score(candidate, regime_snapshot)
    outcome_score = _outcome_score(memory)
    severity = _journal_severity(journal)
    missing_penalty = min(0.30, 0.05 * len(missing_context))
    guardrail_penalty = GUARDRAIL_PENALTY.get(severity, 0.03)
    score = round(max(0.0, min(1.0, (
        0.50 * candidate_score
        + 0.20 * q_score
        + 0.15 * mem_score
        + 0.10 * regime_score
        + 0.05 * outcome_score
        - missing_penalty
        - guardrail_penalty
    ))), 6)
    band = _priority_band(score, severity)

    risk_notes = []
    risk_notes.extend(_loads(candidate.get("risk_notes_json"), []))
    if quality and quality.get("red_flags"):
        risk_notes.extend(quality.get("red_flags", []))
    if memory:
        risk_notes.extend(memory.get("risk_memory", []))
    if journal and severity in {"slow_down", "manual_review"}:
        risk_notes.append(f"decision_journal_{severity}")

    return {
        "rank": 0,
        "ticker": ticker,
        "sector": candidate.get("sector"),
        "priority_score": score,
        "priority_band": band,
        "research_reason": "; ".join(_loads(candidate.get("inclusion_reasons_json"), [])) or "candidate evidence available",
        "candidate_ref": {"run_id": candidate.get("run_id"), "item_id": candidate.get("item_id"), "source_hash": candidate.get("source_hash", "")},
        "market_regime_ref": {"snapshot_id": (regime_snapshot or {}).get("snapshot_id", ""), "source_hash": (regime_snapshot or {}).get("data_source_hash", (regime_snapshot or {}).get("source_hash", ""))},
        "fundamental_quality_ref": {"report_id": (quality or {}).get("report_id", ""), "source_hash": (quality or {}).get("source_hash", "")},
        "memory_ref": {"pack_id": (memory or {}).get("pack_id", ""), "source_hash": (memory or {}).get("source_hash", "")},
        "decision_guardrail_ref": {"journal_id": (journal or {}).get("journal_id", ""), "source_hash": (journal or {}).get("source_hash", "")},
        "outcome_snapshot": (memory or {}).get("outcome_summary", {}),
        "quality_snapshot": {"label": (quality or {}).get("quality_label", ""), "score": q_score},
        "regime_snapshot": {"label": (regime_snapshot or {}).get("regime_label", ""), "confidence": (regime_snapshot or {}).get("confidence")},
        "memory_snapshot": {"status": (memory or {}).get("memory_status", ""), "themes": (memory or {}).get("recurring_themes", [])},
        "guardrail_snapshot": {"severity": severity, "cooling_off_suggestion": (journal or {}).get("cooling_off_suggestion", "")},
        "missing_context": sorted(set(missing_context)),
        "risk_notes": sorted(set(str(r) for r in risk_notes)),
        "suggested_research_action": _suggested_action(band, missing_context, severity),
        "disclaimer": P42_ARTIFACT_DISCLAIMER,
    }
```

- [ ] **Step 5: Add brief builder and source hash**

Append:

```python
def compute_boss_copilot_source_hash(seed: dict[str, Any]) -> str:
    return _source_hash_payload(seed)


def build_boss_copilot_daily_brief(
    *,
    as_of_date: str,
    candidate_run: dict | None,
    candidate_items: list[dict],
    regime_snapshot: dict | None,
    quality_by_ticker: dict[str, dict],
    memory_by_ticker: dict[str, dict],
    journal_by_ticker: dict[str, dict],
    max_priorities: int = 8,
) -> dict[str, Any]:
    selected_items = sorted(candidate_items, key=lambda c: (int(c.get("rank", 999999) or 999999), _ticker(c.get("ticker"))))[:max_priorities]
    priorities = [
        _build_priority(
            c,
            regime_snapshot,
            quality_by_ticker.get(_ticker(c.get("ticker"))),
            memory_by_ticker.get(_ticker(c.get("ticker"))),
            journal_by_ticker.get(_ticker(c.get("ticker"))),
        )
        for c in selected_items
    ]
    priorities.sort(key=lambda p: (-p["priority_score"], int((candidate_run or {}).get("rank", 0) or 0), p["ticker"]))
    for idx, priority in enumerate(priorities, start=1):
        priority["rank"] = idx

    missing_counts: dict[str, int] = {}
    for priority in priorities:
        for item in priority["missing_context"]:
            missing_counts[item] = missing_counts.get(item, 0) + 1

    if not priorities:
        status = P42_STATUS_NO_CANDIDATES
    elif missing_counts:
        status = P42_STATUS_LIMITED_CONTEXT
    else:
        status = P42_STATUS_READY

    summary = {
        "priority_count": len(priorities),
        "high_priority_count": sum(1 for p in priorities if p["priority_band"] == "high_priority"),
        "medium_priority_count": sum(1 for p in priorities if p["priority_band"] == "medium_priority"),
        "low_priority_count": sum(1 for p in priorities if p["priority_band"] == "low_priority"),
        "context_blocked_count": sum(1 for p in priorities if p["priority_band"] == "context_blocked"),
        "manual_review_count": sum(1 for p in priorities if p["guardrail_snapshot"]["severity"] == "manual_review"),
        "missing_context_counts": dict(sorted(missing_counts.items())),
        "regime_label": (regime_snapshot or {}).get("regime_label", ""),
        "regime_confidence": (regime_snapshot or {}).get("confidence"),
        "candidate_run_ref": {"run_id": (candidate_run or {}).get("run_id", ""), "source_hash": (candidate_run or {}).get("source_hash", "")},
    }
    seed = {
        "schema_version": P42_SCHEMA_VERSION,
        "as_of_date": as_of_date,
        "max_priorities": max_priorities,
        "candidate_run": summary["candidate_run_ref"],
        "regime": priorities[0]["market_regime_ref"] if priorities else {},
        "priorities": [
            {
                "ticker": p["ticker"],
                "candidate": p["candidate_ref"],
                "quality": p["fundamental_quality_ref"],
                "memory": p["memory_ref"],
                "journal": p["decision_guardrail_ref"],
            }
            for p in priorities
        ],
    }
    source_hash = compute_boss_copilot_source_hash(seed)
    brief_id = hashlib.sha256(f"{as_of_date}|{source_hash}".encode("utf-8")).hexdigest()[:16]
    return {
        "schema_version": P42_SCHEMA_VERSION,
        "brief_id": brief_id,
        "as_of_date": as_of_date,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "summary": summary,
        "priorities": priorities,
        "source_hash": source_hash,
        "disclaimer": P42_ARTIFACT_DISCLAIMER,
    }
```

- [ ] **Step 6: Add artifact writer**

Append:

```python
def write_boss_copilot_daily_brief_artifacts(brief: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "p42_boss_copilot_daily_brief.json"
    md_path = output_dir / "p42_boss_copilot_daily_brief.md"
    json_path.write_text(json.dumps(brief, indent=2, sort_keys=True, default=str), encoding="utf-8")

    lines = [
        "# Boss Co-Pilot Daily Brief",
        "",
        f"As of: `{brief['as_of_date']}`",
        f"Status: `{brief['status']}`",
        f"Priority count: `{brief['summary']['priority_count']}`",
        "",
        "## Market Context",
        "",
        f"- Regime: `{brief['summary'].get('regime_label', '')}`",
        f"- Confidence: `{brief['summary'].get('regime_confidence', '')}`",
        "",
        "## Research Priorities",
        "",
        "| Rank | Ticker | Band | Score | Suggested Research Action | Missing Context |",
        "|------|--------|------|-------|---------------------------|-----------------|",
    ]
    for p in brief.get("priorities", []):
        lines.append(
            f"| {p['rank']} | {p['ticker']} | {p['priority_band']} | "
            f"{p['priority_score']:.4f} | {p['suggested_research_action']} | "
            f"{', '.join(p['missing_context']) or 'none'} |"
        )
    lines.extend(["", "## Guardrails and Slow-Down Notes", ""])
    notes = []
    for p in brief.get("priorities", []):
        severity = p.get("guardrail_snapshot", {}).get("severity", "info")
        if severity != "info":
            notes.append(f"- {p['ticker']}: `{severity}` / `{p['guardrail_snapshot'].get('cooling_off_suggestion', '')}`")
    lines.extend(notes or ["- none"])
    lines.extend(["", "## Evidence Coverage", ""])
    missing = brief["summary"].get("missing_context_counts", {})
    if missing:
        for key, count in sorted(missing.items()):
            lines.append(f"- {key}: {count}")
    else:
        lines.append("- complete for selected priorities")
    lines.extend(["", "---", "", f"> {brief.get('disclaimer', P42_ARTIFACT_DISCLAIMER)}", ""])
    markdown = "\n".join(lines)
    lowered = markdown.lower()
    for forbidden in P42_FORBIDDEN_TERMS:
        if forbidden in lowered:
            raise ValueError(f"forbidden boss co-pilot term rendered: {forbidden}")
    md_path.write_text(markdown, encoding="utf-8")
    return {"json": json_path, "md": md_path}
```

- [ ] **Step 7: Add focused tests for scoring, hash, and artifacts**

Append tests:

```python
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
```

- [ ] **Step 8: Run tests and commit P42-A**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_boss_copilot_daily_brief.py -q
```

Expected: P42-A tests pass.

Commit:

```bash
git add agent/research_v1/boss_copilot_daily_brief.py tests/agent/research_v1/test_boss_copilot_daily_brief.py
git commit -m "feat: add boss copilot daily brief"
```

## Task 2: P42-B Database Helpers + Persistence

**Files:**
- Modify: `agent/research_v1/data/database.py`
- Modify: `tests/agent/research_v1/test_boss_copilot_daily_brief.py`

- [ ] **Step 1: Add persistence tests**

Append:

```python
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
```

- [ ] **Step 2: Implement P42 database table**

In `ResearchDatabase`, add:

```python
def initialize_boss_copilot_brief_schema(self) -> None:
    conn = self._get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS boss_copilot_daily_briefs (
            brief_id TEXT PRIMARY KEY,
            schema_version TEXT NOT NULL,
            as_of_date TEXT NOT NULL,
            created_at TEXT NOT NULL,
            status TEXT NOT NULL,
            priority_count INTEGER NOT NULL,
            manual_review_count INTEGER NOT NULL,
            source_hash TEXT NOT NULL,
            brief_json TEXT NOT NULL,
            UNIQUE(as_of_date, source_hash)
        )
    """)
    conn.commit()
    conn.close()
```

- [ ] **Step 3: Implement P42 persistence helpers**

Add:

```python
def save_boss_copilot_daily_brief(self, brief: dict) -> str:
    self.initialize_boss_copilot_brief_schema()
    summary = brief.get("summary", {})
    conn = self._get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT OR IGNORE INTO boss_copilot_daily_briefs (
            brief_id, schema_version, as_of_date, created_at,
            status, priority_count, manual_review_count,
            source_hash, brief_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            brief["brief_id"],
            brief["schema_version"],
            brief["as_of_date"],
            brief.get("created_at", ""),
            brief.get("status", ""),
            summary.get("priority_count", 0),
            summary.get("manual_review_count", 0),
            brief["source_hash"],
            json.dumps(brief),
        ),
    )
    conn.commit()
    conn.close()
    return brief["brief_id"]


def list_boss_copilot_daily_briefs(self, as_of_date: str | None = None, limit: int = 20) -> list[dict]:
    self.initialize_boss_copilot_brief_schema()
    conn = self._get_connection()
    cursor = conn.cursor()
    if as_of_date:
        cursor.execute(
            """SELECT * FROM boss_copilot_daily_briefs
               WHERE as_of_date = ?
               ORDER BY created_at DESC, brief_id ASC
               LIMIT ?""",
            (as_of_date, limit),
        )
    else:
        cursor.execute(
            """SELECT * FROM boss_copilot_daily_briefs
               ORDER BY as_of_date DESC, created_at DESC, brief_id ASC
               LIMIT ?""",
            (limit,),
        )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
```

- [ ] **Step 4: Add latest-as-of read helpers**

Add:

```python
def get_latest_candidate_pool_run_as_of(self, as_of_date: str) -> dict | None:
    self.initialize_candidate_pool_schema()
    conn = self._get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT * FROM candidate_pool_runs
           WHERE as_of_date <= ?
           ORDER BY as_of_date DESC, created_at DESC, run_id ASC
           LIMIT 1""",
        (as_of_date,),
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_latest_decision_journal_entry(self, ticker: str, as_of_date: str) -> dict | None:
    self.initialize_decision_journal_schema()
    conn = self._get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT * FROM decision_journal_entries
           WHERE ticker = ? AND as_of_date <= ?
           ORDER BY as_of_date DESC, created_at DESC, journal_id ASC
           LIMIT 1""",
        (ticker, as_of_date),
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None
```

Use existing helpers for:

- `list_candidate_pool_items(run_id)`
- `list_market_regime_snapshots_as_of(as_of_date, limit=1)`
- `list_fundamental_quality_reports_as_of(ticker, as_of_date, limit=1)`
- `get_latest_research_memory_pack(ticker, as_of_date)`

- [ ] **Step 5: Run tests and commit P42-B**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_boss_copilot_daily_brief.py -q
```

Commit:

```bash
git add agent/research_v1/data/database.py tests/agent/research_v1/test_boss_copilot_daily_brief.py
git commit -m "feat: persist boss copilot briefs"
```

## Task 3: P42-C Run Orchestration + CLI

**Files:**
- Modify: `agent/research_v1/boss_copilot_daily_brief.py`
- Modify: `agent/research_v1/batch_cli.py`
- Modify: `tests/agent/research_v1/test_boss_copilot_daily_brief.py`
- Modify: `tests/agent/research_v1/test_batch_cli.py`

- [ ] **Step 1: Add run orchestration test**

Append:

```python
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
```

- [ ] **Step 2: Implement run orchestration**

Append to module:

```python
def run_boss_copilot_daily_brief(db: Any, as_of_date: str, output_root: Path, max_priorities: int = 8) -> dict[str, Any]:
    if max_priorities <= 0:
        return {"status": P42_STATUS_BLOCKED_INVALID_INPUT, "warnings": ["max_priorities_must_be_positive"]}

    candidate_run = db.get_latest_candidate_pool_run_as_of(as_of_date)
    candidate_items = db.list_candidate_pool_items(candidate_run["run_id"]) if candidate_run else []
    regime_rows = db.list_market_regime_snapshots_as_of(as_of_date, limit=1)
    regime_snapshot = regime_rows[0] if regime_rows else None

    tickers = sorted({_ticker(item.get("ticker")) for item in candidate_items if _ticker(item.get("ticker"))})
    quality_by_ticker: dict[str, dict] = {}
    memory_by_ticker: dict[str, dict] = {}
    journal_by_ticker: dict[str, dict] = {}
    for ticker in tickers:
        quality_rows = db.list_fundamental_quality_reports_as_of(ticker, as_of_date, limit=1)
        if quality_rows:
            quality_by_ticker[ticker] = quality_rows[0]
        memory = db.get_latest_research_memory_pack(ticker, as_of_date)
        if memory:
            memory_by_ticker[ticker] = memory
        journal = db.get_latest_decision_journal_entry(ticker, as_of_date)
        if journal:
            journal_by_ticker[ticker] = journal

    brief = build_boss_copilot_daily_brief(
        as_of_date=as_of_date,
        candidate_run=candidate_run,
        candidate_items=candidate_items,
        regime_snapshot=regime_snapshot,
        quality_by_ticker=quality_by_ticker,
        memory_by_ticker=memory_by_ticker,
        journal_by_ticker=journal_by_ticker,
        max_priorities=max_priorities,
    )
    db.save_boss_copilot_daily_brief(brief)
    output_dir = Path(output_root) / as_of_date
    paths = write_boss_copilot_daily_brief_artifacts(brief, output_dir)
    missing_total = sum(brief["summary"].get("missing_context_counts", {}).values())
    return {
        "status": brief["status"],
        "output_dir": str(output_dir),
        "priority_count": brief["summary"]["priority_count"],
        "high_priority_count": brief["summary"]["high_priority_count"],
        "manual_review_count": brief["summary"]["manual_review_count"],
        "missing_context_count": missing_total,
        "paths": paths,
    }
```

- [ ] **Step 3: Add hard-boundary test**

Append:

```python
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
```

- [ ] **Step 4: Add CLI tests**

Append to `test_batch_cli.py`:

```python
def test_boss_copilot_brief_run_cli_success_writes_artifacts(tmp_path, monkeypatch, capsys):
    from agent.research_v1.batch_cli import main

    app_root = tmp_path / "app"

    def fake_run(**kwargs):
        output_dir = kwargs["output_root"] / "2026-04-30"
        output_dir.mkdir(parents=True, exist_ok=True)
        return {
            "status": "brief_ready",
            "output_dir": str(output_dir),
            "priority_count": 2,
            "high_priority_count": 1,
            "manual_review_count": 0,
            "missing_context_count": 0,
        }

    monkeypatch.setattr("agent.research_v1.batch_cli.run_boss_copilot_daily_brief", fake_run)
    code = main(["--app-root", str(app_root), "boss-copilot-brief-run", "--as-of-date", "2026-04-30"])
    out = capsys.readouterr().out

    assert code == 0
    assert "Boss co-pilot brief status: brief_ready" in out
    assert str(app_root / "output" / "governance" / "2026-04-30") in out


def test_boss_copilot_brief_run_cli_rejects_invalid_date(tmp_path, capsys):
    from agent.research_v1.batch_cli import main

    code = main(["--app-root", str(tmp_path), "boss-copilot-brief-run", "--as-of-date", "not-a-date"])

    assert code == 2
    assert "invalid boss-copilot-brief-run input" in capsys.readouterr().out


def test_boss_copilot_brief_run_cli_rejects_non_positive_max_priorities(tmp_path, capsys):
    from agent.research_v1.batch_cli import main

    code = main(["--app-root", str(tmp_path), "boss-copilot-brief-run", "--as-of-date", "2026-04-30", "--max-priorities", "0"])

    assert code == 2
    assert "max-priorities must be positive" in capsys.readouterr().out
```

- [ ] **Step 5: Wire CLI**

In `batch_cli.py` imports:

```python
from agent.research_v1.boss_copilot_daily_brief import run_boss_copilot_daily_brief
```

Add command:

```python
def _cmd_boss_copilot_brief_run(paths: HermesPaths, as_of_date: str, output_root: str, max_priorities: int) -> int:
    from datetime import date as _date

    try:
        _date.fromisoformat(as_of_date)
    except (ValueError, TypeError):
        print(f"invalid boss-copilot-brief-run input: invalid date format '{as_of_date}'")
        return 2
    if max_priorities <= 0:
        print("invalid boss-copilot-brief-run input: max-priorities must be positive")
        return 2

    output_path = Path(output_root).expanduser()
    if not output_path.is_absolute():
        output_path = paths.app_root / output_path

    database = _ensure_database(paths)
    result = run_boss_copilot_daily_brief(
        db=database,
        as_of_date=as_of_date,
        output_root=output_path.resolve(),
        max_priorities=max_priorities,
    )
    if result.get("status") == "blocked_invalid_input":
        print(f"invalid boss-copilot-brief-run input: {result.get('warnings', ['unknown'])[0]}")
        return 2

    print(f"Boss co-pilot brief status: {result['status']}")
    print(f"Output dir: {result['output_dir']}")
    print(f"Priority count: {result['priority_count']}")
    print(f"High priority count: {result['high_priority_count']}")
    print(f"Manual review count: {result['manual_review_count']}")
    print(f"Missing context count: {result['missing_context_count']}")
    return 0
```

Add parser:

```python
copilot_parser = subparsers.add_parser("boss-copilot-brief-run", help="Run boss co-pilot daily brief.")
copilot_parser.add_argument("--as-of-date", required=True, help="As-of date YYYY-MM-DD.")
copilot_parser.add_argument("--output-root", default="output/governance", help="Root directory for boss co-pilot brief artifacts.")
copilot_parser.add_argument("--max-priorities", default=8, type=int, help="Maximum research priorities to include.")
```

Add dispatch:

```python
if args.command == "boss-copilot-brief-run":
    return _cmd_boss_copilot_brief_run(
        paths,
        as_of_date=args.as_of_date,
        output_root=args.output_root,
        max_priorities=args.max_priorities,
    )
```

- [ ] **Step 6: Run tests and commit P42-C**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_boss_copilot_daily_brief.py tests/agent/research_v1/test_batch_cli.py -q -k "boss_copilot or boss-copilot"
```

Commit:

```bash
git add agent/research_v1/boss_copilot_daily_brief.py agent/research_v1/batch_cli.py tests/agent/research_v1/test_boss_copilot_daily_brief.py tests/agent/research_v1/test_batch_cli.py
git commit -m "feat: add boss copilot brief cli"
```

## Task 4: P42-D Docs + Regression

**Files:**
- Modify: `README.md`
- Modify: `agent/research_v1/README.md`

- [ ] **Step 1: Update root README**

Add P42 section near P36-P41:

```markdown
### P42 Boss Co-Pilot Daily Brief

P42 aggregates existing P36-P41 evidence into a daily boss-facing research-priority brief. It reads recommendation outcomes, market regime, fundamental quality, candidate pools, research memory, and decision-journal guardrails, then writes `p42_boss_copilot_daily_brief.json` and `.md` under `output/governance/YYYY-MM-DD/`.

P42 is daily research-priority evidence only. It does not create recommendations, instruct trades, place orders, schedule jobs, send notifications, or mutate prior evidence.
```

Update verification count section with executor's actual test counts after tests run.

- [ ] **Step 2: Update research README Data Flow**

Add:

```markdown
#### P42 Boss Co-Pilot Daily Brief

`boss_copilot_daily_brief.py` reads persisted P36-P41 evidence and emits a daily research-priority brief for the boss. The flow is one-way: P42 does not call `HermesResearchApp.run()`, `final_judge`, P36-P41 runtime commands, or broker/order APIs. Missing upstream evidence is surfaced as limited context rather than hidden.
```

- [ ] **Step 3: Run verification**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_boss_copilot_daily_brief.py -q
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_batch_cli.py -q -k "boss_copilot or boss-copilot"
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_recommendation_outcomes.py tests/agent/research_v1/test_market_regime_context.py tests/agent/research_v1/test_fundamental_quality.py tests/agent/research_v1/test_candidate_pool.py tests/agent/research_v1/test_research_memory_pack.py tests/agent/research_v1/test_decision_journal_guardrails.py -q
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_governance_runtime.py tests/agent/research_v1/test_boss_governance_brief.py tests/agent/research_v1/test_signal_family_edge_review.py -q
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_doc_standards.py -q
```

Then run the full P20-P42 chain. If host-specific PDF/Futu checks fail, report them separately.

- [ ] **Step 4: Commit P42-D**

```bash
git add README.md agent/research_v1/README.md
git commit -m "docs: document p42 boss copilot brief"
```

## Final Report Template

```text
P42 Implementation Complete

Status Summary
Phase   Status   Commit
P42-A   PASS     <commit> feat: add boss copilot daily brief
P42-B   PASS     <commit> feat: persist boss copilot briefs
P42-C   PASS     <commit> feat: add boss copilot brief cli
P42-D   PASS     <commit> docs: document p42 boss copilot brief

Verification
- P42 focused: <n> passed
- P42 CLI: <n> passed
- P36-P41 regression: <n> passed
- Governance-adjacent regression: <n> passed
- Doc standards: <n> passed
- Full P20-P42 chain: <n> passed, with known host-specific gaps listed separately

Files Changed
- agent/research_v1/boss_copilot_daily_brief.py
- agent/research_v1/data/database.py
- agent/research_v1/batch_cli.py
- tests/agent/research_v1/test_boss_copilot_daily_brief.py
- tests/agent/research_v1/test_batch_cli.py
- README.md
- agent/research_v1/README.md

Hard Boundary Compliance
- no auto-trading
- no broker orders
- no production approval
- no production config mutation
- no model training
- no scheduling or notifications
- no viewer
- no final_judge changes
- no HermesResearchApp.run invocation
- no CanonicalSignal or CanonicalReport creation
- no JudgeInputPacket mutation
- no P36/P37/P38/P39/P40/P41 mutation
- no P36-P41 runtime invocation
```

## Review Checklist

- [ ] P42 only reads existing evidence.
- [ ] Missing upstream evidence is explicit.
- [ ] As-of lookups cannot use future evidence.
- [ ] Same-day revisions use latest `created_at`.
- [ ] Source hash changes when selected upstream source hash changes.
- [ ] Manual-review guardrails force `context_blocked`.
- [ ] Markdown has no forbidden trading language.
- [ ] CLI validates date and max priorities.
- [ ] Docs mention P42 in root and research README.
