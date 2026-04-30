# P37 Market Regime Context Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone daily market-regime context layer so Hermes can produce auditable top-down market evidence without changing ticker recommendations or trading behavior.

**Architecture:** Add a focused `market_regime_context.py` module for proxy history normalization, deterministic metrics, rule-based regime classification, artifact writing, and run orchestration. Extend `ResearchDatabase` with append-only market-regime snapshot persistence, then expose a local `market-regime-run` CLI command that writes P37 artifacts under `output/governance/YYYY-MM-DD/`.

**Tech Stack:** Python 3.11, dataclasses, sqlite3, pathlib, json, hashlib, datetime, statistics, argparse, pytest, existing Futu history provider, fake providers in tests.

---

## File Structure

- Create `agent/research_v1/market_regime_context.py`
  - P37 constants, default proxy universe, normalized history rows, metric computation, regime classification, confidence scoring, deterministic source hashing, artifact writing, and run orchestration.
- Modify `agent/research_v1/data/database.py`
  - Add market-regime snapshot schema and persistence/query methods.
- Modify `agent/research_v1/batch_cli.py`
  - Add `market-regime-run`.
- Create `tests/agent/research_v1/test_market_regime_context.py`
  - Focused P37 metric, classification, persistence, artifact, CLI-adjacent, and hard-boundary tests.
- Modify `tests/agent/research_v1/test_batch_cli.py`
  - Add CLI tests for `market-regime-run`.
- Modify `README.md` and `agent/research_v1/README.md`
  - Document P37 as standalone market-context evidence.

Do not modify `final_judge`, `RoleWeightConfig`, `JudgeInputPacket`, P35 runtime, or P36 outcome tracking in this phase.

## Constants

Use these exact constants in `agent/research_v1/market_regime_context.py`:

```python
P37_SCHEMA_VERSION = "p37_market_regime_snapshot.1"

P37_STATUS_COMPLETED = "completed"
P37_STATUS_COMPLETED_WITH_WARNINGS = "completed_with_warnings"
P37_STATUS_DEGRADED_MISSING_INPUTS = "degraded_missing_inputs"

REGIME_RISK_ON_BROAD = "risk_on_broad"
REGIME_RISK_ON_NARROW = "risk_on_narrow"
REGIME_RISK_OFF = "risk_off"
REGIME_HIGH_VOLATILITY = "high_volatility"
REGIME_RANGE_BOUND = "range_bound"
REGIME_DEGRADED_UNKNOWN = "degraded_unknown"

P37_DEFAULT_LOOKBACK_DAYS = 90

P37_ARTIFACT_DISCLAIMER = (
    "P37 is market-context evidence only. It does not approve production "
    "adoption, change recommendations, instruct trades, place orders, train "
    "models, schedule jobs, or mutate production configuration."
)
```

Default proxy universe:

```python
DEFAULT_MARKET_PROXIES = {
    "SPY": "us_equity_large_cap",
    "QQQ": "us_growth",
    "IWM": "us_small_cap",
    "VIX": "volatility_proxy",
    "TLT": "duration_rates_proxy",
    "HYG": "high_yield_credit_proxy",
    "LQD": "investment_grade_credit_proxy",
    "UUP": "dollar_proxy",
    "XLK": "technology",
    "XLF": "financials",
    "XLY": "consumer_discretionary",
    "XLP": "consumer_staples",
    "XLE": "energy",
    "XLV": "healthcare",
    "XLI": "industrials",
    "XLU": "utilities",
    "XLB": "materials",
    "XLC": "communication_services",
    "XLRE": "real_estate",
}

SECTOR_PROXY_SYMBOLS = frozenset({
    "XLK", "XLF", "XLY", "XLP", "XLE", "XLV", "XLI", "XLU", "XLB", "XLC", "XLRE",
})
```

---

### Task 1: P37-A Market Regime Metrics + Classification

