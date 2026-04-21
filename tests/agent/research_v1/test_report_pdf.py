"""Tests for batch PDF export."""

from __future__ import annotations

import json
from pathlib import Path

from agent.research_v1.data.database import ResearchDatabase
from agent.research_v1.report_pdf_legacy import build_batch_export_html


def _extract_pdf_path(output: str, tmp_path: Path) -> Path:
    pdf_lines = [line for line in output.strip().splitlines() if line.strip().endswith(".pdf")]
    assert pdf_lines
    pdf_path = Path(pdf_lines[-1].split(" to ", 1)[-1].strip())
    assert pdf_path.parent == tmp_path / "exports"
    return pdf_path


def test_export_pdf_writes_a_valid_pdf(tmp_path, capsys):
    from agent.research_v1 import batch_cli

    fixture_path = Path(__file__).parent / "fixtures" / "sample_batch_payload.json"
    ingest_input = tmp_path / "sample_batch_payload.json"
    ingest_input.write_text(fixture_path.read_text(encoding="utf-8"), encoding="utf-8")

    assert batch_cli.main(["--app-root", str(tmp_path), "ingest", "--input", str(ingest_input)]) == 0
    capsys.readouterr()

    db = ResearchDatabase(str(tmp_path / "data" / "research.db"))
    batch = db.get_research_batch(1)
    assert batch is not None

    assert batch_cli.main(["--app-root", str(tmp_path), "export-pdf", "--batch-id", "1"]) == 0
    pdf_path = _extract_pdf_path(capsys.readouterr().out, tmp_path)

    data = pdf_path.read_bytes()
    assert data.startswith(b"%PDF-")
    assert pdf_path.exists()
    assert pdf_path.suffix == ".pdf"
    assert pdf_path.stat().st_size > 0


def test_export_pdf_preserves_non_ascii_content_in_html_and_pdf(tmp_path, capsys):
    from agent.research_v1 import batch_cli

    fixture_path = Path(__file__).parent / "fixtures" / "sample_batch_payload.json"
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    payload["title"] = "Boss Watchlist 中文版"
    payload["boss_summary"] = "先看 NVDA，再看 AMD。整体机会仍在，但追高要谨慎。"
    payload["tickers"][0]["top_thesis"] = "AI 需求延续，龙头地位还在。"
    payload["tickers"][0]["report"]["bottom_line"] = "这批里先看 NVDA。"
    payload["tickers"][1]["report"]["research_summary"] = "AMD 也有机会，但优先级排第二。"

    ingest_input = tmp_path / "unicode_batch_payload.json"
    ingest_input.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    assert batch_cli.main(["--app-root", str(tmp_path), "ingest", "--input", str(ingest_input)]) == 0
    capsys.readouterr()

    db = ResearchDatabase(str(tmp_path / "data" / "research.db"))
    snapshot = db.get_research_batch_with_items_and_reports(1)
    assert snapshot is not None

    html = build_batch_export_html(snapshot)
    assert "Boss Watchlist 中文版" in html
    assert "先看 NVDA，再看 AMD。整体机会仍在，但追高要谨慎。" in html
    assert "这批里先看 NVDA。" in html

    assert batch_cli.main(["--app-root", str(tmp_path), "export-pdf", "--batch-id", "1"]) == 0
    pdf_path = _extract_pdf_path(capsys.readouterr().out, tmp_path)

    data = pdf_path.read_bytes()
    assert data.startswith(b"%PDF-")
    assert pdf_path.exists()
    assert pdf_path.suffix == ".pdf"
    assert pdf_path.stat().st_size > 0
