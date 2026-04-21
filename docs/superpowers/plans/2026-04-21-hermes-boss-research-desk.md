# Hermes Boss Research Desk Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn Hermes into a local product shell that can initialize local state, ingest assistant-produced batch research, render a boss-first overview/detail UI, and export a PDF report.

**Architecture:** Keep the existing `agent.research_v1` package and add a thin product layer on top of it. Reuse `ResearchDatabase` and `viewer.py`, extend the schema with batch/report tables, add an application entrypoint plus a structured ingest path, and generate both HTML views and PDF output from persisted batch data.

**Tech Stack:** Python 3.11+, SQLite, stdlib HTTP server, argparse, JSON, pytest, ReportLab for PDF generation

---

## File Structure

### Existing files to modify

- `E:\hermes-agent\agent\research_v1\data\database.py`
  - Extend schema and add batch/report CRUD methods.
- `E:\hermes-agent\agent\research_v1\viewer.py`
  - Upgrade from signal tables to boss research dashboard routes and rendering.
- `E:\hermes-agent\README.md`
  - Update local usage instructions.
- `E:\hermes-agent\tests\agent\research_v1\test_database.py`
  - Add schema and CRUD coverage for new product tables.
- `E:\hermes-agent\tests\agent\research_v1\test_p6_viewer.py`
  - Add research dashboard rendering and route coverage.

### New files to create

- `E:\hermes-agent\agent\research_v1\app.py`
  - Product CLI entrypoint for `init`, `create-batch`, `ingest`, `viewer`, `export-pdf`, and `status`.
- `E:\hermes-agent\agent\research_v1\paths.py`
  - Centralize local app directories and file paths.
- `E:\hermes-agent\agent\research_v1\research_batch_service.py`
  - Own ingest contract and batch persistence orchestration.
- `E:\hermes-agent\agent\research_v1\report_pdf.py`
  - Generate boss-facing PDF report from persisted batch data.
- `E:\hermes-agent\tests\agent\research_v1\test_app.py`
  - Cover app CLI flows and initialization behavior.
- `E:\hermes-agent\tests\agent\research_v1\test_report_pdf.py`
  - Verify PDF generation and content anchors.
- `E:\hermes-agent\tests\agent\research_v1\fixtures\sample_batch_payload.json`
  - Stable ingest fixture for tests.

## Task 1: Add App Paths And Local Initialization

**Files:**
- Create: `E:\hermes-agent\agent\research_v1\paths.py`
- Create: `E:\hermes-agent\tests\agent\research_v1\test_app.py`
- Modify: `E:\hermes-agent\README.md`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

from agent.research_v1.paths import HermesPaths


