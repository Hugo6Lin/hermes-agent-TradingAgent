# P45 Futu Market Data Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only Futu/OpenD market-data readiness gate so Hermes can prove whether live market data is usable before relying on P36/P37/P39/P42 evidence.

**Architecture:** Create a focused `market_data_readiness.py` module that performs SDK, OpenD TCP, and optional live quote checks, writes P45 artifacts, and persists append-only readiness reports. Extend `ResearchDatabase` with a P45 table and expose a local `market-data-readiness-run` CLI. Tests use fake providers by default; live Futu checks are opt-in only via `HERMES_LIVE_FUTU=1`.

**Tech Stack:** Python 3.11, dataclasses/typing protocols, pathlib, socket, importlib.metadata, hashlib, json, sqlite3, argparse, pytest, existing `FutuQuoteClient`, optional live Futu OpenD.

---

## File Structure

- Create `agent/research_v1/market_data_readiness.py`
  - SDK/OpenD/live-readiness checks, report builder, artifact writer, runtime entrypoint.
- Modify `agent/research_v1/data/database.py`
  - Add `market_data_readiness_reports` schema and save/list helpers.
- Modify `agent/research_v1/batch_cli.py`
  - Add `market-data-readiness-run`.
- Create `tests/agent/research_v1/test_market_data_readiness.py`
  - Focused unit/runtime/persistence tests with fake providers.
- Create `tests/agent/research_v1/test_futu_live_smoke.py`
  - Opt-in live tests skipped unless `HERMES_LIVE_FUTU=1`.
- Modify `tests/agent/research_v1/test_batch_cli.py`
  - CLI tests for success, invalid input, provider unavailable.
- Modify `README.md`
  - Add P45 overview and commands.
- Modify `agent/research_v1/README.md`
  - Add P45 data flow.
- Modify `agent/research_v1/data/README.md`
  - Document Futu/OpenD readiness and operator setup.

Expected commits:

1. `feat: add futu market data readiness`
2. `feat: persist market data readiness reports`
3. `feat: add market data readiness cli`
4. `docs: document p45 market data readiness`

---

## Task 1: P45-A Core Readiness Module

**Files:**
- Create: `agent/research_v1/market_data_readiness.py`
- Test: `tests/agent/research_v1/test_market_data_readiness.py`

- [ ] **Step 1: Create focused failing tests for static checks**

Add to `tests/agent/research_v1/test_market_data_readiness.py`:

```python
"""Tests for P45 Futu market-data readiness."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent.research_v1.market_data_readiness import (
    P45_SCHEMA_VERSION,
    build_market_data_readiness_report,
    write_market_data_readiness_artifacts,
)


class FakeProvider:
    data_source = "fake_futu"

    def __init__(self, *, snapshot=None, history=None, options=None, fail_option=False):
        self.snapshot = snapshot if snapshot is not None else [{"code": "US.AAPL", "last_price": 200.0}]
        self.history = history if history is not None else {
            "US.AAPL": [{"date": "2026-04-29", "open": 199.0, "close": 200.0, "high": 201.0, "low": 198.0}],
            "HK.00700": [{"date": "2026-04-29", "open": 400.0, "close": 405.0, "high": 408.0, "low": 399.0}],
        }
        self.options = options if options is not None else [{"code": "US.AAPL260117C200000", "strike_price": 200.0}]
        self.fail_option = fail_option

    def fetch_snapshot(self, symbols):
        return list(self.snapshot)

    def fetch_history(self, symbol, start_date, end_date):
        return list(self.history.get(symbol, []))

    def fetch_option_chain(self, symbol, start=None, end=None):
        if self.fail_option:
            raise RuntimeError("permission denied for option chain")
        return list(self.options)


def test_sdk_missing_returns_unavailable_with_install_guidance(tmp_path: Path):
    report = build_market_data_readiness_report(
        as_of_date="2026-04-30",
        host="127.0.0.1",
        port=11111,
        symbols=["US.AAPL"],
        history_days=30,
        option_symbol="US.AAPL",
        live=True,
        sdk_result={"status": "not_installed", "module": "futu", "version": ""},
        opend_result={"status": "not_tested", "reachable": False},
        provider=None,
    )

    assert report["schema_version"] == P45_SCHEMA_VERSION
    assert report["status"] == "provider_unavailable"
    assert "install_futu_api_sdk" in report["recommended_actions"]


def test_live_false_returns_not_tested_live(tmp_path: Path):
    report = build_market_data_readiness_report(
        as_of_date="2026-04-30",
        host="127.0.0.1",
        port=11111,
        symbols=["US.AAPL"],
        history_days=30,
        option_symbol="US.AAPL",
        live=False,
        sdk_result={"status": "passed", "module": "futu", "version": "10.4.6408"},
        opend_result={"status": "passed", "reachable": True},
        provider=FakeProvider(),
    )

    assert report["status"] == "provider_not_tested_live"
    assert any(c["status"] == "not_tested_live" for c in report["checks"])


def test_fake_provider_success_returns_provider_ready(tmp_path: Path):
    report = build_market_data_readiness_report(
        as_of_date="2026-04-30",
        host="127.0.0.1",
        port=11111,
        symbols=["US.AAPL", "HK.00700"],
        history_days=30,
        option_symbol="US.AAPL",
        live=True,
        sdk_result={"status": "passed", "module": "futu", "version": "10.4.6408"},
        opend_result={"status": "passed", "reachable": True},
        provider=FakeProvider(),
    )

    assert report["status"] == "provider_ready"
    assert report["snapshot_summary"]["row_count"] == 1
    assert report["history_summary"]["US.AAPL"]["row_count"] == 1
    assert report["option_chain_summary"]["row_count"] == 1


def test_option_permission_failure_degrades_not_unavailable(tmp_path: Path):
    report = build_market_data_readiness_report(
        as_of_date="2026-04-30",
        host="127.0.0.1",
        port=11111,
        symbols=["US.AAPL"],
        history_days=30,
        option_symbol="US.AAPL",
        live=True,
        sdk_result={"status": "passed", "module": "futu", "version": "10.4.6408"},
        opend_result={"status": "passed", "reachable": True},
        provider=FakeProvider(fail_option=True),
    )

    assert report["status"] == "provider_degraded"
    assert "option_chain_permission_limited" in report["recommended_actions"]


def test_source_hash_changes_when_check_result_changes(tmp_path: Path):
    base = dict(
        as_of_date="2026-04-30",
        host="127.0.0.1",
        port=11111,
        symbols=["US.AAPL"],
        history_days=30,
        option_symbol="US.AAPL",
        live=True,
        sdk_result={"status": "passed", "module": "futu", "version": "10.4.6408"},
        opend_result={"status": "passed", "reachable": True},
    )
    first = build_market_data_readiness_report(provider=FakeProvider(), **base)
    second = build_market_data_readiness_report(provider=FakeProvider(snapshot=[{"code": "US.AAPL", "last_price": 201.0}]), **base)

    assert first["source_hash"] != second["source_hash"]


def test_writer_emits_json_and_markdown(tmp_path: Path):
    report = build_market_data_readiness_report(
        as_of_date="2026-04-30",
        host="127.0.0.1",
        port=11111,
        symbols=["US.AAPL"],
        history_days=30,
        option_symbol="US.AAPL",
        live=False,
        sdk_result={"status": "passed", "module": "futu", "version": "10.4.6408"},
        opend_result={"status": "passed", "reachable": True},
        provider=FakeProvider(),
    )

    paths = write_market_data_readiness_artifacts(report, tmp_path / "output" / "governance" / "2026-04-30")

    assert paths["json"].name == "p45_market_data_readiness.json"
    assert paths["md"].name == "p45_market_data_readiness.md"
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert payload["schema_version"] == P45_SCHEMA_VERSION
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_market_data_readiness.py -q
```

