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


def validate_inputs(
    *,
    as_of_date: str,
    host: str,
    port: int,
    symbols: list[str],
    history_days: int,
    option_symbol: str | None,
) -> list[str]:
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


def _check_history(
    provider: ReadinessProvider, symbols: list[str], start_date: str, end_date: str
) -> tuple[dict[str, Any], dict[str, Any]]:
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
        valid = bool(rows) and all(row.get("date") is not None and row.get("close") is not None for row in rows)
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


def _check_options(
    provider: ReadinessProvider, option_symbol: str | None
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
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


def _check_forbidden(text: str) -> None:
    lowered = text.lower()
    for term in FORBIDDEN_RENDER_TERMS:
        if term in lowered:
            raise ValueError(f"forbidden market data readiness term rendered: {term}")


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
    _check_forbidden(text)
    return text


def write_market_data_readiness_artifacts(report: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "p45_market_data_readiness.json"
    md_path = output_dir / "p45_market_data_readiness.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_markdown(report), encoding="utf-8")
    return {"json": json_path, "md": md_path}


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
    sdk_check: Any = check_futu_sdk,
    opend_check: Any = check_opend_tcp,
    db: Any | None = None,
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
    if db is not None:
        db.save_market_data_readiness_report(report)
    return {
        "status": report["status"],
        "output_dir": str(output_dir),
        "report_id": report["report_id"],
        "source_hash": report["source_hash"],
        "recommended_actions": report["recommended_actions"],
        "paths": paths,
    }
