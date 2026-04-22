"""PDF export for Hermes canonical research reports.

This module provides two export paths:
1. export_task_pdf - exports a research task as a legacy-style PDF (backward compatible)
2. export_poster_pdf - exports a single-ticker decision poster (new poster-style)
3. export_batch_report_pdf - exports a multi-ticker batch report (new report-style)

All use the same color system: orange-red (#E85A3C) + teal-green (#2DD4A8)
and Chinese-first bilingual hierarchy.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Optional

from agent.research_v1.data.database import ResearchDatabase


def _find_edge_executable() -> Path:
    """Locate a local Microsoft Edge executable for headless PDF export."""
    candidates = [
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    ]

    env_path = shutil.which("msedge") or shutil.which("msedge.exe")
    if env_path:
        candidates.insert(0, Path(env_path))

    for candidate in candidates:
        if candidate.exists():
            return candidate

    raise FileNotFoundError(
        "Microsoft Edge is required for PDF export but could not be found. "
        "Expected msedge.exe in a standard install location."
    )


def _watchlist_rows(entries: list[dict] | None) -> str:
    """Render watchlist entries as HTML table rows."""
    from html import escape
    if not entries:
        return '<tr><td colspan="5">No watchlist entries</td></tr>'
    rows = ""
    for e in entries:
        rows += f"""
        <tr>
          <td>{escape(e.get('ticker', ''))}</td>
          <td>{escape(e.get('status', ''))}</td>
          <td>{escape(e.get('thesis_state', ''))}</td>
          <td>{escape(e.get('alert_level', ''))}</td>
          <td>{escape(e.get('current_action_bias', ''))}</td>
        </tr>
        """
    return rows


def _validation_rows(entries: list[dict] | None) -> str:
    """Render validation results as HTML table rows."""
    from html import escape
    if not entries:
        return '<tr><td colspan="6">No validation results</td></tr>'
    rows = ""
    for e in entries:
        rows += f"""
        <tr>
          <td>{escape(e.get('ticker', ''))}</td>
          <td>{escape(e.get('regime', ''))}</td>
          <td>{escape(e.get('historical_support', ''))}</td>
          <td>{escape(e.get('environment_fit', ''))}</td>
          <td>{escape(e.get('main_failure_mode', ''))}</td>
          <td>{e.get('validation_confidence', 0.0):.0%}</td>
        </tr>
        """
    return rows


def _render_report_html(reports: list[dict], signals: list[dict], watchlist_entries: list[dict] | None = None, validation_results: list[dict] | None = None) -> str:
    """Render a batch research report as HTML from canonical data."""
    from html import escape

    report_rows = ""
    for r in reports:
        trade_plan = r.get("trade_plan") or {}
        risk_watch = r.get("risk_watch") or []
        risk_watch_html = "<br/>".join(f"<li>{escape(rw)}</li>" for rw in risk_watch) if risk_watch else "<li>None</li>"
        report_rows += f"""
        <section class="report-card">
          <h2>{escape(r.get('title', ''))} <span class="ticker">{escape(r.get('ticker', ''))}</span></h2>
          <p class="bottom-line"><strong>Bottom Line:</strong> {escape(r.get('bottom_line', ''))}</p>
          <p><strong>Executive Summary:</strong> {escape(r.get('executive_summary', ''))}</p>
          <p><strong>Why Now:</strong> {escape(r.get('why_now', ''))}</p>
          <div class="case-grid">
            <div class="case bullish">
              <h3>Bull Case</h3>
              <p>{escape(r.get('bull_case', ''))}</p>
            </div>
            <div class="case bearish">
              <h3>Bear Case</h3>
              <p>{escape(r.get('bear_case', ''))}</p>
            </div>
          </div>
          <p><strong>Trade Plan:</strong> {escape(trade_plan.get('action', 'N/A'))} |
            Entry: {trade_plan.get('entry_price', 'N/A')} |
            Stop: {trade_plan.get('stop_loss', 'N/A')} |
            Target: {trade_plan.get('take_profit', 'N/A')} |
            Horizon: {escape(trade_plan.get('holding_period', 'N/A'))}</p>
          <p><strong>Risk Watch:</strong></p>
          <ul>{risk_watch_html}</ul>
        </section>
        """

    signal_rows = ""
    for s in signals:
        risk_flags = s.get("risk_flags") or []
        risk_html = ", ".join(escape(str(rf)) for rf in risk_flags) if risk_flags else "None"
        signal_rows += f"""
        <tr>
          <td>{escape(s.get('ticker', ''))}</td>
          <td>{escape(s.get('rating', ''))}</td>
          <td>{s.get('confidence', 0.0):.0%}</td>
          <td>{s.get('priority_score', 0.0):.1f}</td>
          <td>{risk_html}</td>
        </tr>
        """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>Hermes Research Batch</title>
  <style>
    :root {{
      --bg: #f5efe1;
      --panel: #fffaf0;
      --ink: #1f2933;
      --accent: #0f766e;
      --line: #d6c7a6;
      --buy: #15803d;
      --sell: #b91c1c;
      --hold: #92400e;
    }}
    body {{
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      background: var(--bg);
      color: var(--ink);
      padding: 32px;
    }}
    h1 {{ margin-bottom: 8px; }}
    .meta {{ color: #666; margin-bottom: 24px; }}
    .report-card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 20px 24px;
      margin-bottom: 24px;
      box-shadow: 0 4px 12px rgba(31,41,51,0.06);
    }}
    .report-card h2 {{ margin: 0 0 8px; }}
    .report-card h2 .ticker {{ color: var(--accent); font-size: 0.8em; }}
    .bottom-line {{ font-size: 1.05em; }}
    .case-grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;
      margin: 12px 0;
    }}
    .case h3 {{ margin: 0 0 6px; font-size: 0.95em; }}
    .bullish h3 {{ color: var(--buy); }}
    .bearish h3 {{ color: var(--sell); }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 12px;
    }}
    th, td {{
      text-align: left;
      padding: 8px 6px;
      border-bottom: 1px solid rgba(214,199,166,0.7);
    }}
    th {{ color: var(--accent); font-weight: 700; }}
    ul {{ margin: 4px 0; padding-left: 20px; }}
  </style>
</head>
<body>
  <h1>Hermes Research Batch</h1>
  <p class="meta">{len(reports)} report(s), {len(signals)} signal(s)</p>
  {report_rows}
  <h2>Signals</h2>
  <table>
    <thead>
      <tr>
        <th>Ticker</th>
        <th>Rating</th>
        <th>Confidence</th>
        <th>Priority</th>
        <th>Risk Flags</th>
      </tr>
    </thead>
    <tbody>{signal_rows}</tbody>
  </table>

  <h2>Watchlist</h2>
  <table>
    <thead>
      <tr>
        <th>Ticker</th>
        <th>Status</th>
        <th>Thesis State</th>
        <th>Alert Level</th>
        <th>Action Bias</th>
      </tr>
    </thead>
    <tbody>
      {(_watchlist_rows(watchlist_entries) if watchlist_entries else '<tr><td colspan="5">No watchlist entries</td></tr>')}
    </tbody>
  </table>

  <h2>Validation</h2>
  <table>
    <thead>
      <tr>
        <th>Ticker</th>
        <th>Regime</th>
        <th>Historical Support</th>
        <th>Environment Fit</th>
        <th>Main Failure Mode</th>
        <th>Confidence</th>
      </tr>
    </thead>
    <tbody>
      {(_validation_rows(validation_results) if validation_results else '<tr><td colspan="6">No validation results</td></tr>')}
    </tbody>
  </table>
</body>
</html>
"""


