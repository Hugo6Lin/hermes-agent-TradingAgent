# P0 Signal Standardization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add structured executable signal output to grading and persist first-class signal records with signal-time price snapshots and revision history.

**Architecture:** Keep the first implementation narrow. Extend `GradingAgent` so it emits a structured signal payload derived from existing score output, then add SQLite schema support in `ResearchDatabase` for `signals`, `price_snapshots`, and `signal_revisions`. Reuse existing test files and database patterns rather than introducing a new service layer yet.

**Tech Stack:** Python 3, pytest, sqlite3, existing Hermes `research_v1` modules

---

## File Structure

- Modify `E:/hermes-agent/agent/research_v1/grading.py`
  - Extend grading output with structured signal fields
- Modify `E:/hermes-agent/agent/research_v1/data/database.py`
  - Add schema initialization for `signals`, `price_snapshots`, and `signal_revisions`
- Modify `E:/hermes-agent/tests/agent/research_v1/test_review_grade_monitor.py`
  - Add grading tests for structured signal fields
- Modify `E:/hermes-agent/tests/agent/research_v1/test_database.py`
  - Add schema tests for new signal tables

### Task 1: Add structured signal grading output

**Files:**
- Modify: `E:/hermes-agent/tests/agent/research_v1/test_review_grade_monitor.py`
- Modify: `E:/hermes-agent/agent/research_v1/grading.py`

- [ ] **Step 1: Write the failing test**

```python
def test_grading_returns_structured_signal_fields():
    grader = GradingAgent(llm_client=Mock())

    result = grader.grade(
        research_decision={
            "symbol": "AAPL",
            "market_data": {"price": 150.0},
            "fundamentals_summary": {"verdict": "buy", "confidence": 0.9},
            "technical_summary": {"signal": "buy", "rsi": 45},
            "industry_summary": {"trend": "bullish"},
            "macro_data": {"trend": "bullish"}
        },
        analyst_reports={}
    )

    assert "signal" in result
    assert result["signal"]["symbol"] == "AAPL"
    assert result["signal"]["entry_price"] == 150.0
    assert result["signal"]["stop_loss"] is not None
    assert result["signal"]["take_profit"] is not None
    assert result["signal"]["holding_horizon"] in ["5d", "20d", "60d"]
    assert result["signal"]["signal_valid_until"] is not None
    assert result["signal"]["priority_score"] is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest E:/hermes-agent/tests/agent/research_v1/test_review_grade_monitor.py -k structured_signal_fields -v`
Expected: FAIL because `grade()` does not yet return a `signal` object

- [ ] **Step 3: Write minimal implementation**

```python
from datetime import datetime, timedelta


class GradingAgent:
    ...
    def grade(self, research_decision: dict, analyst_reports: dict) -> dict:
        ...
        signal = self._build_signal(
            research_decision=research_decision,
            grade=grade,
            composite_score=composite_score,
        )

        return {
            "grade": grade,
            "fundamental_score": fundamental_score,
            "technical_score": technical_score,
            "macro_score": macro_score,
            "composite_score": composite_score,
            "signal": signal,
        }

    def _build_signal(self, research_decision: dict, grade: str, composite_score: float) -> dict:
        symbol = research_decision.get("symbol", "UNKNOWN")
        current_price = research_decision.get("market_data", {}).get("price")
        if current_price is None:
            current_price = 0.0

        holding_horizon = self._determine_holding_horizon(grade)
        validity_days = {"5d": 1, "20d": 3, "60d": 5}[holding_horizon]
        signal_valid_until = (datetime.utcnow() + timedelta(days=validity_days)).isoformat()

        return {
            "symbol": symbol,
            "entry_price": current_price,
            "stop_loss": round(current_price * 0.93, 2) if current_price else 0.0,
            "take_profit": round(current_price * 1.12, 2) if current_price else 0.0,
            "holding_horizon": holding_horizon,
            "signal_valid_until": signal_valid_until,
            "priority_score": round(composite_score, 2),
            "confidence": round(composite_score / 100, 4),
        }

    def _determine_holding_horizon(self, grade: str) -> str:
        return {"S": "20d", "A": "20d", "B": "5d", "C": "5d"}.get(grade, "5d")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest E:/hermes-agent/tests/agent/research_v1/test_review_grade_monitor.py -k structured_signal_fields -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add E:/hermes-agent/tests/agent/research_v1/test_review_grade_monitor.py E:/hermes-agent/agent/research_v1/grading.py
git commit -m "feat: add structured signal output to grading"
```