Expected: import failure for `agent.research_v1.market_data_readiness`.

- [ ] **Step 3: Implement `market_data_readiness.py`**

Create `agent/research_v1/market_data_readiness.py` with:

```python
"""P45 Futu market-data provider readiness."""

from __future__ import annotations

import hashlib
import importlib
import json
import socket
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Protocol

P45_SCHEMA_VERSION = "p45_market_data_readiness.1"
MIN_FUTU_API_VERSION = "10.4.6408"

P45_STATUS_READY = "provider_ready"
P45_STATUS_DEGRADED = "provider_degraded"
P45_STATUS_UNAVAILABLE = "provider_unavailable"
P45_STATUS_NOT_TESTED_LIVE = "provider_not_tested_live"
P45_STATUS_BLOCKED_INVALID_INPUT = "blocked_invalid_input"

P45_DISCLAIMER = (
    "P45 is market-data provider readiness only. It does not recommend trades, "
    "submit orders, unlock trading, query positions, approve production adoption, "
    "train models, schedule jobs, or mutate research decisions."
)

FORBIDDEN_RENDER_TERMS = (
    "buy this now",
    "sell this now",
    "follow this trade",
    "guaranteed edge",
    "production approved",
    "model promoted",
    "execute trade",
    "place order",
)

ALLOWED_PREFIXES = ("US.", "HK.", "SH.", "SZ.", "SG.")


class ReadinessProvider(Protocol):
    data_source: str

    def fetch_snapshot(self, symbols: list[str]) -> list[dict]: ...

    def fetch_history(self, symbol: str, start_date: str, end_date: str) -> list[dict]: ...

    def fetch_option_chain(self, symbol: str, start: str | None = None, end: str | None = None) -> list[dict]: ...


def _sha(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _parse_version(value: str) -> tuple[int, ...]:
    try:
        return tuple(int(part) for part in str(value).split("."))
    except ValueError:
        return (0,)


def validate_inputs(*, as_of_date: str, host: str, port: int, symbols: list[str], history_days: int, option_symbol: str | None) -> list[str]:
    errors: list[str] = []
    try:
        _parse_date(as_of_date)
    except (ValueError, TypeError):
        errors.append("invalid_date_format")
    if not host or not str(host).strip():
        errors.append("invalid_host")
    if not isinstance(port, int) or port <= 0 or port > 65535:
        errors.append("invalid_port")
    if history_days <= 0:
        errors.append("history_days_must_be_positive")
    if not symbols:
        errors.append("symbols_required")
    for symbol in symbols:
        if not any(str(symbol).upper().startswith(prefix) for prefix in ALLOWED_PREFIXES):
            errors.append(f"invalid_symbol:{symbol}")
    if option_symbol and not any(str(option_symbol).upper().startswith(prefix) for prefix in ALLOWED_PREFIXES):
        errors.append(f"invalid_option_symbol:{option_symbol}")
    return errors


def check_futu_sdk() -> dict[str, Any]:
    started = time.monotonic()
    try:
        module = importlib.import_module("futu")
    except Exception as exc:
        return {
            "check_id": "sdk_import",
            "status": "not_installed",
            "severity": "critical",
            "details": {"module": "futu", "error": exc.__class__.__name__},
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "duration_ms": int((time.monotonic() - started) * 1000),
        }
    version = str(getattr(module, "__version__", "0"))
    status = "passed" if _parse_version(version) >= _parse_version(MIN_FUTU_API_VERSION) else "degraded"
    return {
        "check_id": "sdk_version",
        "status": status,
        "severity": "info" if status == "passed" else "warning",
        "details": {"module": "futu", "version": version, "minimum": MIN_FUTU_API_VERSION},
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "duration_ms": int((time.monotonic() - started) * 1000),
    }


def check_opend_tcp(host: str, port: int, timeout: float = 2.0) -> dict[str, Any]:
    started = time.monotonic()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            reachable = True
    except OSError as exc:
        return {
            "check_id": "opend_tcp",
            "status": "not_reachable",
            "severity": "critical",
            "details": {"host": host, "port": port, "error": exc.__class__.__name__},
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "duration_ms": int((time.monotonic() - started) * 1000),
        }
    return {
        "check_id": "opend_tcp",
        "status": "passed",
        "severity": "info",
        "details": {"host": host, "port": port, "reachable": reachable},
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "duration_ms": int((time.monotonic() - started) * 1000),
    }


def _check_row_has(row: dict[str, Any], keys: tuple[str, ...]) -> bool:
    return all(row.get(key) is not None for key in keys)


def _check_snapshot(provider: ReadinessProvider, symbols: list[str]) -> tuple[dict[str, Any], dict[str, Any]]:
    started = time.monotonic()
    try:
        rows = provider.fetch_snapshot(symbols)
    except Exception as exc:
        return _failed_check("snapshot", exc, started), {"row_count": 0, "returned_codes": []}
    returned_codes = [str(row.get("code", "")) for row in rows if row.get("code")]
    valid = bool(rows) and all(row.get("code") for row in rows)
    status = "passed" if valid else "failed"
    return {
        "check_id": "snapshot",
        "status": status,
        "severity": "info" if valid else "critical",
        "details": {"row_count": len(rows), "returned_codes": returned_codes},
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "duration_ms": int((time.monotonic() - started) * 1000),
    }, {"row_count": len(rows), "returned_codes": returned_codes}


def _check_history(provider: ReadinessProvider, symbols: list[str], start_date: str, end_date: str) -> tuple[dict[str, Any], dict[str, Any]]:
    started = time.monotonic()
    summary: dict[str, Any] = {}
    failures: list[str] = []
    for symbol in symbols:
        try:
            rows = provider.fetch_history(symbol, start_date, end_date)
        except Exception as exc:
            failures.append(f"{symbol}:{exc.__class__.__name__}")
            summary[symbol] = {"row_count": 0, "status": "failed"}
            continue
        valid = bool(rows) and all(_check_row_has(row, ("date", "close")) for row in rows)
        summary[symbol] = {"row_count": len(rows), "status": "passed" if valid else "failed"}
        if not valid:
            failures.append(symbol)
    passed = not failures and bool(summary)
    return {
        "check_id": "history_kline",
        "status": "passed" if passed else "failed",
        "severity": "info" if passed else "critical",
        "details": {"failures": failures, "symbols": symbols},
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "duration_ms": int((time.monotonic() - started) * 1000),
    }, summary


def _check_options(provider: ReadinessProvider, option_symbol: str | None) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    started = time.monotonic()
    if not option_symbol:
        return {
            "check_id": "option_chain",
            "status": "skipped",
            "severity": "info",
            "details": {"reason": "option_symbol_empty"},
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "duration_ms": int((time.monotonic() - started) * 1000),
        }, {"row_count": 0, "status": "skipped"}, []
    try:
        rows = provider.fetch_option_chain(option_symbol)
    except Exception as exc:
        return {
            "check_id": "option_chain",
            "status": "permission_limited",
            "severity": "warning",
            "details": {"symbol": option_symbol, "error": exc.__class__.__name__},
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "duration_ms": int((time.monotonic() - started) * 1000),
        }, {"row_count": 0, "status": "permission_limited"}, ["option_chain_permission_limited"]
    valid = bool(rows)
    return {
        "check_id": "option_chain",
        "status": "passed" if valid else "degraded",
        "severity": "info" if valid else "warning",
        "details": {"symbol": option_symbol, "row_count": len(rows)},
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "duration_ms": int((time.monotonic() - started) * 1000),
    }, {"row_count": len(rows), "status": "passed" if valid else "degraded"}, []


def _failed_check(check_id: str, exc: Exception, started: float) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "status": "failed",
        "severity": "critical",
        "details": {"error": exc.__class__.__name__},
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "duration_ms": int((time.monotonic() - started) * 1000),
    }


def build_market_data_readiness_report(
    *,
    as_of_date: str,
    host: str,
    port: int,
    symbols: list[str],
    history_days: int,
    option_symbol: str | None,
    live: bool,
    sdk_result: dict[str, Any],
    opend_result: dict[str, Any],
    provider: ReadinessProvider | None,
) -> dict[str, Any]:
    checks = [sdk_result, opend_result]
    recommended_actions: list[str] = []
    snapshot_summary: dict[str, Any] = {"row_count": 0, "returned_codes": []}
    history_summary: dict[str, Any] = {}
    option_chain_summary: dict[str, Any] = {"row_count": 0, "status": "skipped"}

    if sdk_result.get("status") == "not_installed":
        recommended_actions.append("install_futu_api_sdk")
    if opend_result.get("status") == "not_reachable":
        recommended_actions.append("start_futu_opend_gui")

    if not live:
        checks.append({
            "check_id": "live_quote_calls",
            "status": "not_tested_live",
            "severity": "info",
            "details": {"reason": "live_flag_false"},
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "duration_ms": 0,
        })
        status = P45_STATUS_NOT_TESTED_LIVE
    elif sdk_result.get("status") in {"not_installed"} or opend_result.get("status") == "not_reachable":
        status = P45_STATUS_UNAVAILABLE
    elif provider is None:
        checks.append({
            "check_id": "provider",
            "status": "failed",
            "severity": "critical",
            "details": {"reason": "provider_unavailable"},
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "duration_ms": 0,
        })
        status = P45_STATUS_UNAVAILABLE
    else:
        start_date = (_parse_date(as_of_date) - timedelta(days=history_days)).isoformat()
        snapshot_check, snapshot_summary = _check_snapshot(provider, symbols)
        history_check, history_summary = _check_history(provider, symbols, start_date, as_of_date)
        option_check, option_chain_summary, option_actions = _check_options(provider, option_symbol)
        checks.extend([snapshot_check, history_check, option_check, {
            "check_id": "no_trade_context_used",
            "status": "passed",
            "severity": "info",
            "details": {"trade_contexts": []},
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "duration_ms": 0,
        }])
        recommended_actions.extend(option_actions)
        critical_failed = any(c["severity"] == "critical" and c["status"] not in {"passed"} for c in checks)
        degraded = any(c["status"] in {"degraded", "permission_limited"} for c in checks)
        if critical_failed:
            status = P45_STATUS_UNAVAILABLE
        elif degraded:
            status = P45_STATUS_DEGRADED
        else:
            status = P45_STATUS_READY

    seed = {
        "schema_version": P45_SCHEMA_VERSION,
        "as_of_date": as_of_date,
        "host": host,
        "port": port,
        "symbols": symbols,
        "history_days": history_days,
        "option_symbol": option_symbol or "",
        "live": live,
        "checks": [
            {
                "check_id": c.get("check_id"),
                "status": c.get("status"),
                "severity": c.get("severity"),
                "details": c.get("details", {}),
            }
            for c in checks
        ],
        "snapshot_summary": snapshot_summary,
        "history_summary": history_summary,
        "option_chain_summary": option_chain_summary,
    }
    source_hash = _sha(seed)
    report_id = hashlib.sha256(f"{as_of_date}|{host}|{port}|{source_hash}".encode("utf-8")).hexdigest()[:16]
    return {
        "schema_version": P45_SCHEMA_VERSION,
        "report_id": report_id,
        "as_of_date": as_of_date,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "host": host,
        "port": port,
        "symbols": symbols,
        "history_days": history_days,
        "option_symbol": option_symbol or "",
        "live": live,
        "sdk": sdk_result,
        "opend": opend_result,
        "checks": checks,
        "snapshot_summary": snapshot_summary,
        "history_summary": history_summary,
        "option_chain_summary": option_chain_summary,
        "permission_summary": {"permission_limited": [c for c in checks if c.get("status") == "permission_limited"]},
        "recommended_actions": sorted(set(recommended_actions)),
        "source_hash": source_hash,
        "disclaimer": P45_DISCLAIMER,
    }


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# P45 Market Data Readiness",
        "",
        f"As of: `{report.get('as_of_date', '')}`",
        f"Status: `{report.get('status', '')}`",
        f"OpenD: `{report.get('host')}:{report.get('port')}`",
        "",
        "## Checks",
        "",
        "| Check | Status | Severity | Details |",
        "|-------|--------|----------|---------|",
    ]
    for check in report.get("checks", []):
        details = json.dumps(check.get("details", {}), sort_keys=True)
        lines.append(f"| {check.get('check_id')} | {check.get('status')} | {check.get('severity')} | `{details}` |")
    lines.extend(["", "## Recommended Actions", ""])
    actions = report.get("recommended_actions", [])
    if actions:
        for action in actions:
            lines.append(f"- {action}")
    else:
        lines.append("- none")
    lines.extend(["", "---", "", f"> {report.get('disclaimer', P45_DISCLAIMER)}", ""])
    text = "\n".join(lines)
    lowered = text.lower()
    for term in FORBIDDEN_RENDER_TERMS:
        if term in lowered:
            raise ValueError(f"forbidden market data readiness term rendered: {term}")
    return text


def write_market_data_readiness_artifacts(report: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "p45_market_data_readiness.json"
    md_path = output_dir / "p45_market_data_readiness.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_markdown(report), encoding="utf-8")
    return {"json": json_path, "md": md_path}
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_market_data_readiness.py -q
```