def _write_html_to_pdf(html: str, pdf_path: Path, timeout: int = 120) -> Path:
    """Write HTML content to PDF using Edge headless.

    Args:
        html: HTML content string.
        pdf_path: Output path for the PDF file.
        timeout: Timeout in seconds for the Edge process.

    Returns:
        Path to the exported PDF file.
    """
    edge_executable = _find_edge_executable()
    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(dir=str(pdf_path.parent)) as temp_dir:
        html_path = Path(temp_dir) / "output.html"
        html_path.write_text(html, encoding="utf-8")

        # Copy CSS to temp dir for local loading
        template_dir = Path(__file__).parent / "report_templates"
        css_path = template_dir / "boss_report_pdf.css"
        if css_path.exists():
            shutil.copy(css_path, Path(temp_dir) / "boss_report_pdf.css")

        command = [
            str(edge_executable),
            "--headless",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            "--allow-file-access-from-files",
            "--run-all-compositor-stages-before-draw",
            f"--print-to-pdf={pdf_path}",
            html_path.as_uri(),
        ]
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            raise RuntimeError(
                "Microsoft Edge failed to export the PDF.\n"
                f"stdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}"
            )

    if not pdf_path.exists() or pdf_path.stat().st_size == 0:
        raise RuntimeError("PDF export completed but did not produce a valid file")

    return pdf_path


