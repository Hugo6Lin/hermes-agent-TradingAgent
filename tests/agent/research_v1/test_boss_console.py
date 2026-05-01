"""Tests for P51 boss web console and design system."""

from __future__ import annotations

import json
from pathlib import Path


def test_design_md_exists_and_has_required_sections():
    text = Path("DESIGN.md").read_text(encoding="utf-8")
    required = [
        "Product Context",
        "Aesthetic Direction",
        "Color Palette",
        "Typography",
        "Components",
        "Layout",
        "Do's and Don'ts",
        "Responsive Behavior",
        "Agent Prompt Guide",
    ]
    for section in required:
        assert section in text
    assert "--bg-page: #f6f1e8" in text
    assert "Preview sample" in text
    assert "place order" in text


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sample_governance_root(tmp_path: Path) -> Path:
    day = tmp_path / "governance" / "zeta-preview" / "2026-05-01"
    _write_json(day / "boss_preview.json", {
        "schema_version": "p49_boss_preview.1",
        "status": "boss_preview_ready",
        "as_of_date": "2026-05-01",
        "tickers": ["ZETA"],
        "live_status": "provider_ready",
        "top_candidates": ["ZETA"],
        "warnings": ["preview_sample_inputs_used"],
    })
    _write_json(day / "ZETA_BOSS_BRIEF.json", {
        "schema_version": "p50_boss_pdf_brief.1",
        "status": "boss_pdf_brief_ready",
        "ticker": "ZETA",
        "verdict": "Usable preview, not decision-grade yet.",
        "live_data_status": "Ready",
        "evidence_base_status": "Preview-only / Incomplete",
        "guardrail_status": "Caution",
        "html_path": str(day / "ZETA_BOSS_BRIEF.html"),
        "pdf_path": str(day / "ZETA_BOSS_BRIEF.pdf"),
        "manifest_path": str(day / "ZETA_BOSS_BRIEF.json"),
    })
    _write_json(day / "p44_evidence_freshness_drift_monitor.json", {
        "status": "monitor_red",
        "missing_context_patterns": ["outcome_context"],
    })
    # Create a stub PDF so pdf_status can be "ready"
    (day / "ZETA_BOSS_BRIEF.pdf").write_bytes(b"%PDF-1.4\n%stub\n")
    return tmp_path / "governance"


def test_console_model_loads_reports_from_governance_root(tmp_path: Path):
    from agent.research_v1.boss_console.console_model import build_console_model

    root = _sample_governance_root(tmp_path)
    model = build_console_model(root, as_of_date="2026-05-01", tickers=["ZETA"])
    assert model["schema_version"] == "p51_boss_console.1"
    assert model["reports"][0]["ticker"] == "ZETA"
    assert model["reports"][0]["pdf_status"] == "ready"
    assert model["evidence_health"]["overall_status"] == "monitor_red"


def test_console_renderer_outputs_required_sections_and_hides_forbidden_terms(tmp_path: Path):
    from agent.research_v1.boss_console.console_model import build_console_model
    from agent.research_v1.boss_console.console_renderer import FORBIDDEN_CONSOLE_TERMS, render_console_html

    root = _sample_governance_root(tmp_path)
    model = build_console_model(root, as_of_date="2026-05-01", tickers=["ZETA"])
    html = render_console_html(model)
    for text in ["Hermes Boss Console", "Run Boss Preview", "Report Center", "Ticker Workspace", "Evidence Matrix", "P52 Futu chart", "P52 watchlist heatmap"]:
        assert text in html
    for term in FORBIDDEN_CONSOLE_TERMS:
        assert term not in html
