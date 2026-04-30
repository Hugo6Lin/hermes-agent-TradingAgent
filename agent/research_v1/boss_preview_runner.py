"""P49 one-command boss preview runner."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable

P49_SCHEMA_VERSION = "p49_boss_preview.1"
P49_DISCLAIMER = (
    "P49 is a boss preview runner only. It does not submit orders, approve "
    "production adoption, train models, schedule jobs, call final_judge, or "
    "change research decisions."
)
TICKER_RE = re.compile(r"^(US\.)?[A-Z0-9._-]{1,20}$|^HK\.\d{5}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_preview_tickers(tickers: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in tickers:
        ticker = str(raw).strip().upper()
        if ticker and ticker not in seen:
            seen.add(ticker)
            out.append(ticker)
    return out


def futu_symbols_for_tickers(tickers: list[str]) -> list[str]:
    symbols = []
    for ticker in normalize_preview_tickers(tickers):
        if ticker.startswith(("US.", "HK.", "SH.", "SZ.", "SG.")):
            symbols.append(ticker)
        elif ticker.isalpha():
            symbols.append(f"US.{ticker}")
    return symbols


def normalize_output_root(output_root: Path, as_of_date: str) -> tuple[Path, list[str]]:
    root = Path(output_root)
    warnings: list[str] = []
    if root.name == as_of_date and DATE_RE.match(root.name):
        root = root.parent
        warnings.append("normalized_date_suffixed_output_root")
    return root, warnings


def validate_boss_preview_inputs(tickers: list[str], as_of_date: str, max_candidates: int, governance_root: Path) -> dict[str, Any]:
    warnings: list[str] = []
    try:
        date.fromisoformat(as_of_date)
    except (TypeError, ValueError):
        warnings.append(f"invalid_as_of_date:{as_of_date}")
    normalized = normalize_preview_tickers(tickers)
    if not normalized:
        warnings.append("empty_ticker_list")
    for ticker in normalized:
        if not TICKER_RE.match(ticker):
            warnings.append(f"invalid_ticker:{ticker}")
    if max_candidates <= 0:
        warnings.append("max_candidates_must_be_positive")
    if governance_root.exists() and not governance_root.is_dir():
        warnings.append("governance_root_not_a_directory")
    if warnings:
        return {"schema_version": P49_SCHEMA_VERSION, "status": "boss_preview_blocked_invalid_input", "tickers": normalized, "warnings": warnings}
    return {"status": "valid", "tickers": normalized, "warnings": []}


def _sha(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


def build_boss_preview_report(as_of_date: str, tickers: list[str], live_requested: bool, phase_results: list[dict[str, Any]], warnings: list[str]) -> dict[str, Any]:
    p45 = next((p for p in phase_results if p.get("phase_id") == "P45"), {})
    p39 = next((p for p in phase_results if p.get("phase_id") == "P39"), {})
    p42 = next((p for p in phase_results if p.get("phase_id") == "P42"), {})
    top = [p39.get("top_candidate")] if p39.get("top_candidate") else []
    ready = p45.get("status") in {"provider_ready", "provider_degraded"} and bool(top) and bool(p42.get("artifact_paths"))
    status = "boss_preview_ready" if ready else "boss_preview_limited"
    seed = {"schema_version": P49_SCHEMA_VERSION, "as_of_date": as_of_date, "tickers": tickers, "live_requested": live_requested, "phase_results": phase_results, "warnings": warnings}
    source_hash = _sha(seed)
    return {
        "schema_version": P49_SCHEMA_VERSION,
        "preview_id": f"p49-{as_of_date}-{source_hash[:12]}",
        "as_of_date": as_of_date,
        "created_at": utc_now_iso(),
        "status": status,
        "tickers": normalize_preview_tickers(tickers),
        "live_requested": live_requested,
        "live_status": p45.get("status", "not_run"),
        "top_candidates": top,
        "boss_summary": "Hermes produced a limited boss preview." if status != "boss_preview_ready" else "Hermes produced a boss preview with live data readiness and candidates.",
        "phase_results": phase_results,
        "data_source_breakdown": _data_source_breakdown(phase_results),
        "missing_or_stale_evidence": [w for w in warnings if "missing" in w or "stale" in w],
        "what_to_inspect_first": _what_to_inspect_first(phase_results),
        "hard_boundary_compliance": _hard_boundary_compliance(),
        "artifact_paths": [path for phase in phase_results for path in phase.get("artifact_paths", [])],
        "warnings": sorted(set(warnings)),
        "source_hash": source_hash,
        "disclaimer": P49_DISCLAIMER,
    }


def _data_source_breakdown(phase_results: list[dict[str, Any]]) -> dict[str, list[str]]:
    out = {"live": [], "database": [], "sample": [], "missing": []}
    for phase in phase_results:
        source = phase.get("data_source", "missing")
        out.setdefault(source, []).append(phase.get("phase_id", "unknown"))
    return out


def _what_to_inspect_first(phase_results: list[dict[str, Any]]) -> list[str]:
    order = ["boss_preview.md", "p42_boss_copilot_daily_brief.md", "p39_candidate_pool.md", "p44_evidence_freshness_drift_monitor.md", "p48_research_context_prompt_pack.md"]
    return order


def _hard_boundary_compliance() -> dict[str, bool]:
    return {
        "no_auto_trading": True,
        "no_broker_orders": True,
        "no_production_approval": True,
        "no_model_training": True,
        "no_scheduler": True,
        "no_final_judge": True,
        "no_hermes_research_app_run": True,
    }


def render_boss_preview_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Hermes Boss Preview",
        "",
        "## Plain-English Verdict",
        "",
        report.get("boss_summary", ""),
        "",
        "## Today's Top Candidates",
    ]
    lines.extend([f"- {ticker}" for ticker in report.get("top_candidates", [])] or ["- No candidate reached preview-ready status."])
    lines.extend(["", "## Market/Data Status", "", f"- Live requested: {report.get('live_requested')}", f"- Live status: {report.get('live_status')}"])
    lines.extend(["", "## What Hermes Produced"])
    for phase in report.get("phase_results", []):
        lines.append(f"- {phase.get('phase_id')}: {phase.get('status')} — {phase.get('boss_summary', '')}")
    lines.extend(["", "## Live vs Sample vs Missing"])
    for key, phases in report.get("data_source_breakdown", {}).items():
        lines.append(f"- {key}: {', '.join(phases) if phases else 'none'}")
    lines.extend(["", "## What The Boss Should Inspect First"])
    lines.extend([f"- {item}" for item in report.get("what_to_inspect_first", [])])
    lines.extend(["", "## Hard Boundary Compliance"])
    for key, ok in report.get("hard_boundary_compliance", {}).items():
        lines.append(f"- {key}: {'yes' if ok else 'no'}")
    lines.extend(["", "## Artifact Links"])
    lines.extend([f"- {path}" for path in report.get("artifact_paths", [])] or ["- none"])
    lines.extend(["", "## Technical Appendix"])
    lines.extend([f"- warning: {w}" for w in report.get("warnings", [])] or ["- no warnings"])
    lines.extend(["", "## Disclaimer", "", report.get("disclaimer", P49_DISCLAIMER), ""])
    return "\n".join(lines)


def write_boss_preview_report(report: dict[str, Any], output_root: Path) -> dict[str, Path]:
    output_dir = Path(output_root) / report["as_of_date"]
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "boss_preview.json"
    md_path = output_dir / "boss_preview.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    md_path.write_text(render_boss_preview_markdown(report), encoding="utf-8")
    return {"json": json_path, "md": md_path}
