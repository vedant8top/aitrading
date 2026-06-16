"""Health manager: generates HEALTHY / WARNING / CRITICAL status."""

from __future__ import annotations

import enum
import logging
import time
from datetime import datetime, timezone
from typing import Optional

from src.runtime.heartbeat_monitor import HeartbeatMonitor
from src.runtime.runtime_state import RuntimeState

logger = logging.getLogger("runtime.health")


class HealthStatus(str, enum.Enum):
    HEALTHY = "HEALTHY"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class HealthManager:
    """Generate system health status.

    Rules:
        HEALTHY:  heartbeat < 10 min old AND failure rate < 5%
        WARNING:  heartbeat > 10 min OR failure rate > 5%
        CRITICAL: heartbeat > 30 min OR failure rate > 20%
    """

    def __init__(
        self,
        heartbeat_monitor: HeartbeatMonitor,
        runtime_state: RuntimeState,
        healthy_heartbeat_max: int = 600,
        warning_heartbeat_max: int = 1800,
        healthy_failure_rate: float = 0.05,
        warning_failure_rate: float = 0.20,
    ) -> None:
        self.heartbeat = heartbeat_monitor
        self.state = runtime_state
        self.healthy_heartbeat_max = healthy_heartbeat_max
        self.warning_heartbeat_max = warning_heartbeat_max
        self.healthy_failure_rate = healthy_failure_rate
        self.warning_failure_rate = warning_failure_rate
        self._last_status: Optional[HealthStatus] = None
        self._history: list[dict] = []

    def assess(self) -> HealthStatus:
        """Assess current system health."""
        secs_since_beat = self.heartbeat.seconds_since_last_beat() or float("inf")
        total = self.state.get_cycle_count()
        failed = self.state.get_failed_cycles()
        failure_rate = failed / total if total > 0 else 0.0

        if secs_since_beat > self.warning_heartbeat_max or failure_rate > self.warning_failure_rate:
            status = HealthStatus.CRITICAL
        elif secs_since_beat > self.healthy_heartbeat_max or failure_rate > self.healthy_failure_rate:
            status = HealthStatus.WARNING
        else:
            status = HealthStatus.HEALTHY

        now = datetime.now(timezone.utc).isoformat()
        record = {
            "timestamp": now,
            "status": status.value,
            "seconds_since_heartbeat": secs_since_beat,
            "failure_rate": failure_rate,
            "total_cycles": total,
            "failed_cycles": failed,
        }
        self._history.append(record)
        logger.info("Health: %s (heartbeat=%.0fs, failures=%d/%d=%.1f%%)",
                     status.value, secs_since_beat, failed, total, failure_rate * 100)

        self._last_status = status
        self.state.set_current_status(status.value)
        return status

    @property
    def last_status(self) -> Optional[HealthStatus]:
        return self._last_status

    def get_history(self, limit: int = 100) -> list[dict]:
        return self._history[-limit:]

    def get_summary(self) -> dict:
        secs = self.heartbeat.seconds_since_last_beat()
        total = self.state.get_cycle_count()
        failed = self.state.get_failed_cycles()
        rate = failed / total if total > 0 else 0.0
        return {
            "status": (self._last_status or HealthStatus.UNKNOWN if hasattr(HealthStatus, "UNKNOWN") else None),
            "seconds_since_heartbeat": secs,
            "failure_rate": rate,
            "total_cycles": total,
            "successful_cycles": self.state.get_successful_cycles(),
            "failed_cycles": failed,
        }