"""Runtime service management for Hermes polling and health."""


class HermesServiceManager:
    """Track polling cadence, health, and degraded-mode transitions."""

    def __init__(
        self,
        max_consecutive_failures: int = 3,
        active_poll_seconds: int = 300,
        idle_poll_seconds: int = 3600,
        heartbeat_ttl_seconds: int = 300,
    ):
        self.max_consecutive_failures = max_consecutive_failures
        self.active_poll_seconds = active_poll_seconds
        self.idle_poll_seconds = idle_poll_seconds
        self.heartbeat_ttl_seconds = heartbeat_ttl_seconds
        self.consecutive_failures = 0
        self.degraded_mode = False

    def record_poll_result(self, data_available: bool) -> None:
        """Update service state after a polling cycle."""
        if data_available:
            self.consecutive_failures = 0
            self.degraded_mode = False
            return

        self.consecutive_failures += 1
        if self.consecutive_failures >= self.max_consecutive_failures:
            self.degraded_mode = True

    def get_service_status(self) -> dict:
        """Return current health and degraded status."""
        return {
            "consecutive_failures": self.consecutive_failures,
            "degraded_mode": self.degraded_mode,
        }

    def get_poll_interval(self, market_open: bool) -> int:
        """Return active or idle polling cadence based on market state."""
        return self.active_poll_seconds if market_open else self.idle_poll_seconds

    def evaluate_health(self, last_heartbeat_age_seconds: int) -> dict:
        """Evaluate heartbeat freshness and restart need."""
        healthy = last_heartbeat_age_seconds <= self.heartbeat_ttl_seconds
        return {
            "healthy": healthy,
            "should_restart": not healthy,
            "last_heartbeat_age_seconds": last_heartbeat_age_seconds,
        }
