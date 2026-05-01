"""Render the P51/P55 boss console HTML.

P55 applies the V2.1 cockpit visual language to the static HTML output:

* glass top chrome with brand mark + nav tabs
* glass command bar with ticker input
* full-width market regime strip
* watchlist heatmap card
* report center table
* ticker workspace with chart-first layout and evidence matrix
* evidence health and review queue side rail
* boss-readable status badges (Ready / Limited / Stale / Sample / Blocked /
  Missing) — never raw provider/monitor codes

The renderer is presentation-only. It does not call providers, run research,
invoke ``final_judge``, expose broker/order/trading controls, or include any
imperative trading copy.
"""

from __future__ import annotations

import re
from html import escape
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Forbidden-content and status-reduction tables.
# ---------------------------------------------------------------------------

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
    "buy this now",
    "sell this now",
)

# Terms that look "boss-friendly" but leak raw operational vocabulary or
# imperative trading instruction into the boss UI. These are checked as
# substrings (case-insensitive) on rendered HTML.
FORBIDDEN_CONSOLE_PHRASES = (
    "buy now",
    "sell now",
    "place order",
    "submit order",
    "unlock trade",
    "trade unlock",
    "copy trade",
    "auto trade",
    "follow this trade",
    "guaranteed edge",
    "production approved",
    "model promoted",
)

_STATUS_REDUCTION: dict[str, str] = {
    # Ready family
    "provider_ready": "Ready",
    "boss_preview_ready": "Ready",
    "boss_pdf_brief_ready": "Ready",
    "boss_pdf_brief_html_ready": "Ready",
    "boss_console_ready": "Ready",
    "brief_ready": "Ready",
    "completed": "Ready",
    "monitor_green": "Ready",
    "ready": "Ready",
    "clear": "Ready",
    "decision-grade": "Ready",
    "visual_assets_ready": "Ready",
    # Limited family
    "monitor_yellow": "Limited",
    "monitor_red": "Limited",
    "provider_not_tested_live": "Limited",
    "boss_preview_limited": "Limited",
    "boss_pdf_brief_degraded": "Limited",
    "degraded_missing_inputs": "Limited",
    "prompt_pack_limited": "Limited",
    "preview-only": "Limited",
    "preview-only / incomplete": "Limited",
    "incomplete": "Limited",
    "limited": "Limited",
    "caution": "Limited",
    # Sample family
    "preview_sample": "Sample",
    "sample": "Sample",
    # Stale family
    "stale": "Stale",
    # Blocked family
    "provider_unavailable": "Blocked",
    "blocked": "Blocked",
    "blocked_invalid_input": "Blocked",
    "boss_preview_blocked_invalid_input": "Blocked",
    "boss_pdf_brief_blocked_invalid_input": "Blocked",
    "boss_console_blocked_invalid_input": "Blocked",
    "blocked_missing_context": "Blocked",
    "visual_assets_missing_data": "Blocked",
    # Missing family
    "unknown": "Missing",
    "missing": "Missing",
    "not built yet": "Missing",
}


def _reduce_status(value: str) -> str:
    """Convert a raw provider/monitor/phase status to a boss-readable label.

    Always returns one of the V2.1 status set: Ready, Limited, Sample, Stale,
    Blocked, Missing.
    """
    raw = (value or "").strip()
    lower = raw.lower()
    if lower in _STATUS_REDUCTION:
        return _STATUS_REDUCTION[lower]
    if not lower:
        return "Missing"
    if "green" in lower or "ok" == lower:
        return "Ready"
    if "red" in lower or "blocked" in lower or "failed" in lower or "error" in lower:
        return "Blocked"
    if "yellow" in lower or "degraded" in lower or "partial" in lower or "preview" in lower or "incomplete" in lower:
        return "Limited"
    if "sample" in lower:
        return "Sample"
    if "stale" in lower:
        return "Stale"
    return "Missing"


def _badge_class(label: str) -> str:
    lower = label.lower()
    if lower == "ready":
        return "ready"
    if lower == "limited":
        return "limited"
    if lower == "stale":
        return "stale"
    if lower == "sample":
        return "sample"
    if lower in ("blocked", "missing"):
        return "blocked"
    return "sample"


def _badge(value: str) -> str:
    label = _reduce_status(value)
    return f'<span class="badge {_badge_class(label)}">{escape(label)}</span>'


def _css() -> str:
    return (Path(__file__).parent / "static" / "boss_console.css").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# SVG inlining (P52 visual assets).
# ---------------------------------------------------------------------------

