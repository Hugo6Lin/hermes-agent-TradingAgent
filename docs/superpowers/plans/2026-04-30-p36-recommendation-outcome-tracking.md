# P36 Recommendation Outcome Tracking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build canonical recommendation outcome tracking so Hermes can measure realized forward outcomes for prior recommendations without trading, scheduling, training, or changing P35 runtime.

**Architecture:** Add a focused `recommendation_outcomes.py` module for action resolution, price-history normalization, deterministic outcome calculation, artifact writing, and boundary-safe orchestration. Extend `ResearchDatabase` with canonical outcome persistence and summaries, then expose a local `outcome-run` CLI command that writes standalone P36 artifacts under `output/governance/YYYY-MM-DD/`.

**Tech Stack:** Python 3.11, dataclasses, sqlite3, pathlib, json, hashlib, datetime, statistics, argparse, pytest, existing canonical research tables, existing Futu history provider, fake providers in tests.

---

## File Structure

- Create `agent/research_v1/recommendation_outcomes.py`
  - P36 constants, dataclasses, action resolution, latest-report tie-breaker, calendar resolution, price-row normalization, deterministic source hashing, outcome calculation, aggregation, artifact writing, and run orchestration.
- Modify `agent/research_v1/data/database.py`
  - Canonical outcome schema, append-only idempotent save, query helpers, and summary helpers.
- Modify `agent/research_v1/data/futu_opend.py`
  - Preserve existing behavior while including `open`, `high`, `low`, and adjustment provenance when daily history provides them.
- Modify `agent/research_v1/batch_cli.py`
  - Add `outcome-run`.
- Create `tests/agent/research_v1/test_recommendation_outcomes.py`
  - P36 calculation, action semantics, idempotence, persistence, artifacts, and hard-boundary tests.
- Modify `tests/agent/research_v1/test_batch_cli.py`
  - CLI success and invalid-input coverage for `outcome-run`.
- Modify `README.md` and `agent/research_v1/README.md`
  - Document P36 in the system map and data flow.

Do not modify P35 runtime behavior. Do not wire P36 into P35 registry/runtime/brief in this phase.

## Constants

Use these exact constants in `agent/research_v1/recommendation_outcomes.py`:

```python
P36_SCHEMA_VERSION = "p36_recommendation_outcome.1"

P36_EVALUATED_ACTIONS = frozenset({"Buy Stock", "Buy Call"})
P36_NOT_EVALUABLE_ACTIONS = frozenset({
    "Bull Call Spread",
    "Sell Cash-Secured Put",
    "Covered Call",
})
P36_NOT_APPLICABLE_ACTIONS = frozenset({"Watchlist", "No Trade"})

P36_STATUS_EVALUATED = "evaluated"
P36_STATUS_NOT_EVALUABLE = "not_evaluable_in_v1"
P36_STATUS_NOT_APPLICABLE = "not_applicable"
P36_STATUS_INSUFFICIENT_DATA = "insufficient_data"
P36_STATUS_INVALID_SIGNAL = "invalid_signal"

P36_ENTRY_RULE_NEXT_OPEN = "next_open"
P36_DEFAULT_HORIZONS = (5, 20, 60)

PRICE_ADJUSTMENT_ADJUSTED = "adjusted"
PRICE_ADJUSTMENT_UNADJUSTED = "unadjusted"
PRICE_ADJUSTMENT_UNKNOWN = "unknown"

PATH_PRECISION_OHLC = "ohlc"
PATH_PRECISION_CLOSE_ONLY = "close_only"

COST_BASIS_NONE = "none"
COST_BASIS_FLAT_BPS = "flat_bps"
```

---

### Task 1: P36-A Canonical Outcome Schema + Persistence

**Files:**
- Modify: `agent/research_v1/data/database.py`
- Create: `tests/agent/research_v1/test_recommendation_outcomes.py`

- [ ] **Step 1: Add failing persistence tests**

Create `tests/agent/research_v1/test_recommendation_outcomes.py` with these initial tests:

