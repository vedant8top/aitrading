"""Runtime metrics: tracks operational metrics during runtime harness execution."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("runtime.harness.metrics")


class RuntimeMetrics:
    """Collects and persists operational metrics during runtime harness.

    Tracks per cycle: uptime, signals, failures, memory, heartbeat count, API errors.
    Generates hourly summaries and final summary.
    """

    def __init__(self) -> None:
        self._start_time = time.time()
        self._cycle_count = 0
        self._signal_count = 0
        self._failure_count = 0
        self._heartbeat_count = 0
        self._api_error_count = 0
        self._restart_count = 0
        self._cycle_details: list[dict] = []
        self._hourly: dict[str, dict] = {}
        self._daily: dict[str, dict] = {}

    def record_cycle(self, cycle: int, success: bool, signals: int = 0,
                     api_errors: int = 0, details: Optional[dict] = None) -> None:
        now = datetime.now(timezone.utc)
        hour_key = now.strftime("%Y-%m-%d %H:00")
        day_key = now.strftime("%Y-%m-%d")
        elapsed = time.time() - self._start_time

        entry = {
            "cycle": cycle, "timestamp": now.isoformat(), "success": success,
            "signals": signals, "api_errors": api_errors,
            "elapsed_s": round(elapsed, 2), "details": details or {},
        }
        self._cycle_details.append(entry)
        self._cycle_count += 1
        self._signal_count += signals
        self._api_error_count += api_errors
        if not success:
            self._failure_count += 1

        for bucket in [self._hourly, self._daily]:
            key = hour_key if bucket is self._hourly else day_key
            if key not in bucket:
                bucket[key] = {"cycles": 0, "success": 0, "failure": 0, "signals": 0, "api_errors": 0}
            bucket[key]["cycles"] += 1
            bucket[key]["signals"] += signals
            bucket[key]["api_errors"] += api_errors
            if success:
                bucket[key]["success"] += 1
            else:
                bucket[key]["failure"] += 1

    def record_heartbeat(self) -> None:
        self._heartbeat_count += 1

    def record_restart(self) -> None:
        self._restart_count += 1

    def uptime_seconds(self) -> float:
        return time.time() - self._start_time

    def memory_usage_mb(self) -> float:
        try:
            import psutil, os
            return psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
        except ImportError:
            return 0.0

    def get_summary(self) -> dict:
        return {
            "cycle_count": self._cycle_count,
            "signal_count": self._signal_count,
            "failure_count": self._failure_count,
            "heartbeat_count": self._heartbeat_count,
            "api_error_count": self._api_error_count,
            "restart_count": self._restart_count,
            "uptime_s": round(self.uptime_seconds(), 2),
            "memory_mb": round(self.memory_usage_mb(), 2),
        }

    def get_hourly(self) -> dict[str, dict]:
        return dict(self._hourly)

    def get_daily(self) -> dict[str, dict]:
        return dict(self._daily)

    def get_cycle_history(self, limit: int = 100) -> list[dict]:
        return self._cycle_details[-limit:]