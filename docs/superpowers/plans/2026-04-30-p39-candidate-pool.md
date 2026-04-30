# P39 Candidate Pool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone deterministic candidate-pool engine so Hermes can surface research candidates from a point-in-time universe without changing recommendations.

**Architecture:** Add `candidate_pool.py` for universe validation, optional evidence joins, deterministic scoring, category assignment, artifact writing, and run orchestration. Extend `ResearchDatabase` with append-only candidate-pool run/item persistence, then expose a local `candidate-pool-run` CLI command.

**Tech Stack:** Python 3.11, dataclasses, sqlite3, pathlib, json, hashlib, datetime, argparse, pytest, local JSON fixtures.

---

## File Structure

- Create `agent/research_v1/candidate_pool.py`
  - P39 constants, universe normalization, source-date integrity, scoring, evidence joins, source hashing, artifact writing, and run orchestration.
- Modify `agent/research_v1/data/database.py`
  - Add candidate-pool schema and persistence/query helpers.
- Modify `agent/research_v1/batch_cli.py`
  - Add `candidate-pool-run`.
- Create `tests/agent/research_v1/test_candidate_pool.py`
  - Focused P39 scoring, exclusion, evidence, persistence, artifact, and hard-boundary tests.
- Modify `tests/agent/research_v1/test_batch_cli.py`
  - Add CLI tests for `candidate-pool-run`.
- Modify `README.md` and `agent/research_v1/README.md`
  - Document P39 as standalone candidate-discovery evidence.

Do not modify `app.py`, `final_judge.py`, `orchestrator.py`, `contracts.py`, `recommendation_outcomes.py`, `market_regime_context.py`, or `fundamental_quality.py` in this phase except for imports in tests if needed.

## Constants

Use these exact constants in `agent/research_v1/candidate_pool.py`:

```python
P39_SCHEMA_VERSION = "p39_candidate_pool.1"

P39_STATUS_COMPLETED = "completed"
P39_STATUS_COMPLETED_WITH_WARNINGS = "completed_with_warnings"
P39_STATUS_NO_CANDIDATES = "no_candidates"
P39_STATUS_BLOCKED_INVALID_INPUT = "blocked_invalid_input"

CANDIDATE_STATUS_INCLUDED = "included"
CANDIDATE_STATUS_EXCLUDED_MISSING_REQUIRED_FIELDS = "excluded_missing_required_fields"
CANDIDATE_STATUS_EXCLUDED_FUTURE_SOURCE_DATE = "excluded_future_source_date"
CANDIDATE_STATUS_EXCLUDED_LOW_LIQUIDITY = "excluded_low_liquidity"
CANDIDATE_STATUS_EXCLUDED_LOW_PRICE = "excluded_low_price"
CANDIDATE_STATUS_EXCLUDED_USER_RULE = "excluded_user_rule"

WORKFLOW_RESEARCH = "research_candidate"
WORKFLOW_MONITOR = "monitor_candidate"
WORKFLOW_DEFER = "defer_candidate"

P39_ARTIFACT_DISCLAIMER = (
    "P39 is candidate-discovery evidence only. It does not recommend trades, "
    "approve production adoption, place orders, train models, schedule jobs, "
    "or mutate research decisions."
)
```

Required ticker fields:

```python
P39_REQUIRED_TICKER_FIELDS = (
    "ticker",
    "sector",
    "source_date",
    "close",
    "close_20d_ago",
    "close_60d_ago",
    "close_120d_ago",
    "high_252d",
    "low_252d",
    "avg_dollar_volume_20d",
    "realized_vol_20d",
)
```

Forbidden terms:

```python
P39_FORBIDDEN_TERMS = (
    "buy this",
    "sell this",
    "follow this trade",
    "guaranteed edge",
    "production approved",
    "model promoted",
    "trade now",
)
```

## Task 1: P39-A Candidate Scoring Core

**Files:**
- Create: `agent/research_v1/candidate_pool.py`
- Create: `tests/agent/research_v1/test_candidate_pool.py`

- [ ] **Step 1: Write failing scoring tests**