**Files:**
- Create: `agent/research_v1/market_regime_context.py`
- Create: `tests/agent/research_v1/test_market_regime_context.py`

- [ ] **Step 1: Write failing metric tests**

Create `tests/agent/research_v1/test_market_regime_context.py`:

```python
"""Tests for P37 market regime context."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from agent.research_v1.market_regime_context import (
    DEFAULT_MARKET_PROXIES,
    build_market_regime_snapshot,
    compute_data_source_hash,
    compute_proxy_metrics,
    normalize_history_rows,
)


class FakeMarketProvider:
    data_source = "fake_market_provider"
    price_adjustment = "adjusted"

    def __init__(self, histories: dict[str, list[dict]]):
        self.histories = histories
        self.calls: list[tuple[str, date, date]] = []

    def fetch_history(self, symbol, start_date, end_date):
        self.calls.append((symbol, start_date, end_date))
        return self.histories.get(symbol, [])


def _history(start_price: float, days: int = 90, daily_step: float = 1.0) -> list[dict]:
    start = date(2026, 1, 1)
    rows = []
    for idx in range(days):
        close = start_price + idx * daily_step
        rows.append({
            "date": str(start + timedelta(days=idx)),
            "open": close - 0.25,
            "high": close + 0.50,
            "low": close - 0.50,
            "close": close,
            "volume": 1_000_000 + idx,
            "price_adjustment": "adjusted",
        })
    return rows


def _histories(step: float = 1.0) -> dict[str, list[dict]]:
    return {symbol: _history(100.0 + i, daily_step=step) for i, symbol in enumerate(DEFAULT_MARKET_PROXIES)}


def test_proxy_metrics_compute_returns_vol_drawdown_and_sma_flags():
    rows = normalize_history_rows(_history(100.0, days=90, daily_step=1.0))
    metrics = compute_proxy_metrics("SPY", "us_equity_large_cap", rows)

    assert metrics["symbol"] == "SPY"
    assert metrics["return_1d"] > 0
    assert metrics["return_5d"] > 0
    assert metrics["return_20d"] > 0
    assert metrics["realized_vol_20d"] >= 0
    assert metrics["drawdown_20d"] <= 0
    assert metrics["above_sma_20"] is True
    assert metrics["above_sma_50"] is True


def test_data_source_hash_is_deterministic():
    histories = _histories()
    first = compute_data_source_hash(histories)
    second = compute_data_source_hash(dict(reversed(list(histories.items()))))

    assert first == second
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_market_regime_context.py -q
```

Expected: fail because `market_regime_context.py` does not exist.

- [ ] **Step 3: Implement metric helpers**

Create `agent/research_v1/market_regime_context.py` with:

```python
from __future__ import annotations

import hashlib
import json
import math
import statistics
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

P37_SCHEMA_VERSION = "p37_market_regime_snapshot.1"
P37_STATUS_COMPLETED = "completed"
P37_STATUS_COMPLETED_WITH_WARNINGS = "completed_with_warnings"
P37_STATUS_DEGRADED_MISSING_INPUTS = "degraded_missing_inputs"

REGIME_RISK_ON_BROAD = "risk_on_broad"
REGIME_RISK_ON_NARROW = "risk_on_narrow"
REGIME_RISK_OFF = "risk_off"
REGIME_HIGH_VOLATILITY = "high_volatility"
REGIME_RANGE_BOUND = "range_bound"
REGIME_DEGRADED_UNKNOWN = "degraded_unknown"

P37_DEFAULT_LOOKBACK_DAYS = 90
P37_ARTIFACT_DISCLAIMER = (
    "P37 is market-context evidence only. It does not approve production "
    "adoption, change recommendations, instruct trades, place orders, train "
    "models, schedule jobs, or mutate production configuration."
)
```

Implement:

