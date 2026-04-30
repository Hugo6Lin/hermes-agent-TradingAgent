"""P37 Market Regime Context — standalone market-context evidence only.

This module computes deterministic market-regime snapshots from market proxy
histories. It does not approve production adoption, change recommendations,
instruct trades, place orders, train models, schedule jobs, or mutate
production configuration.
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# ── Schema & status constants ────────────────────────────────────────────────

P37_SCHEMA_VERSION = "p37_market_regime_snapshot.1"

P37_STATUS_COMPLETED = "completed"
P37_STATUS_COMPLETED_WITH_WARNINGS = "completed_with_warnings"
P37_STATUS_DEGRADED_MISSING_INPUTS = "degraded_missing_inputs"

# ── Regime labels ────────────────────────────────────────────────────────────

REGIME_RISK_ON_BROAD = "risk_on_broad"
REGIME_RISK_ON_NARROW = "risk_on_narrow"
REGIME_RISK_OFF = "risk_off"
REGIME_HIGH_VOLATILITY = "high_volatility"
REGIME_RANGE_BOUND = "range_bound"
REGIME_DEGRADED_UNKNOWN = "degraded_unknown"

# ── Defaults ─────────────────────────────────────────────────────────────────

P37_DEFAULT_LOOKBACK_DAYS = 90

P37_ARTIFACT_DISCLAIMER = (
    "P37 is market-context evidence only. It does not approve production "
    "adoption, change recommendations, instruct trades, place orders, train "
    "models, schedule jobs, or mutate production configuration."
)

DEFAULT_MARKET_PROXIES: dict[str, str] = {
    "SPY": "us_equity_large_cap",
    "QQQ": "us_growth",
    "IWM": "us_small_cap",
    "VIX": "volatility_proxy",
    "TLT": "duration_rates_proxy",
    "HYG": "high_yield_credit_proxy",
    "LQD": "investment_grade_credit_proxy",
    "UUP": "dollar_proxy",
    "XLK": "technology",
    "XLF": "financials",
    "XLY": "consumer_discretionary",
    "XLP": "consumer_staples",
    "XLE": "energy",
    "XLV": "healthcare",
    "XLI": "industrials",
    "XLU": "utilities",
    "XLB": "materials",
    "XLC": "communication_services",
    "XLRE": "real_estate",
}

SECTOR_PROXY_SYMBOLS: frozenset[str] = frozenset({
    "XLK", "XLF", "XLY", "XLP", "XLE", "XLV", "XLI", "XLU", "XLB", "XLC", "XLRE",
})


# ── History normalization ────────────────────────────────────────────────────

def normalize_history_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize raw provider rows to a canonical form sorted by date."""
    normalized: list[dict[str, Any]] = []
    for row in rows:
        if row.get("close") is None or not row.get("date"):
            continue
        normalized.append({
            "date": str(row["date"]),
            "open": row.get("open"),
            "high": row.get("high"),
            "low": row.get("low"),
            "close": float(row["close"]),
            "volume": row.get("volume"),
            "price_adjustment": row.get("price_adjustment", "unknown"),
        })
    normalized.sort(key=lambda r: r["date"])
    return normalized


# ── Metric helpers ───────────────────────────────────────────────────────────

def _return_n(rows: list[dict[str, Any]], n: int) -> float | None:
    """Compute n-day return from the last n+1 closing prices."""
    if len(rows) < n + 1:
        return None
    old_close = rows[-(n + 1)]["close"]
    new_close = rows[-1]["close"]
    if old_close == 0:
        return None
    return (new_close - old_close) / old_close


def _realized_vol_20d(rows: list[dict[str, Any]]) -> float | None:
    """Annualized realized volatility from 20d of daily percentage returns."""
    if len(rows) < 21:
        return None
    recent = rows[-21:]
    daily_returns: list[float] = []
    for i in range(1, len(recent)):
        prev = recent[i - 1]["close"]
        if prev == 0:
            return None
        daily_returns.append((recent[i]["close"] - prev) / prev)
    if len(daily_returns) < 2:
        return None
    return statistics.stdev(daily_returns) * math.sqrt(252)


def _drawdown_n(rows: list[dict[str, Any]], n: int) -> float | None:
    """Max drawdown over the last n rows."""
    window = rows[-n:]
    if len(window) < 2:
        return None
    peak = window[0]["close"]
    max_dd = 0.0
    for row in window:
        c = row["close"]
        if c > peak:
            peak = c
        dd = (c - peak) / peak if peak != 0 else 0.0
        if dd < max_dd:
            max_dd = dd
    return max_dd


