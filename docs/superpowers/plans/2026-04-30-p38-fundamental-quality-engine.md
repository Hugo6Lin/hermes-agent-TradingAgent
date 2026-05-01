# P38 Fundamental Quality Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone deterministic fundamental-quality engine so Hermes can score business quality from point-in-time financial rows without changing ticker recommendations.

**Architecture:** Add a focused `fundamental_quality.py` module for financial-row normalization, source-date integrity, deterministic metrics, dimension scoring, report building, artifact writing, and run orchestration. Extend `ResearchDatabase` with append-only fundamental-quality persistence, then expose a local `fundamental-quality-run` CLI command that reads a JSON input file and writes P38 artifacts under `output/governance/YYYY-MM-DD/`.

**Tech Stack:** Python 3.11, dataclasses, sqlite3, pathlib, json, hashlib, datetime, statistics, argparse, pytest, local JSON fixtures.

---

## File Structure

- Create `agent/research_v1/fundamental_quality.py`
  - P38 constants, input normalization, source-date integrity, metric computation, dimension scoring, label assignment, source hashing, artifact writing, and run orchestration.
- Modify `agent/research_v1/data/database.py`
  - Add fundamental-quality report schema and persistence/query methods.
- Modify `agent/research_v1/batch_cli.py`
  - Add `fundamental-quality-run`.
- Create `tests/agent/research_v1/test_fundamental_quality.py`
  - Focused P38 metric, scoring, source-integrity, persistence, artifact, CLI-adjacent, and hard-boundary tests.
- Modify `tests/agent/research_v1/test_batch_cli.py`
  - Add CLI tests for `fundamental-quality-run`.
- Modify `README.md` and `agent/research_v1/README.md`
  - Document P38 as standalone fundamental-quality evidence.

Do not modify `final_judge`, `RoleWeightConfig`, `JudgeInputPacket`, `_extract_thesis_inputs()`, `ThesisEngine`, P35 runtime, P36 outcome tracking, or P37 market-regime context in this phase.

## Constants

Use these exact constants in `agent/research_v1/fundamental_quality.py`:

```python
P38_SCHEMA_VERSION = "p38_fundamental_quality.1"

P38_STATUS_COMPLETED = "completed"
P38_STATUS_COMPLETED_WITH_WARNINGS = "completed_with_warnings"
P38_STATUS_DEGRADED_INSUFFICIENT_HISTORY = "degraded_insufficient_history"
P38_STATUS_BLOCKED_MISSING_FUNDAMENTALS = "blocked_missing_fundamentals"

QUALITY_COMPOUNDER = "compounder_quality"
QUALITY_SOLID = "solid_quality"
QUALITY_WATCHLIST = "watchlist_quality"
QUALITY_LOW = "low_quality"
QUALITY_BLOCKED = "blocked_missing_fundamentals"

P38_ARTIFACT_DISCLAIMER = (
    "P38 is fundamental-quality evidence only. It does not approve production "
    "adoption, change recommendations, instruct trades, place orders, train "
    "models, schedule jobs, or mutate production configuration."
)
```

Required input fields:

```python
P38_REQUIRED_ROW_FIELDS = (
    "period_end",
    "source_date",
    "revenue",
    "gross_profit",
    "operating_income",
    "net_income",
    "cfo",
    "capex",
    "total_debt",
    "cash_and_equivalents",
    "shareholders_equity",
    "shares_outstanding",
)
```

Dimension weights:

```python
P38_DIMENSION_WEIGHTS = {
    "profitability_score": 0.25,
    "growth_quality_score": 0.20,
    "cash_conversion_score": 0.20,
    "balance_sheet_score": 0.15,
    "dilution_score": 0.10,
    "stability_score": 0.10,
}
```

---

### Task 1: P38-A Metrics + Scoring

**Files:**
- Create: `agent/research_v1/fundamental_quality.py`
- Create: `tests/agent/research_v1/test_fundamental_quality.py`

- [ ] **Step 1: Write failing metric tests**

Create `tests/agent/research_v1/test_fundamental_quality.py`:

