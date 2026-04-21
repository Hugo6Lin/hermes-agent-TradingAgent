"""Minimal read-only web viewer for Hermes."""

from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from agent.research_v1.data.database import ResearchDatabase


def _fetch_latest_batch(database: ResearchDatabase) -> dict | None:
    """Load the latest persisted research batch and its ticker items."""
    conn = database._get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT batch_id FROM research_batches ORDER BY batch_id DESC LIMIT 1")
        row = cursor.fetchone()
        if row is None:
            return None
        batch_id = row["batch_id"]
        batch = database.get_research_batch(batch_id)
        if batch is None:
            return None
        items = database.list_research_batch_items(batch_id)
        for item in items:
            conn2 = database._get_connection()
            cursor2 = conn2.cursor()
            try:
                cursor2.execute(
                    "SELECT * FROM company_reports WHERE batch_item_id = ? ORDER BY report_id DESC LIMIT 1",
                    (item["item_id"],),
                )
                report_row = cursor2.fetchone()
                item["report"] = dict(report_row) if report_row else None
            finally:
                conn2.close()
        return {
            "mode": "batch",
            "batch": batch,
            "items": items,
        }
    finally:
        conn.close()


def _fetch_batch_item_snapshot(database: ResearchDatabase, item_id: int) -> dict | None:
    """Load the owning batch and canonical report for a specific ticker item."""
    conn = database._get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM research_batch_items WHERE item_id = ?", (item_id,))
        item_row = cursor.fetchone()
        if item_row is None:
            return None
        item = dict(item_row)
        batch_id = item["batch_id"]
        batch = database.get_research_batch(batch_id)
        if batch is None:
            return None
        cursor.execute(
            "SELECT * FROM company_reports WHERE batch_item_id = ? ORDER BY report_id DESC LIMIT 1",
            (item_id,),
        )
        report_row = cursor.fetchone()
        item["report"] = dict(report_row) if report_row else None
        return {
            "mode": "batch",
            "batch": batch,
            "items": [item],
        }
    finally:
        conn.close()


def build_viewer_snapshot(database: ResearchDatabase) -> dict:
    """Collect the minimal dashboard dataset from persisted tables.

    Includes both legacy tables (signals, positions, paper_trades, alerts)
    and canonical tables (canonical_signals, canonical_reports).
    Gracefully degrades when canonical tables have not been initialized yet.
    """
    # Prefer latest batch if one exists
    try:
        batch_snapshot = _fetch_latest_batch(database)
        if batch_snapshot is not None:
            return batch_snapshot
    except Exception:
        pass

    snapshot = {
        "mode": "legacy",
        "signals": database.list_recent_signals(limit=20),
        "positions": database.list_positions(status="open", limit=20),
        "paper_trades": database.list_paper_trades(status="open", limit=20),
        "alerts": database.list_recent_alerts(unread_only=True, limit=20),
    }
    try:
        snapshot["canonical_signals"] = database.list_canonical_signals(limit=20)
        snapshot["canonical_reports"] = database.list_canonical_reports(limit=20)
    except Exception:
        snapshot["canonical_signals"] = []
        snapshot["canonical_reports"] = []
    # Phase 16: structured watchlist entries
    try:
        snapshot["watchlist_entries"] = database.list_watchlist_entries()
    except Exception:
        snapshot["watchlist_entries"] = []
    return snapshot