```python
"""Tests for P36 recommendation outcome tracking."""

from __future__ import annotations

from pathlib import Path

from agent.research_v1.contracts import CanonicalSignal, ResearchMode, ResearchTask
from agent.research_v1.data.database import ResearchDatabase


def _db(tmp_path: Path) -> ResearchDatabase:
    db = ResearchDatabase(str(tmp_path / "research.db"))
    db.initialize()
    db.initialize_canonical_schema()
    db.initialize_canonical_outcome_schema()
    return db


def _task() -> ResearchTask:
    return ResearchTask(
        task_id="task_p36_aapl",
        request_text="Research AAPL",
        tickers=["AAPL"],
        research_mode=ResearchMode.STANDARD,
    )


def _signal() -> CanonicalSignal:
    return CanonicalSignal(
        ticker="AAPL",
        rating="BUY",
        confidence=0.82,
        priority_score=88.0,
        entry_price=100.0,
        stop_loss=92.0,
        take_profit=115.0,
        holding_horizon="60d",
        decision_reason="P36 fixture",
    )


def _seed_signal(db: ResearchDatabase) -> str:
    task = _task()
    signal = _signal()
    db.save_research_task(task)
    return db.save_canonical_signal(signal, task.task_id)


def _outcome_payload(signal_id: str, data_hash: str = "hash_a") -> dict:
    return {
        "schema_version": "p36_recommendation_outcome.1",
        "signal_id": signal_id,
        "task_id": "task_p36_aapl",
        "ticker": "AAPL",
        "action": "Buy Stock",
        "rating": "BUY",
        "horizon_days": 5,
        "calendar": "XNYS",
        "entry_rule": "next_open",
        "entry_price": 101.0,
        "entry_date": "2026-04-01",
        "exit_price": 110.0,
        "exit_date": "2026-04-08",
        "target_reached": False,
        "stop_breached": False,
        "target_reached_before_stop": False,
        "benchmark_return_pct": None,
        "gross_return_pct": 0.0891089109,
        "net_return_pct": 0.0891089109,
        "max_drawdown_pct": -0.01,
        "win": True,
        "win_definition": "net_return_positive",
        "status": "evaluated",
        "evaluation_proxy": "none",
        "cost_basis": "none",
        "cost_bps": 0.0,
        "data_source": "fake_provider",
        "price_adjustment": "adjusted",
        "data_source_hash": data_hash,
        "path_precision": "ohlc",
        "evaluated_for_date": "2026-04-30",
        "evaluated_at": "2026-04-30T12:00:00Z",
    }


def test_canonical_outcome_schema_persists_rows(tmp_path: Path):
    db = _db(tmp_path)
    signal_id = _seed_signal(db)

    outcome_id = db.save_canonical_outcome(_outcome_payload(signal_id=signal_id))
    rows = db.list_canonical_outcomes_by_signal(signal_id)

    assert outcome_id
    assert len(rows) == 1
    assert rows[0]["schema_version"] == "p36_recommendation_outcome.1"
    assert rows[0]["status"] == "evaluated"
    assert rows[0]["action"] == "Buy Stock"
    assert rows[0]["evaluated_for_date"] == "2026-04-30"
    assert rows[0]["evaluated_at"] == "2026-04-30T12:00:00Z"


def test_canonical_outcome_natural_key_noops_same_data(tmp_path: Path):
    db = _db(tmp_path)
    signal_id = _seed_signal(db)

    first = db.save_canonical_outcome(_outcome_payload(signal_id=signal_id, data_hash="same_hash"))
    second = db.save_canonical_outcome(_outcome_payload(signal_id=signal_id, data_hash="same_hash"))
    rows = db.list_canonical_outcomes_by_signal(signal_id)

    assert first == second
    assert len(rows) == 1


def test_canonical_outcome_revised_data_hash_appends_row(tmp_path: Path):
    db = _db(tmp_path)
    signal_id = _seed_signal(db)

    first = db.save_canonical_outcome(_outcome_payload(signal_id=signal_id, data_hash="hash_a"))
    second = db.save_canonical_outcome(_outcome_payload(signal_id=signal_id, data_hash="hash_b"))
    rows = db.list_canonical_outcomes_by_signal(signal_id)

    assert first != second
    assert len(rows) == 2


def test_canonical_outcome_summaries_group_by_action_rating_ticker_and_horizon(tmp_path: Path):
    db = _db(tmp_path)
    signal_id = _seed_signal(db)
    db.save_canonical_outcome(_outcome_payload(signal_id=signal_id, data_hash="hash_a"))

    assert db.summarize_outcomes_by("action")[0]["group"] == "Buy Stock"
    assert db.summarize_outcomes_by("rating")[0]["group"] == "BUY"
    assert db.summarize_outcomes_by("ticker")[0]["group"] == "AAPL"
    assert db.summarize_outcomes_by("horizon")[0]["group"] == 5
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_recommendation_outcomes.py -q
```