```python
"""Tests for P38 fundamental quality engine."""

from __future__ import annotations

from pathlib import Path

from agent.research_v1.fundamental_quality import (
    P38_SCHEMA_VERSION,
    build_fundamental_quality_report,
    compute_source_hash,
    normalize_financial_rows,
)


def _row(
    period_end: str,
    source_date: str,
    revenue: float = 100.0,
    gross_profit: float = 50.0,
    operating_income: float = 25.0,
    net_income: float = 20.0,
    cfo: float = 24.0,
    capex: float = -5.0,
    total_debt: float = 20.0,
    cash: float = 10.0,
    equity: float = 80.0,
    shares: float = 10.0,
    eps: float = 2.0,
    ebit: float = 25.0,
) -> dict:
    return {
        "period_end": period_end,
        "filing_date": source_date,
        "source_date": source_date,
        "revenue": revenue,
        "gross_profit": gross_profit,
        "operating_income": operating_income,
        "net_income": net_income,
        "cfo": cfo,
        "capex": capex,
        "free_cash_flow": cfo + capex,
        "total_debt": total_debt,
        "cash_and_equivalents": cash,
        "shareholders_equity": equity,
        "shares_outstanding": shares,
        "eps": eps,
        "ebit": ebit,
        "current_assets": 50.0,
        "current_liabilities": 25.0,
    }


def _rows() -> list[dict]:
    return [
        _row("2025-03-31", "2025-05-01", revenue=100.0, gross_profit=48.0, operating_income=22.0, net_income=18.0, cfo=22.0, eps=1.8),
        _row("2025-06-30", "2025-08-01", revenue=110.0, gross_profit=54.0, operating_income=26.0, net_income=21.0, cfo=25.0, eps=2.1),
        _row("2025-09-30", "2025-11-01", revenue=120.0, gross_profit=60.0, operating_income=30.0, net_income=24.0, cfo=29.0, eps=2.4),
        _row("2025-12-31", "2026-02-01", revenue=132.0, gross_profit=67.0, operating_income=34.0, net_income=27.0, cfo=33.0, eps=2.7),
        _row("2026-03-31", "2026-04-25", revenue=145.0, gross_profit=75.0, operating_income=39.0, net_income=31.0, cfo=38.0, eps=3.1),
    ]


def test_normalized_rows_compute_latest_margins_roic_leverage_and_fcf():
    normalized = normalize_financial_rows(_rows(), as_of_date="2026-04-30")

    assert len(normalized.usable_rows) == 5
    latest = normalized.usable_rows[-1]
    assert latest["gross_margin"] > 0
    assert latest["operating_margin"] > 0
    assert latest["net_margin"] > 0
    assert latest["roic"] > 0
    assert latest["debt_to_equity"] >= 0
    assert latest["free_cash_flow"] == latest["cfo"] + latest["capex"]


def test_report_computes_growth_scores_and_compounder_label():
    report = build_fundamental_quality_report({
        "ticker": "AAPL",
        "sector": "technology",
        "currency": "USD",
        "rows": _rows(),
    }, as_of_date="2026-04-30")

    assert report["schema_version"] == P38_SCHEMA_VERSION
    assert report["ticker"] == "AAPL"
    assert report["overall_quality_score"] >= 0.65
    assert report["quality_label"] in {"compounder_quality", "solid_quality"}
    assert report["dimension_scores"]["profitability_score"] > 0.5
    assert report["trend_metrics"]["revenue_growth_yoy"] is not None
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_fundamental_quality.py -q
```

Expected: fail because `fundamental_quality.py` does not exist.

- [ ] **Step 3: Implement normalization and metrics**

Create `agent/research_v1/fundamental_quality.py` with:

- constants from this plan
- `NormalizedFinancialRows` dataclass with `usable_rows`, `ignored_future_rows`, `warnings`, `missing_required_fields`
- `normalize_financial_rows(rows, as_of_date)`
- safe ratio helpers
- latest metric computation
- YoY trend metric computation

Rules:

- Ignore rows where `source_date > as_of_date`.
- Sort usable rows by `period_end`.
- Add derived `free_cash_flow = cfo + capex` when missing.
- Add `capex_sign_check` warning if capex is positive.
- Compute gross margin, operating margin, net margin, ROE, ROIC, FCF margin, FCF conversion, debt/equity, net debt/FCF, current ratio, and share count growth.

- [ ] **Step 4: Add source integrity and red flag tests**

Append:

```python
def test_future_source_rows_are_ignored_and_warned():
    rows = _rows() + [_row("2026-06-30", "2026-08-01", revenue=999.0)]
    report = build_fundamental_quality_report({
        "ticker": "AAPL",
        "sector": "technology",
        "currency": "USD",
        "rows": rows,
    }, as_of_date="2026-04-30")

    assert report["ignored_future_row_count"] == 1
    assert "future_source_date_ignored" in report["warnings"]
    assert report["latest_metrics"]["revenue"] != 999.0


def test_blocked_missing_fundamentals_when_fewer_than_two_usable_rows():
    report = build_fundamental_quality_report({
        "ticker": "AAPL",
        "sector": "technology",
        "currency": "USD",
        "rows": [_row("2025-03-31", "2025-05-01")],
    }, as_of_date="2026-04-30")

    assert report["status"] == "blocked_missing_fundamentals"
    assert report["quality_label"] == "blocked_missing_fundamentals"


def test_degraded_insufficient_history_with_two_or_three_rows():
    report = build_fundamental_quality_report({
        "ticker": "AAPL",
        "sector": "technology",
        "currency": "USD",
        "rows": _rows()[:3],
    }, as_of_date="2026-04-30")

    assert report["status"] == "degraded_insufficient_history"
    assert "insufficient_history" in report["red_flags"]


def test_high_dilution_leverage_and_negative_fcf_trigger_flags():
    rows = _rows()
    rows[-1]["shares_outstanding"] = 20.0
    rows[-1]["total_debt"] = 500.0
    rows[-1]["cfo"] = -10.0
    rows[-1]["capex"] = -5.0
    rows[-1].pop("free_cash_flow", None)

    report = build_fundamental_quality_report({
        "ticker": "DILUTE",
        "sector": "technology",
        "currency": "USD",
        "rows": rows,
    }, as_of_date="2026-04-30")

    assert "share_dilution_high" in report["red_flags"]
    assert "debt_to_equity_high" in report["red_flags"]
    assert "negative_fcf" in report["red_flags"]
    assert report["overall_quality_score"] < 0.8


def test_source_hash_changes_on_middle_row_revision():
    base = {"ticker": "AAPL", "sector": "technology", "currency": "USD", "rows": _rows()}
    revised = {"ticker": "AAPL", "sector": "technology", "currency": "USD", "rows": [dict(r) for r in _rows()]}
    revised["rows"][2]["revenue"] = 777.0

    assert compute_source_hash(base, "2026-04-30") != compute_source_hash(revised, "2026-04-30")
```

- [ ] **Step 5: Implement scoring and report builder**

Implement:

```python
def build_fundamental_quality_report(ticker_payload: dict, as_of_date: str) -> dict:
    ...
```

It must return all fields required by the spec, including:

- `schema_version`
- `as_of_date`
- `created_at`
- `ticker`
- `sector`
- `currency`
- `status`
- `quality_label`
- `overall_quality_score`
- `confidence`
- `coverage_ratio`
- `usable_row_count`
- `ignored_future_row_count`
- `dimension_scores`
- `latest_metrics`
- `trend_metrics`
- `red_flags`
- `warnings`
- `source_hash`
- `summary`

Use deterministic bounded scoring helpers. Keep formulas simple, documented, and non-configurable in P38.

- [ ] **Step 6: Run focused P38 tests**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_fundamental_quality.py -q
```

Expected: P38-A tests pass.

- [ ] **Step 7: Commit P38-A**

Run:

```bash
git add agent/research_v1/fundamental_quality.py tests/agent/research_v1/test_fundamental_quality.py
git commit -m "feat: add fundamental quality scoring"
```

---

### Task 2: P38-B Persistence + Artifacts

**Files:**
- Modify: `agent/research_v1/data/database.py`
- Modify: `agent/research_v1/fundamental_quality.py`
- Modify: `tests/agent/research_v1/test_fundamental_quality.py`

- [ ] **Step 1: Add failing persistence and artifact tests**

Append:

```python
from agent.research_v1.data.database import ResearchDatabase
from agent.research_v1.fundamental_quality import write_fundamental_quality_artifacts


def _db(tmp_path: Path) -> ResearchDatabase:
    db = ResearchDatabase(str(tmp_path / "research.db"))
    db.initialize()
    db.initialize_fundamental_quality_schema()
    return db


def test_fundamental_quality_persistence_is_idempotent(tmp_path: Path):
    db = _db(tmp_path)
    report = build_fundamental_quality_report({
        "ticker": "AAPL",
        "sector": "technology",
        "currency": "USD",
        "rows": _rows(),
    }, as_of_date="2026-04-30")

    first = db.save_fundamental_quality_report(report)
    second = db.save_fundamental_quality_report(report)
    rows = db.list_fundamental_quality_reports(ticker="AAPL", as_of_date="2026-04-30")

    assert first == second
    assert len(rows) == 1


