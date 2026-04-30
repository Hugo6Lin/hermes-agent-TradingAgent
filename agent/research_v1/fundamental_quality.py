"""P38 Fundamental Quality Engine — standalone fundamental-quality evidence only.

This module computes deterministic fundamental-quality scores from point-in-time
financial rows. It does not approve production adoption, change recommendations,
instruct trades, place orders, train models, schedule jobs, or mutate
production configuration.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── Schema & status constants ────────────────────────────────────────────────

P38_SCHEMA_VERSION = "p38_fundamental_quality.1"

P38_STATUS_COMPLETED = "completed"
P38_STATUS_COMPLETED_WITH_WARNINGS = "completed_with_warnings"
P38_STATUS_DEGRADED_INSUFFICIENT_HISTORY = "degraded_insufficient_history"
P38_STATUS_BLOCKED_MISSING_FUNDAMENTALS = "blocked_missing_fundamentals"

QUALITY_COMPOUNDER = "compounder_quality"
QUALITY_SOLID = "solid_quality"
QUALITY_WATCHLIST = "watchlist_quality"
QUALITY_LOW = "low_quality"
QUALITY_BLOCKED = "blocked_missing_fundamentals"

P38_ARTIFACT_DISCLAIMER = (
    "P38 is fundamental-quality evidence only. It does not approve production "
    "adoption, change recommendations, instruct trades, place orders, train "
    "models, schedule jobs, or mutate production configuration."
)

P38_REQUIRED_ROW_FIELDS = (
    "period_end",
    "source_date",
    "revenue",
    "gross_profit",
    "operating_income",
    "net_income",
    "cfo",
    "capex",
    "total_debt",
    "cash_and_equivalents",
    "shareholders_equity",
    "shares_outstanding",
)

P38_DIMENSION_WEIGHTS = {
    "profitability_score": 0.25,
    "growth_quality_score": 0.20,
    "cash_conversion_score": 0.20,
    "balance_sheet_score": 0.15,
    "dilution_score": 0.10,
    "stability_score": 0.10,
}

# ── Red flags ────────────────────────────────────────────────────────────────

SEVERE_RED_FLAGS = frozenset({
    "negative_revenue",
    "negative_equity",
    "negative_fcf",
    "fcf_conversion_below_zero",
    "debt_to_equity_high",
    "net_debt_to_fcf_high",
})


# ── Normalization ────────────────────────────────────────────────────────────

@dataclass
class NormalizedFinancialRows:
    usable_rows: list[dict[str, Any]] = field(default_factory=list)
    ignored_future_rows: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    missing_required_fields: list[str] = field(default_factory=list)


def _safe_ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def _compute_row_metrics(row: dict[str, Any]) -> dict[str, Any]:
    """Add derived metrics to a financial row."""
    enriched = dict(row)

    revenue = row.get("revenue")
    gross_profit = row.get("gross_profit")
    operating_income = row.get("operating_income")
    net_income = row.get("net_income")
    cfo = row.get("cfo")
    capex = row.get("capex")
    total_debt = row.get("total_debt")
    cash = row.get("cash_and_equivalents")
    equity = row.get("shareholders_equity")
    shares = row.get("shares_outstanding")
    ebit = row.get("ebit")
    current_assets = row.get("current_assets")
    current_liabilities = row.get("current_liabilities")

    # Free cash flow
    if "free_cash_flow" in row and row["free_cash_flow"] is not None:
        enriched["free_cash_flow"] = row["free_cash_flow"]
    elif cfo is not None and capex is not None:
        enriched["free_cash_flow"] = cfo + capex
    else:
        enriched["free_cash_flow"] = None

    # Margins
    enriched["gross_margin"] = _safe_ratio(gross_profit, revenue)
    enriched["operating_margin"] = _safe_ratio(operating_income, revenue)
    enriched["net_margin"] = _safe_ratio(net_income, revenue)
    enriched["fcf_margin"] = _safe_ratio(enriched.get("free_cash_flow"), revenue)

    # Returns
    enriched["roe"] = _safe_ratio(net_income, equity)
    invested_capital = None
    if total_debt is not None and equity is not None and cash is not None:
        invested_capital = total_debt + equity - cash
    enriched["roic"] = _safe_ratio(ebit or operating_income, invested_capital)

    # FCF conversion
    enriched["fcf_conversion"] = _safe_ratio(enriched.get("free_cash_flow"), net_income)

    # Leverage
    enriched["debt_to_equity"] = _safe_ratio(total_debt, equity)
    enriched["net_debt_to_fcf"] = _safe_ratio(
        (total_debt - cash) if total_debt is not None and cash is not None else None,
        enriched.get("free_cash_flow"),
    )

    # Liquidity
    enriched["current_ratio"] = _safe_ratio(current_assets, current_liabilities)

    return enriched


def normalize_financial_rows(
    rows: list[dict[str, Any]],
    as_of_date: str,
) -> NormalizedFinancialRows:
    """Normalize and filter financial rows by source-date integrity."""
    result = NormalizedFinancialRows()
    warnings: list[str] = []

    for row in rows:
        source_date = row.get("source_date")
        if source_date and source_date > as_of_date:
            result.ignored_future_rows.append(row)
            warnings.append("future_source_date_ignored")
            continue

        # Check required fields
        missing = [f for f in P38_REQUIRED_ROW_FIELDS if f not in row or row[f] is None]
        if missing:
            result.missing_required_fields.extend(missing)
            continue

        # Capex sign check
        capex = row.get("capex")
        if capex is not None and capex > 0:
            warnings.append("capex_sign_check")

        result.usable_rows.append(_compute_row_metrics(row))

    result.usable_rows.sort(key=lambda r: r["period_end"])
    result.warnings = list(set(warnings))
    return result


# ── Trend metrics ────────────────────────────────────────────────────────────

def _yoy_growth(current: float | None, prior: float | None) -> float | None:
    if current is None or prior is None or prior == 0:
        return None
    return (current - prior) / abs(prior)


def _compute_trend_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute YoY growth metrics from sorted usable rows."""
    if len(rows) < 2:
        return {
            "revenue_growth_yoy": None,
            "eps_growth_yoy": None,
            "fcf_growth_yoy": None,
            "share_count_growth_yoy": None,
            "margin_stability": None,
            "fcf_stability": None,
        }

    latest = rows[-1]
    prior = rows[-2]

    revenue_growth = _yoy_growth(latest.get("revenue"), prior.get("revenue"))
    eps_growth = _yoy_growth(latest.get("eps"), prior.get("eps"))
    fcf_growth = _yoy_growth(latest.get("free_cash_flow"), prior.get("free_cash_flow"))
    share_count_growth = _yoy_growth(latest.get("shares_outstanding"), prior.get("shares_outstanding"))

    # Stability: coefficient of variation of margins across all rows
    def _cv(values: list[float | None]) -> float | None:
        valid = [v for v in values if v is not None]
        if len(valid) < 2:
            return None
        mean = sum(valid) / len(valid)
        if mean == 0:
            return None
        variance = sum((v - mean) ** 2 for v in valid) / len(valid)
        return (variance ** 0.5) / abs(mean)

    margin_stability = _cv([r.get("operating_margin") for r in rows])
    fcf_stability = _cv([r.get("fcf_margin") for r in rows])

    return {
        "revenue_growth_yoy": revenue_growth,
        "eps_growth_yoy": eps_growth,
        "fcf_growth_yoy": fcf_growth,
        "share_count_growth_yoy": share_count_growth,
        "margin_stability": margin_stability,
        "fcf_stability": fcf_stability,
    }


