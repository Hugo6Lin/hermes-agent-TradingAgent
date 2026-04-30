"""P39 Candidate Pool Engine — standalone candidate-discovery evidence only.

This module screens a point-in-time ticker universe, ranks candidates, and
explains inclusion or exclusion. It does not recommend trades, approve
production adoption, place orders, train models, schedule jobs, or mutate
research decisions.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── Schema & status constants ────────────────────────────────────────────────

P39_SCHEMA_VERSION = "p39_candidate_pool.1"

P39_STATUS_COMPLETED = "completed"
P39_STATUS_COMPLETED_WITH_WARNINGS = "completed_with_warnings"
P39_STATUS_NO_CANDIDATES = "no_candidates"
P39_STATUS_BLOCKED_INVALID_INPUT = "blocked_invalid_input"

CANDIDATE_STATUS_INCLUDED = "included"
CANDIDATE_STATUS_EXCLUDED_MISSING_REQUIRED_FIELDS = "excluded_missing_required_fields"
CANDIDATE_STATUS_EXCLUDED_FUTURE_SOURCE_DATE = "excluded_future_source_date"
CANDIDATE_STATUS_EXCLUDED_LOW_LIQUIDITY = "excluded_low_liquidity"
CANDIDATE_STATUS_EXCLUDED_LOW_PRICE = "excluded_low_price"
CANDIDATE_STATUS_EXCLUDED_USER_RULE = "excluded_user_rule"

WORKFLOW_RESEARCH = "research_candidate"
WORKFLOW_MONITOR = "monitor_candidate"
WORKFLOW_DEFER = "defer_candidate"

P39_ARTIFACT_DISCLAIMER = (
    "P39 is candidate-discovery evidence only. It does not recommend trades, "
    "approve production adoption, place orders, train models, schedule jobs, "
    "or mutate research decisions."
)

P39_REQUIRED_TICKER_FIELDS = (
    "ticker",
    "sector",
    "source_date",
    "close",
    "close_20d_ago",
    "close_60d_ago",
    "close_120d_ago",
    "high_252d",
    "low_252d",
    "avg_dollar_volume_20d",
    "realized_vol_20d",
)

P39_FORBIDDEN_TERMS = (
    "buy this",
    "sell this",
    "follow this trade",
    "guaranteed edge",
    "production approved",
    "model promoted",
    "trade now",
)

P39_SEVERE_P38_RED_FLAGS = frozenset({
    "negative_revenue",
    "negative_equity",
    "negative_fcf",
    "fcf_conversion_below_zero",
    "debt_to_equity_high",
    "net_debt_to_fcf_high",
})

P39_COMPONENT_WEIGHTS = {
    "momentum_score": 0.30,
    "quality_score": 0.25,
    "regime_score": 0.20,
    "liquidity_score": 0.10,
    "risk_penalty_score": 0.10,
    "track_record_score": 0.05,
}

P39_CYCLICAL_SECTORS = frozenset({
    "technology", "communication_services", "consumer_discretionary",
    "industrials", "materials", "financials",
})
P39_DEFENSIVE_SECTORS = frozenset({
    "utilities", "consumer_staples", "healthcare",
})

P39_REGIME_LABEL_FALLBACK = {
    "risk_on_broad": {
        "cyclical": 0.75,
        "defensive": 0.45,
        "default": 0.55,
    },
    "risk_on_narrow": {
        "technology": 0.70,
        "communication_services": 0.70,
        "default": 0.45,
    },
    "neutral": {
        "default": 0.50,
    },
    "risk_off": {
        "defensive": 0.70,
        "cyclical": 0.40,
        "default": 0.50,
    },
    "high_volatility": {
        "default": 0.35,
    },
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _scale(value: float, low: float, high: float) -> float:
    if high == low:
        return 0.5
    return _clamp((value - low) / (high - low))


def _safe_return(current: float, prior: float) -> float:
    if prior == 0:
        return 0.0
    return current / prior - 1.0


# ── Component scoring ────────────────────────────────────────────────────────

def _momentum_score(row: dict[str, Any]) -> tuple[float, dict[str, float]]:
    close = float(row["close"])
    r20 = _safe_return(close, float(row["close_20d_ago"]))
    r60 = _safe_return(close, float(row["close_60d_ago"]))
    r120 = _safe_return(close, float(row["close_120d_ago"]))
    distance = _safe_return(close, float(row["high_252d"]))
    score = (
        0.50 * _scale(r60, -0.20, 0.30)
        + 0.30 * _scale(r20, -0.10, 0.15)
        + 0.20 * _scale(distance, -0.35, 0.0)
    )
    return round(score, 4), {
        "return_20d": round(r20, 4),
        "return_60d": round(r60, 4),
        "return_120d": round(r120, 4),
        "distance_from_252d_high": round(distance, 4),
    }


def _liquidity_score(avg_dollar_volume_20d: float) -> float:
    if avg_dollar_volume_20d < 5_000_000:
        return 0.0
    if avg_dollar_volume_20d <= 50_000_000:
        return round(_scale(avg_dollar_volume_20d, 5_000_000, 50_000_000) * 0.35 + 0.25, 4)
    if avg_dollar_volume_20d <= 250_000_000:
        return round(_scale(avg_dollar_volume_20d, 50_000_000, 250_000_000) * 0.25 + 0.60, 4)
    if avg_dollar_volume_20d <= 1_000_000_000:
        return round(_scale(avg_dollar_volume_20d, 250_000_000, 1_000_000_000) * 0.15 + 0.85, 4)
    return 1.0


def _risk_penalty_score(row: dict[str, Any], returns: dict[str, float]) -> float:
    penalty = 0.0
    vol = float(row.get("realized_vol_20d", 0.0))
    if vol > 0.60:
        penalty += 0.20
    elif vol > 0.40:
        penalty += 0.10

    r20 = returns.get("return_20d", 0.0)
    if r20 < -0.10:
        penalty += 0.10

    close = float(row["close"])
    high = float(row["high_252d"])
    if high > 0 and (close / high - 1.0) < -0.30:
        penalty += 0.10

    return round(_clamp(1.0 - penalty), 4)


def _track_record_score(outcome_prior: dict[str, Any] | None) -> float:
    if not outcome_prior:
        return 0.50
    hit = float(outcome_prior.get("hit_rate_20d", 0.5))
    median_ret = float(outcome_prior.get("median_net_return_20d", 0.0))
    normalized_ret = _scale(median_ret, -0.10, 0.10)
    score = 0.60 * hit + 0.40 * normalized_ret
    sample = int(outcome_prior.get("sample_size", 0))
    if sample < 3:
        score = min(score, 0.55)
    return round(score, 4)


def _quality_score(
    row: dict[str, Any],
    quality_by_ticker: dict[str, dict[str, Any]] | None,
    missing_context: list[str],
    evidence_refs: dict[str, Any],
) -> float:
    ticker = row.get("ticker", "")
    q = (quality_by_ticker or {}).get(ticker)
    if not q:
        missing_context.append("missing_fundamental_quality")
        return 0.50
    evidence_refs["p38_quality_source_hash"] = q.get("source_hash", "")
    base = float(q.get("overall_quality_score", 0.5))
    red_flags_raw = q.get("red_flags_json", "[]")
    if isinstance(red_flags_raw, str):
        try:
            red_flags = json.loads(red_flags_raw)
        except (json.JSONDecodeError, ValueError):
            red_flags = []
    else:
        red_flags = red_flags_raw
    severe_count = len(P39_SEVERE_P38_RED_FLAGS & set(red_flags))
    penalty = 0.10 * min(severe_count, 3)
    return round(_clamp(base - penalty), 4)


def _regime_score(
    row: dict[str, Any],
    regime_context: dict[str, Any] | None,
    missing_context: list[str],
    evidence_refs: dict[str, Any],
) -> float:
    sector = row.get("sector", "")
    if regime_context:
        evidence_refs["p37_regime_source_hash"] = regime_context.get("source_hash", "")
        regime_label = regime_context.get("regime_label", "neutral")
        confidence = float(regime_context.get("confidence", 0.5))
        sector_scores_raw = regime_context.get("sector_scores_json", "{}")
        if isinstance(sector_scores_raw, str):
            try:
                sector_scores = json.loads(sector_scores_raw)
            except (json.JSONDecodeError, ValueError):
                sector_scores = {}
        else:
            sector_scores = sector_scores_raw
        if sector in sector_scores:
            return round(float(sector_scores[sector]) * confidence, 4)
        # Derive from regime label — check explicit sector overrides first
        fallback = P39_REGIME_LABEL_FALLBACK.get(regime_label, P39_REGIME_LABEL_FALLBACK["neutral"])
        if sector in fallback:
            base = fallback[sector]
        elif sector in P39_CYCLICAL_SECTORS:
            base = fallback.get("cyclical", fallback.get("default", 0.50))
        elif sector in P39_DEFENSIVE_SECTORS:
            base = fallback.get("defensive", fallback.get("default", 0.50))
        else:
            base = fallback.get("default", 0.50)
        return round(base * confidence, 4)
    missing_context.append("missing_market_regime_context")
    return 0.50


def _candidate_category(
    row: dict[str, Any],
    total: float,
    component_scores: dict[str, float],
    returns: dict[str, float],
    outcome_prior: dict[str, Any] | None,
) -> str:
    quality = component_scores.get("quality_score", 0.0)
    momentum = component_scores.get("momentum_score", 0.0)
    regime = component_scores.get("regime_score", 0.0)
    liquidity = component_scores.get("liquidity_score", 0.0)
    r60 = returns.get("return_60d", 0.0)
    r120 = returns.get("return_120d", 0.0)

    if quality >= 0.65 and momentum >= 0.65:
        return "quality_momentum"
    if regime >= 0.75 and total >= 0.60:
        return "regime_aligned"
    if r60 > 0 and r120 < 0 and quality >= 0.55:
        return "recovery_watchlist"
    if liquidity >= 0.90 and total >= 0.55:
        return "liquidity_leader"
    if outcome_prior:
        sample = int(outcome_prior.get("sample_size", 0))
        hit = float(outcome_prior.get("hit_rate_20d", 0.0))
        if sample >= 3 and hit >= 0.60:
            return "outcome_retest"
    return "balanced_candidate"


def _workflow_action(total_score: float, risk_notes: list[str]) -> str:
    if total_score >= 0.70:
        return WORKFLOW_RESEARCH
    if total_score >= 0.50:
        return WORKFLOW_MONITOR
    return WORKFLOW_DEFER


# ── Source hash ──────────────────────────────────────────────────────────────

def compute_candidate_pool_source_hash(
    input_payload: dict[str, Any],
    as_of_date: str,
    regime_context: dict[str, Any] | None = None,
    quality_by_ticker: dict[str, dict[str, Any]] | None = None,
) -> str:
    """Deterministic SHA-256 over canonical JSON of universe and evidence refs."""
    canonical = {
        "schema_version": P39_SCHEMA_VERSION,
        "as_of_date": as_of_date,
        "universe_id": input_payload.get("universe_id", ""),
        "source": input_payload.get("source", ""),
        "tickers": sorted(
            input_payload.get("tickers", []),
            key=lambda r: str(r.get("ticker", "")) if isinstance(r, dict) else "",
        ),
        "regime_source_hash": (regime_context or {}).get("source_hash", ""),
        "quality_source_hashes": {
            ticker: report.get("source_hash", "")
            for ticker, report in sorted((quality_by_ticker or {}).items())
        },
    }
    return hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


# ── Pool builder ─────────────────────────────────────────────────────────────

def build_candidate_pool(
    input_payload: dict[str, Any],
    as_of_date: str | None = None,
    regime_context: dict[str, Any] | None = None,
    quality_by_ticker: dict[str, dict[str, Any]] | None = None,
    max_candidates: int = 20,
) -> dict[str, Any]:
    """Build a deterministic candidate pool from a point-in-time universe."""
    effective_as_of = as_of_date or input_payload.get("as_of_date", "")
    universe_id = input_payload.get("universe_id", "")
    source = input_payload.get("source", "")
    now = datetime.now(timezone.utc).isoformat()

    source_hash = compute_candidate_pool_source_hash(
        input_payload, effective_as_of, regime_context, quality_by_ticker
    )

    candidates: list[dict[str, Any]] = []
    excluded_items: list[dict[str, Any]] = []
    warnings: list[str] = []

    for raw_row in input_payload.get("tickers", []):
        # Non-dict rows
        if not isinstance(raw_row, dict):
            excluded_items.append({
                "ticker": str(raw_row),
                "sector": "",
                "candidate_status": CANDIDATE_STATUS_EXCLUDED_MISSING_REQUIRED_FIELDS,
                "exclusion_reasons": ["non_dict_ticker_item"],
                "missing_required_fields": [],
                "source_date": "",
                "created_at": now,
            })
            warnings.append("non_dict_ticker_item_excluded")
            continue

        ticker = raw_row.get("ticker", "")
        sector = raw_row.get("sector", "")
        source_date = raw_row.get("source_date", "")

        # Future source date
        if source_date and source_date > effective_as_of:
            excluded_items.append({
                "ticker": ticker,
                "sector": sector,
                "candidate_status": CANDIDATE_STATUS_EXCLUDED_FUTURE_SOURCE_DATE,
                "exclusion_reasons": ["future_source_date"],
                "missing_required_fields": [],
                "source_date": source_date,
                "created_at": now,
            })
            warnings.append("future_source_date_excluded")
            continue

        # Missing required fields
        missing = [f for f in P39_REQUIRED_TICKER_FIELDS if f not in raw_row or raw_row[f] is None]
        if missing:
            excluded_items.append({
                "ticker": ticker,
                "sector": sector,
                "candidate_status": CANDIDATE_STATUS_EXCLUDED_MISSING_REQUIRED_FIELDS,
                "exclusion_reasons": ["missing_required_fields"],
                "missing_required_fields": sorted(missing),
                "source_date": source_date,
                "created_at": now,
            })
            warnings.append("missing_required_fields_excluded")
            continue

        # Low price
        close = float(raw_row["close"])
        if close < 5.0:
            excluded_items.append({
                "ticker": ticker,
                "sector": sector,
                "candidate_status": CANDIDATE_STATUS_EXCLUDED_LOW_PRICE,
                "exclusion_reasons": ["close_below_minimum"],
                "missing_required_fields": [],
                "source_date": source_date,
                "created_at": now,
            })
            warnings.append("low_price_excluded")
            continue

        # Low liquidity
        vol = float(raw_row["avg_dollar_volume_20d"])
        if vol < 5_000_000:
            excluded_items.append({
                "ticker": ticker,
                "sector": sector,
                "candidate_status": CANDIDATE_STATUS_EXCLUDED_LOW_LIQUIDITY,
                "exclusion_reasons": ["avg_dollar_volume_below_minimum"],
                "missing_required_fields": [],
                "source_date": source_date,
                "created_at": now,
            })
            warnings.append("low_liquidity_excluded")
            continue

        # User-supplied exclude reasons
        user_excludes = raw_row.get("exclude_reasons")
        if user_excludes:
            excluded_items.append({
                "ticker": ticker,
                "sector": sector,
                "candidate_status": CANDIDATE_STATUS_EXCLUDED_USER_RULE,
                "exclusion_reasons": list(user_excludes) if isinstance(user_excludes, list) else [str(user_excludes)],
                "missing_required_fields": [],
                "source_date": source_date,
                "created_at": now,
            })
            warnings.append("user_rule_excluded")
            continue

        # Score
        missing_context: list[str] = []
        evidence_refs: dict[str, Any] = {}

        momentum, returns = _momentum_score(raw_row)
        liquidity = _liquidity_score(vol)
        risk = _risk_penalty_score(raw_row, returns)
        outcome_prior = raw_row.get("outcome_prior")
        track = _track_record_score(outcome_prior)
        quality = _quality_score(raw_row, quality_by_ticker, missing_context, evidence_refs)
        regime = _regime_score(raw_row, regime_context, missing_context, evidence_refs)

        component_scores = {
            "momentum_score": momentum,
            "quality_score": quality,
            "regime_score": regime,
            "liquidity_score": liquidity,
            "risk_penalty_score": risk,
            "track_record_score": track,
        }
        total = round(sum(
            P39_COMPONENT_WEIGHTS[k] * component_scores[k]
            for k in P39_COMPONENT_WEIGHTS
        ), 4)

        category = _candidate_category(raw_row, total, component_scores, returns, outcome_prior)
        risk_notes: list[str] = []
        if raw_row.get("realized_vol_20d", 0) > 0.40:
            risk_notes.append("elevated_volatility")
        if returns.get("return_20d", 0) < -0.10:
            risk_notes.append("sharp_recent_decline")

        inclusion_reasons: list[str] = []
        if component_scores["momentum_score"] >= 0.65:
            inclusion_reasons.append("strong_momentum")
        if component_scores["quality_score"] >= 0.65:
            inclusion_reasons.append("solid_quality")
        if component_scores["regime_score"] >= 0.60:
            inclusion_reasons.append("regime_supportive")
        if component_scores["liquidity_score"] >= 0.85:
            inclusion_reasons.append("high_liquidity")
        if not inclusion_reasons:
            inclusion_reasons.append("balanced_candidate")

        candidates.append({
            "schema_version": P39_SCHEMA_VERSION,
            "run_id": "",
            "as_of_date": effective_as_of,
            "universe_id": universe_id,
            "ticker": ticker,
            "sector": sector,
            "currency": raw_row.get("currency", ""),
            "source_date": source_date,
            "candidate_status": CANDIDATE_STATUS_INCLUDED,
            "candidate_category": category,
            "workflow_action": _workflow_action(total, risk_notes),
            "total_score": total,
            "component_scores": component_scores,
            "feature_snapshot": returns,
            "evidence_refs": evidence_refs,
            "inclusion_reasons": inclusion_reasons,
            "risk_notes": risk_notes,
            "missing_context": sorted(missing_context),
            "source_hash": source_hash,
            "created_at": now,
        })

    # Sort: total DESC, momentum DESC, quality DESC, ticker ASC
    candidates.sort(key=lambda c: (
        -c["total_score"],
        -c["component_scores"]["momentum_score"],
        -c["component_scores"]["quality_score"],
        c["ticker"],
    ))
    candidates = candidates[:max_candidates]

    # Assign run_id
    for c in candidates:
        c["run_id"] = hashlib.sha256(
            f"{effective_as_of}|{universe_id}|{source_hash}".encode("utf-8")
        ).hexdigest()[:16]

    # Status
    if not candidates and not excluded_items:
        status = P39_STATUS_BLOCKED_INVALID_INPUT
    elif not candidates:
        status = P39_STATUS_NO_CANDIDATES
    elif warnings:
        status = P39_STATUS_COMPLETED_WITH_WARNINGS
    else:
        status = P39_STATUS_COMPLETED

    return {
        "schema_version": P39_SCHEMA_VERSION,
        "run_id": candidates[0]["run_id"] if candidates else hashlib.sha256(
            f"{effective_as_of}|{universe_id}|{source_hash}".encode("utf-8")
        ).hexdigest()[:16],
        "as_of_date": effective_as_of,
        "created_at": now,
        "universe_id": universe_id,
        "source": source,
        "source_hash": source_hash,
        "status": status,
        "candidates": candidates,
        "excluded_items": excluded_items,
        "summary": {
            "candidate_count": len(candidates),
            "excluded_count": len(excluded_items),
            "top_candidate": candidates[0]["ticker"] if candidates else "",
        },
        "warnings": warnings,
        "disclaimer": P39_ARTIFACT_DISCLAIMER,
    }


# ── Artifact writer ──────────────────────────────────────────────────────────

def write_candidate_pool_artifacts(
    pool: dict[str, Any],
    output_dir: Path,
) -> dict[str, Path]:
    """Write JSON and Markdown artifacts for a candidate pool."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "p39_candidate_pool.json"
    md_path = output_dir / "p39_candidate_pool.md"

    json_path.write_text(json.dumps(pool, indent=2, default=str), encoding="utf-8")

    candidates = pool.get("candidates", [])
    excluded = pool.get("excluded_items", [])
    lines = [
        f"# Candidate Pool — {pool.get('as_of_date', '')}",
        "",
        f"- Status: {pool.get('status', '')}",
        f"- Universe: {pool.get('universe_id', '')}",
        f"- Candidates: {len(candidates)}",
        f"- Excluded: {len(excluded)}",
        "",
    ]

    if candidates:
        lines.extend([
            "## Top Candidates",
            "",
            "| Rank | Ticker | Category | Workflow | Score | Reasons |",
            "|------|--------|----------|----------|-------|---------|",
        ])
        for i, c in enumerate(candidates, start=1):
            reasons = ", ".join(c.get("inclusion_reasons", [])[:3])
            lines.append(
                f"| {i} | {c['ticker']} | {c['candidate_category']} | "
                f"{c['workflow_action']} | {c['total_score']:.2f} | {reasons} |"
            )
        lines.append("")

    # Category counts
    category_counts: dict[str, int] = {}
    for c in candidates:
        cat = c.get("candidate_category", "unknown")
        category_counts[cat] = category_counts.get(cat, 0) + 1
    if category_counts:
        lines.extend(["## Category Counts", ""])
        for cat, count in sorted(category_counts.items()):
            lines.append(f"- {cat}: {count}")
        lines.append("")

    # Missing context
    missing_ctx = sorted({
        item for c in candidates for item in c.get("missing_context", [])
    })
    if missing_ctx:
        lines.extend(["## Missing Context", ""])
        for item in missing_ctx:
            lines.append(f"- {item}")
        lines.append("")

    # Excluded items
    if excluded:
        lines.extend(["## Excluded Items", ""])
        for item in excluded[:20]:
            reasons = ", ".join(item.get("exclusion_reasons", []))
            lines.append(f"- {item.get('ticker', '')}: {item.get('candidate_status', '')} ({reasons})")
        lines.append("")

    lines.extend(["---", "", f"> {pool.get('disclaimer', P39_ARTIFACT_DISCLAIMER)}", ""])

    markdown = "\n".join(lines)
    lowered = markdown.lower()
    for forbidden in P39_FORBIDDEN_TERMS:
        if forbidden in lowered:
            raise ValueError(f"forbidden candidate-pool term rendered: {forbidden}")
    md_path.write_text(markdown, encoding="utf-8")
    return {"json": json_path, "md": md_path}


