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
