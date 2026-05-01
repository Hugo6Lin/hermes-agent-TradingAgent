# P44 Evidence Freshness & Drift Monitor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone read-only monitor that reports freshness, coverage, source-hash churn, and missing-context patterns across P36-P43 evidence.

**Architecture:** Add `evidence_freshness_drift_monitor.py` for deterministic monitoring and artifact writing. Extend `ResearchDatabase` with append-only P44 persistence and evidence snapshot helpers, then expose `evidence-monitor-run` in the CLI.

**Tech Stack:** Python 3.11, sqlite3, pathlib, json, hashlib, datetime, argparse, pytest.

---

## File Structure

- Create: `agent/research_v1/evidence_freshness_drift_monitor.py`
  - Phase monitor model, freshness/coverage/churn classification, missing-context aggregation, source hashing, artifact writer, runtime orchestration.
- Modify: `agent/research_v1/data/database.py`
  - Add P44 report table and read helpers for phase evidence rows.
- Modify: `agent/research_v1/batch_cli.py`
  - Add `evidence-monitor-run`.
- Create: `tests/agent/research_v1/test_evidence_freshness_drift_monitor.py`
  - Focused P44 tests.
- Modify: `tests/agent/research_v1/test_batch_cli.py`
  - P44 CLI tests.
- Modify: `README.md`
  - Add P44 overview and verification section.
- Modify: `agent/research_v1/README.md`
  - Add P44 Data Flow note.

Do not modify P36-P43 runtime modules except `batch_cli.py` imports/dispatch and database read/persistence helpers.

## Constants

Use these constants:

