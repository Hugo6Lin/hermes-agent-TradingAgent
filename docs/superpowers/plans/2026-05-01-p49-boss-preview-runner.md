# P49 Boss Preview Runner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a one-command boss preview runner where the boss supplies tickers and Hermes produces a readable preview report plus safe co-pilot artifacts.

**Architecture:** Add `boss_preview_runner.py` as a thin orchestrator over existing read-only/append-only P37-P48 runtimes. It owns input normalization, live/default policy, valid preview sample builders, safe phase execution, boss markdown rendering, and artifact writing; persistence is optional in v1 via the JSON report.

**Tech Stack:** Python standard library, existing `ResearchDatabase`, existing P37-P48 runtime functions, pytest, existing `batch_cli.py` argparse patterns.

---

## File Structure

- Create `agent/research_v1/boss_preview_runner.py`: validation, output-root normalization, sample input builders, safe phase execution, boss report assembly, JSON/Markdown writers.
- Modify `agent/research_v1/batch_cli.py`: add `boss-preview-run`.
- Create `tests/agent/research_v1/test_boss_preview_runner.py`: focused P49 tests.
- Modify `tests/agent/research_v1/test_batch_cli.py`: P49 CLI tests.
- Create `docs/skills/hermes-boss-preview/SKILL.md`: repo-local skill draft for future agents.
- Modify `README.md`: add P49 boss preview command and behavior.
- Modify `agent/research_v1/README.md`: add P49 data-flow note.

## Commit Split

1. `feat: add boss preview runner`
2. `feat: add boss preview sample input builders`
3. `feat: add boss preview cli and skill draft`
4. `docs: document p49 boss preview runner`

## Task 1: P49-A Boss Preview Runner

**Files:**
- Create: `agent/research_v1/boss_preview_runner.py`
- Test: `tests/agent/research_v1/test_boss_preview_runner.py`

- [ ] **Step 1: Write focused runner tests**

Create `tests/agent/research_v1/test_boss_preview_runner.py`:

```python
"""Tests for P49 boss preview runner."""

from __future__ import annotations

from pathlib import Path

from agent.research_v1.boss_preview_runner import (
    normalize_preview_tickers,
    normalize_output_root,
    build_boss_preview_report,
    render_boss_preview_markdown,
    validate_boss_preview_inputs,
)


def test_normalize_preview_tickers_accepts_plain_and_prefixed():
    assert normalize_preview_tickers([" nvda ", "US.AMZN", "NVDA", "HK.00700"]) == ["NVDA", "US.AMZN", "HK.00700"]


def test_validate_rejects_empty_tickers():
    result = validate_boss_preview_inputs([], "2026-05-01", 8, Path("output/governance"))
    assert result["status"] == "boss_preview_blocked_invalid_input"
    assert "empty_ticker_list" in result["warnings"]


def test_normalize_output_root_removes_date_suffix(tmp_path: Path):
    root = tmp_path / "output" / "governance" / "2026-05-01"
    normalized, warnings = normalize_output_root(root, "2026-05-01")
    assert normalized == tmp_path / "output" / "governance"
    assert "normalized_date_suffixed_output_root" in warnings


def test_boss_report_ready_when_live_and_candidate_exist(tmp_path: Path):
    report = build_boss_preview_report(
        as_of_date="2026-05-01",
        tickers=["NVDA"],
        live_requested=True,
        phase_results=[
            {"phase_id": "P45", "status": "provider_ready", "artifact_paths": ["p45.json"], "boss_summary": "Futu ready."},
            {"phase_id": "P39", "status": "completed", "candidate_count": 1, "top_candidate": "NVDA", "artifact_paths": ["p39.json"], "boss_summary": "NVDA ranked first."},
            {"phase_id": "P42", "status": "brief_ready", "artifact_paths": ["p42.json"], "boss_summary": "Brief ready."},
        ],
        warnings=[],
    )
    assert report["status"] == "boss_preview_ready"
    assert report["top_candidates"] == ["NVDA"]


def test_markdown_boss_summary_comes_before_technical_appendix():
    report = build_boss_preview_report(
        as_of_date="2026-05-01",
        tickers=["NVDA"],
        live_requested=True,
        phase_results=[],
        warnings=["sample_data_used"],
    )
    md = render_boss_preview_markdown(report)
    assert md.index("## Plain-English Verdict") < md.index("## Technical Appendix")
    assert "sample_data_used" in md
```