def test_paths_create_expected_local_directories(tmp_path: Path):
    paths = HermesPaths.from_root(tmp_path)

    created = paths.ensure_directories()

    assert paths.app_root == tmp_path
    assert paths.data_dir.exists()
    assert paths.reports_dir.exists()
    assert paths.exports_dir.exists()
    assert paths.database_path == tmp_path / "data" / "research.db"
    assert created == {
        "app_root": str(tmp_path),
        "database_path": str(tmp_path / "data" / "research.db"),
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest E:\hermes-agent\tests\agent\research_v1\test_app.py::test_paths_create_expected_local_directories -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'agent.research_v1.paths'`

- [ ] **Step 3: Write minimal implementation**

```python
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class HermesPaths:
    app_root: Path
    data_dir: Path
    reports_dir: Path
    exports_dir: Path
    database_path: Path

    @classmethod
    def from_root(cls, root: str | Path) -> "HermesPaths":
        root_path = Path(root).expanduser().resolve()
        data_dir = root_path / "data"
        reports_dir = root_path / "reports"
        exports_dir = root_path / "exports"
        return cls(
            app_root=root_path,
            data_dir=data_dir,
            reports_dir=reports_dir,
            exports_dir=exports_dir,
            database_path=data_dir / "research.db",
        )

    def ensure_directories(self) -> dict[str, str]:
        self.app_root.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.exports_dir.mkdir(parents=True, exist_ok=True)
        return {
            "app_root": str(self.app_root),
            "database_path": str(self.database_path),
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest E:\hermes-agent\tests\agent\research_v1\test_app.py::test_paths_create_expected_local_directories -v`

Expected: PASS

- [ ] **Step 5: Update README for local app root**

```md
## Local App Data

Hermes stores local runtime state under a chosen app root directory.

Default layout:

- `data/research.db`
- `reports/`
- `exports/`
```

- [ ] **Step 6: Commit**

```bash
git -C E:\hermes-agent add agent/research_v1/paths.py tests/agent/research_v1/test_app.py README.md
git -C E:\hermes-agent commit -m "feat: add Hermes local path management"
```

## Task 2: Extend Database For Batch Research Product Data

**Files:**
- Modify: `E:\hermes-agent\agent\research_v1\data\database.py`
- Modify: `E:\hermes-agent\tests\agent\research_v1\test_database.py`

- [ ] **Step 1: Write the failing test**

```python
import os
import tempfile

from agent.research_v1.data.database import ResearchDatabase


def test_database_persists_batch_and_reports():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = ResearchDatabase(os.path.join(tmpdir, "research.db"))
        db.initialize()

        batch_id = db.create_research_batch(
            title="US Big Tech Batch",
            requested_tickers=["AAPL", "MSFT"],
            boss_summary="AAPL leads on current setup.",
            status="completed",
        )
        item_id = db.add_research_batch_item(
            batch_id=batch_id,
            symbol="AAPL",
            display_rank=1,
            overall_rating="A",
            confidence=0.82,
            priority_score=81.5,
            action="BUY",
            top_thesis="Earnings resilience",
            top_risk="Valuation compression",
            entry_price=186.5,
            stop_loss=173.45,
            take_profit=208.88,
            holding_horizon="20d",
        )
        report_id = db.save_company_report(
            batch_item_id=item_id,
            bottom_line="AAPL is the top name in this batch.",
            why_it_matters="Execution remains strong.",
            action_plan="Accumulate near entry zone.",
            bull_case="Services mix supports margin resilience.",
            risk_watch="Macro slowdown could compress multiples.",
            research_summary="Balanced upside with manageable risk.",
            signal_snapshot_json='{"grade": "A"}',
        )

        batch = db.get_research_batch(batch_id)
        items = db.list_research_batch_items(batch_id)
        report = db.get_company_report(report_id)

        assert batch["title"] == "US Big Tech Batch"
        assert batch["requested_tickers"] == '["AAPL", "MSFT"]'
        assert items[0]["symbol"] == "AAPL"
        assert report["bottom_line"] == "AAPL is the top name in this batch."
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest E:\hermes-agent\tests\agent\research_v1\test_database.py::test_database_persists_batch_and_reports -v`

Expected: FAIL with `AttributeError: 'ResearchDatabase' object has no attribute 'create_research_batch'`

- [ ] **Step 3: Add schema tables**

```python
cursor.execute("""
    CREATE TABLE IF NOT EXISTS research_batches (
        batch_id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        requested_tickers TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'draft',
        boss_summary TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS research_batch_items (
        item_id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_id INTEGER NOT NULL,
        symbol TEXT NOT NULL,
        display_rank INTEGER NOT NULL,
        overall_rating TEXT NOT NULL,
        confidence REAL NOT NULL,
        priority_score REAL NOT NULL,
        action TEXT NOT NULL,
        top_thesis TEXT NOT NULL,
        top_risk TEXT NOT NULL,
        entry_price REAL NOT NULL,
        stop_loss REAL NOT NULL,
        take_profit REAL NOT NULL,
        holding_horizon TEXT NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (batch_id) REFERENCES research_batches(batch_id)
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS company_reports (
        report_id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_item_id INTEGER NOT NULL,
        bottom_line TEXT NOT NULL,
        why_it_matters TEXT NOT NULL,
        action_plan TEXT NOT NULL,
        bull_case TEXT NOT NULL,
        risk_watch TEXT NOT NULL,
        research_summary TEXT NOT NULL,
        signal_snapshot_json TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (batch_item_id) REFERENCES research_batch_items(item_id)
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS report_versions (
        version_id INTEGER PRIMARY KEY AUTOINCREMENT,
        report_id INTEGER NOT NULL,
        version_label TEXT NOT NULL,
        content_json TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (report_id) REFERENCES company_reports(report_id)
    )
""")
```

- [ ] **Step 4: Add CRUD methods**

```python
def create_research_batch(self, title: str, requested_tickers: list[str], boss_summary: str, status: str = "draft") -> int:
    conn = self._get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO research_batches (title, requested_tickers, status, boss_summary)
        VALUES (?, ?, ?, ?)
        """,
        (title, json.dumps(requested_tickers), status, boss_summary),
    )
    batch_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return batch_id


def add_research_batch_item(self, **kwargs) -> int:
    conn = self._get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO research_batch_items (
            batch_id, symbol, display_rank, overall_rating, confidence,
            priority_score, action, top_thesis, top_risk,
            entry_price, stop_loss, take_profit, holding_horizon
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            kwargs["batch_id"], kwargs["symbol"], kwargs["display_rank"],
            kwargs["overall_rating"], kwargs["confidence"], kwargs["priority_score"],
            kwargs["action"], kwargs["top_thesis"], kwargs["top_risk"],
            kwargs["entry_price"], kwargs["stop_loss"], kwargs["take_profit"],
            kwargs["holding_horizon"],
        ),
    )
    item_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return item_id


def save_company_report(self, **kwargs) -> int:
    conn = self._get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO company_reports (
            batch_item_id, bottom_line, why_it_matters, action_plan,
            bull_case, risk_watch, research_summary, signal_snapshot_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            kwargs["batch_item_id"], kwargs["bottom_line"], kwargs["why_it_matters"],
            kwargs["action_plan"], kwargs["bull_case"], kwargs["risk_watch"],
            kwargs["research_summary"], kwargs["signal_snapshot_json"],
        ),
    )
    report_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return report_id
```

- [ ] **Step 5: Add retrieval methods**

```python
def get_research_batch(self, batch_id: int) -> Optional[dict]:
    conn = self._get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM research_batches WHERE batch_id = ?", (batch_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row is not None else None


def list_research_batch_items(self, batch_id: int) -> list[dict]:
    conn = self._get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT * FROM research_batch_items
        WHERE batch_id = ?
        ORDER BY display_rank ASC, updated_at DESC
        """,
        (batch_id,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_company_report(self, report_id: int) -> Optional[dict]:
    conn = self._get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM company_reports WHERE report_id = ?", (report_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row is not None else None
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest E:\hermes-agent\tests\agent\research_v1\test_database.py::test_database_persists_batch_and_reports -v`

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git -C E:\hermes-agent add agent/research_v1/data/database.py tests/agent/research_v1/test_database.py
git -C E:\hermes-agent commit -m "feat: add research batch persistence"
```

## Task 3: Add Structured Batch Ingest Service

**Files:**
- Create: `E:\hermes-agent\agent\research_v1\research_batch_service.py`
- Create: `E:\hermes-agent\tests\agent\research_v1\fixtures\sample_batch_payload.json`
- Modify: `E:\hermes-agent\tests\agent\research_v1\test_app.py`

- [ ] **Step 1: Write the failing test**

```python
import json
import os
import tempfile
from pathlib import Path

from agent.research_v1.data.database import ResearchDatabase
from agent.research_v1.research_batch_service import save_batch_research


def test_save_batch_research_persists_batch_fixture():
    fixture_path = Path(__file__).parent / "fixtures" / "sample_batch_payload.json"
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))

    with tempfile.TemporaryDirectory() as tmpdir:
        db = ResearchDatabase(os.path.join(tmpdir, "research.db"))
        db.initialize()

        result = save_batch_research(db, payload)

        batch = db.get_research_batch(result["batch_id"])
        items = db.list_research_batch_items(result["batch_id"])

        assert batch["status"] == "completed"
        assert len(items) == 2
        assert items[0]["display_rank"] == 1
        assert items[1]["display_rank"] == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest E:\hermes-agent\tests\agent\research_v1\test_app.py::test_save_batch_research_persists_batch_fixture -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'agent.research_v1.research_batch_service'`

- [ ] **Step 3: Add sample fixture**

```json
{
  "title": "US AI Leaders",
  "boss_summary": "NVDA ranks first, AMD ranks second.",
  "status": "completed",
  "tickers": [
    {
      "symbol": "NVDA",
      "display_rank": 1,
      "overall_rating": "S",
      "confidence": 0.91,
      "priority_score": 92.5,
      "action": "BUY",
      "top_thesis": "AI demand remains structurally strong.",
      "top_risk": "Valuation remains elevated.",
      "entry_price": 120.0,
      "stop_loss": 111.6,
      "take_profit": 134.4,
      "holding_horizon": "20d",
      "report": {
        "bottom_line": "NVDA is the strongest setup in the batch.",
        "why_it_matters": "Leadership remains durable.",
        "action_plan": "Build exposure near entry.",
        "bull_case": "Demand visibility remains high.",
        "risk_watch": "Crowded positioning can amplify pullbacks.",
        "research_summary": "Best combination of momentum and quality.",
        "signal_snapshot_json": "{\"grade\": \"S\"}"
      }
    },
    {
      "symbol": "AMD",
      "display_rank": 2,
      "overall_rating": "A",
      "confidence": 0.81,
      "priority_score": 80.0,
      "action": "WATCH",
      "top_thesis": "Execution is improving.",
      "top_risk": "Competitive pressure remains real.",
      "entry_price": 160.0,
      "stop_loss": 148.8,
      "take_profit": 179.2,
      "holding_horizon": "20d",
      "report": {
        "bottom_line": "AMD is attractive but second to NVDA.",
        "why_it_matters": "Product cycle remains supportive.",
        "action_plan": "Watch for cleaner entry.",
        "bull_case": "Share gains remain possible.",
        "risk_watch": "Execution miss would hurt sentiment.",
        "research_summary": "Good setup, but not top priority.",
        "signal_snapshot_json": "{\"grade\": \"A\"}"
      }
    }
  ]
}
```

- [ ] **Step 4: Write minimal implementation**

```python
from typing import Any

from agent.research_v1.data.database import ResearchDatabase


def save_batch_research(database: ResearchDatabase, payload: dict[str, Any]) -> dict[str, int]:
    batch_id = database.create_research_batch(
        title=payload["title"],
        requested_tickers=[item["symbol"] for item in payload["tickers"]],
        boss_summary=payload["boss_summary"],
        status=payload.get("status", "completed"),
    )

    for ticker in payload["tickers"]:
        item_id = database.add_research_batch_item(
            batch_id=batch_id,
            symbol=ticker["symbol"],
            display_rank=ticker["display_rank"],
            overall_rating=ticker["overall_rating"],
            confidence=ticker["confidence"],
            priority_score=ticker["priority_score"],
            action=ticker["action"],
            top_thesis=ticker["top_thesis"],
            top_risk=ticker["top_risk"],
            entry_price=ticker["entry_price"],
            stop_loss=ticker["stop_loss"],
            take_profit=ticker["take_profit"],
            holding_horizon=ticker["holding_horizon"],
        )
        database.save_company_report(batch_item_id=item_id, **ticker["report"])

    return {"batch_id": batch_id}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest E:\hermes-agent\tests\agent\research_v1\test_app.py::test_save_batch_research_persists_batch_fixture -v`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git -C E:\hermes-agent add agent/research_v1/research_batch_service.py tests/agent/research_v1/test_app.py tests/agent/research_v1/fixtures/sample_batch_payload.json
git -C E:\hermes-agent commit -m "feat: add structured research batch ingest"
```

## Task 4: Add Product CLI Entrypoint

**Files:**
- Create: `E:\hermes-agent\agent\research_v1\app.py`
- Modify: `E:\hermes-agent\tests\agent\research_v1\test_app.py`

- [ ] **Step 1: Write the failing test**

```python
import json
import tempfile
from pathlib import Path

from agent.research_v1.app import main


def test_app_init_and_status_commands(capsys):
    with tempfile.TemporaryDirectory() as tmpdir:
        exit_code = main(["--app-root", tmpdir, "init"])
        assert exit_code == 0

        exit_code = main(["--app-root", tmpdir, "status"])
        assert exit_code == 0

        captured = capsys.readouterr()
        assert "Hermes initialized" in captured.out
        assert "research.db" in captured.out


def test_app_ingest_command(capsys):
    fixture_path = Path(__file__).parent / "fixtures" / "sample_batch_payload.json"
    with tempfile.TemporaryDirectory() as tmpdir:
        main(["--app-root", tmpdir, "init"])
        exit_code = main(["--app-root", tmpdir, "ingest", "--input", str(fixture_path)])

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Batch saved" in captured.out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest E:\hermes-agent\tests\agent\research_v1\test_app.py::test_app_init_and_status_commands E:\hermes-agent\tests\agent\research_v1\test_app.py::test_app_ingest_command -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'agent.research_v1.app'`

- [ ] **Step 3: Write minimal CLI implementation**

```python
import argparse
import json
from pathlib import Path

from agent.research_v1.data.database import ResearchDatabase
from agent.research_v1.paths import HermesPaths
from agent.research_v1.research_batch_service import save_batch_research
from agent.research_v1.viewer import serve_viewer


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hermes")
    parser.add_argument("--app-root", default=".hermes")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init")
    subparsers.add_parser("status")
    ingest = subparsers.add_parser("ingest")
    ingest.add_argument("--input", required=True)
    viewer = subparsers.add_parser("viewer")
    viewer.add_argument("--host", default="127.0.0.1")
    viewer.add_argument("--port", type=int, default=8008)
    export_pdf = subparsers.add_parser("export-pdf")
    export_pdf.add_argument("--batch-id", type=int, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    paths = HermesPaths.from_root(args.app_root)
    paths.ensure_directories()
    db = ResearchDatabase(str(paths.database_path))
    db.initialize()

    if args.command == "init":
        print(f"Hermes initialized at {paths.app_root}")
        print(paths.database_path)
        return 0
    if args.command == "status":
        print(f"App root: {paths.app_root}")
        print(f"Database: {paths.database_path}")
        return 0
    if args.command == "ingest":
        payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
        result = save_batch_research(db, payload)
        print(f"Batch saved: {result['batch_id']}")
        return 0
    if args.command == "viewer":
        server = serve_viewer(db, host=args.host, port=args.port)
        print(f"Hermes viewer at http://{args.host}:{args.port}")
        server.serve_forever()
    parser.error(f"Unsupported command: {args.command}")
    return 2
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest E:\hermes-agent\tests\agent\research_v1\test_app.py::test_app_init_and_status_commands E:\hermes-agent\tests\agent\research_v1\test_app.py::test_app_ingest_command -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C E:\hermes-agent add agent/research_v1/app.py tests/agent/research_v1/test_app.py
git -C E:\hermes-agent commit -m "feat: add Hermes product CLI"
```

## Task 5: Upgrade Viewer To Boss-First Overview And Detail Pages

**Files:**
- Modify: `E:\hermes-agent\agent\research_v1\viewer.py`
- Modify: `E:\hermes-agent\tests\agent\research_v1\test_p6_viewer.py`

- [ ] **Step 1: Write the failing test**

```python
import os
import tempfile

from agent.research_v1.data.database import ResearchDatabase
from agent.research_v1.research_batch_service import save_batch_research
from agent.research_v1.viewer import build_dashboard_snapshot, render_dashboard_html, render_ticker_detail_html


def test_viewer_renders_batch_overview_and_detail(sample_batch_payload):
    with tempfile.TemporaryDirectory() as tmpdir:
        db = ResearchDatabase(os.path.join(tmpdir, "research.db"))
        db.initialize()
        result = save_batch_research(db, sample_batch_payload)

        snapshot = build_dashboard_snapshot(db, result["batch_id"])
        overview_html = render_dashboard_html(snapshot)
        detail_html = render_ticker_detail_html(snapshot["items"][0], snapshot["reports"][snapshot["items"][0]["item_id"]])

        assert "Executive Summary" in overview_html
        assert "NVDA" in overview_html
        assert "Top Risk" in overview_html
        assert "Bottom Line" in detail_html
        assert "Risk Watch" in detail_html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest E:\hermes-agent\tests\agent\research_v1\test_p6_viewer.py::test_viewer_renders_batch_overview_and_detail -v`

Expected: FAIL with missing functions or missing batch rendering fields

- [ ] **Step 3: Add snapshot builders**

```python
def build_dashboard_snapshot(database: ResearchDatabase, batch_id: int | None = None) -> dict:
    latest_batch = database.get_latest_research_batch() if batch_id is None else database.get_research_batch(batch_id)
    if latest_batch is None:
        return {"batch": None, "items": [], "reports": {}}

    items = database.list_research_batch_items(latest_batch["batch_id"])
    reports = {
        item["item_id"]: database.get_company_report_by_item(item["item_id"])
        for item in items
    }
    return {"batch": latest_batch, "items": items, "reports": reports}
```

- [ ] **Step 4: Add overview and detail renderers**

```python
def render_ticker_detail_html(item: dict, report: dict) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"/><title>{escape(item['symbol'])} Detail</title></head>
<body>
  <h1>{escape(item['symbol'])}</h1>
  <h2>Bottom Line</h2>
  <p>{escape(report['bottom_line'])}</p>
  <h2>Suggested Action</h2>
  <p>{escape(item['action'])}</p>
  <h2>Trade Plan</h2>
  <p>Entry {item['entry_price']} / Stop {item['stop_loss']} / Take Profit {item['take_profit']}</p>
  <h2>Bull Case</h2>
  <p>{escape(report['bull_case'])}</p>
  <h2>Risk Watch</h2>
  <p>{escape(report['risk_watch'])}</p>
</body>
</html>"""
```

- [ ] **Step 5: Add HTTP routes**

```python
if self.path in ("/", "/batches/latest"):
    snapshot = build_dashboard_snapshot(database)
    html = render_dashboard_html(snapshot).encode("utf-8")
elif self.path.startswith("/batch/"):
    batch_id = int(self.path.split("/")[-1])
    snapshot = build_dashboard_snapshot(database, batch_id=batch_id)
    html = render_dashboard_html(snapshot).encode("utf-8")
elif self.path.startswith("/ticker/"):
    item_id = int(self.path.split("/")[-1])
    item = database.get_research_batch_item(item_id)
    report = database.get_company_report_by_item(item_id)
    html = render_ticker_detail_html(item, report).encode("utf-8")
else:
    self.send_error(404)
    return
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest E:\hermes-agent\tests\agent\research_v1\test_p6_viewer.py::test_viewer_renders_batch_overview_and_detail -v`

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git -C E:\hermes-agent add agent/research_v1/viewer.py tests/agent/research_v1/test_p6_viewer.py
git -C E:\hermes-agent commit -m "feat: add boss-first research dashboard"
```

## Task 6: Add PDF Export

**Files:**
- Create: `E:\hermes-agent\agent\research_v1\report_pdf.py`
- Create: `E:\hermes-agent\tests\agent\research_v1\test_report_pdf.py`
- Modify: `E:\hermes-agent\agent\research_v1\app.py`

- [ ] **Step 1: Write the failing test**

```python
import os
import tempfile

from agent.research_v1.data.database import ResearchDatabase
from agent.research_v1.report_pdf import export_batch_pdf
from agent.research_v1.research_batch_service import save_batch_research


def test_export_batch_pdf_creates_file(sample_batch_payload):
    with tempfile.TemporaryDirectory() as tmpdir:
        db = ResearchDatabase(os.path.join(tmpdir, "research.db"))
        db.initialize()
        result = save_batch_research(db, sample_batch_payload)

        pdf_path = export_batch_pdf(
            database=db,
            batch_id=result["batch_id"],
            output_dir=tmpdir,
        )

        assert os.path.exists(pdf_path)
        assert pdf_path.endswith(".pdf")
        assert os.path.getsize(pdf_path) > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest E:\hermes-agent\tests\agent\research_v1\test_report_pdf.py::test_export_batch_pdf_creates_file -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'agent.research_v1.report_pdf'`

- [ ] **Step 3: Write minimal PDF exporter**

```python
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


def export_batch_pdf(database, batch_id: int, output_dir: str | Path) -> str:
    batch = database.get_research_batch(batch_id)
    items = database.list_research_batch_items(batch_id)
    output_path = Path(output_dir) / f"batch-{batch_id}.pdf"
    pdf = canvas.Canvas(str(output_path), pagesize=letter)
    y = 750

    pdf.setTitle(batch["title"])
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(72, y, batch["title"])
    y -= 24
    pdf.setFont("Helvetica", 11)
    pdf.drawString(72, y, batch.get("boss_summary") or "")
    y -= 36
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(72, y, "Executive Summary")
    y -= 24

    for item in items:
        line = f"{item['display_rank']}. {item['symbol']} | {item['overall_rating']} | {item['action']} | thesis: {item['top_thesis']}"
        pdf.setFont("Helvetica", 10)
        pdf.drawString(72, y, line[:100])
        y -= 18
        if y < 80:
            pdf.showPage()
            y = 750

    pdf.save()
    return str(output_path)
```

- [ ] **Step 4: Wire CLI export command**

```python
from agent.research_v1.report_pdf import export_batch_pdf

if args.command == "export-pdf":
    output_path = export_batch_pdf(db, args.batch_id, paths.exports_dir)
    print(f"PDF exported: {output_path}")
    return 0
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest E:\hermes-agent\tests\agent\research_v1\test_report_pdf.py::test_export_batch_pdf_creates_file -v`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git -C E:\hermes-agent add agent/research_v1/report_pdf.py agent/research_v1/app.py tests/agent/research_v1/test_report_pdf.py
git -C E:\hermes-agent commit -m "feat: add boss report PDF export"
```

## Task 7: End-To-End Verification And Docs

**Files:**
- Modify: `E:\hermes-agent\README.md`
- Modify: `E:\hermes-agent\tests\agent\research_v1\test_app.py`

- [ ] **Step 1: Add end-to-end CLI test**

```python
from pathlib import Path
import tempfile

from agent.research_v1.app import main


def test_end_to_end_init_ingest_export_flow(capsys):
    fixture_path = Path(__file__).parent / "fixtures" / "sample_batch_payload.json"
    with tempfile.TemporaryDirectory() as tmpdir:
        assert main(["--app-root", tmpdir, "init"]) == 0
        assert main(["--app-root", tmpdir, "ingest", "--input", str(fixture_path)]) == 0
        assert main(["--app-root", tmpdir, "export-pdf", "--batch-id", "1"]) == 0

        captured = capsys.readouterr()
        assert "Hermes initialized" in captured.out
        assert "Batch saved: 1" in captured.out
        assert "PDF exported:" in captured.out
```

- [ ] **Step 2: Run end-to-end test to verify it passes**

Run: `pytest E:\hermes-agent\tests\agent\research_v1\test_app.py::test_end_to_end_init_ingest_export_flow -v`

Expected: PASS

- [ ] **Step 3: Update README usage**

```md
## Boss Research Desk Quickstart

Initialize local state:

```bash
python -m agent.research_v1.app --app-root .hermes init
```

Ingest assistant-produced batch research:

```bash
python -m agent.research_v1.app --app-root .hermes ingest --input tests/agent/research_v1/fixtures/sample_batch_payload.json
```

Launch viewer:

```bash
python -m agent.research_v1.app --app-root .hermes viewer
```

Export PDF:

```bash
python -m agent.research_v1.app --app-root .hermes export-pdf --batch-id 1
```
```

- [ ] **Step 4: Run focused product verification**

Run: `pytest E:\hermes-agent\tests\agent\research_v1\test_app.py E:\hermes-agent\tests\agent\research_v1\test_database.py E:\hermes-agent\tests\agent\research_v1\test_p6_viewer.py E:\hermes-agent\tests\agent\research_v1\test_report_pdf.py -v`

Expected: PASS for all new product workflow tests

- [ ] **Step 5: Commit**

```bash
git -C E:\hermes-agent add README.md tests/agent/research_v1/test_app.py
git -C E:\hermes-agent commit -m "docs: add Hermes boss desk quickstart"
```

## Self-Review

### Spec coverage

- local startup flow: Task 1 and Task 4
- SQLite persistence and batch storage: Task 2 and Task 3
- overview-first web UI: Task 5
- detail pages: Task 5
- PDF generation: Task 6
- clear ingest interface for assistant output: Task 3
- verification requirements: Task 7

No uncovered spec sections remain for this phase.

### Placeholder scan

Checked for `TODO`, `TBD`, “implement later”, “appropriate error handling”, and vague testing instructions. None remain in the plan body.

### Type consistency

- batch identifiers consistently use `batch_id`
- item identifiers consistently use `item_id`
- company report linkage consistently uses `batch_item_id`
- ingest function consistently uses `save_batch_research(database, payload)`

These names are consistent across tasks.