Create `tests/agent/research_v1/test_candidate_pool.py` with these helpers and first tests:

```python
from __future__ import annotations

import json
from pathlib import Path

from agent.research_v1.candidate_pool import (
    P39_SCHEMA_VERSION,
    build_candidate_pool,
    compute_candidate_pool_source_hash,
)


def _ticker(
    ticker: str = "AAPL",
    sector: str = "technology",
    source_date: str = "2026-04-30",
    close: float = 200.0,
    close_20d_ago: float = 190.0,
    close_60d_ago: float = 170.0,
    close_120d_ago: float = 160.0,
    high_252d: float = 215.0,
    low_252d: float = 140.0,
    avg_dollar_volume_20d: float = 1_500_000_000.0,
    realized_vol_20d: float = 0.24,
    outcome_prior: dict | None = None,
) -> dict:
    row = {
        "ticker": ticker,
        "sector": sector,
        "currency": "USD",
        "source_date": source_date,
        "close": close,
        "close_20d_ago": close_20d_ago,
        "close_60d_ago": close_60d_ago,
        "close_120d_ago": close_120d_ago,
        "high_252d": high_252d,
        "low_252d": low_252d,
        "avg_dollar_volume_20d": avg_dollar_volume_20d,
        "realized_vol_20d": realized_vol_20d,
        "market_cap": 3_000_000_000_000.0,
        "benchmark_return_60d": 0.05,
        "catalyst_tags": ["earnings_soon"],
    }
    if outcome_prior is not None:
        row["outcome_prior"] = outcome_prior
    return row


def _payload(tickers: list[dict]) -> dict:
    return {
        "as_of_date": "2026-04-30",
        "source": "fixture",
        "universe_id": "us_liquid_growth",
        "tickers": tickers,
    }


def test_valid_universe_row_computes_component_scores():
    pool = build_candidate_pool(_payload([_ticker()]), as_of_date="2026-04-30")

    assert pool["schema_version"] == P39_SCHEMA_VERSION
    assert pool["status"] == "completed"
    assert len(pool["candidates"]) == 1
    candidate = pool["candidates"][0]
    assert candidate["ticker"] == "AAPL"
    assert candidate["workflow_action"] in {"research_candidate", "monitor_candidate", "defer_candidate"}
    assert 0.0 <= candidate["total_score"] <= 1.0
    assert candidate["component_scores"]["momentum_score"] > 0.5
    assert candidate["component_scores"]["liquidity_score"] > 0.8
    assert candidate["component_scores"]["risk_penalty_score"] > 0.5


def test_sorting_tie_breaker_is_deterministic_by_ticker():
    pool = build_candidate_pool(_payload([_ticker("MSFT"), _ticker("AAPL")]), as_of_date="2026-04-30")

    assert [c["ticker"] for c in pool["candidates"]] == ["AAPL", "MSFT"]
```

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_candidate_pool.py -q
```

Expected: import failure for `agent.research_v1.candidate_pool`.

- [ ] **Step 2: Implement constants, validation, and deterministic scoring**

Create `agent/research_v1/candidate_pool.py` with:

```python
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

P39_SCHEMA_VERSION = "p39_candidate_pool.1"
P39_STATUS_COMPLETED = "completed"
P39_STATUS_COMPLETED_WITH_WARNINGS = "completed_with_warnings"
P39_STATUS_NO_CANDIDATES = "no_candidates"
P39_STATUS_BLOCKED_INVALID_INPUT = "blocked_invalid_input"

CANDIDATE_STATUS_INCLUDED = "included"
CANDIDATE_STATUS_EXCLUDED_MISSING_REQUIRED_FIELDS = "excluded_missing_required_fields"
CANDIDATE_STATUS_EXCLUDED_FUTURE_SOURCE_DATE = "excluded_future_source_date"
CANDIDATE_STATUS_EXCLUDED_LOW_LIQUIDITY = "excluded_low_liquidity"
CANDIDATE_STATUS_EXCLUDED_LOW_PRICE = "excluded_low_price"
CANDIDATE_STATUS_EXCLUDED_USER_RULE = "excluded_user_rule"

