"""Tests for P53 boss one-command console orchestrator."""

from __future__ import annotations

import json
from pathlib import Path

from agent.research_v1.boss_one_command import (
    P53_SCHEMA_VERSION,
    default_run_id,
    normalize_boss_output_root,
    run_boss_one_command,
    validate_boss_one_command_inputs,
)


class FakeDB:
    pass


def _fake_runners(calls: list[tuple[str, dict]], tmp_path: Path):
    def p49(**kwargs):
        calls.append(("P49", kwargs))
        preview_dir = Path(kwargs["output_root"]) / kwargs["as_of_date"]
        preview_dir.mkdir(parents=True, exist_ok=True)
        (preview_dir / "boss_preview.json").write_text("{}", encoding="utf-8")
        return {
            "status": "boss_preview_ready",
            "preview_id": "p49-test",
            "tickers": kwargs["tickers"],
            "artifact_paths": [str(preview_dir / "boss_preview.json")],
            "warnings": [],
            "source_hash": "p49hash",
        }

    def p52(**kwargs):
        calls.append(("P52", kwargs))
        out = Path(kwargs["output_root"]) / kwargs["as_of_date"]
        out.mkdir(parents=True, exist_ok=True)
        p = out / "p52_market_visual_snapshot.json"
        p.write_text("{}", encoding="utf-8")
        return {
            "status": "visual_assets_ready",
            "output_dir": str(out),
            "artifact_paths": [str(p)],
            "warnings": [],
            "source_hash": "p52hash",
        }

    def p50(**kwargs):
        calls.append(("P50", kwargs))
        ticker = kwargs["ticker"]
        out = Path(kwargs["output_dir"])
        out.mkdir(parents=True, exist_ok=True)
        html = out / f"{ticker}_BOSS_BRIEF.html"
        pdf = out / f"{ticker}_BOSS_BRIEF.pdf"
        manifest = out / f"{ticker}_BOSS_BRIEF.json"
        html.write_text("<html></html>", encoding="utf-8")
        pdf.write_bytes(b"%PDF-1.4\n")
        manifest.write_text("{}", encoding="utf-8")
        return {
            "status": "boss_pdf_brief_ready",
            "ticker": ticker,
            "html_path": str(html),
            "pdf_path": str(pdf),
            "manifest_path": str(manifest),
            "warnings": [],
            "source_hash": f"p50hash-{ticker}",
        }

    def p51(**kwargs):
        calls.append(("P51", kwargs))
        out = Path(kwargs["output_dir"])
        out.mkdir(parents=True, exist_ok=True)
        html = out / "boss_console.html"
        js = out / "boss_console.json"
        html.write_text("<html>console</html>", encoding="utf-8")
        js.write_text("{}", encoding="utf-8")
        return {
            "status": "boss_console_ready",
            "html_path": str(html),
            "json_path": str(js),
            "report_count": 2,
            "warnings": [],
        }

    return {"P49": p49, "P52": p52, "P50": p50, "P51": p51}


def test_validate_blocks_invalid_input(tmp_path: Path):
    errors = validate_boss_one_command_inputs(
        tickers=[],
        as_of_date="bad-date",
        output_root=tmp_path / "out",
        governance_root=tmp_path / "gov",
        history_days=5,
        max_candidates=0,
        port=70000,
    )
    assert "tickers_required" in errors
    assert "invalid_date_format" in errors
    assert "history_days_minimum_20" in errors
    assert "max_candidates_must_be_positive" in errors
    assert "invalid_port" in errors


def test_default_run_id_is_stable_and_safe():
    assert default_run_id("2026-05-01", ["US.ZETA", "NVDA"]) == "boss-2026-05-01-us-zeta-nvda"


def test_output_root_does_not_double_append_date(tmp_path: Path):
    root = normalize_boss_output_root(tmp_path / "output" / "boss" / "2026-05-01", "2026-05-01")
    assert root == tmp_path / "output" / "boss" / "2026-05-01"