# =============================================================================
# Legacy API - kept for backward compatibility
# =============================================================================

def export_task_pdf(
    database: ResearchDatabase,
    task_id: str,
    output_dir: str | Path,
) -> Path:
    """
    Export a research task's canonical reports and signals as a PDF document.

    Uses the new Boss Report template (render_batch_report) instead of the legacy
    raw-HTML template.

    Args:
        database: ResearchDatabase instance.
        task_id: The research task ID.
        output_dir: Directory to write the PDF.

    Returns:
        Path to the exported PDF file.
    """
    from agent.research_v1.report_templates.renderer import render_batch_report

    def _first_present(*values: Any, default: Any = "N/A") -> Any:
        for value in values:
            if value not in (None, "", [], {}):
                return value
        return default

    reports = database.get_canonical_reports_by_task(task_id)
    conn = database._get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM canonical_signals WHERE task_id = ? ORDER BY created_at DESC",
        (task_id,),
    )
    signals = []
    for row in cursor.fetchall():
        record = dict(row)
        record["risk_flags"] = json.loads(record.pop("risk_flags_json", "[]"))
        signals.append(record)
    conn.close()

    try:
        watchlist_entries = database.list_watchlist_entries()
    except Exception:
        watchlist_entries = []

    try:
        validation_results = database.list_validation_results()
    except Exception:
        validation_results = []

    if not reports and not signals:
        raise KeyError(f"No canonical reports or signals found for task {task_id!r}")

    signal_by_ticker = {
        signal.get("ticker"): signal
        for signal in signals
        if signal.get("ticker")
    }

    batch_items: list[dict[str, Any]] = []
    company_reports: list[dict[str, Any]] = []
    for rank, report in enumerate(reports, start=1):
        trade_plan = report.get("trade_plan")
        if isinstance(trade_plan, str):
            try:
                trade_plan = json.loads(trade_plan)
            except (json.JSONDecodeError, TypeError):
                trade_plan = {}
        trade_plan = trade_plan or {}

        decision_card = report.get("decision_card")
        instrument_rec = report.get("instrument_rec")
        options_structure = report.get("options_structure")
        early_exit = report.get("early_exit")

        ticker = report.get("ticker", "N/A")
        signal = signal_by_ticker.get(ticker, {})
        primary_action = _first_present(
            decision_card.get("primary_action") if isinstance(decision_card, dict) else None,
            instrument_rec.get("primary_action") if isinstance(instrument_rec, dict) else None,
            signal.get("rating"),
            report.get("rating"),
            default="Watchlist",
        )
        confidence = _first_present(
            report.get("confidence"),
            signal.get("confidence"),
            default=0,
        )
        company_name = _first_present(
            report.get("company_name"),
            report.get("title"),
            signal.get("company_name"),
            default="N/A",
        )
        bottom_line = _first_present(
            report.get("bottom_line"),
            decision_card.get("thesis_summary") if isinstance(decision_card, dict) else None,
            default="",
        )
        why_now = _first_present(
            report.get("why_now"),
            decision_card.get("why_now") if isinstance(decision_card, dict) else None,
            default="",
        )
        bull_case = _first_present(
            report.get("bull_case"),
            decision_card.get("thesis_summary") if isinstance(decision_card, dict) else None,
            default="",
        )
        entry_price = _first_present(
            trade_plan.get("entry_price"),
            signal.get("entry_price"),
            default="N/A",
        )
        take_profit = _first_present(
            trade_plan.get("take_profit"),
            signal.get("take_profit"),
            default="N/A",
        )

        batch_items.append({
            "symbol": ticker,
            "company_name": company_name,
            "overall_rating": primary_action,
            "confidence": confidence,
            "action": primary_action,
            "entry_price": entry_price,
            "take_profit": take_profit,
            "display_rank": rank,
        })

        company_reports.append({
            "ticker": ticker,
            "company_name": company_name,
            "rating": primary_action,
            "confidence": confidence,
            "bottom_line": bottom_line,
            "why_now": why_now,
            "trade_plan": trade_plan,
            "bull_case": bull_case,
            "bear_case": report.get("bear_case", ""),
            "risk_watch": report.get("risk_watch", []),
            "research_summary": report.get("executive_summary", ""),
            "position_decision": decision_card,
            "instrument_rec": instrument_rec,
            "options_structure": options_structure,
            "early_exit": early_exit,
        })

    if not batch_items:
        for rank, signal in enumerate(signals, start=1):
            primary_action = _first_present(signal.get("rating"), default="Watchlist")
            batch_items.append({
                "symbol": signal.get("ticker", "N/A"),
                "company_name": signal.get("company_name", "N/A"),
                "overall_rating": primary_action,
                "confidence": signal.get("confidence", 0),
                "action": primary_action,
                "entry_price": signal.get("entry_price", "N/A"),
                "take_profit": signal.get("take_profit", "N/A"),
                "display_rank": rank,
            })

    output_path = Path(output_dir).expanduser().resolve()
    pdf_path = output_path / f"task_{task_id}.pdf"
    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    template_dir = Path(__file__).parent / "report_templates"
    css_path = template_dir / "boss_report_pdf.css"
    css_content = css_path.read_text(encoding="utf-8") if css_path.exists() else ""

    if batch_items:
        top_item = batch_items[0]
        executive_summary = (
            f"Top pick: {top_item.get('symbol', 'N/A')} "
            f"({top_item.get('action', 'Watchlist')}) - "
            f"Confidence: {top_item.get('confidence', 0):.0%}"
        )
    else:
        executive_summary = ""

    html = render_batch_report(
        batch_items=batch_items,
        company_reports=company_reports,
        watchlist_entries=watchlist_entries,
        validation_results=validation_results,
        executive_summary=executive_summary,
    )

    if css_content and "<link rel=" in html:
        html = html.replace(
            '<link rel="stylesheet" href="boss_report_pdf.css"/>',
            f"<style>\n{css_content}\n</style>",
        )

    return _write_html_to_pdf(html, pdf_path)