Expected: tests added in Step 1 pass.

- [ ] **Step 5: Commit P45-A**

```bash
git add agent/research_v1/market_data_readiness.py tests/agent/research_v1/test_market_data_readiness.py
git commit -m "feat: add futu market data readiness"
```

---

## Task 2: P45-A Runtime Validation And Default Provider

**Files:**
- Modify: `agent/research_v1/market_data_readiness.py`
- Test: `tests/agent/research_v1/test_market_data_readiness.py`

- [ ] **Step 1: Add runtime and boundary tests**

Append:

```python
from agent.research_v1.market_data_readiness import run_market_data_readiness


def test_runtime_rejects_invalid_date(tmp_path: Path):
    result = run_market_data_readiness(
        output_root=tmp_path / "out",
        as_of_date="not-a-date",
        host="127.0.0.1",
        port=11111,
        symbols=["US.AAPL"],
        history_days=30,
        live=False,
        provider=FakeProvider(),
    )

    assert result["status"] == "blocked_invalid_input"
    assert "invalid_date_format" in result["warnings"]


def test_runtime_rejects_unprefixed_symbol(tmp_path: Path):
    result = run_market_data_readiness(
        output_root=tmp_path / "out",
        as_of_date="2026-04-30",
        host="127.0.0.1",
        port=11111,
        symbols=["AAPL"],
        history_days=30,
        live=False,
        provider=FakeProvider(),
    )

    assert result["status"] == "blocked_invalid_input"
    assert "invalid_symbol:AAPL" in result["warnings"]


def test_runtime_writes_artifacts(tmp_path: Path):
    result = run_market_data_readiness(
        output_root=tmp_path / "output" / "governance",
        as_of_date="2026-04-30",
        host="127.0.0.1",
        port=11111,
        symbols=["US.AAPL"],
        history_days=30,
        option_symbol="US.AAPL",
        live=True,
        sdk_check=lambda: {"check_id": "sdk_version", "status": "passed", "severity": "info", "details": {"version": "10.4.6408"}, "observed_at": "x", "duration_ms": 0},
        opend_check=lambda host, port: {"check_id": "opend_tcp", "status": "passed", "severity": "info", "details": {"reachable": True}, "observed_at": "x", "duration_ms": 0},
        provider=FakeProvider(),
    )

    assert result["status"] == "provider_ready"
    assert Path(result["output_dir"]).joinpath("p45_market_data_readiness.json").exists()
    assert Path(result["output_dir"]).joinpath("p45_market_data_readiness.md").exists()


def test_hard_boundaries_are_explicit():
    import agent.research_v1.market_data_readiness as p45

    forbidden_names = {
        "OpenSecTradeContext", "OpenFutureTradeContext", "unlock_trade",
        "place_order", "modify_order", "cancel_order", "HermesResearchApp",
        "final_judge", "CanonicalSignal", "CanonicalReport",
        "run_recommendation_outcome_tracking", "run_market_regime_context",
        "run_candidate_pool", "run_boss_copilot_daily_brief",
    }
    assert not (forbidden_names & set(p45.__dict__))
    assert "market-data provider readiness only" in p45.P45_DISCLAIMER
```

