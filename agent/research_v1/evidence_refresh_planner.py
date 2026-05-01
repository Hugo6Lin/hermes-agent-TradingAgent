"""P46 controlled evidence refresh planner."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

P46_SCHEMA_VERSION = "p46_evidence_refresh_plan.1"

STATUS_READY = "refresh_plan_ready"
STATUS_BLOCKED = "refresh_plan_blocked"
STATUS_NOOP = "refresh_plan_noop"
STATUS_INVALID_INPUT = "blocked_invalid_input"

P46_DISCLAIMER = (
    "P46 is a dry-run evidence refresh planner only. It does not refresh evidence, "
    "call market-data providers, submit orders, approve production adoption, train "
    "models, schedule jobs, or mutate research decisions."
)

FORBIDDEN_TERMS = (
    "buy this now",
    "sell this now",
    "follow this trade",
    "guaranteed edge",
    "production approved",
    "model promoted",
    "execute trade",
    "place order",
    "unlock_trade",
)

PHASES = {
    "P36": ("recommendation_outcomes", "p36_recommendation_outcomes.json"),
    "P37": ("market_regime", "p37_market_regime_snapshot.json"),
    "P38": ("fundamental_quality", "p38_fundamental_quality.json"),
    "P39": ("candidate_pool", "p39_candidate_pool.json"),
    "P40": ("research_memory", "p40_research_memory_pack.json"),
    "P41": ("decision_journal", "p41_decision_journal.json"),
    "P42": ("boss_copilot_brief", "p42_boss_copilot_daily_brief.json"),
    "P43": ("copilot_console_index", "p43_copilot_console_index.json"),
    "P44": ("evidence_freshness_drift_monitor", "p44_evidence_freshness_drift_monitor.json"),
    "P45": ("market_data_readiness", "p45_market_data_readiness.json"),
}

MARKET_DATA_PHASES = {"P36", "P37", "P39", "P42"}

STATUS_ORDER = {
    "refresh_candidate": 0,
    "blocked_invalid_artifact": 1,
    "blocked_provider_unavailable": 2,
    "blocked_missing_monitor": 3,
    "blocked_missing_inputs": 4,
    "defer_no_action": 5,
}


def _sha(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


def _priority(score: int) -> str:
    if score >= 100:
        return "critical"
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    if score >= 1:
        return "low"
    return "none"


def _command(phase_id: str, as_of_date: str) -> str:
    mapping = {
        "P36": f"python -m agent.research_v1.batch_cli outcome-run --as-of-date {as_of_date}",
        "P37": f"python -m agent.research_v1.batch_cli market-regime-run --as-of-date {as_of_date}",
        "P38": f"python -m agent.research_v1.batch_cli fundamental-quality-run --as-of-date {as_of_date} --input <path>",
        "P39": f"python -m agent.research_v1.batch_cli candidate-pool-run --as-of-date {as_of_date} --universe <path>",
        "P40": f"python -m agent.research_v1.batch_cli research-memory-run --as-of-date {as_of_date} --ticker <ticker>",
        "P41": f"python -m agent.research_v1.batch_cli decision-journal-run --as-of-date {as_of_date} --input <path>",
        "P42": f"python -m agent.research_v1.batch_cli boss-copilot-brief-run --as-of-date {as_of_date}",
        "P43": f"python -m agent.research_v1.batch_cli copilot-console-index-run --as-of-date {as_of_date}",
        "P44": f"python -m agent.research_v1.batch_cli evidence-monitor-run --as-of-date {as_of_date}",
        "P45": f"python -m agent.research_v1.batch_cli market-data-readiness-run --as-of-date {as_of_date} --live",
    }
    return mapping[phase_id]


def _reason_codes(phase: dict[str, Any], missing_context_keys: set[str]) -> list[str]:
    reasons: list[str] = []
    if phase.get("freshness_status") == "missing":
        reasons.append("freshness_missing")
    if phase.get("freshness_status") == "stale":
        reasons.append("freshness_stale")
    if phase.get("freshness_status") == "invalid":
        reasons.append("freshness_invalid")
    if phase.get("coverage_status") == "missing":
        reasons.append("coverage_missing")
    if phase.get("coverage_status") == "partial":
        reasons.append("coverage_partial")
    if phase.get("coverage_status") == "invalid":
        reasons.append("coverage_invalid")
    if phase.get("churn_status") == "high_churn":
        reasons.append("churn_high")
    phase_name = str(phase.get("phase_name", ""))
    artifact = PHASES.get(str(phase.get("phase_id")), ("", ""))[1]
    if phase_name in missing_context_keys or artifact in missing_context_keys:
        reasons.append("missing_context_pattern")
    return sorted(set(reasons))


def _score(reasons: list[str], provider_status: str, market_data_phase: bool) -> int:
    if market_data_phase and provider_status in {"provider_unavailable", "provider_not_tested_live", ""}:
        return 0
    weights = {
        "freshness_invalid": 100,
        "coverage_invalid": 100,
        "freshness_missing": 90,
        "coverage_missing": 80,
        "freshness_stale": 60,
        "coverage_partial": 45,
        "churn_high": 35,
        "missing_context_pattern": 20,
    }
    score = sum(weights.get(reason, 0) for reason in reasons)
    if market_data_phase and provider_status == "provider_degraded":
        score = max(0, score - 15)
    return score


def _plan_item(phase_id: str, phase: dict[str, Any], provider_status: str, missing_context_keys: set[str], as_of_date: str) -> dict[str, Any]:
    phase_name, artifact_name = PHASES[phase_id]
    reasons = _reason_codes(phase, missing_context_keys)
    market_data_phase = phase_id in MARKET_DATA_PHASES
    blocking_reasons: list[str] = []
    warnings: list[str] = []
    plan_status = "defer_no_action"
    if "freshness_invalid" in reasons or "coverage_invalid" in reasons:
        plan_status = "blocked_invalid_artifact"
        blocking_reasons.append("inspect_invalid_artifact_first")
    elif market_data_phase and provider_status in {"provider_unavailable", "provider_not_tested_live", ""}:
        plan_status = "blocked_provider_unavailable"
        blocking_reasons.append(provider_status or "provider_missing")
    elif reasons:
        plan_status = "refresh_candidate"
    if market_data_phase and provider_status == "provider_degraded" and plan_status == "refresh_candidate":
        warnings.append("market_data_provider_degraded")

    command = _command(phase_id, as_of_date)
    required_inputs = []
    if "<path>" in command:
        required_inputs.append("operator_input_path")
    if "<ticker>" in command:
        required_inputs.append("ticker")
    if plan_status == "refresh_candidate" and required_inputs:
        plan_status = "blocked_missing_inputs"
        blocking_reasons.extend(required_inputs)

    priority_score = _score(reasons, provider_status, market_data_phase)
    return {
        "item_id": f"{phase_id.lower()}-{_sha({'phase_id': phase_id, 'reasons': reasons})[:8]}",
        "phase_id": phase_id,
        "phase_name": phase_name,
        "artifact_name": artifact_name,
        "plan_status": plan_status,
        "priority": _priority(priority_score if plan_status == "refresh_candidate" else 0),
        "priority_score": priority_score if plan_status == "refresh_candidate" else 0,
        "reason_codes": reasons,
        "blocking_reasons": sorted(set(blocking_reasons)),
        "warnings": sorted(set(warnings)),
        "manual_command": command,
        "required_inputs": required_inputs,
        "latest_evidence_date": phase.get("latest_evidence_date", ""),
        "latest_source_hash": phase.get("latest_source_hash", ""),
        "source_refs": {"monitor_phase": phase},
    }


def build_evidence_refresh_plan(
    *,
    as_of_date: str,
    lookback_days: int,
    max_items: int,
    monitor_report: dict[str, Any] | None,
    provider_report: dict[str, Any] | None,
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    provider_status = (provider_report or {}).get("status", "")
    if monitor_report is None:
        for phase_id in PHASES:
            items.append({
                "item_id": f"{phase_id.lower()}-missing-monitor",
                "phase_id": phase_id,
                "phase_name": PHASES[phase_id][0],
                "artifact_name": PHASES[phase_id][1],
                "plan_status": "blocked_missing_monitor",
                "priority": "none",
                "priority_score": 0,
                "reason_codes": ["monitor_missing"],
                "blocking_reasons": ["missing_p44_monitor"],
                "warnings": [],
                "manual_command": _command("P44", as_of_date),
                "required_inputs": [],
                "latest_evidence_date": "",
                "latest_source_hash": "",
                "source_refs": {},
            })
    else:
        missing_context_keys = {str(item.get("key")) for item in monitor_report.get("missing_context_patterns", [])}
        phase_map = {phase["phase_id"]: phase for phase in monitor_report.get("phase_monitors", [])}
        for phase_id in [p for p in PHASES if p not in {"P44", "P45"}]:
            phase = phase_map.get(phase_id, {
                "phase_id": phase_id,
                "phase_name": PHASES[phase_id][0],
                "freshness_status": "missing",
                "coverage_status": "missing",
                "churn_status": "unknown",
            })
            items.append(_plan_item(phase_id, phase, provider_status, missing_context_keys, as_of_date))
        if monitor_report.get("status") in {"monitor_red", "monitor_yellow"}:
            pseudo = {"phase_id": "P44", "phase_name": PHASES["P44"][0], "freshness_status": "stale", "coverage_status": "partial", "churn_status": "unknown"}
            items.append(_plan_item("P44", pseudo, provider_status, missing_context_keys, as_of_date))
        if provider_report is None or provider_status in {"provider_unavailable", "provider_not_tested_live", "provider_degraded"}:
            pseudo = {"phase_id": "P45", "phase_name": PHASES["P45"][0], "freshness_status": "stale", "coverage_status": "partial", "churn_status": "unknown"}
            items.append(_plan_item("P45", pseudo, provider_status, missing_context_keys, as_of_date))

    items = sorted(items, key=lambda item: (STATUS_ORDER.get(item["plan_status"], 99), -item["priority_score"], item["phase_id"]))[:max_items]
    candidate_count = sum(1 for item in items if item["plan_status"] == "refresh_candidate")
    blocked_count = sum(1 for item in items if item["plan_status"].startswith("blocked_"))
    if candidate_count:
        status = STATUS_READY
    elif blocked_count:
        status = STATUS_BLOCKED
    else:
        status = STATUS_NOOP

    selected_monitor = {
        "report_id": (monitor_report or {}).get("report_id", ""),
        "status": (monitor_report or {}).get("status", ""),
        "source_hash": (monitor_report or {}).get("source_hash", ""),
    }
    selected_provider = {
        "report_id": (provider_report or {}).get("report_id", ""),
        "status": provider_status,
        "source_hash": (provider_report or {}).get("source_hash", ""),
    }
    seed = {
        "schema_version": P46_SCHEMA_VERSION,
        "as_of_date": as_of_date,
        "lookback_days": lookback_days,
        "max_items": max_items,
        "selected_monitor": selected_monitor,
        "selected_provider_readiness": selected_provider,
        "items": items,
    }
    source_hash = _sha(seed)
    plan_id = hashlib.sha256(f"{as_of_date}|{lookback_days}|{max_items}|{source_hash}".encode("utf-8")).hexdigest()[:16]
    return {
        "schema_version": P46_SCHEMA_VERSION,
        "plan_id": plan_id,
        "as_of_date": as_of_date,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "lookback_days": lookback_days,
        "max_items": max_items,
        "selected_monitor": selected_monitor,
        "selected_provider_readiness": selected_provider,
        "items": items,
        "summary": {"candidate_count": candidate_count, "blocked_count": blocked_count, "item_count": len(items)},
        "source_hash": source_hash,
        "disclaimer": P46_DISCLAIMER,
    }


def _check_forbidden(text: str) -> None:
    lowered = text.lower()
    for term in FORBIDDEN_TERMS:
        if term in lowered:
            raise ValueError(f"forbidden evidence refresh planner term rendered: {term}")


def _markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# P46 Evidence Refresh Plan",
        "",
        f"As of: `{plan.get('as_of_date', '')}`",
        f"Status: `{plan.get('status', '')}`",
        "",
        "## Selected Evidence",
        "",
        f"- P44: `{(plan.get('selected_monitor') or {}).get('status', '')}` / `{(plan.get('selected_monitor') or {}).get('source_hash', '')}`",
        f"- P45: `{(plan.get('selected_provider_readiness') or {}).get('status', '')}` / `{(plan.get('selected_provider_readiness') or {}).get('source_hash', '')}`",
        "",
        "## Refresh Candidates",
        "",
        "| Phase | Priority | Score | Reasons | Command |",
        "|-------|----------|-------|---------|---------|",
    ]
    candidates = [item for item in plan.get("items", []) if item.get("plan_status") == "refresh_candidate"]
    if candidates:
        for item in candidates:
            lines.append(f"| {item['phase_id']} | {item['priority']} | {item['priority_score']} | {', '.join(item['reason_codes'])} | `{item['manual_command']}` |")
    else:
        lines.append("| none | none | 0 | none | none |")
    lines.extend(["", "## Blocked Items", "", "| Phase | Status | Blocking Reasons |", "|-------|--------|------------------|"])
    blocked = [item for item in plan.get("items", []) if str(item.get("plan_status", "")).startswith("blocked_")]
    if blocked:
        for item in blocked:
            lines.append(f"| {item['phase_id']} | {item['plan_status']} | {', '.join(item['blocking_reasons'])} |")
    else:
        lines.append("| none | none | none |")
    lines.extend(["", "---", "", f"> {plan.get('disclaimer', P46_DISCLAIMER)}", ""])
    text = "\n".join(lines)
    _check_forbidden(text)
    return text


def write_evidence_refresh_plan_artifacts(plan: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "p46_evidence_refresh_plan.json"
    md_path = output_dir / "p46_evidence_refresh_plan.md"
    json_path.write_text(json.dumps(plan, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_markdown(plan), encoding="utf-8")
    return {"json": json_path, "md": md_path}


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _load_artifact_as_of(root: Path, as_of_date: str, lookback_days: int, filename: str) -> dict | None:
    base = Path(root)
    for offset in range(lookback_days + 1):
        day = (_parse_date(as_of_date) - timedelta(days=offset)).isoformat()
        path = base / day / filename
        if not path.exists():
            continue
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            return None
    return None


def run_evidence_refresh_planner(
    *,
    db: Any,
    governance_root: Path,
    output_root: Path,
    as_of_date: str,
    lookback_days: int = 14,
    max_items: int = 12,
) -> dict[str, Any]:
    try:
        _parse_date(as_of_date)
    except (ValueError, TypeError):
        return {"status": STATUS_INVALID_INPUT, "warnings": ["invalid_date_format"]}
    if lookback_days <= 0:
        return {"status": STATUS_INVALID_INPUT, "warnings": ["lookback_days_must_be_positive"]}
    if max_items <= 0:
        return {"status": STATUS_INVALID_INPUT, "warnings": ["max_items_must_be_positive"]}
    root = Path(governance_root)
    if root.exists() and not root.is_dir():
        return {"status": STATUS_INVALID_INPUT, "warnings": ["governance_root_not_a_directory"]}

    monitor = None
    provider = None
    if hasattr(db, "latest_evidence_freshness_drift_report_as_of"):
        monitor = db.latest_evidence_freshness_drift_report_as_of(as_of_date)
    if hasattr(db, "latest_market_data_readiness_report_as_of"):
        provider = db.latest_market_data_readiness_report_as_of(as_of_date)
    monitor = monitor or _load_artifact_as_of(root, as_of_date, lookback_days, "p44_evidence_freshness_drift_monitor.json")
    provider = provider or _load_artifact_as_of(root, as_of_date, lookback_days, "p45_market_data_readiness.json")

    plan = build_evidence_refresh_plan(
        as_of_date=as_of_date,
        lookback_days=lookback_days,
        max_items=max_items,
        monitor_report=monitor,
        provider_report=provider,
    )
    if hasattr(db, "save_evidence_refresh_plan"):
        db.save_evidence_refresh_plan(plan)
    output_dir = Path(output_root) / as_of_date
    paths = write_evidence_refresh_plan_artifacts(plan, output_dir)
    return {
        "status": plan["status"],
        "output_dir": str(output_dir),
        "plan_id": plan["plan_id"],
        "candidate_count": plan["summary"]["candidate_count"],
        "blocked_count": plan["summary"]["blocked_count"],
        "paths": paths,
    }
