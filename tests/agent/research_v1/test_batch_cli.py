"""Tests for Hermes local app path management."""

import importlib
import json
import os
import sqlite3
import tempfile
from copy import deepcopy
from pathlib import Path

import pytest
from agent.research_v1.data.database import ResearchDatabase
from agent.research_v1.paths import HermesPaths
from agent.research_v1.research_batch_service import save_batch_research


def _get_batch_table_counts(db_path: str) -> tuple[int, int, int]:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM research_batches")
    batch_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM research_batch_items")
    item_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM company_reports")
    report_count = cursor.fetchone()[0]
    conn.close()
    return batch_count, item_count, report_count


def _load_app_module():
    try:
        return importlib.import_module("agent.research_v1.batch_cli")
    except ModuleNotFoundError as exc:  # pragma: no cover - exercised before batch_cli exists
        pytest.fail(f"agent.research_v1.batch_cli could not be imported: {exc}")


def test_paths_create_expected_local_directories(tmp_path: Path):
    paths = HermesPaths.from_root(tmp_path)

    paths.ensure_directories()

    assert paths.app_root == tmp_path
    assert paths.data_dir == tmp_path / "data"
    assert paths.reports_dir == tmp_path / "reports"
    assert paths.exports_dir == tmp_path / "exports"
    assert paths.database_path == tmp_path / "data" / "research.db"
    assert paths.data_dir.exists()
    assert paths.reports_dir.exists()
    assert paths.exports_dir.exists()