```python
P44_SCHEMA_VERSION = "p44_evidence_freshness_drift_monitor.1"

P44_STATUS_GREEN = "monitor_green"
P44_STATUS_YELLOW = "monitor_yellow"
P44_STATUS_RED = "monitor_red"
P44_STATUS_BLOCKED_INVALID_INPUT = "blocked_invalid_input"

PHASES = (
    ("P36", "recommendation_outcomes", "p36_recommendation_outcomes.json"),
    ("P37", "market_regime", "p37_market_regime_snapshot.json"),
    ("P38", "fundamental_quality", "p38_fundamental_quality.json"),
    ("P39", "candidate_pool", "p39_candidate_pool.json"),
    ("P40", "research_memory", "p40_research_memory_pack.json"),
    ("P41", "decision_journal", "p41_decision_journal.json"),
    ("P42", "boss_copilot_brief", "p42_boss_copilot_daily_brief.json"),
    ("P43", "copilot_console_index", "p43_copilot_console_index.json"),
)

P44_ARTIFACT_DISCLAIMER = (
    "P44 is evidence freshness and drift monitoring only. It does not refresh "
    "evidence, schedule jobs, send notifications, recommend trades, submit orders, "
    "or mutate research decisions."
)

P44_FORBIDDEN_TERMS = (
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

## Task 1: P44-A Monitor Model

**Files:**
- Create: `agent/research_v1/evidence_freshness_drift_monitor.py`
- Create: `tests/agent/research_v1/test_evidence_freshness_drift_monitor.py`

- [ ] **Step 1: Write initial monitor tests**

Add:

```python
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
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_evidence_freshness_drift_monitor.py -q
```

Expected: import fails because module does not exist.

- [ ] **Step 3: Implement module skeleton**

Create `agent/research_v1/evidence_freshness_drift_monitor.py`:

```python
"""P44 Evidence Freshness & Drift Monitor."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

P44_SCHEMA_VERSION = "p44_evidence_freshness_drift_monitor.1"
P44_STATUS_GREEN = "monitor_green"
P44_STATUS_YELLOW = "monitor_yellow"
P44_STATUS_RED = "monitor_red"
P44_STATUS_BLOCKED_INVALID_INPUT = "blocked_invalid_input"

PHASES = (
    ("P36", "recommendation_outcomes", "p36_recommendation_outcomes.json"),
    ("P37", "market_regime", "p37_market_regime_snapshot.json"),
    ("P38", "fundamental_quality", "p38_fundamental_quality.json"),
    ("P39", "candidate_pool", "p39_candidate_pool.json"),
    ("P40", "research_memory", "p40_research_memory_pack.json"),
    ("P41", "decision_journal", "p41_decision_journal.json"),
    ("P42", "boss_copilot_brief", "p42_boss_copilot_daily_brief.json"),
    ("P43", "copilot_console_index", "p43_copilot_console_index.json"),
)

P44_ARTIFACT_DISCLAIMER = (
    "P44 is evidence freshness and drift monitoring only. It does not refresh "
    "evidence, schedule jobs, send notifications, recommend trades, submit orders, "
    "or mutate research decisions."
)

P44_FORBIDDEN_TERMS = (
    "buy this now", "sell this now", "follow this trade", "guaranteed edge",
    "production approved", "model promoted", "trade now", "order ticket",
    "place order", "execute trade",
)


def _sha(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _days_old(as_of_date: str, evidence_date: str) -> int:
    return (_parse_date(as_of_date) - _parse_date(evidence_date)).days
```

- [ ] **Step 4: Implement artifact and phase helpers**

Append:

```python
def _artifact_status(governance_root: Path, as_of_date: str, lookback_days: int, artifact_name: str) -> tuple[int, str, list[str]]:
    root = Path(governance_root)
    warnings: list[str] = []
    found_count = 0
    latest_date = ""
    for i in range(lookback_days):
        day = (_parse_date(as_of_date) - timedelta(days=i)).isoformat()
        path = root / day / artifact_name
        if not path.exists():
            continue
        found_count += 1
        if not latest_date:
            latest_date = day
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            warnings.append(f"invalid_json:{artifact_name}")
    return found_count, latest_date, sorted(set(warnings))


def _freshness(as_of_date: str, latest_date: str, freshness_days: int, invalid: bool) -> str:
    if invalid:
        return "invalid"
    if not latest_date:
        return "missing"
    return "fresh" if _days_old(as_of_date, latest_date) <= freshness_days else "stale"


def _churn(rows: list[dict]) -> str:
    hashes = {str(r.get("source_hash", "")) for r in rows if r.get("source_hash")}
    if len(hashes) < 2:
        return "unknown"
    if len(hashes) == 1:
        return "stable"
    if len(hashes) == 2:
        return "changed"
    return "high_churn"


def _coverage(row_count: int, artifact_count: int, invalid: bool) -> str:
    if invalid:
        return "invalid"
    if row_count == 0 and artifact_count == 0:
        return "missing"
    if artifact_count > 0:
        return "complete"
    return "partial"


def _recommended_action(freshness_status: str, churn_status: str, coverage_status: str) -> str:
    if coverage_status == "invalid" or freshness_status == "invalid":
        return "inspect_invalid_artifact"
    if coverage_status == "missing" or freshness_status == "missing":
        return "collect_missing_evidence"
    if freshness_status == "stale":
        return "refresh_stale_evidence"
    if churn_status == "high_churn":
        return "review_source_hash_churn"
    return "none"
```

- [ ] **Step 5: Implement report builder**

Append:

```python
def _latest_row(rows: list[dict]) -> dict:
    if not rows:
        return {}
    return sorted(rows, key=lambda r: (r.get("as_of_date", ""), r.get("created_at", ""), r.get("source_hash", "")), reverse=True)[0]


def _missing_patterns(phase_rows: dict[str, list[dict]]) -> list[dict[str, Any]]:
    counts: dict[str, dict[str, Any]] = {}
    for phase_id, rows in phase_rows.items():
        for row in rows:
            payload = row.get("payload") or {}
            keys: list[str] = []
            if phase_id == "P40":
                keys.extend(payload.get("missing_context", []))
            if phase_id == "P42":
                keys.extend((payload.get("summary") or {}).get("missing_context_counts", {}).keys())
            if phase_id == "P43":
                for day in payload.get("days", []):
                    keys.extend(day.get("missing_artifacts", []))
            for key in keys:
                entry = counts.setdefault(str(key), {"key": str(key), "count": 0, "sources": set()})
                entry["count"] += 1
                entry["sources"].add(phase_id)
    result = []
    for item in counts.values():
        result.append({"key": item["key"], "count": item["count"], "sources": sorted(item["sources"])})
    return sorted(result, key=lambda x: (-x["count"], x["key"]))


def build_evidence_freshness_drift_report(
    *,
    as_of_date: str,
    lookback_days: int,
    freshness_days: int,
    phase_rows: dict[str, list[dict]],
    governance_root: Path,
) -> dict[str, Any]:
    phase_monitors = []
    for phase_id, phase_name, artifact_name in PHASES:
        rows = phase_rows.get(phase_id, [])
        latest = _latest_row(rows)
        artifact_count, artifact_latest_date, artifact_warnings = _artifact_status(governance_root, as_of_date, lookback_days, artifact_name)
        latest_date = latest.get("as_of_date") or artifact_latest_date
        invalid = bool(artifact_warnings)
        freshness_status = _freshness(as_of_date, latest_date, freshness_days, invalid)
        churn_status = _churn(rows)
        coverage_status = _coverage(len(rows), artifact_count, invalid)
        phase_monitors.append({
            "phase_id": phase_id,
            "phase_name": phase_name,
            "latest_evidence_date": latest_date,
            "latest_created_at": latest.get("created_at", ""),
            "latest_source_hash": latest.get("source_hash", ""),
            "row_count": len(rows),
            "artifact_count": artifact_count,
            "freshness_status": freshness_status,
            "churn_status": churn_status,
            "coverage_status": coverage_status,
            "warnings": artifact_warnings,
            "recommended_action": _recommended_action(freshness_status, churn_status, coverage_status),
        })
    missing_patterns = _missing_patterns(phase_rows)
    red_count = sum(1 for p in phase_monitors if p["freshness_status"] in {"missing", "invalid"} or p["coverage_status"] in {"missing", "invalid"})
    yellow_count = sum(1 for p in phase_monitors if p["freshness_status"] == "stale" or p["churn_status"] == "high_churn")
    status = P44_STATUS_RED if red_count else P44_STATUS_YELLOW if yellow_count else P44_STATUS_GREEN
    seed = {
        "schema_version": P44_SCHEMA_VERSION,
        "as_of_date": as_of_date,
        "lookback_days": lookback_days,
        "freshness_days": freshness_days,
        "phase_monitors": phase_monitors,
        "missing_context_patterns": missing_patterns,
    }
    source_hash = _sha(seed)
    report_id = hashlib.sha256(f"{as_of_date}|{lookback_days}|{freshness_days}|{source_hash}".encode("utf-8")).hexdigest()[:16]
    return {
        "schema_version": P44_SCHEMA_VERSION,
        "report_id": report_id,
        "as_of_date": as_of_date,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "lookback_days": lookback_days,
        "freshness_days": freshness_days,
        "phase_monitors": phase_monitors,
        "missing_context_patterns": missing_patterns,
        "summary": {
            "phase_count": len(phase_monitors),
            "red_count": red_count,
            "yellow_count": yellow_count,
            "missing_context_pattern_count": len(missing_patterns),
        },
        "source_hash": source_hash,
        "disclaimer": P44_ARTIFACT_DISCLAIMER,
    }
```

- [ ] **Step 6: Add artifact writer and tests**

Append tests:

```python
def test_stale_evidence_returns_yellow(tmp_path: Path):
    phase_rows = {"P42": [_phase_row("P42", as_of_date="2026-04-20")]}
    report = build_evidence_freshness_drift_report(
        as_of_date="2026-04-30",
        lookback_days=14,
        freshness_days=3,
        phase_rows=phase_rows,
        governance_root=tmp_path / "governance",
    )

    p42 = next(p for p in report["phase_monitors"] if p["phase_id"] == "P42")
    assert p42["freshness_status"] == "stale"


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
```

Append implementation:

```python
def _check_forbidden(text: str) -> None:
    lowered = text.lower()
    for forbidden in P44_FORBIDDEN_TERMS:
        if forbidden in lowered:
            raise ValueError(f"forbidden evidence monitor term rendered: {forbidden}")


def write_evidence_freshness_drift_artifacts(report: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "p44_evidence_freshness_drift_monitor.json"
    md_path = output_dir / "p44_evidence_freshness_drift_monitor.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    lines = [
        "# Evidence Freshness & Drift Monitor",
        "",
        f"As of: `{report['as_of_date']}`",
        f"Status: `{report['status']}`",
        "",
        "## Phase Freshness",
        "",
        "| Phase | Freshness | Coverage | Churn | Action |",
        "|-------|-----------|----------|-------|--------|",
    ]
    for phase in report.get("phase_monitors", []):
        lines.append(
            f"| {phase['phase_id']} | {phase['freshness_status']} | {phase['coverage_status']} | "
            f"{phase['churn_status']} | {phase['recommended_action']} |"
        )
    lines.extend(["", "## Missing Context Patterns", ""])
    patterns = report.get("missing_context_patterns", [])
    if patterns:
        for item in patterns:
            lines.append(f"- {item['key']}: {item['count']} ({', '.join(item['sources'])})")
    else:
        lines.append("- none")
    lines.extend(["", "---", "", f"> {report.get('disclaimer', P44_ARTIFACT_DISCLAIMER)}", ""])
    text = "\n".join(lines)
    _check_forbidden(text)
    md_path.write_text(text, encoding="utf-8")
    return {"json": json_path, "md": md_path}
```

- [ ] **Step 7: Run tests and commit P44-A**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_evidence_freshness_drift_monitor.py -q
```

Commit:

```bash
git add agent/research_v1/evidence_freshness_drift_monitor.py tests/agent/research_v1/test_evidence_freshness_drift_monitor.py
git commit -m "feat: add evidence freshness drift monitor"
```

## Task 2: P44-B Database Helpers + Persistence

**Files:**
- Modify: `agent/research_v1/data/database.py`
- Modify: `tests/agent/research_v1/test_evidence_freshness_drift_monitor.py`

- [ ] **Step 1: Add persistence tests**

Append:

```python
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
```

- [ ] **Step 2: Implement P44 table**

Add to `ResearchDatabase`:

```python
def initialize_evidence_freshness_drift_schema(self) -> None:
    conn = self._get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS evidence_freshness_drift_reports (
            report_id TEXT PRIMARY KEY,
            schema_version TEXT NOT NULL,
            as_of_date TEXT NOT NULL,
            created_at TEXT NOT NULL,
            status TEXT NOT NULL,
            lookback_days INTEGER NOT NULL,
            freshness_days INTEGER NOT NULL,
            phase_count INTEGER NOT NULL,
            red_count INTEGER NOT NULL,
            yellow_count INTEGER NOT NULL,
            source_hash TEXT NOT NULL,
            report_json TEXT NOT NULL,
            UNIQUE(as_of_date, lookback_days, freshness_days, source_hash)
        )
    """)
    conn.commit()
    conn.close()