```python
def normalize_history_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = []
    for row in rows:
        if row.get("close") is None or not row.get("date"):
            continue
        normalized.append({
            "date": str(row["date"]),
            "open": row.get("open"),
            "high": row.get("high"),
            "low": row.get("low"),
            "close": float(row["close"]),
            "volume": row.get("volume"),
            "price_adjustment": row.get("price_adjustment", "unknown"),
        })
    normalized.sort(key=lambda r: r["date"])
    return normalized
```

Implement deterministic returns, realized volatility over percentage returns, drawdown over closing prices, and SMA flags. If there is not enough data for a metric, return `None` for that metric.

- [ ] **Step 4: Add classification tests**

Append tests:

```python
def test_risk_on_broad_classification_from_positive_broad_market():
    provider = FakeMarketProvider(_histories(step=1.0))
    snapshot = build_market_regime_snapshot(provider, as_of_date=date(2026, 4, 30))

    assert snapshot["regime_label"] == "risk_on_broad"
    assert snapshot["coverage_ratio"] == 1.0
    assert snapshot["confidence"] > 0.5
    assert snapshot["classification_reasons"]


def test_degraded_when_required_inputs_missing():
    histories = _histories(step=1.0)
    histories["SPY"] = []
    provider = FakeMarketProvider(histories)

    snapshot = build_market_regime_snapshot(provider, as_of_date=date(2026, 4, 30))

    assert snapshot["status"] == "degraded_missing_inputs"
    assert snapshot["regime_label"] == "degraded_unknown"
    assert "SPY" in snapshot["missing_symbols"]


def test_sector_rotation_ranks_relative_strength_against_spy():
    histories = _histories(step=0.2)
    histories["XLK"] = _history(100.0, daily_step=2.0)
    histories["XLP"] = _history(100.0, daily_step=-0.1)
    provider = FakeMarketProvider(histories)

    snapshot = build_market_regime_snapshot(provider, as_of_date=date(2026, 4, 30))

    ranked = snapshot["sector_rotation"]["ranked_sectors"]
    assert ranked[0]["symbol"] == "XLK"
    assert ranked[-1]["symbol"] == "XLP"
```

- [ ] **Step 5: Implement snapshot builder**

`build_market_regime_snapshot(provider, as_of_date, lookback_days=90, proxy_universe=None)` must:

- fetch all symbols in `DEFAULT_MARKET_PROXIES`
- normalize histories
- compute proxy metrics
- compute breadth metrics
- compute risk appetite metrics
- rank sector relative strength versus SPY
- classify regime with rule-based logic
- compute confidence
- return a dict with all required artifact fields
- never call broker, scheduler, training, P35, P36, or `final_judge`

- [ ] **Step 6: Run focused tests**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_market_regime_context.py -q
```

Expected: metric and classification tests pass.

- [ ] **Step 7: Commit P37-A**

Run:

```bash
git add agent/research_v1/market_regime_context.py tests/agent/research_v1/test_market_regime_context.py
git commit -m "feat: add market regime snapshot metrics"
```

---

### Task 2: P37-B Persistence + Artifacts

**Files:**
- Modify: `agent/research_v1/data/database.py`
- Modify: `agent/research_v1/market_regime_context.py`
- Modify: `tests/agent/research_v1/test_market_regime_context.py`

- [ ] **Step 1: Add failing persistence and artifact tests**

Append:

```python
from agent.research_v1.data.database import ResearchDatabase
from agent.research_v1.market_regime_context import write_market_regime_artifacts


def _db(tmp_path: Path) -> ResearchDatabase:
    db = ResearchDatabase(str(tmp_path / "research.db"))
    db.initialize()
    db.initialize_market_regime_schema()
    return db


def test_market_regime_snapshot_persistence_is_idempotent(tmp_path: Path):
    db = _db(tmp_path)
    snapshot = build_market_regime_snapshot(FakeMarketProvider(_histories()), as_of_date=date(2026, 4, 30))

    first = db.save_market_regime_snapshot(snapshot)
    second = db.save_market_regime_snapshot(snapshot)
    rows = db.list_market_regime_snapshots(as_of_date="2026-04-30")

    assert first == second
    assert len(rows) == 1


