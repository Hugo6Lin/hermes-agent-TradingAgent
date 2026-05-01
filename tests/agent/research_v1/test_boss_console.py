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


def test_console_runtime_writes_html_and_json(tmp_path: Path):
    from agent.research_v1.boss_console.console_runtime import run_boss_console

    root = _sample_governance_root(tmp_path)
    output = tmp_path / "console"
    result = run_boss_console(root, output, as_of_date="2026-05-01", tickers=["ZETA"])
    assert result["status"] == "boss_console_ready"
    assert Path(result["html_path"]).exists()
    assert Path(result["json_path"]).exists()


def test_console_runtime_blocks_invalid_governance_root(tmp_path: Path):
    from agent.research_v1.boss_console.console_runtime import run_boss_console

    result = run_boss_console(tmp_path / "missing", tmp_path / "console")
    assert result["status"] == "boss_console_blocked_invalid_input"
    assert "governance_root_missing" in result["warnings"]


# ---------------------------------------------------------------------------
# P51 review fix 1: multiple *_BOSS_BRIEF.json files per preview directory
# ---------------------------------------------------------------------------

def _multi_brief_governance_root(tmp_path: Path) -> Path:
    day = tmp_path / "governance" / "2026-05-01"
    _write_json(day / "boss_preview.json", {
        "schema_version": "p49_boss_preview.1",
        "status": "boss_preview_ready",
        "as_of_date": "2026-05-01",
        "tickers": ["ZETA", "AAPL"],
        "live_status": "provider_ready",
        "top_candidates": ["ZETA", "AAPL"],
        "warnings": [],
    })
    _write_json(day / "ZETA_BOSS_BRIEF.json", {
        "status": "boss_pdf_brief_ready",
        "ticker": "ZETA",
        "verdict": "ZETA verdict.",
        "live_data_status": "Ready",
        "evidence_base_status": "Preview-only / Incomplete",
        "guardrail_status": "Caution",
        "html_path": str(day / "ZETA_BOSS_BRIEF.html"),
        "pdf_path": str(day / "ZETA_BOSS_BRIEF.pdf"),
    })
    _write_json(day / "AAPL_BOSS_BRIEF.json", {
        "status": "boss_pdf_brief_ready",
        "ticker": "AAPL",
        "verdict": "AAPL verdict.",
        "live_data_status": "Ready",
        "evidence_base_status": "Decision-grade",
        "guardrail_status": "Clear",
        "html_path": str(day / "AAPL_BOSS_BRIEF.html"),
        "pdf_path": str(day / "AAPL_BOSS_BRIEF.pdf"),
    })
    (day / "ZETA_BOSS_BRIEF.pdf").write_bytes(b"%PDF-1.4\n%stub\n")
    (day / "AAPL_BOSS_BRIEF.pdf").write_bytes(b"%PDF-1.4\n%stub\n")
    return tmp_path / "governance"


def test_multiple_brief_files_emit_separate_reports(tmp_path: Path):
    from agent.research_v1.boss_console.console_model import build_console_model

    root = _multi_brief_governance_root(tmp_path)
    model = build_console_model(root, as_of_date="2026-05-01")
    tickers = {r["ticker"] for r in model["reports"]}
    assert "ZETA" in tickers
    assert "AAPL" in tickers
    assert len(model["reports"]) == 2


def test_multiple_brief_files_tickers_filter(tmp_path: Path):
    from agent.research_v1.boss_console.console_model import build_console_model

    root = _multi_brief_governance_root(tmp_path)
    model = build_console_model(root, as_of_date="2026-05-01", tickers=["ZETA"])
    tickers = {r["ticker"] for r in model["reports"]}
    assert tickers == {"ZETA"}


# ---------------------------------------------------------------------------
# P51 review fix 2: html_status based on file existence
# ---------------------------------------------------------------------------