- [ ] **Step 2: Implement runtime and default provider**

Append to `market_data_readiness.py`:

```python
class FutuReadinessProvider:
    """Read-only Futu quote provider for P45."""

    data_source = "futu_opend"

    def __init__(self, host: str, port: int):
        from agent.research_v1.data.futu_opend import FutuOpenDConfig, FutuQuoteClient

        self._client = FutuQuoteClient(config=FutuOpenDConfig(host=host, port=port, default_market="US"))

    def fetch_snapshot(self, symbols: list[str]) -> list[dict]:
        return self._client.fetch_snapshot(symbols)

    def fetch_history(self, symbol: str, start_date: str, end_date: str) -> list[dict]:
        return self._client.fetch_history(symbol, start_date, end_date)

    def fetch_option_chain(self, symbol: str, start: str | None = None, end: str | None = None) -> list[dict]:
        return self._client.fetch_option_chain(symbol, start=start, end=end)


def run_market_data_readiness(
    *,
    output_root: Path,
    as_of_date: str,
    host: str = "127.0.0.1",
    port: int = 11111,
    symbols: list[str] | None = None,
    history_days: int = 30,
    option_symbol: str | None = "US.AAPL",
    live: bool = False,
    provider: ReadinessProvider | None = None,
    sdk_check=check_futu_sdk,
    opend_check=check_opend_tcp,
) -> dict[str, Any]:
    symbols = symbols or ["US.AAPL", "HK.00700"]
    errors = validate_inputs(
        as_of_date=as_of_date,
        host=host,
        port=port,
        symbols=symbols,
        history_days=history_days,
        option_symbol=option_symbol,
    )
    if errors:
        return {"status": P45_STATUS_BLOCKED_INVALID_INPUT, "warnings": errors}

    sdk_result = sdk_check()
    opend_result = opend_check(host, port)
    active_provider = provider
    if live and active_provider is None and sdk_result.get("status") not in {"not_installed"} and opend_result.get("status") != "not_reachable":
        active_provider = FutuReadinessProvider(host, port)

    report = build_market_data_readiness_report(
        as_of_date=as_of_date,
        host=host,
        port=port,
        symbols=symbols,
        history_days=history_days,
        option_symbol=option_symbol,
        live=live,
        sdk_result=sdk_result,
        opend_result=opend_result,
        provider=active_provider,
    )
    output_dir = Path(output_root) / as_of_date
    paths = write_market_data_readiness_artifacts(report, output_dir)
    return {
        "status": report["status"],
        "output_dir": str(output_dir),
        "report_id": report["report_id"],
        "source_hash": report["source_hash"],
        "recommended_actions": report["recommended_actions"],
        "paths": paths,
    }
```

