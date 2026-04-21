"""PDF export for Hermes canonical research reports."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

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


def _render_report_html(reports: list[dict], signals: list[dict], watchlist_entries: list[dict] | None = None) -> str:
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
</body>
</html>
"""


def export_task_pdf(
    database: ResearchDatabase,
    task_id: str,
    output_dir: str | Path,
) -> Path:
    """
    Export a research task's canonical reports and signals as a PDF document.

    Args:
        database: ResearchDatabase instance.
        task_id: The research task ID.
        output_dir: Directory to write the PDF.

    Returns:
        Path to the exported PDF file.
    """
    reports = database.get_canonical_reports_by_task(task_id)
    conn = database._get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM canonical_signals WHERE task_id = ? ORDER BY created_at DESC",
        (task_id,),
    )
    import json
    signals = []
    for row in cursor.fetchall():
        d = dict(row)
        d['risk_flags'] = json.loads(d.pop('risk_flags_json', '[]'))
        signals.append(d)
    conn.close()

    # Phase 16: fetch watchlist entries
    try:
        watchlist_entries = database.list_watchlist_entries()
    except Exception:
        watchlist_entries = []

    if not reports and not signals:
        raise KeyError(f"No canonical reports or signals found for task {task_id!r}")

    output_path = Path(output_dir).expanduser().resolve()
    output_path.mkdir(parents=True, exist_ok=True)
    pdf_path = output_path / f"task_{task_id}.pdf"

    html = _render_report_html(reports, signals, watchlist_entries)
    edge_executable = _find_edge_executable()

    with tempfile.TemporaryDirectory(dir=str(output_path)) as temp_dir:
        html_path = Path(temp_dir) / f"task_{task_id}.html"
        html_path.write_text(html, encoding="utf-8")

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
            timeout=120,
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
