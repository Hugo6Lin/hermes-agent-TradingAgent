"""Runtime for P51 boss console."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent.research_v1.boss_console.console_model import build_console_model
from agent.research_v1.boss_console.console_renderer import render_console_html


def run_boss_console(
    governance_root: Path,
    output_dir: Path,
    as_of_date: str | None = None,
    tickers: list[str] | None = None,
) -> dict[str, Any]:
    root = Path(governance_root)
    if not root.exists():
        return {"status": "boss_console_blocked_invalid_input", "warnings": ["governance_root_missing"]}
    if not root.is_dir():
        return {"status": "boss_console_blocked_invalid_input", "warnings": ["governance_root_not_directory"]}
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    model = build_console_model(root, as_of_date=as_of_date, tickers=tickers)
    html = render_console_html(model)
    html_path = out / "boss_console.html"
    json_path = out / "boss_console.json"
    html_path.write_text(html, encoding="utf-8")
    json_path.write_text(json.dumps(model, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "status": "boss_console_ready",
        "html_path": str(html_path),
        "json_path": str(json_path),
        "report_count": len(model.get("reports", [])),
        "warnings": model.get("warnings", []),
    }
