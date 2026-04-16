"""Timeout degradation strategy for research pipeline.

Progressive timeout system:
- Phase 1: Fast analyst reports (parallel) - 30s timeout
- Phase 2: Bull/Bear debate - 60s timeout
- Phase 3: Manager decision - 90s timeout
- Phase 4: Full report generation - 120s timeout

If a phase times out, fallback to degraded mode with earlier phase results.
"""

import time
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from agent.research_v1.llm_clients import get_timeout_for_model


logger = logging.getLogger(__name__)


class PipelinePhase(Enum):
    """Pipeline phases in order of execution."""
    PHASE1_ANALYSTS = "phase1_analysts"      # 5 parallel analysts
    PHASE2_DEBATE = "phase2_debate"          # Bull/Bear debate
    PHASE3_MANAGER = "phase3_manager"         # Research Manager decision
    PHASE4_REPORT = "phase4_report"           # Full report generation


@dataclass
class PhaseTimeout:
    """Timeout configuration for a pipeline phase."""
    phase: PipelinePhase
    timeout_seconds: int
    max_retries: int = 2


# Default timeout configurations
DEFAULT_PHASE_TIMEOUTS = {
    PipelinePhase.PHASE1_ANALYSTS: PhaseTimeout(
        phase=PipelinePhase.PHASE1_ANALYSTS,
        timeout_seconds=30,
        max_retries=2
    ),
    PipelinePhase.PHASE2_DEBATE: PhaseTimeout(
        phase=PipelinePhase.PHASE2_DEBATE,
        timeout_seconds=60,
        max_retries=2
    ),
    PipelinePhase.PHASE3_MANAGER: PhaseTimeout(
        phase=PipelinePhase.PHASE3_MANAGER,
        timeout_seconds=90,
        max_retries=1
    ),
    PipelinePhase.PHASE4_REPORT: PhaseTimeout(
        phase=PipelinePhase.PHASE4_REPORT,
        timeout_seconds=120,
        max_retries=1
    ),
}


@dataclass
class DegradedResult:
    """Result of a degraded/fallback operation."""
    content: Any
    degraded: bool
    original_phase: PipelinePhase
    fallback_phase: Optional[PipelinePhase]
    error: Optional[str] = None
    tokens_used: int = 0