def test_revised_market_regime_hash_appends(tmp_path: Path):
    db = _db(tmp_path)
    first_snapshot = build_market_regime_snapshot(FakeMarketProvider(_histories(step=1.0)), as_of_date=date(2026, 4, 30))
    second_snapshot = build_market_regime_snapshot(FakeMarketProvider(_histories(step=2.0)), as_of_date=date(2026, 4, 30))

    first = db.save_market_regime_snapshot(first_snapshot)
    second = db.save_market_regime_snapshot(second_snapshot)
    rows = db.list_market_regime_snapshots(as_of_date="2026-04-30")

    assert first != second
    assert len(rows) == 2


def test_market_regime_artifact_writer_outputs_json_and_markdown(tmp_path: Path):
    snapshot = build_market_regime_snapshot(FakeMarketProvider(_histories()), as_of_date=date(2026, 4, 30))

    paths = write_market_regime_artifacts(snapshot, tmp_path / "output" / "governance" / "2026-04-30")

    assert paths["json"].name == "p37_market_regime_snapshot.json"
    assert paths["md"].name == "p37_market_regime_snapshot.md"
    assert paths["json"].exists()
    assert paths["md"].exists()
    assert "P37 is market-context evidence only" in paths["md"].read_text()
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_market_regime_context.py -q
```

Expected: fail because DB methods and artifact writer do not exist.

- [ ] **Step 3: Implement DB methods**

Add to `ResearchDatabase`:

```python
def initialize_market_regime_schema(self) -> None:
    ...

def save_market_regime_snapshot(self, snapshot: dict) -> str:
    ...

def list_market_regime_snapshots(self, as_of_date: str | None = None, limit: int = 20) -> list[dict]:
    ...
```

Schema table:

```sql
CREATE TABLE IF NOT EXISTS market_regime_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    schema_version TEXT NOT NULL,
    as_of_date TEXT NOT NULL,
    created_at TEXT NOT NULL,
    regime_label TEXT NOT NULL,
    confidence REAL NOT NULL,
    coverage_ratio REAL NOT NULL,
    summary_json TEXT NOT NULL,
    metrics_json TEXT NOT NULL,
    proxy_metrics_json TEXT NOT NULL,
    sector_rotation_json TEXT NOT NULL,
    classification_reasons_json TEXT NOT NULL,
    warnings_json TEXT NOT NULL,
    missing_symbols_json TEXT NOT NULL,
    stale_symbols_json TEXT NOT NULL,
    data_source_hash TEXT NOT NULL,
    UNIQUE(as_of_date, data_source_hash)
)
```

`snapshot_id` must be deterministic from `(as_of_date, data_source_hash)`.

- [ ] **Step 4: Implement artifact writer**

`write_market_regime_artifacts(snapshot, output_dir)` writes:

```text
p37_market_regime_snapshot.json
p37_market_regime_snapshot.md
```

Markdown must lead with regime label, confidence, reasons, disclaimer, breadth, and sector rotation.

- [ ] **Step 5: Run tests**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_market_regime_context.py -q
```

Expected: all current P37 tests pass.

- [ ] **Step 6: Commit P37-B**

Run:

```bash
git add agent/research_v1/data/database.py agent/research_v1/market_regime_context.py tests/agent/research_v1/test_market_regime_context.py
git commit -m "feat: persist market regime snapshots"
```

---

### Task 3: P37-C CLI

**Files:**
- Modify: `agent/research_v1/batch_cli.py`
- Modify: `tests/agent/research_v1/test_batch_cli.py`
- Modify: `tests/agent/research_v1/test_market_regime_context.py`

- [ ] **Step 1: Add CLI tests**

Append to `tests/agent/research_v1/test_batch_cli.py`:

