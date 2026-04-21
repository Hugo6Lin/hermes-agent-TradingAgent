"""Argparse-based CLI entrypoint for the Hermes research app."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from agent.research_v1.data.database import ResearchDatabase
from agent.research_v1.data.futu_opend import FutuQuoteClient
from agent.research_v1.paths import HermesPaths
from agent.research_v1.report_pdf_legacy import export_batch_pdf
from agent.research_v1.research_batch_service import save_batch_research
from agent.research_v1.viewer import serve_viewer


def _load_paths(root: str | Path | None = None) -> HermesPaths:
    return HermesPaths.from_root(Path.cwd() if root is None else root)


def _ensure_database(paths: HermesPaths) -> ResearchDatabase:
    paths.ensure_directories()
    database = ResearchDatabase(str(paths.database_path))
    database.initialize()
    return database


def _cmd_init(paths: HermesPaths) -> int:
    _ensure_database(paths)
    print(f"Initialized Hermes research app at {paths.app_root}")
    print(f"Database ready at {paths.database_path}")
    return 0


def _cmd_status(paths: HermesPaths) -> int:
    database_exists = paths.database_path.exists()
    print("Hermes research app status")
    print(f"App root: {paths.app_root}")
    print(f"Data dir: {paths.data_dir} ({'ready' if paths.data_dir.exists() else 'missing'})")
    print(f"Reports dir: {paths.reports_dir} ({'ready' if paths.reports_dir.exists() else 'missing'})")
    print(f"Exports dir: {paths.exports_dir} ({'ready' if paths.exports_dir.exists() else 'missing'})")
    print(f"Database: {paths.database_path} ({'ready' if database_exists else 'missing'})")
    return 0


def _cmd_ingest(paths: HermesPaths, input_path: str) -> int:
    database = _ensure_database(paths)
    payload_path = Path(input_path).expanduser().resolve()
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    result = save_batch_research(database, payload)

    print(f"Ingested batch {result['batch_id']} from {payload_path}")
    print(f"Saved {len(result['item_ids'])} items and {len(result['report_ids'])} reports")
    return 0


def _cmd_viewer(paths: HermesPaths, host: str, port: int) -> int:
    database = _ensure_database(paths)
    server = serve_viewer(database, host=host, port=port)
    print(f"Serving Hermes viewer on http://{host}:{port}")
    try:
        server.serve_forever()
    finally:
        server.server_close()
    return 0


def _cmd_export_pdf(paths: HermesPaths, batch_id: int) -> int:
    database = _ensure_database(paths)
    pdf_path = export_batch_pdf(database, batch_id=batch_id, output_dir=paths.exports_dir)
    print(f"Exported batch {batch_id} PDF to {pdf_path}")
    return 0


def _cmd_quote(symbols: str) -> int:
    client = FutuQuoteClient()
    rows = client.fetch_snapshot([symbol.strip() for symbol in symbols.split(",") if symbol.strip()])
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    return 0


def _cmd_option_chain(symbol: str, start: str | None, end: str | None) -> int:
    client = FutuQuoteClient()
    rows = client.fetch_option_chain(symbol=symbol, start=start, end=end)
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hermes-research")
    parser.add_argument(
        "--app-root",
        default=None,
        help="Override the local Hermes app root directory.",
    )
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("init", help="Create the local Hermes data layout and database.")
    subparsers.add_parser("status", help="Show whether the local Hermes data layout exists.")

    ingest_parser = subparsers.add_parser("ingest", help="Ingest a batch research payload.")
    ingest_parser.add_argument("--input", required=True, help="Path to a JSON batch payload.")

    viewer_parser = subparsers.add_parser("viewer", help="Start the local Hermes viewer.")
    viewer_parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind.")
    viewer_parser.add_argument("--port", default=8008, type=int, help="Port to bind.")

    export_parser = subparsers.add_parser("export-pdf", help="Export a batch report as PDF.")
    export_parser.add_argument("--batch-id", required=True, type=int, help="Batch id to export.")

    quote_parser = subparsers.add_parser("quote", help="Query Futu OpenD market snapshot.")
    quote_parser.add_argument("--symbols", required=True, help="Comma-separated symbols, e.g. AAPL,HK.00700.")

    option_parser = subparsers.add_parser("option-chain", help="Query Futu OpenD option chain.")
    option_parser.add_argument("--symbol", required=True, help="Underlying symbol, e.g. GLW or US.GLD.")
    option_parser.add_argument("--start", default=None, help="Start expiration date YYYY-MM-DD.")
    option_parser.add_argument("--end", default=None, help="End expiration date YYYY-MM-DD.")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    paths = _load_paths(args.app_root)

    if args.command == "init":
        return _cmd_init(paths)
    if args.command == "status":
        return _cmd_status(paths)
    if args.command == "ingest":
        return _cmd_ingest(paths, args.input)
    if args.command == "viewer":
        return _cmd_viewer(paths, args.host, args.port)
    if args.command == "export-pdf":
        return _cmd_export_pdf(paths, args.batch_id)
    if args.command == "quote":
        return _cmd_quote(args.symbols)
    if args.command == "option-chain":
        return _cmd_option_chain(args.symbol, args.start, args.end)

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
