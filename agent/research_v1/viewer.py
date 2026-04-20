"""Minimal read-only web viewer for Hermes."""

from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from agent.research_v1.data.database import ResearchDatabase


def build_viewer_snapshot(database: ResearchDatabase) -> dict:
    """Collect the minimal dashboard dataset from persisted tables."""
    return {
        "signals": database.list_recent_signals(limit=20),
        "positions": database.list_positions(status="open", limit=20),
        "paper_trades": database.list_paper_trades(status="open", limit=20),
        "alerts": database.list_recent_alerts(unread_only=True, limit=20),
    }


def build_end_of_day_summary(snapshot: dict) -> str:
    """Build a narrow text summary for end-of-day review."""
    top_signal = "None"
    if snapshot["signals"]:
        ranked = sorted(snapshot["signals"], key=lambda item: item.get("priority_score", 0), reverse=True)
        top_signal = ranked[0]["symbol"]

    return (
        f"Top signal: {top_signal}\n"
        f"Open positions: {len(snapshot['positions'])}\n"
        f"Paper trades: {len(snapshot['paper_trades'])}\n"
        f"Unread alerts: {len(snapshot['alerts'])}"
    )


def _render_table(title: str, rows: list[dict], columns: list[str]) -> str:
    headers = "".join(f"<th>{escape(column.replace('_', ' ').title())}</th>" for column in columns)
    if not rows:
        body = f"<tr><td colspan='{len(columns)}'>No data</td></tr>"
    else:
        rendered_rows = []
        for row in rows:
            cells = "".join(f"<td>{escape(str(row.get(column, '')))}</td>" for column in columns)
            rendered_rows.append(f"<tr>{cells}</tr>")
        body = "".join(rendered_rows)

    return f"""
    <section class="panel">
      <h2>{escape(title)}</h2>
      <table>
        <thead><tr>{headers}</tr></thead>
        <tbody>{body}</tbody>
      </table>
    </section>
    """


def render_dashboard_html(snapshot: dict) -> str:
    """Render a single-page minimal dashboard."""
    signal_table = _render_table(
        "Current Signals",
        snapshot["signals"],
        ["symbol", "grade", "priority_score", "confidence"],
    )
    position_table = _render_table(
        "Open Positions",
        snapshot["positions"],
        ["symbol", "status", "quantity", "entry_price"],
    )
    paper_table = _render_table(
        "Paper Trades",
        snapshot["paper_trades"],
        ["symbol", "status", "quantity", "entry_price"],
    )
    alert_table = _render_table(
        "Alerts",
        snapshot["alerts"],
        ["symbol", "alert_type", "message"],
    )
    summary = escape(build_end_of_day_summary(snapshot)).replace("\n", "<br/>")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Hermes Viewer</title>
  <style>
    :root {{
      --bg: #f5efe1;
      --panel: #fffaf0;
      --ink: #1f2933;
      --accent: #0f766e;
      --line: #d6c7a6;
    }}
    body {{
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      background: linear-gradient(180deg, #efe4c8 0%, var(--bg) 55%, #f9f6ee 100%);
      color: var(--ink);
    }}
    main {{
      max-width: 1080px;
      margin: 0 auto;
      padding: 32px 20px 48px;
    }}
    h1 {{
      margin-bottom: 8px;
      font-size: clamp(2rem, 4vw, 3rem);
      letter-spacing: 0.02em;
    }}
    .summary {{
      background: rgba(15, 118, 110, 0.08);
      border: 1px solid rgba(15, 118, 110, 0.2);
      padding: 14px 16px;
      border-radius: 14px;
      margin-bottom: 20px;
      line-height: 1.6;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 16px;
    }}
    .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 16px;
      box-shadow: 0 12px 24px rgba(31, 41, 51, 0.06);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.95rem;
    }}
    th, td {{
      text-align: left;
      padding: 8px 6px;
      border-bottom: 1px solid rgba(214, 199, 166, 0.7);
    }}
    th {{
      color: var(--accent);
      font-weight: 700;
    }}
  </style>
</head>
<body>
  <main>
    <h1>Hermes Minimal Viewer</h1>
    <p>Signals, positions, alerts, and paper trades in one page.</p>
    <div class="summary">{summary}</div>
    <div class="grid">
      {signal_table}
      {position_table}
      {paper_table}
      {alert_table}
    </div>
  </main>
</body>
</html>
"""


def serve_viewer(database: ResearchDatabase, host: str = "127.0.0.1", port: int = 8008) -> ThreadingHTTPServer:
    """Create a tiny HTTP server for the Hermes dashboard."""

    class _ViewerHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            snapshot = build_viewer_snapshot(database)
            html = render_dashboard_html(snapshot).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)

        def log_message(self, format: str, *args) -> None:  # noqa: A003
            return

    return ThreadingHTTPServer((host, port), _ViewerHandler)