```

- [ ] **Step 3: Implement save/list helpers**

Add:

```python
def save_evidence_freshness_drift_report(self, report: dict) -> str:
    self.initialize_evidence_freshness_drift_schema()
    summary = report.get("summary", {})
    conn = self._get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT OR IGNORE INTO evidence_freshness_drift_reports (
            report_id, schema_version, as_of_date, created_at, status,
            lookback_days, freshness_days, phase_count, red_count, yellow_count,
            source_hash, report_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            report["report_id"],
            report["schema_version"],
            report["as_of_date"],
            report.get("created_at", ""),
            report.get("status", ""),
            report.get("lookback_days", 0),
            report.get("freshness_days", 0),
            summary.get("phase_count", 0),
            summary.get("red_count", 0),
            summary.get("yellow_count", 0),
            report["source_hash"],
            json.dumps(report),
        ),
    )
    conn.commit()
    conn.close()
    return report["report_id"]


def list_evidence_freshness_drift_reports(self, as_of_date: str | None = None, limit: int = 20) -> list[dict]:
    self.initialize_evidence_freshness_drift_schema()
    conn = self._get_connection()
    cursor = conn.cursor()
    if as_of_date:
        cursor.execute(
            """SELECT * FROM evidence_freshness_drift_reports
               WHERE as_of_date = ?
               ORDER BY created_at DESC, report_id ASC
               LIMIT ?""",
            (as_of_date, limit),
        )
    else:
        cursor.execute(
            """SELECT * FROM evidence_freshness_drift_reports
               ORDER BY as_of_date DESC, created_at DESC, report_id ASC
               LIMIT ?""",
            (limit,),
        )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