- [ ] **Step 3: Run focused tests**

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_market_data_readiness.py -q
```

Expected: all P45-A tests pass.

- [ ] **Step 4: Commit runtime additions**

Amend the P45-A commit if still local and clean, or create:

```bash
git add agent/research_v1/market_data_readiness.py tests/agent/research_v1/test_market_data_readiness.py
git commit -m "feat: add futu market data readiness runtime"
```

If following the four-commit split strictly, squash this into `feat: add futu market data readiness`.

---

## Task 3: P45-B Persistence

**Files:**
- Modify: `agent/research_v1/data/database.py`
- Test: `tests/agent/research_v1/test_market_data_readiness.py`

- [ ] **Step 1: Add persistence tests**

Append:

```python
from agent.research_v1.data.database import ResearchDatabase


def _db(tmp_path: Path) -> ResearchDatabase:
    db = ResearchDatabase(str(tmp_path / "research.db"))
    db.initialize()
    return db


def _ready_report() -> dict:
    return build_market_data_readiness_report(
        as_of_date="2026-04-30",
        host="127.0.0.1",
        port=11111,
        symbols=["US.AAPL"],
        history_days=30,
        option_symbol="US.AAPL",
        live=True,
        sdk_result={"check_id": "sdk_version", "status": "passed", "severity": "info", "details": {"version": "10.4.6408"}, "observed_at": "x", "duration_ms": 0},
        opend_result={"check_id": "opend_tcp", "status": "passed", "severity": "info", "details": {"reachable": True}, "observed_at": "x", "duration_ms": 0},
        provider=FakeProvider(),
    )


def test_market_data_readiness_persistence_is_idempotent(tmp_path: Path):
    db = _db(tmp_path)
    report = _ready_report()

    first = db.save_market_data_readiness_report(report)
    second = db.save_market_data_readiness_report(report)
    rows = db.list_market_data_readiness_reports(as_of_date="2026-04-30")

    assert first == second
    assert len(rows) == 1