def _inline_svg(path_value: str, fallback: str) -> str:
    if not path_value:
        return fallback
    path = Path(path_value)
    if not path.exists() or path.suffix.lower() != ".svg":
        return fallback
    text = path.read_text(encoding="utf-8")
    lower = text.lower()
    if "<script" in lower:
        return fallback
    if "onload=" in lower or "onclick=" in lower or "onerror=" in lower:
        return fallback
    if re.search(r'\bon\w+\s*=', lower):
        return fallback
    if "<foreignobject" in lower:
        return fallback
    if re.search(r'\b(?:href|src|xlink:href)\s*=\s*["\']https?://', lower):
        return fallback
    for term in FORBIDDEN_CONSOLE_TERMS:
        if term in lower:
            return fallback
    return f'<div class="visual-asset">{text}</div>'


# ---------------------------------------------------------------------------
# Section renderers.
# ---------------------------------------------------------------------------

def _topbar(model: dict[str, Any], health: dict[str, Any]) -> str:
    as_of = escape(str(model.get("as_of_date", "") or ""))
    overall_label = _reduce_status(str(health.get("overall_status", "missing")))
    return f"""
    <header class="topbar cockpit-chrome" role="banner">
      <div class="brandmark">
        <div class="mark" aria-hidden="true">H</div>
        <div class="wordmark">Hermes</div>
        <span class="divider" aria-hidden="true"></span>
        <span class="meta-tag">Boss Console</span>
      </div>
      <nav class="nav-tabs" aria-label="Cockpit views">
        <span class="tab is-active">Console</span>
        <span class="tab">Workspace</span>
        <span class="tab">Reports</span>
        <span class="tab">Evidence</span>
      </nav>
      <div class="chrome-meta">
        <span class="stamp">As of {as_of or '—'}</span>
        <span class="badge {_badge_class(overall_label)}">{escape(overall_label)}</span>
      </div>
    </header>
    <h1 class="visually-hidden" style="position:absolute;left:-9999px;">Hermes Boss Console</h1>
    """


def _command_bar(first: dict[str, Any]) -> str:
    live_label = _reduce_status(str(first.get("live_data_status", "missing")))
    return f"""
    <section class="command-region" aria-label="Run Boss Preview">
      <div class="command">
        <div class="ticker-input">
          <input
            aria-label="Ticker input"
            placeholder="Enter tickers — ZETA, NVDA, AMZN"
            autocomplete="off"
            spellcheck="false"
          />
          <button class="btn primary" type="button">Run Boss Preview</button>
          <button class="btn glass" type="button">Open workspace</button>
          <button class="btn glass" type="button">Request brief</button>
        </div>
        <div class="live-status">
          <span class="meta">Live data</span>
          <div class="row"><span class="badge {_badge_class(live_label)}">{escape(live_label)}</span></div>
        </div>
      </div>
    </section>
    """


def _market_strip(model: dict[str, Any]) -> str:
    items = list(model.get("market_tape") or [])
    if not items:
        items = [
            {"label": "S&P 500", "value": "—"},
            {"label": "NASDAQ", "value": "—"},
            {"label": "DOW", "value": "—"},
            {"label": "VIX", "value": "—"},
            {"label": "10Y", "value": "—"},
            {"label": "DXY", "value": "—"},
            {"label": "WTI", "value": "—"},
            {"label": "BTC", "value": "—"},
        ]
    cells = []
    for item in items:
        label = escape(str(item.get("label", "")))
        value = escape(str(item.get("value", "—")))
        delta = escape(str(item.get("delta", "")))
        cells.append(
            f'<div class="cell"><span class="label">{label}</span>'
            f'<span class="value">{value}</span>'
            f'<span class="delta">{delta}</span></div>'
        )
    return f'<section class="market-strip" aria-label="Market regime">{"".join(cells)}</section>'


def _heatmap_card(heatmap_html: str) -> str:
    return f"""
    <article class="card heatmap-card">
      <header class="card-head">
        <h3>Watchlist heatmap</h3>
        <span class="kicker">Sized by tracking weight · color = move</span>
      </header>
      {heatmap_html}
      <div class="heatmap-legend" aria-hidden="true">
        <span>Cell color = move</span>
        <span>Cell size = tracking weight</span>
        <span>Dot = evidence state</span>
      </div>
    </article>
    """


