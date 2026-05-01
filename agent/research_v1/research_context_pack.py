"""P47 read-only research context pack."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

P47_SCHEMA_VERSION = "p47_research_context_pack.1"
P47_DISCLAIMER = (
    "P47 is read-only research context evidence. It does not instruct trades, "
    "submit orders, approve production adoption, train models, schedule jobs, "
    "or change research decisions."
)
FORBIDDEN_RENDER_TERMS = (
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
TICKER_RE = re.compile(r"^[A-Z0-9._-]{1,20}$")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_tickers(tickers: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in tickers:
        ticker = str(raw).strip().upper()
        if ticker and ticker not in seen:
            seen.add(ticker)
            out.append(ticker)
    return out


def validate_request_inputs(
    as_of_date: str,
    tickers: list[str],
    lookback_days: int,
    max_items_per_ticker: int,
    governance_root_is_dir: bool,
) -> dict[str, Any]:
    warnings: list[str] = []
    try:
        date.fromisoformat(as_of_date)
    except ValueError:
        warnings.append(f"invalid_as_of_date:{as_of_date}")
    normalized = normalize_tickers(tickers)
    if not normalized:
        warnings.append("empty_ticker_list")
    for ticker in normalized:
        if not TICKER_RE.match(ticker):
            warnings.append(f"invalid_ticker:{ticker}")
    if lookback_days <= 0:
        warnings.append("lookback_days_must_be_positive")
    if max_items_per_ticker <= 0:
        warnings.append("max_items_per_ticker_must_be_positive")
    if not governance_root_is_dir:
        warnings.append("governance_root_not_a_directory")
    if warnings:
        return {
            "schema_version": P47_SCHEMA_VERSION,
            "status": "blocked_invalid_input",
            "warnings": warnings,
            "tickers": normalized,
        }
    return {"status": "valid", "tickers": normalized, "warnings": []}


def _sha256_json(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _ticker_context(ticker: str, evidence: dict[str, Any], max_items: int) -> dict[str, Any]:
    ticker_evidence = evidence.get("tickers", {}).get(ticker, {})
    source_refs = ticker_evidence.get("source_refs", [])[:max_items]
    sections = {
        "market_regime": ticker_evidence.get("market_regime"),
        "fundamental_quality": ticker_evidence.get("fundamental_quality"),
        "candidate_context": ticker_evidence.get("candidate_context"),
        "outcome_context": ticker_evidence.get("outcome_context"),
        "memory_context": ticker_evidence.get("memory_context"),
        "decision_guardrails": ticker_evidence.get("decision_guardrails"),
        "refresh_context": ticker_evidence.get("refresh_context"),
        "evidence_health": ticker_evidence.get("evidence_health"),
    }
    non_empty = {k: v for k, v in sections.items() if v}
    missing = [] if non_empty else [f"missing_ticker_context:{ticker}"]
    status = "context_ready" if len(non_empty) >= 3 else "context_limited" if non_empty else "context_missing"
    return {
        "ticker": ticker,
        "context_status": status,
        **sections,
        "source_refs": source_refs,
        "missing_context": missing,
        "warnings": ticker_evidence.get("warnings", []),
        "prompt_context": {
            "ticker": ticker,
            "status": status,
            "facts": non_empty,
            "not_wired_to_research_prompts": True,
        },
    }


def build_research_context_pack(
    *,
    as_of_date: str,
    tickers: list[str],
    lookback_days: int,
    max_items_per_ticker: int,
    evidence: dict[str, Any],
    created_at: str | None = None,
) -> dict[str, Any]:
    created = created_at or utc_now_iso()
    normalized = normalize_tickers(tickers)
    system_context = evidence.get("system", {})
    ticker_contexts = [_ticker_context(t, evidence, max_items_per_ticker) for t in normalized]
    missing_context: list[str] = []
    warnings: list[str] = []
    source_refs = list(system_context.get("source_refs", []))
    warnings.extend(system_context.get("warnings", []))
    for ctx in ticker_contexts:
        missing_context.extend(ctx["missing_context"])
        warnings.extend(ctx["warnings"])
        source_refs.extend(ctx["source_refs"])
    has_system = any(system_context.get(k) for k in ("provider_status", "evidence_health_status", "refresh_plan_status"))
    ready_tickers = [ctx for ctx in ticker_contexts if ctx["context_status"] == "context_ready"]
    any_ticker = any(ctx["context_status"] != "context_missing" for ctx in ticker_contexts)
    if ready_tickers and has_system and not missing_context:
        status = "context_pack_ready"
    elif any_ticker or has_system:
        status = "context_pack_limited"
    else:
        status = "context_pack_missing"
    seed = {
        "schema_version": P47_SCHEMA_VERSION,
        "as_of_date": as_of_date,
        "tickers": normalized,
        "lookback_days": lookback_days,
        "max_items_per_ticker": max_items_per_ticker,
        "system_context": system_context,
        "ticker_contexts": ticker_contexts,
        "source_refs": source_refs,
        "missing_context": sorted(set(missing_context)),
        "warnings": sorted(set(warnings)),
    }
    source_hash = _sha256_json(seed)
    pack_id = f"p47-{as_of_date}-{source_hash[:12]}"
    return {
        "schema_version": P47_SCHEMA_VERSION,
        "pack_id": pack_id,
        "as_of_date": as_of_date,
        "created_at": created,
        "status": status,
        "tickers": normalized,
        "lookback_days": lookback_days,
        "max_items_per_ticker": max_items_per_ticker,
        "system_context": system_context,
        "ticker_contexts": ticker_contexts,
        "source_refs": source_refs,
        "missing_context": sorted(set(missing_context)),
        "warnings": sorted(set(warnings)),
        "source_hash": source_hash,
        "disclaimer": P47_DISCLAIMER,
    }


def _assert_safe_rendered(text: str) -> None:
    lowered = text.lower()
    for term in FORBIDDEN_RENDER_TERMS:
        if term in lowered:
            raise ValueError(f"forbidden research context pack term rendered:{term}")


def render_research_context_pack_markdown(pack: dict[str, Any]) -> str:
    lines = [
        "# P47 Research Context Pack",
        "",
        f"Status: {pack['status']}",
        f"As Of: {pack['as_of_date']}",
        "",
        "## System Context",
    ]
    for key, value in sorted(pack.get("system_context", {}).items()):
        if key != "source_refs":
            lines.append(f"- {key}: {value}")
    lines.extend(["", "## Ticker Contexts"])
    for ctx in pack.get("ticker_contexts", []):
        lines.append(f"- {ctx['ticker']}: {ctx['context_status']}")
        for reason in ctx.get("missing_context", []):
            lines.append(f"  - missing: {reason}")
    lines.extend(["", "## Missing Context"])
    lines.extend([f"- {item}" for item in pack.get("missing_context", [])] or ["- none"])
    lines.extend(["", "## Warnings"])
    lines.extend([f"- {item}" for item in pack.get("warnings", [])] or ["- none"])
    lines.extend(["", "## Source References"])
    for ref in pack.get("source_refs", []):
        lines.append(f"- {ref.get('phase_id', 'unknown')} {ref.get('artifact_type', 'artifact')} {ref.get('as_of_date', '')}")
    lines.extend(["", "## Disclaimer", "", pack.get("disclaimer", P47_DISCLAIMER), ""])
    text = "\n".join(lines)
    _assert_safe_rendered(text)
    return text


def write_research_context_pack(pack: dict[str, Any], output_root: Path) -> list[str]:
    output_dir = output_root / pack["as_of_date"]
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "p47_research_context_pack.json"
    md_path = output_dir / "p47_research_context_pack.md"
    json_path.write_text(json.dumps(pack, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_research_context_pack_markdown(pack), encoding="utf-8")
    return [str(json_path), str(md_path)]


def _load_artifact_as_of(governance_root: Path, as_of_date: str, lookback_days: int, filename: str) -> dict | None:
    """Load a JSON artifact from governance_root at or before as_of_date."""
    base = Path(governance_root)
    for offset in range(lookback_days + 1):
        day = (date.fromisoformat(as_of_date) - timedelta(days=offset)).isoformat()
        path = base / day / filename
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return None
    return None


def _safe_db_call(method, *args, _warnings: list[str] | None = None, **kwargs) -> list[dict]:
    """Call a DB method, returning [] if the table doesn't exist."""
    import sqlite3
    try:
        return method(*args, **kwargs)
    except sqlite3.OperationalError as exc:
        if _warnings is not None:
            _warnings.append(f"db_call_failed:{method.__name__}:{exc}")
        return []


