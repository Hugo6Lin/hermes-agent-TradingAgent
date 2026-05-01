"""Tests for P50 boss PDF brief renderer."""

from __future__ import annotations

import json
from pathlib import Path

from agent.research_v1.boss_pdf_brief_renderer import (
    P50_SCHEMA_VERSION,
    FORBIDDEN_MAIN_BODY_TERMS,
    classify_boss_brief,
    load_preview_artifacts,
    render_boss_brief_html,
    validate_boss_pdf_brief_inputs,
    write_boss_brief_outputs,
    run_boss_pdf_brief,
)


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _preview_dir(tmp_path: Path) -> Path:
    root = tmp_path / "preview" / "2026-05-01"
    root.mkdir(parents=True)
    _write_json(root / "boss_preview.json", {
        "status": "boss_preview_ready",
        "ticker": "ZETA",
        "tickers": ["ZETA"],
        "as_of_date": "2026-05-01",
        "live_requested": True,
        "live_status": "provider_ready",
        "top_candidates": ["ZETA"],
        "warnings": ["preview_sample_inputs_used"],
    })
    _write_json(root / "p45_market_data_readiness.json", {
        "status": "provider_ready",
        "checks": [{"name": "snapshot", "status": "passed"}, {"name": "history", "status": "passed"}],
    })
    _write_json(root / "p37_market_regime_snapshot.json", {
        "status": "completed",
        "regime_label": "risk_on_broad",
        "confidence": 1.0,
        "proxy_metrics": {"SPY": {"return_20d": 0.0968}},
        "breadth": {"sector_positive_20d_ratio": 0.91},
    })
    _write_json(root / "p39_candidate_pool.json", {
        "status": "completed",
        "top_candidate": "ZETA",
        "candidate_count": 1,
        "candidates": [{"ticker": "ZETA", "rank": 1, "score": 0.65, "category": "quality_momentum"}],
    })
    _write_json(root / "p41_decision_journal.json", {
        "status": "completed",
        "entries": [{"ticker": "ZETA", "severity": "caution", "guardrail_flags": ["missing_outcome_context"]}],
    })
    _write_json(root / "p44_evidence_freshness_drift_monitor.json", {
        "status": "monitor_red",
        "missing_context_patterns": ["outcome_context"],
    })
    return root


def test_validate_blocks_missing_preview_dir(tmp_path: Path):
    result = validate_boss_pdf_brief_inputs(tmp_path / "missing", "ZETA", None, 3)
    assert result["status"] == "boss_pdf_brief_blocked_invalid_input"
    assert "preview_dir_missing" in result["warnings"]


def test_load_preview_artifacts_requires_boss_preview_json(tmp_path: Path):
    root = tmp_path / "preview"
    root.mkdir()
    result = load_preview_artifacts(root)
    assert result["status"] == "blocked"
    assert "missing:boss_preview.json" in result["warnings"]


def test_classification_live_ready_sample_evidence_is_preview_only(tmp_path: Path):
    root = _preview_dir(tmp_path)
    loaded = load_preview_artifacts(root)
    brief = classify_boss_brief(loaded["artifacts"], ticker="ZETA", preview_dir=root)
    assert brief["schema_version"] == P50_SCHEMA_VERSION
    assert brief["live_data_status"] == "Ready"
    assert brief["market_regime_label"] == "risk_on_broad"
    assert brief["evidence_base_status"] == "Preview-only / Incomplete"
    assert brief["guardrail_status"] == "Caution"
    assert brief["verdict"] == "Usable preview, not decision-grade yet."


def test_html_contains_visual_sections_and_no_forbidden_main_terms(tmp_path: Path):
    root = _preview_dir(tmp_path)
    loaded = load_preview_artifacts(root)
    brief = classify_boss_brief(loaded["artifacts"], "ZETA", root, loaded["warnings"])
    html = render_boss_brief_html(brief)
    assert "class=\"badge" in html
    assert "class=\"score-bar" in html
    assert "Trusted" in html
    assert "Not Decision-Grade Yet" in html
    # Forbidden terms may appear in the appendix but not in the main body
    main_body = html.split('<section class="appendix">', 1)[0]
    for term in FORBIDDEN_MAIN_BODY_TERMS:
        assert term not in main_body