# ── Dimension scoring ────────────────────────────────────────────────────────

def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _score_profitability(rows: list[dict[str, Any]]) -> float:
    """Weighted ROIC, operating margin, gross margin."""
    latest = rows[-1]
    roic = latest.get("roic") or 0.0
    op_margin = latest.get("operating_margin") or 0.0
    gross_margin = latest.get("gross_margin") or 0.0

    # Normalize: 20%+ ROIC → 1.0, 0% → 0.0
    roic_score = _clamp(roic / 0.20)
    # Normalize: 15%+ operating margin → 1.0
    op_score = _clamp(op_margin / 0.15)
    # Normalize: 40%+ gross margin → 1.0
    gross_score = _clamp(gross_margin / 0.40)

    return 0.40 * roic_score + 0.35 * op_score + 0.25 * gross_score


def _score_growth_quality(trend: dict[str, Any]) -> float:
    """Weighted revenue growth, EPS growth, FCF growth."""
    rev = trend.get("revenue_growth_yoy")
    eps = trend.get("eps_growth_yoy")
    fcf = trend.get("fcf_growth_yoy")

    def _growth_score(g: float | None) -> float:
        if g is None:
            return 0.5  # neutral when unknown
        # 20%+ growth → 1.0, -20% → 0.0
        return _clamp((g + 0.20) / 0.40)

    return 0.40 * _growth_score(rev) + 0.35 * _growth_score(eps) + 0.25 * _growth_score(fcf)