def _above_sma(rows: list[dict[str, Any]], n: int) -> bool | None:
    """True if the latest close is above the n-day SMA."""
    if len(rows) < n:
        return None
    closes = [r["close"] for r in rows[-n:]]
    sma = sum(closes) / n
    return rows[-1]["close"] > sma


# ── Proxy metrics ────────────────────────────────────────────────────────────

def compute_proxy_metrics(
    symbol: str,
    label: str,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compute deterministic metrics for a single proxy."""
    return {
        "symbol": symbol,
        "label": label,
        "return_1d": _return_n(rows, 1),
        "return_5d": _return_n(rows, 5),
        "return_20d": _return_n(rows, 20),
        "realized_vol_20d": _realized_vol_20d(rows),
        "drawdown_20d": _drawdown_n(rows, 20),
        "drawdown_60d": _drawdown_n(rows, 60),
        "above_sma_20": _above_sma(rows, 20),
        "above_sma_50": _above_sma(rows, 50),
    }


# ── Data source hashing ─────────────────────────────────────────────────────

def compute_data_source_hash(histories: dict[str, list[dict]]) -> str:
    """Deterministic SHA-256 over sorted symbol → first/last date + count."""
    parts: list[str] = []
    for symbol in sorted(histories):
        rows = histories[symbol]
        if rows:
            parts.append(f"{symbol}:{len(rows)}:{rows[0].get('date','')}:{rows[-1].get('date','')}")
        else:
            parts.append(f"{symbol}:0::")
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


# ── Snapshot builder ─────────────────────────────────────────────────────────

def _compute_breadth(
    proxy_metrics: dict[str, dict],
) -> dict[str, float | None]:
    """Compute breadth metrics from available proxies."""
    above_20: list[bool] = []
    above_50: list[bool] = []
    positive_20d: list[bool] = []

    for symbol, metrics in proxy_metrics.items():
        if metrics["above_sma_20"] is not None:
            above_20.append(metrics["above_sma_20"])
        if metrics["above_sma_50"] is not None:
            above_50.append(metrics["above_sma_50"])
        if symbol in SECTOR_PROXY_SYMBOLS and metrics["return_20d"] is not None:
            positive_20d.append(metrics["return_20d"] > 0)

    return {
        "breadth_above_sma_20": sum(above_20) / len(above_20) if above_20 else None,
        "breadth_above_sma_50": sum(above_50) / len(above_50) if above_50 else None,
        "sector_positive_20d_ratio": sum(positive_20d) / len(positive_20d) if positive_20d else None,
    }


def _compute_risk_appetite(
    proxy_metrics: dict[str, dict],
) -> dict[str, float | None]:
    """Compute risk appetite proxies from metric differences."""
    def _get(sym: str, key: str) -> float | None:
        m = proxy_metrics.get(sym)
        return m.get(key) if m else None

    hyg_ret = _get("HYG", "return_20d")
    lqd_ret = _get("LQD", "return_20d")
    qqq_ret = _get("QQQ", "return_20d")
    xlp_ret = _get("XLP", "return_20d")
    iwm_ret = _get("IWM", "return_20d")
    spy_ret = _get("SPY", "return_20d")
    tlt_ret = _get("TLT", "return_20d")
    uup_ret = _get("UUP", "return_20d")

    return {
        "credit_risk_appetite_20d": (hyg_ret - lqd_ret) if hyg_ret is not None and lqd_ret is not None else None,
        "growth_vs_defensive_20d": (qqq_ret - xlp_ret) if qqq_ret is not None and xlp_ret is not None else None,
        "small_vs_large_20d": (iwm_ret - spy_ret) if iwm_ret is not None and spy_ret is not None else None,
        "duration_pressure_20d": (-tlt_ret) if tlt_ret is not None else None,
        "dollar_pressure_20d": uup_ret,
    }


def _compute_sector_rotation(
    proxy_metrics: dict[str, dict],
) -> dict[str, Any]:
    """Rank sectors by 20d relative strength vs SPY."""
    spy_ret = proxy_metrics.get("SPY", {}).get("return_20d")
    ranked: list[dict[str, Any]] = []
    for symbol in sorted(SECTOR_PROXY_SYMBOLS):
        m = proxy_metrics.get(symbol, {})
        sector_ret = m.get("return_20d")
        if sector_ret is not None and spy_ret is not None:
            rs = sector_ret - spy_ret
        else:
            rs = None
        ranked.append({"symbol": symbol, "return_20d": sector_ret, "relative_strength_20d": rs})
    ranked.sort(key=lambda r: r["relative_strength_20d"] if r["relative_strength_20d"] is not None else float("-inf"), reverse=True)
    return {"ranked_sectors": ranked}


def _classify_regime(
    proxy_metrics: dict[str, dict],
    breadth: dict[str, float | None],
    risk_appetite: dict[str, float | None],
    missing_symbols: list[str],
) -> tuple[str, list[str]]:
    """Rule-based regime classification with reasons."""
    reasons: list[str] = []

    if missing_symbols:
        return REGIME_DEGRADED_UNKNOWN, [f"missing required inputs: {', '.join(missing_symbols)}"]

    spy_ret = proxy_metrics.get("SPY", {}).get("return_20d")
    spy_vol = proxy_metrics.get("SPY", {}).get("realized_vol_20d")
    spy_dd = proxy_metrics.get("SPY", {}).get("drawdown_20d")
    breadth_20 = breadth.get("breadth_above_sma_20")
    breadth_50 = breadth.get("breadth_above_sma_50")
    sector_ratio = breadth.get("sector_positive_20d_ratio")
    credit_app = risk_appetite.get("credit_risk_appetite_20d")

    # High volatility: elevated VIX or high SPY vol with material drawdown
    vix_m = proxy_metrics.get("VIX", {})
    vix_close = None
    # We check vol thresholds
    high_vol = False
    if spy_vol is not None and spy_vol > 0.25 and spy_dd is not None and spy_dd < -0.05:
        high_vol = True
        reasons.append(f"SPY realized vol {spy_vol:.1%} with drawdown {spy_dd:.1%}")
    if high_vol:
        return REGIME_HIGH_VOLATILITY, reasons

    # Risk off: negative SPY, weak breadth, negative credit appetite
    if spy_ret is not None and spy_ret < 0:
        weak_breadth = breadth_20 is not None and breadth_20 < 0.4
        neg_credit = credit_app is not None and credit_app < 0
        if weak_breadth and neg_credit:
            reasons.append(f"SPY 20d return {spy_ret:.2%}")
            reasons.append(f"breadth above SMA20 {breadth_20:.0%}")
            reasons.append(f"credit risk appetite {credit_app:.2%}")
            return REGIME_RISK_OFF, reasons

    # Risk on broad: positive SPY, strong breadth, broad sector participation
    if spy_ret is not None and spy_ret > 0:
        strong_breadth = breadth_20 is not None and breadth_20 > 0.6
        broad_sectors = sector_ratio is not None and sector_ratio > 0.6
        if strong_breadth and broad_sectors:
            reasons.append(f"SPY 20d return {spy_ret:.2%}")
            reasons.append(f"breadth above SMA20 {breadth_20:.0%}")
            reasons.append(f"sector positive ratio {sector_ratio:.0%}")
            return REGIME_RISK_ON_BROAD, reasons

    # Risk on narrow: positive SPY/QQQ but weak breadth or narrow sectors
    qqq_ret = proxy_metrics.get("QQQ", {}).get("return_20d")
    if spy_ret is not None and spy_ret > 0 or qqq_ret is not None and qqq_ret > 0:
        reasons.append(f"SPY 20d return {spy_ret:.2%}" if spy_ret is not None else "SPY data unavailable")
        if breadth_20 is not None:
            reasons.append(f"breadth above SMA20 {breadth_20:.0%}")
        return REGIME_RISK_ON_NARROW, reasons

    # Range bound: nothing dominates
    reasons.append("no dominant regime signal")
    return REGIME_RANGE_BOUND, reasons


def _compute_confidence(
    coverage_ratio: float,
    proxy_metrics: dict[str, dict],
    breadth: dict[str, float | None],
    regime_label: str,
    warnings: list[str],
) -> float:
    """Confidence bounded [0, 1], penalized by contradictions."""
    confidence = min(1.0, coverage_ratio)

    # Contradiction penalties
    spy_ret = proxy_metrics.get("SPY", {}).get("return_20d")
    breadth_20 = breadth.get("breadth_above_sma_20")

    # Risk-on index with weak breadth
    if spy_ret is not None and spy_ret > 0 and breadth_20 is not None and breadth_20 < 0.4:
        confidence -= 0.15
        warnings.append("contradiction: positive SPY with weak breadth")

    # High volatility with risk-on
    spy_vol = proxy_metrics.get("SPY", {}).get("realized_vol_20d")
    if regime_label in (REGIME_RISK_ON_BROAD, REGIME_RISK_ON_NARROW):
        if spy_vol is not None and spy_vol > 0.25:
            confidence -= 0.15
            warnings.append("contradiction: high volatility with risk-on classification")

    # Equity strength with credit deterioration
    credit_app = None
    hyg_ret = proxy_metrics.get("HYG", {}).get("return_20d")
    lqd_ret = proxy_metrics.get("LQD", {}).get("return_20d")
    if hyg_ret is not None and lqd_ret is not None:
        credit_app = hyg_ret - lqd_ret
    if spy_ret is not None and spy_ret > 0 and credit_app is not None and credit_app < -0.02:
        confidence -= 0.10
        warnings.append("contradiction: equity strength with credit deterioration")

    return max(0.0, min(1.0, confidence))


def build_market_regime_snapshot(
    provider: Any,
    as_of_date: date,
    lookback_days: int = P37_DEFAULT_LOOKBACK_DAYS,
    proxy_universe: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build a deterministic market-regime snapshot from provider history."""
    proxies = proxy_universe or DEFAULT_MARKET_PROXIES
    start_date = as_of_date - timedelta(days=lookback_days)

    # Fetch and normalize all proxy histories
    raw_histories: dict[str, list[dict]] = {}
    normalized: dict[str, list[dict]] = {}
    missing: list[str] = []
    stale: list[str] = []
    warnings: list[str] = []

    for symbol in proxies:
        rows = provider.fetch_history(symbol, start_date, as_of_date)
        raw_histories[symbol] = rows
        norm = normalize_history_rows(rows)
        normalized[symbol] = norm
        if not norm:
            missing.append(symbol)

    # Compute data source hash
    data_source_hash = compute_data_source_hash(raw_histories)

    # Compute per-proxy metrics
    proxy_metrics: dict[str, dict] = {}
    for symbol, label in proxies.items():
        rows = normalized.get(symbol, [])
        if rows:
            proxy_metrics[symbol] = compute_proxy_metrics(symbol, label, rows)
        else:
            proxy_metrics[symbol] = {
                "symbol": symbol, "label": label,
                "return_1d": None, "return_5d": None, "return_20d": None,
                "realized_vol_20d": None, "drawdown_20d": None, "drawdown_60d": None,
                "above_sma_20": None, "above_sma_50": None,
            }

    # Coverage ratio
    total = len(proxies)
    available = total - len(missing)
    coverage_ratio = available / total if total > 0 else 0.0

    # Breadth, risk appetite, sector rotation
    breadth = _compute_breadth(proxy_metrics)
    risk_appetite = _compute_risk_appetite(proxy_metrics)
    sector_rotation = _compute_sector_rotation(proxy_metrics)

    # Classification
    regime_label, classification_reasons = _classify_regime(
        proxy_metrics, breadth, risk_appetite, missing,
    )

    # Confidence
    confidence = _compute_confidence(coverage_ratio, proxy_metrics, breadth, regime_label, warnings)

    # Status
    if missing:
        status = P37_STATUS_DEGRADED_MISSING_INPUTS
    elif warnings:
        status = P37_STATUS_COMPLETED_WITH_WARNINGS
    else:
        status = P37_STATUS_COMPLETED

    # Summary
    summary_parts: list[str] = []
    summary_parts.append(f"Regime: {regime_label}")
    summary_parts.append(f"Confidence: {confidence:.2f}")
    summary_parts.append(f"Coverage: {coverage_ratio:.0%}")
    if missing:
        summary_parts.append(f"Missing: {', '.join(missing)}")

    now = datetime.now(timezone.utc)

    return {
        "schema_version": P37_SCHEMA_VERSION,
        "as_of_date": str(as_of_date),
        "created_at": now.isoformat(),
        "status": status,
        "regime_label": regime_label,
        "confidence": round(confidence, 4),
        "coverage_ratio": round(coverage_ratio, 4),
        "summary": " | ".join(summary_parts),
        "classification_reasons": classification_reasons,
        "warnings": warnings,
        "missing_symbols": missing,
        "stale_symbols": stale,
        "breadth": breadth,
        "risk_appetite": risk_appetite,
        "sector_rotation": sector_rotation,
        "proxy_metrics": proxy_metrics,
        "data_source_hash": data_source_hash,
        "disclaimer": P37_ARTIFACT_DISCLAIMER,
    }


# ── Artifact writer ──────────────────────────────────────────────────────────

def write_market_regime_artifacts(
    snapshot: dict[str, Any],
    output_dir: Path,
) -> dict[str, Path]:
    """Write JSON and Markdown artifacts for a market-regime snapshot."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "p37_market_regime_snapshot.json"
    md_path = output_dir / "p37_market_regime_snapshot.md"

    # JSON
    json_path.write_text(json.dumps(snapshot, indent=2, default=str), encoding="utf-8")

    # Markdown
    lines: list[str] = []
    lines.append(f"# Market Regime Snapshot — {snapshot['as_of_date']}")
    lines.append("")
    lines.append(f"**Regime:** {snapshot['regime_label']}")
    lines.append(f"**Confidence:** {snapshot['confidence']:.2f}")
    lines.append(f"**Status:** {snapshot['status']}")
    lines.append("")
    lines.append("## Classification Reasons")
    lines.append("")
    for reason in snapshot.get("classification_reasons", []):
        lines.append(f"- {reason}")
    lines.append("")
    lines.append(f"## Disclaimer")
    lines.append("")
    lines.append(f"> {snapshot['disclaimer']}")
    lines.append("")
    lines.append("## Breadth")
    lines.append("")
    breadth = snapshot.get("breadth", {})
    for key, val in breadth.items():
        display = f"{val:.0%}" if val is not None else "N/A"
        lines.append(f"- **{key}:** {display}")
    lines.append("")
    lines.append("## Sector Rotation")
    lines.append("")
    lines.append("| Sector | Return 20d | Relative Strength vs SPY |")
    lines.append("|--------|-----------|--------------------------|")
    for sector in snapshot.get("sector_rotation", {}).get("ranked_sectors", []):
        ret = f"{sector['return_20d']:.2%}" if sector["return_20d"] is not None else "N/A"
        rs = f"{sector['relative_strength_20d']:.2%}" if sector["relative_strength_20d"] is not None else "N/A"
        lines.append(f"| {sector['symbol']} | {ret} | {rs} |")
    lines.append("")
    lines.append(f"*Data source hash: {snapshot.get('data_source_hash', 'N/A')}*")
    lines.append("")

    md_path.write_text("\n".join(lines), encoding="utf-8")

    return {"json": json_path, "md": md_path}


# ── Run orchestration ────────────────────────────────────────────────────────

def run_market_regime_context(
    db: Any,
    as_of_date: date,
    lookback_days: int = P37_DEFAULT_LOOKBACK_DAYS,
    output_root: Path | None = None,
    provider: Any | None = None,
) -> dict[str, Any]:
    """Run market-regime context: fetch, compute, persist, write artifacts."""
    # Default provider uses FutuQuoteClient
    if provider is None:
        from agent.research_v1.data.futu_opend import FutuQuoteClient

        class _FutuMarketProvider:
            data_source = "futu_opend"
            price_adjustment = "adjusted"

            def __init__(self) -> None:
                self._client = FutuQuoteClient()

            def fetch_history(self, symbol, start_date, end_date):
                return self._client.fetch_history(
                    symbol=symbol,
                    start_date=str(start_date),
                    end_date=str(end_date),
                )

        provider = _FutuMarketProvider()

    snapshot = build_market_regime_snapshot(provider, as_of_date, lookback_days)

    # Persist
    db.initialize_market_regime_schema()
    snapshot_id = db.save_market_regime_snapshot(snapshot)

    # Write artifacts
    if output_root is None:
        output_root = Path("output/governance")
    output_dir = Path(output_root) / str(as_of_date)
    paths = write_market_regime_artifacts(snapshot, output_dir)

    return {
        "status": snapshot["status"],
        "snapshot_id": snapshot_id,
        "output_dir": str(output_dir),
        "regime_label": snapshot["regime_label"],
        "confidence": snapshot["confidence"],
        "missing_symbols": snapshot["missing_symbols"],
        "warnings": snapshot["warnings"],
        "paths": paths,
    }