Expected: fail because canonical outcome schema methods do not exist.

- [ ] **Step 3: Implement schema and persistence**

Modify `ResearchDatabase` in `agent/research_v1/data/database.py`:

```python
def initialize_canonical_outcome_schema(self) -> None:
    conn = self._get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS canonical_recommendation_outcomes (
                canonical_outcome_id TEXT PRIMARY KEY,
                schema_version TEXT NOT NULL,
                signal_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                ticker TEXT NOT NULL,
                action TEXT NOT NULL,
                rating TEXT NOT NULL,
                horizon_days INTEGER NOT NULL,
                calendar TEXT NOT NULL,
                entry_rule TEXT NOT NULL,
                entry_price REAL,
                entry_date TEXT,
                exit_price REAL,
                exit_date TEXT,
                target_reached INTEGER NOT NULL DEFAULT 0,
                stop_breached INTEGER NOT NULL DEFAULT 0,
                target_reached_before_stop INTEGER NOT NULL DEFAULT 0,
                benchmark_return_pct REAL,
                gross_return_pct REAL,
                net_return_pct REAL,
                max_drawdown_pct REAL,
                win INTEGER NOT NULL DEFAULT 0,
                win_definition TEXT NOT NULL,
                status TEXT NOT NULL,
                evaluation_proxy TEXT NOT NULL DEFAULT 'none',
                cost_basis TEXT NOT NULL DEFAULT 'none',
                cost_bps REAL NOT NULL DEFAULT 0.0,
                data_source TEXT NOT NULL,
                price_adjustment TEXT NOT NULL DEFAULT 'unknown',
                data_source_hash TEXT NOT NULL,
                path_precision TEXT NOT NULL DEFAULT 'close_only',
                evaluated_for_date TEXT NOT NULL,
                evaluated_at TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(signal_id, horizon_days, evaluated_for_date, data_source_hash),
                FOREIGN KEY (signal_id) REFERENCES canonical_signals(signal_id)
            )
        """)
        conn.commit()
    finally:
        conn.close()
```

Add `save_canonical_outcome`, `list_canonical_outcomes_by_signal`, `get_recent_outcome_track_record`, and `summarize_outcomes_by`. Convert SQLite integer booleans back to Python booleans in query results. `save_canonical_outcome` must derive `canonical_outcome_id` from:

```python
parts = [
    outcome["signal_id"],
    str(outcome["horizon_days"]),
    outcome["evaluated_for_date"],
    outcome["data_source_hash"],
]
```

and must use `INSERT OR IGNORE` so identical natural-key reruns are no-ops.

- [ ] **Step 4: Run tests and confirm pass**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_recommendation_outcomes.py -q
```

Expected: `4 passed`.

- [ ] **Step 5: Commit P36-A**

Run:

```bash
git add agent/research_v1/data/database.py tests/agent/research_v1/test_recommendation_outcomes.py
git commit -m "feat: add canonical recommendation outcome persistence"
```

---

### Task 2: P36-B Outcome Computation + Provider Plumbing

**Files:**
- Create: `agent/research_v1/recommendation_outcomes.py`
- Modify: `agent/research_v1/data/futu_opend.py`
- Modify: `tests/agent/research_v1/test_recommendation_outcomes.py`

- [ ] **Step 1: Add failing computation tests**

Append tests covering action semantics, entry semantics, costs, provenance, and win definitions:

```python
from datetime import date

from agent.research_v1.recommendation_outcomes import (
    compute_data_source_hash,
    evaluate_recommendation_signal,
    normalize_price_rows,
    resolve_calendar,
)


class FakeHistoryProvider:
    data_source = "fake_provider"
    price_adjustment = "adjusted"

    def __init__(self, rows):
        self.rows = rows

    def fetch_history(self, symbol, start_date, end_date):
        return self.rows