```

- [ ] **Step 4: Implement evidence snapshot helper**

Add a pragmatic helper:

```python
def collect_evidence_phase_rows(self, as_of_date: str, lookback_days: int) -> dict[str, list[dict]]:
    """Collect recent evidence rows for P44. Missing tables return empty phase lists."""
    result = {phase: [] for phase in ("P36", "P37", "P38", "P39", "P40", "P41", "P42", "P43")}
    conn = self._get_connection()
    cursor = conn.cursor()
    queries = {
        "P36": ("canonical_recommendation_outcomes", "evaluated_for_date", "evaluated_at", "data_source_hash", "status"),
        "P37": ("market_regime_snapshots", "as_of_date", "created_at", "data_source_hash", "regime_label"),
        "P38": ("fundamental_quality_reports", "as_of_date", "created_at", "source_hash", "quality_label"),
        "P39": ("candidate_pool_runs", "as_of_date", "created_at", "source_hash", "status"),
        "P40": ("research_memory_packs", "as_of_date", "created_at", "source_hash", "memory_status"),
        "P41": ("decision_journal_entries", "as_of_date", "created_at", "source_hash", "severity"),
        "P42": ("boss_copilot_daily_briefs", "as_of_date", "created_at", "source_hash", "status"),
        "P43": ("copilot_console_indexes", "as_of_date", "created_at", "source_hash", "status"),
    }
    for phase, (table, date_col, created_col, hash_col, status_col) in queries.items():
        try:
            cursor.execute(
                f"""SELECT *, {date_col} AS _evidence_date, {created_col} AS _created_at,
                          {hash_col} AS _source_hash, {status_col} AS _status
                    FROM {table}
                    WHERE date({date_col}) <= date(?)
                      AND date({date_col}) >= date(?, ?)
                    ORDER BY date({date_col}) DESC, {created_col} DESC
                    LIMIT 100""",
                (as_of_date, as_of_date, f"-{lookback_days} days"),
            )
            rows = []
            for row in cursor.fetchall():
                d = dict(row)
                payload = {}
                for json_col in ("entry_json", "brief_json", "index_json", "report_json", "missing_context_json", "summary_json"):
                    if json_col in d and d.get(json_col):
                        try:
                            payload.update(json.loads(d[json_col]) if isinstance(json.loads(d[json_col]), dict) else {json_col: json.loads(d[json_col])})
                        except (json.JSONDecodeError, TypeError):
                            pass
                rows.append({
                    "phase_id": phase,
                    "as_of_date": d.get("_evidence_date", ""),
                    "created_at": d.get("_created_at", ""),
                    "source_hash": d.get("_source_hash", ""),
                    "status": d.get("_status", ""),
                    "payload": payload,
                })
            result[phase] = rows
        except Exception:
            result[phase] = []
    conn.close()
    return result