def test_html_status_missing_when_file_absent(tmp_path: Path):
    from agent.research_v1.boss_console.console_model import build_console_model
    from agent.research_v1.boss_console.console_renderer import render_console_html

    root = _sample_governance_root(tmp_path)
    # The fixture creates ZETA_BOSS_BRIEF.pdf but NOT ZETA_BOSS_BRIEF.html
    model = build_console_model(root, as_of_date="2026-05-01", tickers=["ZETA"])
    report = model["reports"][0]
    assert report["html_status"] == "missing"
    html = render_console_html(model)
    assert "HTML missing" in html


def test_html_status_ready_when_file_exists(tmp_path: Path):
    from agent.research_v1.boss_console.console_model import build_console_model

    root = _sample_governance_root(tmp_path)
    day = root / "zeta-preview" / "2026-05-01"
    (day / "ZETA_BOSS_BRIEF.html").write_text("<html></html>", encoding="utf-8")
    model = build_console_model(root, as_of_date="2026-05-01", tickers=["ZETA"])
    report = model["reports"][0]
    assert report["html_status"] == "ready"


# ---------------------------------------------------------------------------
# P51 review fix 3: boss-facing status label reduction
# ---------------------------------------------------------------------------

_RAW_CODES_SHOULD_NOT_APPEAR = [
    "provider_ready",
    "boss_preview_ready",
    "monitor_red",
    "boss_pdf_brief_ready",
    "preview-only / incomplete",
]


def test_rendered_html_reduces_raw_status_codes(tmp_path: Path):
    from agent.research_v1.boss_console.console_model import build_console_model
    from agent.research_v1.boss_console.console_renderer import render_console_html

    root = _sample_governance_root(tmp_path)
    model = build_console_model(root, as_of_date="2026-05-01", tickers=["ZETA"])
    html = render_console_html(model)
    for code in _RAW_CODES_SHOULD_NOT_APPEAR:
        assert code not in html, f"raw code {code!r} should be reduced before rendering"


_MATRIX_RAW_CODES = [
    "provider_ready",
    "preview-only / incomplete",
    "missing",
    "unknown",
]


def test_evidence_matrix_reduces_raw_status_codes(tmp_path: Path):
    from agent.research_v1.boss_console.console_model import build_console_model
    from agent.research_v1.boss_console.console_renderer import render_console_html

    root = _sample_governance_root(tmp_path)
    model = build_console_model(root, as_of_date="2026-05-01", tickers=["ZETA"])
    html = render_console_html(model)
    matrix = html.split('Evidence Matrix')[1].split('</table>')[0]
    for code in _MATRIX_RAW_CODES:
        assert code not in matrix, f"raw code {code!r} found in Evidence Matrix"


def test_console_uses_p52_visual_assets_when_present(tmp_path: Path):
    from agent.research_v1.boss_console.console_model import build_console_model
    from agent.research_v1.boss_console.console_renderer import render_console_html

    root = _sample_governance_root(tmp_path)
    day = root / "zeta-preview" / "2026-05-01"
    assets = day / "p52_assets"
    assets.mkdir()
    kline = assets / "ZETA_kline.svg"
    heatmap = assets / "watchlist_heatmap.svg"
    kline.write_text("<svg><text>ZETA K-line</text></svg>", encoding="utf-8")
    heatmap.write_text("<svg><text>Watchlist Heatmap</text></svg>", encoding="utf-8")
    _write_json(day / "p52_market_visual_snapshot.json", {
        "schema_version": "p52_market_visual_assets.1",
        "status": "visual_assets_ready",
        "as_of_date": "2026-05-01",
        "tickers": ["ZETA"],
        "ticker_visuals": [{
            "ticker": "ZETA",
            "data_status": "visual_ready",
            "asset_paths": {"kline_svg": str(kline)},
        }],
        "heatmap": {"asset_path": str(heatmap), "metric": "return_20d"},
        "warnings": [],
    })
    model = build_console_model(root, as_of_date="2026-05-01", tickers=["ZETA"])
    assert model["reports"][0]["visual_assets"]["kline_svg"] == str(kline)
    html = render_console_html(model)
    assert "ZETA K-line" in html
    assert "Watchlist Heatmap" in html
    assert "P52 Futu chart slot" not in html