def _score_cash_conversion(rows: list[dict[str, Any]]) -> float:
    """Weighted FCF margin and FCF conversion."""
    latest = rows[-1]
    fcf_margin = latest.get("fcf_margin")
    fcf_conv = latest.get("fcf_conversion")

    margin_score = _clamp((fcf_margin or 0) / 0.10) if fcf_margin is not None else 0.5
    # Conversion > 1.0 is good (FCF > net income)
    conv_score = _clamp(fcf_conv / 1.0) if fcf_conv is not None else 0.5

    return 0.50 * margin_score + 0.50 * conv_score


def _score_balance_sheet(rows: list[dict[str, Any]]) -> float:
    """Penalize high debt/equity, high net debt/FCF, weak current ratio."""
    latest = rows[-1]
    de = latest.get("debt_to_equity")
    nd_fcf = latest.get("net_debt_to_fcf")
    cr = latest.get("current_ratio")

    # Debt/equity: 0 → 1.0, 2.0+ → 0.0
    de_score = _clamp(1.0 - (de or 0) / 2.0) if de is not None else 0.5

    # Net debt/FCF: 0 → 1.0, 5+ → 0.0
    nd_score = _clamp(1.0 - (nd_fcf or 0) / 5.0) if nd_fcf is not None else 0.5

    # Current ratio: 2.0+ → 1.0, 0.5 → 0.0
    cr_score = _clamp(((cr or 1.0) - 0.5) / 1.5) if cr is not None else 0.5

    return 0.40 * de_score + 0.35 * nd_score + 0.25 * cr_score


def _score_dilution(trend: dict[str, Any]) -> float:
    """Penalize positive share count growth; reward stable or declining shares."""
    g = trend.get("share_count_growth_yoy")
    if g is None:
        return 0.5
    # -5% or less → 1.0, +10% → 0.0
    return _clamp(1.0 - (g + 0.05) / 0.15)


def _score_stability(trend: dict[str, Any]) -> float:
    """Penalize high margin volatility and FCF volatility."""
    ms = trend.get("margin_stability")
    fs = trend.get("fcf_stability")

    # Lower CV is better. CV of 0 → 1.0, CV of 1.0+ → 0.0
    ms_score = _clamp(1.0 - (ms or 0)) if ms is not None else 0.5
    fs_score = _clamp(1.0 - (fs or 0)) if fs is not None else 0.5

    return 0.50 * ms_score + 0.50 * fs_score


def _compute_dimension_scores(
    rows: list[dict[str, Any]],
    trend: dict[str, Any],
) -> dict[str, float]:
    return {
        "profitability_score": round(_score_profitability(rows), 4),
        "growth_quality_score": round(_score_growth_quality(trend), 4),
        "cash_conversion_score": round(_score_cash_conversion(rows), 4),
        "balance_sheet_score": round(_score_balance_sheet(rows), 4),
        "dilution_score": round(_score_dilution(trend), 4),
        "stability_score": round(_score_stability(trend), 4),
    }


def _overall_score(dimension_scores: dict[str, float]) -> float:
    total = 0.0
    for dim, weight in P38_DIMENSION_WEIGHTS.items():
        total += weight * dimension_scores.get(dim, 0.0)
    return round(total, 4)


