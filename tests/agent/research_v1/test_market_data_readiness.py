"""Tests for P45 Futu market-data readiness."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent.research_v1.market_data_readiness import (
    P45_DISCLAIMER,
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
        sdk_result={"check_id": "sdk_import", "status": "not_installed", "severity": "critical", "module": "futu", "version": ""},
        opend_result={"check_id": "opend_tcp", "status": "not_tested", "severity": "info", "reachable": False},
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
        sdk_result={"check_id": "sdk_version", "status": "passed", "severity": "info", "module": "futu", "version": "10.4.6408"},
        opend_result={"check_id": "opend_tcp", "status": "passed", "severity": "info", "reachable": True},
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
        sdk_result={"check_id": "sdk_version", "status": "passed", "severity": "info", "module": "futu", "version": "10.4.6408"},
        opend_result={"check_id": "opend_tcp", "status": "passed", "severity": "info", "reachable": True},
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
        sdk_result={"check_id": "sdk_version", "status": "passed", "severity": "info", "module": "futu", "version": "10.4.6408"},
        opend_result={"check_id": "opend_tcp", "status": "passed", "severity": "info", "reachable": True},
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
        sdk_result={"check_id": "sdk_version", "status": "passed", "severity": "info", "module": "futu", "version": "10.4.6408"},
        opend_result={"check_id": "opend_tcp", "status": "passed", "severity": "info", "reachable": True},
    )
    first = build_market_data_readiness_report(provider=FakeProvider(), **base)
    second = build_market_data_readiness_report(provider=FakeProvider(snapshot=[{"code": "US.AAPL", "last_price": 201.0}, {"code": "HK.00700", "last_price": 405.0}]), **base)

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
        sdk_result={"check_id": "sdk_version", "status": "passed", "severity": "info", "module": "futu", "version": "10.4.6408"},
        opend_result={"check_id": "opend_tcp", "status": "passed", "severity": "info", "reachable": True},
        provider=FakeProvider(),
    )

    paths = write_market_data_readiness_artifacts(report, tmp_path / "output" / "governance" / "2026-04-30")

    assert paths["json"].name == "p45_market_data_readiness.json"
    assert paths["md"].name == "p45_market_data_readiness.md"
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert payload["schema_version"] == P45_SCHEMA_VERSION


def test_markdown_rejects_forbidden_trading_language():
    from agent.research_v1.market_data_readiness import _markdown

    report = {
        "as_of_date": "2026-04-30",
        "status": "provider_ready",
        "host": "127.0.0.1",
        "port": 11111,
        "checks": [],
        "recommended_actions": [],
        "disclaimer": "buy this now",
    }
    with pytest.raises(ValueError, match="forbidden"):
        _markdown(report)


def test_disclaimer_contains_required_phrase():
    report = build_market_data_readiness_report(
        as_of_date="2026-04-30",
        host="127.0.0.1",
        port=11111,
        symbols=["US.AAPL"],
        history_days=30,
        option_symbol="US.AAPL",
        live=False,
        sdk_result={"check_id": "sdk_version", "status": "passed", "severity": "info", "module": "futu", "version": "10.4.6408"},
        opend_result={"check_id": "opend_tcp", "status": "passed", "severity": "info", "reachable": True},
        provider=FakeProvider(),
    )
    assert "market-data provider readiness only" in report["disclaimer"]
    assert "market-data provider readiness only" in P45_DISCLAIMER


def test_markdown_includes_check_table_and_actions(tmp_path: Path):
    from agent.research_v1.market_data_readiness import _markdown

    report = build_market_data_readiness_report(
        as_of_date="2026-04-30",
        host="127.0.0.1",
        port=11111,
        symbols=["US.AAPL"],
        history_days=30,
        option_symbol="US.AAPL",
        live=True,
        sdk_result={"check_id": "sdk_import", "status": "not_installed", "severity": "critical", "module": "futu", "version": ""},
        opend_result={"check_id": "opend_tcp", "status": "not_reachable", "severity": "critical", "reachable": False},
        provider=None,
    )
    md = _markdown(report)

    assert "sdk_import" in md or "sdk_version" in md
    assert "install_futu_api_sdk" in md
    assert "start_futu_opend_gui" in md


def test_opend_unreachable_returns_unavailable(tmp_path: Path):
    report = build_market_data_readiness_report(
        as_of_date="2026-04-30",
        host="127.0.0.1",
        port=11111,
        symbols=["US.AAPL"],
        history_days=30,
        option_symbol="US.AAPL",
        live=True,
        sdk_result={"check_id": "sdk_version", "status": "passed", "severity": "info", "module": "futu", "version": "10.4.6408"},
        opend_result={"check_id": "opend_tcp", "status": "not_reachable", "severity": "critical", "reachable": False},
        provider=None,
    )

    assert report["status"] == "provider_unavailable"
    assert "start_futu_opend_gui" in report["recommended_actions"]


def test_unprefixed_symbol_rejected():
    from agent.research_v1.market_data_readiness import validate_inputs

    errors = validate_inputs(
        as_of_date="2026-04-30",
        host="127.0.0.1",
        port=11111,
        symbols=["AAPL"],
        history_days=30,
        option_symbol="US.AAPL",
    )

    assert "invalid_symbol:AAPL" in errors


def test_source_hash_stable_for_identical_input(tmp_path: Path):
    kwargs = dict(
        as_of_date="2026-04-30",
        host="127.0.0.1",
        port=11111,
        symbols=["US.AAPL"],
        history_days=30,
        option_symbol="US.AAPL",
        live=True,
        sdk_result={"check_id": "sdk_version", "status": "passed", "severity": "info", "module": "futu", "version": "10.4.6408"},
        opend_result={"check_id": "opend_tcp", "status": "passed", "severity": "info", "reachable": True},
        provider=FakeProvider(),
    )
    first = build_market_data_readiness_report(**kwargs)
    second = build_market_data_readiness_report(**kwargs)

    assert first["source_hash"] == second["source_hash"]


def test_option_chain_skipped_when_empty():
    report = build_market_data_readiness_report(
        as_of_date="2026-04-30",
        host="127.0.0.1",
        port=11111,
        symbols=["US.AAPL"],
        history_days=30,
        option_symbol="",
        live=True,
        sdk_result={"check_id": "sdk_version", "status": "passed", "severity": "info", "module": "futu", "version": "10.4.6408"},
        opend_result={"check_id": "opend_tcp", "status": "passed", "severity": "info", "reachable": True},
        provider=FakeProvider(),
    )

    assert report["option_chain_summary"]["status"] == "skipped"
    assert any(c["status"] == "skipped" for c in report["checks"])


# ── P45 runtime tests ──────────────────────────────────────────────────

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


def test_runtime_rejects_non_positive_history_days(tmp_path: Path):
    result = run_market_data_readiness(
        output_root=tmp_path / "out",
        as_of_date="2026-04-30",
        host="127.0.0.1",
        port=11111,
        symbols=["US.AAPL"],
        history_days=0,
        live=False,
        provider=FakeProvider(),
    )

    assert result["status"] == "blocked_invalid_input"
    assert "history_days_must_be_positive" in result["warnings"]


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
        "run_copilot_console_index", "run_evidence_freshness_drift_monitor",
        "_extract_thesis_inputs",
    }
    assert not (forbidden_names & set(p45.__dict__))
    assert "market-data provider readiness only" in p45.P45_DISCLAIMER


# ── P45-B persistence tests ─────────────────────────────────────────────

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


def test_runtime_persists_when_db_provided(tmp_path: Path):
    db = _db(tmp_path)
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
        db=db,
    )

    assert result["status"] == "provider_ready"
    assert len(db.list_market_data_readiness_reports(as_of_date="2026-04-30")) == 1
