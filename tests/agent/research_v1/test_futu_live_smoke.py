"""Optional live smoke tests for P45 Futu market-data readiness.

Skipped unless HERMES_LIVE_FUTU=1. When enabled, performs read-only
snapshot/history checks against a local OpenD gateway.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

LIVE = os.environ.get("HERMES_LIVE_FUTU") == "1"

pytestmark = pytest.mark.skipif(not LIVE, reason="Set HERMES_LIVE_FUTU=1 to run live Futu smoke tests")


def test_sdk_import_succeeds():
    from agent.research_v1.market_data_readiness import check_futu_sdk

    result = check_futu_sdk()
    assert result["status"] in {"passed", "degraded"}, (
        f"futu-api must be importable for live tests; got {result['status']}"
    )


def test_opend_tcp_reachable():
    from agent.research_v1.market_data_readiness import check_opend_tcp

    host = os.environ.get("FUTU_OPEND_HOST", "127.0.0.1")
    port = int(os.environ.get("FUTU_OPEND_PORT", "11111"))
    result = check_opend_tcp(host, port)
    assert result["status"] == "passed", (
        f"OpenD must be reachable at {host}:{port}; got {result['status']}"
    )


def test_live_readiness_report_provider_ready_or_degraded(tmp_path: Path):
    from agent.research_v1.market_data_readiness import run_market_data_readiness

    host = os.environ.get("FUTU_OPEND_HOST", "127.0.0.1")
    port = int(os.environ.get("FUTU_OPEND_PORT", "11111"))
    result = run_market_data_readiness(
        output_root=tmp_path / "output" / "governance",
        as_of_date="2026-04-30",
        host=host,
        port=port,
        symbols=["US.AAPL"],
        history_days=30,
        option_symbol="US.AAPL",
        live=True,
    )
    assert result["status"] in {"provider_ready", "provider_degraded"}, (
        f"Expected ready or degraded with live OpenD; got {result['status']}"
    )
    assert Path(result["output_dir"]).joinpath("p45_market_data_readiness.json").exists()
