"""P43 Read-Only Co-Pilot Console Index."""

from __future__ import annotations

import hashlib
import html
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

P43_SCHEMA_VERSION = "p43_copilot_console_index.1"
P43_STATUS_READY = "console_ready"
P43_STATUS_LIMITED_CONTEXT = "console_limited_context"
P43_STATUS_NO_ARTIFACTS = "console_no_artifacts"
P43_STATUS_BLOCKED_INVALID_INPUT = "blocked_invalid_input"

P43_REQUIRED_LATEST_FILES = ("p42_boss_copilot_daily_brief.json", "p42_boss_copilot_daily_brief.md")
P43_KNOWN_JSON = (
    "p36_recommendation_outcomes.json",
    "p37_market_regime_snapshot.json",
    "p38_fundamental_quality.json",
    "p39_candidate_pool.json",
    "p40_research_memory_pack.json",
    "p41_decision_journal.json",
    "p42_boss_copilot_daily_brief.json",
)
P43_KNOWN_MARKDOWN = tuple(name.replace(".json", ".md") for name in P43_KNOWN_JSON)
P43_ALL_KNOWN = P43_KNOWN_JSON + P43_KNOWN_MARKDOWN

P43_ARTIFACT_DISCLAIMER = (
    "P43 is a static read-only evidence index. It does not recommend trades, "
    "submit orders, schedule jobs, send notifications, or mutate research decisions."
)
P43_FORBIDDEN_TERMS = (
    "buy this now", "sell this now", "follow this trade", "guaranteed edge",
    "production approved", "model promoted", "trade now", "order ticket",
    "place order", "execute trade",
)