# ── Red flags ────────────────────────────────────────────────────────────────

def _detect_red_flags(
    rows: list[dict[str, Any]],
    trend: dict[str, Any],
    normalized: NormalizedFinancialRows,
) -> list[str]:
    flags: list[str] = []
    latest = rows[-1] if rows else {}

    if latest.get("revenue") is not None and latest["revenue"] < 0:
        flags.append("negative_revenue")
    if latest.get("shareholders_equity") is not None and latest["shareholders_equity"] < 0:
        flags.append("negative_equity")
    if latest.get("free_cash_flow") is not None and latest["free_cash_flow"] < 0:
        flags.append("negative_fcf")
    if latest.get("fcf_conversion") is not None and latest["fcf_conversion"] < 0:
        flags.append("fcf_conversion_below_zero")
    if latest.get("debt_to_equity") is not None and latest["debt_to_equity"] > 2.0:
        flags.append("debt_to_equity_high")
    if latest.get("net_debt_to_fcf") is not None and latest["net_debt_to_fcf"] > 5.0:
        flags.append("net_debt_to_fcf_high")

    share_growth = trend.get("share_count_growth_yoy")
    if share_growth is not None and share_growth > 0.05:
        flags.append("share_dilution_high")

    # Margin compression: latest operating margin < prior
    if len(rows) >= 2:
        latest_margin = rows[-1].get("operating_margin")
        prior_margin = rows[-2].get("operating_margin")
        if latest_margin is not None and prior_margin is not None and latest_margin < prior_margin * 0.90:
            flags.append("margin_compression")

    if normalized.warnings:
        for w in normalized.warnings:
            if w == "future_source_date_ignored":
                flags.append("source_date_after_as_of_ignored")
            elif w == "capex_sign_check":
                flags.append("capex_sign_check")

    if len(rows) < 4:
        flags.append("insufficient_history")

    if normalized.missing_required_fields:
        flags.append("missing_required_fields")

    return list(dict.fromkeys(flags))  # deduplicate preserving order


# ── Label and confidence ─────────────────────────────────────────────────────

def _assign_quality_label(
    overall: float,
    status: str,
    red_flags: list[str],
) -> str:
    if status == P38_STATUS_BLOCKED_MISSING_FUNDAMENTALS:
        return QUALITY_BLOCKED

    severe = bool(SEVERE_RED_FLAGS & set(red_flags))

    if overall >= 0.80 and not severe:
        return QUALITY_COMPOUNDER
    if overall >= 0.65 and not severe:
        return QUALITY_SOLID
    if overall >= 0.45 or status == P38_STATUS_DEGRADED_INSUFFICIENT_HISTORY:
        return QUALITY_WATCHLIST
    return QUALITY_LOW


def _compute_confidence(
    usable_row_count: int,
    red_flags: list[str],
) -> float:
    confidence = 1.0
    if usable_row_count < 4:
        confidence -= 0.15
    severe_count = len(SEVERE_RED_FLAGS & set(red_flags))
    confidence -= 0.10 * min(severe_count, 3)
    return round(max(0.0, min(1.0, confidence)), 4)


# ── Source hash ──────────────────────────────────────────────────────────────

def compute_source_hash(ticker_payload: dict, as_of_date: str) -> str:
    """Deterministic SHA-256 over all financial rows and metadata."""
    canonical = {
        "as_of_date": as_of_date,
        "ticker": ticker_payload.get("ticker", ""),
        "sector": ticker_payload.get("sector", ""),
        "currency": ticker_payload.get("currency", ""),
        "rows": [],
    }
    for row in ticker_payload.get("rows", []):
        canonical["rows"].append({
            k: row.get(k)
            for k in sorted(row.keys())
        })
    canonical["rows"].sort(key=lambda r: (r.get("period_end", ""), r.get("source_date", "")))
    return hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


# ── Report builder ───────────────────────────────────────────────────────────