### Task 2: Add SQLite schema support for signal persistence

**Files:**
- Modify: `E:/hermes-agent/tests/agent/research_v1/test_database.py`
- Modify: `E:/hermes-agent/agent/research_v1/data/database.py`

- [ ] **Step 1: Write the failing test**

```python
def test_initialize_creates_signal_tables():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "research.db")
        db = ResearchDatabase(db_path)
        db.initialize()

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        table_names = {row[0] for row in cursor.fetchall()}
        conn.close()

        assert "signals" in table_names
        assert "price_snapshots" in table_names
        assert "signal_revisions" in table_names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest E:/hermes-agent/tests/agent/research_v1/test_database.py -k signal_tables -v`
Expected: FAIL because the three signal tables do not yet exist

- [ ] **Step 3: Write minimal implementation**

```python
cursor.execute("""
    CREATE TABLE IF NOT EXISTS signals (
        signal_id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id INTEGER,
        symbol TEXT NOT NULL,
        grade TEXT NOT NULL,
        confidence REAL NOT NULL,
        entry_price REAL NOT NULL,
        stop_loss REAL NOT NULL,
        take_profit REAL NOT NULL,
        holding_horizon TEXT NOT NULL,
        signal_valid_until TEXT NOT NULL,
        priority_score REAL NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (task_id) REFERENCES analysis_tasks(task_id)
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS price_snapshots (
        snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
        signal_id INTEGER,
        symbol TEXT NOT NULL,
        price REAL NOT NULL,
        snapshot_type TEXT NOT NULL,
        captured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (signal_id) REFERENCES signals(signal_id)
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS signal_revisions (
        revision_id INTEGER PRIMARY KEY AUTOINCREMENT,
        signal_id INTEGER NOT NULL,
        previous_grade TEXT,
        new_grade TEXT NOT NULL,
        revision_reason TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (signal_id) REFERENCES signals(signal_id)
    )
""")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest E:/hermes-agent/tests/agent/research_v1/test_database.py -k signal_tables -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add E:/hermes-agent/tests/agent/research_v1/test_database.py E:/hermes-agent/agent/research_v1/data/database.py
git commit -m "feat: add signal persistence tables"
```

### Task 3: Verify P0 base path stays green

**Files:**
- Test: `E:/hermes-agent/tests/agent/research_v1/test_review_grade_monitor.py`
- Test: `E:/hermes-agent/tests/agent/research_v1/test_database.py`

- [ ] **Step 1: Run targeted grading and database tests**

Run: `pytest E:/hermes-agent/tests/agent/research_v1/test_review_grade_monitor.py E:/hermes-agent/tests/agent/research_v1/test_database.py -v`
Expected: PASS with no failures

- [ ] **Step 2: Review for minimality**

Check that implementation only adds:
- structured signal payload generation
- three new schema tables
- no provider, backtest, or UI work

- [ ] **Step 3: Commit**

```bash
git add E:/hermes-agent/agent/research_v1/grading.py E:/hermes-agent/agent/research_v1/data/database.py E:/hermes-agent/tests/agent/research_v1/test_review_grade_monitor.py E:/hermes-agent/tests/agent/research_v1/test_database.py
git commit -m "feat: complete p0 signal standardization base"
```

## Self-Review

- Spec coverage:
  - structured signal output covered in Task 1
  - `signals`, `price_snapshots`, `signal_revisions` schema covered in Task 2
  - verification covered in Task 3
- Placeholder scan:
  - no TBD or TODO markers remain
- Type consistency:
  - `signal`, `entry_price`, `stop_loss`, `take_profit`, `holding_horizon`, `signal_valid_until`, and `priority_score` use the same names across tests and implementation