def _rows(start=100.0, count=70):
    rows = []
    for idx in range(count):
        price = start + idx
        rows.append({
            "date": f"2026-04-{idx + 1:02d}" if idx < 30 else f"2026-05-{idx - 29:02d}",
            "open": price,
            "high": price + 2.0,
            "low": price - 2.0,
            "close": price + 1.0,
            "price_adjustment": "adjusted",
        })
    return rows


def test_buy_stock_evaluates_default_horizons_with_ohlc_data():
    outcomes = evaluate_recommendation_signal(
        signal={
            "signal_id": "signal_1",
            "task_id": "task_1",
            "ticker": "AAPL",
            "rating": "BUY",
            "entry_price": 100.0,
            "stop_loss": 92.0,
            "take_profit": 115.0,
            "created_at": "2026-04-01T20:00:00Z",
        },
        action="Buy Stock",
        provider=FakeHistoryProvider(_rows()),
        evaluated_for_date=date(2026, 4, 30),
    )

    assert [row["horizon_days"] for row in outcomes] == [5, 20, 60]
    assert all(row["status"] == "evaluated" for row in outcomes)
    assert outcomes[0]["entry_rule"] == "next_open"
    assert outcomes[0]["entry_price"] == 100.0
    assert outcomes[0]["path_precision"] == "ohlc"


def test_buy_call_uses_underlying_price_proxy():
    outcomes = evaluate_recommendation_signal(
        signal={
            "signal_id": "signal_2",
            "task_id": "task_2",
            "ticker": "AAPL",
            "rating": "BUY",
            "entry_price": 100.0,
            "stop_loss": None,
            "take_profit": None,
            "created_at": "2026-04-01T20:00:00Z",
        },
        action="Buy Call",
        provider=FakeHistoryProvider(_rows()),
        evaluated_for_date=date(2026, 4, 30),
    )

    assert all(row["status"] == "evaluated" for row in outcomes)
    assert all(row["evaluation_proxy"] == "underlying_price_proxy" for row in outcomes)


def test_option_income_and_spread_structures_are_not_evaluable_in_v1():
    for action in ["Bull Call Spread", "Sell Cash-Secured Put", "Covered Call"]:
        outcomes = evaluate_recommendation_signal(
            signal={
                "signal_id": f"signal_{action}",
                "task_id": "task_struct",
                "ticker": "AAPL",
                "rating": "BUY",
                "entry_price": 100.0,
                "stop_loss": None,
                "take_profit": None,
                "created_at": "2026-04-01T20:00:00Z",
            },
            action=action,
            provider=FakeHistoryProvider(_rows()),
            evaluated_for_date=date(2026, 4, 30),
        )
        assert {row["status"] for row in outcomes} == {"not_evaluable_in_v1"}


def test_watchlist_and_no_trade_are_not_applicable():
    for action in ["Watchlist", "No Trade"]:
        outcomes = evaluate_recommendation_signal(
            signal={
                "signal_id": f"signal_{action}",
                "task_id": "task_na",
                "ticker": "AAPL",
                "rating": "HOLD",
                "entry_price": None,
                "stop_loss": None,
                "take_profit": None,
                "created_at": "2026-04-01T20:00:00Z",
            },
            action=action,
            provider=FakeHistoryProvider(_rows()),
            evaluated_for_date=date(2026, 4, 30),
        )
        assert {row["status"] for row in outcomes} == {"not_applicable"}


def test_missing_action_or_entry_price_is_invalid_signal():
    missing_action = evaluate_recommendation_signal(
        signal={
            "signal_id": "signal_missing_action",
            "task_id": "task_invalid",
            "ticker": "AAPL",
            "rating": "BUY",
            "entry_price": 100.0,
            "stop_loss": None,
            "take_profit": None,
            "created_at": "2026-04-01T20:00:00Z",
        },
        action=None,
        provider=FakeHistoryProvider(_rows()),
        evaluated_for_date=date(2026, 4, 30),
    )
    missing_entry = evaluate_recommendation_signal(
        signal={
            "signal_id": "signal_missing_entry",
            "task_id": "task_invalid",
            "ticker": "AAPL",
            "rating": "BUY",
            "entry_price": None,
            "stop_loss": None,
            "take_profit": None,
            "created_at": "2026-04-01T20:00:00Z",
        },
        action="Buy Stock",
        provider=FakeHistoryProvider(_rows()),
        evaluated_for_date=date(2026, 4, 30),
    )

    assert {row["status"] for row in missing_action} == {"invalid_signal"}
    assert {row["status"] for row in missing_entry} == {"invalid_signal"}