def build_fundamental_quality_report(
    ticker_payload: dict,
    as_of_date: str,
) -> dict[str, Any]:
    """Build a deterministic fundamental-quality report for one ticker."""
    ticker = ticker_payload.get("ticker", "")
    sector = ticker_payload.get("sector", "")
    currency = ticker_payload.get("currency", "")
    rows = ticker_payload.get("rows", [])

    now = datetime.now(timezone.utc).isoformat()
    source_hash = compute_source_hash(ticker_payload, as_of_date)

    normalized = normalize_financial_rows(rows, as_of_date)
    usable = normalized.usable_rows
    usable_count = len(usable)

    # Status
    if usable_count < 2:
        status = P38_STATUS_BLOCKED_MISSING_FUNDAMENTALS
    elif usable_count < 4:
        status = P38_STATUS_DEGRADED_INSUFFICIENT_HISTORY
    elif normalized.warnings:
        status = P38_STATUS_COMPLETED_WITH_WARNINGS
    else:
        status = P38_STATUS_COMPLETED

    # Latest metrics
    latest_metrics: dict[str, Any] = {}
    if usable:
        latest = usable[-1]
        latest_metrics = {
            "period_end": latest.get("period_end"),
            "revenue": latest.get("revenue"),
            "gross_margin": latest.get("gross_margin"),
            "operating_margin": latest.get("operating_margin"),
            "net_margin": latest.get("net_margin"),
            "roe": latest.get("roe"),
            "roic": latest.get("roic"),
            "fcf_margin": latest.get("fcf_margin"),
            "fcf_conversion": latest.get("fcf_conversion"),
            "debt_to_equity": latest.get("debt_to_equity"),
            "net_debt_to_fcf": latest.get("net_debt_to_fcf"),
            "current_ratio": latest.get("current_ratio"),
            "free_cash_flow": latest.get("free_cash_flow"),
            "shares_outstanding": latest.get("shares_outstanding"),
        }

    # Trend metrics
    trend_metrics = _compute_trend_metrics(usable)

    # Dimension scores
    dimension_scores = _compute_dimension_scores(usable, trend_metrics) if usable else {
        k: 0.0 for k in P38_DIMENSION_WEIGHTS
    }

    # Overall score
    overall = _overall_score(dimension_scores) if usable else 0.0

    # Red flags
    red_flags = _detect_red_flags(usable, trend_metrics, normalized)

    # Label
    quality_label = _assign_quality_label(overall, status, red_flags)

    # Confidence
    confidence = _compute_confidence(usable_count, red_flags)

    # Coverage ratio
    total_rows = len(rows)
    coverage_ratio = round(usable_count / total_rows, 4) if total_rows > 0 else 0.0

    # Summary
    summary_parts = [f"{ticker}: {quality_label} (score={overall:.2f}, conf={confidence:.2f})"]
    if red_flags:
        summary_parts.append(f"flags={','.join(red_flags[:3])}")

    return {
        "schema_version": P38_SCHEMA_VERSION,
        "as_of_date": as_of_date,
        "created_at": now,
        "ticker": ticker,
        "sector": sector,
        "currency": currency,
        "status": status,
        "quality_label": quality_label,
        "overall_quality_score": overall,
        "confidence": confidence,
        "coverage_ratio": coverage_ratio,
        "usable_row_count": usable_count,
        "ignored_future_row_count": len(normalized.ignored_future_rows),
        "dimension_scores": dimension_scores,
        "latest_metrics": latest_metrics,
        "trend_metrics": trend_metrics,
        "red_flags": red_flags,
        "warnings": normalized.warnings,
        "source_hash": source_hash,
        "summary": " | ".join(summary_parts),
    }


# ── Artifact writer ──────────────────────────────────────────────────────────