- [ ] **Step 2: Run tests and confirm they fail**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_boss_preview_runner.py -q
```

Expected: import errors for missing P49 module/functions.

- [ ] **Step 3: Implement core runner helpers**

Create `agent/research_v1/boss_preview_runner.py`:

```python
"""P49 one-command boss preview runner."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable

P49_SCHEMA_VERSION = "p49_boss_preview.1"
P49_DISCLAIMER = (
    "P49 is a boss preview runner only. It does not submit orders, approve "
    "production adoption, train models, schedule jobs, call final_judge, or "
    "change research decisions."
)
TICKER_RE = re.compile(r"^(US\\.)?[A-Z0-9._-]{1,20}$|^HK\\.\\d{5}$")
DATE_RE = re.compile(r"^\\d{4}-\\d{2}-\\d{2}$")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_preview_tickers(tickers: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in tickers:
        ticker = str(raw).strip().upper()
        if ticker and ticker not in seen:
            seen.add(ticker)
            out.append(ticker)
    return out


def futu_symbols_for_tickers(tickers: list[str]) -> list[str]:
    symbols = []
    for ticker in normalize_preview_tickers(tickers):
        if ticker.startswith(("US.", "HK.", "SH.", "SZ.", "SG.")):
            symbols.append(ticker)
        elif ticker.isalpha():
            symbols.append(f"US.{ticker}")
    return symbols


def normalize_output_root(output_root: Path, as_of_date: str) -> tuple[Path, list[str]]:
    root = Path(output_root)
    warnings: list[str] = []
    if root.name == as_of_date and DATE_RE.match(root.name):
        root = root.parent
        warnings.append("normalized_date_suffixed_output_root")
    return root, warnings


def validate_boss_preview_inputs(tickers: list[str], as_of_date: str, max_candidates: int, governance_root: Path) -> dict[str, Any]:
    warnings: list[str] = []
    try:
        date.fromisoformat(as_of_date)
    except (TypeError, ValueError):
        warnings.append(f"invalid_as_of_date:{as_of_date}")
    normalized = normalize_preview_tickers(tickers)
    if not normalized:
        warnings.append("empty_ticker_list")
    for ticker in normalized:
        if not TICKER_RE.match(ticker):
            warnings.append(f"invalid_ticker:{ticker}")
    if max_candidates <= 0:
        warnings.append("max_candidates_must_be_positive")
    if governance_root.exists() and not governance_root.is_dir():
        warnings.append("governance_root_not_a_directory")
    if warnings:
        return {"schema_version": P49_SCHEMA_VERSION, "status": "boss_preview_blocked_invalid_input", "tickers": normalized, "warnings": warnings}
    return {"status": "valid", "tickers": normalized, "warnings": []}


def _sha(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


def build_boss_preview_report(as_of_date: str, tickers: list[str], live_requested: bool, phase_results: list[dict[str, Any]], warnings: list[str]) -> dict[str, Any]:
    p45 = next((p for p in phase_results if p.get("phase_id") == "P45"), {})
    p39 = next((p for p in phase_results if p.get("phase_id") == "P39"), {})
    p42 = next((p for p in phase_results if p.get("phase_id") == "P42"), {})
    top = [p39.get("top_candidate")] if p39.get("top_candidate") else []
    ready = p45.get("status") in {"provider_ready", "provider_degraded"} and bool(top) and bool(p42.get("artifact_paths"))
    status = "boss_preview_ready" if ready else "boss_preview_limited"
    seed = {"schema_version": P49_SCHEMA_VERSION, "as_of_date": as_of_date, "tickers": tickers, "live_requested": live_requested, "phase_results": phase_results, "warnings": warnings}
    source_hash = _sha(seed)
    return {
        "schema_version": P49_SCHEMA_VERSION,
        "preview_id": f"p49-{as_of_date}-{source_hash[:12]}",
        "as_of_date": as_of_date,
        "created_at": utc_now_iso(),
        "status": status,
        "tickers": normalize_preview_tickers(tickers),
        "live_requested": live_requested,
        "live_status": p45.get("status", "not_run"),
        "top_candidates": top,
        "boss_summary": "Hermes produced a limited boss preview." if status != "boss_preview_ready" else "Hermes produced a boss preview with live data readiness and candidates.",
        "phase_results": phase_results,
        "data_source_breakdown": _data_source_breakdown(phase_results),
        "missing_or_stale_evidence": [w for w in warnings if "missing" in w or "stale" in w],
        "what_to_inspect_first": _what_to_inspect_first(phase_results),
        "hard_boundary_compliance": _hard_boundary_compliance(),
        "artifact_paths": [path for phase in phase_results for path in phase.get("artifact_paths", [])],
        "warnings": sorted(set(warnings)),
        "source_hash": source_hash,
        "disclaimer": P49_DISCLAIMER,
    }


def _data_source_breakdown(phase_results: list[dict[str, Any]]) -> dict[str, list[str]]:
    out = {"live": [], "database": [], "sample": [], "missing": []}
    for phase in phase_results:
        source = phase.get("data_source", "missing")
        out.setdefault(source, []).append(phase.get("phase_id", "unknown"))
    return out


def _what_to_inspect_first(phase_results: list[dict[str, Any]]) -> list[str]:
    order = ["boss_preview.md", "p42_boss_copilot_daily_brief.md", "p39_candidate_pool.md", "p44_evidence_freshness_drift_monitor.md", "p48_research_context_prompt_pack.md"]
    return order


def _hard_boundary_compliance() -> dict[str, bool]:
    return {
        "no_auto_trading": True,
        "no_broker_orders": True,
        "no_production_approval": True,
        "no_model_training": True,
        "no_scheduler": True,
        "no_final_judge": True,
        "no_hermes_research_app_run": True,
    }


def render_boss_preview_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Hermes Boss Preview",
        "",
        "## Plain-English Verdict",
        "",
        report.get("boss_summary", ""),
        "",
        "## Today's Top Candidates",
    ]
    lines.extend([f"- {ticker}" for ticker in report.get("top_candidates", [])] or ["- No candidate reached preview-ready status."])
    lines.extend(["", "## Market/Data Status", "", f"- Live requested: {report.get('live_requested')}", f"- Live status: {report.get('live_status')}"])
    lines.extend(["", "## What Hermes Produced"])
    for phase in report.get("phase_results", []):
        lines.append(f"- {phase.get('phase_id')}: {phase.get('status')} — {phase.get('boss_summary', '')}")
    lines.extend(["", "## Live vs Sample vs Missing"])
    for key, phases in report.get("data_source_breakdown", {}).items():
        lines.append(f"- {key}: {', '.join(phases) if phases else 'none'}")
    lines.extend(["", "## What The Boss Should Inspect First"])
    lines.extend([f"- {item}" for item in report.get("what_to_inspect_first", [])])
    lines.extend(["", "## Hard Boundary Compliance"])
    for key, ok in report.get("hard_boundary_compliance", {}).items():
        lines.append(f"- {key}: {'yes' if ok else 'no'}")
    lines.extend(["", "## Artifact Links"])
    lines.extend([f"- {path}" for path in report.get("artifact_paths", [])] or ["- none"])
    lines.extend(["", "## Technical Appendix"])
    lines.extend([f"- warning: {w}" for w in report.get("warnings", [])] or ["- no warnings"])
    lines.extend(["", "## Disclaimer", "", report.get("disclaimer", P49_DISCLAIMER), ""])
    return "\\n".join(lines)


def write_boss_preview_report(report: dict[str, Any], output_root: Path) -> dict[str, Path]:
    output_dir = Path(output_root) / report["as_of_date"]
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "boss_preview.json"
    md_path = output_dir / "boss_preview.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True, default=str) + "\\n", encoding="utf-8")
    md_path.write_text(render_boss_preview_markdown(report), encoding="utf-8")
    return {"json": json_path, "md": md_path}
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_boss_preview_runner.py -q
```

Expected: P49-A tests pass.

- [ ] **Step 5: Commit P49-A**

```bash
git add agent/research_v1/boss_preview_runner.py tests/agent/research_v1/test_boss_preview_runner.py
git commit -m "feat: add boss preview runner"
```

## Task 2: P49-B Sample Builders And Runtime

**Files:**
- Modify: `agent/research_v1/boss_preview_runner.py`
- Test: `tests/agent/research_v1/test_boss_preview_runner.py`

- [ ] **Step 1: Add sample-builder tests**

Append:

```python
from agent.research_v1.boss_preview_runner import (
    build_preview_fundamental_input,
    build_preview_candidate_input,
    run_boss_preview,
)
from agent.research_v1.data.database import ResearchDatabase


def test_preview_fundamental_input_has_required_rows():
    payload = build_preview_fundamental_input(["NVDA"], "2026-05-01")
    assert payload["_preview_sample"] is True
    assert len(payload["tickers"][0]["rows"]) == 5
    assert "shares_outstanding" in payload["tickers"][0]["rows"][-1]


def test_preview_candidate_input_has_required_fields():
    payload = build_preview_candidate_input(["NVDA"], "2026-05-01")
    row = payload["tickers"][0]
    for key in ("close", "close_20d_ago", "high_252d", "avg_dollar_volume_20d", "realized_vol_20d"):
        assert key in row


def test_run_boss_preview_writes_boss_report_with_fake_phase_runners(tmp_path: Path):
    db = ResearchDatabase(str(tmp_path / "test.db"))
    db.initialize()
    result = run_boss_preview(
        db=db,
        tickers=["NVDA"],
        as_of_date="2026-05-01",
        output_root=tmp_path / "output" / "governance",
        governance_root=tmp_path / "output" / "governance",
        live=False,
        max_candidates=3,
        phase_runners={
            "P45": lambda **kw: {"status": "provider_not_tested_live", "paths": {}, "warnings": []},
            "P37": lambda **kw: {"status": "completed", "paths": {}, "warnings": []},
            "P38": lambda **kw: {"status": "completed", "paths": {}, "warnings": []},
            "P39": lambda **kw: {"status": "completed", "top_candidate": "NVDA", "candidate_count": 1, "paths": {}, "warnings": []},
            "P42": lambda **kw: {"status": "brief_ready", "paths": {"md": tmp_path / "p42.md"}, "warnings": []},
        },
    )
    assert result["status"] in {"boss_preview_ready", "boss_preview_limited"}
    assert (tmp_path / "output" / "governance" / "2026-05-01" / "boss_preview.md").exists()
```

- [ ] **Step 2: Add sample builders**

Append to `boss_preview_runner.py`:

```python
def build_preview_fundamental_input(tickers: list[str], as_of_date: str) -> dict[str, Any]:
    rows = []
    base_year = int(as_of_date[:4]) - 1
    periods = [f"{base_year}-03-31", f"{base_year}-06-30", f"{base_year}-09-30", f"{base_year}-12-31", as_of_date]
    for i, period in enumerate(periods):
        revenue = 100.0 + i * 12.0
        rows.append({
            "period_end": period,
            "filing_date": period,
            "source_date": period,
            "revenue": revenue,
            "gross_profit": revenue * 0.52,
            "operating_income": revenue * 0.25,
            "net_income": revenue * 0.20,
            "cfo": revenue * 0.24,
            "capex": -revenue * 0.04,
            "free_cash_flow": revenue * 0.20,
            "total_debt": revenue * 0.30,
            "cash_and_equivalents": revenue * 0.25,
            "shareholders_equity": revenue * 0.80,
            "shares_outstanding": 1000.0,
            "eps": 2.0 + i * 0.2,
            "ebit": revenue * 0.26,
            "current_assets": revenue * 0.60,
            "current_liabilities": revenue * 0.30,
        })
    return {
        "_preview_sample": True,
        "sample_reason": "No verified fundamentals source was provided for boss preview.",
        "as_of_date": as_of_date,
        "tickers": [
            {"ticker": t.replace("US.", ""), "sector": "technology", "currency": "USD", "rows": rows}
            for t in normalize_preview_tickers(tickers)
        ],
    }


def build_preview_candidate_input(tickers: list[str], as_of_date: str) -> dict[str, Any]:
    rows = []
    for i, ticker in enumerate(normalize_preview_tickers(tickers)):
        close = 100.0 + i * 15.0
        rows.append({
            "ticker": ticker.replace("US.", ""),
            "sector": "technology",
            "currency": "USD",
            "source_date": as_of_date,
            "close": close,
            "close_20d_ago": close * 0.95,
            "close_60d_ago": close * 0.88,
            "close_120d_ago": close * 0.82,
            "high_252d": close * 1.10,
            "low_252d": close * 0.65,
            "avg_dollar_volume_20d": 1_000_000_000.0,
            "realized_vol_20d": 0.28,
            "market_cap": 100_000_000_000.0,
            "benchmark_return_60d": 0.04,
            "catalyst_tags": ["boss_preview_sample"],
        })
    return {"_preview_sample": True, "sample_reason": "Preview candidate features generated for boss demo.", "as_of_date": as_of_date, "source": "p49_preview_sample", "universe_id": "boss_preview", "tickers": rows}


def build_preview_decision_input(ticker: str, as_of_date: str) -> dict[str, Any]:
    return {
        "_preview_sample": True,
        "as_of_date": as_of_date,
        "decisions": [{
            "ticker": ticker,
            "contemplated_action": "Watchlist",
            "decision_intent": "research_review",
            "stated_reason": "Boss preview sample decision for guardrail demonstration.",
            "confidence": 0.55,
            "position_context": {"portfolio_weight_pct": 0.0, "sector_weight_pct": 0.0},
        }],
    }
```

- [ ] **Step 3: Implement safe phase runner**

Add:

```python
def _paths_from_result(result: dict[str, Any]) -> list[str]:
    paths = result.get("paths") or {}
    if isinstance(paths, dict):
        return [str(p) for p in paths.values()]
    return [str(p) for p in result.get("artifact_paths", [])]


def _phase_result(phase_id: str, result: dict[str, Any], data_source: str, boss_summary: str) -> dict[str, Any]:
    return {
        "phase_id": phase_id,
        "status": result.get("status", "unknown"),
        "data_source": data_source,
        "artifact_paths": _paths_from_result(result),
        "warnings": result.get("warnings", []),
        "candidate_count": result.get("candidate_count", 0),
        "top_candidate": result.get("top_candidate", ""),
        "boss_summary": boss_summary,
    }


def _safe_call(phase_id: str, fn: Callable[..., dict[str, Any]], data_source: str, boss_summary: str, **kwargs) -> dict[str, Any]:
    try:
        return _phase_result(phase_id, fn(**kwargs), data_source, boss_summary)
    except Exception as exc:
        return {
            "phase_id": phase_id,
            "status": "phase_failed",
            "data_source": data_source,
            "artifact_paths": [],
            "warnings": [f"{phase_id}_failed:{exc.__class__.__name__}"],
            "candidate_count": 0,
            "top_candidate": "",
            "boss_summary": f"{phase_id} could not complete; preview continued safely.",
        }
```

- [ ] **Step 4: Implement `run_boss_preview`**

Add imports inside the function to avoid hard dependencies during tests:

```python
def run_boss_preview(db: Any, tickers: list[str], as_of_date: str, output_root: Path, governance_root: Path, live: bool = True, max_candidates: int = 8, provider: Any | None = None, phase_runners: dict[str, Callable[..., dict[str, Any]]] | None = None) -> dict[str, Any]:
    output_root, root_warnings = normalize_output_root(Path(output_root), as_of_date)
    validation = validate_boss_preview_inputs(tickers, as_of_date, max_candidates, Path(governance_root))
    if validation["status"] != "valid":
        return validation
    normalized = validation["tickers"]
    output_dir = output_root / as_of_date
    output_dir.mkdir(parents=True, exist_ok=True)
    warnings = list(root_warnings)

    if phase_runners is None:
        from agent.research_v1.market_data_readiness import run_market_data_readiness
        from agent.research_v1.market_regime_context import run_market_regime_context
        from agent.research_v1.fundamental_quality import run_fundamental_quality
        from agent.research_v1.candidate_pool import run_candidate_pool
        from agent.research_v1.research_memory_pack import run_research_memory_pack
        from agent.research_v1.decision_journal_guardrails import run_decision_journal_guardrails
        from agent.research_v1.boss_copilot_daily_brief import run_boss_copilot_daily_brief
        from agent.research_v1.copilot_console_index import run_copilot_console_index
        from agent.research_v1.evidence_freshness_drift_monitor import run_evidence_freshness_drift_monitor
        from agent.research_v1.evidence_refresh_planner import run_evidence_refresh_planner
        from agent.research_v1.research_context_pack import run_research_context_pack
        from agent.research_v1.research_context_prompt_pack import run_research_context_prompt_pack
        phase_runners = {
            "P45": run_market_data_readiness,
            "P37": run_market_regime_context,
            "P38": run_fundamental_quality,
            "P39": run_candidate_pool,
            "P40": run_research_memory_pack,
            "P41": run_decision_journal_guardrails,
            "P42": run_boss_copilot_daily_brief,
            "P43": run_copilot_console_index,
            "P44": run_evidence_freshness_drift_monitor,
            "P46": run_evidence_refresh_planner,
            "P47": run_research_context_pack,
            "P48": run_research_context_prompt_pack,
        }

    p38_input = build_preview_fundamental_input(normalized, as_of_date)
    p39_input = build_preview_candidate_input(normalized, as_of_date)
    first_ticker = normalized[0]
    p41_input = build_preview_decision_input(first_ticker.replace("US.", ""), as_of_date)
    (output_dir / "p49_preview_fundamentals_input.json").write_text(json.dumps(p38_input, indent=2, sort_keys=True) + "\\n", encoding="utf-8")
    (output_dir / "p49_preview_candidate_input.json").write_text(json.dumps(p39_input, indent=2, sort_keys=True) + "\\n", encoding="utf-8")
    (output_dir / "p49_preview_decision_input.json").write_text(json.dumps(p41_input, indent=2, sort_keys=True) + "\\n", encoding="utf-8")
    warnings.append("preview_sample_inputs_used")

    phase_results = []
    p45_symbols = futu_symbols_for_tickers(normalized)
    option_symbol = next((s for s in p45_symbols if s.startswith("US.")), "US.AAPL")
    phase_results.append(_safe_call("P45", phase_runners["P45"], "live" if live else "environment", "Checked Futu market-data readiness.", output_root=output_root, as_of_date=as_of_date, symbols=p45_symbols, option_symbol=option_symbol, live=live, provider=provider))
    phase_results.append(_safe_call("P37", phase_runners["P37"], "live" if live else "provider", "Attempted market-regime snapshot.", db=db, as_of_date=date.fromisoformat(as_of_date), output_root=output_root, provider=provider))
    phase_results.append(_safe_call("P38", phase_runners["P38"], "sample", "Scored preview sample fundamentals.", db=db, input_payload=p38_input, as_of_date=as_of_date, output_root=output_root))
    phase_results.append(_safe_call("P39", phase_runners["P39"], "sample", "Ranked preview candidate pool.", db=db, input_payload=p39_input, as_of_date=as_of_date, output_root=output_root, max_candidates=max_candidates))
    phase_results.append(_safe_call("P40", phase_runners["P40"], "database", "Collected prior research memory.", db=db, tickers=[t.replace("US.", "") for t in normalized[:2]], as_of_date=as_of_date, output_root=output_root))
    phase_results.append(_safe_call("P41", phase_runners["P41"], "sample", "Ran preview decision guardrails.", db=db, input_payload=p41_input, as_of_date=as_of_date, output_root=output_root))
    phase_results.append(_safe_call("P42", phase_runners["P42"], "database", "Built boss co-pilot brief.", db=db, as_of_date=as_of_date, output_root=output_root, max_priorities=max_candidates))
    phase_results.append(_safe_call("P43", phase_runners["P43"], "filesystem", "Indexed preview artifacts.", governance_root=output_root, output_root=output_root, as_of_date=as_of_date, lookback_days=14))
    phase_results.append(_safe_call("P44", phase_runners["P44"], "filesystem", "Monitored evidence freshness.", db=db, governance_root=output_root, output_root=output_root, as_of_date=as_of_date, lookback_days=14))
    phase_results.append(_safe_call("P46", phase_runners["P46"], "database", "Planned next evidence refreshes.", db=db, governance_root=output_root, output_root=output_root, as_of_date=as_of_date, lookback_days=14, max_items=12))
    phase_results.append(_safe_call("P47", phase_runners["P47"], "database", "Prepared research context pack.", db=db, governance_root=output_root, output_root=output_root, as_of_date=as_of_date, tickers=normalized[:2], lookback_days=180, max_items_per_ticker=8))
    phase_results.append(_safe_call("P48", phase_runners["P48"], "database", "Prepared prompt dry-run pack.", db=db, governance_root=output_root, output_root=output_root, as_of_date=as_of_date, tickers=normalized[:2], roles=["fundamentals", "risk", "technical"], max_block_chars=1200))

    for phase in phase_results:
        warnings.extend(phase.get("warnings", []))
    report = build_boss_preview_report(as_of_date, normalized, live, phase_results, warnings)
    paths = write_boss_preview_report(report, output_root)
    report["artifact_paths"].extend([str(paths["json"]), str(paths["md"])])
    return report
```

- [ ] **Step 5: Run focused tests**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_boss_preview_runner.py -q
```

Expected: focused tests pass.

- [ ] **Step 6: Commit P49-B**

```bash
git add agent/research_v1/boss_preview_runner.py tests/agent/research_v1/test_boss_preview_runner.py
git commit -m "feat: add boss preview sample input builders"
```

## Task 3: P49-C CLI And Skill Draft

**Files:**
- Modify: `agent/research_v1/batch_cli.py`
- Modify: `tests/agent/research_v1/test_batch_cli.py`
- Create: `docs/skills/hermes-boss-preview/SKILL.md`

- [ ] **Step 1: Add CLI tests**

Add to `tests/agent/research_v1/test_batch_cli.py`:

```python
def test_boss_preview_run_cli_success(monkeypatch, tmp_path, capsys):
    from agent.research_v1.batch_cli import main
    (tmp_path / "data").mkdir()
    captured = {}

    def fake_run(**kwargs):
        captured.update(kwargs)
        return {
            "status": "boss_preview_limited",
            "preview_id": "p49-2026-05-01-abc",
            "tickers": ["NVDA", "AMZN"],
            "top_candidates": ["NVDA"],
            "warnings": [],
            "artifact_paths": [str(tmp_path / "output" / "governance" / "2026-05-01" / "boss_preview.md")],
        }

    monkeypatch.setattr("agent.research_v1.batch_cli.run_boss_preview", fake_run)
    code = main(["--app-root", str(tmp_path), "boss-preview-run", "--tickers", "NVDA,AMZN", "--as-of-date", "2026-05-01"])
    assert code == 0
    assert captured["live"] is True
    assert captured["tickers"] == ["NVDA", "AMZN"]
    assert "Boss preview status: boss_preview_limited" in capsys.readouterr().out


def test_boss_preview_run_cli_supports_no_live(monkeypatch, tmp_path, capsys):
    from agent.research_v1.batch_cli import main
    (tmp_path / "data").mkdir()
    captured = {}

    def fake_run(**kwargs):
        captured.update(kwargs)
        return {"status": "boss_preview_limited", "preview_id": "p49", "tickers": ["NVDA"], "top_candidates": [], "warnings": [], "artifact_paths": []}

    monkeypatch.setattr("agent.research_v1.batch_cli.run_boss_preview", fake_run)
    code = main(["--app-root", str(tmp_path), "boss-preview-run", "--tickers", "NVDA", "--as-of-date", "2026-05-01", "--no-live"])
    assert code == 0
    assert captured["live"] is False
```

- [ ] **Step 2: Wire CLI**

Import `run_boss_preview`. Add parser:

```python
preview_parser = subparsers.add_parser("boss-preview-run", help="Run one-command boss preview from tickers.")
preview_parser.add_argument("--tickers", required=True, help="Comma-separated ticker symbols.")
preview_parser.add_argument("--as-of-date", default=None, help="Preview date YYYY-MM-DD; default today.")
preview_parser.add_argument("--output-root", default="output/governance", help="Governance output root.")
preview_parser.add_argument("--governance-root", default="output/governance", help="Governance artifact root.")
preview_parser.add_argument("--live", dest="live", action="store_true", default=True, help="Enable live Futu readiness by default.")
preview_parser.add_argument("--no-live", dest="live", action="store_false", help="Disable live Futu calls.")
preview_parser.add_argument("--max-candidates", default=8, type=int, help="Maximum preview candidates.")
```

Dispatch:

```python
if args.command == "boss-preview-run":
    as_of_date = args.as_of_date or date.today().isoformat()
    output_path = Path(args.output_root).expanduser()
    if not output_path.is_absolute():
        output_path = paths.app_root / output_path
    governance_path = Path(args.governance_root).expanduser()
    if not governance_path.is_absolute():
        governance_path = paths.app_root / governance_path
    result = run_boss_preview(
        db=_ensure_database(paths),
        tickers=[t.strip() for t in args.tickers.split(",") if t.strip()],
        as_of_date=as_of_date,
        output_root=output_path.resolve(),
        governance_root=governance_path.resolve(),
        live=args.live,
        max_candidates=args.max_candidates,
    )
    if result.get("status") == "boss_preview_blocked_invalid_input":
        print(f"invalid boss-preview-run input: {result.get('warnings', ['unknown'])[0]}")
        return 2
    print(f"Boss preview status: {result['status']}")
    print(f"Preview id: {result['preview_id']}")
    print(f"Tickers: {', '.join(result['tickers'])}")
    print(f"Top candidates: {', '.join(result.get('top_candidates', [])) or 'none'}")
    for path in result.get("artifact_paths", []):
        if str(path).endswith("boss_preview.md"):
            print(f"Boss report: {path}")
    return 0
```

- [ ] **Step 3: Add repo-local skill draft**

Create `docs/skills/hermes-boss-preview/SKILL.md`:

```markdown
---
name: hermes-boss-preview
description: Use when the boss gives tickers and wants a Hermes V1 preview. Run the one-command boss preview runner instead of manually chaining governance commands.
---

# Hermes Boss Preview

When the boss gives tickers, use:

```bash
/opt/homebrew/bin/python3.11 -m agent.research_v1.batch_cli boss-preview-run \
  --tickers NVDA,AMZN,MSFT \
  --output-root output/governance
```

Rules:

- Use live Futu readiness by default.
- Use `--no-live` only when the boss explicitly asks for offline preview.
- Pass `--output-root output/governance`, not a date-suffixed directory.
- Read `output/governance/YYYY-MM-DD/boss_preview.md` first.
- Explain live vs sample vs missing evidence before technical details.
- Do not place trades, submit orders, call `HermesResearchApp.run()`, call `final_judge`, train models, schedule jobs, or mutate production config.
```

- [ ] **Step 4: Run CLI tests**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_batch_cli.py -q -k "boss_preview or boss-preview"
```

Expected: P49 CLI tests pass.

- [ ] **Step 5: Commit P49-C**

```bash
git add agent/research_v1/batch_cli.py tests/agent/research_v1/test_batch_cli.py docs/skills/hermes-boss-preview/SKILL.md
git commit -m "feat: add boss preview cli and skill draft"
```

## Task 4: P49-D Docs And Regression

**Files:**
- Modify: `README.md`
- Modify: `agent/research_v1/README.md`

- [ ] **Step 1: Update docs**

Add:

````markdown
### P49 Boss Preview Runner

P49 is the one-command boss preview. The boss only supplies tickers:

```bash
/opt/homebrew/bin/python3.11 -m agent.research_v1.batch_cli boss-preview-run \
  --tickers AMZN,ALAB,NVDA,ORCL,QCOM,SOFI \
  --output-root output/governance
```

The runner enables live Futu readiness by default, normalizes date-suffixed output roots, creates valid preview sample inputs when verified fundamentals are unavailable, runs safe P37-P48 preview phases, and writes:

```text
output/governance/YYYY-MM-DD/boss_preview.md
output/governance/YYYY-MM-DD/boss_preview.json
```

The preview is not a trade instruction and does not call `HermesResearchApp.run()`, `final_judge`, broker/order APIs, model training, scheduling, or notifications.
````

- [ ] **Step 2: Run verification**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_boss_preview_runner.py -q
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_batch_cli.py -q -k "boss_preview or boss-preview"
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_market_data_readiness.py tests/agent/research_v1/test_research_context_pack.py tests/agent/research_v1/test_research_context_prompt_pack.py -q
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_doc_standards.py -q
```

Expected: P49 focused, CLI, P45/P47/P48 regressions, and doc standards pass.

- [ ] **Step 3: Commit P49-D**

```bash
git add README.md agent/research_v1/README.md
git commit -m "docs: document p49 boss preview runner"
```

## Final Report Template

```text
P49 Implementation Complete

Status Summary
Phase   Status   Commit
P49-A   PASS     <commit> feat: add boss preview runner
P49-B   PASS     <commit> feat: add boss preview sample input builders
P49-C   PASS     <commit> feat: add boss preview cli and skill draft
P49-D   PASS     <commit> docs: document p49 boss preview runner

Verification
- P49 focused: <N> passed
- P49 CLI: <N> passed
- P45/P47/P48 regression: <N> passed
- Doc standards: <N> passed
- Full relevant chain: <N> passed, known host-specific gaps listed separately

Preview Behavior
- Boss input required: tickers only
- Live Futu readiness default: enabled
- Output root double-date guard: enabled
- Valid preview sample input generation: enabled
- Boss report path: output/governance/YYYY-MM-DD/boss_preview.md

Hard Boundary Compliance
- no auto-trading
- no broker orders
- no production approval
- no production config mutation
- no model training
- no scheduling or notifications
- no dynamic viewer/server
- no HermesResearchApp.run invocation
- no final_judge invocation
- no SubagentExecutor invocation
- no LLM calls
- no CanonicalSignal or CanonicalReport creation
- no JudgeInputPacket mutation
- no live SubagentTask mutation
```