def test_missing_next_open_or_horizon_row_is_insufficient_data():
    no_open_rows = _rows()
    no_open_rows[0] = {**no_open_rows[0], "open": None}
    no_open = evaluate_recommendation_signal(
        signal={
            "signal_id": "signal_no_open",
            "task_id": "task_data",
            "ticker": "AAPL",
            "rating": "BUY",
            "entry_price": 100.0,
            "stop_loss": None,
            "take_profit": None,
            "created_at": "2026-04-01T20:00:00Z",
        },
        action="Buy Stock",
        provider=FakeHistoryProvider(no_open_rows),
        evaluated_for_date=date(2026, 4, 30),
    )
    short_history = evaluate_recommendation_signal(
        signal={
            "signal_id": "signal_short_history",
            "task_id": "task_data",
            "ticker": "AAPL",
            "rating": "BUY",
            "entry_price": 100.0,
            "stop_loss": None,
            "take_profit": None,
            "created_at": "2026-04-01T20:00:00Z",
        },
        action="Buy Stock",
        provider=FakeHistoryProvider(_rows(count=6)),
        evaluated_for_date=date(2026, 4, 30),
    )

    assert {row["status"] for row in no_open} == {"insufficient_data"}
    assert any(row["horizon_days"] == 20 and row["status"] == "insufficient_data" for row in short_history)


def test_calendar_hash_adjustment_cost_and_win_semantics():
    assert resolve_calendar("HK.00700") == "XHKG"
    assert resolve_calendar("US.AAPL") == "XNYS"
    assert resolve_calendar("AAPL") == "XNYS"

    rows = normalize_price_rows([
        {"date": "2026-04-01", "open": 100.0, "high": 102.0, "low": 98.0, "close": 101.0},
        {"date": "2026-04-02", "open": 101.0, "high": 120.0, "low": 99.0, "close": 119.0},
    ], default_price_adjustment="unknown")
    assert rows[0]["price_adjustment"] == "unknown"
    assert compute_data_source_hash(rows) == compute_data_source_hash(list(reversed(rows)))

    outcomes = evaluate_recommendation_signal(
        signal={
            "signal_id": "signal_win",
            "task_id": "task_win",
            "ticker": "AAPL",
            "rating": "BUY",
            "entry_price": 100.0,
            "stop_loss": 95.0,
            "take_profit": 110.0,
            "created_at": "2026-04-01T20:00:00Z",
        },
        action="Buy Stock",
        provider=FakeHistoryProvider(_rows()),
        evaluated_for_date=date(2026, 4, 30),
        flat_cost_bps=10.0,
    )

    assert outcomes[0]["cost_basis"] == "flat_bps"
    assert outcomes[0]["cost_bps"] == 10.0
    assert outcomes[0]["net_return_pct"] < outcomes[0]["gross_return_pct"]
    assert outcomes[0]["win_definition"] == "target_reached_before_stop"
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_recommendation_outcomes.py -q
```

Expected: fail because `recommendation_outcomes.py` does not exist.

- [ ] **Step 3: Implement `recommendation_outcomes.py`**

Create `agent/research_v1/recommendation_outcomes.py` with:

- constants from this plan
- `resolve_calendar(ticker: str) -> str | None`
- `normalize_price_rows(rows, default_price_adjustment="unknown") -> list[dict]`
- `compute_data_source_hash(rows: list[dict]) -> str`
- `evaluate_recommendation_signal(...) -> list[dict]`
- `resolve_signal_action(db, task_id: str) -> str | None`
- `build_distribution_summary(outcomes: list[dict]) -> list[dict]`
- `run_recommendation_outcome_tracking(...)`
- `write_recommendation_outcome_artifacts(...)`

Implementation rules:

- Sort normalized rows by `date`.
- Use fixed hash field order `date`, `open`, `high`, `low`, `close`, `price_adjustment`.
- If action is `Watchlist` or `No Trade`, emit one row per default horizon with `status = not_applicable`.
- If action is a v1 non-evaluable structure, emit one row per default horizon with `status = not_evaluable_in_v1`.
- If action is unknown or entry price is missing for an evaluated action, emit one row per default horizon with `status = invalid_signal`.
- For evaluated actions, use the first normalized row after signal creation as entry row. Its `open` is the entry price.
- Do not use close as fallback for entry.
- For horizon `N`, use the row at `entry_index + N`; if absent, emit `insufficient_data` for that horizon.
- Compute drawdown from lows when available; otherwise from closes and set `path_precision = close_only`.
- For target/stop ordering, scan rows from entry through exit; the first event wins.
- Persist `evaluated_for_date` from the run input and `evaluated_at` as UTC ISO-8601 with `Z`.

- [ ] **Step 4: Extend Futu history normalization**

Modify `agent/research_v1/data/futu_opend.py` so `FutuQuoteClient.fetch_history` returns `open`, `high`, `low`, and `price_adjustment` when available while preserving existing `date` and `close` keys.

Use:

```python
row = {
    "date": date_value,
    "day": date_value,
    "open": _safe_float(raw.get("open")),
    "high": _safe_float(raw.get("high")),
    "low": _safe_float(raw.get("low")),
    "close": _safe_float(raw.get("close")),
    "price_adjustment": "adjusted",
}
```

Preserve existing behavior for callers that only read `day`, `date`, and `close`.

- [ ] **Step 5: Run focused computation tests**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_recommendation_outcomes.py -q
```