WORKFLOW_RESEARCH = "research_candidate"
WORKFLOW_MONITOR = "monitor_candidate"
WORKFLOW_DEFER = "defer_candidate"

P39_ARTIFACT_DISCLAIMER = (
    "P39 is candidate-discovery evidence only. It does not recommend trades, "
    "approve production adoption, place orders, train models, schedule jobs, "
    "or mutate research decisions."
)

P39_REQUIRED_TICKER_FIELDS = (
    "ticker", "sector", "source_date", "close", "close_20d_ago",
    "close_60d_ago", "close_120d_ago", "high_252d", "low_252d",
    "avg_dollar_volume_20d", "realized_vol_20d",
)

P39_FORBIDDEN_TERMS = (
    "buy this", "sell this", "follow this trade", "guaranteed edge",
    "production approved", "model promoted", "trade now",
)
```

Implement helper functions:

```python
def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _scale(value: float, low: float, high: float) -> float:
    if high == low:
        return 0.5
    return _clamp((value - low) / (high - low))


def _safe_return(current: float, prior: float) -> float:
    if prior == 0:
        return 0.0
    return current / prior - 1.0
```

Implement component scoring exactly from the spec:

```python
def _momentum_score(row: dict[str, Any]) -> tuple[float, dict[str, float]]:
    close = float(row["close"])
    r20 = _safe_return(close, float(row["close_20d_ago"]))
    r60 = _safe_return(close, float(row["close_60d_ago"]))
    r120 = _safe_return(close, float(row["close_120d_ago"]))
    distance = _safe_return(close, float(row["high_252d"]))
    score = (
        0.50 * _scale(r60, -0.20, 0.30)
        + 0.30 * _scale(r20, -0.10, 0.15)
        + 0.20 * _scale(distance, -0.35, 0.0)
    )
    return round(score, 4), {
        "return_20d": round(r20, 4),
        "return_60d": round(r60, 4),
        "return_120d": round(r120, 4),
        "distance_from_252d_high": round(distance, 4),
    }
```

Implement:

- `_liquidity_score(avg_dollar_volume_20d)`
- `_risk_penalty_score(row, returns)`
- `_track_record_score(outcome_prior)`
- `_quality_score(row, quality_by_ticker, missing_context, evidence_refs)`
- `_regime_score(row, regime_context, missing_context, evidence_refs)`
- `_candidate_category(row, total, component_scores, returns, outcome_prior)`
- `_workflow_action(total_score, risk_notes)`

Use the exact formulas from the spec.

- [ ] **Step 3: Implement `build_candidate_pool()` and source hash**

Implement:

```python
def compute_candidate_pool_source_hash(
    input_payload: dict[str, Any],
    as_of_date: str,
    regime_context: dict[str, Any] | None = None,
    quality_by_ticker: dict[str, dict[str, Any]] | None = None,
) -> str:
    canonical = {
        "schema_version": P39_SCHEMA_VERSION,
        "as_of_date": as_of_date,
        "universe_id": input_payload.get("universe_id", ""),
        "source": input_payload.get("source", ""),
        "tickers": sorted(input_payload.get("tickers", []), key=lambda r: str(r.get("ticker", "")) if isinstance(r, dict) else ""),
        "regime_source_hash": (regime_context or {}).get("source_hash", ""),
        "quality_source_hashes": {
            ticker: report.get("source_hash", "")
            for ticker, report in sorted((quality_by_ticker or {}).items())
        },
    }
    return hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