# =============================================================================
# New Poster & Report APIs
# =============================================================================

def export_poster_pdf(
    signal: dict,
    report: dict,
    output_path: str | Path,
    market_data: Optional[dict] = None,
    watchlist_entry: Optional[dict] = None,
    validation_result: Optional[dict] = None,
    position_decision: Optional[Any] = None,
    instrument_rec: Optional[Any] = None,
    options_structure: Optional[Any] = None,
    early_exit_plan: Optional[Any] = None,
) -> Path:
    """
    Export a single-ticker decision poster as a PDF document.

    This generates the Boss Poster - a single-page decision board with:
    - TOP ZONE: Action, Size, Target, Ticker, Conviction, Why Now, Risks
    - MIDDLE ZONE: KPIs, Thesis, Technical, Instrument Choice, Options
    - BOTTOM ZONE: Watchlist State, Validation Summary

    Args:
        signal: Canonical signal dict with ticker, rating, confidence, entry_price, etc.
        report: Canonical report dict with bottom_line, why_now, bull_case, risk_watch, trade_plan, etc.
        output_path: Output path for the PDF file.
        market_data: Optional dict with current price, P/E, EPS growth, analyst rating.
        watchlist_entry: Optional watchlist entry dict.
        validation_result: Optional validation result dict.
        position_decision: Optional PositionDecisionCard dataclass with primary_action, conviction, etc.
        instrument_rec: Optional InstrumentRecommendation dataclass with ranked_alternatives.
        options_structure: Optional OptionsStructure dataclass with primary_contract details.
        early_exit_plan: Optional EarlyExitPlan dataclass with exit zones.

    Returns:
        Path to the exported PDF file.
    """
    from agent.research_v1.report_templates.renderer import render_boss_poster

    pdf_path = Path(output_path).expanduser().resolve()
    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    # Inline CSS into HTML for standalone rendering
    template_dir = Path(__file__).parent / "report_templates"
    css_path = template_dir / "boss_report_pdf.css"
    if css_path.exists():
        css_content = css_path.read_text(encoding="utf-8")
    else:
        css_content = ""

    html = render_boss_poster(
        signal=signal,
        report=report,
        market_data=market_data,
        watchlist_entry=watchlist_entry,
        validation_result=validation_result,
        position_decision=position_decision,
        instrument_rec=instrument_rec,
        options_structure=options_structure,
        early_exit_plan=early_exit_plan,
    )

    # Inject CSS inline for standalone HTML
    if css_content and "<link rel=" in html:
        html = html.replace(
            '<link rel="stylesheet" href="boss_report_pdf.css"/>',
            f'<style>\n{css_content}\n</style>'
        )

    return _write_html_to_pdf(html, pdf_path)


