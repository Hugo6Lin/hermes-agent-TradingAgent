"""P42 Boss Co-Pilot Daily Brief - deterministic research-priority evidence."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

P42_SCHEMA_VERSION = "p42_boss_copilot_daily_brief.1"
P42_STATUS_READY = "brief_ready"
P42_STATUS_LIMITED_CONTEXT = "brief_limited_context"
P42_STATUS_NO_CANDIDATES = "brief_no_candidates"
P42_STATUS_BLOCKED_INVALID_INPUT = "blocked_invalid_input"

P42_ARTIFACT_DISCLAIMER = (
    "P42 is daily research-priority evidence only. It summarizes existing "
    "Hermes evidence and does not recommend trades, submit orders, approve "
    "production adoption, train models, schedule jobs, or mutate research decisions."
)

P42_FORBIDDEN_TERMS = (
    "buy this now", "sell this now", "follow this trade", "guaranteed edge",
    "production approved", "model promoted", "trade now", "order ticket",
    "place order", "execute trade",
)

GUARDRAIL_PENALTY = {"info": 0.0, "caution": 0.03, "slow_down": 0.08, "manual_review": 0.15}


def _clamp(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, number))


def _loads(value: Any, fallback: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if value in (None, ""):
        return fallback
    try:
        return json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return fallback


def _ticker(value: Any) -> str:
    return str(value or "").strip().upper()


def _source_hash_payload(brief_seed: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(brief_seed, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def _quality_score(report: dict | None) -> float:
    if not report:
        return 0.0
    return _clamp(report.get("overall_quality_score"))


def _memory_score(pack: dict | None) -> float:
    if not pack:
        return 0.0
    if pack.get("memory_status") == "memory_available":
        return 0.75
    if pack.get("memory_status") == "limited_memory":
        return 0.45
    return 0.2


def _outcome_score(pack: dict | None) -> float:
    if not pack:
        return 0.0
    summary = pack.get("outcome_summary") or {}
    evaluated = int(summary.get("evaluated_rows", 0) or 0)
    if evaluated <= 0:
        return 0.25
    return _clamp(summary.get("win_rate", 0.0))


def _regime_fit_score(candidate: dict, regime_snapshot: dict | None) -> float:
    if not regime_snapshot:
        return 0.0
    confidence = _clamp(regime_snapshot.get("confidence"))
    return round(0.5 + (0.5 * confidence), 6)


def _journal_severity(journal: dict | None) -> str:
    if not journal:
        return "caution"
    return str(journal.get("severity", "info"))


def _priority_band(score: float, severity: str) -> str:
    if severity == "manual_review" or score < 0.35:
        return "context_blocked"
    if score >= 0.75:
        return "high_priority"
    if score >= 0.55:
        return "medium_priority"
    return "low_priority"


def _suggested_action(band: str, missing_context: list[str], severity: str) -> str:
    if severity == "manual_review":
        return "manual_review_before_any_action"
    if missing_context:
        return "refresh_missing_context"
    if band == "context_blocked":
        return "defer_until_context_improves"
    return "review_research_pack"


def _build_priority(candidate: dict, regime_snapshot: dict | None, quality: dict | None, memory: dict | None, journal: dict | None) -> dict[str, Any]:
    ticker = _ticker(candidate.get("ticker"))
    missing_context: list[str] = []
    if not regime_snapshot:
        missing_context.append("missing_market_regime_context")
    if not quality:
        missing_context.append("missing_fundamental_quality")
    if not memory:
        missing_context.append("missing_research_memory")
    if not journal:
        missing_context.append("missing_decision_journal")

    candidate_score = _clamp(candidate.get("total_score"))
    q_score = _quality_score(quality)
    mem_score = _memory_score(memory)
    regime_score = _regime_fit_score(candidate, regime_snapshot)
    outcome_scr = _outcome_score(memory)
    severity = _journal_severity(journal)
    missing_penalty = min(0.30, 0.05 * len(missing_context))
    guardrail_penalty = GUARDRAIL_PENALTY.get(severity, 0.03)
    score = round(max(0.0, min(1.0, (
        0.50 * candidate_score
        + 0.20 * q_score
        + 0.15 * mem_score
        + 0.10 * regime_score
        + 0.05 * outcome_scr
        - missing_penalty
        - guardrail_penalty
    ))), 6)
    band = _priority_band(score, severity)

    risk_notes = []
    risk_notes.extend(_loads(candidate.get("risk_notes_json"), []))
    if quality and quality.get("red_flags"):
        risk_notes.extend(quality.get("red_flags", []))
    if memory:
        risk_notes.extend(memory.get("risk_memory", []))
    if journal and severity in {"slow_down", "manual_review"}:
        risk_notes.append(f"decision_journal_{severity}")

    return {
        "rank": 0,
        "candidate_rank": int(candidate.get("rank", 999999) or 999999),
        "ticker": ticker,
        "sector": candidate.get("sector"),
        "priority_score": score,
        "priority_band": band,
        "research_reason": "; ".join(_loads(candidate.get("inclusion_reasons_json"), [])) or "candidate evidence available",
        "candidate_ref": {"run_id": candidate.get("run_id"), "item_id": candidate.get("item_id"), "source_hash": candidate.get("source_hash", "")},
        "market_regime_ref": {"snapshot_id": (regime_snapshot or {}).get("snapshot_id", ""), "source_hash": (regime_snapshot or {}).get("data_source_hash", (regime_snapshot or {}).get("source_hash", ""))},
        "fundamental_quality_ref": {"report_id": (quality or {}).get("report_id", ""), "source_hash": (quality or {}).get("source_hash", "")},
        "memory_ref": {"pack_id": (memory or {}).get("pack_id", ""), "source_hash": (memory or {}).get("source_hash", "")},
        "decision_guardrail_ref": {"journal_id": (journal or {}).get("journal_id", ""), "source_hash": (journal or {}).get("source_hash", "")},
        "outcome_snapshot": (memory or {}).get("outcome_summary", {}),
        "quality_snapshot": {"label": (quality or {}).get("quality_label", ""), "score": q_score},
        "regime_snapshot": {"label": (regime_snapshot or {}).get("regime_label", ""), "confidence": (regime_snapshot or {}).get("confidence")},
        "memory_snapshot": {"status": (memory or {}).get("memory_status", ""), "themes": (memory or {}).get("recurring_themes", [])},
        "guardrail_snapshot": {"severity": severity, "cooling_off_suggestion": (journal or {}).get("cooling_off_suggestion", "")},
        "missing_context": sorted(set(missing_context)),
        "risk_notes": sorted(set(str(r) for r in risk_notes)),
        "suggested_research_action": _suggested_action(band, missing_context, severity),
        "disclaimer": P42_ARTIFACT_DISCLAIMER,
    }


def compute_boss_copilot_source_hash(seed: dict[str, Any]) -> str:
    return _source_hash_payload(seed)


def build_boss_copilot_daily_brief(
    *,
    as_of_date: str,
    candidate_run: dict | None,
    candidate_items: list[dict],
    regime_snapshot: dict | None,
    quality_by_ticker: dict[str, dict],
    memory_by_ticker: dict[str, dict],
    journal_by_ticker: dict[str, dict],
    max_priorities: int = 8,
) -> dict[str, Any]:
    selected_items = sorted(candidate_items, key=lambda c: (int(c.get("rank", 999999) or 999999), _ticker(c.get("ticker"))))[:max_priorities]
    priorities = [
        _build_priority(
            c,
            regime_snapshot,
            quality_by_ticker.get(_ticker(c.get("ticker"))),
            memory_by_ticker.get(_ticker(c.get("ticker"))),
            journal_by_ticker.get(_ticker(c.get("ticker"))),
        )
        for c in selected_items
    ]
    priorities.sort(key=lambda p: (-p["priority_score"], p["candidate_rank"], p["ticker"]))
    for idx, priority in enumerate(priorities, start=1):
        priority["rank"] = idx

    missing_counts: dict[str, int] = {}
    for priority in priorities:
        for item in priority["missing_context"]:
            missing_counts[item] = missing_counts.get(item, 0) + 1

    if not priorities:
        status = P42_STATUS_NO_CANDIDATES
    elif missing_counts:
        status = P42_STATUS_LIMITED_CONTEXT
    else:
        status = P42_STATUS_READY

    summary = {
        "priority_count": len(priorities),
        "high_priority_count": sum(1 for p in priorities if p["priority_band"] == "high_priority"),
        "medium_priority_count": sum(1 for p in priorities if p["priority_band"] == "medium_priority"),
        "low_priority_count": sum(1 for p in priorities if p["priority_band"] == "low_priority"),
        "context_blocked_count": sum(1 for p in priorities if p["priority_band"] == "context_blocked"),
        "manual_review_count": sum(1 for p in priorities if p["guardrail_snapshot"]["severity"] == "manual_review"),
        "missing_context_counts": dict(sorted(missing_counts.items())),
        "regime_label": (regime_snapshot or {}).get("regime_label", ""),
        "regime_confidence": (regime_snapshot or {}).get("confidence"),
        "candidate_run_ref": {"run_id": (candidate_run or {}).get("run_id", ""), "source_hash": (candidate_run or {}).get("source_hash", "")},
    }
    seed = {
        "schema_version": P42_SCHEMA_VERSION,
        "as_of_date": as_of_date,
        "max_priorities": max_priorities,
        "candidate_run": summary["candidate_run_ref"],
        "regime": priorities[0]["market_regime_ref"] if priorities else {},
        "priorities": [
            {
                "ticker": p["ticker"],
                "candidate": p["candidate_ref"],
                "quality": p["fundamental_quality_ref"],
                "memory": p["memory_ref"],
                "journal": p["decision_guardrail_ref"],
            }
            for p in priorities
        ],
    }
    source_hash = compute_boss_copilot_source_hash(seed)
    brief_id = hashlib.sha256(f"{as_of_date}|{source_hash}".encode("utf-8")).hexdigest()[:16]
    return {
        "schema_version": P42_SCHEMA_VERSION,
        "brief_id": brief_id,
        "as_of_date": as_of_date,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "summary": summary,
        "priorities": priorities,
        "source_hash": source_hash,
        "disclaimer": P42_ARTIFACT_DISCLAIMER,
    }


def write_boss_copilot_daily_brief_artifacts(brief: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "p42_boss_copilot_daily_brief.json"
    md_path = output_dir / "p42_boss_copilot_daily_brief.md"
    json_path.write_text(json.dumps(brief, indent=2, sort_keys=True, default=str), encoding="utf-8")

    lines = [
        "# Boss Co-Pilot Daily Brief",
        "",
        f"As of: `{brief['as_of_date']}`",
        f"Status: `{brief['status']}`",
        f"Priority count: `{brief['summary']['priority_count']}`",
        "",
        "## Market Context",
        "",
        f"- Regime: `{brief['summary'].get('regime_label', '')}`",
        f"- Confidence: `{brief['summary'].get('regime_confidence', '')}`",
        "",
        "## Research Priorities",
        "",
        "| Rank | Ticker | Band | Score | Suggested Research Action | Missing Context |",
        "|------|--------|------|-------|---------------------------|-----------------|",
    ]
    for p in brief.get("priorities", []):
        lines.append(
            f"| {p['rank']} | {p['ticker']} | {p['priority_band']} | "
            f"{p['priority_score']:.4f} | {p['suggested_research_action']} | "
            f"{', '.join(p['missing_context']) or 'none'} |"
        )
    lines.extend(["", "## Guardrails and Slow-Down Notes", ""])
    notes = []
    for p in brief.get("priorities", []):
        severity = p.get("guardrail_snapshot", {}).get("severity", "info")
        if severity != "info":
            notes.append(f"- {p['ticker']}: `{severity}` / `{p['guardrail_snapshot'].get('cooling_off_suggestion', '')}`")
    lines.extend(notes or ["- none"])
    lines.extend(["", "## Evidence Coverage", ""])
    missing = brief["summary"].get("missing_context_counts", {})
    if missing:
        for key, count in sorted(missing.items()):
            lines.append(f"- {key}: {count}")
    else:
        lines.append("- complete for selected priorities")
    lines.extend(["", "---", "", f"> {brief.get('disclaimer', P42_ARTIFACT_DISCLAIMER)}", ""])
    markdown = "\n".join(lines)
    lowered = markdown.lower()
    for forbidden in P42_FORBIDDEN_TERMS:
        if forbidden in lowered:
            raise ValueError(f"forbidden boss co-pilot term rendered: {forbidden}")
    md_path.write_text(markdown, encoding="utf-8")
    return {"json": json_path, "md": md_path}


def run_boss_copilot_daily_brief(db: Any, as_of_date: str, output_root: Path, max_priorities: int = 8) -> dict[str, Any]:
    from datetime import date as _date

    try:
        _date.fromisoformat(as_of_date)
    except (ValueError, TypeError):
        return {"status": P42_STATUS_BLOCKED_INVALID_INPUT, "warnings": ["invalid_date_format"]}
    if max_priorities <= 0:
        return {"status": P42_STATUS_BLOCKED_INVALID_INPUT, "warnings": ["max_priorities_must_be_positive"]}

    db.initialize_candidate_pool_schema()
    db.initialize_market_regime_schema()
    db.initialize_fundamental_quality_schema()
    db.initialize_memory_pack_schema()
    db.initialize_decision_journal_schema()

    candidate_run = db.get_latest_candidate_pool_run_as_of(as_of_date)
    candidate_items = db.list_candidate_pool_items(candidate_run["run_id"]) if candidate_run else []
    regime_rows = db.list_market_regime_snapshots_as_of(as_of_date, limit=1)
    regime_snapshot = regime_rows[0] if regime_rows else None

    tickers = sorted({_ticker(item.get("ticker")) for item in candidate_items if _ticker(item.get("ticker"))})
    quality_by_ticker: dict[str, dict] = {}
    memory_by_ticker: dict[str, dict] = {}
    journal_by_ticker: dict[str, dict] = {}
    for ticker in tickers:
        quality_rows = db.list_fundamental_quality_reports_as_of(ticker, as_of_date, limit=1)
        if quality_rows:
            quality_by_ticker[ticker] = quality_rows[0]
        memory = db.get_latest_research_memory_pack(ticker, as_of_date)
        if memory:
            memory_by_ticker[ticker] = memory
        journal = db.get_latest_decision_journal_entry(ticker, as_of_date)
        if journal:
            journal_by_ticker[ticker] = journal

    brief = build_boss_copilot_daily_brief(
        as_of_date=as_of_date,
        candidate_run=candidate_run,
        candidate_items=candidate_items,
        regime_snapshot=regime_snapshot,
        quality_by_ticker=quality_by_ticker,
        memory_by_ticker=memory_by_ticker,
        journal_by_ticker=journal_by_ticker,
        max_priorities=max_priorities,
    )
    db.save_boss_copilot_daily_brief(brief)
    output_dir = Path(output_root) / as_of_date
    paths = write_boss_copilot_daily_brief_artifacts(brief, output_dir)
    missing_total = sum(brief["summary"].get("missing_context_counts", {}).values())
    return {
        "status": brief["status"],
        "output_dir": str(output_dir),
        "priority_count": brief["summary"]["priority_count"],
        "high_priority_count": brief["summary"]["high_priority_count"],
        "manual_review_count": brief["summary"]["manual_review_count"],
        "missing_context_count": missing_total,
        "paths": paths,
    }
