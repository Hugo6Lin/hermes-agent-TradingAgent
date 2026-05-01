# P41 Decision Journal Guardrails Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone deterministic decision journal and behavioral guardrail layer so Hermes can surface emotional-decision risks without changing recommendations.

**Architecture:** Add `decision_journal_guardrails.py` for input validation, P40 memory lookup, guardrail scoring, source hashing, artifact writing, and run orchestration. Extend `ResearchDatabase` with append-only decision-journal persistence and P40 lookup helpers, then expose a local `decision-journal-run` CLI command.

**Tech Stack:** Python 3.11, sqlite3, pathlib, json, hashlib, datetime, argparse, pytest.

---

## File Structure

- Create `agent/research_v1/decision_journal_guardrails.py`
  - P41 constants, decision validation, memory lookup adaptation, guardrail generation, source hashing, artifact writing, and run orchestration.
- Modify `agent/research_v1/data/database.py`
  - Add decision-journal schema, persistence/query helpers, and latest P40 memory helper.
- Modify `agent/research_v1/batch_cli.py`
  - Add `decision-journal-run`.
- Create `tests/agent/research_v1/test_decision_journal_guardrails.py`
  - Focused P41 validation, guardrail, source-hash, persistence, artifact, and hard-boundary tests.
- Modify `tests/agent/research_v1/test_batch_cli.py`
  - Add CLI tests for `decision-journal-run`.
- Modify `README.md` and `agent/research_v1/README.md`
  - Document P41 as standalone behavioral guardrail evidence.

Do not modify `app.py`, `final_judge.py`, `orchestrator.py`, `contracts.py`, `recommendation_outcomes.py`, `market_regime_context.py`, `fundamental_quality.py`, `candidate_pool.py`, or `research_memory_pack.py`.

## Constants

Use these exact constants:

```python
P41_SCHEMA_VERSION = "p41_decision_journal.1"

P41_STATUS_COMPLETED = "completed"
P41_STATUS_COMPLETED_WITH_WARNINGS = "completed_with_warnings"
P41_STATUS_BLOCKED_INVALID_INPUT = "blocked_invalid_input"

SEVERITY_INFO = "info"
SEVERITY_CAUTION = "caution"
SEVERITY_SLOW_DOWN = "slow_down"
SEVERITY_MANUAL_REVIEW = "manual_review"

P41_ARTIFACT_DISCLAIMER = (
    "P41 is behavioral guardrail evidence only. It records decision context "
    "and does not recommend trades, place orders, approve production adoption, "
    "train models, schedule jobs, or mutate research decisions."
)
```

Allowed actions:

```python
P41_ALLOWED_ACTIONS = (
    "research_candidate",
    "monitor_candidate",
    "defer_candidate",
    "review_existing_signal",
    "journal_only",
)
```

Forbidden action fragments:

```python
P41_FORBIDDEN_ACTION_FRAGMENTS = (
    "buy",
    "sell",
    "short",
    "call",
    "put",
    "trade_now",
)
```

## Task 1: P41-A Guardrail Engine

**Files:**
- Create: `agent/research_v1/decision_journal_guardrails.py`
- Create: `tests/agent/research_v1/test_decision_journal_guardrails.py`

- [ ] **Step 1: Write failing validation and guardrail tests**

Create `tests/agent/research_v1/test_decision_journal_guardrails.py`:

```python
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
```

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_decision_journal_guardrails.py -q
```

Expected: import failure for `agent.research_v1.decision_journal_guardrails`.

- [ ] **Step 2: Implement constants, validation, and source hash**

Create `agent/research_v1/decision_journal_guardrails.py`:

```python
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

P41_SCHEMA_VERSION = "p41_decision_journal.1"
P41_STATUS_COMPLETED = "completed"
P41_STATUS_COMPLETED_WITH_WARNINGS = "completed_with_warnings"
P41_STATUS_BLOCKED_INVALID_INPUT = "blocked_invalid_input"

SEVERITY_INFO = "info"
SEVERITY_CAUTION = "caution"
SEVERITY_SLOW_DOWN = "slow_down"
SEVERITY_MANUAL_REVIEW = "manual_review"

P41_ARTIFACT_DISCLAIMER = (
    "P41 is behavioral guardrail evidence only. It records decision context "
    "and does not recommend trades, place orders, approve production adoption, "
    "train models, schedule jobs, or mutate research decisions."
)

