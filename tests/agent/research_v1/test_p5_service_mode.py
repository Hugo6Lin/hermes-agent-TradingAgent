"""Tests for P5 macOS service mode and stress scenarios."""

from pathlib import Path

from agent.research_v1.macos_service import (
    LaunchAgentConfig,
    build_launch_agent_plist,
    build_launchctl_command,
)
from agent.research_v1.service_manager import HermesServiceManager
from agent.research_v1.stress_testing import (
    STRESS_SCENARIOS,
    evaluate_stress_scenarios,
)


def test_build_launch_agent_plist_contains_required_launchd_keys():
    """Render a valid launchd plist for Hermes background service."""
    plist = build_launch_agent_plist(
        LaunchAgentConfig(
            label="com.hermes.agent",
            program_arguments=["/usr/bin/python3", "-m", "agent.research_v1.cli"],
            working_directory="/Users/test/hermes-agent",
            standard_out_path="/tmp/hermes.out",
            standard_error_path="/tmp/hermes.err",
            run_at_load=True,
            keep_alive=True,
            start_interval=300,
        )
    )

    assert "<key>Label</key>" in plist
    assert "com.hermes.agent" in plist
    assert "<key>ProgramArguments</key>" in plist
    assert "<key>RunAtLoad</key>" in plist
    assert "<key>KeepAlive</key>" in plist


def test_build_launchctl_command_matches_action():
    """Build deterministic launchctl commands for load/unload actions."""
    command = build_launchctl_command("load", "/tmp/com.hermes.agent.plist")
    assert command == ["launchctl", "load", "/tmp/com.hermes.agent.plist"]


def test_service_manager_enters_degraded_mode_after_repeated_data_failures():
    """Service manager should enter degraded mode when data is repeatedly unavailable."""
    manager = HermesServiceManager(max_consecutive_failures=3)

    manager.record_poll_result(data_available=False)
    manager.record_poll_result(data_available=False)
    manager.record_poll_result(data_available=False)

    assert manager.degraded_mode is True
    assert manager.get_service_status()["consecutive_failures"] == 3


def test_service_manager_recovers_after_healthy_poll():
    """Healthy poll should clear degraded mode and failure streak."""
    manager = HermesServiceManager(max_consecutive_failures=2)
    manager.record_poll_result(data_available=False)
    manager.record_poll_result(data_available=False)

    manager.record_poll_result(data_available=True)

    status = manager.get_service_status()
    assert status["degraded_mode"] is False
    assert status["consecutive_failures"] == 0


def test_service_manager_uses_idle_interval_after_market_close():
    """Polling interval should drop to idle cadence outside market hours."""
    manager = HermesServiceManager(active_poll_seconds=300, idle_poll_seconds=3600)

    assert manager.get_poll_interval(market_open=True) == 300
    assert manager.get_poll_interval(market_open=False) == 3600


def test_service_manager_requests_restart_when_heartbeat_is_stale():
    """Stale heartbeat should trigger a restart recommendation."""
    manager = HermesServiceManager(heartbeat_ttl_seconds=120)
    status = manager.evaluate_health(last_heartbeat_age_seconds=180)

    assert status["healthy"] is False
    assert status["should_restart"] is True


def test_stress_scenarios_define_three_extreme_market_regimes():
    """Expose the agreed stress test scenarios for downstream validation."""
    assert set(STRESS_SCENARIOS.keys()) == {"2008_crisis", "2020_covid_crash", "2022_rate_hike_bear"}


def test_evaluate_stress_scenarios_flags_high_drawdown_regimes():
    """Warn when stress scenario performance breaches risk thresholds."""
    result = evaluate_stress_scenarios(
        scenario_results={
            "2008_crisis": {"win_rate": 0.35, "max_drawdown": -0.42, "average_return": -0.18},
            "2020_covid_crash": {"win_rate": 0.48, "max_drawdown": -0.21, "average_return": -0.05},
            "2022_rate_hike_bear": {"win_rate": 0.40, "max_drawdown": -0.28, "average_return": -0.09},
        },
        max_drawdown_limit=-0.25,
    )

    assert result["scenario_count"] == 3
    assert result["has_critical_regime"] is True
    assert any(item["scenario"] == "2008_crisis" for item in result["warnings"])


def test_install_scripts_exist_for_launch_agent_setup():
    """Install and uninstall scripts should be present for launch agent setup."""
    assert Path(r"E:\hermes-agent\install.sh").exists()
    assert Path(r"E:\hermes-agent\uninstall.sh").exists()


def test_install_script_generates_plist_from_workspace_context():
    """Install script should generate plist from the local workspace, not copy a static file."""
    content = Path(r"E:\hermes-agent\install.sh").read_text(encoding="utf-8")
    assert "build_launch_agent_plist" in content
    assert "ROOT_DIR" in content