```

Implement `build_candidate_pool(input_payload, as_of_date=None, regime_context=None, quality_by_ticker=None, max_candidates=20)` returning the top-level object from the spec.

Rules:

- Exclude non-dict rows with `excluded_missing_required_fields`.
- Exclude future `source_date`.
- Exclude missing required fields and record exact field names.
- Exclude `close < 5.0`.
- Exclude `avg_dollar_volume_20d < 5000000`.
- Exclude caller `exclude_reasons`.
- Preserve excluded rows in `excluded_items`.
- Sort included candidates deterministically.
- Limit candidates to `max_candidates`.
- Set status to `no_candidates` when no candidates remain.
- Add disclaimer.

- [ ] **Step 4: Add evidence and exclusion tests**

Append tests:

```python
def test_p38_quality_report_improves_quality_score_and_refs():
    quality = {"AAPL": {"overall_quality_score": 0.82, "confidence": 0.9, "red_flags_json": "[]", "source_hash": "q1"}}
    pool = build_candidate_pool(_payload([_ticker()]), "2026-04-30", quality_by_ticker=quality)
    c = pool["candidates"][0]
    assert c["component_scores"]["quality_score"] >= 0.80
    assert c["evidence_refs"]["p38_quality_source_hash"] == "q1"


def test_missing_p38_quality_records_missing_context():
    pool = build_candidate_pool(_payload([_ticker()]), "2026-04-30")
    assert "missing_fundamental_quality" in pool["candidates"][0]["missing_context"]


def test_p37_regime_context_affects_regime_score_and_refs():
    regime = {"regime_label": "risk_on_broad", "confidence": 0.9, "sector_scores_json": '{"technology": 0.8}', "source_hash": "r1"}
    pool = build_candidate_pool(_payload([_ticker(sector="technology")]), "2026-04-30", regime_context=regime)
    c = pool["candidates"][0]
    assert c["component_scores"]["regime_score"] > 0.65
    assert c["evidence_refs"]["p37_regime_source_hash"] == "r1"


def test_exclusions_are_preserved():
    rows = [
        _ticker("LOWVOL", avg_dollar_volume_20d=1_000_000),
        _ticker("PENNY", close=2.0),
        _ticker("FUTURE", source_date="2026-05-01"),
    ]
    pool = build_candidate_pool(_payload(rows), "2026-04-30")
    statuses = {item["ticker"]: item["candidate_status"] for item in pool["excluded_items"]}
    assert statuses["LOWVOL"] == "excluded_low_liquidity"
    assert statuses["PENNY"] == "excluded_low_price"
    assert statuses["FUTURE"] == "excluded_future_source_date"
```

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_candidate_pool.py -q
```

Expected: all P39-A tests pass.

- [ ] **Step 5: Commit P39-A**

```bash
git add agent/research_v1/candidate_pool.py tests/agent/research_v1/test_candidate_pool.py
git commit -m "feat: add candidate pool scoring"
```

## Task 2: P39-B Persistence + Artifacts

**Files:**
- Modify: `agent/research_v1/data/database.py`
- Modify: `agent/research_v1/candidate_pool.py`
- Modify: `tests/agent/research_v1/test_candidate_pool.py`

- [ ] **Step 1: Write failing persistence and artifact tests**

Append tests:

```python
from agent.research_v1.data.database import ResearchDatabase
from agent.research_v1.candidate_pool import write_candidate_pool_artifacts


def _db(tmp_path: Path) -> ResearchDatabase:
    db = ResearchDatabase(str(tmp_path / "research.db"))
    db.initialize()
    db.initialize_candidate_pool_schema()
    return db


def test_candidate_pool_persistence_is_idempotent(tmp_path: Path):
    db = _db(tmp_path)
    pool = build_candidate_pool(_payload([_ticker()]), "2026-04-30")

    first = db.save_candidate_pool(pool)
    second = db.save_candidate_pool(pool)
    runs = db.list_candidate_pool_runs(as_of_date="2026-04-30")
    items = db.list_candidate_pool_items(first)

    assert first == second
    assert len(runs) == 1
    assert len(items) == 1


def test_revised_candidate_pool_source_hash_appends(tmp_path: Path):
    db = _db(tmp_path)
    first_pool = build_candidate_pool(_payload([_ticker()]), "2026-04-30")
    revised = _ticker()
    revised["close_60d_ago"] = 150.0
    second_pool = build_candidate_pool(_payload([revised]), "2026-04-30")

    first = db.save_candidate_pool(first_pool)
    second = db.save_candidate_pool(second_pool)
    runs = db.list_candidate_pool_runs(as_of_date="2026-04-30")

    assert first != second
    assert len(runs) == 2


def test_candidate_pool_artifacts_are_written_and_safe(tmp_path: Path):
    pool = build_candidate_pool(_payload([_ticker()]), "2026-04-30")
    paths = write_candidate_pool_artifacts(pool, tmp_path / "output" / "governance" / "2026-04-30")

    assert paths["json"].name == "p39_candidate_pool.json"
    assert paths["md"].name == "p39_candidate_pool.md"
    text = paths["md"].read_text(encoding="utf-8").lower()
    assert "p39 is candidate-discovery evidence only" in text
    for forbidden in ("buy this", "sell this", "trade now"):
        assert forbidden not in text
```