Expected: all tests in the file pass.

- [ ] **Step 6: Commit P36-B**

Run:

```bash
git add agent/research_v1/recommendation_outcomes.py agent/research_v1/data/futu_opend.py tests/agent/research_v1/test_recommendation_outcomes.py
git commit -m "feat: compute recommendation outcomes"
```

---

### Task 3: P36-C CLI + Artifact Writer

**Files:**
- Modify: `agent/research_v1/batch_cli.py`
- Modify: `tests/agent/research_v1/test_batch_cli.py`
- Modify: `tests/agent/research_v1/test_recommendation_outcomes.py`

- [ ] **Step 1: Add artifact and hard-boundary tests**

Append tests to `tests/agent/research_v1/test_recommendation_outcomes.py`:

```python
from agent.research_v1.recommendation_outcomes import (
    build_distribution_summary,
    write_recommendation_outcome_artifacts,
)


def test_distribution_summary_leads_with_central_tendency():
    outcomes = [
        {**_outcome_payload("signal_a", "hash_a"), "action": "Buy Stock", "net_return_pct": 0.10, "max_drawdown_pct": -0.02, "win": True},
        {**_outcome_payload("signal_b", "hash_b"), "action": "Buy Stock", "net_return_pct": -0.04, "max_drawdown_pct": -0.08, "win": False},
    ]

    summary = build_distribution_summary(outcomes)

    assert summary
    assert summary[0]["group_type"] in {"action", "rating", "horizon"}
    assert "median_net_return" in summary[0]
    assert "p25_net_return" in summary[0]
    assert "p75_net_return" in summary[0]


def test_artifact_writer_outputs_json_and_markdown(tmp_path: Path):
    report = {
        "run_date": "2026-04-30",
        "evaluated_for_date": "2026-04-30",
        "schema_version": "p36_recommendation_outcome.1",
        "status": "completed",
        "signals_considered": 1,
        "outcome_rows_written": 1,
        "duplicate_rows_skipped": 0,
        "evaluated_count": 1,
        "not_applicable_count": 0,
        "not_evaluable_count": 0,
        "insufficient_data_count": 0,
        "invalid_signal_count": 0,
        "warnings": [],
        "distribution_summary": [],
        "extreme_examples": [],
        "disclaimer": "P36 is recommendation outcome tracking only. It does not approve production adoption, instruct trades, place orders, train models, schedule jobs, or mutate production configuration.",
    }

    paths = write_recommendation_outcome_artifacts(report, tmp_path / "output" / "governance" / "2026-04-30")

    assert paths["json"].name == "p36_recommendation_outcomes.json"
    assert paths["md"].name == "p36_recommendation_outcomes.md"
    assert paths["json"].exists()
    assert paths["md"].exists()
    assert "does not approve production adoption" in paths["md"].read_text()


def test_p36_hard_boundaries_are_explicit():
    from agent.research_v1 import recommendation_outcomes as p36

    forbidden_names = {
        "broker",
        "order",
        "scheduler",
        "notification",
        "train_model",
        "run_governance_runtime",
    }
    module_names = set(p36.__dict__)

    assert not (forbidden_names & module_names)
    assert "output/governance" in p36.P36_ARTIFACT_DISCLAIMER or "governance" in p36.P36_ARTIFACT_DISCLAIMER
```