def test_app_init_and_status_commands(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    app = _load_app_module()

    assert app.main(["--app-root", str(tmp_path), "init"]) == 0
    init_output = capsys.readouterr().out

    assert (tmp_path / "data").is_dir()
    assert (tmp_path / "reports").is_dir()
    assert (tmp_path / "exports").is_dir()
    assert (tmp_path / "data" / "research.db").exists()
    assert "initialized" in init_output.lower()

    assert app.main(["--app-root", str(tmp_path), "status"]) == 0
    status_output = capsys.readouterr().out

    assert str(tmp_path.resolve()) in status_output
    assert "database" in status_output.lower()
    assert "ready" in status_output.lower() or "exists" in status_output.lower()


def test_app_ingest_command(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    app = _load_app_module()
    fixture_path = Path(__file__).parent / "fixtures" / "sample_batch_payload.json"
    ingest_input = tmp_path / "sample_batch_payload.json"
    ingest_input.write_text(fixture_path.read_text(encoding="utf-8"), encoding="utf-8")

    assert app.main(["--app-root", str(tmp_path), "ingest", "--input", str(ingest_input)]) == 0
    output = capsys.readouterr().out

    db_path = tmp_path / "data" / "research.db"
    db = ResearchDatabase(str(db_path))

    batch = db.get_research_batch(1)
    items = db.list_research_batch_items(1)

    assert batch is not None
    assert batch["title"] == "US AI Leaders"
    assert len(items) == 2
    assert items[0]["symbol"] == "NVDA"
    assert items[1]["symbol"] == "AMD"
    assert "batch" in output.lower()
    assert "ingested" in output.lower() or "saved" in output.lower()


def test_app_end_to_end_init_ingest_and_export_pdf(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    app = _load_app_module()
    fixture_path = Path(__file__).parent / "fixtures" / "sample_batch_payload.json"
    ingest_input = tmp_path / "sample_batch_payload.json"
    ingest_input.write_text(fixture_path.read_text(encoding="utf-8"), encoding="utf-8")

    assert app.main(["--app-root", str(tmp_path), "init"]) == 0
    capsys.readouterr()

    assert app.main(["--app-root", str(tmp_path), "ingest", "--input", str(ingest_input)]) == 0
    ingest_output = capsys.readouterr().out
    assert "batch" in ingest_output.lower()

    assert app.main(["--app-root", str(tmp_path), "export-pdf", "--batch-id", "1"]) == 0
    export_output = capsys.readouterr().out

    pdf_lines = [line for line in export_output.strip().splitlines() if line.strip().endswith(".pdf")]
    assert pdf_lines
    pdf_path = Path(pdf_lines[-1].split(" to ", 1)[-1].strip())

    assert pdf_path.exists()
    assert pdf_path.parent == tmp_path / "exports"
    assert pdf_path.suffix == ".pdf"
    assert pdf_path.read_bytes().startswith(b"%PDF-")


def test_app_quote_command_uses_futu_snapshot(monkeypatch, capsys: pytest.CaptureFixture[str]):
    app = _load_app_module()

    def fake_fetch_snapshot(self, symbols):
        assert symbols == ["AAPL", "HK.00700"]
        return [{"code": "US.AAPL", "last_price": 200.0}]

    monkeypatch.setattr("agent.research_v1.data.futu_opend.FutuQuoteClient.fetch_snapshot", fake_fetch_snapshot)

    assert app.main(["quote", "--symbols", "AAPL,HK.00700"]) == 0
    output = capsys.readouterr().out

    assert "US.AAPL" in output
    assert "200.0" in output


def test_app_option_chain_command_uses_futu(monkeypatch, capsys: pytest.CaptureFixture[str]):
    app = _load_app_module()

    def fake_fetch_option_chain(self, symbol, start=None, end=None):
        assert symbol == "GLW"
        assert start == "2027-01-01"
        assert end == "2027-01-31"
        return [{"code": "US.GLW270115C00140000", "strike_price": 140.0}]

    monkeypatch.setattr("agent.research_v1.data.futu_opend.FutuQuoteClient.fetch_option_chain", fake_fetch_option_chain)

    assert app.main(["option-chain", "--symbol", "GLW", "--start", "2027-01-01", "--end", "2027-01-31"]) == 0
    output = capsys.readouterr().out

    assert "US.GLW270115C00140000" in output


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
        assert batch["requested_tickers"] == ["NVDA", "AMD"]
        assert len(items) == 2
        assert items[0]["display_rank"] == 1
        assert items[0]["symbol"] == "NVDA"
        assert items[1]["display_rank"] == 2
        assert items[1]["symbol"] == "AMD"

        conn = sqlite3.connect(os.path.join(tmpdir, "research.db"))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM company_reports WHERE report_id IN (?, ?) ORDER BY report_id",
            tuple(result["report_ids"]),
        )
        reports = cursor.fetchall()
        conn.close()

        assert len(reports) == 2
        assert reports[0]["bottom_line"] == "NVDA is the strongest setup in the batch."
        assert reports[1]["bottom_line"] == "AMD is attractive but second to NVDA."


def test_save_batch_research_rolls_back_on_bad_report_payload():
    fixture_path = Path(__file__).parent / "fixtures" / "sample_batch_payload.json"
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    bad_payload = deepcopy(payload)
    del bad_payload["tickers"][1]["report"]["research_summary"]

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "research.db")
        db = ResearchDatabase(db_path)
        db.initialize()

        with pytest.raises(KeyError):
            save_batch_research(db, bad_payload)

        batch_count, item_count, report_count = _get_batch_table_counts(db_path)

        assert batch_count == 0
        assert item_count == 0
        assert report_count == 0


@pytest.mark.parametrize("tickers", [None, []])
def test_save_batch_research_requires_non_empty_tickers(tickers):
    fixture_path = Path(__file__).parent / "fixtures" / "sample_batch_payload.json"
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    if tickers is None:
        del payload["tickers"]
    else:
        payload["tickers"] = tickers

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "research.db")
        db = ResearchDatabase(db_path)
        db.initialize()

        with pytest.raises(ValueError):
            save_batch_research(db, payload)

        batch_count, item_count, report_count = _get_batch_table_counts(db_path)

        assert batch_count == 0
        assert item_count == 0
        assert report_count == 0