def test_write_outputs_with_stub_pdf_renderer(tmp_path: Path):
    root = _preview_dir(tmp_path)
    loaded = load_preview_artifacts(root)
    brief = classify_boss_brief(loaded["artifacts"], "ZETA", root, loaded["warnings"])

    def fake_pdf(html: str, pdf_path: Path) -> Path:
        pdf_path.write_bytes(b"%PDF-1.4\n%stub\n")
        return pdf_path

    result = write_boss_brief_outputs(brief, tmp_path / "out", render_pdf=True, pdf_renderer=fake_pdf)
    assert result["status"] == "boss_pdf_brief_ready"
    assert Path(result["html_path"]).exists()
    assert Path(result["pdf_path"]).read_bytes().startswith(b"%PDF-")
    assert Path(result["manifest_path"]).exists()


def test_pdf_failure_degrades_but_preserves_html(tmp_path: Path):
    root = _preview_dir(tmp_path)
    loaded = load_preview_artifacts(root)
    brief = classify_boss_brief(loaded["artifacts"], "ZETA", root, loaded["warnings"])

    def failing_pdf(html: str, pdf_path: Path) -> Path:
        raise RuntimeError("edge missing")

    result = write_boss_brief_outputs(brief, tmp_path / "out", render_pdf=True, pdf_renderer=failing_pdf)
    assert result["status"] == "boss_pdf_brief_degraded"
    assert Path(result["html_path"]).exists()
    assert result["pdf_path"] == ""
    assert "pdf_render_failed:RuntimeError" in result["warnings"]


def test_render_rejects_forbidden_trading_language_in_candidate_category(tmp_path: Path):
    root = tmp_path / "preview" / "2026-05-01"
    root.mkdir(parents=True)
    _write_json(root / "boss_preview.json", {
        "status": "boss_preview_ready",
        "ticker": "ZETA",
        "tickers": ["ZETA"],
        "as_of_date": "2026-05-01",
        "live_requested": True,
        "live_status": "provider_ready",
        "top_candidates": ["ZETA"],
        "warnings": [],
    })
    _write_json(root / "p39_candidate_pool.json", {
        "status": "completed",
        "top_candidate": "ZETA",
        "candidate_count": 1,
        "candidates": [{"ticker": "ZETA", "rank": 1, "score": 0.9, "category": "buy this now"}],
    })
    loaded = load_preview_artifacts(root)
    brief = classify_boss_brief(loaded["artifacts"], "ZETA", root, loaded["warnings"])
    import pytest
    with pytest.raises(ValueError, match="forbidden_main_body_term"):
        render_boss_brief_html(brief)


def test_classify_brief_includes_evidence_gaps(tmp_path: Path):
    root = _preview_dir(tmp_path)
    loaded = load_preview_artifacts(root)
    brief = classify_boss_brief(loaded["artifacts"], "ZETA", root, loaded["warnings"])
    gaps = brief.get("evidence_gaps", [])
    assert len(gaps) >= 11
    labels = {g["label"] for g in gaps}
    assert "Live Data" in labels
    assert "Market Regime" in labels
    assert "Fundamentals" in labels
    assert "Evidence Monitor" in labels
    # p37 is completed => Ready
    p37_gap = next(g for g in gaps if g["phase"] == "P37")
    assert p37_gap["status"] == "Ready"
    # p38 is missing => Missing
    p38_gap = next(g for g in gaps if g["phase"] == "P38")
    assert p38_gap["status"] == "Missing"