def test_revised_fundamental_source_hash_appends(tmp_path: Path):
    db = _db(tmp_path)
    first_report = build_fundamental_quality_report({"ticker": "AAPL", "sector": "technology", "currency": "USD", "rows": _rows()}, "2026-04-30")
    revised_rows = _rows()
    revised_rows[2]["revenue"] = 777.0
    second_report = build_fundamental_quality_report({"ticker": "AAPL", "sector": "technology", "currency": "USD", "rows": revised_rows}, "2026-04-30")

    first = db.save_fundamental_quality_report(first_report)
    second = db.save_fundamental_quality_report(second_report)
    rows = db.list_fundamental_quality_reports(ticker="AAPL", as_of_date="2026-04-30")

    assert first != second
    assert len(rows) == 2


def test_fundamental_quality_artifacts_are_written(tmp_path: Path):
    report = build_fundamental_quality_report({"ticker": "AAPL", "sector": "technology", "currency": "USD", "rows": _rows()}, "2026-04-30")
    payload = {
        "schema_version": P38_SCHEMA_VERSION,
        "as_of_date": "2026-04-30",
        "created_at": report["created_at"],
        "status": "completed",
        "reports": [report],
        "summary": {"report_count": 1, "blocked_count": 0},
        "warnings": [],
        "disclaimer": "P38 is fundamental-quality evidence only. It does not approve production adoption, change recommendations, instruct trades, place orders, train models, schedule jobs, or mutate production configuration.",
    }

    paths = write_fundamental_quality_artifacts(payload, tmp_path / "output" / "governance" / "2026-04-30")

    assert paths["json"].name == "p38_fundamental_quality.json"
    assert paths["md"].name == "p38_fundamental_quality.md"
    assert paths["json"].exists()
    assert paths["md"].exists()
    assert "P38 is fundamental-quality evidence only" in paths["md"].read_text()
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_fundamental_quality.py -q
```

Expected: fail because DB methods and artifact writer do not exist.

- [ ] **Step 3: Implement DB methods**

Add to `ResearchDatabase`:

```python
def initialize_fundamental_quality_schema(self) -> None:
    ...

def save_fundamental_quality_report(self, report: dict) -> str:
    ...

def list_fundamental_quality_reports(
    self,
    ticker: str | None = None,
    as_of_date: str | None = None,
    limit: int = 20,
) -> list[dict]:
    ...
```

Schema table:

```sql
CREATE TABLE IF NOT EXISTS fundamental_quality_reports (
    report_id TEXT PRIMARY KEY,
    schema_version TEXT NOT NULL,
    as_of_date TEXT NOT NULL,
    created_at TEXT NOT NULL,
    ticker TEXT NOT NULL,
    sector TEXT,
    currency TEXT,
    status TEXT NOT NULL,
    quality_label TEXT NOT NULL,
    overall_quality_score REAL,
    confidence REAL NOT NULL,
    coverage_ratio REAL NOT NULL,
    usable_row_count INTEGER NOT NULL,
    ignored_future_row_count INTEGER NOT NULL,
    dimension_scores_json TEXT NOT NULL,
    latest_metrics_json TEXT NOT NULL,
    trend_metrics_json TEXT NOT NULL,
    red_flags_json TEXT NOT NULL,
    warnings_json TEXT NOT NULL,
    source_hash TEXT NOT NULL,
    summary TEXT NOT NULL,
    UNIQUE(ticker, as_of_date, source_hash)
)
```

`report_id` must be deterministic from `(ticker, as_of_date, source_hash)`.

- [ ] **Step 4: Implement artifact writer**

`write_fundamental_quality_artifacts(payload, output_dir)` writes:

```text
p38_fundamental_quality.json
p38_fundamental_quality.md
```

Markdown must lead with ticker summary table, quality labels, overall scores, red flags, dimension scores, and disclaimer.

- [ ] **Step 5: Run tests**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_fundamental_quality.py -q
```

Expected: all current P38 tests pass.

- [ ] **Step 6: Commit P38-B**

Run:

```bash
git add agent/research_v1/data/database.py agent/research_v1/fundamental_quality.py tests/agent/research_v1/test_fundamental_quality.py
git commit -m "feat: persist fundamental quality reports"
```

---

### Task 3: P38-C CLI

