"""Tests for timeout degradation system."""

import pytest
import time
from agent.research_v1.timeout_degradation import (
    TimeoutDegradationManager,
    PipelinePhase,
    PhaseTimeout,
    DegradedResult,
    DEFAULT_PHASE_TIMEOUTS
)


def test_phase_enum():
    assert PipelinePhase.PHASE1_ANALYSTS.value == "phase1_analysts"
    assert PipelinePhase.PHASE2_DEBATE.value == "phase2_debate"


def test_default_timeouts():
    assert DEFAULT_PHASE_TIMEOUTS[PipelinePhase.PHASE1_ANALYSTS].timeout_seconds == 30
    assert DEFAULT_PHASE_TIMEOUTS[PipelinePhase.PHASE2_DEBATE].timeout_seconds == 60
    assert DEFAULT_PHASE_TIMEOUTS[PipelinePhase.PHASE3_MANAGER].timeout_seconds == 90
    assert DEFAULT_PHASE_TIMEOUTS[PipelinePhase.PHASE4_REPORT].timeout_seconds == 120


def test_successful_execution():
    manager = TimeoutDegradationManager()

    def sample_func():
        return {"data": "success"}

    result = manager.execute_with_timeout(
        PipelinePhase.PHASE1_ANALYSTS,
        sample_func
    )

    assert result.degraded is False
    assert result.content == {"data": "success"}
    assert result.error is None


def test_timeout_handling():
    manager = TimeoutDegradationManager()

    def slow_func():
        time.sleep(0.5)  # Very short sleep for test

    # Use a timeout of 0.1s which should trigger immediate timeout
    manager.phase_timeouts[PipelinePhase.PHASE1_ANALYSTS] = PhaseTimeout(
        phase=PipelinePhase.PHASE1_ANALYSTS,
        timeout_seconds=0,
        max_retries=0
    )

    result = manager.execute_with_timeout(
        PipelinePhase.PHASE1_ANALYSTS,
        slow_func
    )

    assert result.degraded is True
    assert result.content is None


def test_fallback_to_earlier_phase():
    manager = TimeoutDegradationManager()

    # Pre-store a result in phase 1
    manager._phase_results[PipelinePhase.PHASE1_ANALYSTS] = {"analyst": "data"}

    # Phase 2 will fail and should fallback to phase 1
    manager.phase_timeouts[PipelinePhase.PHASE2_DEBATE] = PhaseTimeout(
        phase=PipelinePhase.PHASE2_DEBATE,
        timeout_seconds=0,
        max_retries=0
    )

    def failing_func():
        raise TimeoutError("Simulated timeout")

    result = manager.execute_with_timeout(
        PipelinePhase.PHASE2_DEBATE,
        failing_func
    )

    assert result.degraded is True
    assert result.fallback_phase == PipelinePhase.PHASE1_ANALYSTS
    assert result.content == {"analyst": "data"}


def test_custom_fallback_function():
    manager = TimeoutDegradationManager()

    manager.phase_timeouts[PipelinePhase.PHASE1_ANALYSTS] = PhaseTimeout(
        phase=PipelinePhase.PHASE1_ANALYSTS,
        timeout_seconds=0,
        max_retries=0
    )

    def failing_func():
        raise TimeoutError("Simulated timeout")

    def fallback():
        return {"fallback": "data"}

    result = manager.execute_with_timeout(
        PipelinePhase.PHASE1_ANALYSTS,
        failing_func,
        fallback_func=fallback
    )

    assert result.degraded is True
    assert result.content == {"fallback": "data"}


def test_degradation_log():
    manager = TimeoutDegradationManager()

    manager.phase_timeouts[PipelinePhase.PHASE1_ANALYSTS] = PhaseTimeout(
        phase=PipelinePhase.PHASE1_ANALYSTS,
        timeout_seconds=0,
        max_retries=0
    )

    def failing_func():
        raise TimeoutError("Test timeout")

    manager.execute_with_timeout(PipelinePhase.PHASE1_ANALYSTS, failing_func)

    assert manager.has_degraded() is True
    log = manager.get_degradation_log()
    assert len(log) == 1
    assert log[0]["failed_phase"] == "phase1_analysts"


def test_no_degradation_when_disabled():
    manager = TimeoutDegradationManager(enable_degradation=False)

    manager.phase_timeouts[PipelinePhase.PHASE1_ANALYSTS] = PhaseTimeout(
        phase=PipelinePhase.PHASE1_ANALYSTS,
        timeout_seconds=0,
        max_retries=0
    )

    def failing_func():
        raise TimeoutError("Simulated timeout")

    result = manager.execute_with_timeout(
        PipelinePhase.PHASE1_ANALYSTS,
        failing_func
    )

    assert result.degraded is True
    assert result.content is None
    assert result.fallback_phase is None


def test_get_latest_result():
    manager = TimeoutDegradationManager()

    def sample_func():
        return {"phase": "analysts"}

    manager.execute_with_timeout(PipelinePhase.PHASE1_ANALYSTS, sample_func)

    result = manager.get_latest_result(PipelinePhase.PHASE1_ANALYSTS)
    assert result == {"phase": "analysts"}

    assert manager.get_latest_result(PipelinePhase.PHASE2_DEBATE) is None
