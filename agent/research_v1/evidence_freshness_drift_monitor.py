"""P44 Evidence Freshness & Drift Monitor."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

P44_SCHEMA_VERSION = "p44_evidence_freshness_drift_monitor.1"
P44_STATUS_GREEN = "monitor_green"
P44_STATUS_YELLOW = "monitor_yellow"
P44_STATUS_RED = "monitor_red"
P44_STATUS_BLOCKED_INVALID_INPUT = "blocked_invalid_input"

PHASES = (
    ("P36", "recommendation_outcomes", "p36_recommendation_outcomes.json"),
    ("P37", "market_regime", "p37_market_regime_snapshot.json"),
    ("P38", "fundamental_quality", "p38_fundamental_quality.json"),
    ("P39", "candidate_pool", "p39_candidate_pool.json"),
    ("P40", "research_memory", "p40_research_memory_pack.json"),
    ("P41", "decision_journal", "p41_decision_journal.json"),
    ("P42", "boss_copilot_brief", "p42_boss_copilot_daily_brief.json"),
    ("P43", "copilot_console_index", "p43_copilot_console_index.json"),
)

P44_ARTIFACT_DISCLAIMER = (
    "P44 is evidence freshness and drift monitoring only. It does not refresh "
    "evidence, schedule jobs, send notifications, recommend trades, submit orders, "
    "or mutate research decisions."
)

P44_FORBIDDEN_TERMS = (
    "buy this now", "sell this now", "follow this trade", "guaranteed edge",
    "production approved", "model promoted", "trade now", "order ticket",
    "place order", "execute trade",
)


def _sha(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _days_old(as_of_date: str, evidence_date: str) -> int:
    return (_parse_date(as_of_date) - _parse_date(evidence_date)).days


def _artifact_status(governance_root: Path, as_of_date: str, lookback_days: int, artifact_name: str) -> tuple[int, str, list[str], str]:
    root = Path(governance_root)
    warnings: list[str] = []
    found_count = 0
    latest_date = ""
    latest_content_hash = ""
    for i in range(lookback_days):
        day = (_parse_date(as_of_date) - timedelta(days=i)).isoformat()
        path = root / day / artifact_name
        if not path.exists():
            continue
        found_count += 1
        try:
            content = path.read_bytes()
        except OSError:
            continue
        if not latest_date:
            latest_date = day
            latest_content_hash = hashlib.sha256(content).hexdigest()
            try:
                json.loads(content)
            except (json.JSONDecodeError, OSError, UnicodeDecodeError):
                warnings.append(f"invalid_json:{artifact_name}")
    return found_count, latest_date, sorted(set(warnings)), latest_content_hash


def _freshness(as_of_date: str, latest_date: str, freshness_days: int, invalid: bool) -> str:
    if invalid:
        return "invalid"
    if not latest_date:
        return "missing"
    return "fresh" if _days_old(as_of_date, latest_date) <= freshness_days else "stale"


def _churn(rows: list[dict]) -> str:
    available = [r for r in rows if r.get("source_hash")]
    if len(available) < 2:
        return "unknown"
    unique = {str(r.get("source_hash", "")) for r in available}
    if len(unique) == 1:
        return "stable"
    if len(unique) == 2:
        return "changed"
    return "high_churn"


def _coverage(row_count: int, artifact_count: int, invalid: bool, latest_evidence_date: str, artifact_latest_date: str) -> str:
    if invalid:
        return "invalid"
    if row_count == 0 and artifact_count == 0:
        return "missing"
    if artifact_count > 0 and artifact_latest_date and latest_evidence_date and artifact_latest_date >= latest_evidence_date:
        return "complete"
    if artifact_count > 0:
        return "partial"
    return "partial"


def _recommended_action(freshness_status: str, churn_status: str, coverage_status: str) -> str:
    if coverage_status == "invalid" or freshness_status == "invalid":
        return "inspect_invalid_artifact"
    if coverage_status == "missing" or freshness_status == "missing":
        return "collect_missing_evidence"
    if freshness_status == "stale":
        return "refresh_stale_evidence"
    if churn_status == "high_churn":
        return "review_source_hash_churn"
    return "none"


def _latest_row(rows: list[dict]) -> dict:
    if not rows:
        return {}
    return sorted(rows, key=lambda r: (r.get("as_of_date", ""), r.get("created_at", ""), r.get("source_hash", "")), reverse=True)[0]


def _missing_patterns(phase_rows: dict[str, list[dict]]) -> list[dict[str, Any]]:
    counts: dict[str, dict[str, Any]] = {}
    for phase_id, rows in phase_rows.items():
        for row in rows:
            payload = row.get("payload") or {}
            keys: list[str] = []
            if phase_id == "P40":
                keys.extend(payload.get("missing_context", []))
            if phase_id == "P41":
                keys.extend(payload.get("missing_context", []))
            if phase_id == "P42":
                keys.extend((payload.get("summary") or {}).get("missing_context_counts", {}).keys())
            if phase_id == "P43":
                for day in payload.get("days", []):
                    keys.extend(day.get("missing_artifacts", []))
            for key in keys:
                entry = counts.setdefault(str(key), {"key": str(key), "count": 0, "sources": set()})
                entry["count"] += 1
                entry["sources"].add(phase_id)
    result = []
    for item in counts.values():
        result.append({"key": item["key"], "count": item["count"], "sources": sorted(item["sources"])})
    return sorted(result, key=lambda x: (-x["count"], x["key"]))


def build_evidence_freshness_drift_report(
    *,
    as_of_date: str,
    lookback_days: int,
    freshness_days: int,
    phase_rows: dict[str, list[dict]],
    governance_root: Path,
) -> dict[str, Any]:
    phase_monitors = []
    artifact_fingerprints: dict[str, str] = {}
    for phase_id, phase_name, artifact_name in PHASES:
        rows = phase_rows.get(phase_id, [])
        latest = _latest_row(rows)
        artifact_count, artifact_latest_date, artifact_warnings, artifact_content_hash = _artifact_status(governance_root, as_of_date, lookback_days, artifact_name)
        if artifact_content_hash:
            artifact_fingerprints[artifact_name] = artifact_content_hash
        latest_date = latest.get("as_of_date") or artifact_latest_date
        invalid = bool(artifact_warnings)
        freshness_status = _freshness(as_of_date, latest_date, freshness_days, invalid)
        churn_status = _churn(rows)
        coverage_status = _coverage(len(rows), artifact_count, invalid, latest_date, artifact_latest_date)
        phase_monitors.append({
            "phase_id": phase_id,
            "phase_name": phase_name,
            "latest_evidence_date": latest_date,
            "latest_created_at": latest.get("created_at", ""),
            "latest_source_hash": latest.get("source_hash", ""),
            "row_count": len(rows),
            "artifact_count": artifact_count,
            "freshness_status": freshness_status,
            "churn_status": churn_status,
            "coverage_status": coverage_status,
            "warnings": artifact_warnings,
            "recommended_action": _recommended_action(freshness_status, churn_status, coverage_status),
        })
    missing_patterns = _missing_patterns(phase_rows)
    red_count = sum(1 for p in phase_monitors if p["freshness_status"] in {"missing", "invalid"} or p["coverage_status"] in {"missing", "invalid"})
    yellow_count = sum(1 for p in phase_monitors if p["freshness_status"] == "stale" or p["churn_status"] == "high_churn")
    status = P44_STATUS_RED if red_count else P44_STATUS_YELLOW if yellow_count else P44_STATUS_GREEN
    seed = {
        "schema_version": P44_SCHEMA_VERSION,
        "as_of_date": as_of_date,
        "lookback_days": lookback_days,
        "freshness_days": freshness_days,
        "phase_monitors": phase_monitors,
        "missing_context_patterns": missing_patterns,
        "artifact_fingerprints": artifact_fingerprints,
    }
    source_hash = _sha(seed)
    report_id = hashlib.sha256(f"{as_of_date}|{lookback_days}|{freshness_days}|{source_hash}".encode("utf-8")).hexdigest()[:16]
    return {
        "schema_version": P44_SCHEMA_VERSION,
        "report_id": report_id,
        "as_of_date": as_of_date,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "lookback_days": lookback_days,
        "freshness_days": freshness_days,
        "phase_monitors": phase_monitors,
        "missing_context_patterns": missing_patterns,
        "summary": {
            "phase_count": len(phase_monitors),
            "red_count": red_count,
            "yellow_count": yellow_count,
            "missing_context_pattern_count": len(missing_patterns),
        },
        "source_hash": source_hash,
        "disclaimer": P44_ARTIFACT_DISCLAIMER,
    }


def _check_forbidden(text: str) -> None:
    lowered = text.lower()
    for forbidden in P44_FORBIDDEN_TERMS:
        if forbidden in lowered:
            raise ValueError(f"forbidden evidence monitor term rendered: {forbidden}")


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Evidence Freshness & Drift Monitor",
        "",
        f"As of: `{report.get('as_of_date', '')}`",
        f"Status: `{report.get('status', '')}`",
        "",
        "## Phase Freshness",
        "",
        "| Phase | Name | Freshness | Coverage | Churn | Latest Date | Action |",
        "|-------|------|-----------|----------|-------|-------------|--------|",
    ]
    for phase in report.get("phase_monitors", []):
        lines.append(
            f"| {phase['phase_id']} | {phase['phase_name']} | {phase['freshness_status']} | "
            f"{phase['coverage_status']} | {phase['churn_status']} | "
            f"{phase.get('latest_evidence_date', '')} | {phase['recommended_action']} |"
        )

    lines.extend(["", "## Warnings", ""])
    any_warnings = False
    for phase in report.get("phase_monitors", []):
        for warning in phase.get("warnings", []):
            any_warnings = True
            lines.append(f"- {phase['phase_id']}: {warning}")
    if not any_warnings:
        lines.append("- none")

    lines.extend(["", "## Missing Context Patterns", ""])
    patterns = report.get("missing_context_patterns", [])
    if patterns:
        for item in patterns:
            lines.append(f"- {item['key']}: {item['count']} ({', '.join(item['sources'])})")
    else:
        lines.append("- none")

    lines.extend(["", "## Recommended Manual Follow-Up Actions", ""])
    actions_seen = set()
    for phase in report.get("phase_monitors", []):
        action = phase.get("recommended_action", "none")
        if action != "none" and action not in actions_seen:
            actions_seen.add(action)
            lines.append(f"- **{phase['phase_id']}**: {action}")
    if not actions_seen:
        lines.append("- none")

    lines.extend(["", "---", "", f"> {report.get('disclaimer', P44_ARTIFACT_DISCLAIMER)}", ""])
    text = "\n".join(lines)
    _check_forbidden(text)
    return text


def write_evidence_freshness_drift_artifacts(report: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "p44_evidence_freshness_drift_monitor.json"
    md_path = output_dir / "p44_evidence_freshness_drift_monitor.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_markdown(report), encoding="utf-8")
    return {"json": json_path, "md": md_path}


def run_evidence_freshness_drift_monitor(
    db: Any,
    governance_root: Path,
    output_root: Path,
    as_of_date: str,
    lookback_days: int = 14,
    freshness_days: int = 3,
) -> dict[str, Any]:
    try:
        _parse_date(as_of_date)
    except ValueError:
        return {"status": P44_STATUS_BLOCKED_INVALID_INPUT, "warnings": ["invalid_date_format"]}
    if lookback_days <= 0:
        return {"status": P44_STATUS_BLOCKED_INVALID_INPUT, "warnings": ["lookback_days_must_be_positive"]}
    if freshness_days <= 0:
        return {"status": P44_STATUS_BLOCKED_INVALID_INPUT, "warnings": ["freshness_days_must_be_positive"]}
    root = Path(governance_root)
    if root.exists() and not root.is_dir():
        return {"status": P44_STATUS_BLOCKED_INVALID_INPUT, "warnings": ["governance_root_not_a_directory"]}

    phase_rows = db.collect_evidence_phase_rows(as_of_date, lookback_days)
    report = build_evidence_freshness_drift_report(
        as_of_date=as_of_date,
        lookback_days=lookback_days,
        freshness_days=freshness_days,
        phase_rows=phase_rows,
        governance_root=root,
    )
    db.save_evidence_freshness_drift_report(report)
    output_dir = Path(output_root) / as_of_date
    paths = write_evidence_freshness_drift_artifacts(report, output_dir)
    summary = report.get("summary", {})
    return {
        "status": report["status"],
        "output_dir": str(output_dir),
        "phase_count": summary.get("phase_count", 0),
        "red_count": summary.get("red_count", 0),
        "yellow_count": summary.get("yellow_count", 0),
        "missing_context_pattern_count": summary.get("missing_context_pattern_count", 0),
        "paths": paths,
    }