def test_market_data_readiness_revised_hash_appends(tmp_path: Path):
    db = _db(tmp_path)
    first = _ready_report()
    second = dict(first)
    second["source_hash"] = "revised-hash"
    second["report_id"] = "revised-report"

    db.save_market_data_readiness_report(first)
    db.save_market_data_readiness_report(second)
    rows = db.list_market_data_readiness_reports(as_of_date="2026-04-30")

    assert len(rows) == 2
```

- [ ] **Step 2: Implement database helpers**

In `agent/research_v1/data/database.py`, add methods near other P4x helpers:

```python
    # ── P45 Market Data Readiness ───────────────────────────────────────

    def initialize_market_data_readiness_schema(self) -> None:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS market_data_readiness_reports (
                report_id TEXT PRIMARY KEY,
                schema_version TEXT NOT NULL,
                as_of_date TEXT NOT NULL,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL,
                host TEXT NOT NULL,
                port INTEGER NOT NULL,
                symbols_json TEXT NOT NULL,
                history_days INTEGER NOT NULL,
                option_symbol TEXT NOT NULL,
                live INTEGER NOT NULL,
                source_hash TEXT NOT NULL,
                report_json TEXT NOT NULL,
                UNIQUE(as_of_date, host, port, symbols_json, history_days, option_symbol, live, source_hash)
            )
        """)
        conn.commit()
        conn.close()

    def save_market_data_readiness_report(self, report: dict) -> str:
        self.initialize_market_data_readiness_schema()
        symbols_json = json.dumps(report.get("symbols", []), sort_keys=True)
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT OR IGNORE INTO market_data_readiness_reports (
                report_id, schema_version, as_of_date, created_at, status,
                host, port, symbols_json, history_days, option_symbol, live,
                source_hash, report_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                report["report_id"],
                report["schema_version"],
                report["as_of_date"],
                report.get("created_at", ""),
                report.get("status", ""),
                report.get("host", ""),
                int(report.get("port", 0)),
                symbols_json,
                int(report.get("history_days", 0)),
                report.get("option_symbol", ""),
                1 if report.get("live") else 0,
                report["source_hash"],
                json.dumps(report, sort_keys=True, default=str),
            ),
        )
        conn.commit()
        conn.close()
        return report["report_id"]

    def list_market_data_readiness_reports(self, as_of_date: str | None = None, limit: int = 20) -> list[dict]:
        self.initialize_market_data_readiness_schema()
        conn = self._get_connection()
        cursor = conn.cursor()
        if as_of_date:
            cursor.execute(
                """SELECT * FROM market_data_readiness_reports
                   WHERE as_of_date = ?
                   ORDER BY created_at DESC, report_id ASC
                   LIMIT ?""",
                (as_of_date, limit),
            )
        else:
            cursor.execute(
                """SELECT * FROM market_data_readiness_reports
                   ORDER BY as_of_date DESC, created_at DESC, report_id ASC
                   LIMIT ?""",
                (limit,),
            )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
```

- [ ] **Step 3: Persist from runtime**

Modify `run_market_data_readiness()` to accept optional `db` and save when provided:

```python
def run_market_data_readiness(..., db: Any | None = None, ...):
    ...
    if db is not None:
        db.save_market_data_readiness_report(report)
```

Update runtime test to pass `db=_db(tmp_path)` and assert one row exists.

- [ ] **Step 4: Run persistence tests**

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_market_data_readiness.py -q
```

Expected: P45 focused tests pass.

- [ ] **Step 5: Commit P45-B**

```bash
git add agent/research_v1/data/database.py agent/research_v1/market_data_readiness.py tests/agent/research_v1/test_market_data_readiness.py
git commit -m "feat: persist market data readiness reports"
```

---

## Task 4: P45-C CLI

**Files:**
- Modify: `agent/research_v1/batch_cli.py`
- Modify: `tests/agent/research_v1/test_batch_cli.py`

- [ ] **Step 1: Add CLI tests**

Append to `tests/agent/research_v1/test_batch_cli.py`:

```python
def test_market_data_readiness_cli_success(monkeypatch, tmp_path, capsys):
    from agent.research_v1 import batch_cli as app

    app_root = tmp_path
    (app_root / "data").mkdir()

    def fake_run(**kwargs):
        return {
            "status": "provider_not_tested_live",
            "output_dir": str(app_root / "output" / "governance" / "2026-04-30"),
            "report_id": "r1",
            "source_hash": "h1",
            "recommended_actions": [],
            "paths": {},
        }

    monkeypatch.setattr("agent.research_v1.batch_cli.run_market_data_readiness", fake_run)
    code = app.main(["--app-root", str(app_root), "market-data-readiness-run", "--as-of-date", "2026-04-30"])

    assert code == 0
    assert "Market data readiness status: provider_not_tested_live" in capsys.readouterr().out


def test_market_data_readiness_cli_rejects_invalid_date(tmp_path, capsys):
    from agent.research_v1 import batch_cli as app

    code = app.main(["--app-root", str(tmp_path), "market-data-readiness-run", "--as-of-date", "not-a-date"])

    assert code == 2
    assert "invalid market-data-readiness-run input" in capsys.readouterr().out


def test_market_data_readiness_cli_provider_unavailable_returns_3(monkeypatch, tmp_path, capsys):
    from agent.research_v1 import batch_cli as app

    def fake_run(**kwargs):
        return {
            "status": "provider_unavailable",
            "output_dir": str(tmp_path / "output"),
            "report_id": "r1",
            "source_hash": "h1",
            "recommended_actions": ["install_futu_api_sdk"],
            "paths": {},
        }

    monkeypatch.setattr("agent.research_v1.batch_cli.run_market_data_readiness", fake_run)
    code = app.main(["--app-root", str(tmp_path), "market-data-readiness-run", "--as-of-date", "2026-04-30", "--live"])

    assert code == 3
    assert "install_futu_api_sdk" in capsys.readouterr().out
```

- [ ] **Step 2: Wire CLI imports and command**

In `batch_cli.py`, add import:

```python
from agent.research_v1.market_data_readiness import run_market_data_readiness
```

Add command handler:

```python
def _cmd_market_data_readiness_run(
    paths: HermesPaths,
    as_of_date: str,
    symbols: str,
    history_days: int,
    option_symbol: str,
    host: str,
    port: int,
    live: bool,
    output_root: str,
) -> int:
    from datetime import date as _date

    try:
        _date.fromisoformat(as_of_date)
    except (ValueError, TypeError):
        print(f"invalid market-data-readiness-run input: invalid date format '{as_of_date}'")
        return 2
    parsed_symbols = [item.strip().upper() for item in symbols.split(",") if item.strip()]
    if not parsed_symbols:
        print("invalid market-data-readiness-run input: symbols required")
        return 2
    if history_days <= 0:
        print("invalid market-data-readiness-run input: history-days must be positive")
        return 2
    output_path = Path(output_root).expanduser()
    if not output_path.is_absolute():
        output_path = paths.app_root / output_path
    database = _ensure_database(paths)
    result = run_market_data_readiness(
        output_root=output_path.resolve(),
        as_of_date=as_of_date,
        host=host,
        port=port,
        symbols=parsed_symbols,
        history_days=history_days,
        option_symbol=option_symbol.strip().upper() if option_symbol else "",
        live=live,
        db=database,
    )
    if result.get("status") == "blocked_invalid_input":
        print(f"invalid market-data-readiness-run input: {result.get('warnings', ['unknown'])[0]}")
        return 2
    print(f"Market data readiness status: {result['status']}")
    print(f"Output dir: {result['output_dir']}")
    print(f"Report id: {result['report_id']}")
    for action in result.get("recommended_actions", []):
        print(f"Recommended action: {action}")
    return 3 if result.get("status") == "provider_unavailable" else 0
```

Add parser:

```python
    readiness_parser = subparsers.add_parser("market-data-readiness-run", help="Run Futu market-data readiness checks.")
    readiness_parser.add_argument("--as-of-date", required=True, help="As-of date YYYY-MM-DD.")
    readiness_parser.add_argument("--symbols", default="US.AAPL,HK.00700", help="Comma-separated prefixed symbols.")
    readiness_parser.add_argument("--history-days", default=30, type=int, help="History lookback in calendar days.")
    readiness_parser.add_argument("--option-symbol", default="US.AAPL", help="Prefixed option underlying symbol; empty skips option check.")
    readiness_parser.add_argument("--host", default=os.getenv("FUTU_OPEND_HOST", "127.0.0.1"), help="Futu OpenD host.")
    readiness_parser.add_argument("--port", default=int(os.getenv("FUTU_OPEND_PORT", "11111")), type=int, help="Futu OpenD port.")
    readiness_parser.add_argument("--live", action="store_true", help="Opt in to live OpenD quote calls.")
    readiness_parser.add_argument("--output-root", default="output/governance", help="Output root for P45 artifacts.")
```

Add dispatch:

```python
    if args.command == "market-data-readiness-run":
        return _cmd_market_data_readiness_run(
            paths,
            as_of_date=args.as_of_date,
            symbols=args.symbols,
            history_days=args.history_days,
            option_symbol=args.option_symbol,
            host=args.host,
            port=args.port,
            live=args.live,
            output_root=args.output_root,
        )
```

- [ ] **Step 3: Run CLI tests**

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_batch_cli.py -q -k "market_data_readiness or market-data-readiness"
```

Expected: P45 CLI tests pass.

- [ ] **Step 4: Commit P45-C**

```bash
git add agent/research_v1/batch_cli.py tests/agent/research_v1/test_batch_cli.py
git commit -m "feat: add market data readiness cli"
```

---

## Task 5: Optional Live Smoke Test

**Files:**
- Create: `tests/agent/research_v1/test_futu_live_smoke.py`

- [ ] **Step 1: Add skipped-by-default live test**

Create:

```python
"""Opt-in live Futu OpenD smoke tests for P45.

