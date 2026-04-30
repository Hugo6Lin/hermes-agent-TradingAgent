"""Tests for P49 boss preview runner."""

from __future__ import annotations

from pathlib import Path

from agent.research_v1.boss_preview_runner import (
    normalize_preview_tickers,
    normalize_output_root,
    build_boss_preview_report,
    render_boss_preview_markdown,
    validate_boss_preview_inputs,
)


def test_normalize_preview_tickers_accepts_plain_and_prefixed():
    assert normalize_preview_tickers([" nvda ", "US.AMZN", "NVDA", "HK.00700"]) == ["NVDA", "US.AMZN", "HK.00700"]


def test_validate_rejects_empty_tickers():
    result = validate_boss_preview_inputs([], "2026-05-01", 8, Path("output/governance"))
    assert result["status"] == "boss_preview_blocked_invalid_input"
    assert "empty_ticker_list" in result["warnings"]


def test_normalize_output_root_removes_date_suffix(tmp_path: Path):
    root = tmp_path / "output" / "governance" / "2026-05-01"
    normalized, warnings = normalize_output_root(root, "2026-05-01")
    assert normalized == tmp_path / "output" / "governance"
    assert "normalized_date_suffixed_output_root" in warnings


def test_boss_report_ready_when_live_and_candidate_exist(tmp_path: Path):
    report = build_boss_preview_report(
        as_of_date="2026-05-01",
        tickers=["NVDA"],
        live_requested=True,
        phase_results=[
            {"phase_id": "P45", "status": "provider_ready", "artifact_paths": ["p45.json"], "boss_summary": "Futu ready."},
            {"phase_id": "P39", "status": "completed", "candidate_count": 1, "top_candidate": "NVDA", "artifact_paths": ["p39.json"], "boss_summary": "NVDA ranked first."},
            {"phase_id": "P42", "status": "brief_ready", "artifact_paths": ["p42.json"], "boss_summary": "Brief ready."},
        ],
        warnings=[],
    )
    assert report["status"] == "boss_preview_ready"
    assert report["top_candidates"] == ["NVDA"]


def test_markdown_boss_summary_comes_before_technical_appendix():
    report = build_boss_preview_report(
        as_of_date="2026-05-01",
        tickers=["NVDA"],
        live_requested=True,
        phase_results=[],
        warnings=["sample_data_used"],
    )
    md = render_boss_preview_markdown(report)
    assert md.index("## Plain-English Verdict") < md.index("## Technical Appendix")
    assert "sample_data_used" in md