- [ ] **Step 2: Add database schema**

Add methods to `ResearchDatabase`:

```python
def initialize_candidate_pool_schema(self) -> None:
    conn = self._get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS candidate_pool_runs (
            run_id TEXT PRIMARY KEY,
            schema_version TEXT NOT NULL,
            as_of_date TEXT NOT NULL,
            created_at TEXT NOT NULL,
            universe_id TEXT NOT NULL,
            source TEXT,
            status TEXT NOT NULL,
            candidate_count INTEGER NOT NULL,
            excluded_count INTEGER NOT NULL,
            source_hash TEXT NOT NULL,
            warnings_json TEXT NOT NULL,
            summary_json TEXT NOT NULL,
            UNIQUE(as_of_date, universe_id, source_hash)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS candidate_pool_items (
            item_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            schema_version TEXT NOT NULL,
            as_of_date TEXT NOT NULL,
            created_at TEXT NOT NULL,
            universe_id TEXT NOT NULL,
            ticker TEXT NOT NULL,
            sector TEXT,
            currency TEXT,
            source_date TEXT,
            candidate_status TEXT NOT NULL,
            candidate_category TEXT,
            workflow_action TEXT,
            rank INTEGER,
            total_score REAL,
            component_scores_json TEXT NOT NULL,
            feature_snapshot_json TEXT NOT NULL,
            evidence_refs_json TEXT NOT NULL,
            inclusion_reasons_json TEXT NOT NULL,
            risk_notes_json TEXT NOT NULL,
            missing_context_json TEXT NOT NULL,
            source_hash TEXT NOT NULL,
            UNIQUE(run_id, ticker, source_hash)
        )
    """)
    conn.commit()
    conn.close()
```

Implement:

- `save_candidate_pool(pool: dict) -> str`
- `list_candidate_pool_runs(as_of_date: str | None = None, limit: int = 20) -> list[dict]`
- `list_candidate_pool_items(run_id: str) -> list[dict]`

Use deterministic SHA-256 IDs:

```text
run_id = sha256(as_of_date|universe_id|source_hash)[:16]
item_id = sha256(run_id|ticker|source_hash)[:16]
```

- [ ] **Step 3: Add artifact writer**

In `candidate_pool.py`, implement:

```python
def write_candidate_pool_artifacts(pool: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "p39_candidate_pool.json"
    md_path = output_dir / "p39_candidate_pool.md"
    json_path.write_text(json.dumps(pool, indent=2, default=str), encoding="utf-8")

    candidates = pool.get("candidates", [])
    excluded = pool.get("excluded_items", [])
    lines = [
        f"# Candidate Pool - {pool.get('as_of_date', '')}",
        "",
        f"- Status: {pool.get('status', '')}",
        f"- Universe: {pool.get('universe_id', '')}",
        f"- Candidates: {len(candidates)}",
        f"- Excluded: {len(excluded)}",
        "",
    ]
    if candidates:
        lines.extend([
            "## Top Candidates",
            "",
            "| Rank | Ticker | Category | Workflow | Score | Reasons |",
            "|------|--------|----------|----------|-------|---------|",
        ])
        for i, candidate in enumerate(candidates, start=1):
            reasons = ", ".join(candidate.get("inclusion_reasons", [])[:3])
            lines.append(
                f"| {i} | {candidate['ticker']} | {candidate['candidate_category']} | "
                f"{candidate['workflow_action']} | {candidate['total_score']:.2f} | {reasons} |"
            )
        lines.append("")
    category_counts: dict[str, int] = {}
    for candidate in candidates:
        category = candidate.get("candidate_category", "unknown")
        category_counts[category] = category_counts.get(category, 0) + 1
    if category_counts:
        lines.extend(["## Category Counts", ""])
        for category, count in sorted(category_counts.items()):
            lines.append(f"- {category}: {count}")
        lines.append("")
    missing_context = sorted({
        item
        for candidate in candidates
        for item in candidate.get("missing_context", [])
    })
    if missing_context:
        lines.extend(["## Missing Context", ""])
        for item in missing_context:
            lines.append(f"- {item}")
        lines.append("")
    if excluded:
        lines.extend(["## Excluded Items", ""])
        for item in excluded[:20]:
            reasons = ", ".join(item.get("exclusion_reasons", []))
            lines.append(f"- {item.get('ticker', '')}: {item.get('candidate_status', '')} ({reasons})")
        lines.append("")
    lines.extend(["---", "", f"> {pool.get('disclaimer', P39_ARTIFACT_DISCLAIMER)}", ""])

    markdown = "\n".join(lines)
    lowered = markdown.lower()
    for forbidden in P39_FORBIDDEN_TERMS:
        if forbidden in lowered:
            raise ValueError(f"forbidden candidate-pool term rendered: {forbidden}")
    md_path.write_text(markdown, encoding="utf-8")
    return {"json": json_path, "md": md_path}
```

- [ ] **Step 4: Run tests and commit P39-B**

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_candidate_pool.py -q
git add agent/research_v1/candidate_pool.py agent/research_v1/data/database.py tests/agent/research_v1/test_candidate_pool.py
git commit -m "feat: persist candidate pool reports"
```

## Task 3: P39-C Run Orchestration + CLI

**Files:**
- Modify: `agent/research_v1/candidate_pool.py`
- Modify: `agent/research_v1/batch_cli.py`
- Modify: `tests/agent/research_v1/test_candidate_pool.py`
- Modify: `tests/agent/research_v1/test_batch_cli.py`

- [ ] **Step 1: Write failing run orchestration and hard-boundary tests**

Append:

```python
from agent.research_v1.candidate_pool import run_candidate_pool


def test_run_candidate_pool_persists_and_writes_artifacts(tmp_path: Path):
    db = _db(tmp_path)
    payload = _payload([_ticker()])
    result = run_candidate_pool(
        db=db,
        input_payload=payload,
        as_of_date="2026-04-30",
        output_root=tmp_path / "output" / "governance",
        max_candidates=20,
    )

    assert result["status"] == "completed"
    assert result["candidate_count"] == 1
    assert (Path(result["output_dir"]) / "p39_candidate_pool.json").exists()


def test_p39_hard_boundaries_are_explicit():
    from agent.research_v1 import candidate_pool as p39

    forbidden_names = {
        "broker", "order", "train_model", "scheduler", "notification",
        "HermesResearchApp", "run_research", "final_judge",
        "run_governance_runtime", "run_recommendation_outcome_tracking",
        "run_market_regime_context", "run_fundamental_quality",
        "_extract_thesis_inputs",
    }
    assert not (forbidden_names & set(p39.__dict__))
    assert "candidate-discovery evidence only" in p39.P39_ARTIFACT_DISCLAIMER