```python
def test_market_regime_run_cli_success_writes_artifacts(tmp_path, monkeypatch, capsys):
    from agent.research_v1.batch_cli import main

    app_root = tmp_path / "app"
    app_root.mkdir()

    def fake_run(**kwargs):
        output_dir = kwargs["output_root"] / "2026-04-30"
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "p37_market_regime_snapshot.json").write_text("{}", encoding="utf-8")
        (output_dir / "p37_market_regime_snapshot.md").write_text("# P37", encoding="utf-8")
        return {
            "status": "completed",
            "output_dir": str(output_dir),
            "regime_label": "risk_on_broad",
            "confidence": 0.82,
            "missing_symbols": [],
            "warnings": [],
        }

    monkeypatch.setattr("agent.research_v1.batch_cli.run_market_regime_context", fake_run)

    code = main([
        "--app-root", str(app_root),
        "market-regime-run",
        "--as-of-date", "2026-04-30",
        "--lookback-days", "90",
    ])

    out = capsys.readouterr().out
    assert code == 0
    assert "Market regime status: completed" in out
    assert "risk_on_broad" in out
    assert str(app_root / "output" / "governance" / "2026-04-30") in out


def test_market_regime_run_cli_rejects_invalid_inputs(tmp_path, capsys):
    from agent.research_v1.batch_cli import main

    app_root = tmp_path / "app"
    app_root.mkdir()

    code = main([
        "--app-root", str(app_root),
        "market-regime-run",
        "--as-of-date", "bad-date",
        "--lookback-days", "-1",
    ])

    assert code == 2
    assert "invalid market-regime-run input" in capsys.readouterr().out
```

- [ ] **Step 2: Add hard-boundary test**

Append to `tests/agent/research_v1/test_market_regime_context.py`:

```python
def test_p37_hard_boundaries_are_explicit():
    from agent.research_v1 import market_regime_context as p37

    forbidden_names = {
        "broker",
        "order",
        "train_model",
        "scheduler",
        "notification",
        "final_judge",
        "run_governance_runtime",
        "run_recommendation_outcome_tracking",
    }

    assert not (forbidden_names & set(p37.__dict__))
    assert "does not approve production" in p37.P37_ARTIFACT_DISCLAIMER
```

- [ ] **Step 3: Run tests and confirm failure**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_market_regime_context.py tests/agent/research_v1/test_batch_cli.py -q
```

Expected: fail because CLI is not wired.

- [ ] **Step 4: Implement run orchestration and CLI**

In `market_regime_context.py`, implement:

```python
def run_market_regime_context(
    db,
    as_of_date: date,
    lookback_days: int = P37_DEFAULT_LOOKBACK_DAYS,
    output_root: Path | None = None,
    provider: Any | None = None,
) -> dict:
    ...
```

Default provider should use `FutuQuoteClient` through a small `_FutuMarketProvider`, but tests must be able to inject fake providers.

In `batch_cli.py`, add `market-regime-run` with:

```text
--as-of-date
--lookback-days
--output-root
```

Print:

```text
Market regime status: <status>
Output dir: <path>
Regime label: <label>
Confidence: <value>
Missing symbols: <count>
Warning: <warning>
```

Return `2` for invalid date or non-positive lookback.

- [ ] **Step 5: Run CLI tests**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_market_regime_context.py tests/agent/research_v1/test_batch_cli.py -q
```

Expected: P37 focused and relevant batch CLI tests pass, aside from any existing host-only PDF browser dependency outside P37.

- [ ] **Step 6: Commit P37-C**

Run:

```bash
git add agent/research_v1/market_regime_context.py agent/research_v1/batch_cli.py tests/agent/research_v1/test_market_regime_context.py tests/agent/research_v1/test_batch_cli.py
git commit -m "feat: add market regime cli"
```

---

### Task 4: P37-D Docs + Regression

**Files:**
- Modify: `README.md`
- Modify: `agent/research_v1/README.md`