**Files:**
- Modify: `agent/research_v1/batch_cli.py`
- Modify: `tests/agent/research_v1/test_batch_cli.py`
- Modify: `agent/research_v1/fundamental_quality.py`
- Modify: `tests/agent/research_v1/test_fundamental_quality.py`

- [ ] **Step 1: Add run orchestration test**

Append:

```python
from agent.research_v1.fundamental_quality import run_fundamental_quality


def test_run_fundamental_quality_persists_and_writes_artifacts(tmp_path: Path):
    db = _db(tmp_path)
    input_payload = {
        "as_of_date": "2026-04-30",
        "source": "fixture",
        "tickers": [{"ticker": "AAPL", "sector": "technology", "currency": "USD", "rows": _rows()}],
    }

    result = run_fundamental_quality(
        db=db,
        input_payload=input_payload,
        as_of_date="2026-04-30",
        output_root=tmp_path / "output" / "governance",
    )

    assert result["status"] == "completed"
    assert result["report_count"] == 1
    assert (Path(result["output_dir"]) / "p38_fundamental_quality.json").exists()
```

- [ ] **Step 2: Add CLI tests**

Append to `tests/agent/research_v1/test_batch_cli.py`:

```python
def test_fundamental_quality_run_cli_success_writes_artifacts(tmp_path, monkeypatch, capsys):
    from agent.research_v1.batch_cli import main

    app_root = tmp_path / "app"
    app_root.mkdir()
    input_path = tmp_path / "fundamentals.json"
    input_path.write_text('{"as_of_date":"2026-04-30","tickers":[]}', encoding="utf-8")

    def fake_run(**kwargs):
        output_dir = kwargs["output_root"] / "2026-04-30"
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "p38_fundamental_quality.json").write_text("{}", encoding="utf-8")
        (output_dir / "p38_fundamental_quality.md").write_text("# P38", encoding="utf-8")
        return {
            "status": "completed",
            "output_dir": str(output_dir),
            "report_count": 1,
            "blocked_count": 0,
            "warning_count": 0,
        }

    monkeypatch.setattr("agent.research_v1.batch_cli.run_fundamental_quality", fake_run)

    code = main([
        "--app-root", str(app_root),
        "fundamental-quality-run",
        "--input", str(input_path),
        "--as-of-date", "2026-04-30",
    ])

    out = capsys.readouterr().out
    assert code == 0
    assert "Fundamental quality status: completed" in out
    assert str(app_root / "output" / "governance" / "2026-04-30") in out


def test_fundamental_quality_run_cli_rejects_invalid_json(tmp_path, capsys):
    from agent.research_v1.batch_cli import main

    app_root = tmp_path / "app"
    app_root.mkdir()
    input_path = tmp_path / "bad.json"
    input_path.write_text("{bad", encoding="utf-8")

    code = main([
        "--app-root", str(app_root),
        "fundamental-quality-run",
        "--input", str(input_path),
        "--as-of-date", "2026-04-30",
    ])

    assert code == 2
    assert "invalid fundamental-quality-run input" in capsys.readouterr().out
```

- [ ] **Step 3: Add hard-boundary test**

Append:

```python
def test_p38_hard_boundaries_are_explicit():
    from agent.research_v1 import fundamental_quality as p38

    forbidden_names = {
        "broker",
        "order",
        "train_model",
        "scheduler",
        "notification",
        "final_judge",
        "run_governance_runtime",
        "run_recommendation_outcome_tracking",
        "run_market_regime_context",
        "_extract_thesis_inputs",
    }

    assert not (forbidden_names & set(p38.__dict__))
    assert "does not approve production" in p38.P38_ARTIFACT_DISCLAIMER
```

- [ ] **Step 4: Run tests and confirm failure**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_fundamental_quality.py tests/agent/research_v1/test_batch_cli.py -q
```

Expected: fail because run orchestration and CLI are not wired.

- [ ] **Step 5: Implement run orchestration and CLI**

In `fundamental_quality.py`, implement:

```python
def run_fundamental_quality(
    db,
    input_payload: dict,
    as_of_date: str | None = None,
    output_root: Path | None = None,
) -> dict:
    ...
```

In `batch_cli.py`, add `fundamental-quality-run` with:

```text
--input
--as-of-date
--output-root
```

Rules:

- Resolve relative `--output-root` under `--app-root`.
- Return `2` for missing file, invalid JSON, invalid as-of date, or missing `tickers` list.
- Print status, output dir, report count, blocked count, and warning count.

- [ ] **Step 6: Run CLI tests**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_fundamental_quality.py tests/agent/research_v1/test_batch_cli.py -q
```