def test_html_evidence_matrix_shows_badges(tmp_path: Path):
    root = _preview_dir(tmp_path)
    loaded = load_preview_artifacts(root)
    brief = classify_boss_brief(loaded["artifacts"], "ZETA", root, loaded["warnings"])
    html = render_boss_brief_html(brief)
    assert "Evidence Matrix" in html
    assert "evidence-matrix" in html
    # Ready badge for P37
    assert ">Ready<" in html
    # Missing badge for absent phases
    assert ">Missing<" in html


def test_title_override_used_in_html(tmp_path: Path):
    root = _preview_dir(tmp_path)
    loaded = load_preview_artifacts(root)
    brief = classify_boss_brief(loaded["artifacts"], "ZETA", root, loaded["warnings"])
    brief["title"] = "Custom ZETA Analysis"
    html = render_boss_brief_html(brief)
    assert "<title>Custom ZETA Analysis</title>" in html
    assert "<h1>Custom ZETA Analysis</h1>" in html


# ---------------------------------------------------------------------------
# P55 regressions — V2.1 brief preview integration.
# ---------------------------------------------------------------------------

P55_TEN_SECOND_READ_LABELS = [
    "Verdict",
    "Price context",
    "Trusted evidence",
    "Evidence gaps",
    "Next review action",
]


def test_brief_renders_v21_ten_second_read_strip(tmp_path: Path):
    root = _preview_dir(tmp_path)
    loaded = load_preview_artifacts(root)
    brief = classify_boss_brief(loaded["artifacts"], "ZETA", root, loaded["warnings"])
    html = render_boss_brief_html(brief)
    assert "ten-second-read" in html
    # 10-second read strip must contain these meta labels above the fold.
    for label in P55_TEN_SECOND_READ_LABELS:
        assert label in html, f"missing 10-second read label: {label!r}"


def test_brief_evidence_gaps_remain_visible_and_not_collapsed(tmp_path: Path):
    root = _preview_dir(tmp_path)
    loaded = load_preview_artifacts(root)
    brief = classify_boss_brief(loaded["artifacts"], "ZETA", root, loaded["warnings"])
    html = render_boss_brief_html(brief)
    # The "do not hide" gap section must be present in the main body.
    main_body = html.split('<section class="appendix">', 1)[0]
    assert "Evidence gaps · do not hide" in main_body
    assert "evidence-gaps-detail" in main_body
    # P38 fundamentals are missing from the fixture → it must render in the
    # gap detail with a Missing badge and a one-line reason.
    gap_section = main_body.split("evidence-gaps-detail", 1)[1].split("</table>", 1)[0]
    assert "Fundamentals" in gap_section
    assert ">Missing<" in gap_section


def test_brief_uses_pdf_safe_typography_fallbacks(tmp_path: Path):
    root = _preview_dir(tmp_path)
    loaded = load_preview_artifacts(root)
    brief = classify_boss_brief(loaded["artifacts"], "ZETA", root, loaded["warnings"])
    html = render_boss_brief_html(brief)
    # No web-font (Google Fonts / unpkg) imports — PDF engines must render
    # offline using system fonts.
    assert "fonts.googleapis.com" not in html
    assert "fonts.gstatic.com" not in html
    assert "@import" not in html
    # System fallbacks must be present.
    assert "Georgia" in html
    assert "BlinkMacSystemFont" in html or "-apple-system" in html


def test_brief_does_not_leak_forbidden_trading_language(tmp_path: Path):
    root = _preview_dir(tmp_path)
    loaded = load_preview_artifacts(root)
    brief = classify_boss_brief(loaded["artifacts"], "ZETA", root, loaded["warnings"])
    html = render_boss_brief_html(brief)
    main_body = html.split('<section class="appendix">', 1)[0].lower()
    forbidden = [
        "buy now",
        "sell now",
        "place order",
        "submit order",
        "unlock trade",
        "follow this trade",
        "guaranteed edge",
        "production approved",
        "model promoted",
    ]
    for phrase in forbidden:
        assert phrase not in main_body, f"forbidden phrase leaked: {phrase!r}"
