"""P41 Decision Journal Guardrails — deterministic behavioral guardrail evidence."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

P41_SCHEMA_VERSION = "p41_decision_journal.1"

P41_STATUS_COMPLETED = "completed"
P41_STATUS_COMPLETED_WITH_WARNINGS = "completed_with_warnings"
P41_STATUS_BLOCKED_INVALID_INPUT = "blocked_invalid_input"

SEVERITY_INFO = "info"
SEVERITY_CAUTION = "caution"
SEVERITY_SLOW_DOWN = "slow_down"
SEVERITY_MANUAL_REVIEW = "manual_review"

P41_ARTIFACT_DISCLAIMER = (
    "P41 is behavioral guardrail evidence only. It records decision context "
    "and does not recommend trades, place orders, approve production adoption, "
    "train models, schedule jobs, or mutate research decisions."
)

P41_ALLOWED_ACTIONS = (
    "research_candidate",
    "monitor_candidate",
    "defer_candidate",
    "review_existing_signal",
    "journal_only",
)

P41_FORBIDDEN_ACTION_FRAGMENTS = ("buy", "sell", "short", "call", "put", "trade_now")
P41_REQUIRED_FIELDS = ("ticker", "contemplated_action", "decision_intent", "stated_reason", "boss_confidence", "urgency")

P41_ALLOWED_INTENTS = (
    "review_before_action",
    "postpone_decision",
    "compare_with_prior",
    "journal_only",
)

SEVERITY_RANK = {SEVERITY_INFO: 0, SEVERITY_CAUTION: 1, SEVERITY_SLOW_DOWN: 2, SEVERITY_MANUAL_REVIEW: 3}


def _normalize_ticker(ticker: str) -> str:
    return str(ticker).strip().upper()


def validate_decision_item(item: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(item, dict):
        return ["decision_item_not_dict"]
    for field in P41_REQUIRED_FIELDS:
        if field not in item or item[field] in (None, ""):
            errors.append(f"missing:{field}")
    action = str(item.get("contemplated_action", "")).lower()
    if action not in P41_ALLOWED_ACTIONS:
        errors.append("invalid_contemplated_action")
    if any(fragment in action for fragment in P41_FORBIDDEN_ACTION_FRAGMENTS):
        errors.append("forbidden_contemplated_action")
    intent = str(item.get("decision_intent", "")).lower()
    if intent and intent not in P41_ALLOWED_INTENTS:
        errors.append("invalid_decision_intent")
    try:
        confidence = float(item.get("boss_confidence", 0))
        if confidence < 0 or confidence > 1:
            errors.append("boss_confidence_out_of_range")
    except (TypeError, ValueError):
        errors.append("boss_confidence_not_numeric")
    return sorted(set(errors))


def _normalize_decision_for_hash(decision: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    normalized["ticker"] = _normalize_ticker(decision.get("ticker", ""))
    normalized["contemplated_action"] = str(decision.get("contemplated_action", "")).strip().lower()
    normalized["decision_intent"] = str(decision.get("decision_intent", "")).strip().lower()
    normalized["stated_reason"] = str(decision.get("stated_reason", "")).strip()
    try:
        normalized["boss_confidence"] = round(float(decision.get("boss_confidence", 0)), 6)
    except (TypeError, ValueError):
        normalized["boss_confidence"] = 0.0
    normalized["urgency"] = str(decision.get("urgency", "")).strip().lower()
    normalized["time_pressure"] = str(decision.get("time_pressure", "")).strip().lower() or None
    normalized["recent_pnl_state"] = str(decision.get("recent_pnl_state", "")).strip().lower() or None
    pos = decision.get("position_context") or {}
    normalized["position_context"] = {
        "current_position_pct": round(float(pos.get("current_position_pct", 0) or 0), 6),
        "sector_exposure_pct": round(float(pos.get("sector_exposure_pct", 0) or 0), 6),
        "cash_available_pct": round(float(pos.get("cash_available_pct", 0) or 0), 6),
    }
    normalized["manual_notes"] = sorted(decision.get("manual_notes", []) or [])
    return normalized


def compute_decision_journal_source_hash(decision: dict[str, Any], as_of_date: str, memory_pack: dict[str, Any] | None) -> str:
    canonical = {
        "schema_version": P41_SCHEMA_VERSION,
        "as_of_date": as_of_date,
        "decision": _normalize_decision_for_hash(decision),
        "memory_pack_id": (memory_pack or {}).get("pack_id", ""),
        "memory_source_hash": (memory_pack or {}).get("source_hash", ""),
    }
    return hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


def _flag(flag_id: str, severity: str, reason: str) -> dict[str, str]:
    return {"flag_id": flag_id, "severity": severity, "reason": reason}


def build_guardrail_flags(decision: dict[str, Any], memory_pack: dict[str, Any] | None) -> tuple[list[dict[str, str]], list[str]]:
    flags: list[dict[str, str]] = []
    missing_context: list[str] = []
    confidence = float(decision.get("boss_confidence", 0.0) or 0.0)
    urgency = str(decision.get("urgency", "")).lower()
    if urgency == "high" and confidence >= 0.80:
        flags.append(_flag("high_urgency_high_confidence", SEVERITY_SLOW_DOWN, "High urgency and confidence can amplify impulsive decisions."))
    if decision.get("time_pressure") == "same_day":
        flags.append(_flag("time_pressure_same_day", SEVERITY_SLOW_DOWN, "Same-day time pressure is visible."))
    if decision.get("recent_pnl_state") == "drawdown":
        flags.append(_flag("recent_drawdown_context", SEVERITY_SLOW_DOWN, "Recent drawdown context is visible."))
    position = decision.get("position_context") or {}
    if float(position.get("current_position_pct", 0.0) or 0.0) >= 0.15:
        flags.append(_flag("position_concentration_high", SEVERITY_MANUAL_REVIEW, "Position concentration is high."))
    if float(position.get("sector_exposure_pct", 0.0) or 0.0) >= 0.40:
        flags.append(_flag("sector_concentration_high", SEVERITY_MANUAL_REVIEW, "Sector concentration is high."))
    if float(position.get("cash_available_pct", 1.0) or 1.0) <= 0.05:
        flags.append(_flag("cash_constraint_visible", SEVERITY_CAUTION, "Cash constraint is visible."))
    if not memory_pack:
        missing_context.append("missing_memory_pack")
        flags.append(_flag("missing_memory_pack", SEVERITY_CAUTION, "No P40 memory pack was found."))
    else:
        for item in memory_pack.get("missing_context", []):
            missing_context.append(item)
            flags.append(_flag(item, SEVERITY_CAUTION, f"Memory pack missing context: {item}"))
        risk_memory = set(memory_pack.get("risk_memory", []))
        recurring_themes = set(memory_pack.get("recurring_themes", []))
        combined_memory = risk_memory | recurring_themes
        if "quality_red_flags_present" in risk_memory:
            flags.append(_flag("quality_red_flags_present", SEVERITY_MANUAL_REVIEW, "P40 memory includes quality red flags."))
        if "negative_outcome_history" in combined_memory:
            flags.append(_flag("negative_outcome_memory", SEVERITY_SLOW_DOWN, "P40 memory includes negative outcome history."))
        if "prior_insufficient_outcome_data" in risk_memory:
            flags.append(_flag("insufficient_outcome_memory", SEVERITY_CAUTION, "Prior outcome data is insufficient."))
        if "stale_research_context" in combined_memory:
            flags.append(_flag("stale_research_memory", SEVERITY_SLOW_DOWN, "P40 memory indicates stale research context."))
    return flags, sorted(set(missing_context))


def _entry_severity(flags: list[dict[str, str]]) -> str:
    if not flags:
        return SEVERITY_INFO
    return max((f["severity"] for f in flags), key=lambda s: SEVERITY_RANK[s])


def _cooling_off(severity: str, flags: list[dict[str, str]]) -> str:
    flag_ids = {f["flag_id"] for f in flags}
    if severity == SEVERITY_MANUAL_REVIEW:
        return "manual_review_before_action"
    if severity == SEVERITY_SLOW_DOWN and ("recent_drawdown_context" in flag_ids or "time_pressure_same_day" in flag_ids):
        return "recheck_next_session"
    if severity == SEVERITY_SLOW_DOWN:
        return "recheck_after_30_minutes"
    return "none"


def build_decision_journal_entry(decision: dict[str, Any], as_of_date: str, memory_pack: dict[str, Any] | None) -> dict[str, Any]:
    ticker = _normalize_ticker(decision.get("ticker", ""))
    source_hash = compute_decision_journal_source_hash(decision, as_of_date, memory_pack)
    journal_id = hashlib.sha256(f"{ticker}|{as_of_date}|{decision.get('contemplated_action', '')}|{source_hash}".encode("utf-8")).hexdigest()[:16]
    flags, missing_context = build_guardrail_flags(decision, memory_pack)
    errors = validate_decision_item(decision)
    if errors:
        flags.append(_flag("manual_review_required", SEVERITY_MANUAL_REVIEW, "Decision input failed validation."))
    severity = _entry_severity(flags)
    return {
        "schema_version": P41_SCHEMA_VERSION,
        "journal_id": journal_id,
        "as_of_date": as_of_date,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "ticker": ticker,
        "contemplated_action": decision.get("contemplated_action", ""),
        "decision_intent": decision.get("decision_intent", ""),
        "stated_reason": decision.get("stated_reason", ""),
        "boss_confidence": decision.get("boss_confidence"),
        "urgency": decision.get("urgency", ""),
        "time_pressure": decision.get("time_pressure", ""),
        "recent_pnl_state": decision.get("recent_pnl_state", ""),
        "position_context": decision.get("position_context", {}),
        "manual_notes": decision.get("manual_notes", []),
        "memory_ref": {
            "pack_id": (memory_pack or {}).get("pack_id", ""),
            "source_hash": (memory_pack or {}).get("source_hash", ""),
        },
        "guardrail_flags": flags,
        "severity": severity,
        "cooling_off_suggestion": _cooling_off(severity, flags),
        "missing_context": missing_context,
        "source_hash": source_hash,
        "disclaimer": P41_ARTIFACT_DISCLAIMER,
    }


def write_decision_journal_artifacts(payload: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "p41_decision_journal.json"
    md_path = output_dir / "p41_decision_journal.md"
    json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    lines = [
        f"# Decision Journal Guardrails - {payload.get('as_of_date', '')}",
        "",
        f"- Status: {payload.get('status', '')}",
        f"- Entries: {len(payload.get('entries', []))}",
        "",
        "## Journal Summary",
        "",
        "| Ticker | Action | Severity | Cooling-Off Suggestion | Flags |",
        "|--------|--------|----------|------------------------|-------|",
    ]
    for entry in payload.get("entries", []):
        flags = ", ".join(f["flag_id"] for f in entry.get("guardrail_flags", [])[:4])
        lines.append(
            f"| {entry['ticker']} | {entry['contemplated_action']} | "
            f"{entry['severity']} | {entry['cooling_off_suggestion']} | {flags} |"
        )
    lines.extend(["", "## Missing Context", ""])
    any_missing = False
    for entry in payload.get("entries", []):
        if entry.get("missing_context"):
            any_missing = True
            lines.append(f"- {entry['ticker']}: {', '.join(entry['missing_context'])}")
    if not any_missing:
        lines.append("- None")
    lines.extend(["", "---", "", f"> {payload.get('disclaimer', P41_ARTIFACT_DISCLAIMER)}", ""])
    markdown = "\n".join(lines)
    lowered = markdown.lower()
    for forbidden in ("buy this now", "sell this now", "follow this trade", "guaranteed edge", "production approved", "model promoted", "trade now", "order ticket"):
        if forbidden in lowered:
            raise ValueError(f"forbidden decision-journal term rendered: {forbidden}")
    md_path.write_text(markdown, encoding="utf-8")
    return {"json": json_path, "md": md_path}


def run_decision_journal_guardrails(
    db: Any,
    input_payload: dict[str, Any],
    as_of_date: str | None = None,
    output_root: Path | None = None,
) -> dict[str, Any]:
    effective_as_of = as_of_date or input_payload.get("as_of_date", "")
    decisions = input_payload.get("decisions", [])
    if not effective_as_of or not isinstance(decisions, list) or not decisions:
        return {"status": P41_STATUS_BLOCKED_INVALID_INPUT, "entry_count": 0, "warnings": ["invalid input"]}
    db.initialize_decision_journal_schema()
    entries: list[dict[str, Any]] = []
    warnings: list[str] = []
    for item in decisions:
        if not isinstance(item, dict):
            warnings.append("decision_item_not_dict")
            continue
        errors = validate_decision_item(item)
        if errors:
            return {"status": P41_STATUS_BLOCKED_INVALID_INPUT, "entry_count": 0, "warnings": errors}
        ticker = _normalize_ticker(item.get("ticker", ""))
        try:
            memory_pack = db.get_latest_research_memory_pack(ticker, effective_as_of)
        except Exception:
            memory_pack = None
        entry = build_decision_journal_entry(item, effective_as_of, memory_pack)
        db.save_decision_journal_entry(entry)
        entries.append(entry)
    manual_review_count = sum(1 for e in entries if e["severity"] == SEVERITY_MANUAL_REVIEW)
    slow_down_count = sum(1 for e in entries if e["severity"] == SEVERITY_SLOW_DOWN)
    status = P41_STATUS_COMPLETED_WITH_WARNINGS if warnings else P41_STATUS_COMPLETED
    payload = {
        "schema_version": P41_SCHEMA_VERSION,
        "as_of_date": effective_as_of,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": input_payload.get("source", ""),
        "status": status,
        "entries": entries,
        "summary": {
            "entry_count": len(entries),
            "manual_review_count": manual_review_count,
            "slow_down_count": slow_down_count,
        },
        "warnings": warnings,
        "disclaimer": P41_ARTIFACT_DISCLAIMER,
    }
    output_dir = Path(output_root or "output/governance") / effective_as_of
    paths = write_decision_journal_artifacts(payload, output_dir)
    return {
        "status": status,
        "output_dir": str(output_dir),
        "entry_count": len(entries),
        "manual_review_count": manual_review_count,
        "slow_down_count": slow_down_count,
        "warning_count": len(warnings),
        "paths": paths,
    }