Expected: P38 focused and relevant batch CLI tests pass, aside from any existing host-only PDF browser dependency outside P38.

- [ ] **Step 7: Commit P38-C**

Run:

```bash
git add agent/research_v1/fundamental_quality.py agent/research_v1/batch_cli.py tests/agent/research_v1/test_fundamental_quality.py tests/agent/research_v1/test_batch_cli.py
git commit -m "feat: add fundamental quality cli"
```

---

### Task 4: P38-D Docs + Regression

**Files:**
- Modify: `README.md`
- Modify: `agent/research_v1/README.md`

- [ ] **Step 1: Update root README**

Add P38 to the current-version/system map:

```markdown
### P38 Fundamental Quality Engine

P38 adds standalone deterministic fundamental-quality scoring from point-in-time financial rows. It computes profitability, growth quality, cash conversion, balance-sheet strength, dilution, and stability dimensions, persists append-only `fundamental_quality_reports`, and writes `p38_fundamental_quality.{json,md}` under `output/governance/YYYY-MM-DD/`.

P38 is evidence only. It does not change ticker recommendations, call `final_judge`, alter `RoleWeightConfig`, inject into `JudgeInputPacket`, train models, schedule jobs, send notifications, place trades, or approve production adoption.
```

- [ ] **Step 2: Update research README Data Flow**

In `agent/research_v1/README.md`, add:

```markdown
#### P38 Fundamental Quality Engine

`fundamental_quality.py` consumes point-in-time financial rows and emits standalone fundamental-quality reports. The flow is one-way: quality reports are persisted and written to artifacts, but P38 does not alter `_extract_thesis_inputs()`, `ThesisEngine`, `final_judge`, `RoleWeightConfig`, `JudgeInputPacket`, P35 governance runtime, P36 outcome tracking, P37 market-regime context, or production configuration.
```

- [ ] **Step 3: Run focused verification**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_fundamental_quality.py -q
```

Expected: all P38 tests pass.

- [ ] **Step 4: Run P36/P37 focused regression**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest \
  tests/agent/research_v1/test_recommendation_outcomes.py \
  tests/agent/research_v1/test_market_regime_context.py \
  -q
```

Expected: P36 and P37 remain green.

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

Run the existing full P20-P37 command from `README.md`, adding:

```text
tests/agent/research_v1/test_fundamental_quality.py
```

Expected: full chain passes, except any explicitly documented host-only PDF browser dependency unrelated to P38.

- [ ] **Step 8: Commit P38-D**

Run:

```bash
git add README.md agent/research_v1/README.md
git commit -m "docs: document p38 fundamental quality"
```

---

## Final Review Checklist

- [ ] P38 focused tests pass.
- [ ] P36/P37 focused regression passes.
- [ ] Governance-adjacent regression passes.
- [ ] Doc standards pass.
- [ ] `fundamental-quality-run` writes `p38_fundamental_quality.json`.
- [ ] `fundamental-quality-run` writes `p38_fundamental_quality.md`.
- [ ] Rerun with same `(ticker, as_of_date, source_hash)` does not duplicate rows.
- [ ] Rerun with revised source rows appends a distinguishable report.
- [ ] P38 ignores future-source-date rows.
- [ ] P38 does not call broker/order APIs.
- [ ] P38 does not train models.
- [ ] P38 does not schedule jobs or send notifications.
- [ ] P38 does not mutate production config.
- [ ] P38 does not call `final_judge`.
- [ ] P38 does not call P35 runtime.
- [ ] P38 does not call P36 outcome tracking.
- [ ] P38 does not call P37 market-regime context.
- [ ] P38 does not change `_extract_thesis_inputs()` or ticker recommendations.

## Executor Report Format

When implementation finishes, report:

```text
P38 Implementation Complete

Status Summary
Phase   Status   Commit
P38-A   PASS     <commit>
P38-B   PASS     <commit>
P38-C   PASS     <commit>
P38-D   PASS     <commit>

Verification
- P38 focused: <result>
- P36/P37 focused regression: <result>
- Governance-adjacent regression: <result>
- Doc standards: <result>
- Full P20-P38 chain: <result or environment note>

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
- no thesis input mutation
- no P35 runtime wiring
- no P36/P37 mutation

Known Risks
- <only real residual risks>
```