```

This helper is read-only and tolerates absent optional tables.

- [ ] **Step 5: Run tests and commit P44-B**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_evidence_freshness_drift_monitor.py -q
```

Commit:

```bash
git add agent/research_v1/data/database.py tests/agent/research_v1/test_evidence_freshness_drift_monitor.py
git commit -m "feat: persist evidence freshness drift reports"
```

## Task 3: P44-C Runtime + CLI

**Files:**
- Modify: `agent/research_v1/evidence_freshness_drift_monitor.py`
- Modify: `agent/research_v1/batch_cli.py`
- Modify: `tests/agent/research_v1/test_evidence_freshness_drift_monitor.py`
- Modify: `tests/agent/research_v1/test_batch_cli.py`

- [ ] **Step 1: Add runtime tests**

Append:

```python
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
```

- [ ] **Step 2: Implement runtime**

Append:

```python
def run_evidence_freshness_drift_monitor(
    db: Any,
    governance_root: Path,
    output_root: Path,
    as_of_date: str,
    lookback_days: int = 14,
    freshness_days: int = 3,
) -> dict[str, Any]:
    try:
        _parse_date(as_of_date)
    except ValueError:
        return {"status": P44_STATUS_BLOCKED_INVALID_INPUT, "warnings": ["invalid_date_format"]}
    if lookback_days <= 0:
        return {"status": P44_STATUS_BLOCKED_INVALID_INPUT, "warnings": ["lookback_days_must_be_positive"]}
    if freshness_days <= 0:
        return {"status": P44_STATUS_BLOCKED_INVALID_INPUT, "warnings": ["freshness_days_must_be_positive"]}
    root = Path(governance_root)
    if root.exists() and not root.is_dir():
        return {"status": P44_STATUS_BLOCKED_INVALID_INPUT, "warnings": ["governance_root_not_a_directory"]}

    phase_rows = db.collect_evidence_phase_rows(as_of_date, lookback_days)
    report = build_evidence_freshness_drift_report(
        as_of_date=as_of_date,
        lookback_days=lookback_days,
        freshness_days=freshness_days,
        phase_rows=phase_rows,
        governance_root=root,
    )
    db.save_evidence_freshness_drift_report(report)
    output_dir = Path(output_root) / as_of_date
    paths = write_evidence_freshness_drift_artifacts(report, output_dir)
    summary = report.get("summary", {})
    return {
        "status": report["status"],
        "output_dir": str(output_dir),
        "phase_count": summary.get("phase_count", 0),
        "red_count": summary.get("red_count", 0),
        "yellow_count": summary.get("yellow_count", 0),
        "missing_context_pattern_count": summary.get("missing_context_pattern_count", 0),
        "paths": paths,
    }
```