- [ ] **Step 2: Add CLI tests**

Append to `tests/agent/research_v1/test_batch_cli.py`:

```python
def test_outcome_run_cli_success_writes_p36_artifacts(tmp_path, monkeypatch, capsys):
    from agent.research_v1.batch_cli import main

    app_root = tmp_path / "app"
    app_root.mkdir()

    def fake_run(**kwargs):
        output_dir = kwargs["output_root"] / "2026-04-30"
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "p36_recommendation_outcomes.json").write_text("{}", encoding="utf-8")
        (output_dir / "p36_recommendation_outcomes.md").write_text("# P36", encoding="utf-8")
        return {
            "status": "completed",
            "output_dir": str(output_dir),
            "outcome_rows_written": 1,
            "duplicate_rows_skipped": 0,
            "warnings": [],
        }

    monkeypatch.setattr("agent.research_v1.batch_cli.run_recommendation_outcome_tracking", fake_run)

    code = main([
        "--app-root", str(app_root),
        "outcome-run",
        "--as-of-date", "2026-04-30",
        "--limit", "10",
        "--flat-cost-bps", "0",
    ])

    out = capsys.readouterr().out
    assert code == 0
    assert "Outcome tracking status: completed" in out
    assert str(app_root / "output" / "governance" / "2026-04-30") in out


def test_outcome_run_cli_rejects_negative_limit(tmp_path, capsys):
    from agent.research_v1.batch_cli import main

    app_root = tmp_path / "app"
    app_root.mkdir()

    code = main([
        "--app-root", str(app_root),
        "outcome-run",
        "--as-of-date", "2026-04-30",
        "--limit", "-1",
    ])

    assert code == 2
    assert "invalid outcome-run input" in capsys.readouterr().out
```

- [ ] **Step 3: Run tests and confirm failure**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_recommendation_outcomes.py tests/agent/research_v1/test_batch_cli.py -q
```

Expected: fail because artifact writer and CLI command are not complete.

- [ ] **Step 4: Implement artifact writer and CLI**

In `recommendation_outcomes.py`, implement:

```python
P36_ARTIFACT_DISCLAIMER = (
    "P36 is recommendation outcome tracking only. It does not approve production "
    "adoption, instruct trades, place orders, train models, schedule jobs, or "
    "mutate production configuration. Artifacts are written under output/governance."
)
```

`write_recommendation_outcome_artifacts(report, output_dir)` must write:

```text
p36_recommendation_outcomes.json
p36_recommendation_outcomes.md
```

In `batch_cli.py`, add an `outcome-run` subcommand with:

```text
--as-of-date
--output-root
--limit
--flat-cost-bps
```

Resolve relative `--output-root` under `--app-root`, matching `governance-run`.

Print:

```text
Outcome tracking status: <status>
Output dir: <path>
Outcome rows written: <n>
Duplicate rows skipped: <n>
Warning: <warning>
```

Return `2` for invalid limit, invalid date, or negative flat cost. Return `0` otherwise.

- [ ] **Step 5: Run CLI and artifact tests**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_recommendation_outcomes.py tests/agent/research_v1/test_batch_cli.py -q
```

Expected: P36 tests pass and existing batch CLI tests remain green except any known host-level PDF browser dependency outside P36.

- [ ] **Step 6: Commit P36-C**

Run:

```bash
git add agent/research_v1/recommendation_outcomes.py agent/research_v1/batch_cli.py tests/agent/research_v1/test_recommendation_outcomes.py tests/agent/research_v1/test_batch_cli.py
git commit -m "feat: add recommendation outcome cli"
```