These tests are skipped unless HERMES_LIVE_FUTU=1.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from agent.research_v1.market_data_readiness import run_market_data_readiness


pytestmark = pytest.mark.skipif(
    os.getenv("HERMES_LIVE_FUTU") != "1",
    reason="Set HERMES_LIVE_FUTU=1 to run live Futu OpenD smoke tests.",
)


def test_live_futu_readiness_smoke(tmp_path: Path):
    result = run_market_data_readiness(
        output_root=tmp_path / "output" / "governance",
        as_of_date=os.getenv("HERMES_LIVE_FUTU_AS_OF_DATE", "2026-04-30"),
        host=os.getenv("FUTU_OPEND_HOST", "127.0.0.1"),
        port=int(os.getenv("FUTU_OPEND_PORT", "11111")),
        symbols=os.getenv("HERMES_LIVE_FUTU_SYMBOLS", "US.AAPL,HK.00700").split(","),
        history_days=30,
        option_symbol=os.getenv("HERMES_LIVE_FUTU_OPTION_SYMBOL", "US.AAPL"),
        live=True,
    )

    assert result["status"] in {"provider_ready", "provider_degraded", "provider_unavailable"}
    assert Path(result["output_dir"]).joinpath("p45_market_data_readiness.json").exists()
```

- [ ] **Step 2: Run skipped test**

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_futu_live_smoke.py -q
```