- [ ] **Step 3: Add hard-boundary test**

Append:

```python
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
```

- [ ] **Step 4: Add CLI tests**

Append to `test_batch_cli.py`:

```python
def test_evidence_monitor_run_cli_success_writes_artifacts(tmp_path, monkeypatch, capsys):
    from agent.research_v1.batch_cli import main

    app_root = tmp_path / "app"

    def fake_run(**kwargs):
        output_dir = kwargs["output_root"] / "2026-04-30"
        output_dir.mkdir(parents=True, exist_ok=True)
        return {
            "status": "monitor_yellow",
            "output_dir": str(output_dir),
            "phase_count": 8,
            "red_count": 0,
            "yellow_count": 1,
            "missing_context_pattern_count": 2,
        }

    monkeypatch.setattr("agent.research_v1.batch_cli.run_evidence_freshness_drift_monitor", fake_run)
    code = main(["--app-root", str(app_root), "evidence-monitor-run", "--as-of-date", "2026-04-30"])
    out = capsys.readouterr().out

    assert code == 0
    assert "Evidence monitor status: monitor_yellow" in out


def test_evidence_monitor_run_cli_rejects_invalid_date(tmp_path, capsys):
    from agent.research_v1.batch_cli import main

    code = main(["--app-root", str(tmp_path), "evidence-monitor-run", "--as-of-date", "not-a-date"])

    assert code == 2
    assert "invalid evidence-monitor-run input" in capsys.readouterr().out
```

