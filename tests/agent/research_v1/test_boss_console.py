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
    kline.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg"><text>ZETA K-line</text></svg>',
        encoding="utf-8",
    )
    heatmap.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg"><text>Watchlist Heatmap</text></svg>',
        encoding="utf-8",
    )
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


def test_malicious_svg_falls_back_to_placeholder(tmp_path: Path):
    from agent.research_v1.boss_console.console_model import build_console_model
    from agent.research_v1.boss_console.console_renderer import render_console_html

    root = _sample_governance_root(tmp_path)
    day = root / "zeta-preview" / "2026-05-01"
    assets = day / "p52_assets"
    assets.mkdir()
    kline = assets / "ZETA_kline.svg"
    heatmap = assets / "watchlist_heatmap.svg"

    # Malicious SVG with onload event handler
    kline.write_text('<svg onload="alert(1)"><text>ZETA</text></svg>', encoding="utf-8")
    heatmap.write_text("<svg><text>Heatmap</text></svg>", encoding="utf-8")
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
    html = render_console_html(model)
    # Malicious kline should fall back to placeholder
    assert "P52 Futu chart slot" in html
    assert 'alert(1)' not in html


def test_svg_with_foreignobject_falls_back(tmp_path: Path):
    from agent.research_v1.boss_console.console_model import build_console_model
    from agent.research_v1.boss_console.console_renderer import render_console_html

    root = _sample_governance_root(tmp_path)
    day = root / "zeta-preview" / "2026-05-01"
    assets = day / "p52_assets"
    assets.mkdir()
    kline = assets / "ZETA_kline.svg"
    heatmap = assets / "watchlist_heatmap.svg"

    kline.write_text('<svg><foreignObject><body>bad</body></foreignObject></svg>', encoding="utf-8")
    heatmap.write_text("<svg><text>Heatmap</text></svg>", encoding="utf-8")
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
    html = render_console_html(model)
    assert "P52 Futu chart slot" in html
    assert "foreignObject" not in html


# ---------------------------------------------------------------------------
# P55 regressions — V2.1 cockpit visual integration.
# ---------------------------------------------------------------------------

P55_V21_VISUAL_ANCHORS = [
    "cockpit-chrome",            # glass top chrome
    "brandmark",                 # Hermes wordmark block
    "Hermes",                    # wordmark text
    "Boss Console",              # nav label
    "command-region",            # command bar wrapper
    "Open workspace",            # allowed action label
    "Request brief",             # allowed action label
    "market-strip",              # market regime strip
    "Watchlist heatmap",         # heatmap card
    "Report Center",             # report center card
    "report-table",              # terminal-like report table
    "Ticker Workspace",          # workspace card
    "Evidence Matrix",           # workspace evidence matrix
    "Today's review queue",      # side rail review queue
    "Evidence health",           # side rail evidence health
]


def test_console_renders_v21_visual_anchors(tmp_path: Path):
    from agent.research_v1.boss_console.console_model import build_console_model
    from agent.research_v1.boss_console.console_renderer import render_console_html

    root = _sample_governance_root(tmp_path)
    model = build_console_model(root, as_of_date="2026-05-01", tickers=["ZETA"])
    html = render_console_html(model)
    for anchor in P55_V21_VISUAL_ANCHORS:
        assert anchor in html, f"missing v2.1 visual anchor: {anchor}"


P55_FORBIDDEN_RAW_STATUSES = [
    "provider_ready",
    "monitor_red",
    "monitor_yellow",
    "visual_assets_missing_data",
    "blocked_missing_context",
    "prompt_pack_limited",
    "boss_preview_ready",
    "boss_pdf_brief_ready",
    "preview-only / incomplete",
    "preview-only / Incomplete",
]