Expected: skipped unless `HERMES_LIVE_FUTU=1`.

- [ ] **Step 3: Do not require live test in CI**

No CI wiring should force `HERMES_LIVE_FUTU=1`.

---

## Task 6: P45-D Documentation

**Files:**
- Modify: `README.md`
- Modify: `agent/research_v1/README.md`
- Modify: `agent/research_v1/data/README.md`

- [ ] **Step 1: Update root README**

Add a P45 section using this Markdown:

~~~markdown
### P45 — Futu Market Data Readiness

P45 adds a read-only Futu/OpenD readiness gate. It checks whether the Hermes Python runtime can import `futu`, whether local OpenD is reachable, and, when `--live` is passed, whether snapshot/history/option-chain quote calls return usable rows. It writes:

```text
output/governance/YYYY-MM-DD/p45_market_data_readiness.json
output/governance/YYYY-MM-DD/p45_market_data_readiness.md
```

Example:

```bash
/opt/homebrew/bin/python3.11 -m agent.research_v1.batch_cli market-data-readiness-run \
  --as-of-date 2026-04-30 \
  --symbols US.AAPL,HK.00700 \
  --history-days 30 \
  --option-symbol US.AAPL \
  --live
```

Futu does not use a normal cloud API key in this path. It requires local Futu OpenD to be installed, running, and logged in, plus the Python package `futu-api`.
~~~

- [ ] **Step 2: Update research README data flow**

Add:

```markdown
P45 sits between evidence monitoring and refresh planning. It does not refresh evidence itself; it reports whether the Futu market-data source is usable for later P36/P37 refreshes.
```

- [ ] **Step 3: Update data README**

Add:

~~~markdown
`market_data_readiness.py` is the P45 operator-facing smoke gate for Futu/OpenD. Unit tests use fake providers. Live checks are opt-in:

```bash
HERMES_LIVE_FUTU=1 /opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_futu_live_smoke.py -q
```

The readiness gate must not import trade contexts or call order APIs.
~~~

- [ ] **Step 4: Run docs tests**

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_doc_standards.py -q
```

Expected: pass.

- [ ] **Step 5: Commit P45-D**

```bash
git add README.md agent/research_v1/README.md agent/research_v1/data/README.md tests/agent/research_v1/test_futu_live_smoke.py
git commit -m "docs: document p45 market data readiness"
```

---

## Final Verification

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_market_data_readiness.py -q
```

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_batch_cli.py -q -k "market_data_readiness or market-data-readiness"
```

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_futu_live_smoke.py -q
```

Expected: skipped unless `HERMES_LIVE_FUTU=1`.

Run:

```bash
/opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_doc_standards.py -q
```

Run P36-P44 focused regression:

```bash
/opt/homebrew/bin/python3.11 -m pytest \
  tests/agent/research_v1/test_recommendation_outcomes.py \
  tests/agent/research_v1/test_market_regime_context.py \
  tests/agent/research_v1/test_fundamental_quality.py \
  tests/agent/research_v1/test_candidate_pool.py \
  tests/agent/research_v1/test_research_memory_pack.py \
  tests/agent/research_v1/test_decision_journal_guardrails.py \
  tests/agent/research_v1/test_boss_copilot_daily_brief.py \
  tests/agent/research_v1/test_copilot_console_index.py \
  tests/agent/research_v1/test_evidence_freshness_drift_monitor.py \
  -q
```

Run governance-adjacent regression:

```bash
/opt/homebrew/bin/python3.11 -m pytest \
  tests/agent/research_v1/test_governance_runtime.py \
  tests/agent/research_v1/test_boss_governance_brief.py \
  tests/agent/research_v1/test_signal_family_edge_review.py \
  -q
```

Optional live smoke, only if operator intentionally enables it:

```bash
HERMES_LIVE_FUTU=1 /opt/homebrew/bin/python3.11 -m pytest tests/agent/research_v1/test_futu_live_smoke.py -q
```

Manual operator command after implementation:

```bash
/opt/homebrew/bin/python3.11 -m agent.research_v1.batch_cli market-data-readiness-run \
  --as-of-date 2026-04-30 \
  --symbols US.AAPL,HK.00700 \
  --history-days 30 \
  --option-symbol US.AAPL \
  --live
```

If this returns `provider_unavailable` with `install_futu_api_sdk`, install:

```bash
/opt/homebrew/bin/python3.11 -m pip install futu-api==10.4.6408
```

Then re-run the manual command.

## Final Report Template

Return:

```text
P45 Implementation Complete

Status Summary
Phase   Status   Commit
P45-A   PASS     <hash> feat: add futu market data readiness
P45-B   PASS     <hash> feat: persist market data readiness reports
P45-C   PASS     <hash> feat: add market data readiness cli
P45-D   PASS     <hash> docs: document p45 market data readiness

Verification
- P45 focused: <N> passed
- P45 CLI: <N> passed
- P45 live smoke: skipped by default / or <status if HERMES_LIVE_FUTU=1>
- P36-P44 regression: <N> passed
- Governance-adjacent regression: <N> passed
- Doc standards: <N> passed
- Full P20-P45 chain: <N> passed, known host gaps listed separately

Futu Local State Observed
- futu-api import: present/missing, version if present
- OpenD TCP: reachable/unreachable at host:port
- Live quote checks: ready/degraded/unavailable/not tested
- Missing setup, if any: <list>

Hard Boundary Compliance
- no auto-trading
- no broker orders
- no production approval
- no production config mutation
- no model training
- no scheduling or notifications
- no viewer/server
- no trade context imports
- no unlock_trade
- no final_judge changes
- no HermesResearchApp.run invocation
- no CanonicalSignal or CanonicalReport creation
- no JudgeInputPacket mutation
- no P36-P44 mutation or runtime invocation
```
