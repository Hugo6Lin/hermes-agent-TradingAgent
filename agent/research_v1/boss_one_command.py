"""P53 one-command boss console orchestration."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable

P53_SCHEMA_VERSION = "p53_boss_one_command.1"
STATUS_READY = "boss_one_command_ready"
STATUS_HTML_ONLY = "boss_one_command_ready_html_only"
STATUS_DEGRADED = "boss_one_command_degraded"
STATUS_INVALID = "boss_one_command_blocked_invalid_input"
P53_DISCLAIMER = (
    "P53 is a local boss-preview orchestrator. It does not recommend trades, "
    "submit orders, unlock trading, query positions, approve production adoption, "
    "train models, schedule jobs, or mutate research decisions."
)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sha(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def validate_boss_one_command_inputs(
    *,
    tickers: list[str],
    as_of_date: str,
    output_root: Path,
    governance_root: Path,
    history_days: int,
    max_candidates: int,
    port: int,
) -> list[str]:
    errors: list[str] = []
    try:
        date.fromisoformat(as_of_date)
    except (TypeError, ValueError):
        errors.append("invalid_date_format")
    if not tickers:
        errors.append("tickers_required")
    for ticker in tickers:
        clean = str(ticker).strip().upper()
        if not clean or any(ch in clean for ch in "<>\"' "):
            errors.append(f"invalid_ticker:{ticker}")
    if history_days < 20:
        errors.append("history_days_minimum_20")
    if max_candidates <= 0:
        errors.append("max_candidates_must_be_positive")
    if not isinstance(port, int) or port <= 0 or port > 65535:
        errors.append("invalid_port")
    if Path(output_root).exists() and not Path(output_root).is_dir():
        errors.append("output_root_not_directory")
    if Path(governance_root).exists() and not Path(governance_root).is_dir():
        errors.append("governance_root_not_directory")
    return errors


def normalize_tickers(tickers: list[str]) -> list[str]:
    return [str(t).strip().upper() for t in tickers if str(t).strip()]


def default_run_id(as_of_date: str, tickers: list[str]) -> str:
    joined = "-".join(tickers).lower()
    safe = re.sub(r"[^a-z0-9]+", "-", joined).strip("-")
    return f"boss-{as_of_date}-{safe}"


def normalize_boss_output_root(output_root: Path, as_of_date: str) -> Path:
    root = Path(output_root)
    return root if root.name == as_of_date else root / as_of_date


def _classify(render_pdf: bool, console: dict, briefs: list[dict]) -> str:
    console_ok = console.get("status") == "boss_console_ready" and bool(console.get("html_path"))
    if not console_ok:
        return STATUS_DEGRADED
    if not render_pdf:
        return STATUS_HTML_ONLY
    all_ready = bool(briefs) and all(
        b.get("status") == "boss_pdf_brief_ready" and b.get("pdf_path") for b in briefs
    )
    return STATUS_READY if all_ready else STATUS_DEGRADED


def _default_runners() -> dict[str, Callable[..., dict]]:
    from agent.research_v1.boss_preview_runner import run_boss_preview
    from agent.research_v1.market_visual_assets import run_market_visual_assets
    from agent.research_v1.boss_pdf_brief_renderer import run_boss_pdf_brief
    from agent.research_v1.boss_console.console_runtime import run_boss_console

    return {
        "P49": run_boss_preview,
        "P52": run_market_visual_assets,
        "P50": run_boss_pdf_brief,
        "P51": run_boss_console,
    }


def write_boss_one_command_summary(summary: dict[str, Any], output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "p53_boss_one_command_summary.json"
    md_path = output_dir / "p53_boss_one_command_summary.md"
    json_path.write_text(json.dumps(summary, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    lines = [
        "# P53 Boss One-Command Summary",
        "",
        f"Status: {summary.get('status', '')}",
        f"As of: {summary.get('as_of_date', '')}",
        f"Console: {summary.get('console', {}).get('html_path', '')}",
        "",
        "## Briefs",
    ]
    for brief in summary.get("briefs", []):
        lines.append(
            f"- {brief.get('ticker', '')}: PDF={brief.get('pdf_path') or 'not generated'} HTML={brief.get('html_path') or 'not generated'}"
        )
    lines.extend(["", "## Warnings"])
    lines.extend([f"- {w}" for w in summary.get("warnings", [])] or ["- none"])
    lines.extend(["", "---", "", f"> {P53_DISCLAIMER}", ""])
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return {"json": str(json_path), "md": str(md_path)}


def run_boss_one_command(
    *,
    db: Any,
    tickers: list[str],
    as_of_date: str,
    output_root: Path,
    governance_root: Path,
    run_id: str | None = None,
    live: bool = True,
    render_pdf: bool = True,
    history_days: int = 120,
    max_candidates: int = 8,
    host: str = "127.0.0.1",
    port: int = 11111,
    runners: dict[str, Callable[..., dict]] | None = None,
) -> dict:
    normalized = normalize_tickers(tickers)
    errors = validate_boss_one_command_inputs(
        tickers=normalized,
        as_of_date=as_of_date,
        output_root=output_root,
        governance_root=governance_root,
        history_days=history_days,
        max_candidates=max_candidates,
        port=port,
    )
    if errors:
        return {
            "schema_version": P53_SCHEMA_VERSION,
            "status": STATUS_INVALID,
            "as_of_date": as_of_date,
            "tickers": normalized,
            "run_id": "",
            "console": {},
            "preview": {},
            "visuals": {},
            "briefs": [],
            "warnings": errors,
            "source_hash": _sha(errors),
            "summary_json_path": "",
            "summary_md_path": "",
        }

    rid = run_id or default_run_id(as_of_date, normalized)
    governance_run_root = Path(governance_root) / rid
    preview_dir = governance_run_root / as_of_date
    boss_output_dir = normalize_boss_output_root(Path(output_root), as_of_date)
    runners = runners or _default_runners()

    all_warnings: list[str] = []
    child_hashes: dict[str, str] = {}

    # --- P49 ---
    try:
        p49_result = runners["P49"](
            db=db,
            tickers=normalized,
            as_of_date=as_of_date,
            output_root=governance_run_root,
            governance_root=governance_run_root,
            live=live,
            max_candidates=max_candidates,
        )
    except Exception as exc:
        return {
            "schema_version": P53_SCHEMA_VERSION,
            "status": STATUS_INVALID,
            "as_of_date": as_of_date,
            "tickers": normalized,
            "run_id": rid,
            "console": {},
            "preview": {"status": "error", "error": str(exc)},
            "visuals": {},
            "briefs": [],
            "warnings": [f"p49_error:{exc}"],
            "source_hash": _sha(str(exc)),
            "summary_json_path": "",
            "summary_md_path": "",
        }

    if p49_result.get("status", "").endswith("blocked_invalid_input"):
        return {
            "schema_version": P53_SCHEMA_VERSION,
            "status": STATUS_INVALID,
            "as_of_date": as_of_date,
            "tickers": normalized,
            "run_id": rid,
            "console": {},
            "preview": {"status": p49_result.get("status", "")},
            "visuals": {},
            "briefs": [],
            "warnings": p49_result.get("warnings", []),
            "source_hash": _sha(p49_result.get("source_hash", "")),
            "summary_json_path": "",
            "summary_md_path": "",
        }

    all_warnings.extend(p49_result.get("warnings", []))
    child_hashes["P49"] = p49_result.get("source_hash", "")

    # --- P52 ---
    try:
        p52_result = runners["P52"](
            tickers=normalized,
            as_of_date=as_of_date,
            output_root=governance_run_root,
            history_days=history_days,
            live=live,
            host=host,
            port=port,
            db=db,
        )
    except Exception as exc:
        p52_result = {"status": "visual_assets_missing_data", "warnings": [f"p52_error:{exc}"], "source_hash": "", "artifact_paths": []}

    all_warnings.extend(p52_result.get("warnings", []))
    child_hashes["P52"] = p52_result.get("source_hash", "")

    # --- P50 per ticker ---
    briefs: list[dict] = []
    for ticker in normalized:
        try:
            p50_result = runners["P50"](
                preview_dir=preview_dir,
                ticker=ticker,
                output_dir=preview_dir,
                title=f"{ticker} Boss Brief",
                render_pdf=render_pdf,
            )
        except Exception as exc:
            p50_result = {
                "status": "boss_pdf_brief_degraded",
                "ticker": ticker,
                "html_path": "",
                "pdf_path": "",
                "manifest_path": "",
                "warnings": [f"p50_error:{exc}"],
                "source_hash": "",
            }

        all_warnings.extend(p50_result.get("warnings", []))
        child_hashes[f"P50:{ticker}"] = p50_result.get("source_hash", "")
        briefs.append({
            "ticker": ticker,
            "status": p50_result.get("status", "boss_pdf_brief_degraded"),
            "pdf_path": p50_result.get("pdf_path", ""),
            "html_path": p50_result.get("html_path", ""),
            "manifest_path": p50_result.get("manifest_path", ""),
            "source_hash": p50_result.get("source_hash", ""),
        })

    # --- P51 ---
    try:
        p51_result = runners["P51"](
            governance_root=governance_run_root,
            output_dir=boss_output_dir,
            as_of_date=as_of_date,
            tickers=normalized,
        )
    except Exception as exc:
        p51_result = {"status": "boss_console_error", "html_path": "", "json_path": "", "warnings": [f"p51_error:{exc}"]}

    all_warnings.extend(p51_result.get("warnings", []))

    console = {
        "html_path": p51_result.get("html_path", ""),
        "json_path": p51_result.get("json_path", ""),
        "status": p51_result.get("status", ""),
    }

    status = _classify(render_pdf, console, briefs)

    hash_seed = {
        "as_of_date": as_of_date,
        "tickers": normalized,
        "run_id": rid,
        "child_hashes": child_hashes,
        "brief_statuses": [(b["ticker"], b["status"]) for b in briefs],
        "console_status": console.get("status", ""),
        "warnings": all_warnings,
    }
    source_hash = _sha(hash_seed)

    summary = {
        "schema_version": P53_SCHEMA_VERSION,
        "status": status,
        "as_of_date": as_of_date,
        "tickers": normalized,
        "run_id": rid,
        "console": console,
        "preview": {
            "status": p49_result.get("status", ""),
            "preview_dir": str(preview_dir),
            "source_hash": child_hashes.get("P49", ""),
        },
        "visuals": {
            "status": p52_result.get("status", ""),
            "artifact_paths": p52_result.get("artifact_paths", []),
            "source_hash": child_hashes.get("P52", ""),
        },
        "briefs": briefs,
        "warnings": all_warnings,
        "source_hash": source_hash,
        "disclaimer": P53_DISCLAIMER,
    }

    paths = write_boss_one_command_summary(summary, boss_output_dir)
    summary["summary_json_path"] = paths["json"]
    summary["summary_md_path"] = paths["md"]
    return summary