def _sha(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


def _extract_status(path: Path) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return {}, [f"invalid_json:{path.name}"]
    extracted = {}
    for key in ("schema_version", "status", "overall_status", "as_of_date", "run_date", "summary", "source_hash"):
        if key in data:
            extracted[key] = data[key]
    return extracted, warnings


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name


def scan_governance_day(day_dir: Path, governance_root: Path | None = None) -> dict[str, Any]:
    root = governance_root or day_dir.parent
    present = []
    json_links = {}
    markdown_links = {}
    status_extracts = {}
    warnings = []
    for name in P43_ALL_KNOWN:
        path = day_dir / name
        if path.exists():
            present.append(name)
            if name.endswith(".json"):
                json_links[name] = _relative(path, root)
                extracted, file_warnings = _extract_status(path)
                status_extracts[name] = extracted
                warnings.extend(file_warnings)
            else:
                markdown_links[name] = _relative(path, root)
    missing = [name for name in P43_ALL_KNOWN if name not in present]
    if warnings:
        coverage = "invalid"
    elif present and missing:
        coverage = "partial"
    elif present:
        coverage = "complete"
    else:
        coverage = "empty"
    primary = ""
    if "p42_boss_copilot_daily_brief.md" in markdown_links:
        primary = markdown_links["p42_boss_copilot_daily_brief.md"]
    return {
        "date": day_dir.name,
        "day_dir": _relative(day_dir, root),
        "coverage_status": coverage,
        "present_artifacts": sorted(present),
        "missing_artifacts": missing,
        "json_links": json_links,
        "markdown_links": markdown_links,
        "primary_brief_ref": primary,
        "status_extracts": status_extracts,
        "warnings": sorted(set(warnings)),
    }


def _date_window(as_of_date: str, lookback_days: int) -> set[str]:
    end = date.fromisoformat(as_of_date)
    return {(end - timedelta(days=i)).isoformat() for i in range(lookback_days)}


def _artifact_fingerprint(day_dir: Path, names: list[str]) -> list[dict[str, Any]]:
    rows = []
    for name in sorted(names):
        path = day_dir / name
        if not path.exists():
            continue
        stat = path.stat()
        rows.append({"name": name, "size": stat.st_size, "mtime_ns": stat.st_mtime_ns})
    return rows


def build_copilot_console_index(governance_root: Path, as_of_date: str, lookback_days: int = 14) -> dict[str, Any]:
    governance_root = Path(governance_root)
    if lookback_days <= 0:
        return {"schema_version": P43_SCHEMA_VERSION, "status": P43_STATUS_BLOCKED_INVALID_INPUT, "warnings": ["lookback_days_must_be_positive"]}
    try:
        window = _date_window(as_of_date, lookback_days)
    except ValueError:
        return {"schema_version": P43_SCHEMA_VERSION, "status": P43_STATUS_BLOCKED_INVALID_INPUT, "warnings": ["invalid_date_format"]}

    day_dirs = []
    if governance_root.exists() and governance_root.is_dir():
        for child in governance_root.iterdir():
            if child.is_dir() and child.name in window:
                day_dirs.append(child)
    day_dirs.sort(key=lambda p: p.name, reverse=True)

    days = [scan_governance_day(day, governance_root) for day in day_dirs]
    days = [day for day in days if day["present_artifacts"] or day["warnings"]]
    if not days:
        status = P43_STATUS_NO_ARTIFACTS
    else:
        latest = days[0]
        missing_latest_required = [name for name in P43_REQUIRED_LATEST_FILES if name not in latest["present_artifacts"]]
        status = P43_STATUS_LIMITED_CONTEXT if missing_latest_required else P43_STATUS_READY

    missing_count = sum(len(day["missing_artifacts"]) for day in days)
    invalid_count = sum(len(day["warnings"]) for day in days)
    fingerprints = [
        {"date": day.name, "files": _artifact_fingerprint(day, P43_ALL_KNOWN)}
        for day in day_dirs
    ]
    source_hash = _sha({
        "schema_version": P43_SCHEMA_VERSION,
        "as_of_date": as_of_date,
        "lookback_days": lookback_days,
        "days": days,
        "fingerprints": fingerprints,
    })
    index_id = hashlib.sha256(f"{as_of_date}|{lookback_days}|{source_hash}".encode("utf-8")).hexdigest()[:16]
    return {
        "schema_version": P43_SCHEMA_VERSION,
        "index_id": index_id,
        "as_of_date": as_of_date,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "lookback_days": lookback_days,
        "summary": {
            "day_count": len(days),
            "latest_day": days[0]["date"] if days else "",
            "missing_artifact_count": missing_count,
            "invalid_artifact_count": invalid_count,
        },
        "days": days,
        "source_hash": source_hash,
        "disclaimer": P43_ARTIFACT_DISCLAIMER,
    }


def _check_forbidden(text: str) -> None:
    lowered = text.lower()
    for forbidden in P43_FORBIDDEN_TERMS:
        if forbidden in lowered:
            raise ValueError(f"forbidden copilot console term rendered: {forbidden}")


def _markdown(index: dict[str, Any]) -> str:
    lines = [
        "# Co-Pilot Console Index",
        "",
        f"As of: `{index.get('as_of_date', '')}`",
        f"Status: `{index.get('status', '')}`",
        f"Day count: `{index.get('summary', {}).get('day_count', 0)}`",
        "",
        "## Daily Coverage",
        "",
        "| Date | Coverage | Primary Brief | Missing | Invalid |",
        "|------|----------|---------------|---------|---------|",
    ]
    for day in index.get("days", []):
        primary = day.get("primary_brief_ref") or ""
        primary_link = f"[open]({primary})" if primary else ""
        lines.append(
            f"| {day['date']} | {day['coverage_status']} | {primary_link} | "
            f"{len(day['missing_artifacts'])} | {len(day['warnings'])} |"
        )
    lines.extend(["", "## Missing Artifacts", ""])
    any_missing = False
    for day in index.get("days", []):
        if day["missing_artifacts"]:
            any_missing = True
            lines.append(f"- {day['date']}: {', '.join(day['missing_artifacts'])}")
    if not any_missing:
        lines.append("- none")
    lines.extend(["", "---", "", f"> {index.get('disclaimer', P43_ARTIFACT_DISCLAIMER)}", ""])
    text = "\n".join(lines)
    _check_forbidden(text)
    return text


def _html(index: dict[str, Any]) -> str:
    rows = []
    for day in index.get("days", []):
        primary = html.escape(day.get("primary_brief_ref") or "")
        link = f'<a href="{primary}">open</a>' if primary else ""
        rows.append(
            "<tr>"
            f"<td>{html.escape(day['date'])}</td>"
            f"<td>{html.escape(day['coverage_status'])}</td>"
            f"<td>{link}</td>"
            f"<td>{len(day['missing_artifacts'])}</td>"
            f"<td>{len(day['warnings'])}</td>"
            "</tr>"
        )
    doc = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Hermes Co-Pilot Console Index</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 32px; color: #1f2937; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #d1d5db; padding: 8px; text-align: left; }}
    th {{ background: #f3f4f6; }}
  </style>
</head>
<body>
  <h1>Hermes Co-Pilot Console Index</h1>
  <p>Status: <strong>{html.escape(index.get('status', ''))}</strong></p>
  <p>As of: {html.escape(index.get('as_of_date', ''))}</p>
  <table>
    <thead><tr><th>Date</th><th>Coverage</th><th>Primary Brief</th><th>Missing</th><th>Invalid</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
  <p>{html.escape(index.get('disclaimer', P43_ARTIFACT_DISCLAIMER))}</p>
</body>
</html>"""
    _check_forbidden(doc)
    return doc


def write_copilot_console_index_artifacts(index: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "p43_copilot_console_index.json"
    md_path = output_dir / "p43_copilot_console_index.md"
    html_path = output_dir / "p43_copilot_console_index.html"
    json_path.write_text(json.dumps(index, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_markdown(index), encoding="utf-8")
    html_path.write_text(_html(index), encoding="utf-8")
    return {"json": json_path, "md": md_path, "html": html_path}


def run_copilot_console_index(
    governance_root: Path,
    output_root: Path,
    as_of_date: str,
    lookback_days: int = 14,
    db: Any | None = None,
) -> dict[str, Any]:
    index = build_copilot_console_index(governance_root, as_of_date, lookback_days)
    if index.get("status") == P43_STATUS_BLOCKED_INVALID_INPUT:
        return {"status": P43_STATUS_BLOCKED_INVALID_INPUT, "warnings": index.get("warnings", [])}
    output_dir = Path(output_root) / as_of_date
    paths = write_copilot_console_index_artifacts(index, output_dir)
    if db is not None:
        db.save_copilot_console_index(index)
    summary = index.get("summary", {})
    return {
        "status": index["status"],
        "output_dir": str(output_dir),
        "day_count": summary.get("day_count", 0),
        "latest_day": summary.get("latest_day", ""),
        "missing_artifact_count": summary.get("missing_artifact_count", 0),
        "invalid_artifact_count": summary.get("invalid_artifact_count", 0),
        "paths": paths,
    }