- [ ] **Step 1: Update root README**

Add P37 to the current-version/system map:

```markdown
### P37 Market Regime Context

P37 adds standalone daily market-regime context. It computes index trend, volatility, breadth, risk appetite, and sector rotation from market proxy histories, persists append-only `market_regime_snapshots`, and writes `p37_market_regime_snapshot.{json,md}` under `output/governance/YYYY-MM-DD/`.

P37 is context evidence only. It does not change ticker recommendations, call `final_judge`, train models, schedule jobs, send notifications, place trades, or approve production adoption.
```

- [ ] **Step 2: Update research README Data Flow**

In `agent/research_v1/README.md`, add:

```markdown
#### P37 Market Regime Context

`market_regime_context.py` consumes market proxy histories and emits a standalone market-regime snapshot. The flow is one-way: market context is persisted and written to artifacts, but it does not alter `final_judge`, `RoleWeightConfig`, `JudgeInputPacket`, P35 governance runtime, P36 outcome tracking, or production configuration in P37.
```

- [ ] **Step 3: Run focused verification**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_market_regime_context.py -q
```

Expected: all P37 tests pass.

- [ ] **Step 4: Run P36 focused regression**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_recommendation_outcomes.py -q
```

Expected: P36 remains green.

- [ ] **Step 5: Run governance-adjacent regression**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest \
  tests/agent/research_v1/test_governance_runtime.py \
  tests/agent/research_v1/test_signal_family_edge_review.py \
  tests/agent/research_v1/test_evidence_generation_dry_run.py \
  tests/agent/research_v1/test_boss_governance_brief.py \
  -q
```

Expected: governance-adjacent tests pass.

- [ ] **Step 6: Run doc standards**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_doc_standards.py -q
```

Expected: doc standards pass.

- [ ] **Step 7: Run full chain when host dependencies permit**

Run the existing full P20-P36 command from `README.md`, adding:

```text
tests/agent/research_v1/test_market_regime_context.py
```

Expected: full chain passes, except any explicitly documented host-only PDF browser dependency unrelated to P37.

- [ ] **Step 8: Commit P37-D**

Run:

```bash
git add README.md agent/research_v1/README.md
git commit -m "docs: document p37 market regime context"
```

---

## Final Review Checklist

- [ ] P37 focused tests pass.
- [ ] P36 focused tests pass.
- [ ] Governance-adjacent regression passes.
- [ ] Doc standards pass.
- [ ] `market-regime-run` writes `p37_market_regime_snapshot.json`.
- [ ] `market-regime-run` writes `p37_market_regime_snapshot.md`.
- [ ] Rerun with same `(as_of_date, data_source_hash)` does not duplicate rows.
- [ ] Rerun with revised source data appends a distinguishable row.
- [ ] P37 does not call broker/order APIs.
- [ ] P37 does not train models.
- [ ] P37 does not schedule jobs or send notifications.
- [ ] P37 does not mutate production config.
- [ ] P37 does not call `final_judge`.
- [ ] P37 does not call P35 runtime.
- [ ] P37 does not call P36 outcome tracking.
- [ ] P37 does not change ticker recommendations.

## Executor Report Format

When implementation finishes, report:

```text
P37 Implementation Complete

Status Summary
Phase   Status   Commit
P37-A   PASS     <commit>
P37-B   PASS     <commit>
P37-C   PASS     <commit>
P37-D   PASS     <commit>

Verification
- P37 focused: <result>
- P36 focused regression: <result>
- Governance-adjacent regression: <result>
- Doc standards: <result>
- Full P20-P37 chain: <result or environment note>

Files Changed
- <path>

Hard Boundary Compliance
- no auto-trading
- no broker orders
- no production adoption approval
- no production config mutation
- no model training
- no scheduling or notifications
- no final_judge changes
- no P35 runtime wiring
- no P36 outcome tracking mutation

Known Risks
- <only real residual risks>
```