def _report_center(reports: list[dict[str, Any]]) -> str:
    if not reports:
        body = """
          <div class="report-cards">
            <div class="report-card"><h3>No briefs yet</h3>
              <p class="meta">Run Boss Preview to generate a research brief.</p>
            </div>
          </div>
        """
        return f"""
        <article class="card">
          <header class="card-head">
            <h3>Report Center</h3>
            <span class="kicker">0 briefs</span>
          </header>
          {body}
        </article>
        """

    rows = []
    for report in reports:
        ticker = escape(str(report.get("ticker", "")))
        as_of = escape(str(report.get("as_of_date", "")))
        verdict = escape(str(report.get("verdict") or "Open the brief to review."))
        live_badge = _badge(str(report.get("live_data_status", "missing")))
        evidence_badge = _badge(str(report.get("evidence_base_status", "missing")))
        guardrail_badge = _badge(str(report.get("guardrail_status", "missing")))
        sample_badge = ""
        if report.get("sample"):
            sample_badge = '<span class="badge sample">Preview sample — not decision-grade</span>'

        pdf_path = report.get("pdf_path") if report.get("pdf_status") == "ready" else ""
        html_path = report.get("html_path") if report.get("html_status") == "ready" else ""
        pdf_action = (
            f'<a class="action" href="{escape(pdf_path)}">Open PDF</a>'
            if pdf_path
            else '<span class="badge blocked">PDF missing</span>'
        )
        html_action = (
            f'<a class="action ghost" href="{escape(html_path)}">Open HTML</a>'
            if html_path
            else '<span class="badge blocked">HTML missing</span>'
        )

        rows.append(
            f"""
            <tr>
              <td class="ticker-cell">{ticker}</td>
              <td class="verdict-cell">
                <div class="verdict">{verdict}</div>
                <div class="meta">As of {as_of}</div>
              </td>
              <td>{live_badge}</td>
              <td>{evidence_badge}</td>
              <td>{guardrail_badge}</td>
              <td>{sample_badge}</td>
              <td class="row-actions">{pdf_action}{html_action}</td>
            </tr>
            """
        )

    table = f"""
      <table class="report-table">
        <thead>
          <tr>
            <th scope="col">Ticker</th>
            <th scope="col">Verdict</th>
            <th scope="col">Live data</th>
            <th scope="col">Evidence</th>
            <th scope="col">Guardrails</th>
            <th scope="col">Sample</th>
            <th scope="col" style="text-align:right;">Open</th>
          </tr>
        </thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    """

    return f"""
    <article class="card">
      <header class="card-head">
        <h3>Report Center</h3>
        <span class="kicker">{len(reports)} brief{'' if len(reports) == 1 else 's'}</span>
      </header>
      {table}
    </article>
    """


def _ticker_workspace(first: dict[str, Any], chart_html: str) -> str:
    ticker = escape(str(first.get("ticker", "No ticker selected")))
    verdict = escape(str(first.get("verdict") or "Open or generate a PDF brief to populate this workspace."))
    matrix_rows = "".join(
        f"<tr><td>{escape(label)}</td><td>{escape(_reduce_status(str(first.get(field, 'unknown'))))}</td></tr>"
        for label, field in (
            ("Live data", "live_data_status"),
            ("Evidence base", "evidence_base_status"),
            ("Guardrails", "guardrail_status"),
            ("PDF", "pdf_status"),
            ("HTML", "html_status"),
        )
    )
    return f"""
    <article class="card">
      <header class="card-head">
        <h3>Ticker Workspace</h3>
        <span class="kicker">Selected: {ticker}</span>
      </header>
      <div class="workspace">
        <div class="chart-pane">
          {chart_html}
        </div>
        <div class="verdict-pane">
          <strong style="font-size:14px;">{ticker}</strong>
          <p style="margin:8px 0 12px; color: var(--text-secondary);">{verdict}</p>
          <h4 style="margin: 8px 0 6px; font-size: 12px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; color: var(--text-secondary);">Evidence Matrix</h4>
          <table class="matrix" role="table">
            {matrix_rows}
          </table>
        </div>
      </div>
    </article>
    """


def _live_data_card(first: dict[str, Any]) -> str:
    rows = []
    for label, field in (
        ("Live quote", "live_data_status"),
        ("Brief PDF", "pdf_status"),
        ("Brief HTML", "html_status"),
        ("Preview", "preview_status"),
    ):
        rows.append(
            f"""
            <div class="health-row">
              <div class="pillar"><span class="name">{escape(label)}</span>{_badge(str(first.get(field, 'missing')))}</div>
            </div>
            """
        )
    return f"""
    <article class="card">
      <header class="card-head">
        <h3>Live data status</h3>
        <span class="kicker">Cockpit health</span>
      </header>
      <div class="health-list">{''.join(rows)}</div>
    </article>
    """


