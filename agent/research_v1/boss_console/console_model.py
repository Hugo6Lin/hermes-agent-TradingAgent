"""Build P51 boss console models from existing artifacts."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

P51_SCHEMA_VERSION = "p51_boss_console.1"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _iter_preview_dirs(governance_root: Path) -> list[Path]:
    root = Path(governance_root)
    if not root.exists() or not root.is_dir():
        return []
    return sorted(
        [p.parent for p in root.rglob("boss_preview.json")],
        key=lambda p: str(p),
        reverse=True,
    )


def _ticker_allowed(ticker: str, tickers: list[str] | None) -> bool:
    if not tickers:
        return True
    allowed = {t.strip().upper() for t in tickers if t.strip()}
    return ticker.upper() in allowed


def _report_from_dir(day_dir: Path, tickers: list[str] | None) -> dict[str, Any] | None:
    boss = _read_json(day_dir / "boss_preview.json") or {}
    brief_files = sorted(day_dir.glob("*_BOSS_BRIEF.json"))
    ticker = ""
    brief: dict[str, Any] = {}
    if brief_files:
        brief = _read_json(brief_files[0]) or {}
        ticker = str(brief.get("ticker", "")).upper()
    if not ticker:
        candidates = boss.get("tickers") or boss.get("top_candidates") or []
        ticker = str(candidates[0]).upper() if candidates else ""
    if not ticker or not _ticker_allowed(ticker, tickers):
        return None
    pdf_path = brief.get("pdf_path") or str(day_dir / f"{ticker}_BOSS_BRIEF.pdf")
    html_path = brief.get("html_path") or str(day_dir / f"{ticker}_BOSS_BRIEF.html")
    pdf_status = "ready" if pdf_path and Path(pdf_path).exists() else "missing"
    return {
        "ticker": ticker,
        "as_of_date": boss.get("as_of_date") or day_dir.name,
        "preview_status": boss.get("status", "unknown"),
        "brief_status": brief.get("status", "missing"),
        "verdict": brief.get("verdict") or boss.get("boss_summary", ""),
        "live_data_status": brief.get("live_data_status") or boss.get("live_status", "unknown"),
        "evidence_base_status": brief.get("evidence_base_status", "unknown"),
        "guardrail_status": brief.get("guardrail_status", "unknown"),
        "pdf_path": pdf_path,
        "html_path": html_path,
        "pdf_status": pdf_status,
        "preview_dir": str(day_dir),
        "sample": "preview_sample_inputs_used" in boss.get("warnings", []),
    }


def _evidence_health(preview_dirs: list[Path]) -> dict[str, Any]:
    statuses = []
    missing = []
    for day_dir in preview_dirs:
        monitor = _read_json(day_dir / "p44_evidence_freshness_drift_monitor.json") or {}
        if monitor:
            statuses.append(monitor.get("status", "unknown"))
            missing.extend(monitor.get("missing_context_patterns") or [])
    if "monitor_red" in statuses:
        overall = "monitor_red"
    elif statuses:
        overall = statuses[0]
    else:
        overall = "missing"
    return {"overall_status": overall, "missing_context_patterns": sorted(set(missing))}


def build_console_model(
    governance_root: Path,
    as_of_date: str | None = None,
    tickers: list[str] | None = None,
) -> dict[str, Any]:
    dirs = _iter_preview_dirs(governance_root)
    if as_of_date:
        dirs = [d for d in dirs if d.name == as_of_date]
    reports = []
    for day_dir in dirs:
        report = _report_from_dir(day_dir, tickers)
        if report:
            reports.append(report)
    return {
        "schema_version": P51_SCHEMA_VERSION,
        "created_at": _now(),
        "as_of_date": as_of_date or "",
        "governance_root": str(governance_root),
        "market_tape": [],
        "reports": reports,
        "ticker_workspaces": reports,
        "evidence_health": _evidence_health(dirs),
        "warnings": [] if Path(governance_root).is_dir() else ["governance_root_invalid"],
    }
