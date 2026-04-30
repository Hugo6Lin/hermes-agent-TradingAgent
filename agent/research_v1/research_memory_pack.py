"""P40 Research Memory Pack — deterministic ticker-level memory evidence."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any

P40_SCHEMA_VERSION = "p40_research_memory_pack.1"

P40_STATUS_MEMORY_AVAILABLE = "memory_available"
P40_STATUS_LIMITED_MEMORY = "limited_memory"
P40_STATUS_NO_PRIOR_MEMORY = "no_prior_memory"
P40_STATUS_BLOCKED_INVALID_INPUT = "blocked_invalid_input"

P40_ARTIFACT_DISCLAIMER = (
    "P40 is research-memory evidence only. It summarizes historical Hermes "
    "context and does not recommend trades, approve production adoption, place "
    "orders, train models, schedule jobs, or mutate research decisions."
)

P40_FORBIDDEN_TERMS = (
    "buy this now",
    "sell this now",
    "follow this trade",
    "guaranteed edge",
    "production approved",
    "model promoted",
    "trade now",
)


def normalize_memory_tickers(tickers: list[str]) -> list[str]:
    cleaned = {str(t).strip().upper() for t in tickers if str(t).strip()}
    return sorted(cleaned)


def _json_load(value: Any, fallback: Any) -> Any:
    if value is None:
        return fallback
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError, ValueError):
        return fallback


def _resolve_visible_action(report: dict[str, Any]) -> tuple[str, list[str]]:
    warnings: list[str] = []
    decision_card = report.get("decision_card") or _json_load(report.get("decision_card_json"), None)
    instrument = report.get("instrument_rec") or _json_load(report.get("instrument_rec_json"), None)
    trade_plan = report.get("trade_plan") or _json_load(report.get("trade_plan_json"), None)
    if isinstance(decision_card, dict) and decision_card.get("primary_action"):
        return str(decision_card["primary_action"]), warnings
    if isinstance(instrument, dict) and instrument.get("primary_action"):
        return str(instrument["primary_action"]), warnings
    if isinstance(trade_plan, dict) and trade_plan.get("action"):
        warnings.append("legacy_action_fallback_used")
        return str(trade_plan["action"]), warnings
    return "unknown_prior_action", warnings


def _summarize_outcomes(outcomes_by_signal: dict[str, list[dict]], as_of_date: str = "") -> dict[str, Any]:
    all_outcomes: list[dict] = []
    for signal_id, rows in outcomes_by_signal.items():
        for row in rows:
            eval_date = row.get("evaluated_for_date", "")
            if as_of_date and eval_date and eval_date > as_of_date:
                continue
            all_outcomes.append(row)

    total = len(all_outcomes)
    evaluated_rows = sum(1 for o in all_outcomes if o.get("status") == "evaluated")
    not_applicable_rows = sum(1 for o in all_outcomes if o.get("status") == "not_applicable")
    insufficient_data_rows = sum(1 for o in all_outcomes if o.get("status") == "insufficient_data")

    numeric_returns = [
        o["net_return_pct"]
        for o in all_outcomes
        if o.get("net_return_pct") is not None and isinstance(o.get("net_return_pct"), (int, float))
    ]
    median_return = round(median(numeric_returns), 6) if numeric_returns else None
    best_return = round(max(numeric_returns), 6) if numeric_returns else None
    worst_return = round(min(numeric_returns), 6) if numeric_returns else None

    # Win rate: use persisted win field, else derive from net_return_pct > 0
    win_rows = [o for o in all_outcomes if o.get("status") == "evaluated"]
    if win_rows and all("win" in o for o in win_rows):
        win_count = sum(1 for o in win_rows if o["win"])
    else:
        win_count = sum(1 for o in win_rows if (o.get("net_return_pct") or 0) > 0)
    win_rate = round(win_count / len(win_rows), 4) if win_rows else 0.0

    status_counts: dict[str, int] = {}
    for o in all_outcomes:
        s = o.get("status", "unknown")
        status_counts[s] = status_counts.get(s, 0) + 1

    latest_dates = [o.get("evaluated_for_date", "") for o in all_outcomes if o.get("evaluated_for_date")]
    latest_outcome_date = max(latest_dates) if latest_dates else ""

    return {
        "total_outcome_rows": total,
        "evaluated_rows": evaluated_rows,
        "not_applicable_rows": not_applicable_rows,
        "insufficient_data_rows": insufficient_data_rows,
        "win_rate": win_rate,
        "median_net_return_pct": median_return,
        "best_net_return_pct": best_return,
        "worst_net_return_pct": worst_return,
        "latest_outcome_date": latest_outcome_date,
        "status_counts": status_counts,
    }


def _summarize_candidate_history(candidate_items: list[dict]) -> dict[str, Any]:
    if not candidate_items:
        return {
            "appearance_count": 0,
            "latest_candidate_date": "",
            "latest_category": "",
            "latest_workflow_action": "",
            "best_total_score": 0.0,
            "latest_total_score": 0.0,
            "recent_inclusion_reasons": [],
            "recent_missing_context": [],
        }

    sorted_items = sorted(candidate_items, key=lambda r: (r.get("created_at", ""), r.get("item_id", "")), reverse=True)
    latest = sorted_items[0]
    scores = [item.get("total_score", 0.0) for item in sorted_items if isinstance(item.get("total_score"), (int, float))]
    best_score = round(max(scores), 6) if scores else 0.0
    latest_score = round(latest.get("total_score", 0.0), 6) if isinstance(latest.get("total_score"), (int, float)) else 0.0

    latest_reasons = _json_load(latest.get("inclusion_reasons_json"), [])
    latest_missing = _json_load(latest.get("missing_context_json"), [])

    return {
        "appearance_count": len(sorted_items),
        "latest_candidate_date": latest.get("created_at", ""),
        "latest_category": latest.get("candidate_category", ""),
        "latest_workflow_action": latest.get("workflow_action", ""),
        "best_total_score": best_score,
        "latest_total_score": latest_score,
        "recent_inclusion_reasons": latest_reasons if isinstance(latest_reasons, list) else [],
        "recent_missing_context": latest_missing if isinstance(latest_missing, list) else [],
    }


def _quality_context(quality_report: dict | None, missing_context: list[str]) -> dict[str, Any]:
    if not quality_report:
        missing_context.append("missing_fundamental_quality")
        return {}
    return {
        "as_of_date": quality_report.get("as_of_date", ""),
        "quality_label": quality_report.get("quality_label", ""),
        "overall_quality_score": quality_report.get("overall_quality_score"),
        "confidence": quality_report.get("confidence"),
        "red_flags": quality_report.get("red_flags", []),
        "missing_required_fields": quality_report.get("missing_required_fields", []),
        "source_hash": quality_report.get("source_hash", ""),
    }


def _regime_context(regime_snapshot: dict | None, missing_context: list[str]) -> dict[str, Any]:
    if not regime_snapshot:
        missing_context.append("missing_market_regime_context")
        return {}
    return {
        "as_of_date": regime_snapshot.get("as_of_date", ""),
        "regime_label": regime_snapshot.get("regime_label", ""),
        "confidence": regime_snapshot.get("confidence"),
        "source_hash": regime_snapshot.get("data_source_hash", regime_snapshot.get("source_hash", "")),
    }


def _derive_recurring_themes(pack_parts: dict, as_of_date: str = "") -> list[str]:
    themes: list[str] = []

    candidate = pack_parts.get("candidate_history", {})
    if candidate.get("appearance_count", 0) >= 2:
        category = candidate.get("latest_category", "")
        if "quality" in category:
            themes.append("repeated_quality_candidate")
        if "momentum" in category:
            themes.append("repeated_momentum_candidate")

    latest = pack_parts.get("latest_research", {})
    if latest.get("confidence") and isinstance(latest["confidence"], (int, float)) and latest["confidence"] >= 0.75:
        themes.append("prior_high_confidence_research")

    watchlist = pack_parts.get("watchlist_context", {})
    if watchlist.get("status"):
        themes.append("prior_watchlist_state")

    outcomes = pack_parts.get("outcome_summary", {})
    if outcomes.get("win_rate", 0) > 0.6 and outcomes.get("evaluated_rows", 0) >= 2:
        themes.append("positive_outcome_history")
    elif outcomes.get("win_rate", 0) < 0.4 and outcomes.get("evaluated_rows", 0) >= 2:
        themes.append("negative_outcome_history")

    latest_research = pack_parts.get("latest_research", {})
    if latest_research.get("created_at") and as_of_date:
        try:
            created = datetime.fromisoformat(latest_research["created_at"].replace("Z", "+00:00"))
            as_of = datetime.fromisoformat(as_of_date + "T00:00:00+00:00")
            if (as_of - created).days > 90:
                themes.append("stale_research_context")
        except (ValueError, TypeError):
            pass

    return sorted(themes)


def _derive_risk_memory(pack_parts: dict, action_warnings: list[str]) -> list[str]:
    risks: list[str] = []

    outcomes = pack_parts.get("outcome_summary", {})
    if outcomes.get("insufficient_data_rows", 0) > 0:
        risks.append("prior_insufficient_outcome_data")

    missing = pack_parts.get("missing_context_list", [])
    missing_count = sum(1 for m in missing if m.startswith("missing_"))
    if missing_count >= 3:
        risks.append("recurring_missing_context")

    quality = pack_parts.get("quality_context", {})
    red_flags = quality.get("red_flags", [])
    if red_flags:
        risks.append("quality_red_flags_present")

    risks.extend(action_warnings)

    return sorted(set(risks))


def compute_research_memory_source_hash(pack_seed: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(pack_seed, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def build_research_memory_pack(
    ticker: str,
    as_of_date: str,
    lookback_days: int,
    records: dict[str, Any],
    max_items_per_ticker: int = 5,
) -> dict[str, Any]:
    ticker = ticker.strip().upper()
    created_at = datetime.now(timezone.utc).isoformat()
    signals = sorted(
        records.get("signals", []),
        key=lambda r: (r.get("created_at", ""), r.get("signal_id", "")),
        reverse=True,
    )
    reports = sorted(
        records.get("reports", []),
        key=lambda r: (r.get("created_at", ""), r.get("report_id", "")),
        reverse=True,
    )
    selected_signals = signals[:max_items_per_ticker]
    selected_reports = reports[:max_items_per_ticker]

    action_warnings: list[str] = []
    latest_research: dict[str, Any] = {}
    if selected_reports or selected_signals:
        latest_report = selected_reports[0] if selected_reports else {}
        latest_signal = selected_signals[0] if selected_signals else {}
        visible_action, action_warnings = _resolve_visible_action(latest_report)
        latest_research = {
            "task_id": latest_signal.get("task_id") or latest_report.get("task_id", ""),
            "signal_id": latest_signal.get("signal_id", ""),
            "report_id": latest_report.get("report_id", ""),
            "created_at": latest_signal.get("created_at") or latest_report.get("created_at", ""),
            "rating": latest_signal.get("rating", ""),
            "confidence": latest_signal.get("confidence"),
            "priority_score": latest_signal.get("priority_score"),
            "visible_action": visible_action,
            "title": latest_report.get("title", ""),
            "bottom_line": latest_report.get("bottom_line", ""),
            "why_now": latest_report.get("why_now", ""),
            "risk_flags": latest_signal.get("risk_flags") or _json_load(latest_signal.get("risk_flags_json"), []),
            "decision_reason": latest_signal.get("decision_reason", ""),
        }

    missing_context: list[str] = []
    if not latest_research:
        missing_context.append("missing_research_context")
    outcome_summary = _summarize_outcomes(records.get("outcomes_by_signal", {}), as_of_date)
    if outcome_summary["total_outcome_rows"] == 0:
        missing_context.append("missing_outcome_context")
    candidate_history = _summarize_candidate_history(records.get("candidate_items", []))
    if candidate_history["appearance_count"] == 0:
        missing_context.append("missing_candidate_history")
    quality_context = _quality_context(records.get("quality_report"), missing_context)
    regime_context = _regime_context(records.get("regime_snapshot"), missing_context)
    watchlist_context = records.get("watchlist_entry") or {}
    validation_context = records.get("validation_result") or {}
    if not watchlist_context:
        missing_context.append("missing_watchlist_context")
    if not validation_context:
        missing_context.append("missing_validation_context")

    pack_parts = {
        "latest_research": latest_research,
        "outcome_summary": outcome_summary,
        "candidate_history": candidate_history,
        "quality_context": quality_context,
        "regime_context": regime_context,
        "watchlist_context": watchlist_context,
        "validation_context": validation_context,
        "missing_context_list": missing_context,
    }
    recurring_themes = _derive_recurring_themes(pack_parts, as_of_date)
    risk_memory = _derive_risk_memory(pack_parts, action_warnings)
    source_refs = {
        "signal_ids": [row.get("signal_id", "") for row in selected_signals],
        "report_ids": [row.get("report_id", "") for row in selected_reports],
        "candidate_item_ids": [row.get("item_id", "") for row in records.get("candidate_items", [])[:max_items_per_ticker]],
        "p38_source_hash": quality_context.get("source_hash", ""),
        "p37_source_hash": regime_context.get("source_hash", ""),
    }
    source_hash = compute_research_memory_source_hash({
        "schema_version": P40_SCHEMA_VERSION,
        "ticker": ticker,
        "as_of_date": as_of_date,
        "lookback_days": lookback_days,
        "source_refs": source_refs,
        "latest_research": latest_research,
        "outcome_summary": outcome_summary,
        "candidate_history": candidate_history,
        "quality_context": quality_context,
        "regime_context": regime_context,
        "watchlist_updated_at": watchlist_context.get("updated_at", ""),
        "validation_updated_at": validation_context.get("updated_at", ""),
    })
    pack_id = hashlib.sha256(f"{ticker}|{as_of_date}|{lookback_days}|{source_hash}".encode("utf-8")).hexdigest()[:16]
    has_primary_memory = bool(selected_signals or selected_reports or outcome_summary["total_outcome_rows"] or candidate_history["appearance_count"])
    has_any_context = has_primary_memory or bool(quality_context or regime_context or watchlist_context or validation_context)
    status = P40_STATUS_MEMORY_AVAILABLE if has_primary_memory else (P40_STATUS_LIMITED_MEMORY if has_any_context else P40_STATUS_NO_PRIOR_MEMORY)
    return {
        "schema_version": P40_SCHEMA_VERSION,
        "pack_id": pack_id,
        "as_of_date": as_of_date,
        "created_at": created_at,
        "ticker": ticker,
        "lookback_days": lookback_days,
        "memory_status": status,
        "latest_research": latest_research,
        "prior_signals": selected_signals,
        "outcome_summary": outcome_summary,
        "candidate_history": candidate_history,
        "quality_context": quality_context,
        "regime_context": regime_context,
        "watchlist_context": watchlist_context,
        "validation_context": validation_context,
        "recurring_themes": recurring_themes,
        "risk_memory": risk_memory,
        "missing_context": sorted(set(missing_context)),
        "source_refs": source_refs,
        "source_hash": source_hash,
        "disclaimer": P40_ARTIFACT_DISCLAIMER,
    }


def write_research_memory_artifacts(payload: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "p40_research_memory_pack.json"
    md_path = output_dir / "p40_research_memory_pack.md"
    json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    packs = payload.get("packs", [])
    lines = [
        f"# Research Memory Pack - {payload.get('as_of_date', '')}",
        "",
        f"- Status: {payload.get('status', '')}",
        f"- Tickers: {len(packs)}",
        "",
        "## Ticker Summary",
        "",
        "| Ticker | Status | Latest Action | Outcomes | Candidate Appearances |",
        "|--------|--------|---------------|----------|-----------------------|",
    ]
    for pack in packs:
        latest = pack.get("latest_research", {})
        outcome = pack.get("outcome_summary", {})
        candidate = pack.get("candidate_history", {})
        lines.append(
            f"| {pack['ticker']} | {pack['memory_status']} | "
            f"{latest.get('visible_action', 'historical context only')} | "
            f"{outcome.get('evaluated_rows', 0)} evaluated | "
            f"{candidate.get('appearance_count', 0)} |"
        )

    # Latest research context section
    lines.extend(["", "## Latest Research Context", ""])
    for pack in packs:
        latest = pack.get("latest_research", {})
        if latest:
            lines.append(f"### {pack['ticker']}")
            lines.append(f"- Action: {latest.get('visible_action', 'unknown')}")
            lines.append(f"- Rating: {latest.get('rating', 'N/A')}")
            lines.append(f"- Date: {latest.get('created_at', 'N/A')}")
            if latest.get("bottom_line"):
                lines.append(f"- Bottom line: {latest['bottom_line']}")
            lines.append("")

    # Outcome memory section
    lines.extend(["## Outcome Memory", ""])
    for pack in packs:
        outcome = pack.get("outcome_summary", {})
        if outcome.get("total_outcome_rows", 0) > 0:
            lines.append(f"### {pack['ticker']}")
            lines.append(f"- Evaluated: {outcome.get('evaluated_rows', 0)}")
            lines.append(f"- Win rate: {outcome.get('win_rate', 0):.1%}")
            if outcome.get("median_net_return_pct") is not None:
                lines.append(f"- Median return: {outcome['median_net_return_pct']:.2%}")
            lines.append("")

    # Candidate history section
    lines.extend(["## Candidate History", ""])
    for pack in packs:
        candidate = pack.get("candidate_history", {})
        if candidate.get("appearance_count", 0) > 0:
            lines.append(f"### {pack['ticker']}")
            lines.append(f"- Appearances: {candidate['appearance_count']}")
            lines.append(f"- Best score: {candidate.get('best_total_score', 0):.2f}")
            lines.append(f"- Latest category: {candidate.get('latest_category', 'N/A')}")
            lines.append("")

    # Missing context section
    lines.extend(["## Missing Context", ""])
    for pack in packs:
        missing = pack.get("missing_context", [])
        if missing:
            lines.append(f"- {pack['ticker']}: {', '.join(missing)}")
    if not any(pack.get("missing_context") for pack in packs):
        lines.append("- None")
    lines.append("")

    # Risk memory section
    lines.extend(["## Risk Memory", ""])
    for pack in packs:
        risks = pack.get("risk_memory", [])
        if risks:
            lines.append(f"- {pack['ticker']}: {', '.join(risks)}")
    if not any(pack.get("risk_memory") for pack in packs):
        lines.append("- None")
    lines.append("")

    lines.extend(["---", "", f"> {payload.get('disclaimer', P40_ARTIFACT_DISCLAIMER)}", ""])
    markdown = "\n".join(lines)
    lowered = markdown.lower()
    for forbidden in P40_FORBIDDEN_TERMS:
        if forbidden in lowered:
            raise ValueError(f"forbidden research-memory term rendered: {forbidden}")
    md_path.write_text(markdown, encoding="utf-8")
    return {"json": json_path, "md": md_path}


def run_research_memory_pack(
    db: Any,
    tickers: list[str],
    as_of_date: str,
    lookback_days: int = 180,
    output_root: Path | None = None,
    max_items_per_ticker: int = 5,
) -> dict[str, Any]:
    normalized = normalize_memory_tickers(tickers)
    if not normalized:
        return {"status": P40_STATUS_BLOCKED_INVALID_INPUT, "ticker_count": 0, "warnings": ["empty ticker list"]}
    db.initialize_memory_pack_schema()
    packs: list[dict[str, Any]] = []
    warnings: list[str] = []
    for ticker in normalized:
        records: dict[str, Any] = {}
        try:
            records["signals"] = db.list_canonical_signals_for_ticker(ticker, as_of_date, lookback_days, max_items_per_ticker)
        except Exception:
            records["signals"] = []
            warnings.append(f"{ticker}:missing_signal_table")
        try:
            records["reports"] = db.list_canonical_reports_for_ticker(ticker, as_of_date, lookback_days, max_items_per_ticker)
        except Exception:
            records["reports"] = []
            warnings.append(f"{ticker}:missing_report_table")
        try:
            records["candidate_items"] = db.list_candidate_pool_items_for_ticker(ticker, as_of_date, lookback_days, max_items_per_ticker)
        except Exception:
            records["candidate_items"] = []
        try:
            q = db.list_fundamental_quality_reports_as_of(ticker, as_of_date, limit=1)
            records["quality_report"] = q[0] if q else None
        except Exception:
            records["quality_report"] = None
        try:
            r = db.list_market_regime_snapshots_as_of(as_of_date, limit=1)
            records["regime_snapshot"] = r[0] if r else None
        except Exception:
            records["regime_snapshot"] = None
        try:
            records["watchlist_entry"] = db.get_watchlist_entry_for_ticker(ticker)
        except Exception:
            records["watchlist_entry"] = None
        try:
            records["validation_result"] = db.get_validation_result_for_ticker(ticker)
        except Exception:
            records["validation_result"] = None
        # Gather outcomes keyed by signal_id
        outcomes_by_signal: dict[str, list[dict]] = {}
        for sig in records.get("signals", []):
            sid = sig.get("signal_id", "")
            if sid:
                try:
                    outcomes_by_signal[sid] = db.list_canonical_outcomes_by_signal(sid)
                except Exception:
                    outcomes_by_signal[sid] = []
        records["outcomes_by_signal"] = outcomes_by_signal
        pack = build_research_memory_pack(ticker, as_of_date, lookback_days, records, max_items_per_ticker)
        db.save_research_memory_pack(pack)
        packs.append(pack)
    summary = {
        "ticker_count": len(packs),
        "memory_available": sum(1 for p in packs if p["memory_status"] == P40_STATUS_MEMORY_AVAILABLE),
        "limited_memory": sum(1 for p in packs if p["memory_status"] == P40_STATUS_LIMITED_MEMORY),
        "no_prior_memory": sum(1 for p in packs if p["memory_status"] == P40_STATUS_NO_PRIOR_MEMORY),
    }
    payload = {
        "schema_version": P40_SCHEMA_VERSION,
        "as_of_date": as_of_date,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "completed",
        "packs": packs,
        "summary": summary,
        "warnings": warnings,
        "disclaimer": P40_ARTIFACT_DISCLAIMER,
    }
    output_dir = Path(output_root or "output/governance") / as_of_date
    paths = write_research_memory_artifacts(payload, output_dir)
    return {"status": "completed", "output_dir": str(output_dir), "warning_count": len(warnings), "paths": paths, **summary}
