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


def test_governance_run_cli_success(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    app = _load_app_module()
    config_path = tmp_path / "governance_config.json"
    config_path.write_text(json.dumps({
        "version_readiness": {
            "version_id": "p35-cli",
            "branch": "codex/quant-governance-p20-p30",
            "commit": "local-test",
            "evidence": {
                "p20_p30_regression_passed": True,
                "p31_p34_regression_passed": True,
                "doc_standards_passed": True,
            },
            "notes": "P35 CLI test",
        },
        "signal_families": [],
        "expected_artifacts": [],
        "generation_requests": [],
        "edge_reviews": [],
    }), encoding="utf-8")

    result = app.main([
        "--app-root", str(tmp_path),
        "governance-run",
        "--config", str(config_path),
        "--run-date", "2026-04-30",
        "--output-root", str(tmp_path / "output" / "governance"),
    ])

    out = capsys.readouterr().out
    assert result == 0
    assert "Governance runtime status:" in out
    assert "Boss brief status:" in out
    assert "Output dir:" in out


def test_governance_run_cli_invalid_config_returns_nonzero(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    app = _load_app_module()
    config_path = tmp_path / "broken.json"
    config_path.write_text("{not-json", encoding="utf-8")

    result = app.main([
        "--app-root", str(tmp_path),
        "governance-run",
        "--config", str(config_path),
        "--run-date", "2026-04-30",
        "--output-root", str(tmp_path / "output" / "governance"),
    ])

    out = capsys.readouterr().out
    assert result == 2
    assert "Governance runtime status: blocked_invalid_config" in out


def test_governance_run_cli_default_output_root_uses_app_root(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    app = _load_app_module()
    config_path = tmp_path / "governance_config.json"
    config_path.write_text(json.dumps({
        "version_readiness": {
            "version_id": "p35-cli",
            "branch": "codex/quant-governance-p20-p30",
            "commit": "local-test",
            "evidence": {
                "p20_p30_regression_passed": True,
                "p31_p34_regression_passed": True,
                "doc_standards_passed": True,
            },
            "notes": "P35 CLI default output test",
        },
        "signal_families": [],
        "expected_artifacts": [],
        "generation_requests": [],
        "edge_reviews": [],
    }), encoding="utf-8")

    result = app.main([
        "--app-root", str(tmp_path),
        "governance-run",
        "--config", str(config_path),
        "--run-date", "2026-04-30",
    ])

    out = capsys.readouterr().out
    assert result == 0
    assert str(tmp_path / "output" / "governance") in out


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


# ── P37 market-regime-run CLI tests ──────────────────────────────────────────

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


# ── P38 fundamental-quality-run CLI tests ────────────────────────────────────

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


def test_fundamental_quality_run_cli_rejects_invalid_date(tmp_path, capsys):
    from agent.research_v1.batch_cli import main

    app_root = tmp_path / "app"
    app_root.mkdir()
    input_path = tmp_path / "fundamentals.json"
    input_path.write_text('{"as_of_date":"2026-04-30","tickers":[]}', encoding="utf-8")

    code = main([
        "--app-root", str(app_root),
        "fundamental-quality-run",
        "--input", str(input_path),
        "--as-of-date", "not-a-date",
    ])

    assert code == 2
    out = capsys.readouterr().out
    assert "invalid fundamental-quality-run input" in out
    assert "date" in out.lower()


def test_fundamental_quality_run_cli_rejects_non_dict_ticker_item(tmp_path, capsys):
    from agent.research_v1.batch_cli import main

    app_root = tmp_path / "app"
    app_root.mkdir()
    input_path = tmp_path / "fundamentals.json"
    input_path.write_text('{"as_of_date":"2026-04-30","tickers":["AAPL"]}', encoding="utf-8")

    code = main([
        "--app-root", str(app_root),
        "fundamental-quality-run",
        "--input", str(input_path),
        "--as-of-date", "2026-04-30",
    ])

    assert code == 2
    out = capsys.readouterr().out
    assert "invalid fundamental-quality-run input" in out
    assert "ticker" in out.lower()


# ── P39 candidate-pool-run CLI tests ─────────────────────────────────────────

def test_candidate_pool_run_cli_success_writes_artifacts(tmp_path, monkeypatch, capsys):
    from agent.research_v1.batch_cli import main

    app_root = tmp_path / "app"
    app_root.mkdir()
    input_path = tmp_path / "universe.json"
    input_path.write_text(
        '{"as_of_date":"2026-04-30","source":"fixture","universe_id":"u1","tickers":[]}',
        encoding="utf-8",
    )

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

    code = main([
        "--app-root", str(app_root),
        "candidate-pool-run",
        "--input", str(input_path),
        "--as-of-date", "2026-04-30",
    ])
    out = capsys.readouterr().out

    assert code == 0
    assert "Candidate pool status: no_candidates" in out
    assert str(app_root / "output" / "governance" / "2026-04-30") in out


def test_candidate_pool_run_cli_rejects_invalid_date(tmp_path, capsys):
    from agent.research_v1.batch_cli import main

    app_root = tmp_path / "app"
    app_root.mkdir()
    input_path = tmp_path / "universe.json"
    input_path.write_text(
        '{"as_of_date":"2026-04-30","source":"fixture","universe_id":"u1","tickers":[]}',
        encoding="utf-8",
    )

    code = main([
        "--app-root", str(app_root),
        "candidate-pool-run",
        "--input", str(input_path),
        "--as-of-date", "not-a-date",
    ])

    assert code == 2
    assert "invalid candidate-pool-run input" in capsys.readouterr().out


def test_candidate_pool_run_cli_rejects_non_dict_ticker(tmp_path, capsys):
    from agent.research_v1.batch_cli import main

    app_root = tmp_path / "app"
    app_root.mkdir()
    input_path = tmp_path / "universe.json"
    input_path.write_text(
        '{"as_of_date":"2026-04-30","source":"fixture","universe_id":"u1","tickers":["AAPL"]}',
        encoding="utf-8",
    )

    code = main([
        "--app-root", str(app_root),
        "candidate-pool-run",
        "--input", str(input_path),
        "--as-of-date", "2026-04-30",
    ])

    assert code == 2
    assert "invalid candidate-pool-run input" in capsys.readouterr().out


def test_candidate_pool_run_cli_rejects_negative_max_candidates(tmp_path, capsys):
    from agent.research_v1.batch_cli import main

    app_root = tmp_path / "app"
    app_root.mkdir()
    input_path = tmp_path / "universe.json"
    input_path.write_text(
        '{"as_of_date":"2026-04-30","source":"fixture","universe_id":"u1","tickers":[]}',
        encoding="utf-8",
    )

    code = main([
        "--app-root", str(app_root),
        "candidate-pool-run",
        "--input", str(input_path),
        "--max-candidates", "-1",
    ])

    assert code == 2
    assert "invalid candidate-pool-run input" in capsys.readouterr().out


# ── P40 memory-pack-run CLI tests ────────────────────────────────────────

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


def test_memory_pack_run_cli_rejects_invalid_date(tmp_path, capsys):
    from agent.research_v1.batch_cli import main

    code = main(["--app-root", str(tmp_path), "memory-pack-run", "--tickers", "AAPL", "--as-of-date", "not-a-date"])

    assert code == 2
    assert "invalid date format" in capsys.readouterr().out


def test_memory_pack_run_cli_requires_date(tmp_path, capsys):
    from agent.research_v1.batch_cli import main

    code = main(["--app-root", str(tmp_path), "memory-pack-run", "--tickers", "AAPL"])

    assert code == 2
    assert "--as-of-date is required" in capsys.readouterr().out


def test_memory_pack_run_cli_rejects_negative_lookback(tmp_path, capsys):
    from agent.research_v1.batch_cli import main

    code = main(["--app-root", str(tmp_path), "memory-pack-run", "--tickers", "AAPL", "--as-of-date", "2026-04-30", "--lookback-days", "-1"])

    assert code == 2
    assert "lookback-days must be positive" in capsys.readouterr().out


# ── P41 decision-journal-run CLI tests ───────────────────────────────────

def test_decision_journal_run_cli_success_writes_artifacts(tmp_path, monkeypatch, capsys):
    from agent.research_v1.batch_cli import main

    app_root = tmp_path / "app"
    input_path = tmp_path / "journal.json"
    input_path.write_text(
        '{"as_of_date":"2026-04-30","source":"fixture","decisions":[{"ticker":"AAPL","contemplated_action":"research_candidate","decision_intent":"review_before_action","stated_reason":"fixture","boss_confidence":0.8,"urgency":"high"}]}',
        encoding="utf-8",
    )

    def fake_run(**kwargs):
        output_dir = kwargs["output_root"] / "2026-04-30"
        output_dir.mkdir(parents=True, exist_ok=True)
        return {"status": "completed", "output_dir": str(output_dir), "entry_count": 1, "manual_review_count": 0, "slow_down_count": 1, "warning_count": 0}

    monkeypatch.setattr("agent.research_v1.batch_cli.run_decision_journal_guardrails", fake_run)
    code = main(["--app-root", str(app_root), "decision-journal-run", "--input", str(input_path), "--as-of-date", "2026-04-30"])
    out = capsys.readouterr().out

    assert code == 0
    assert "Decision journal status: completed" in out
    assert str(app_root / "output" / "governance" / "2026-04-30") in out


def test_decision_journal_run_cli_rejects_invalid_date(tmp_path, capsys):
    from agent.research_v1.batch_cli import main

    input_path = tmp_path / "journal.json"
    input_path.write_text('{"decisions":[]}', encoding="utf-8")
    code = main(["--app-root", str(tmp_path), "decision-journal-run", "--input", str(input_path), "--as-of-date", "not-a-date"])

    assert code == 2
    assert "invalid date format" in capsys.readouterr().out


def test_decision_journal_run_cli_rejects_empty_decisions(tmp_path, capsys):
    from agent.research_v1.batch_cli import main

    input_path = tmp_path / "journal.json"
    input_path.write_text('{"as_of_date":"2026-04-30","decisions":[]}', encoding="utf-8")
    code = main(["--app-root", str(tmp_path), "decision-journal-run", "--input", str(input_path)])

    assert code == 2
    assert "missing or empty" in capsys.readouterr().out


def test_decision_journal_run_cli_rejects_missing_file(tmp_path, capsys):
    from agent.research_v1.batch_cli import main

    code = main(["--app-root", str(tmp_path), "decision-journal-run", "--input", "/nonexistent/journal.json"])

    assert code == 2
    assert "file not found" in capsys.readouterr().out


# ── P42 boss-copilot-brief-run CLI tests ────────────────────────────────

def test_boss_copilot_brief_run_cli_success_writes_artifacts(tmp_path, monkeypatch, capsys):
    from agent.research_v1.batch_cli import main

    app_root = tmp_path / "app"

    def fake_run(**kwargs):
        output_dir = kwargs["output_root"] / "2026-04-30"
        output_dir.mkdir(parents=True, exist_ok=True)
        return {
            "status": "brief_ready",
            "output_dir": str(output_dir),
            "priority_count": 2,
            "high_priority_count": 1,
            "manual_review_count": 0,
            "missing_context_count": 0,
        }

    monkeypatch.setattr("agent.research_v1.batch_cli.run_boss_copilot_daily_brief", fake_run)
    code = main(["--app-root", str(app_root), "boss-copilot-brief-run", "--as-of-date", "2026-04-30"])
    out = capsys.readouterr().out

    assert code == 0
    assert "Boss co-pilot brief status: brief_ready" in out
    assert str(app_root / "output" / "governance" / "2026-04-30") in out


def test_boss_copilot_brief_run_cli_rejects_invalid_date(tmp_path, capsys):
    from agent.research_v1.batch_cli import main

    code = main(["--app-root", str(tmp_path), "boss-copilot-brief-run", "--as-of-date", "not-a-date"])

    assert code == 2
    assert "invalid boss-copilot-brief-run input" in capsys.readouterr().out


def test_boss_copilot_brief_run_cli_rejects_non_positive_max_priorities(tmp_path, capsys):
    from agent.research_v1.batch_cli import main

    code = main(["--app-root", str(tmp_path), "boss-copilot-brief-run", "--as-of-date", "2026-04-30", "--max-priorities", "0"])

    assert code == 2
    assert "max-priorities must be positive" in capsys.readouterr().out


# ── P43 copilot-console-index-run CLI tests ─────────────────────────────

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


# ── P44 Evidence Monitor CLI tests ──────────────────────────────────────

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


def test_evidence_monitor_run_cli_rejects_non_positive_lookback(tmp_path, capsys):
    from agent.research_v1.batch_cli import main

    code = main(["--app-root", str(tmp_path), "evidence-monitor-run", "--as-of-date", "2026-04-30", "--lookback-days", "0"])

    assert code == 2
    assert "lookback-days must be positive" in capsys.readouterr().out


def test_evidence_monitor_run_cli_rejects_non_positive_freshness(tmp_path, capsys):
    from agent.research_v1.batch_cli import main

    code = main(["--app-root", str(tmp_path), "evidence-monitor-run", "--as-of-date", "2026-04-30", "--freshness-days", "0"])

    assert code == 2
    assert "freshness-days must be positive" in capsys.readouterr().out


# ── P45 CLI tests ──────────────────────────────────────────────────────

def test_market_data_readiness_run_cli_success(tmp_path, monkeypatch, capsys):
    from agent.research_v1.batch_cli import main

    app_root = tmp_path / "app"
    app_root.mkdir()

    def fake_run(**kwargs):
        output_dir = Path(kwargs["output_root"]) / kwargs["as_of_date"]
        output_dir.mkdir(parents=True, exist_ok=True)
        return {
            "status": "provider_ready",
            "output_dir": str(output_dir),
            "report_id": "abc123",
            "source_hash": "def456",
            "recommended_actions": [],
            "paths": {},
        }

    monkeypatch.setattr("agent.research_v1.batch_cli.run_market_data_readiness", fake_run)
    code = main(["--app-root", str(app_root), "market-data-readiness-run", "--as-of-date", "2026-04-30"])
    out = capsys.readouterr().out

    assert code == 0
    assert "Market data readiness status: provider_ready" in out


def test_market_data_readiness_run_cli_rejects_invalid_date(tmp_path, capsys):
    from agent.research_v1.batch_cli import main

    code = main(["--app-root", str(tmp_path), "market-data-readiness-run", "--as-of-date", "not-a-date"])

    assert code == 2
    assert "invalid market-data-readiness-run input" in capsys.readouterr().out


def test_market_data_readiness_run_cli_returns_3_for_unavailable(tmp_path, monkeypatch, capsys):
    from agent.research_v1.batch_cli import main

    app_root = tmp_path / "app"
    app_root.mkdir()

    def fake_run(**kwargs):
        output_dir = Path(kwargs["output_root"]) / kwargs["as_of_date"]
        output_dir.mkdir(parents=True, exist_ok=True)
        return {
            "status": "provider_unavailable",
            "output_dir": str(output_dir),
            "report_id": "abc123",
            "source_hash": "def456",
            "recommended_actions": ["install_futu_api_sdk"],
            "paths": {},
        }

    monkeypatch.setattr("agent.research_v1.batch_cli.run_market_data_readiness", fake_run)
    code = main(["--app-root", str(app_root), "market-data-readiness-run", "--as-of-date", "2026-04-30"])
    out = capsys.readouterr().out

    assert code == 3
    assert "provider_unavailable" in out
    assert "install_futu_api_sdk" in out


def test_market_data_readiness_run_cli_passes_live_flag(tmp_path, monkeypatch, capsys):
    from agent.research_v1.batch_cli import main

    app_root = tmp_path / "app"
    app_root.mkdir()
    captured = {}

    def fake_run(**kwargs):
        captured["live"] = kwargs.get("live")
        captured["symbols"] = kwargs.get("symbols")
        output_dir = Path(kwargs["output_root"]) / kwargs["as_of_date"]
        output_dir.mkdir(parents=True, exist_ok=True)
        return {
            "status": "provider_not_tested_live",
            "output_dir": str(output_dir),
            "report_id": "abc123",
            "source_hash": "def456",
            "recommended_actions": [],
            "paths": {},
        }

    monkeypatch.setattr("agent.research_v1.batch_cli.run_market_data_readiness", fake_run)
    code = main(["--app-root", str(app_root), "market-data-readiness-run", "--as-of-date", "2026-04-30", "--symbols", "US.MSFT,US.GOOGL"])

    assert code == 0
    assert captured["live"] is False
    assert captured["symbols"] == ["US.MSFT", "US.GOOGL"]
