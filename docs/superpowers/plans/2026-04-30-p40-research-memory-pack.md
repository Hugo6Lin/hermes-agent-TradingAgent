# P40 Research Memory Pack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone deterministic research-memory pack so Hermes can surface prior ticker context without changing recommendations.

**Architecture:** Add `research_memory_pack.py` for ticker normalization, read-only collection from existing DB tables, deterministic memory pack construction, source hashing, artifact writing, and run orchestration. Extend `ResearchDatabase` with query helpers and append-only memory-pack persistence, then expose a local `memory-pack-run` CLI command.

**Tech Stack:** Python 3.11, sqlite3, pathlib, json, hashlib, datetime, statistics, argparse, pytest.

---

## File Structure

- Create `agent/research_v1/research_memory_pack.py`
  - P40 constants, input normalization, DB row collection adapters, memory pack building, source hashing, artifact writing, and run orchestration.
- Modify `agent/research_v1/data/database.py`
  - Add read helpers for ticker history and add `research_memory_packs` persistence.
- Modify `agent/research_v1/batch_cli.py`
  - Add `memory-pack-run`.
- Create `tests/agent/research_v1/test_research_memory_pack.py`
  - Focused P40 normalization, collection, summary, source-hash, persistence, artifact, CLI-adjacent, and hard-boundary tests.
- Modify `tests/agent/research_v1/test_batch_cli.py`
  - Add CLI tests for `memory-pack-run`.
- Modify `README.md` and `agent/research_v1/README.md`
  - Document P40 as standalone research-memory evidence.

Do not modify `app.py`, `final_judge.py`, `orchestrator.py`, `contracts.py`, `recommendation_outcomes.py`, `market_regime_context.py`, `fundamental_quality.py`, or `candidate_pool.py` in this phase.

## Constants

Use these exact constants in `agent/research_v1/research_memory_pack.py`:

```python
P40_SCHEMA_VERSION = "p40_research_memory_pack.1"

P40_STATUS_MEMORY_AVAILABLE = "memory_available"
P40_STATUS_LIMITED_MEMORY = "limited_memory"
P40_STATUS_NO_PRIOR_MEMORY = "no_prior_memory"
P40_STATUS_BLOCKED_INVALID_INPUT = "blocked_invalid_input"

P40_ARTIFACT_DISCLAIMER = (
    "P40 is research-memory evidence only. It summarizes historical Hermes "
    "context and does not recommend trades, approve production adoption, place "
    "orders, train models, schedule jobs, or mutate research decisions."
)

P40_FORBIDDEN_TERMS = (
    "buy this now",
    "sell this now",
    "follow this trade",
    "guaranteed edge",
    "production approved",
    "model promoted",
    "trade now",
)
```

## Task 1: P40-A Memory Collector + Pack Builder

**Files:**
- Create: `agent/research_v1/research_memory_pack.py`
- Create: `tests/agent/research_v1/test_research_memory_pack.py`

- [ ] **Step 1: Write failing normalization and pack tests**

Create `tests/agent/research_v1/test_research_memory_pack.py`:

```python
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
```

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_research_memory_pack.py -q
```

Expected: import failure for `agent.research_v1.research_memory_pack`.

- [ ] **Step 2: Implement constants and normalization**

Create `agent/research_v1/research_memory_pack.py` with:

```python
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any

P40_SCHEMA_VERSION = "p40_research_memory_pack.1"
P40_STATUS_MEMORY_AVAILABLE = "memory_available"
P40_STATUS_LIMITED_MEMORY = "limited_memory"
P40_STATUS_NO_PRIOR_MEMORY = "no_prior_memory"
P40_STATUS_BLOCKED_INVALID_INPUT = "blocked_invalid_input"

P40_ARTIFACT_DISCLAIMER = (
    "P40 is research-memory evidence only. It summarizes historical Hermes "
    "context and does not recommend trades, approve production adoption, place "
    "orders, train models, schedule jobs, or mutate research decisions."
)

P40_FORBIDDEN_TERMS = (
    "buy this now",
    "sell this now",
    "follow this trade",
    "guaranteed edge",
    "production approved",
    "model promoted",
    "trade now",
)