def test_console_does_not_leak_raw_provider_or_monitor_statuses(tmp_path: Path):
    from agent.research_v1.boss_console.console_model import build_console_model
    from agent.research_v1.boss_console.console_renderer import render_console_html

    root = _sample_governance_root(tmp_path)
    model = build_console_model(root, as_of_date="2026-05-01", tickers=["ZETA"])
    # Force-inject boss-unfriendly statuses into the model to verify the
    # renderer reduces them before emitting HTML.
    for report in model["reports"]:
        report["live_data_status"] = "provider_ready"
        report["evidence_base_status"] = "preview-only / Incomplete"
        report["guardrail_status"] = "monitor_red"
        report["preview_status"] = "boss_preview_ready"
        report["brief_status"] = "boss_pdf_brief_ready"
    model["evidence_health"]["overall_status"] = "monitor_red"
    html = render_console_html(model)
    for code in P55_FORBIDDEN_RAW_STATUSES:
        assert code not in html, f"raw status leaked into boss UI: {code!r}"


P55_FORBIDDEN_TRADING_PHRASES = [
    "buy now",
    "sell now",
    "place order",
    "submit order",
    "unlock trade",
    "trade unlock",
    "copy trade",
    "auto trade",
    "follow this trade",
    "guaranteed edge",
    "production approved",
    "model promoted",
]


def test_console_does_not_leak_trading_instruction_language(tmp_path: Path):
    from agent.research_v1.boss_console.console_model import build_console_model
    from agent.research_v1.boss_console.console_renderer import render_console_html

    root = _sample_governance_root(tmp_path)
    model = build_console_model(root, as_of_date="2026-05-01", tickers=["ZETA"])
    html = render_console_html(model)
    lowered = html.lower()
    for phrase in P55_FORBIDDEN_TRADING_PHRASES:
        assert phrase not in lowered, f"forbidden trading phrase leaked: {phrase!r}"


def test_console_renderer_blocks_forbidden_trading_phrase_in_verdict(tmp_path: Path):
    from agent.research_v1.boss_console.console_model import build_console_model
    from agent.research_v1.boss_console.console_renderer import render_console_html

    root = _sample_governance_root(tmp_path)
    model = build_console_model(root, as_of_date="2026-05-01", tickers=["ZETA"])
    # Inject a bad verdict — renderer must refuse to emit it.
    model["reports"][0]["verdict"] = "Buy now is the right move here."
    import pytest
    with pytest.raises(ValueError, match="forbidden_console_phrase:buy now"):
        render_console_html(model)


def test_console_status_badges_use_titlecased_v21_labels(tmp_path: Path):
    from agent.research_v1.boss_console.console_model import build_console_model
    from agent.research_v1.boss_console.console_renderer import render_console_html

    root = _sample_governance_root(tmp_path)
    model = build_console_model(root, as_of_date="2026-05-01", tickers=["ZETA"])
    html = render_console_html(model)
    # At least one of the boss-readable labels must appear in the matrix
    matrix = html.split("Evidence Matrix")[1].split("</table>")[0]
    allowed_labels = ["Ready", "Limited", "Stale", "Sample", "Blocked", "Missing"]
    assert any(label in matrix for label in allowed_labels), (
        f"Evidence Matrix is missing a V2.1 boss-readable label: matrix={matrix!r}"
    )
    # Lowercase variants must NOT appear inside the matrix
    for lowered in (label.lower() for label in allowed_labels):
        assert lowered not in matrix, f"matrix leaks lowercase status: {lowered!r}"


def test_svg_with_external_href_falls_back(tmp_path: Path):
    from agent.research_v1.boss_console.console_model import build_console_model
    from agent.research_v1.boss_console.console_renderer import render_console_html

    root = _sample_governance_root(tmp_path)
    day = root / "zeta-preview" / "2026-05-01"
    assets = day / "p52_assets"
    assets.mkdir()
    kline = assets / "ZETA_kline.svg"
    heatmap = assets / "watchlist_heatmap.svg"

    kline.write_text('<svg><a href="https://evil.com">link</a></svg>', encoding="utf-8")
    heatmap.write_text("<svg><text>Heatmap</text></svg>", encoding="utf-8")
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
    html = render_console_html(model)
    assert "P52 Futu chart slot" in html
    assert "evil.com" not in html