```

- [ ] **Step 2: Implement `run_candidate_pool()`**

In `candidate_pool.py`, implement:

```python
def run_candidate_pool(
    db: Any,
    input_payload: dict[str, Any],
    as_of_date: str | None = None,
    output_root: Path | None = None,
    max_candidates: int = 20,
) -> dict[str, Any]:
    effective_as_of = as_of_date or input_payload.get("as_of_date", "")
    if not effective_as_of:
        return {"status": P39_STATUS_BLOCKED_INVALID_INPUT, "warnings": ["missing as_of_date"]}

    db.initialize_candidate_pool_schema()
    regime_context = None
    if hasattr(db, "list_market_regime_snapshots"):
        regimes = db.list_market_regime_snapshots(as_of_date=effective_as_of, limit=1)
        regime_context = regimes[0] if regimes else None

    quality_by_ticker = {}
    if hasattr(db, "list_fundamental_quality_reports"):
        for row in input_payload.get("tickers", []):
            if isinstance(row, dict) and row.get("ticker"):
                reports = db.list_fundamental_quality_reports(ticker=row["ticker"], as_of_date=effective_as_of, limit=1)
                if reports:
                    quality_by_ticker[row["ticker"]] = reports[0]

    pool = build_candidate_pool(
        input_payload,
        effective_as_of,
        regime_context=regime_context,
        quality_by_ticker=quality_by_ticker,
        max_candidates=max_candidates,
    )
    run_id = db.save_candidate_pool(pool)
    if output_root is None:
        output_root = Path("output/governance")
    output_dir = Path(output_root) / effective_as_of
    paths = write_candidate_pool_artifacts(pool, output_dir)
    return {
        "status": pool["status"],
        "run_id": run_id,
        "output_dir": str(output_dir),
        "candidate_count": len(pool.get("candidates", [])),
        "excluded_count": len(pool.get("excluded_items", [])),
        "top_candidate": pool["candidates"][0]["ticker"] if pool.get("candidates") else "",
        "warning_count": len(pool.get("warnings", [])),
        "paths": paths,
    }
```

- [ ] **Step 3: Write failing CLI tests**

Append to `tests/agent/research_v1/test_batch_cli.py`:

```python
def test_candidate_pool_run_cli_success_writes_artifacts(tmp_path, monkeypatch, capsys):
    from agent.research_v1.batch_cli import main

    app_root = tmp_path / "app"
    input_path = tmp_path / "universe.json"
    input_path.write_text('{"as_of_date":"2026-04-30","source":"fixture","universe_id":"u1","tickers":[]}', encoding="utf-8")

    def fake_run(**kwargs):
        output_dir = kwargs["output_root"] / "2026-04-30"
        output_dir.mkdir(parents=True, exist_ok=True)
        return {
            "status": "no_candidates",
            "output_dir": str(output_dir),
            "candidate_count": 0,
            "excluded_count": 0,
            "top_candidate": "",
            "warning_count": 0,
        }

    monkeypatch.setattr("agent.research_v1.batch_cli.run_candidate_pool", fake_run)

    code = main(["--app-root", str(app_root), "candidate-pool-run", "--input", str(input_path), "--as-of-date", "2026-04-30"])
    out = capsys.readouterr().out

    assert code == 0
    assert "Candidate pool status: no_candidates" in out
    assert str(app_root / "output" / "governance" / "2026-04-30") in out


def test_candidate_pool_run_cli_rejects_invalid_date(tmp_path, capsys):
    from agent.research_v1.batch_cli import main

    input_path = tmp_path / "universe.json"
    input_path.write_text('{"as_of_date":"2026-04-30","source":"fixture","universe_id":"u1","tickers":[]}', encoding="utf-8")

    code = main(["--app-root", str(tmp_path), "candidate-pool-run", "--input", str(input_path), "--as-of-date", "not-a-date"])

    assert code == 2
    assert "invalid candidate-pool-run input" in capsys.readouterr().out