def export_batch_report_pdf(
    batch_items: list[dict],
    company_reports: list[dict],
    output_path: str | Path,
    watchlist_entries: Optional[list[dict]] = None,
    validation_results: Optional[list[dict]] = None,
    executive_summary: str = "",
) -> Path:
    """
    Export a multi-ticker batch report as a PDF document.

    This generates the Boss Report - a multi-page executive report with:
    - PAGE 1: Batch overview table + executive summary
    - PAGES 2+: Individual company reports (one per ticker)
    - FINAL PAGE: Watchlist state + validation summary

    Args:
        batch_items: List of research batch item dicts.
        company_reports: List of company report dicts.
        output_path: Output path for the PDF file.
        watchlist_entries: Optional list of watchlist entry dicts.
        validation_results: Optional list of validation result dicts.
        executive_summary: Optional executive summary text.

    Returns:
        Path to the exported PDF file.
    """
    from agent.research_v1.report_templates.renderer import render_batch_report

    pdf_path = Path(output_path).expanduser().resolve()
    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    # Inline CSS into HTML for standalone rendering
    template_dir = Path(__file__).parent / "report_templates"
    css_path = template_dir / "boss_report_pdf.css"
    if css_path.exists():
        css_content = css_path.read_text(encoding="utf-8")
    else:
        css_content = ""

    html = render_batch_report(
        batch_items=batch_items,
        company_reports=company_reports,
        watchlist_entries=watchlist_entries,
        validation_results=validation_results,
        executive_summary=executive_summary,
    )

    # Inject CSS inline for standalone HTML
    if css_content and "<link rel=" in html:
        html = html.replace(
            '<link rel="stylesheet" href="boss_report_pdf.css"/>',
            f'<style>\n{css_content}\n</style>'
        )

    return _write_html_to_pdf(html, pdf_path)

