"""Batch PDF export for Hermes research reports."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from agent.research_v1.data.database import ResearchDatabase
from agent.research_v1.viewer import render_dashboard_html


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


def build_batch_export_html(batch_snapshot: dict) -> str:
    """Build the batch overview HTML used as the PDF source."""
    # Restructure flat batch snapshot into the nested form expected by _render_batch_overview_html
    items = batch_snapshot.get("items", [])
    batch_fields = {k: v for k, v in batch_snapshot.items() if k != "items"}
    snapshot = {
        "mode": "batch",
        "batch": batch_fields,
        "items": items,
    }
    return render_dashboard_html(snapshot)


def export_batch_pdf(database: ResearchDatabase, batch_id: int, output_dir: str | Path) -> Path:
    """Export a saved research batch as a real PDF document."""
    snapshot = database.get_research_batch_with_items_and_reports(batch_id)
    if snapshot is None:
        raise KeyError(f"research batch {batch_id} not found")

    output_path = Path(output_dir).expanduser().resolve()
    output_path.mkdir(parents=True, exist_ok=True)
    pdf_path = output_path / f"batch_{batch_id}.pdf"

    html = build_batch_export_html(snapshot)
    edge_executable = _find_edge_executable()

    with tempfile.TemporaryDirectory(dir=str(output_path)) as temp_dir:
        html_path = Path(temp_dir) / f"batch_{batch_id}.html"
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