def write_fundamental_quality_artifacts(
    payload: dict[str, Any],
    output_dir: Path,
) -> dict[str, Path]:
    """Write JSON and Markdown artifacts for fundamental-quality reports."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "p38_fundamental_quality.json"
    md_path = output_dir / "p38_fundamental_quality.md"

    # JSON
    json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    # Markdown
    lines: list[str] = []
    lines.append(f"# Fundamental Quality Report — {payload.get('as_of_date', '')}")
    lines.append("")

    # Summary table
    reports = payload.get("reports", [])
    if reports:
        lines.append("## Ticker Summary")
        lines.append("")
        lines.append("| Ticker | Label | Score | Confidence | Coverage |")
        lines.append("|--------|-------|-------|------------|----------|")
        for r in reports:
            lines.append(
                f"| {r['ticker']} | {r['quality_label']} | "
                f"{r['overall_quality_score']:.2f} | "
                f"{r['confidence']:.2f} | "
                f"{r['coverage_ratio']:.0%} |"
            )
        lines.append("")

    # Red flags
    all_flags: list[str] = []
    for r in reports:
        for flag in r.get("red_flags", []):
            all_flags.append(f"{r['ticker']}: {flag}")
    if all_flags:
        lines.append("## Red Flags")
        lines.append("")
        for flag in all_flags:
            lines.append(f"- {flag}")
        lines.append("")

    # Dimension scores
    if reports:
        lines.append("## Dimension Scores")
        lines.append("")
        dims = list(P38_DIMENSION_WEIGHTS.keys())
        header = "| Ticker | " + " | ".join(d.replace("_score", "") for d in dims) + " |"
        sep = "|--------|" + "|".join("-------" for _ in dims) + "|"
        lines.append(header)
        lines.append(sep)
        for r in reports:
            ds = r.get("dimension_scores", {})
            vals = " | ".join(f"{ds.get(d, 0):.2f}" for d in dims)
            lines.append(f"| {r['ticker']} | {vals} |")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(f"> {payload.get('disclaimer', P38_ARTIFACT_DISCLAIMER)}")
    lines.append("")

    md_path.write_text("\n".join(lines), encoding="utf-8")

    return {"json": json_path, "md": md_path}


# ── Run orchestration ────────────────────────────────────────────────────────

def run_fundamental_quality(
    db: Any,
    input_payload: dict[str, Any],
    as_of_date: str | None = None,
    output_root: Path | None = None,
) -> dict[str, Any]:
    """Run fundamental-quality scoring: validate, score, persist, write artifacts."""
    effective_as_of = as_of_date or input_payload.get("as_of_date", "")
    if not effective_as_of:
        return {
            "status": "blocked_invalid_input",
            "report_count": 0,
            "blocked_count": 0,
            "warning_count": 0,
            "output_dir": "",
            "warnings": ["missing as_of_date"],
        }

    db.initialize_fundamental_quality_schema()

    tickers = input_payload.get("tickers", [])
    reports: list[dict[str, Any]] = []
    all_warnings: list[str] = []
    blocked_count = 0
    written_count = 0
    skipped_count = 0

    for ticker_payload in tickers:
        report = build_fundamental_quality_report(ticker_payload, effective_as_of)
        reports.append(report)

        if report["status"] == P38_STATUS_BLOCKED_MISSING_FUNDAMENTALS:
            blocked_count += 1

        report_id = db.save_fundamental_quality_report(report)
        written_count += 1

        all_warnings.extend(report.get("warnings", []))
        all_warnings.extend(report.get("red_flags", []))

    # Determine overall status
    if blocked_count == len(reports) and blocked_count > 0:
        overall_status = P38_STATUS_BLOCKED_MISSING_FUNDAMENTALS
    elif all_warnings:
        overall_status = P38_STATUS_COMPLETED_WITH_WARNINGS
    else:
        overall_status = P38_STATUS_COMPLETED

    payload = {
        "schema_version": P38_SCHEMA_VERSION,
        "as_of_date": effective_as_of,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": overall_status,
        "reports": reports,
        "summary": {
            "report_count": len(reports),
            "blocked_count": blocked_count,
        },
        "warnings": all_warnings,
        "disclaimer": P38_ARTIFACT_DISCLAIMER,
    }

    # Write artifacts
    if output_root is None:
        output_root = Path("output/governance")
    output_dir = Path(output_root) / effective_as_of
    paths = write_fundamental_quality_artifacts(payload, output_dir)

    return {
        "status": overall_status,
        "output_dir": str(output_dir),
        "report_count": len(reports),
        "blocked_count": blocked_count,
        "warning_count": len(all_warnings),
        "reports": reports,
        "paths": paths,
    }
