# P43 Read-Only Co-Pilot Console Index Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a static read-only console index that scans existing P36-P42 governance artifacts and writes navigable JSON, Markdown, and HTML index files.

**Architecture:** Add `copilot_console_index.py` for artifact scanning, coverage classification, source hashing, static rendering, and run orchestration. Extend `ResearchDatabase` with append-only P43 persistence, then expose a local `copilot-console-index-run` CLI command.

**Tech Stack:** Python 3.11, sqlite3, pathlib, json, hashlib, datetime, html escaping, argparse, pytest.

---

## File Structure

- Create: `agent/research_v1/copilot_console_index.py`
  - Artifact scanner, console model builder, source hash, JSON/Markdown/HTML writers, runtime orchestration.
- Modify: `agent/research_v1/data/database.py`
  - Add `copilot_console_indexes` table and save/list helpers.
- Modify: `agent/research_v1/batch_cli.py`
  - Add `copilot-console-index-run`.
- Create: `tests/agent/research_v1/test_copilot_console_index.py`
  - Focused P43 tests.
- Modify: `tests/agent/research_v1/test_batch_cli.py`
  - P43 CLI tests.
- Modify: `README.md`
  - Add P43 overview and verification section.
- Modify: `agent/research_v1/README.md`
  - Add P43 Data Flow note.

Do not modify `app.py`, `final_judge.py`, `orchestrator.py`, `contracts.py`, or any P36-P42 runtime module except `batch_cli.py` imports/dispatch.

## Constants

Use these constants in `copilot_console_index.py`:

```python
P43_SCHEMA_VERSION = "p43_copilot_console_index.1"

P43_STATUS_READY = "console_ready"
P43_STATUS_LIMITED_CONTEXT = "console_limited_context"
P43_STATUS_NO_ARTIFACTS = "console_no_artifacts"
P43_STATUS_BLOCKED_INVALID_INPUT = "blocked_invalid_input"

P43_REQUIRED_LATEST_FILES = (
    "p42_boss_copilot_daily_brief.json",
    "p42_boss_copilot_daily_brief.md",
)

P43_KNOWN_JSON = (
    "p36_recommendation_outcomes.json",
    "p37_market_regime_snapshot.json",
    "p38_fundamental_quality.json",
    "p39_candidate_pool.json",
    "p40_research_memory_pack.json",
    "p41_decision_journal.json",
    "p42_boss_copilot_daily_brief.json",
)

P43_KNOWN_MARKDOWN = (
    "p36_recommendation_outcomes.md",
    "p37_market_regime_snapshot.md",
    "p38_fundamental_quality.md",
    "p39_candidate_pool.md",
    "p40_research_memory_pack.md",
    "p41_decision_journal.md",
    "p42_boss_copilot_daily_brief.md",
)

P43_ARTIFACT_DISCLAIMER = (
    "P43 is a static read-only evidence index. It does not recommend trades, "
    "place orders, schedule jobs, send notifications, or mutate research decisions."
)

P43_FORBIDDEN_TERMS = (
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

## Task 1: P43-A Scanner + Console Model

**Files:**
- Create: `agent/research_v1/copilot_console_index.py`
- Create: `tests/agent/research_v1/test_copilot_console_index.py`

- [ ] **Step 1: Write scanner tests**

Add:

```python
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
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_copilot_console_index.py -q
```

Expected: import fails because module does not exist.

- [ ] **Step 3: Implement module skeleton and scanner**

Create `agent/research_v1/copilot_console_index.py`:

```python
"""P43 Read-Only Co-Pilot Console Index."""

from __future__ import annotations

import hashlib
import html
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

P43_SCHEMA_VERSION = "p43_copilot_console_index.1"
P43_STATUS_READY = "console_ready"
P43_STATUS_LIMITED_CONTEXT = "console_limited_context"
P43_STATUS_NO_ARTIFACTS = "console_no_artifacts"
P43_STATUS_BLOCKED_INVALID_INPUT = "blocked_invalid_input"

P43_REQUIRED_LATEST_FILES = ("p42_boss_copilot_daily_brief.json", "p42_boss_copilot_daily_brief.md")
P43_KNOWN_JSON = (
    "p36_recommendation_outcomes.json",
    "p37_market_regime_snapshot.json",
    "p38_fundamental_quality.json",
    "p39_candidate_pool.json",
    "p40_research_memory_pack.json",
    "p41_decision_journal.json",
    "p42_boss_copilot_daily_brief.json",
)
P43_KNOWN_MARKDOWN = tuple(name.replace(".json", ".md") for name in P43_KNOWN_JSON)
P43_ALL_KNOWN = P43_KNOWN_JSON + P43_KNOWN_MARKDOWN