def _evidence_health_card(health: dict[str, Any]) -> str:
    overall = _reduce_status(str(health.get("overall_status", "missing")))
    overall_cls = _badge_class(overall)
    missing = health.get("missing_context_patterns") or []
    missing_safe = []
    for raw in missing:
        if not isinstance(raw, str):
            continue
        # Convert internal pattern names like "outcome_context" → "Outcome context"
        pretty = raw.replace("_", " ").strip().capitalize()
        if not pretty:
            continue
        missing_safe.append(pretty)
    missing_html = (
        '<ul style="margin:8px 0 0; padding-left:18px; color: var(--text-secondary); font-size:12px;">'
        + "".join(f"<li>{escape(item)}</li>" for item in missing_safe[:8])
        + "</ul>"
        if missing_safe
        else '<p class="meta" style="margin:6px 0 0;">No missing-context patterns flagged.</p>'
    )
    return f"""
    <article class="card">
      <header class="card-head">
        <h3>Evidence health</h3>
        <span class="badge {overall_cls}">{escape(overall)}</span>
      </header>
      <div class="card-body">
        <div class="health-row">
          <div class="bar"><div class="bar-fill {overall_cls}" style="width: {'100%' if overall == 'Ready' else '60%' if overall == 'Limited' else '30%'};"></div></div>
          <div class="note">Watchlist evidence consolidated across previews.</div>
        </div>
        {missing_html}
      </div>
    </article>
    """


def _review_queue_card(reports: list[dict[str, Any]]) -> str:
    items = []
    for report in reports[:3]:
        ticker = escape(str(report.get("ticker", "")))
        evidence = _reduce_status(str(report.get("evidence_base_status", "missing")))
        if evidence in ("Ready",):
            reason = "Thesis stable · re-grade after next data refresh"
        elif evidence == "Limited":
            reason = "Limited evidence · refresh evidence"
        elif evidence == "Stale":
            reason = "Evidence stale · refresh sources"
        elif evidence == "Sample":
            reason = "Preview sample · review guardrails"
        else:
            reason = "Evidence gap · review guardrails"
        items.append(
            f"""
            <div class="item">
              <span class="ticker">{ticker}</span>
              <span class="reason">{escape(reason)}</span>
              <span class="due">today</span>
            </div>
            """
        )
    if not items:
        items.append(
            '<p class="meta">No items in queue. Run Boss Preview to populate.</p>'
        )
    return f"""
    <article class="card">
      <header class="card-head">
        <h3>Today's review queue</h3>
        <span class="kicker">{min(len(reports), 3)} item{'' if len(reports) == 1 else 's'}</span>
      </header>
      <div class="card-body">
        <div class="review-queue">{''.join(items)}</div>
      </div>
    </article>
    """


# ---------------------------------------------------------------------------
# Public API.
# ---------------------------------------------------------------------------

def render_console_html(model: dict[str, Any]) -> str:
    reports = model.get("reports", [])
    first = reports[0] if reports else {}
    health = model.get("evidence_health", {}) or {}

    chart_html = _inline_svg(
        (first.get("visual_assets") or {}).get("kline_svg", ""),
        '<div class="chart-slot">P52 Futu chart slot</div>',
    )
    heatmap_html = _inline_svg(
        first.get("heatmap_svg", ""),
        '<section class="heatmap-region legacy-fallback">P52 watchlist heatmap slot</section>',
    )

    body = f"""
    <main class="shell">
      {_topbar(model, health)}
      {_command_bar(first)}
      {_market_strip(model)}
      <div class="cockpit-grid">
        <div class="col-main">
          {_heatmap_card(heatmap_html)}
          {_report_center(reports)}
          {_ticker_workspace(first, chart_html)}
        </div>
        <div class="col-side">
          {_live_data_card(first)}
          {_evidence_health_card(health)}
          {_review_queue_card(reports)}
        </div>
      </div>
    </main>
    """

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Hermes Boss Console</title>
  <style>{_css()}</style>
</head>
<body>{body}</body>
</html>"""

    lowered = html.lower()
    for term in FORBIDDEN_CONSOLE_TERMS:
        if term in lowered:
            raise ValueError(f"forbidden_console_term:{term}")
    for phrase in FORBIDDEN_CONSOLE_PHRASES:
        if phrase in lowered:
            raise ValueError(f"forbidden_console_phrase:{phrase}")
    return html