def normalize_memory_tickers(tickers: list[str]) -> list[str]:
    cleaned = {str(t).strip().upper() for t in tickers if str(t).strip()}
    return sorted(cleaned)
```

- [ ] **Step 3: Implement action resolution and summaries**

Implement helpers:

```python
def _json_load(value: Any, fallback: Any) -> Any:
    if value is None:
        return fallback
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError, ValueError):
        return fallback


def _resolve_visible_action(report: dict[str, Any]) -> tuple[str, list[str]]:
    warnings: list[str] = []
    decision_card = report.get("decision_card") or _json_load(report.get("decision_card_json"), None)
    instrument = report.get("instrument_rec") or _json_load(report.get("instrument_rec_json"), None)
    trade_plan = report.get("trade_plan") or _json_load(report.get("trade_plan_json"), None)
    if isinstance(decision_card, dict) and decision_card.get("primary_action"):
        return str(decision_card["primary_action"]), warnings
    if isinstance(instrument, dict) and instrument.get("primary_action"):
        return str(instrument["primary_action"]), warnings
    if isinstance(trade_plan, dict) and trade_plan.get("action"):
        warnings.append("legacy_action_fallback_used")
        return str(trade_plan["action"]), warnings
    return "unknown_prior_action", warnings
```

Implement:

- `_summarize_outcomes(outcomes_by_signal: dict[str, list[dict]]) -> dict`
- `_summarize_candidate_history(candidate_items: list[dict]) -> dict`
- `_quality_context(quality_report: dict | None, missing_context: list[str]) -> dict`
- `_regime_context(regime_snapshot: dict | None, missing_context: list[str]) -> dict`
- `_derive_recurring_themes(pack_parts: dict) -> list[str]`
- `_derive_risk_memory(pack_parts: dict, action_warnings: list[str]) -> list[str]`

Use deterministic sorted lists.

- [ ] **Step 4: Implement source hash and `build_research_memory_pack()`**

Implement:

```python
def compute_research_memory_source_hash(pack_seed: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(pack_seed, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()
```

Implement:

```python
def build_research_memory_pack(
    ticker: str,
    as_of_date: str,
    lookback_days: int,
    records: dict[str, Any],
    max_items_per_ticker: int = 5,
) -> dict[str, Any]:
    ticker = ticker.strip().upper()
    created_at = datetime.now(timezone.utc).isoformat()
    signals = sorted(records.get("signals", []), key=lambda r: (r.get("created_at", ""), r.get("signal_id", "")), reverse=True)
    reports = sorted(records.get("reports", []), key=lambda r: (r.get("created_at", ""), r.get("report_id", "")), reverse=True)
    selected_signals = signals[:max_items_per_ticker]
    selected_reports = reports[:max_items_per_ticker]

    action_warnings: list[str] = []
    latest_research: dict[str, Any] = {}
    if selected_reports or selected_signals:
        latest_report = selected_reports[0] if selected_reports else {}
        latest_signal = selected_signals[0] if selected_signals else {}
        visible_action, action_warnings = _resolve_visible_action(latest_report)
        latest_research = {
            "task_id": latest_signal.get("task_id") or latest_report.get("task_id", ""),
            "signal_id": latest_signal.get("signal_id", ""),
            "report_id": latest_report.get("report_id", ""),
            "created_at": latest_signal.get("created_at") or latest_report.get("created_at", ""),
            "rating": latest_signal.get("rating", ""),
            "confidence": latest_signal.get("confidence"),
            "priority_score": latest_signal.get("priority_score"),
            "visible_action": visible_action,
            "title": latest_report.get("title", ""),
            "bottom_line": latest_report.get("bottom_line", ""),
            "why_now": latest_report.get("why_now", ""),
            "risk_flags": latest_signal.get("risk_flags") or _json_load(latest_signal.get("risk_flags_json"), []),
            "decision_reason": latest_signal.get("decision_reason", ""),
        }

    missing_context: list[str] = []
    if not latest_research:
        missing_context.append("missing_research_context")
    outcome_summary = _summarize_outcomes(records.get("outcomes_by_signal", {}))
    if outcome_summary["total_outcome_rows"] == 0:
        missing_context.append("missing_outcome_context")
    candidate_history = _summarize_candidate_history(records.get("candidate_items", []))
    if candidate_history["appearance_count"] == 0:
        missing_context.append("missing_candidate_history")
    quality_context = _quality_context(records.get("quality_report"), missing_context)
    regime_context = _regime_context(records.get("regime_snapshot"), missing_context)
    watchlist_context = records.get("watchlist_entry") or {}
    validation_context = records.get("validation_result") or {}
    if not watchlist_context:
        missing_context.append("missing_watchlist_context")
    if not validation_context:
        missing_context.append("missing_validation_context")

    pack_parts = {
        "latest_research": latest_research,
        "outcome_summary": outcome_summary,
        "candidate_history": candidate_history,
        "quality_context": quality_context,
        "regime_context": regime_context,
        "watchlist_context": watchlist_context,
        "validation_context": validation_context,
    }
    recurring_themes = _derive_recurring_themes(pack_parts)
    risk_memory = _derive_risk_memory(pack_parts, action_warnings)
    source_refs = {
        "signal_ids": [row.get("signal_id", "") for row in selected_signals],
        "report_ids": [row.get("report_id", "") for row in selected_reports],
        "candidate_item_ids": [row.get("item_id", "") for row in records.get("candidate_items", [])[:max_items_per_ticker]],
        "p38_source_hash": quality_context.get("source_hash", ""),
        "p37_source_hash": regime_context.get("source_hash", ""),
    }
    source_hash = compute_research_memory_source_hash({
        "schema_version": P40_SCHEMA_VERSION,
        "ticker": ticker,
        "as_of_date": as_of_date,
        "lookback_days": lookback_days,
        "source_refs": source_refs,
        "latest_research": latest_research,
        "outcome_summary": outcome_summary,
        "candidate_history": candidate_history,
        "quality_context": quality_context,
        "regime_context": regime_context,
        "watchlist_updated_at": watchlist_context.get("updated_at", ""),
        "validation_updated_at": validation_context.get("updated_at", ""),
    })
    pack_id = hashlib.sha256(f"{ticker}|{as_of_date}|{lookback_days}|{source_hash}".encode("utf-8")).hexdigest()[:16]
    has_primary_memory = bool(selected_signals or selected_reports or outcome_summary["total_outcome_rows"] or candidate_history["appearance_count"])
    has_any_context = has_primary_memory or bool(quality_context or regime_context or watchlist_context or validation_context)
    status = P40_STATUS_MEMORY_AVAILABLE if has_primary_memory else (P40_STATUS_LIMITED_MEMORY if has_any_context else P40_STATUS_NO_PRIOR_MEMORY)
    return {
        "schema_version": P40_SCHEMA_VERSION,
        "pack_id": pack_id,
        "as_of_date": as_of_date,
        "created_at": created_at,
        "ticker": ticker,
        "lookback_days": lookback_days,
        "memory_status": status,
        "latest_research": latest_research,
        "prior_signals": selected_signals,
        "outcome_summary": outcome_summary,
        "candidate_history": candidate_history,
        "quality_context": quality_context,
        "regime_context": regime_context,
        "watchlist_context": watchlist_context,
        "validation_context": validation_context,
        "recurring_themes": recurring_themes,
        "risk_memory": risk_memory,
        "missing_context": sorted(set(missing_context)),
        "source_refs": source_refs,
        "source_hash": source_hash,
        "disclaimer": P40_ARTIFACT_DISCLAIMER,
    }
```

Records keys:

```text
signals
reports
outcomes_by_signal
candidate_items
quality_report
regime_snapshot
watchlist_entry
validation_result
```

Rules:

- Sort signals by `created_at DESC, signal_id ASC`.
- Sort reports by `created_at DESC, report_id ASC`.
- Pick latest report/signal for `latest_research`.
- Include up to `max_items_per_ticker` prior signals.
- Compute outcome summary from P36 rows.
- Compute candidate history from P39 rows.
- Build source refs from selected row IDs/hashes.
- Set status according to the spec.
- Add `source_hash`, then deterministic `pack_id = sha256(ticker|as_of_date|lookback_days|source_hash)[:16]`.

- [ ] **Step 5: Add focused summary tests**

Append tests:

```python
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
```

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_research_memory_pack.py -q
```

Expected: all P40-A tests pass.

- [ ] **Step 6: Commit P40-A**

```bash
git add agent/research_v1/research_memory_pack.py tests/agent/research_v1/test_research_memory_pack.py
git commit -m "feat: add research memory collector"
```

## Task 2: P40-B Persistence + Artifacts

**Files:**
- Modify: `agent/research_v1/data/database.py`
- Modify: `agent/research_v1/research_memory_pack.py`
- Modify: `tests/agent/research_v1/test_research_memory_pack.py`

- [ ] **Step 1: Write failing DB and artifact tests**

Append tests:

```python
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
```

- [ ] **Step 2: Add database helpers**

Add methods to `ResearchDatabase`:

```python
def initialize_memory_pack_schema(self) -> None:
    conn = self._get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS research_memory_packs (
            pack_id TEXT PRIMARY KEY,
            schema_version TEXT NOT NULL,
            as_of_date TEXT NOT NULL,
            created_at TEXT NOT NULL,
            ticker TEXT NOT NULL,
            lookback_days INTEGER NOT NULL,
            memory_status TEXT NOT NULL,
            source_hash TEXT NOT NULL,
            latest_research_json TEXT NOT NULL,
            outcome_summary_json TEXT NOT NULL,
            candidate_history_json TEXT NOT NULL,
            quality_context_json TEXT NOT NULL,
            regime_context_json TEXT NOT NULL,
            watchlist_context_json TEXT NOT NULL,
            validation_context_json TEXT NOT NULL,
            recurring_themes_json TEXT NOT NULL,
            risk_memory_json TEXT NOT NULL,
            missing_context_json TEXT NOT NULL,
            source_refs_json TEXT NOT NULL,
            summary TEXT NOT NULL,
            UNIQUE(ticker, as_of_date, lookback_days, source_hash)
        )
    """)
    conn.commit()
    conn.close()

def save_research_memory_pack(self, pack: dict) -> str:
    self.initialize_memory_pack_schema()
    conn = self._get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT OR IGNORE INTO research_memory_packs (
            pack_id, schema_version, as_of_date, created_at, ticker,
            lookback_days, memory_status, source_hash,
            latest_research_json, outcome_summary_json, candidate_history_json,
            quality_context_json, regime_context_json, watchlist_context_json,
            validation_context_json, recurring_themes_json, risk_memory_json,
            missing_context_json, source_refs_json, summary
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            pack["pack_id"],
            pack["schema_version"],
            pack["as_of_date"],
            pack["created_at"],
            pack["ticker"],
            pack["lookback_days"],
            pack["memory_status"],
            pack["source_hash"],
            json.dumps(pack.get("latest_research", {})),
            json.dumps(pack.get("outcome_summary", {})),
            json.dumps(pack.get("candidate_history", {})),
            json.dumps(pack.get("quality_context", {})),
            json.dumps(pack.get("regime_context", {})),
            json.dumps(pack.get("watchlist_context", {})),
            json.dumps(pack.get("validation_context", {})),
            json.dumps(pack.get("recurring_themes", [])),
            json.dumps(pack.get("risk_memory", [])),
            json.dumps(pack.get("missing_context", [])),
            json.dumps(pack.get("source_refs", {})),
            f"{pack['ticker']}: {pack['memory_status']}",
        ),
    )
    conn.commit()
    conn.close()
    return pack["pack_id"]

def list_research_memory_packs(self, ticker: str | None = None, as_of_date: str | None = None, limit: int = 20) -> list[dict]:
    self.initialize_memory_pack_schema()
    conn = self._get_connection()
    cursor = conn.cursor()
    conditions: list[str] = []
    params: list[Any] = []
    if ticker:
        conditions.append("ticker = ?")
        params.append(ticker)
    if as_of_date:
        conditions.append("as_of_date = ?")
        params.append(as_of_date)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params.append(limit)
    cursor.execute(
        f"SELECT * FROM research_memory_packs {where} ORDER BY created_at DESC, pack_id ASC LIMIT ?",
        params,
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
```

Schema must match the spec. Use:

```text
UNIQUE(ticker, as_of_date, lookback_days, source_hash)
```

Add read helpers:

```python
def list_canonical_signals_for_ticker(self, ticker: str, as_of_date: str, lookback_days: int, limit: int = 5) -> list[dict]
def list_canonical_reports_for_ticker(self, ticker: str, as_of_date: str, lookback_days: int, limit: int = 5) -> list[dict]
def list_candidate_pool_items_for_ticker(self, ticker: str, as_of_date: str, lookback_days: int, limit: int = 5) -> list[dict]
def get_watchlist_entry_for_ticker(self, ticker: str) -> dict | None
def get_validation_result_for_ticker(self, ticker: str) -> dict | None
```

For lookback filtering, use SQLite date comparison against `date(created_at)` or `date(as_of_date)` where available. Order deterministically with newest date, then stable ID.

- [ ] **Step 3: Add artifact writer**

In `research_memory_pack.py`, implement:

```python
def write_research_memory_artifacts(payload: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "p40_research_memory_pack.json"
    md_path = output_dir / "p40_research_memory_pack.md"
    json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    packs = payload.get("packs", [])
    lines = [
        f"# Research Memory Pack - {payload.get('as_of_date', '')}",
        "",
        f"- Status: {payload.get('status', '')}",
        f"- Tickers: {len(packs)}",
        "",
        "## Ticker Summary",
        "",
        "| Ticker | Status | Latest Action | Outcomes | Candidate Appearances |",
        "|--------|--------|---------------|----------|-----------------------|",
    ]
    for pack in packs:
        latest = pack.get("latest_research", {})
        outcome = pack.get("outcome_summary", {})
        candidate = pack.get("candidate_history", {})
        lines.append(
            f"| {pack['ticker']} | {pack['memory_status']} | "
            f"{latest.get('visible_action', 'historical context only')} | "
            f"{outcome.get('evaluated_rows', 0)} evaluated | "
            f"{candidate.get('appearance_count', 0)} |"
        )
    lines.extend(["", "---", "", f"> {payload.get('disclaimer', P40_ARTIFACT_DISCLAIMER)}", ""])
    markdown = "\n".join(lines)
    lowered = markdown.lower()
    for forbidden in P40_FORBIDDEN_TERMS:
        if forbidden in lowered:
            raise ValueError(f"forbidden research-memory term rendered: {forbidden}")
    md_path.write_text(markdown, encoding="utf-8")
    return {"json": json_path, "md": md_path}
```

- [ ] **Step 4: Run tests and commit P40-B**

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_research_memory_pack.py -q
git add agent/research_v1/research_memory_pack.py agent/research_v1/data/database.py tests/agent/research_v1/test_research_memory_pack.py
git commit -m "feat: persist research memory packs"
```

## Task 3: P40-C Run Orchestration + CLI

**Files:**
- Modify: `agent/research_v1/research_memory_pack.py`
- Modify: `agent/research_v1/batch_cli.py`
- Modify: `tests/agent/research_v1/test_research_memory_pack.py`
- Modify: `tests/agent/research_v1/test_batch_cli.py`

- [ ] **Step 1: Write failing run and boundary tests**

Append:

```python
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
```

- [ ] **Step 2: Implement `run_research_memory_pack()`**

In `research_memory_pack.py`, implement:

```python
def run_research_memory_pack(
    db: Any,
    tickers: list[str],
    as_of_date: str,
    lookback_days: int = 180,
    output_root: Path | None = None,
    max_items_per_ticker: int = 5,
) -> dict[str, Any]:
    normalized = normalize_memory_tickers(tickers)
    if not normalized:
        return {"status": P40_STATUS_BLOCKED_INVALID_INPUT, "ticker_count": 0, "warnings": ["empty ticker list"]}
    db.initialize_memory_pack_schema()
    packs: list[dict[str, Any]] = []
    warnings: list[str] = []
    for ticker in normalized:
        records: dict[str, Any] = {}
        try:
            records["signals"] = db.list_canonical_signals_for_ticker(ticker, as_of_date, lookback_days, max_items_per_ticker)
        except Exception:
            records["signals"] = []
            warnings.append(f"{ticker}:missing_signal_table")
        try:
            records["reports"] = db.list_canonical_reports_for_ticker(ticker, as_of_date, lookback_days, max_items_per_ticker)
        except Exception:
            records["reports"] = []
            warnings.append(f"{ticker}:missing_report_table")
        try:
            records["candidate_items"] = db.list_candidate_pool_items_for_ticker(ticker, as_of_date, lookback_days, max_items_per_ticker)
        except Exception:
            records["candidate_items"] = []
        try:
            q = db.list_fundamental_quality_reports_as_of(ticker, as_of_date, limit=1)
            records["quality_report"] = q[0] if q else None
        except Exception:
            records["quality_report"] = None
        try:
            r = db.list_market_regime_snapshots_as_of(as_of_date, limit=1)
            records["regime_snapshot"] = r[0] if r else None
        except Exception:
            records["regime_snapshot"] = None
        try:
            records["watchlist_entry"] = db.get_watchlist_entry_for_ticker(ticker)
        except Exception:
            records["watchlist_entry"] = None
        try:
            records["validation_result"] = db.get_validation_result_for_ticker(ticker)
        except Exception:
            records["validation_result"] = None
        pack = build_research_memory_pack(ticker, as_of_date, lookback_days, records, max_items_per_ticker)
        db.save_research_memory_pack(pack)
        packs.append(pack)
    summary = {
        "ticker_count": len(packs),
        "memory_available": sum(1 for p in packs if p["memory_status"] == P40_STATUS_MEMORY_AVAILABLE),
        "limited_memory": sum(1 for p in packs if p["memory_status"] == P40_STATUS_LIMITED_MEMORY),
        "no_prior_memory": sum(1 for p in packs if p["memory_status"] == P40_STATUS_NO_PRIOR_MEMORY),
    }
    payload = {
        "schema_version": P40_SCHEMA_VERSION,
        "as_of_date": as_of_date,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "completed",
        "packs": packs,
        "summary": summary,
        "warnings": warnings,
        "disclaimer": P40_ARTIFACT_DISCLAIMER,
    }
    output_dir = Path(output_root or "output/governance") / as_of_date
    paths = write_research_memory_artifacts(payload, output_dir)
    return {"status": "completed", "output_dir": str(output_dir), "warning_count": len(warnings), "paths": paths, **summary}
```

Rules:

- Initialize memory schema.
- For each ticker, gather records through DB helpers.
- Use try/except around optional helpers and add missing context instead of crashing.
- Build and persist each pack.
- Write combined artifacts.
- Return status counts and output paths.

- [ ] **Step 3: Write failing CLI tests**

Append to `tests/agent/research_v1/test_batch_cli.py`:

```python
def test_memory_pack_run_cli_success_writes_artifacts(tmp_path, monkeypatch, capsys):
    from agent.research_v1.batch_cli import main

    app_root = tmp_path / "app"

    def fake_run(**kwargs):
        output_dir = kwargs["output_root"] / "2026-04-30"
        output_dir.mkdir(parents=True, exist_ok=True)
        return {
            "status": "completed",
            "output_dir": str(output_dir),
            "ticker_count": 1,
            "memory_available": 0,
            "limited_memory": 0,
            "no_prior_memory": 1,
            "warning_count": 0,
        }

    monkeypatch.setattr("agent.research_v1.batch_cli.run_research_memory_pack", fake_run)

    code = main(["--app-root", str(app_root), "memory-pack-run", "--tickers", "aapl", "--as-of-date", "2026-04-30"])
    out = capsys.readouterr().out

    assert code == 0
    assert "Research memory status: completed" in out
    assert str(app_root / "output" / "governance" / "2026-04-30") in out


def test_memory_pack_run_cli_rejects_empty_tickers(tmp_path, capsys):
    from agent.research_v1.batch_cli import main

    code = main(["--app-root", str(tmp_path), "memory-pack-run", "--tickers", " , ", "--as-of-date", "2026-04-30"])

    assert code == 2
    assert "invalid memory-pack-run input" in capsys.readouterr().out
```

- [ ] **Step 4: Implement CLI**

In `batch_cli.py`:

- Import `run_research_memory_pack`.
- Add `_cmd_memory_pack_run(paths, tickers, input_path, as_of_date, lookback_days, output_root, max_items_per_ticker)`.
- Accept `--tickers`, `--input`, `--as-of-date`, `--lookback-days`, `--output-root`, `--max-items-per-ticker`.
- Validate input path and JSON if supplied.
- Merge tickers from JSON and CLI.
- Validate date, lookback, max items, and non-empty tickers.
- Resolve relative `output_root` under `paths.app_root`.
- Print exact summary lines from the spec.
- Return `2` for invalid input.

- [ ] **Step 5: Run tests and commit P40-C**

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_research_memory_pack.py tests/agent/research_v1/test_batch_cli.py -q -k "memory_pack or memory-pack"
git add agent/research_v1/research_memory_pack.py agent/research_v1/batch_cli.py tests/agent/research_v1/test_research_memory_pack.py tests/agent/research_v1/test_batch_cli.py
git commit -m "feat: add research memory cli"
```

## Task 4: P40-D Docs + Regression

**Files:**
- Modify: `README.md`
- Modify: `agent/research_v1/README.md`

- [ ] **Step 1: Update root README**

Document:

- `agent/research_v1/research_memory_pack.py`
- `memory-pack-run`
- `p40_research_memory_pack.{json,md}`
- P40 is research-memory evidence only.
- P40 does not call the research app or alter recommendations.

- [ ] **Step 2: Update research README Data Flow**

Add:

```text
P40 research_memory_pack.py reads prior Hermes artifacts and DB rows for a ticker and emits a deterministic memory pack. The flow is one-way: memory packs do not call HermesResearchApp.run(), final_judge, JudgeInputPacket, or broker/order APIs.
```

- [ ] **Step 3: Run verification**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_research_memory_pack.py -q
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_batch_cli.py -q -k "memory_pack or memory-pack"
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_recommendation_outcomes.py tests/agent/research_v1/test_market_regime_context.py tests/agent/research_v1/test_fundamental_quality.py tests/agent/research_v1/test_candidate_pool.py -q
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_governance_runtime.py tests/agent/research_v1/test_boss_governance_brief.py tests/agent/research_v1/test_signal_family_edge_review.py -q
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_doc_standards.py -q
```

Then run the full P20-P40 chain. If host-specific PDF/Futu checks fail, report them separately.

- [ ] **Step 4: Commit P40-D**

```bash
git add README.md agent/research_v1/README.md
git commit -m "docs: document p40 research memory"
```

## Final Report Format

```text
P40 Implementation Complete

Status Summary
Phase   Status   Commit
P40-A   PASS     <commit> feat: add research memory collector
P40-B   PASS     <commit> feat: persist research memory packs
P40-C   PASS     <commit> feat: add research memory cli
P40-D   PASS     <commit> docs: document p40 research memory

Verification
- P40 focused: <n> passed
- P40 CLI: <n> passed
- P36-P39 regression: <n> passed
- Governance-adjacent regression: <n> passed
- Doc standards: <n> passed
- Full P20-P40 chain: <n> passed, with known host-specific gaps listed separately

Files Changed
- agent/research_v1/research_memory_pack.py
- agent/research_v1/data/database.py
- agent/research_v1/batch_cli.py
- tests/agent/research_v1/test_research_memory_pack.py
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
- no P35/P36/P37/P38/P39 mutation
```

## Review Checklist

- [ ] Tickers normalize deterministically.
- [ ] Prior research action resolution prefers decision card before legacy trade plan.
- [ ] Outcome summary uses P36 persisted fields.
- [ ] Candidate history uses P39 rows read-only.
- [ ] P37/P38 context uses latest at or before `as_of_date`.
- [ ] Missing optional context is explicit.
- [ ] Source hash changes when selected source rows change.
- [ ] Persistence is idempotent and append-only.
- [ ] Markdown contains no forbidden trading instructions.
- [ ] CLI rejects invalid inputs.
- [ ] No research decision path changed.