class TimeoutDegradationManager:
    """Manages timeout degradation for pipeline phases.

    If a phase times out, this manager provides fallback to degraded
    results from earlier phases.
    """

    def __init__(
        self,
        phase_timeouts: dict[PipelinePhase, PhaseTimeout] = None,
        enable_degradation: bool = True
    ):
        """Initialize TimeoutDegradationManager.

        Args:
            phase_timeouts: Timeout configs per phase. Uses defaults if None.
            enable_degradation: Whether to enable fallback degradation.
        """
        self.phase_timeouts = phase_timeouts or DEFAULT_PHASE_TIMEOUTS
        self.enable_degradation = enable_degradation
        self._phase_results: dict[PipelinePhase, Any] = {}
        self._degradation_log: list[dict] = []

    def execute_with_timeout(
        self,
        phase: PipelinePhase,
        func: Callable[[], Any],
        fallback_func: Optional[Callable[[], Any]] = None
    ) -> DegradedResult:
        """Execute a function with timeout and degradation fallback.

        Args:
            phase: The current pipeline phase.
            func: The function to execute.
            fallback_func: Optional fallback function if timeout occurs.

        Returns:
            DegradedResult with content and degradation info.
        """
        phase_config = self.phase_timeouts.get(phase)
        if phase_config is None:
            # No timeout configured for this phase
            result = func()
            return DegradedResult(
                content=result,
                degraded=False,
                original_phase=phase,
                fallback_phase=None
            )

        timeout = phase_config.timeout_seconds
        max_retries = phase_config.max_retries

        last_error = None
        for attempt in range(max_retries + 1):
            try:
                start_time = time.time()
                result = func()
                elapsed = time.time() - start_time

                # Check if elapsed time exceeded timeout
                if elapsed > timeout:
                    raise TimeoutError(
                        f"Phase {phase.value} exceeded timeout "
                        f"({elapsed:.2f}s > {timeout}s)"
                    )

                logger.info(f"Phase {phase.value} completed in {elapsed:.2f}s")

                # Store result for potential fallback by later phases
                self._phase_results[phase] = result

                return DegradedResult(
                    content=result,
                    degraded=False,
                    original_phase=phase,
                    fallback_phase=None
                )

            except TimeoutError as exc:
                last_error = exc
                logger.warning(
                    f"Phase {phase.value} timeout after {timeout}s "
                    f"(attempt {attempt + 1}/{max_retries + 1})"
                )

                if attempt < max_retries:
                    # Exponential backoff before retry
                    wait_time = timeout * (attempt + 1)
                    logger.info(f"Retrying after {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    # All retries exhausted
                    break

            except Exception as exc:
                last_error = exc
                logger.error(f"Phase {phase.value} failed: {exc}")
                break

        # Timeout or failure - try degradation
        if self.enable_degradation:
            return self._degrade_phase(phase, last_error, fallback_func)

        return DegradedResult(
            content=None,
            degraded=True,
            original_phase=phase,
            fallback_phase=None,
            error=str(last_error)
        )

    def _degrade_phase(
        self,
        failed_phase: PipelinePhase,
        error: Optional[Exception],
        fallback_func: Optional[Callable[[], Any]]
    ) -> DegradedResult:
        """Attempt to degrade to an earlier phase or use fallback.

        Args:
            failed_phase: The phase that failed.
            error: The error that occurred.
            fallback_func: Optional fallback function.

        Returns:
            DegradedResult with fallback content.
        """
        logger.info(f"Degrading from phase {failed_phase.value}")

        # Try to use stored results from earlier phases
        fallback_phase = self._get_fallback_phase(failed_phase)
        fallback_content = None

        if fallback_phase and fallback_phase in self._phase_results:
            fallback_content = self._phase_results[fallback_phase]
            logger.info(f"Using fallback from phase {fallback_phase.value}")

        elif fallback_func is not None:
            try:
                fallback_content = fallback_func()
                logger.info("Using provided fallback function")
            except Exception as exc:
                logger.error(f"Fallback function also failed: {exc}")
                fallback_content = None

        # Log degradation
        degradation_entry = {
            "failed_phase": failed_phase.value,
            "fallback_phase": fallback_phase.value if fallback_phase else None,
            "error": str(error),
            "timestamp": time.time()
        }
        self._degradation_log.append(degradation_entry)

        return DegradedResult(
            content=fallback_content,
            degraded=True,
            original_phase=failed_phase,
            fallback_phase=fallback_phase,
            error=str(error)
        )

    def _get_fallback_phase(self, failed_phase: PipelinePhase) -> Optional[PipelinePhase]:
        """Get the fallback phase for a failed phase.

        Args:
            failed_phase: The phase that failed.

        Returns:
            The fallback phase, or None if no fallback available.
        """
        fallback_map = {
            PipelinePhase.PHASE4_REPORT: PipelinePhase.PHASE3_MANAGER,
            PipelinePhase.PHASE3_MANAGER: PipelinePhase.PHASE2_DEBATE,
            PipelinePhase.PHASE2_DEBATE: PipelinePhase.PHASE1_ANALYSTS,
            PipelinePhase.PHASE1_ANALYSTS: None,  # No fallback
        }
        return fallback_map.get(failed_phase)

    def get_degradation_log(self) -> list[dict]:
        """Get log of all degradations that occurred.

        Returns:
            List of degradation entries.
        """
        return list(self._degradation_log)

    def has_degraded(self) -> bool:
        """Check if any degradation occurred.

        Returns:
            True if any phase was degraded.
        """
        return len(self._degradation_log) > 0

    def get_latest_result(self, phase: PipelinePhase) -> Optional[Any]:
        """Get stored result for a phase.

        Args:
            phase: The phase to get result for.

        Returns:
            The stored result, or None if not available.
        """
        return self._phase_results.get(phase)


def get_model_timeout_for_phase(phase: PipelinePhase, model: str) -> int:
    """Get appropriate timeout for a model in a given phase.

    Uses the larger of model timeout or phase timeout.

    Args:
        phase: The pipeline phase.
        model: The model name.

    Returns:
        Timeout in seconds.
    """
    phase_timeout = DEFAULT_PHASE_TIMEOUTS.get(phase)
    model_timeout = get_timeout_for_model(model)

    if phase_timeout:
        return max(phase_timeout.timeout_seconds, model_timeout)
    return model_timeout