P43_ARTIFACT_DISCLAIMER = (
    "P43 is a static read-only evidence index. It does not recommend trades, "
    "place orders, schedule jobs, send notifications, or mutate research decisions."
)
P43_FORBIDDEN_TERMS = (
    "buy this now", "sell this now", "follow this trade", "guaranteed edge",
    "production approved", "model promoted", "trade now", "order ticket",
    "place order", "execute trade",
)


def _sha(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


def _extract_status(path: Path) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return {}, [f"invalid_json:{path.name}"]
    extracted = {}
    for key in ("schema_version", "status", "overall_status", "as_of_date", "run_date", "summary", "source_hash"):
        if key in data:
            extracted[key] = data[key]
    return extracted, warnings


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name


def scan_governance_day(day_dir: Path, governance_root: Path | None = None) -> dict[str, Any]:
    root = governance_root or day_dir.parent
    present = []
    json_links = {}
    markdown_links = {}
    status_extracts = {}
    warnings = []
    for name in P43_ALL_KNOWN:
        path = day_dir / name
        if path.exists():
            present.append(name)
            if name.endswith(".json"):
                json_links[name] = _relative(path, root)
                extracted, file_warnings = _extract_status(path)
                status_extracts[name] = extracted
                warnings.extend(file_warnings)
            else:
                markdown_links[name] = _relative(path, root)
    missing = [name for name in P43_ALL_KNOWN if name not in present]
    if warnings:
        coverage = "invalid"
    elif present and missing:
        coverage = "partial"
    elif present:
        coverage = "complete"
    else:
        coverage = "empty"
    primary = ""
    if "p42_boss_copilot_daily_brief.md" in markdown_links:
        primary = markdown_links["p42_boss_copilot_daily_brief.md"]
    return {
        "date": day_dir.name,
        "day_dir": _relative(day_dir, root),
        "coverage_status": coverage,
        "present_artifacts": sorted(present),
        "missing_artifacts": missing,
        "json_links": json_links,
        "markdown_links": markdown_links,
        "primary_brief_ref": primary,
        "status_extracts": status_extracts,
        "warnings": sorted(set(warnings)),
    }
```

- [ ] **Step 4: Implement index builder and source hash**

Append:

```python
def _date_window(as_of_date: str, lookback_days: int) -> set[str]:
    end = date.fromisoformat(as_of_date)
    return {(end - timedelta(days=i)).isoformat() for i in range(lookback_days)}


def _artifact_fingerprint(day_dir: Path, names: list[str]) -> list[dict[str, Any]]:
    rows = []
    for name in sorted(names):
        path = day_dir / name
        if not path.exists():
            continue
        stat = path.stat()
        rows.append({"name": name, "size": stat.st_size, "mtime_ns": stat.st_mtime_ns})
    return rows


def build_copilot_console_index(governance_root: Path, as_of_date: str, lookback_days: int = 14) -> dict[str, Any]:
    governance_root = Path(governance_root)
    if lookback_days <= 0:
        return {"schema_version": P43_SCHEMA_VERSION, "status": P43_STATUS_BLOCKED_INVALID_INPUT, "warnings": ["lookback_days_must_be_positive"]}
    try:
        window = _date_window(as_of_date, lookback_days)
    except ValueError:
        return {"schema_version": P43_SCHEMA_VERSION, "status": P43_STATUS_BLOCKED_INVALID_INPUT, "warnings": ["invalid_date_format"]}

    day_dirs = []
    if governance_root.exists() and governance_root.is_dir():
        for child in governance_root.iterdir():
            if child.is_dir() and child.name in window:
                day_dirs.append(child)
    day_dirs.sort(key=lambda p: p.name, reverse=True)

    days = [scan_governance_day(day, governance_root) for day in day_dirs]
    days = [day for day in days if day["present_artifacts"] or day["warnings"]]
    if not days:
        status = P43_STATUS_NO_ARTIFACTS
    else:
        latest = days[0]
        missing_latest_required = [name for name in P43_REQUIRED_LATEST_FILES if name not in latest["present_artifacts"]]
        status = P43_STATUS_LIMITED_CONTEXT if missing_latest_required else P43_STATUS_READY

    missing_count = sum(len(day["missing_artifacts"]) for day in days)
    invalid_count = sum(len(day["warnings"]) for day in days)
    fingerprints = [
        {"date": day.name, "files": _artifact_fingerprint(day, P43_ALL_KNOWN)}
        for day in day_dirs
    ]
    source_hash = _sha({
        "schema_version": P43_SCHEMA_VERSION,
        "as_of_date": as_of_date,
        "lookback_days": lookback_days,
        "days": days,
        "fingerprints": fingerprints,
    })
    index_id = hashlib.sha256(f"{as_of_date}|{lookback_days}|{source_hash}".encode("utf-8")).hexdigest()[:16]
    return {
        "schema_version": P43_SCHEMA_VERSION,
        "index_id": index_id,
        "as_of_date": as_of_date,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "lookback_days": lookback_days,
        "summary": {
            "day_count": len(days),
            "latest_day": days[0]["date"] if days else "",
            "missing_artifact_count": missing_count,
            "invalid_artifact_count": invalid_count,
        },
        "days": days,
        "source_hash": source_hash,
        "disclaimer": P43_ARTIFACT_DISCLAIMER,
    }
```

- [ ] **Step 5: Add writer tests and implementation**

Append tests:

```python
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
```

Append implementation:

```python
def _check_forbidden(text: str) -> None:
    lowered = text.lower()
    for forbidden in P43_FORBIDDEN_TERMS:
        if forbidden in lowered:
            raise ValueError(f"forbidden copilot console term rendered: {forbidden}")


def _markdown(index: dict[str, Any]) -> str:
    lines = [
        "# Co-Pilot Console Index",
        "",
        f"As of: `{index.get('as_of_date', '')}`",
        f"Status: `{index.get('status', '')}`",
        f"Day count: `{index.get('summary', {}).get('day_count', 0)}`",
        "",
        "## Daily Coverage",
        "",
        "| Date | Coverage | Primary Brief | Missing | Invalid |",
        "|------|----------|---------------|---------|---------|",
    ]
    for day in index.get("days", []):
        primary = day.get("primary_brief_ref") or ""
        primary_link = f"[open]({primary})" if primary else ""
        lines.append(
            f"| {day['date']} | {day['coverage_status']} | {primary_link} | "
            f"{len(day['missing_artifacts'])} | {len(day['warnings'])} |"
        )
    lines.extend(["", "## Missing Artifacts", ""])
    any_missing = False
    for day in index.get("days", []):
        if day["missing_artifacts"]:
            any_missing = True
            lines.append(f"- {day['date']}: {', '.join(day['missing_artifacts'])}")
    if not any_missing:
        lines.append("- none")
    lines.extend(["", "---", "", f"> {index.get('disclaimer', P43_ARTIFACT_DISCLAIMER)}", ""])
    text = "\n".join(lines)
    _check_forbidden(text)
    return text


def _html(index: dict[str, Any]) -> str:
    rows = []
    for day in index.get("days", []):
        primary = html.escape(day.get("primary_brief_ref") or "")
        link = f'<a href="{primary}">open</a>' if primary else ""
        rows.append(
            "<tr>"
            f"<td>{html.escape(day['date'])}</td>"
            f"<td>{html.escape(day['coverage_status'])}</td>"
            f"<td>{link}</td>"
            f"<td>{len(day['missing_artifacts'])}</td>"
            f"<td>{len(day['warnings'])}</td>"
            "</tr>"
        )
    doc = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Hermes Co-Pilot Console Index</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 32px; color: #1f2937; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #d1d5db; padding: 8px; text-align: left; }}
    th {{ background: #f3f4f6; }}
  </style>
</head>
<body>
  <h1>Hermes Co-Pilot Console Index</h1>
  <p>Status: <strong>{html.escape(index.get('status', ''))}</strong></p>
  <p>As of: {html.escape(index.get('as_of_date', ''))}</p>
  <table>
    <thead><tr><th>Date</th><th>Coverage</th><th>Primary Brief</th><th>Missing</th><th>Invalid</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
  <p>{html.escape(index.get('disclaimer', P43_ARTIFACT_DISCLAIMER))}</p>
</body>
</html>"""
    _check_forbidden(doc)
    return doc


def write_copilot_console_index_artifacts(index: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "p43_copilot_console_index.json"
    md_path = output_dir / "p43_copilot_console_index.md"
    html_path = output_dir / "p43_copilot_console_index.html"
    json_path.write_text(json.dumps(index, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_markdown(index), encoding="utf-8")
    html_path.write_text(_html(index), encoding="utf-8")
    return {"json": json_path, "md": md_path, "html": html_path}
```

- [ ] **Step 6: Run tests and commit P43-A**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_copilot_console_index.py -q
```

Commit:

```bash
git add agent/research_v1/copilot_console_index.py tests/agent/research_v1/test_copilot_console_index.py
git commit -m "feat: add copilot console index scanner"
```

## Task 2: P43-B Persistence

**Files:**
- Modify: `agent/research_v1/data/database.py`
- Modify: `tests/agent/research_v1/test_copilot_console_index.py`

- [ ] **Step 1: Add persistence tests**

Append:

```python
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
```

- [ ] **Step 2: Implement P43 table**

Add to `ResearchDatabase`:

```python
def initialize_copilot_console_index_schema(self) -> None:
    conn = self._get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS copilot_console_indexes (
            index_id TEXT PRIMARY KEY,
            schema_version TEXT NOT NULL,
            as_of_date TEXT NOT NULL,
            created_at TEXT NOT NULL,
            status TEXT NOT NULL,
            lookback_days INTEGER NOT NULL,
            day_count INTEGER NOT NULL,
            latest_day TEXT,
            source_hash TEXT NOT NULL,
            index_json TEXT NOT NULL,
            UNIQUE(as_of_date, lookback_days, source_hash)
        )
    """)
    conn.commit()
    conn.close()
```

- [ ] **Step 3: Implement save/list helpers**

Add:

```python
def save_copilot_console_index(self, index: dict) -> str:
    self.initialize_copilot_console_index_schema()
    summary = index.get("summary", {})
    conn = self._get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT OR IGNORE INTO copilot_console_indexes (
            index_id, schema_version, as_of_date, created_at, status,
            lookback_days, day_count, latest_day, source_hash, index_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            index["index_id"],
            index["schema_version"],
            index["as_of_date"],
            index.get("created_at", ""),
            index.get("status", ""),
            index.get("lookback_days", 0),
            summary.get("day_count", 0),
            summary.get("latest_day", ""),
            index["source_hash"],
            json.dumps(index),
        ),
    )
    conn.commit()
    conn.close()
    return index["index_id"]


def list_copilot_console_indexes(self, as_of_date: str | None = None, limit: int = 20) -> list[dict]:
    self.initialize_copilot_console_index_schema()
    conn = self._get_connection()
    cursor = conn.cursor()
    if as_of_date:
        cursor.execute(
            """SELECT * FROM copilot_console_indexes
               WHERE as_of_date = ?
               ORDER BY created_at DESC, index_id ASC
               LIMIT ?""",
            (as_of_date, limit),
        )
    else:
        cursor.execute(
            """SELECT * FROM copilot_console_indexes
               ORDER BY as_of_date DESC, created_at DESC, index_id ASC
               LIMIT ?""",
            (limit,),
        )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
```

- [ ] **Step 4: Run tests and commit P43-B**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_copilot_console_index.py -q
```

Commit:

```bash
git add agent/research_v1/data/database.py tests/agent/research_v1/test_copilot_console_index.py
git commit -m "feat: persist copilot console indexes"
```

## Task 3: P43-C Runtime + CLI

**Files:**
- Modify: `agent/research_v1/copilot_console_index.py`
- Modify: `agent/research_v1/batch_cli.py`
- Modify: `tests/agent/research_v1/test_copilot_console_index.py`
- Modify: `tests/agent/research_v1/test_batch_cli.py`

- [ ] **Step 1: Add runtime test**

Append:

```python
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
```

- [ ] **Step 2: Implement runtime**

Append:

```python
def run_copilot_console_index(
    governance_root: Path,
    output_root: Path,
    as_of_date: str,
    lookback_days: int = 14,
    db: Any | None = None,
) -> dict[str, Any]:
    index = build_copilot_console_index(governance_root, as_of_date, lookback_days)
    if index.get("status") == P43_STATUS_BLOCKED_INVALID_INPUT:
        return {"status": P43_STATUS_BLOCKED_INVALID_INPUT, "warnings": index.get("warnings", [])}
    output_dir = Path(output_root) / as_of_date
    paths = write_copilot_console_index_artifacts(index, output_dir)
    if db is not None:
        db.save_copilot_console_index(index)
    summary = index.get("summary", {})
    return {
        "status": index["status"],
        "output_dir": str(output_dir),
        "day_count": summary.get("day_count", 0),
        "latest_day": summary.get("latest_day", ""),
        "missing_artifact_count": summary.get("missing_artifact_count", 0),
        "invalid_artifact_count": summary.get("invalid_artifact_count", 0),
        "paths": paths,
    }
```

- [ ] **Step 3: Add hard-boundary test**

Append:

```python
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
```

- [ ] **Step 4: Add CLI tests**

Append to `test_batch_cli.py`:

```python
def test_copilot_console_index_run_cli_success_writes_artifacts(tmp_path, monkeypatch, capsys):
    from agent.research_v1.batch_cli import main

    app_root = tmp_path / "app"

    def fake_run(**kwargs):
        output_dir = kwargs["output_root"] / "2026-04-30"
        output_dir.mkdir(parents=True, exist_ok=True)
        return {
            "status": "console_ready",
            "output_dir": str(output_dir),
            "day_count": 2,
            "latest_day": "2026-04-30",
            "missing_artifact_count": 3,
            "invalid_artifact_count": 0,
        }

    monkeypatch.setattr("agent.research_v1.batch_cli.run_copilot_console_index", fake_run)
    code = main(["--app-root", str(app_root), "copilot-console-index-run", "--as-of-date", "2026-04-30"])
    out = capsys.readouterr().out

    assert code == 0
    assert "Co-pilot console index status: console_ready" in out
    assert str(app_root / "output" / "governance" / "2026-04-30") in out


def test_copilot_console_index_run_cli_rejects_invalid_date(tmp_path, capsys):
    from agent.research_v1.batch_cli import main

    code = main(["--app-root", str(tmp_path), "copilot-console-index-run", "--as-of-date", "not-a-date"])

    assert code == 2
    assert "invalid copilot-console-index-run input" in capsys.readouterr().out


def test_copilot_console_index_run_cli_rejects_non_positive_lookback(tmp_path, capsys):
    from agent.research_v1.batch_cli import main

    code = main(["--app-root", str(tmp_path), "copilot-console-index-run", "--as-of-date", "2026-04-30", "--lookback-days", "0"])

    assert code == 2
    assert "lookback-days must be positive" in capsys.readouterr().out
```

- [ ] **Step 5: Wire CLI**

In `batch_cli.py` imports:

```python
from agent.research_v1.copilot_console_index import run_copilot_console_index
```

Add command:

```python
def _cmd_copilot_console_index_run(
    paths: HermesPaths,
    as_of_date: str,
    lookback_days: int,
    governance_root: str,
    output_root: str,
) -> int:
    from datetime import date as _date

    try:
        _date.fromisoformat(as_of_date)
    except (ValueError, TypeError):
        print(f"invalid copilot-console-index-run input: invalid date format '{as_of_date}'")
        return 2
    if lookback_days <= 0:
        print("invalid copilot-console-index-run input: lookback-days must be positive")
        return 2

    governance_path = Path(governance_root).expanduser()
    if not governance_path.is_absolute():
        governance_path = paths.app_root / governance_path
    output_path = Path(output_root).expanduser()
    if not output_path.is_absolute():
        output_path = paths.app_root / output_path

    database = _ensure_database(paths)
    result = run_copilot_console_index(
        governance_root=governance_path.resolve(),
        output_root=output_path.resolve(),
        as_of_date=as_of_date,
        lookback_days=lookback_days,
        db=database,
    )
    if result.get("status") == "blocked_invalid_input":
        print(f"invalid copilot-console-index-run input: {result.get('warnings', ['unknown'])[0]}")
        return 2
    print(f"Co-pilot console index status: {result['status']}")
    print(f"Output dir: {result['output_dir']}")
    print(f"Day count: {result['day_count']}")
    print(f"Latest day: {result['latest_day']}")
    print(f"Missing artifact count: {result['missing_artifact_count']}")
    print(f"Invalid artifact count: {result['invalid_artifact_count']}")
    return 0
```

Add parser:

```python
console_parser = subparsers.add_parser("copilot-console-index-run", help="Run static co-pilot console index.")
console_parser.add_argument("--as-of-date", required=True, help="As-of date YYYY-MM-DD.")
console_parser.add_argument("--lookback-days", default=14, type=int, help="Number of calendar days to scan.")
console_parser.add_argument("--governance-root", default="output/governance", help="Governance artifact root.")
console_parser.add_argument("--output-root", default="output/governance", help="Output root for console index artifacts.")
```

Add dispatch:

```python
if args.command == "copilot-console-index-run":
    return _cmd_copilot_console_index_run(
        paths,
        as_of_date=args.as_of_date,
        lookback_days=args.lookback_days,
        governance_root=args.governance_root,
        output_root=args.output_root,
    )
```

- [ ] **Step 6: Run tests and commit P43-C**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_copilot_console_index.py tests/agent/research_v1/test_batch_cli.py -q -k "copilot_console or copilot-console"
```

Commit:

```bash
git add agent/research_v1/copilot_console_index.py agent/research_v1/batch_cli.py tests/agent/research_v1/test_copilot_console_index.py tests/agent/research_v1/test_batch_cli.py
git commit -m "feat: add copilot console index cli"
```

## Task 4: P43-D Docs + Regression

**Files:**
- Modify: `README.md`
- Modify: `agent/research_v1/README.md`

- [ ] **Step 1: Update root README**

Add:

```markdown
### P43 Read-Only Co-Pilot Console Index

P43 scans existing P36-P42 governance artifacts and writes a static local console index: `p43_copilot_console_index.json`, `.md`, and `.html`. It is a navigation layer over existing evidence, not a live dashboard or trading surface.

P43 is a static read-only evidence index. It does not run research, call prior phase runtimes, schedule jobs, send notifications, recommend trades, or mutate research decisions.
```

- [ ] **Step 2: Update research README Data Flow**

Add:

```markdown
#### P43 Read-Only Co-Pilot Console Index

`copilot_console_index.py` scans existing files under `output/governance/YYYY-MM-DD/` and writes a static index for navigation. The flow is one-way: P43 does not invoke P36-P42 runtimes, `HermesResearchApp.run()`, `final_judge`, or broker/order APIs.
```

- [ ] **Step 3: Run verification**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_copilot_console_index.py -q
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_batch_cli.py -q -k "copilot_console or copilot-console"
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_recommendation_outcomes.py tests/agent/research_v1/test_market_regime_context.py tests/agent/research_v1/test_fundamental_quality.py tests/agent/research_v1/test_candidate_pool.py tests/agent/research_v1/test_research_memory_pack.py tests/agent/research_v1/test_decision_journal_guardrails.py tests/agent/research_v1/test_boss_copilot_daily_brief.py -q
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_governance_runtime.py tests/agent/research_v1/test_boss_governance_brief.py tests/agent/research_v1/test_signal_family_edge_review.py -q
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_doc_standards.py -q
```

Run full P20-P43 chain. Report host-specific PDF/Futu gaps separately if unrelated.

- [ ] **Step 4: Commit P43-D**

```bash
git add README.md agent/research_v1/README.md
git commit -m "docs: document p43 copilot console index"
```

## Final Report Template

```text
P43 Implementation Complete

Status Summary
Phase   Status   Commit
P43-A   PASS     <commit> feat: add copilot console index scanner
P43-B   PASS     <commit> feat: persist copilot console indexes
P43-C   PASS     <commit> feat: add copilot console index cli
P43-D   PASS     <commit> docs: document p43 copilot console index

Verification
- P43 focused: <n> passed
- P43 CLI: <n> passed
- P36-P42 regression: <n> passed
- Governance-adjacent regression: <n> passed
- Doc standards: <n> passed
- Full P20-P43 chain: <n> passed, with known host-specific gaps listed separately

Files Changed
- agent/research_v1/copilot_console_index.py
- agent/research_v1/data/database.py
- agent/research_v1/batch_cli.py
- tests/agent/research_v1/test_copilot_console_index.py
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
- no P36-P42 mutation
- no P36-P42 runtime invocation
```

## Review Checklist

- [ ] P43 scans files read-only.
- [ ] P43 never invokes prior phase runtimes.
- [ ] Static HTML has no remote dependencies.
- [ ] Missing artifacts are explicit.
- [ ] Invalid JSON does not crash scanning.
- [ ] Source hash changes when scanned artifacts change.
- [ ] CLI validates date and lookback.
- [ ] Markdown and HTML reject forbidden trading language.
- [ ] Docs mention P43 in root and research README.