def collect_research_context_evidence(
    db: Any,
    governance_root: Path,
    as_of_date: str,
    tickers: list[str],
    lookback_days: int,
) -> dict[str, Any]:
    """Collect P36-P46 evidence for context pack assembly."""
    _warns: list[str] = []
    evidence: dict[str, Any] = {"system": {}, "tickers": {ticker: {} for ticker in tickers}}

    # System context: prefer DB rows at or before as_of_date, fall back to JSON artifacts
    _system_evidence_specs = [
        # (db_method, target_key, phase_id, artifact_filename, id_key)
        ("list_evidence_freshness_drift_reports_as_of", "evidence_health_status", "P44", "p44_evidence_freshness_drift_monitor.json", "report_id"),
        ("list_market_data_readiness_reports_as_of", "provider_status", "P45", "p45_market_data_readiness.json", "report_id"),
        ("list_evidence_refresh_plans_as_of", "refresh_plan_status", "P46", "p46_evidence_refresh_plan.json", "plan_id"),
        ("list_boss_copilot_daily_briefs_as_of", "latest_boss_brief_status", "P42", "p42_boss_copilot_daily_brief.json", "brief_id"),
        ("list_copilot_console_indexes_as_of", "latest_console_index_status", "P43", "p43_copilot_console_index.json", "index_id"),
    ]
    for method_name, target_key, phase_id, artifact_filename, id_key in _system_evidence_specs:
        populated = False
        method = getattr(db, method_name, None)
        if method:
            rows = _safe_db_call(method, as_of_date, _warnings=_warns)
            if rows:
                row = rows[0]
                evidence["system"][target_key] = row.get("status")
                evidence["system"].setdefault("source_refs", []).append({
                    "phase_id": phase_id,
                    "artifact_type": method_name,
                    "source_id": row.get(id_key, ""),
                    "as_of_date": row.get("as_of_date"),
                    "created_at": row.get("created_at"),
                    "source_hash": row.get("source_hash"),
                })
                populated = True
        if not populated:
            artifact = _load_artifact_as_of(governance_root, as_of_date, lookback_days, artifact_filename)
            if artifact:
                evidence["system"][target_key] = artifact.get("status", "unknown")
                evidence["system"].setdefault("source_refs", []).append({
                    "phase_id": phase_id,
                    "artifact_type": "json_artifact",
                    "source_id": artifact.get("report_id", ""),
                    "as_of_date": artifact.get("as_of_date"),
                    "created_at": artifact.get("created_at"),
                    "source_hash": artifact.get("source_hash"),
                    "path": str(governance_root / artifact.get("as_of_date", "") / artifact_filename),
                })

    # Ticker context from P37 (market regime - system-wide but relevant per ticker)
    regime_method = getattr(db, "list_market_regime_snapshots_as_of", None)
    regime_snapshot = None
    if regime_method:
        rows = _safe_db_call(regime_method, as_of_date, _warnings=_warns)
        if rows:
            regime_snapshot = rows[0]
    if not regime_snapshot:
        regime_snapshot = _load_artifact_as_of(governance_root, as_of_date, lookback_days, "p37_market_regime_snapshot.json")

    for ticker in tickers:
        tctx = evidence["tickers"][ticker]

        # Market regime (system-wide, same for all tickers)
        if regime_snapshot:
            tctx["market_regime"] = {
                "regime_label": regime_snapshot.get("regime_label", regime_snapshot.get("status", "")),
                "as_of_date": regime_snapshot.get("as_of_date"),
            }
            tctx.setdefault("source_refs", []).append({
                "phase_id": "P37",
                "artifact_type": "market_regime_snapshot",
                "source_id": regime_snapshot.get("snapshot_id", regime_snapshot.get("report_id", "")),
                "as_of_date": regime_snapshot.get("as_of_date"),
                "created_at": regime_snapshot.get("created_at"),
                "source_hash": regime_snapshot.get("source_hash", regime_snapshot.get("data_source_hash", "")),
            })

        # Fundamental quality (P38 - per ticker)
        quality_method = getattr(db, "list_fundamental_quality_reports_as_of", None)
        if quality_method:
            rows = _safe_db_call(quality_method, ticker, as_of_date, _warnings=_warns)
            if rows:
                row = rows[0]
                tctx["fundamental_quality"] = {
                    "quality_score": row.get("overall_quality_score"),
                    "quality_label": row.get("quality_label"),
                    "as_of_date": row.get("as_of_date"),
                }
                tctx.setdefault("source_refs", []).append({
                    "phase_id": "P38",
                    "artifact_type": "fundamental_quality_report",
                    "source_id": row.get("report_id"),
                    "as_of_date": row.get("as_of_date"),
                    "created_at": row.get("created_at"),
                    "source_hash": row.get("source_hash"),
                })

        # Candidate pool (P39 - per ticker)
        candidate_method = getattr(db, "list_candidate_pool_items_for_ticker", None)
        if candidate_method:
            rows = _safe_db_call(candidate_method, ticker, as_of_date, lookback_days, limit=3, _warnings=_warns)
            if rows:
                row = rows[0]
                tctx["candidate_context"] = {
                    "candidate_status": row.get("candidate_status"),
                    "candidate_category": row.get("candidate_category"),
                    "as_of_date": row.get("as_of_date"),
                }
                tctx.setdefault("source_refs", []).append({
                    "phase_id": "P39",
                    "artifact_type": "candidate_pool_item",
                    "source_id": row.get("item_id"),
                    "as_of_date": row.get("as_of_date"),
                    "created_at": row.get("created_at"),
                    "source_hash": row.get("source_hash"),
                })

        # Outcome context (P36 - per ticker)
        outcome_method = getattr(db, "list_canonical_outcomes_for_ticker", None)
        if outcome_method:
            rows = _safe_db_call(outcome_method, ticker, as_of_date, lookback_days, limit=3, _warnings=_warns)
            if rows:
                row = rows[0]
                tctx["outcome_context"] = {
                    "status": row.get("status"),
                    "net_return_pct": row.get("net_return_pct"),
                    "as_of_date": row.get("evaluated_for_date"),
                }
                tctx.setdefault("source_refs", []).append({
                    "phase_id": "P36",
                    "artifact_type": "recommendation_outcome",
                    "source_id": row.get("canonical_outcome_id"),
                    "as_of_date": row.get("evaluated_for_date"),
                    "created_at": row.get("evaluated_at"),
                    "source_hash": row.get("data_source_hash"),
                })

        # Memory context (P40 - per ticker)
        memory_method = getattr(db, "list_research_memory_packs_as_of", None)
        if memory_method:
            rows = _safe_db_call(memory_method, ticker, as_of_date, _warnings=_warns)
            if rows:
                row = rows[0]
                tctx["memory_context"] = {
                    "memory_status": row.get("memory_status"),
                    "as_of_date": row.get("as_of_date"),
                }
                tctx.setdefault("source_refs", []).append({
                    "phase_id": "P40",
                    "artifact_type": "research_memory_pack",
                    "source_id": row.get("pack_id"),
                    "as_of_date": row.get("as_of_date"),
                    "created_at": row.get("created_at"),
                    "source_hash": row.get("source_hash"),
                })

        # Decision guardrails (P41 - per ticker)
        journal_method = getattr(db, "list_decision_journal_entries_as_of", None)
        if journal_method:
            rows = _safe_db_call(journal_method, ticker, as_of_date, _warnings=_warns)
            if rows:
                row = rows[0]
                tctx["decision_guardrails"] = {
                    "entry_status": row.get("entry_status"),
                    "as_of_date": row.get("as_of_date"),
                }
                tctx.setdefault("source_refs", []).append({
                    "phase_id": "P41",
                    "artifact_type": "decision_journal_entry",
                    "source_id": row.get("entry_id"),
                    "as_of_date": row.get("as_of_date"),
                    "created_at": row.get("created_at"),
                    "source_hash": row.get("source_hash"),
                })

    if _warns:
        evidence["system"]["warnings"] = sorted(set(_warns))
    return evidence


def run_research_context_pack(
    db: Any,
    governance_root: Path,
    output_root: Path,
    as_of_date: str,
    tickers: list[str],
    lookback_days: int = 180,
    max_items_per_ticker: int = 8,
) -> dict[str, Any]:
    """Run P47 research context pack assembly."""
    governance_root = Path(governance_root)
    validation = validate_request_inputs(
        as_of_date, tickers, lookback_days, max_items_per_ticker,
        governance_root.is_dir() if governance_root.exists() else True,
    )
    if validation["status"] == "blocked_invalid_input":
        return validation
    normalized = validation["tickers"]
    evidence = collect_research_context_evidence(db, governance_root, as_of_date, normalized, lookback_days)
    pack = build_research_context_pack(
        as_of_date=as_of_date,
        tickers=normalized,
        lookback_days=lookback_days,
        max_items_per_ticker=max_items_per_ticker,
        evidence=evidence,
    )
    artifacts = write_research_context_pack(pack, Path(output_root))
    if hasattr(db, "save_research_context_pack"):
        db.save_research_context_pack(pack)
    pack["artifacts"] = artifacts
    return pack