def build_end_of_day_summary(snapshot: dict) -> str:
    """Build a narrow text summary for end-of-day review."""
    if snapshot.get("mode") == "batch":
        batch = snapshot["batch"]
        top_item = snapshot["items"][0] if snapshot["items"] else None
        return (
            f"Executive summary: {batch.get('boss_summary', 'None')}\n"
            f"Top ticker: {top_item['symbol'] if top_item else 'None'}\n"
            f"Top risk: {top_item['top_risk'] if top_item else 'None'}"
        )

    top_signal = "None"
    if snapshot.get("signals"):
        ranked = sorted(snapshot["signals"], key=lambda item: item.get("priority_score", 0), reverse=True)
        top_signal = ranked[0]["symbol"]
    elif snapshot.get("canonical_signals"):
        ranked = sorted(snapshot["canonical_signals"], key=lambda item: item.get("priority_score", 0), reverse=True)
        top_signal = ranked[0]["ticker"]

    return (
        f"Top signal: {top_signal}\n"
        f"Open positions: {len(snapshot.get('positions', []))}\n"
        f"Paper trades: {len(snapshot.get('paper_trades', []))}\n"
        f"Unread alerts: {len(snapshot.get('alerts', []))}"
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


def _render_batch_overview_html(snapshot: dict) -> str:
    """Render batch overview page."""
    batch = snapshot["batch"]
    items = snapshot["items"]
    requested_tickers = ", ".join(batch.get("requested_tickers", []))
    top_item = items[0] if items else None
    cards = []
    for item in items:
        report = item.get("report") or {}
        cards.append(
            f"""
            <article class="ticker-card">
              <div class="ticker-meta">Rank {escape(str(item['display_rank']))} / {escape(item['overall_rating'])}</div>
              <h3><a href="/ticker/{escape(str(item['item_id']))}">{escape(item['symbol'])}</a></h3>
              <p><strong>Action:</strong> {escape(item['action'])}</p>
              <p><strong>Top Thesis:</strong> {escape(item['top_thesis'])}</p>
              <p><strong>Top Risk:</strong> {escape(item['top_risk'])}</p>
              <p><strong>Bottom Line:</strong> {escape(report.get('bottom_line', ''))}</p>
            </article>
            """
        )

    top_risk_text = escape(top_item["top_risk"]) if top_item else "None"
    top_ticker = escape(top_item["symbol"]) if top_item else "None"
    summary = escape(batch.get("boss_summary", ""))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Hermes Research Batch</title>
  <style>
    :root {{
      --bg: #0f172a;
      --panel: rgba(15, 23, 42, 0.82);
      --panel-soft: rgba(30, 41, 59, 0.86);
      --ink: #e2e8f0;
      --muted: #94a3b8;
      --accent: #f59e0b;
      --line: rgba(148, 163, 184, 0.22);
    }}
    body {{
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(245, 158, 11, 0.24), transparent 32%),
        radial-gradient(circle at top right, rgba(14, 165, 233, 0.22), transparent 28%),
        linear-gradient(180deg, #020617 0%, #0f172a 42%, #111827 100%);
    }}
    main {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 32px 20px 48px;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: clamp(2.2rem, 5vw, 3.6rem);
      letter-spacing: 0.02em;
    }}
    .eyebrow {{
      color: var(--accent);
      text-transform: uppercase;
      letter-spacing: 0.18em;
      font-size: 0.78rem;
      margin-bottom: 10px;
    }}
    .hero {{
      display: grid;
      gap: 18px;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      margin: 22px 0 26px;
    }}
    .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 22px;
      padding: 18px;
      box-shadow: 0 20px 40px rgba(2, 6, 23, 0.25);
    }}
    .panel h2 {{
      margin-top: 0;
    }}
    .stat {{
      display: inline-block;
      margin-right: 18px;
      color: var(--muted);
    }}
    .cards {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 16px;
    }}
    .ticker-card {{
      background: var(--panel-soft);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 16px;
    }}
    .ticker-card h3 {{
      margin: 8px 0 10px;
      font-size: 1.45rem;
    }}
    .ticker-card a {{
      color: #fff;
      text-decoration: none;
    }}
    .ticker-meta {{
      color: var(--accent);
      font-size: 0.82rem;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}
    .muted {{
      color: var(--muted);
    }}
  </style>
</head>
<body>
  <main>
    <div class="eyebrow">Research Batch Overview</div>
    <h1>{escape(batch["title"])}</h1>
    <p class="muted">Requested tickers: {escape(requested_tickers)} | Status: {escape(batch["status"])}</p>
    <section class="hero">
      <article class="panel">
        <h2>Executive Summary</h2>
        <p>{summary}</p>
      </article>
      <article class="panel">
        <h2>Snapshot</h2>
        <p><span class="stat"><strong>Top ticker:</strong> {top_ticker}</span></p>
        <p><span class="stat"><strong>Top risk:</strong> {top_risk_text}</span></p>
        <p><span class="stat"><strong>Items:</strong> {len(items)}</span></p>
      </article>
    </section>
    <section class="panel">
      <h2>Tickers</h2>
      <div class="cards">
        {''.join(cards) if cards else '<p class="muted">No ticker items found.</p>'}
      </div>
    </section>
  </main>
</body>
</html>
"""


def _render_ticker_detail_html(snapshot: dict) -> str:
    """Render ticker detail page for a batch item."""
    if not snapshot.get("items"):
        raise KeyError("ticker item missing")
    item = snapshot["items"][0]
    batch = snapshot["batch"]
    report = item.get("report") or {}
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{escape(item['symbol'])} Detail</title>
  <style>
    :root {{
      --bg: #08101f;
      --panel: rgba(8, 15, 31, 0.88);
      --panel-soft: rgba(15, 23, 42, 0.94);
      --ink: #e5eefb;
      --muted: #9fb0c8;
      --accent: #7dd3fc;
      --line: rgba(125, 211, 252, 0.16);
    }}
    body {{
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      color: var(--ink);
      background: radial-gradient(circle at top right, rgba(125, 211, 252, 0.18), transparent 30%), linear-gradient(180deg, #020617 0%, #0b1120 100%);
    }}
    main {{
      max-width: 960px;
      margin: 0 auto;
      padding: 32px 20px 48px;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: clamp(2.1rem, 5vw, 3.3rem);
    }}
    .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 22px;
      padding: 18px;
      box-shadow: 0 20px 40px rgba(2, 6, 23, 0.24);
      margin-top: 16px;
    }}
    .eyebrow {{
      color: var(--accent);
      text-transform: uppercase;
      letter-spacing: 0.18em;
      font-size: 0.78rem;
      margin-bottom: 10px;
    }}
    .muted {{
      color: var(--muted);
    }}
    .grid {{
      display: grid;
      gap: 16px;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    }}
    .metric {{
      background: var(--panel-soft);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 16px;
    }}
    .metric h2 {{
      margin-top: 0;
    }}
  </style>
</head>
<body>
  <main>
    <div class="eyebrow">Ticker Detail</div>
    <h1>{escape(item['symbol'])}</h1>
    <p class="muted">{escape(batch['title'])} | Rank {escape(str(item['display_rank']))} | {escape(item['overall_rating'])}</p>
    <section class="grid">
      <article class="metric">
        <h2>Bottom Line</h2>
        <p>{escape(report.get('bottom_line', ''))}</p>
      </article>
      <article class="metric">
        <h2>Risk Watch</h2>
        <p>{escape(report.get('risk_watch', ''))}</p>
      </article>
    </section>
    <section class="panel">
      <h2>Research Notes</h2>
      <p><strong>Why It Matters:</strong> {escape(report.get('why_it_matters', ''))}</p>
      <p><strong>Action Plan:</strong> {escape(report.get('action_plan', ''))}</p>
      <p><strong>Bull Case:</strong> {escape(report.get('bull_case', ''))}</p>
      <p><strong>Top Thesis:</strong> {escape(item['top_thesis'])}</p>
      <p><strong>Top Risk:</strong> {escape(item['top_risk'])}</p>
      <p><strong>Holding Horizon:</strong> {escape(item['holding_horizon'])}</p>
    </section>
  </main>
</body>
</html>
"""


def render_dashboard_html(snapshot: dict) -> str:
    """Render a single-page minimal dashboard."""
    if snapshot.get("mode") == "batch":
        return _render_batch_overview_html(snapshot)

    signal_table = _render_table(
        "Legacy Signals",
        snapshot.get("signals", []),
        ["symbol", "grade", "priority_score", "confidence"],
    )
    canonical_signal_table = _render_table(
        "Canonical Signals",
        snapshot.get("canonical_signals", []),
        ["ticker", "rating", "priority_score", "confidence"],
    )
    canonical_report_table = _render_table(
        "Canonical Reports",
        snapshot.get("canonical_reports", []),
        ["ticker", "title", "bottom_line"],
    )
    position_table = _render_table(
        "Open Positions",
        snapshot.get("positions", []),
        ["symbol", "status", "quantity", "entry_price"],
    )
    paper_table = _render_table(
        "Paper Trades",
        snapshot.get("paper_trades", []),
        ["symbol", "status", "quantity", "entry_price"],
    )
    alert_table = _render_table(
        "Alerts",
        snapshot.get("alerts", []),
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
      {canonical_signal_table}
      {canonical_report_table}
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
            path = urlparse(self.path).path.rstrip("/")

            if path.startswith("/ticker/"):
                try:
                    item_id = int(path.split("/")[-1])
                    snapshot = _fetch_batch_item_snapshot(database, item_id)
                    if snapshot is None:
                        html = b"<html><body><h1>Not Found</h1></body></html>"
                        self.send_response(404)
                    else:
                        html = _render_ticker_detail_html(snapshot).encode("utf-8")
                        self.send_response(200)
                except (ValueError, IndexError):
                    html = b"<html><body><h1>Invalid ticker ID</h1></body></html>"
                    self.send_response(400)
                content_type = "text/html; charset=utf-8"

            elif path == "/batches/latest":
                snapshot = _fetch_latest_batch(database)
                if snapshot is None:
                    html = b"<html><body><h1>No batches found</h1></body></html>"
                    self.send_response(404)
                else:
                    html = render_dashboard_html(snapshot).encode("utf-8")
                    self.send_response(200)
                content_type = "text/html; charset=utf-8"

            else:
                snapshot = build_viewer_snapshot(database)
                html = render_dashboard_html(snapshot).encode("utf-8")
                self.send_response(200)
                content_type = "text/html; charset=utf-8"

            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)

        def log_message(self, format: str, *args) -> None:  # noqa: A003
            return

    return ThreadingHTTPServer((host, port), _ViewerHandler)
