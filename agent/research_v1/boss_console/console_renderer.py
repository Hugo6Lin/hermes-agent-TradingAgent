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


def _css() -> str:
    return (Path(__file__).parent / "static" / "boss_console.css").read_text(encoding="utf-8")


def _badge(value: str) -> str:
    lower = value.lower()
    cls = "sample"
    if "ready" in lower or "clear" in lower:
        cls = "ready"
    elif "red" in lower or "missing" in lower or "blocked" in lower:
        cls = "blocked"
    elif "preview" in lower or "limited" in lower or "caution" in lower or "incomplete" in lower:
        cls = "limited"
    return f'<span class="badge {cls}">{escape(value)}</span>'


def _report_card(report: dict[str, Any]) -> str:
    pdf = report.get("pdf_path") if report.get("pdf_status") == "ready" else ""
    html = report.get("html_path", "")
    pdf_action = f'<a class="action" href="{escape(pdf)}">Open PDF</a>' if pdf else '<span class="badge blocked">PDF missing</span>'
    html_action = f'<a class="action" href="{escape(html)}">Open HTML</a>' if html else ""
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
      <div class="chart-slot">P52 Futu chart slot</div>
      <div class="card">
        <h3>{escape(first.get("ticker", "No ticker selected"))}</h3>
        <p>{escape(first.get("verdict", "Open or generate a PDF brief to populate this workspace."))}</p>
        <table class="matrix" aria-label="Evidence Matrix">
          <tr><td>Live Data</td><td>{escape(str(first.get("live_data_status", "unknown")))}</td></tr>
          <tr><td>Evidence Base</td><td>{escape(str(first.get("evidence_base_status", "unknown")))}</td></tr>
          <tr><td>Guardrails</td><td>{escape(str(first.get("guardrail_status", "unknown")))}</td></tr>
          <tr><td>PDF</td><td>{escape(str(first.get("pdf_status", "missing")))}</td></tr>
        </table>
      </div>
    </section>
    <h2 class="section-title">Watchlist Heatmap</h2>
    <section class="heatmap-slot">P52 watchlist heatmap slot</section>
  </main>
</body>
</html>"""
    for term in FORBIDDEN_CONSOLE_TERMS:
        if term in html:
            raise ValueError(f"forbidden_console_term:{term}")
    return html
