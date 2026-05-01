"""Render P51 boss console HTML."""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

FORBIDDEN_CONSOLE_TERMS = (
    "canonical_recommendation_outcomes",
    "db_call_failed",
    "phase_failed",
    "artifact_paths",
    "unlock_trade",
    "place order",
    "submit order",
    "production approved",
    "model promoted",
    "guaranteed edge",
    "follow this trade",
)

_STATUS_REDUCTION: dict[str, str] = {
    "provider_ready": "Ready",
    "boss_preview_ready": "Ready",
    "boss_pdf_brief_ready": "Ready",
    "brief_ready": "Ready",
    "completed": "Ready",
    "monitor_green": "Ready",
    "monitor_yellow": "Caution",
    "monitor_red": "Caution",
    "provider_not_tested_live": "Limited",
    "provider_unavailable": "Missing",
    "boss_preview_limited": "Limited",
    "boss_pdf_brief_degraded": "Limited",
    "degraded_missing_inputs": "Limited",
    "blocked": "Missing",
    "blocked_invalid_input": "Missing",
    "boss_preview_blocked_invalid_input": "Missing",
    "boss_pdf_brief_blocked_invalid_input": "Missing",
    "unknown": "Not built yet",
    "missing": "Not built yet",
    "preview-only": "Preview only",
    "preview-only / incomplete": "Preview only",
    "decision-grade": "Ready",
    "incomplete": "Limited",
    "clear": "Ready",
    "caution": "Caution",
    "ready": "Ready",
    "limited": "Limited",
}


def _reduce_status(value: str) -> str:
    lower = value.strip().lower()
    return _STATUS_REDUCTION.get(lower, value)


def _css() -> str:
    return (Path(__file__).parent / "static" / "boss_console.css").read_text(encoding="utf-8")


def _badge(value: str) -> str:
    reduced = _reduce_status(value)
    lower = reduced.lower()
    cls = "sample"
    if "ready" in lower or "clear" in lower:
        cls = "ready"
    elif "red" in lower or "missing" in lower or "blocked" in lower or "not built" in lower:
        cls = "blocked"
    elif "preview" in lower or "limited" in lower or "caution" in lower or "incomplete" in lower:
        cls = "limited"
    return f'<span class="badge {cls}">{escape(reduced)}</span>'


def _inline_svg(path_value: str, fallback: str) -> str:
    if not path_value:
        return fallback
    path = Path(path_value)
    if not path.exists() or path.suffix.lower() != ".svg":
        return fallback
    text = path.read_text(encoding="utf-8")
    if "<script" in text.lower():
        return fallback
    return f'<div class="visual-asset">{text}</div>'


def _report_card(report: dict[str, Any]) -> str:
    pdf = report.get("pdf_path") if report.get("pdf_status") == "ready" else ""
    html_ready = report.get("html_status") == "ready"
    html = report.get("html_path", "") if html_ready else ""
    pdf_action = f'<a class="action" href="{escape(pdf)}">Open PDF</a>' if pdf else '<span class="badge blocked">PDF missing</span>'
    html_action = f'<a class="action" href="{escape(html)}">Open HTML</a>' if html else '<span class="badge blocked">HTML missing</span>'
    sample = '<div class="meta">Preview sample — not decision-grade</div>' if report.get("sample") else ""
    return f"""
    <article class="card report-card">
      <h3>{escape(report.get("ticker", ""))}</h3>
      <p>{escape(report.get("verdict", "No verdict available."))}</p>
      <div>{_badge(str(report.get("live_data_status", "unknown")))} {_badge(str(report.get("evidence_base_status", "unknown")))} {_badge(str(report.get("guardrail_status", "unknown")))}</div>
      {sample}
      <p class="meta">As of {escape(str(report.get("as_of_date", "")))}</p>
      <div style="display:flex; gap:8px; flex-wrap:wrap;">{pdf_action}{html_action}</div>
    </article>
    """


def render_console_html(model: dict[str, Any]) -> str:
    reports = model.get("reports", [])
    cards = "".join(_report_card(r) for r in reports) or '<div class="card">No boss reports found yet.</div>'
    first = reports[0] if reports else {}
    health = model.get("evidence_health", {})
    market_tape = model.get("market_tape") or [
        {"label": "SPY", "value": "P52"},
        {"label": "QQQ", "value": "P52"},
        {"label": "VIX", "value": "P52"},
        {"label": "10Y", "value": "P52"},
    ]
    tape = "".join(f'<span class="tape-chip">{escape(x["label"])} {escape(str(x["value"]))}</span>' for x in market_tape)

    chart_html = _inline_svg(
        (first.get("visual_assets") or {}).get("kline_svg", ""),
        '<div class="chart-slot">P52 Futu chart slot</div>',
    )
    heatmap_html = _inline_svg(
        first.get("heatmap_svg", ""),
        '<section class="heatmap-slot">P52 watchlist heatmap slot</section>',
    )

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>Hermes Boss Console</title>
  <style>{_css()}</style>
</head>
<body>
  <main class="shell">
    <header class="topbar">
      <div class="brand"><h1>Hermes Boss Console</h1><p>Research cockpit · PDF briefs · evidence health</p></div>
      <div>{_badge(str(health.get("overall_status", "missing")))}</div>
    </header>
    <section class="market-tape">{tape}</section>
    <section class="command" aria-label="Run Boss Preview">
      <input aria-label="Ticker input" placeholder="Enter tickers — ZETA, NVDA, AMZN"/>
      <button type="button">Run Boss Preview</button>
    </section>
    <section class="grid">
      <div class="card"><div class="meta">Live Data</div>{_badge(str(first.get("live_data_status", "Unknown")))}</div>
      <div class="card"><div class="meta">Evidence</div>{_badge(str(first.get("evidence_base_status", "Unknown")))}</div>
      <div class="card"><div class="meta">Latest PDF</div>{_badge(str(first.get("pdf_status", "missing")))}</div>
      <div class="card"><div class="meta">Monitor</div>{_badge(str(health.get("overall_status", "missing")))}</div>
    </section>
    <h2 class="section-title">Report Center</h2>
    <section class="reports">{cards}</section>
    <h2 class="section-title">Ticker Workspace</h2>
    <section class="workspace">
      {chart_html}
      <div class="card">
        <h3>{escape(first.get("ticker", "No ticker selected"))}</h3>
        <p>{escape(first.get("verdict", "Open or generate a PDF brief to populate this workspace."))}</p>
        <table class="matrix" aria-label="Evidence Matrix">
          <tr><td>Live Data</td><td>{escape(_reduce_status(str(first.get("live_data_status", "unknown"))))}</td></tr>
          <tr><td>Evidence Base</td><td>{escape(_reduce_status(str(first.get("evidence_base_status", "unknown"))))}</td></tr>
          <tr><td>Guardrails</td><td>{escape(_reduce_status(str(first.get("guardrail_status", "unknown"))))}</td></tr>
          <tr><td>PDF</td><td>{escape(_reduce_status(str(first.get("pdf_status", "missing"))))}</td></tr>
        </table>
      </div>
    </section>
    <h2 class="section-title">Watchlist Heatmap</h2>
    {heatmap_html}
  </main>
</body>
</html>"""
    for term in FORBIDDEN_CONSOLE_TERMS:
        if term in html:
            raise ValueError(f"forbidden_console_term:{term}")
    return html