P41_ALLOWED_ACTIONS = (
    "research_candidate",
    "monitor_candidate",
    "defer_candidate",
    "review_existing_signal",
    "journal_only",
)

P41_FORBIDDEN_ACTION_FRAGMENTS = ("buy", "sell", "short", "call", "put", "trade_now")
P41_REQUIRED_FIELDS = ("ticker", "contemplated_action", "decision_intent", "stated_reason", "boss_confidence", "urgency")
```

Implement:

```python
def _normalize_ticker(ticker: str) -> str:
    return str(ticker).strip().upper()


def validate_decision_item(item: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(item, dict):
        return ["decision_item_not_dict"]
    for field in P41_REQUIRED_FIELDS:
        if field not in item or item[field] in (None, ""):
            errors.append(f"missing:{field}")
    action = str(item.get("contemplated_action", "")).lower()
    if action not in P41_ALLOWED_ACTIONS:
        errors.append("invalid_contemplated_action")
    if any(fragment in action for fragment in P41_FORBIDDEN_ACTION_FRAGMENTS):
        errors.append("forbidden_contemplated_action")
    try:
        confidence = float(item.get("boss_confidence", 0))
        if confidence < 0 or confidence > 1:
            errors.append("boss_confidence_out_of_range")
    except (TypeError, ValueError):
        errors.append("boss_confidence_not_numeric")
    return sorted(set(errors))


def compute_decision_journal_source_hash(decision: dict[str, Any], as_of_date: str, memory_pack: dict[str, Any] | None) -> str:
    canonical = {
        "schema_version": P41_SCHEMA_VERSION,
        "as_of_date": as_of_date,
        "decision": decision,
        "memory_pack_id": (memory_pack or {}).get("pack_id", ""),
        "memory_source_hash": (memory_pack or {}).get("source_hash", ""),
    }
    return hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()
```

- [ ] **Step 3: Implement guardrail generation**

Implement:

```python
def _flag(flag_id: str, severity: str, reason: str) -> dict[str, str]:
    return {"flag_id": flag_id, "severity": severity, "reason": reason}


def build_guardrail_flags(decision: dict[str, Any], memory_pack: dict[str, Any] | None) -> tuple[list[dict[str, str]], list[str]]:
    flags: list[dict[str, str]] = []
    missing_context: list[str] = []
    confidence = float(decision.get("boss_confidence", 0.0))
    urgency = str(decision.get("urgency", "")).lower()
    if urgency == "high" and confidence >= 0.80:
        flags.append(_flag("high_urgency_high_confidence", SEVERITY_SLOW_DOWN, "High urgency and confidence can amplify impulsive decisions."))
    if decision.get("time_pressure") == "same_day":
        flags.append(_flag("time_pressure_same_day", SEVERITY_SLOW_DOWN, "Same-day time pressure is visible."))
    if decision.get("recent_pnl_state") == "drawdown":
        flags.append(_flag("recent_drawdown_context", SEVERITY_SLOW_DOWN, "Recent drawdown context is visible."))
    position = decision.get("position_context") or {}
    if float(position.get("current_position_pct", 0.0) or 0.0) >= 0.15:
        flags.append(_flag("position_concentration_high", SEVERITY_MANUAL_REVIEW, "Position concentration is high."))
    if float(position.get("sector_exposure_pct", 0.0) or 0.0) >= 0.40:
        flags.append(_flag("sector_concentration_high", SEVERITY_MANUAL_REVIEW, "Sector concentration is high."))
    if float(position.get("cash_available_pct", 1.0) or 1.0) <= 0.05:
        flags.append(_flag("cash_constraint_visible", SEVERITY_CAUTION, "Cash constraint is visible."))
    if not memory_pack:
        missing_context.append("missing_memory_pack")
        flags.append(_flag("missing_memory_pack", SEVERITY_CAUTION, "No P40 memory pack was found."))
    else:
        for item in memory_pack.get("missing_context", []):
            missing_context.append(item)
            flags.append(_flag(item, SEVERITY_CAUTION, f"Memory pack missing context: {item}"))
        risk_memory = set(memory_pack.get("risk_memory", []))
        if "quality_red_flags_present" in risk_memory:
            flags.append(_flag("quality_red_flags_present", SEVERITY_MANUAL_REVIEW, "P40 memory includes quality red flags."))
        if "negative_outcome_history" in risk_memory:
            flags.append(_flag("negative_outcome_memory", SEVERITY_SLOW_DOWN, "P40 memory includes negative outcome history."))
        if "prior_insufficient_outcome_data" in risk_memory:
            flags.append(_flag("insufficient_outcome_memory", SEVERITY_CAUTION, "Prior outcome data is insufficient."))
        if "stale_research_context" in memory_pack.get("recurring_themes", []):
            flags.append(_flag("stale_research_memory", SEVERITY_SLOW_DOWN, "P40 memory indicates stale research context."))
    return flags, sorted(set(missing_context))
```

Implement severity ranking and cooling-off:

```python
SEVERITY_RANK = {SEVERITY_INFO: 0, SEVERITY_CAUTION: 1, SEVERITY_SLOW_DOWN: 2, SEVERITY_MANUAL_REVIEW: 3}

def _entry_severity(flags: list[dict[str, str]]) -> str:
    if not flags:
        return SEVERITY_INFO
    return max((f["severity"] for f in flags), key=lambda s: SEVERITY_RANK[s])


def _cooling_off(severity: str, flags: list[dict[str, str]]) -> str:
    flag_ids = {f["flag_id"] for f in flags}
    if severity == SEVERITY_MANUAL_REVIEW:
        return "manual_review_before_action"
    if severity == SEVERITY_SLOW_DOWN and ("recent_drawdown_context" in flag_ids or "time_pressure_same_day" in flag_ids):
        return "recheck_next_session"
    if severity == SEVERITY_SLOW_DOWN:
        return "recheck_after_30_minutes"
    return "none"
```

- [ ] **Step 4: Implement `build_decision_journal_entry()`**

```python
def build_decision_journal_entry(decision: dict[str, Any], as_of_date: str, memory_pack: dict[str, Any] | None) -> dict[str, Any]:
    errors = validate_decision_item(decision)
    ticker = _normalize_ticker(decision.get("ticker", ""))
    source_hash = compute_decision_journal_source_hash(decision, as_of_date, memory_pack)
    journal_id = hashlib.sha256(f"{ticker}|{as_of_date}|{decision.get('contemplated_action', '')}|{source_hash}".encode("utf-8")).hexdigest()[:16]
    flags, missing_context = build_guardrail_flags(decision, memory_pack)
    if errors:
        flags.append(_flag("manual_review_required", SEVERITY_MANUAL_REVIEW, "Decision input failed validation."))
    severity = _entry_severity(flags)
    return {
        "schema_version": P41_SCHEMA_VERSION,
        "journal_id": journal_id,
        "as_of_date": as_of_date,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "ticker": ticker,
        "contemplated_action": decision.get("contemplated_action", ""),
        "decision_intent": decision.get("decision_intent", ""),
        "stated_reason": decision.get("stated_reason", ""),
        "boss_confidence": decision.get("boss_confidence"),
        "urgency": decision.get("urgency", ""),
        "time_pressure": decision.get("time_pressure", ""),
        "recent_pnl_state": decision.get("recent_pnl_state", ""),
        "position_context": decision.get("position_context", {}),
        "manual_notes": decision.get("manual_notes", []),
        "memory_ref": {
            "pack_id": (memory_pack or {}).get("pack_id", ""),
            "source_hash": (memory_pack or {}).get("source_hash", ""),
        },
        "guardrail_flags": flags,
        "severity": severity,
        "cooling_off_suggestion": _cooling_off(severity, flags),
        "missing_context": missing_context,
        "source_hash": source_hash,
        "disclaimer": P41_ARTIFACT_DISCLAIMER,
    }
```

- [ ] **Step 5: Add focused guardrail tests**

Append:

```python
def test_high_urgency_high_confidence_slow_down():
    entry = build_decision_journal_entry(_decision(urgency="high", boss_confidence=0.90), "2026-04-30", None)
    flags = {f["flag_id"] for f in entry["guardrail_flags"]}
    assert "high_urgency_high_confidence" in flags
    assert entry["severity"] in {"slow_down", "manual_review"}


def test_high_concentration_manual_review():
    entry = build_decision_journal_entry(_decision(position_context={"current_position_pct": 0.20, "sector_exposure_pct": 0.10}), "2026-04-30", None)
    assert entry["severity"] == "manual_review"
    assert entry["cooling_off_suggestion"] == "manual_review_before_action"


def test_source_hash_changes_when_memory_source_changes():
    decision = _decision()
    first = build_decision_journal_entry(decision, "2026-04-30", {"pack_id": "p1", "source_hash": "h1"})
    second = build_decision_journal_entry(decision, "2026-04-30", {"pack_id": "p1", "source_hash": "h2"})
    assert first["source_hash"] != second["source_hash"]
```

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_decision_journal_guardrails.py -q
```

Expected: P41-A tests pass.

- [ ] **Step 6: Commit P41-A**

```bash
git add agent/research_v1/decision_journal_guardrails.py tests/agent/research_v1/test_decision_journal_guardrails.py
git commit -m "feat: add decision journal guardrails"
```

## Task 2: P41-B Persistence + Artifacts

**Files:**
- Modify: `agent/research_v1/data/database.py`
- Modify: `agent/research_v1/decision_journal_guardrails.py`
- Modify: `tests/agent/research_v1/test_decision_journal_guardrails.py`

- [ ] **Step 1: Write failing persistence and artifact tests**

Append:

```python
from agent.research_v1.data.database import ResearchDatabase
from agent.research_v1.decision_journal_guardrails import write_decision_journal_artifacts


def _db(tmp_path: Path) -> ResearchDatabase:
    db = ResearchDatabase(str(tmp_path / "research.db"))
    db.initialize()
    db.initialize_decision_journal_schema()
    return db


def test_decision_journal_persistence_is_idempotent(tmp_path: Path):
    db = _db(tmp_path)
    entry = build_decision_journal_entry(_decision(), "2026-04-30", None)
    first = db.save_decision_journal_entry(entry)
    second = db.save_decision_journal_entry(entry)
    rows = db.list_decision_journal_entries(ticker="AAPL", as_of_date="2026-04-30")
    assert first == second
    assert len(rows) == 1


def test_decision_journal_revised_source_hash_appends(tmp_path: Path):
    db = _db(tmp_path)
    first_entry = build_decision_journal_entry(_decision(stated_reason="first"), "2026-04-30", None)
    second_entry = build_decision_journal_entry(_decision(stated_reason="second"), "2026-04-30", None)
    first = db.save_decision_journal_entry(first_entry)
    second = db.save_decision_journal_entry(second_entry)
    rows = db.list_decision_journal_entries(ticker="AAPL", as_of_date="2026-04-30")
    assert first != second
    assert len(rows) == 2


def test_decision_journal_artifacts_are_written_and_safe(tmp_path: Path):
    entry = build_decision_journal_entry(_decision(), "2026-04-30", None)
    payload = {
        "schema_version": P41_SCHEMA_VERSION,
        "as_of_date": "2026-04-30",
        "created_at": entry["created_at"],
        "source": "fixture",
        "status": "completed",
        "entries": [entry],
        "summary": {"entry_count": 1, "manual_review_count": 0, "slow_down_count": 1},
        "warnings": [],
        "disclaimer": entry["disclaimer"],
    }
    paths = write_decision_journal_artifacts(payload, tmp_path / "output" / "governance" / "2026-04-30")
    text = paths["md"].read_text(encoding="utf-8").lower()
    assert paths["json"].name == "p41_decision_journal.json"
    assert "p41 is behavioral guardrail evidence only" in text
    assert "trade now" not in text
```

- [ ] **Step 2: Add database schema and helpers**

Add to `ResearchDatabase`:

```python
def initialize_decision_journal_schema(self) -> None:
    conn = self._get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS decision_journal_entries (
            journal_id TEXT PRIMARY KEY,
            schema_version TEXT NOT NULL,
            as_of_date TEXT NOT NULL,
            created_at TEXT NOT NULL,
            ticker TEXT NOT NULL,
            contemplated_action TEXT NOT NULL,
            decision_intent TEXT NOT NULL,
            boss_confidence REAL,
            urgency TEXT,
            severity TEXT NOT NULL,
            cooling_off_suggestion TEXT NOT NULL,
            memory_pack_id TEXT,
            source_hash TEXT NOT NULL,
            entry_json TEXT NOT NULL,
            UNIQUE(ticker, as_of_date, contemplated_action, source_hash)
        )
    """)
    conn.commit()
    conn.close()
```

Implement:

- `save_decision_journal_entry(entry: dict) -> str`
- `list_decision_journal_entries(ticker: str | None = None, as_of_date: str | None = None, limit: int = 20) -> list[dict]`
- `get_latest_research_memory_pack(ticker: str, as_of_date: str) -> dict | None`

`get_latest_research_memory_pack` must query:

```sql
SELECT * FROM research_memory_packs
WHERE ticker = ? AND as_of_date <= ?
ORDER BY as_of_date DESC, created_at DESC, pack_id ASC
LIMIT 1
```

It must decode JSON columns back into the P40 pack shape used by P41.

- [ ] **Step 3: Add artifact writer**

In `decision_journal_guardrails.py`, implement:

```python
def write_decision_journal_artifacts(payload: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "p41_decision_journal.json"
    md_path = output_dir / "p41_decision_journal.md"
    json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    lines = [
        f"# Decision Journal Guardrails - {payload.get('as_of_date', '')}",
        "",
        f"- Status: {payload.get('status', '')}",
        f"- Entries: {len(payload.get('entries', []))}",
        "",
        "## Journal Summary",
        "",
        "| Ticker | Action | Severity | Cooling-Off Suggestion | Flags |",
        "|--------|--------|----------|------------------------|-------|",
    ]
    for entry in payload.get("entries", []):
        flags = ", ".join(f["flag_id"] for f in entry.get("guardrail_flags", [])[:4])
        lines.append(
            f"| {entry['ticker']} | {entry['contemplated_action']} | "
            f"{entry['severity']} | {entry['cooling_off_suggestion']} | {flags} |"
        )
    lines.extend(["", "## Missing Context", ""])
    any_missing = False
    for entry in payload.get("entries", []):
        if entry.get("missing_context"):
            any_missing = True
            lines.append(f"- {entry['ticker']}: {', '.join(entry['missing_context'])}")
    if not any_missing:
        lines.append("- None")
    lines.extend(["", "---", "", f"> {payload.get('disclaimer', P41_ARTIFACT_DISCLAIMER)}", ""])
    markdown = "\n".join(lines)
    lowered = markdown.lower()
    for forbidden in ("buy this now", "sell this now", "follow this trade", "guaranteed edge", "production approved", "model promoted", "trade now", "order ticket"):
        if forbidden in lowered:
            raise ValueError(f"forbidden decision-journal term rendered: {forbidden}")
    md_path.write_text(markdown, encoding="utf-8")
    return {"json": json_path, "md": md_path}
```

- [ ] **Step 4: Run tests and commit P41-B**

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_decision_journal_guardrails.py -q
git add agent/research_v1/decision_journal_guardrails.py agent/research_v1/data/database.py tests/agent/research_v1/test_decision_journal_guardrails.py
git commit -m "feat: persist decision journal entries"
```

## Task 3: P41-C Run Orchestration + CLI

**Files:**
- Modify: `agent/research_v1/decision_journal_guardrails.py`
- Modify: `agent/research_v1/batch_cli.py`
- Modify: `tests/agent/research_v1/test_decision_journal_guardrails.py`
- Modify: `tests/agent/research_v1/test_batch_cli.py`

- [ ] **Step 1: Write failing run and hard-boundary tests**

Append:

```python
from agent.research_v1.decision_journal_guardrails import run_decision_journal_guardrails


def test_run_decision_journal_guardrails_persists_and_writes_artifacts(tmp_path: Path):
    db = _db(tmp_path)
    payload = {"as_of_date": "2026-04-30", "source": "fixture", "decisions": [_decision()]}
    result = run_decision_journal_guardrails(db, payload, as_of_date="2026-04-30", output_root=tmp_path / "output" / "governance")
    assert result["entry_count"] == 1
    assert (Path(result["output_dir"]) / "p41_decision_journal.json").exists()


def test_p41_hard_boundaries_are_explicit():
    from agent.research_v1 import decision_journal_guardrails as p41
    forbidden_names = {
        "broker", "order", "train_model", "scheduler", "notification",
        "HermesResearchApp", "run_research", "final_judge", "JudgeInputPacket",
        "CanonicalSignal", "CanonicalReport", "run_governance_runtime",
        "run_recommendation_outcome_tracking", "run_market_regime_context",
        "run_fundamental_quality", "run_candidate_pool", "run_research_memory_pack",
        "_extract_thesis_inputs",
    }
    assert not (forbidden_names & set(p41.__dict__))
    assert "behavioral guardrail evidence only" in p41.P41_ARTIFACT_DISCLAIMER
```

- [ ] **Step 2: Implement `run_decision_journal_guardrails()`**

```python
def run_decision_journal_guardrails(
    db: Any,
    input_payload: dict[str, Any],
    as_of_date: str | None = None,
    output_root: Path | None = None,
) -> dict[str, Any]:
    effective_as_of = as_of_date or input_payload.get("as_of_date", "")
    decisions = input_payload.get("decisions", [])
    if not effective_as_of or not isinstance(decisions, list) or not decisions:
        return {"status": P41_STATUS_BLOCKED_INVALID_INPUT, "entry_count": 0, "warnings": ["invalid input"]}
    db.initialize_decision_journal_schema()
    entries: list[dict[str, Any]] = []
    warnings: list[str] = []
    for item in decisions:
        errors = validate_decision_item(item if isinstance(item, dict) else {})
        if errors:
            warnings.extend(errors)
            if "forbidden_contemplated_action" in errors or "invalid_contemplated_action" in errors:
                return {"status": P41_STATUS_BLOCKED_INVALID_INPUT, "entry_count": 0, "warnings": errors}
        ticker = _normalize_ticker(item.get("ticker", ""))
        try:
            memory_pack = db.get_latest_research_memory_pack(ticker, effective_as_of)
        except Exception:
            memory_pack = None
        entry = build_decision_journal_entry(item, effective_as_of, memory_pack)
        db.save_decision_journal_entry(entry)
        entries.append(entry)
    manual_review_count = sum(1 for e in entries if e["severity"] == SEVERITY_MANUAL_REVIEW)
    slow_down_count = sum(1 for e in entries if e["severity"] == SEVERITY_SLOW_DOWN)
    status = P41_STATUS_COMPLETED_WITH_WARNINGS if warnings else P41_STATUS_COMPLETED
    payload = {
        "schema_version": P41_SCHEMA_VERSION,
        "as_of_date": effective_as_of,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": input_payload.get("source", ""),
        "status": status,
        "entries": entries,
        "summary": {
            "entry_count": len(entries),
            "manual_review_count": manual_review_count,
            "slow_down_count": slow_down_count,
        },
        "warnings": warnings,
        "disclaimer": P41_ARTIFACT_DISCLAIMER,
    }
    output_dir = Path(output_root or "output/governance") / effective_as_of
    paths = write_decision_journal_artifacts(payload, output_dir)
    return {
        "status": status,
        "output_dir": str(output_dir),
        "entry_count": len(entries),
        "manual_review_count": manual_review_count,
        "slow_down_count": slow_down_count,
        "warning_count": len(warnings),
        "paths": paths,
    }
```

- [ ] **Step 3: Write failing CLI tests**

Append to `tests/agent/research_v1/test_batch_cli.py`:

```python
def test_decision_journal_run_cli_success_writes_artifacts(tmp_path, monkeypatch, capsys):
    from agent.research_v1.batch_cli import main
    app_root = tmp_path / "app"
    input_path = tmp_path / "journal.json"
    input_path.write_text('{"as_of_date":"2026-04-30","source":"fixture","decisions":[{"ticker":"AAPL","contemplated_action":"research_candidate","decision_intent":"review_before_action","stated_reason":"fixture","boss_confidence":0.8,"urgency":"high"}]}', encoding="utf-8")

    def fake_run(**kwargs):
        output_dir = kwargs["output_root"] / "2026-04-30"
        output_dir.mkdir(parents=True, exist_ok=True)
        return {"status": "completed", "output_dir": str(output_dir), "entry_count": 1, "manual_review_count": 0, "slow_down_count": 1, "warning_count": 0}

    monkeypatch.setattr("agent.research_v1.batch_cli.run_decision_journal_guardrails", fake_run)
    code = main(["--app-root", str(app_root), "decision-journal-run", "--input", str(input_path), "--as-of-date", "2026-04-30"])
    out = capsys.readouterr().out
    assert code == 0
    assert "Decision journal status: completed" in out
    assert str(app_root / "output" / "governance" / "2026-04-30") in out


def test_decision_journal_run_cli_rejects_invalid_date(tmp_path, capsys):
    from agent.research_v1.batch_cli import main
    input_path = tmp_path / "journal.json"
    input_path.write_text('{"decisions":[]}', encoding="utf-8")
    code = main(["--app-root", str(tmp_path), "decision-journal-run", "--input", str(input_path), "--as-of-date", "not-a-date"])
    assert code == 2
    assert "invalid decision-journal-run input" in capsys.readouterr().out
```

- [ ] **Step 4: Implement CLI**

In `batch_cli.py`:

- Import `run_decision_journal_guardrails`.
- Add `_cmd_decision_journal_run(paths, input_path, as_of_date, output_root)`.
- Validate file exists.
- Validate JSON.
- Validate effective date if provided or from payload.
- Validate `decisions` is a non-empty list of dicts.
- Resolve relative `output_root` under `paths.app_root`.
- Call `run_decision_journal_guardrails`.
- Print exact summary lines from the spec.
- Return `2` for invalid input or blocked runtime input.

Add parser:

```python
journal_parser = subparsers.add_parser("decision-journal-run", help="Run decision journal guardrails.")
journal_parser.add_argument("--input", required=True, help="Path to a JSON decision journal input file.")
journal_parser.add_argument("--as-of-date", default=None, help="Override as-of date YYYY-MM-DD.")
journal_parser.add_argument("--output-root", default="output/governance", help="Root directory for decision journal artifacts.")
```

- [ ] **Step 5: Run tests and commit P41-C**

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_decision_journal_guardrails.py tests/agent/research_v1/test_batch_cli.py -q -k "decision_journal or decision-journal"
git add agent/research_v1/decision_journal_guardrails.py agent/research_v1/batch_cli.py tests/agent/research_v1/test_decision_journal_guardrails.py tests/agent/research_v1/test_batch_cli.py
git commit -m "feat: add decision journal cli"
```

## Task 4: P41-D Docs + Regression

**Files:**
- Modify: `README.md`
- Modify: `agent/research_v1/README.md`

- [ ] **Step 1: Update root README**

Document:

- `agent/research_v1/decision_journal_guardrails.py`
- `decision-journal-run`
- `p41_decision_journal.{json,md}`
- P41 is behavioral guardrail evidence only.
- P41 does not block action, place orders, or alter recommendations.

- [ ] **Step 2: Update research README Data Flow**

Add:

```text
P41 decision_journal_guardrails.py reads explicit boss decision-journal input plus read-only P40 memory packs and emits behavioral guardrail evidence. It does not call HermesResearchApp.run(), final_judge, JudgeInputPacket, or broker/order APIs.
```

- [ ] **Step 3: Run verification**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_decision_journal_guardrails.py -q
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_batch_cli.py -q -k "decision_journal or decision-journal"
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_recommendation_outcomes.py tests/agent/research_v1/test_market_regime_context.py tests/agent/research_v1/test_fundamental_quality.py tests/agent/research_v1/test_candidate_pool.py tests/agent/research_v1/test_research_memory_pack.py -q
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_governance_runtime.py tests/agent/research_v1/test_boss_governance_brief.py tests/agent/research_v1/test_signal_family_edge_review.py -q
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_doc_standards.py -q
```

Then run the full P20-P41 chain. If host-specific PDF/Futu checks fail, report them separately.

- [ ] **Step 4: Commit P41-D**

```bash
git add README.md agent/research_v1/README.md
git commit -m "docs: document p41 decision journal"
```

## Final Report Format

```text
P41 Implementation Complete

Status Summary
Phase   Status   Commit
P41-A   PASS     <commit> feat: add decision journal guardrails
P41-B   PASS     <commit> feat: persist decision journal entries
P41-C   PASS     <commit> feat: add decision journal cli
P41-D   PASS     <commit> docs: document p41 decision journal

Verification
- P41 focused: <n> passed
- P41 CLI: <n> passed
- P36-P40 regression: <n> passed
- Governance-adjacent regression: <n> passed
- Doc standards: <n> passed
- Full P20-P41 chain: <n> passed, with known host-specific gaps listed separately

Files Changed
- agent/research_v1/decision_journal_guardrails.py
- agent/research_v1/data/database.py
- agent/research_v1/batch_cli.py
- tests/agent/research_v1/test_decision_journal_guardrails.py
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
- no P36/P37/P38/P39/P40 mutation
```

## Review Checklist

- [ ] Forbidden contemplated actions are blocked.
- [ ] Guardrail severity is deterministic.
- [ ] Cooling-off suggestion is suggestion-only.
- [ ] P40 memory is consumed read-only.
- [ ] Missing P40 memory is explicit.
- [ ] Source hash changes when boss input or memory source changes.
- [ ] Persistence is idempotent and append-only.
- [ ] Markdown contains no forbidden trading instructions.
- [ ] CLI rejects invalid inputs.
- [ ] No research decision path changed.