def test_happy_path_runs_children_in_order_and_writes_summary(tmp_path: Path):
    calls: list[tuple[str, dict]] = []
    result = run_boss_one_command(
        db=FakeDB(),
        tickers=["ZETA", "NVDA"],
        as_of_date="2026-05-01",
        output_root=tmp_path / "boss",
        governance_root=tmp_path / "governance",
        live=False,
        render_pdf=True,
        history_days=60,
        max_candidates=8,
        runners=_fake_runners(calls, tmp_path),
    )
    assert result["schema_version"] == P53_SCHEMA_VERSION
    assert result["status"] == "boss_one_command_ready"
    assert [name for name, _ in calls] == ["P49", "P52", "P50", "P50", "P51"]
    assert calls[0][1]["live"] is False
    assert calls[1][1]["live"] is False
    assert len(result["briefs"]) == 2
    assert Path(result["console"]["html_path"]).exists()
    assert Path(result["summary_json_path"]).exists()
    assert Path(result["summary_md_path"]).exists()


def test_no_pdf_mode_returns_html_only_status(tmp_path: Path):
    calls: list[tuple[str, dict]] = []
    result = run_boss_one_command(
        db=FakeDB(),
        tickers=["ZETA"],
        as_of_date="2026-05-01",
        output_root=tmp_path / "boss",
        governance_root=tmp_path / "governance",
        live=False,
        render_pdf=False,
        runners=_fake_runners(calls, tmp_path),
    )
    assert result["status"] == "boss_one_command_ready_html_only"
    assert calls[2][1]["render_pdf"] is False


def test_p50_degraded_still_returns_usable_degraded_summary(tmp_path: Path):
    calls: list[tuple[str, dict]] = []
    runners = _fake_runners(calls, tmp_path)
    original_p50 = runners["P50"]

    def degraded_p50(**kwargs):
        result = original_p50(**kwargs)
        result["status"] = "boss_pdf_brief_degraded"
        result["pdf_path"] = ""
        result["warnings"] = ["pdf_render_failed:RuntimeError"]
        return result

    runners["P50"] = degraded_p50
    result = run_boss_one_command(
        db=FakeDB(),
        tickers=["ZETA"],
        as_of_date="2026-05-01",
        output_root=tmp_path / "boss",
        governance_root=tmp_path / "governance",
        runners=runners,
    )
    assert result["status"] == "boss_one_command_degraded"
    assert "pdf_render_failed:RuntimeError" in result["warnings"]
    assert result["briefs"][0]["html_path"]


def test_p51_failure_returns_degraded(tmp_path: Path):
    calls: list[tuple[str, dict]] = []
    runners = _fake_runners(calls, tmp_path)
    runners["P51"] = lambda **kwargs: {"status": "boss_console_blocked_invalid_input", "warnings": ["console_failed"]}
    result = run_boss_one_command(
        db=FakeDB(),
        tickers=["ZETA"],
        as_of_date="2026-05-01",
        output_root=tmp_path / "boss",
        governance_root=tmp_path / "governance",
        runners=runners,
    )
    assert result["status"] == "boss_one_command_degraded"
    assert "console_failed" in result["warnings"]


def test_child_source_hash_changes_p53_source_hash(tmp_path: Path):
    calls: list[tuple[str, dict]] = []
    first = run_boss_one_command(
        db=FakeDB(),
        tickers=["ZETA"],
        as_of_date="2026-05-01",
        output_root=tmp_path / "boss1",
        governance_root=tmp_path / "governance1",
        runners=_fake_runners(calls, tmp_path),
    )
    calls2: list[tuple[str, dict]] = []
    runners = _fake_runners(calls2, tmp_path)
    original_p52 = runners["P52"]

    def changed_p52(**kwargs):
        result = original_p52(**kwargs)
        result["source_hash"] = "different-p52"
        return result

    runners["P52"] = changed_p52
    second = run_boss_one_command(
        db=FakeDB(),
        tickers=["ZETA"],
        as_of_date="2026-05-01",
        output_root=tmp_path / "boss2",
        governance_root=tmp_path / "governance2",
        runners=runners,
    )
    assert first["source_hash"] != second["source_hash"]


def test_boss_one_command_hard_boundary_source_scan():
    source = Path("agent/research_v1/boss_one_command.py").read_text(encoding="utf-8")
    forbidden = [
        "OpenSecTradeContext",
        "unlock_trade",
        "place_order",
        "submit_order",
        "modify_order",
        "accinfo_query",
        "position_list_query",
        "HermesResearchApp",
        "SubagentExecutor",
        "final_judge",
        "CanonicalSignal",
        "CanonicalReport",
        "JudgeInputPacket",
    ]
    for term in forbidden:
        assert term not in source