- [ ] **Step 5: Wire CLI**

In `batch_cli.py` imports:

```python
from agent.research_v1.evidence_freshness_drift_monitor import run_evidence_freshness_drift_monitor
```

Add command:

```python
def _cmd_evidence_monitor_run(
    paths: HermesPaths,
    as_of_date: str,
    lookback_days: int,
    freshness_days: int,
    governance_root: str,
    output_root: str,
) -> int:
    from datetime import date as _date
    try:
        _date.fromisoformat(as_of_date)
    except (ValueError, TypeError):
        print(f"invalid evidence-monitor-run input: invalid date format '{as_of_date}'")
        return 2
    if lookback_days <= 0:
        print("invalid evidence-monitor-run input: lookback-days must be positive")
        return 2
    if freshness_days <= 0:
        print("invalid evidence-monitor-run input: freshness-days must be positive")
        return 2

    governance_path = Path(governance_root).expanduser()
    if not governance_path.is_absolute():
        governance_path = paths.app_root / governance_path
    output_path = Path(output_root).expanduser()
    if not output_path.is_absolute():
        output_path = paths.app_root / output_path

    database = _ensure_database(paths)
    result = run_evidence_freshness_drift_monitor(
        db=database,
        governance_root=governance_path.resolve(),
        output_root=output_path.resolve(),
        as_of_date=as_of_date,
        lookback_days=lookback_days,
        freshness_days=freshness_days,
    )
    if result.get("status") == "blocked_invalid_input":
        print(f"invalid evidence-monitor-run input: {result.get('warnings', ['unknown'])[0]}")
        return 2
    print(f"Evidence monitor status: {result['status']}")
    print(f"Output dir: {result['output_dir']}")
    print(f"Phase count: {result['phase_count']}")
    print(f"Red count: {result['red_count']}")
    print(f"Yellow count: {result['yellow_count']}")
    print(f"Missing context pattern count: {result['missing_context_pattern_count']}")
    return 0
```

Add parser:

```python
monitor_parser = subparsers.add_parser("evidence-monitor-run", help="Run evidence freshness and drift monitor.")
monitor_parser.add_argument("--as-of-date", required=True, help="As-of date YYYY-MM-DD.")
monitor_parser.add_argument("--lookback-days", default=14, type=int, help="Number of calendar days to inspect.")
monitor_parser.add_argument("--freshness-days", default=3, type=int, help="Freshness threshold in calendar days.")
monitor_parser.add_argument("--governance-root", default="output/governance", help="Governance artifact root.")
monitor_parser.add_argument("--output-root", default="output/governance", help="Output root for evidence monitor artifacts.")
```

Add dispatch:

```python
if args.command == "evidence-monitor-run":
    return _cmd_evidence_monitor_run(
        paths,
        as_of_date=args.as_of_date,
        lookback_days=args.lookback_days,
        freshness_days=args.freshness_days,
        governance_root=args.governance_root,
        output_root=args.output_root,
    )
```

- [ ] **Step 6: Run tests and commit P44-C**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_evidence_freshness_drift_monitor.py tests/agent/research_v1/test_batch_cli.py -q -k "evidence_monitor or evidence-monitor"
```

Commit:

```bash
git add agent/research_v1/evidence_freshness_drift_monitor.py agent/research_v1/batch_cli.py tests/agent/research_v1/test_evidence_freshness_drift_monitor.py tests/agent/research_v1/test_batch_cli.py
git commit -m "feat: add evidence monitor cli"
```

## Task 4: P44-D Docs + Regression

**Files:**
- Modify: `README.md`
- Modify: `agent/research_v1/README.md`

- [ ] **Step 1: Update root README**

Add:

```markdown
### P44 Evidence Freshness & Drift Monitor