```

- [ ] **Step 4: Implement CLI**

In `batch_cli.py`:

- Import `run_candidate_pool`.
- Add `_cmd_candidate_pool_run(paths, input_path, as_of_date, output_root, max_candidates)`.
- Validate file exists.
- Validate JSON.
- Validate `tickers` is a list.
- Validate every ticker item is a dict.
- Validate effective date with `date.fromisoformat`.
- Validate `max_candidates > 0`.
- Resolve relative `output_root` under `paths.app_root`.
- Print the exact summary lines from the spec.
- Return `2` for invalid input.

Add parser:

```python
candidate_parser = subparsers.add_parser("candidate-pool-run", help="Run candidate pool discovery.")
candidate_parser.add_argument("--input", required=True, help="Path to a JSON universe input file.")
candidate_parser.add_argument("--as-of-date", default=None, help="Override as-of date YYYY-MM-DD.")
candidate_parser.add_argument("--output-root", default="output/governance", help="Root directory for candidate pool artifacts.")
candidate_parser.add_argument("--max-candidates", default=20, type=int, help="Maximum candidates to keep.")
```

Route in `main()`.

- [ ] **Step 5: Run tests and commit P39-C**

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_candidate_pool.py tests/agent/research_v1/test_batch_cli.py -q -k "candidate_pool or candidate_pool_run"
git add agent/research_v1/candidate_pool.py agent/research_v1/batch_cli.py tests/agent/research_v1/test_candidate_pool.py tests/agent/research_v1/test_batch_cli.py
git commit -m "feat: add candidate pool cli"
```

## Task 4: P39-D Docs + Regression

**Files:**
- Modify: `README.md`
- Modify: `agent/research_v1/README.md`

- [ ] **Step 1: Update root README**

Add P39 to the current version summary and describe:

- `agent/research_v1/candidate_pool.py`
- `candidate-pool-run`
- `p39_candidate_pool.{json,md}`
- P39 is candidate-discovery evidence only.
- P39 does not call the research app or produce recommendations.

- [ ] **Step 2: Update research README**

In `agent/research_v1/README.md`, update the Data Flow section with:

```text
P39 candidate_pool.py consumes a point-in-time ticker universe plus read-only P36/P37/P38 evidence. It emits a candidate pool for human review. The flow is one-way: candidate-pool artifacts do not call HermesResearchApp.run(), final_judge, _extract_thesis_inputs(), or broker/order APIs.
```

- [ ] **Step 3: Run focused and regression verification**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_candidate_pool.py -q
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_batch_cli.py -q -k "candidate_pool or candidate_pool_run"
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_recommendation_outcomes.py tests/agent/research_v1/test_market_regime_context.py tests/agent/research_v1/test_fundamental_quality.py -q
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_governance_runtime.py tests/agent/research_v1/test_boss_governance_brief.py tests/agent/research_v1/test_signal_family_edge_review.py -q
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_doc_standards.py -q
```

Then run the full P20-P39 chain. If the host-specific PDF/Futu checks fail, report them separately and do not hide them.

- [ ] **Step 4: Commit P39-D**

```bash
git add README.md agent/research_v1/README.md
git commit -m "docs: document p39 candidate pool"
```

## Final Report Format

When implementation is complete, report:

```text
P39 Implementation Complete

Status Summary
Phase   Status   Commit
P39-A   PASS     <commit> feat: add candidate pool scoring
P39-B   PASS     <commit> feat: persist candidate pool reports
P39-C   PASS     <commit> feat: add candidate pool cli
P39-D   PASS     <commit> docs: document p39 candidate pool

Verification
- P39 focused: <n> passed
- P39 CLI: <n> passed
- P36/P37/P38 regression: <n> passed
- Governance-adjacent regression: <n> passed
- Doc standards: <n> passed
- Full P20-P39 chain: <n> passed, with known host-specific gaps listed separately

Files Changed
- agent/research_v1/candidate_pool.py
- agent/research_v1/data/database.py
- agent/research_v1/batch_cli.py
- tests/agent/research_v1/test_candidate_pool.py
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
- no P35/P36/P37/P38 mutation
```

## Review Checklist

Before asking for review:

- [ ] Candidate scoring is deterministic.
- [ ] Excluded rows are preserved.
- [ ] Missing required fields are exact and structured.
- [ ] Source hash includes universe data and evidence source hashes.
- [ ] Markdown contains no forbidden trading terms.
- [ ] CLI rejects invalid dates, invalid JSON, non-list tickers, non-dict ticker rows, and non-positive `max_candidates`.
- [ ] Persistence is idempotent and append-only.
- [ ] P36/P37/P38 context is read-only.
- [ ] No research decision path changed.