# ── Run orchestration ────────────────────────────────────────────────────────

def run_candidate_pool(
    db: Any,
    input_payload: dict[str, Any],
    as_of_date: str | None = None,
    output_root: Path | None = None,
    max_candidates: int = 20,
) -> dict[str, Any]:
    """Run candidate pool: validate, score, persist, write artifacts."""
    effective_as_of = as_of_date or input_payload.get("as_of_date", "")
    if not effective_as_of:
        return {
            "status": P39_STATUS_BLOCKED_INVALID_INPUT,
            "run_id": "",
            "output_dir": "",
            "candidate_count": 0,
            "excluded_count": 0,
            "top_candidate": "",
            "warning_count": 0,
            "warnings": ["missing as_of_date"],
        }

    db.initialize_candidate_pool_schema()

    # Read-only P37 regime context (table may not exist yet)
    # Use latest snapshot at or before as_of_date
    regime_context = None
    if hasattr(db, "list_market_regime_snapshots_as_of"):
        try:
            regimes = db.list_market_regime_snapshots_as_of(as_of_date=effective_as_of, limit=1)
            if regimes:
                raw_regime = regimes[0]
                regime_context = {
                    "regime_label": raw_regime.get("regime_label", "neutral"),
                    "confidence": raw_regime.get("confidence", 0.5),
                    "sector_scores_json": raw_regime.get("sector_rotation_json", "{}"),
                    "source_hash": raw_regime.get("data_source_hash", ""),
                }
        except Exception:
            pass

    # Read-only P38 quality reports (table may not exist yet)
    # Use latest report at or before as_of_date
    quality_by_ticker: dict[str, dict[str, Any]] = {}
    if hasattr(db, "list_fundamental_quality_reports_as_of"):
        try:
            for row in input_payload.get("tickers", []):
                if isinstance(row, dict) and row.get("ticker"):
                    reports = db.list_fundamental_quality_reports_as_of(
                        ticker=row["ticker"], as_of_date=effective_as_of, limit=1
                    )
                    if reports:
                        quality_by_ticker[row["ticker"]] = reports[0]
        except Exception:
            pass

    pool = build_candidate_pool(
        input_payload,
        effective_as_of,
        regime_context=regime_context,
        quality_by_ticker=quality_by_ticker,
        max_candidates=max_candidates,
    )

    run_id = db.save_candidate_pool(pool)

    if output_root is None:
        output_root = Path("output/governance")
    output_dir = Path(output_root) / effective_as_of
    paths = write_candidate_pool_artifacts(pool, output_dir)

    return {
        "status": pool["status"],
        "run_id": run_id,
        "output_dir": str(output_dir),
        "candidate_count": len(pool.get("candidates", [])),
        "excluded_count": len(pool.get("excluded_items", [])),
        "top_candidate": pool["candidates"][0]["ticker"] if pool.get("candidates") else "",
        "warning_count": len(pool.get("warnings", [])),
        "paths": paths,
    }
