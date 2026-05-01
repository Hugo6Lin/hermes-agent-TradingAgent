"""P52 read-only Futu market visualization assets."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import date, timedelta
from html import escape
from pathlib import Path
from typing import Any, Protocol

P52_SCHEMA_VERSION = "p52_market_visual_assets.1"
P52_STATUS_READY = "visual_assets_ready"
P52_STATUS_LIMITED = "visual_assets_limited"
P52_STATUS_MISSING = "visual_assets_missing_data"
P52_STATUS_BLOCKED = "blocked_invalid_input"
P52_DISCLAIMER = (
    "P52 is read-only market visualization. It does not recommend trades, "
    "submit orders, unlock trading, query positions, approve production adoption, "
    "train models, schedule jobs, or mutate research decisions."
)
SUPPORTED_HEATMAP_METRICS = {"return_1d", "return_5d", "return_20d"}
FORBIDDEN_RENDER_TERMS = (
    "buy this now",
    "sell this now",
    "follow this trade",
    "guaranteed edge",
    "production approved",
    "model promoted",
    "place order",
    "submit order",
    "unlock trade",
)


class MarketVisualProvider(Protocol):
    data_source: str
    price_adjustment: str

    def fetch_history(self, symbol: str, start_date: str, end_date: str) -> list[dict]: ...
    def fetch_snapshot(self, symbols: list[str]) -> list[dict]: ...


def validate_market_visual_inputs(
    *,
    tickers: list[str],
    as_of_date: str,
    history_days: int,
    heatmap_metric: str,
    port: int = 11111,
) -> list[str]:
    errors: list[str] = []
    try:
        date.fromisoformat(as_of_date)
    except (TypeError, ValueError):
        errors.append("invalid_date_format")
    if not tickers:
        errors.append("tickers_required")
    for ticker in tickers:
        clean = str(ticker).strip().upper()
        if not clean or any(ch in clean for ch in "<>\"' "):
            errors.append(f"invalid_ticker:{ticker}")
    if history_days < 20:
        errors.append("history_days_minimum_20")
    if heatmap_metric not in SUPPORTED_HEATMAP_METRICS:
        errors.append(f"invalid_heatmap_metric:{heatmap_metric}")
    if not isinstance(port, int) or port <= 0 or port > 65535:
        errors.append("invalid_port")
    return errors


def normalize_history_rows(ticker: str, raw_rows: list[dict]) -> tuple[list[dict], list[str]]:
    warnings: list[str] = []
    seen: dict[str, dict] = {}
    for row in raw_rows:
        d = row.get("date")
        c = row.get("close")
        if not d or c is None:
            continue
        normalized = {
            "date": str(d),
            "open": float(row.get("open", c)),
            "high": float(row.get("high", c)),
            "low": float(row.get("low", c)),
            "close": float(c),
            "volume": int(row.get("volume", 0)),
            "price_adjustment": str(row.get("price_adjustment", "adjusted")),
        }
        if d in seen:
            warnings.append(f"duplicate_history_date:{ticker}:{d}")
        seen[d] = normalized
    sorted_rows = sorted(seen.values(), key=lambda r: r["date"])
    return sorted_rows, warnings


def _metrics(history: list[dict]) -> dict:
    if not history:
        return {}
    closes = [r["close"] for r in history]
    last = closes[-1]
    ret_1d = (closes[-1] / closes[-2] - 1) if len(closes) >= 2 else None
    ret_5d = (closes[-1] / closes[-6] - 1) if len(closes) >= 6 else None
    ret_20d = (closes[-1] / closes[-21] - 1) if len(closes) >= 21 else None
    highs_20 = [r["high"] for r in history[-20:]] if len(history) >= 20 else [r["high"] for r in history]
    peak = max(highs_20)
    drawdown_20d = (last / peak - 1) if peak > 0 else None
    sma_20 = sum(closes[-20:]) / min(20, len(closes)) if len(closes) >= 1 else None
    sma_50 = sum(closes[-50:]) / min(50, len(closes)) if len(closes) >= 1 else None
    return {
        "last_close": last,
        "return_1d": round(ret_1d, 6) if ret_1d is not None else None,
        "return_5d": round(ret_5d, 6) if ret_5d is not None else None,
        "return_20d": round(ret_20d, 6) if ret_20d is not None else None,
        "drawdown_20d": round(drawdown_20d, 6) if drawdown_20d is not None else None,
        "sma_20": round(sma_20, 4) if sma_20 is not None else None,
        "sma_50": round(sma_50, 4) if sma_50 is not None else None,
        "above_sma_20": last >= sma_20 if sma_20 is not None else None,
        "above_sma_50": last >= sma_50 if sma_50 is not None else None,
        "history_row_count": len(history),
        "history_start": history[0]["date"],
        "history_end": history[-1]["date"],
    }


def _compute_source_hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]


def build_market_visual_report(
    *,
    tickers: list[str],
    as_of_date: str,
    history_days: int = 120,
    heatmap_metric: str = "return_20d",
    provider: MarketVisualProvider | None = None,
    live: bool = True,
) -> dict:
    normalized_tickers = [t.strip().upper() for t in tickers if t.strip()]
    ticker_visuals: list[dict] = []
    all_warnings: list[str] = []
    end_date = as_of_date
    start_dt = date.fromisoformat(as_of_date) - timedelta(days=history_days + 10)
    start_date = start_dt.isoformat()

    for ticker in normalized_tickers:
        history: list[dict] = []
        if provider is not None:
            try:
                raw = provider.fetch_history(ticker, start_date, end_date)
                history, hist_warnings = normalize_history_rows(ticker, raw)
                all_warnings.extend(hist_warnings)
            except Exception as exc:
                all_warnings.append(f"provider_error:{ticker}:{exc}")

        if not history:
            ticker_visuals.append({
                "ticker": ticker,
                "data_status": "visual_missing_data",
                "metrics": {},
                "history": [],
                "asset_paths": {},
            })
            continue

        m = _metrics(history)
        data_status = "visual_ready" if m.get("history_row_count", 0) >= 20 else "visual_limited"
        ticker_visuals.append({
            "ticker": ticker,
            "data_status": data_status,
            "metrics": m,
            "history": history,
            "asset_paths": {},
        })

    ready_count = sum(1 for v in ticker_visuals if v["data_status"] == "visual_ready")
    if ready_count == len(normalized_tickers):
        status = P52_STATUS_READY
    elif ready_count > 0:
        status = P52_STATUS_LIMITED
    else:
        status = P52_STATUS_MISSING

    provider_status = "provider_not_used_offline" if (not live and provider is None) else "provider_ready"

    hash_payload = {
        "schema_version": P52_SCHEMA_VERSION,
        "as_of_date": as_of_date,
        "tickers": normalized_tickers,
        "history_days": history_days,
        "heatmap_metric": heatmap_metric,
        "provider_data_source": provider.data_source if provider else "offline",
        "price_adjustment": provider.price_adjustment if provider else "none",
        "history": {v["ticker"]: v["history"] for v in ticker_visuals},
    }
    source_hash = _compute_source_hash(hash_payload)

    return {
        "schema_version": P52_SCHEMA_VERSION,
        "status": status,
        "as_of_date": as_of_date,
        "tickers": normalized_tickers,
        "history_days": history_days,
        "heatmap_metric": heatmap_metric,
        "provider_status": provider_status,
        "ticker_visuals": ticker_visuals,
        "heatmap": {},
        "warnings": all_warnings,
        "source_hash": source_hash,
        "disclaimer": P52_DISCLAIMER,
    }


def render_kline_svg(visual: dict) -> str:
    ticker = escape(str(visual.get("ticker", "")))
    history = visual.get("history") or []
    metrics = visual.get("metrics") or {}
    data_status = visual.get("data_status", "missing")

    if data_status == "visual_missing_data" or not history:
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" width="600" height="200" viewBox="0 0 600 200">'
            f'<rect width="600" height="200" fill="#f6f1e8"/>'
            f'<text x="300" y="100" text-anchor="middle" font-family="system-ui" font-size="14" fill="#8a7e6a">'
            f'{ticker}: No data available</text></svg>'
        )

    width, height = 600, 260
    pad_left, pad_right, pad_top, pad_bottom = 50, 20, 30, 50
    chart_w = width - pad_left - pad_right
    chart_h = height - pad_top - pad_bottom

    lows = [r["low"] for r in history]
    highs = [r["high"] for r in history]
    y_min = min(lows)
    y_max = max(highs)
    y_range = y_max - y_min if y_max > y_min else 1.0

    def _x(i: int) -> float:
        return pad_left + (i + 0.5) * chart_w / len(history)

    def _y(val: float) -> float:
        return pad_top + (1.0 - (val - y_min) / y_range) * chart_h

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'<rect width="{width}" height="{height}" fill="#f6f1e8"/>',
    ]

    date_start = escape(history[0]["date"])
    date_end = escape(history[-1]["date"])
    parts.append(f'<text x="{pad_left}" y="18" font-family="system-ui" font-size="12" fill="#5a5040">{ticker} {date_start} to {date_end}</text>')

    for i, row in enumerate(history):
        x = _x(i)
        o, c, h, l = row["open"], row["close"], row["high"], row["low"]
        color = "#2d8a4e" if c >= o else "#c0392b"
        parts.append(f'<line x1="{x:.1f}" y1="{_y(h):.1f}" x2="{x:.1f}" y2="{_y(l):.1f}" stroke="{color}" stroke-width="1"/>')
        body_top = _y(max(o, c))
        body_bot = _y(min(o, c))
        body_h = max(body_bot - body_top, 1)
        parts.append(f'<rect x="{x - 2:.1f}" y="{body_top:.1f}" width="4" height="{body_h:.1f}" fill="{color}"/>')

    sma_20 = metrics.get("sma_20")
    sma_50 = metrics.get("sma_50")
    if sma_20 is not None and len(history) >= 20:
        sma_y = _y(sma_20)
        parts.append(f'<line x1="{pad_left}" y1="{sma_y:.1f}" x2="{width - pad_right}" y2="{sma_y:.1f}" stroke="#d4a017" stroke-width="1.5" stroke-dasharray="4,2"/>')
        parts.append(f'<text x="{width - pad_right}" y="{sma_y - 4:.1f}" text-anchor="end" font-family="system-ui" font-size="9" fill="#d4a017">SMA20</text>')
    if sma_50 is not None and len(history) >= 50:
        sma_y = _y(sma_50)
        parts.append(f'<line x1="{pad_left}" y1="{sma_y:.1f}" x2="{width - pad_right}" y2="{sma_y:.1f}" stroke="#7d6b8a" stroke-width="1.5" stroke-dasharray="4,2"/>')
        parts.append(f'<text x="{width - pad_right}" y="{sma_y - 4:.1f}" text-anchor="end" font-family="system-ui" font-size="9" fill="#7d6b8a">SMA50</text>')

    strip_y = height - 10
    strip_items = []
    for label, key in [("1D", "return_1d"), ("5D", "return_5d"), ("20D", "return_20d"), ("DD20", "drawdown_20d")]:
        val = metrics.get(key)
        if val is not None:
            color = "#2d8a4e" if val >= 0 else "#c0392b"
            strip_items.append(f'<tspan fill="{color}">{label}: {val * 100:+.1f}%</tspan>')
    if strip_items:
        parts.append(f'<text x="{pad_left}" y="{strip_y}" font-family="system-ui" font-size="10" fill="#5a5040">{"  ".join(strip_items)}</text>')

    parts.append("</svg>")
    svg = "".join(parts)
    _check_forbidden(svg)
    return svg


def render_heatmap_svg(visuals: list[dict], metric: str) -> str:
    tiles = []
    for v in visuals:
        ticker = escape(str(v.get("ticker", "")))
        m = v.get("metrics") or {}
        val = m.get(metric)
        data_status = v.get("data_status", "missing")
        if data_status == "visual_missing_data" or val is None:
            tiles.append({"ticker": ticker, "value": None, "label": "No data"})
        else:
            tiles.append({"ticker": ticker, "value": val, "label": f"{val * 100:+.1f}%"})

    cols = max(1, math.ceil(math.sqrt(len(tiles))))
    tile_w, tile_h = 120, 70
    gap = 8
    rows_count = math.ceil(len(tiles) / cols) if tiles else 1
    width = cols * tile_w + (cols - 1) * gap + 20
    height = rows_count * tile_h + (rows_count - 1) * gap + 40

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'<rect width="{width}" height="{height}" fill="#f6f1e8"/>',
        f'<text x="10" y="18" font-family="system-ui" font-size="12" fill="#5a5040">Watchlist Heatmap — {escape(metric)}</text>',
    ]

    for idx, tile in enumerate(tiles):
        col = idx % cols
        row_idx = idx // cols
        x = 10 + col * (tile_w + gap)
        y = 28 + row_idx * (tile_h + gap)
        val = tile["value"]
        if val is None:
            fill = "#d5d0c8"
        elif val > 0:
            intensity = min(val / 0.2, 1.0)
            fill = f"rgb({int(200 - 80 * intensity)}, {int(220 - 40 * intensity)}, {int(200 - 80 * intensity)})"
        elif val < 0:
            intensity = min(abs(val) / 0.2, 1.0)
            fill = f"rgb({int(220 - 40 * intensity)}, {int(200 - 80 * intensity)}, {int(200 - 80 * intensity)})"
        else:
            fill = "#e8e4dc"
        parts.append(f'<rect x="{x}" y="{y}" width="{tile_w}" height="{tile_h}" rx="4" fill="{fill}"/>')
        parts.append(f'<text x="{x + tile_w / 2}" y="{y + 28}" text-anchor="middle" font-family="system-ui" font-size="12" font-weight="bold" fill="#3a3428">{tile["ticker"]}</text>')
        parts.append(f'<text x="{x + tile_w / 2}" y="{y + 48}" text-anchor="middle" font-family="system-ui" font-size="11" fill="#5a5040">{escape(tile["label"])}</text>')

    parts.append("</svg>")
    svg = "".join(parts)
    _check_forbidden(svg)
    return svg


def _check_forbidden(text: str) -> None:
    lower = text.lower()
    for term in FORBIDDEN_RENDER_TERMS:
        if term in lower:
            raise ValueError(f"forbidden_render_term:{term}")


def write_market_visual_artifacts(report: dict, output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    assets_dir = output_dir / "p52_assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    artifact_paths: dict[str, str] = {}

    for visual in report.get("ticker_visuals", []):
        ticker = visual.get("ticker", "")
        if visual.get("data_status") != "visual_missing_data" and visual.get("history"):
            kline_path = assets_dir / f"{ticker}_kline.svg"
            kline_path.write_text(render_kline_svg(visual), encoding="utf-8")
            visual["asset_paths"]["kline_svg"] = str(kline_path)
            artifact_paths[f"{ticker}_kline_svg"] = str(kline_path)

    ready_visuals = [v for v in report.get("ticker_visuals", []) if v.get("data_status") != "visual_missing_data" and v.get("history")]
    if ready_visuals:
        heatmap_path = assets_dir / "watchlist_heatmap.svg"
        heatmap_path.write_text(render_heatmap_svg(ready_visuals, report.get("heatmap_metric", "return_20d")), encoding="utf-8")
        report["heatmap"] = {"asset_path": str(heatmap_path), "tile_count": len(ready_visuals), "metric": report.get("heatmap_metric", "return_20d")}
        artifact_paths["watchlist_heatmap_svg"] = str(heatmap_path)

    json_path = output_dir / "p52_market_visual_snapshot.json"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    artifact_paths["snapshot_json"] = str(json_path)

    md_path = output_dir / "p52_market_visual_snapshot.md"
    md_lines = [
        "# P52 Market Visual Snapshot",
        "",
        f"As of: {report.get('as_of_date', '')}",
        f"Status: {report.get('status', '')}",
        f"Disclaimer: {P52_DISCLAIMER}",
        "",
    ]
    for v in report.get("ticker_visuals", []):
        m = v.get("metrics") or {}
        md_lines.append(f"## {v.get('ticker', '')}")
        md_lines.append(f"- Data status: {v.get('data_status', '')}")
        if m:
            md_lines.append(f"- Last close: {m.get('last_close', 'N/A')}")
            md_lines.append(f"- Return 20d: {m.get('return_20d', 'N/A')}")
        md_lines.append("")
    for w in report.get("warnings", []):
        md_lines.append(f"- Warning: {w}")
    md_path.write_text("\n".join(md_lines), encoding="utf-8")
    artifact_paths["snapshot_md"] = str(md_path)

    return artifact_paths


class _OfflineProvider:
    data_source = "offline"
    price_adjustment = "none"

    def fetch_history(self, symbol: str, start_date: str, end_date: str) -> list[dict]:
        return []

    def fetch_snapshot(self, symbols: list[str]) -> list[dict]:
        return []


class _DefaultFutuVisualProvider:
    def __init__(self, host: str = "127.0.0.1", port: int = 11111):
        from agent.research_v1.data.futu_opend import FutuQuoteClient, FutuOpenDConfig
        config = FutuOpenDConfig(host=host, port=port)
        self._client = FutuQuoteClient(config=config)
        self.data_source = "futu_opend"
        self.price_adjustment = "adjusted"

    def fetch_history(self, symbol: str, start_date: str, end_date: str) -> list[dict]:
        return self._client.fetch_history(symbol, start_date, end_date)

    def fetch_snapshot(self, symbols: list[str]) -> list[dict]:
        return self._client.fetch_snapshot(symbols)


def run_market_visual_assets(
    *,
    tickers: list[str],
    as_of_date: str,
    output_root: Path,
    history_days: int = 120,
    provider: MarketVisualProvider | None = None,
    live: bool = True,
    heatmap_metric: str = "return_20d",
    host: str = "127.0.0.1",
    port: int = 11111,
) -> dict:
    warnings = validate_market_visual_inputs(
        tickers=tickers,
        as_of_date=as_of_date,
        history_days=history_days,
        heatmap_metric=heatmap_metric,
        port=port,
    )
    if warnings:
        return {
            "status": P52_STATUS_BLOCKED,
            "warnings": warnings,
            "output_dir": "",
            "artifact_paths": [],
            "provider_status": "provider_not_used",
        }

    offline_mode = not live and provider is None
    if provider is None:
        if live:
            provider = _DefaultFutuVisualProvider(host=host, port=port)
        else:
            provider = _OfflineProvider()

    report = build_market_visual_report(
        tickers=tickers,
        as_of_date=as_of_date,
        history_days=history_days,
        heatmap_metric=heatmap_metric,
        provider=provider,
        live=live,
    )

    if offline_mode:
        report["provider_status"] = "provider_not_used_offline"

    output_dir = Path(output_root) / as_of_date
    artifact_paths = write_market_visual_artifacts(report, output_dir)
    report["output_dir"] = str(output_dir)
    report["artifact_paths"] = list(artifact_paths.values())
    return report