P44 monitors existing P36-P43 evidence for freshness, coverage, source-hash churn, invalid artifacts, and repeated missing-context patterns. It writes `p44_evidence_freshness_drift_monitor.json` and `.md` under `output/governance/YYYY-MM-DD/`.

P44 is evidence monitoring only. It does not refresh evidence, schedule jobs, send notifications, run prior phases, recommend trades, or mutate research decisions.
```

- [ ] **Step 2: Update research README Data Flow**

Add:

```markdown
#### P44 Evidence Freshness & Drift Monitor

`evidence_freshness_drift_monitor.py` reads persisted P36-P43 evidence and governance artifacts, then emits a deterministic evidence-health report. The flow is one-way: P44 does not invoke P36-P43 runtimes, `HermesResearchApp.run()`, `final_judge`, or broker/order APIs.
```

- [ ] **Step 3: Run verification**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_evidence_freshness_drift_monitor.py -q
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_batch_cli.py -q -k "evidence_monitor or evidence-monitor"
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_recommendation_outcomes.py tests/agent/research_v1/test_market_regime_context.py tests/agent/research_v1/test_fundamental_quality.py tests/agent/research_v1/test_candidate_pool.py tests/agent/research_v1/test_research_memory_pack.py tests/agent/research_v1/test_decision_journal_guardrails.py tests/agent/research_v1/test_boss_copilot_daily_brief.py tests/agent/research_v1/test_copilot_console_index.py -q
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_governance_runtime.py tests/agent/research_v1/test_boss_governance_brief.py tests/agent/research_v1/test_signal_family_edge_review.py -q
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_doc_standards.py -q
```

Run the full P20-P44 chain. Report host-specific PDF/Futu gaps separately if unrelated.

- [ ] **Step 4: Commit P44-D**

```bash
git add README.md agent/research_v1/README.md
git commit -m "docs: document p44 evidence monitor"
```

## Final Report Template

```text
P44 Implementation Complete

Status Summary
Phase   Status   Commit
P44-A   PASS     <commit> feat: add evidence freshness drift monitor
P44-B   PASS     <commit> feat: persist evidence freshness drift reports
P44-C   PASS     <commit> feat: add evidence monitor cli
P44-D   PASS     <commit> docs: document p44 evidence monitor

Verification
- P44 focused: <n> passed
- P44 CLI: <n> passed
- P36-P43 regression: <n> passed
- Governance-adjacent regression: <n> passed
- Doc standards: <n> passed
- Full P20-P44 chain: <n> passed, with known host-specific gaps listed separately

Files Changed
- agent/research_v1/evidence_freshness_drift_monitor.py
- agent/research_v1/data/database.py
- agent/research_v1/batch_cli.py
- tests/agent/research_v1/test_evidence_freshness_drift_monitor.py
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
- no dynamic viewer/server
- no final_judge changes
- no HermesResearchApp.run invocation
- no CanonicalSignal or CanonicalReport creation
- no JudgeInputPacket mutation
- no P36-P43 mutation
- no P36-P43 runtime invocation
```

## Review Checklist

- [ ] P44 reads P36-P43 evidence without mutating it.
- [ ] P44 never invokes prior phase runtimes.
- [ ] Invalid artifacts are visible.
- [ ] Missing phases become red.
- [ ] Stale/high-churn phases become yellow.
- [ ] Source hash changes when selected upstream source hash changes.
- [ ] CLI validates date, lookback, and freshness.
- [ ] Markdown rejects forbidden trading language.
- [ ] Docs mention P44 in root and research README.