---

### Task 4: P36-D Docs + Regression

**Files:**
- Modify: `README.md`
- Modify: `agent/research_v1/README.md`

- [ ] **Step 1: Update root README**

Add P36 to the root `README.md` current-version section:

```markdown
### P36 Recommendation Outcome Tracking

P36 adds standalone canonical outcome tracking. It reads prior canonical recommendations, resolves the boss-facing action from canonical reports, evaluates eligible `Buy Stock` and `Buy Call` recommendations against forward market data, and writes `p36_recommendation_outcomes.{json,md}` under `output/governance/YYYY-MM-DD/`.

P36 is not a broker, scheduler, backtester, model trainer, production approver, or P35 runtime extension. It is an append-only audit loop with natural-key idempotence over `(signal_id, horizon_days, evaluated_for_date, data_source_hash)`.
```

- [ ] **Step 2: Update research README Data Flow**

In `agent/research_v1/README.md`, add:

```markdown
#### P36 Outcome Tracking

`recommendation_outcomes.py` consumes canonical signals and canonical reports after research has completed. It persists forward outcome rows in `canonical_recommendation_outcomes`, then emits standalone P36 artifacts under `output/governance/YYYY-MM-DD/`. The flow is one-way and read-only with respect to research decisions: outcomes do not alter `final_judge`, `RoleWeightConfig`, P33 edge review, P35 runtime, or production configuration in P36.
```

- [ ] **Step 3: Run focused verification**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_recommendation_outcomes.py -q
```

Expected: all P36 tests pass.

- [ ] **Step 4: Run governance-adjacent regression**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest \
  tests/agent/research_v1/test_governance_runtime.py \
  tests/agent/research_v1/test_signal_family_edge_review.py \
  tests/agent/research_v1/test_evidence_generation_dry_run.py \
  tests/agent/research_v1/test_boss_governance_brief.py \
  -q
```

Expected: all selected governance tests pass.

- [ ] **Step 5: Run doc standards**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_doc_standards.py -q
```

Expected: doc standards pass.

- [ ] **Step 6: Run P20-P36 chain when host dependencies permit**

Run the existing full P20-P35 command from `README.md`, adding:

```text
tests/agent/research_v1/test_recommendation_outcomes.py
```

Expected: full chain passes, except any explicitly documented host-only PDF browser dependency unrelated to P36.

- [ ] **Step 7: Commit P36-D**

Run:

```bash
git add README.md agent/research_v1/README.md
git commit -m "docs: document p36 recommendation outcomes"
```

---

## Final Review Checklist

- [ ] P36 focused tests pass.
- [ ] Governance-adjacent regression passes.
- [ ] Doc standards pass.
- [ ] `outcome-run` writes `p36_recommendation_outcomes.json`.
- [ ] `outcome-run` writes `p36_recommendation_outcomes.md`.
- [ ] Rerun with same `(signal_id, horizon_days, evaluated_for_date, data_source_hash)` does not duplicate rows.
- [ ] Rerun with revised `data_source_hash` appends a distinguishable row.
- [ ] P36 does not call broker/order APIs.
- [ ] P36 does not create scheduler or notification behavior.
- [ ] P36 does not mutate production config.
- [ ] P36 does not train models.
- [ ] P36 does not invoke or alter P35 runtime.
- [ ] P36 does not feed P33 edge review, `RoleWeightConfig`, or `JudgeInputPacket`.

## Executor Report Format

When implementation finishes, report:

```text
P36 Implementation Complete

Status Summary
Phase   Status   Commit
P36-A   PASS     <commit>
P36-B   PASS     <commit>
P36-C   PASS     <commit>
P36-D   PASS     <commit>

Verification
- P36 focused: <result>
- Governance-adjacent regression: <result>
- Doc standards: <result>
- Full P20-P36 chain: <result or environment note>

Files Changed
- <path>

Hard Boundary Compliance
- no auto-trading
- no broker orders
- no production adoption approval
- no production config mutation
- no shadow promotion
- no model training
- no scheduling or notifications
- no P35 runtime wiring

Known Risks
- <only real residual risks>
```
