"""Burn test metrics: tracks performance metrics during stress testing."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("testing.metrics")


class BurnTestMetrics:
    """Collects and aggregates metrics during burn test cycles.

    Per-cycle metrics:
    - cycle_count, signal_count, order_count
    - duplicate_signals, duplicate_orders
    - api_failures, db_failures
    - memory_mb, uptime_s

    Aggregation: hourly + daily
    """

    def __init__(self) -> None:
        self._start_time = time.time()
        self._cycle_count = 0
        self._signal_count = 0
        self._order_count = 0
        self._duplicate_signals = 0
        self._duplicate_orders = 0
        self._api_failures = 0
        self._db_failures = 0
        self._restarts = 0
        self._recovery_successes = 0
        self._cycle_metrics: list[dict] = []
        self._hourly: dict[str, dict] = {}
        self._daily: dict[str, dict] = {}
        self._hourly_windows: dict[str, list[dict]] = {}

    def record_cycle(self, cycle: int, success: bool, details: Optional[dict] = None) -> None:
        """Record metrics for one cycle."""
        now = datetime.now(timezone.utc)
        hour_key = now.strftime("%Y-%m-%d %H:00")
        day_key = now.strftime("%Y-%m-%d")
        elapsed = time.time() - self._start_time

        entry = {
            "cycle": cycle,
            "timestamp": now.isoformat(),
            "success": success,
            "elapsed_s": round(elapsed, 2),
            "details": details or {},
        }

        self._cycle_metrics.append(entry)
        self._cycle_count += 1

        # Update hourly
        if hour_key not in self._hourly:
            self._hourly[hour_key] = {"cycles": 0, "success": 0, "failure": 0, "signals": 0, "orders": 0}
        self._hourly[hour_key]["cycles"] += 1
        if success:
            self._hourly[hour_key]["success"] += 1
        else:
            self._hourly[hour_key]["failure"] += 1

        # Update daily
        if day_key not in self._daily:
            self._daily[day_key] = {"cycles": 0, "success": 0, "failure": 0, "signals": 0, "orders": 0}
        self._daily[day_key]["cycles"] += 1
        if success:
            self._daily[day_key]["success"] += 1
        else:
            self._daily[day_key]["failure"] += 1

    def add_signal(self, count: int = 1) -> None:
        self._signal_count += count
        hour_key = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:00")
        day_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if hour_key in self._hourly:
            self._hourly[hour_key]["signals"] += count
        if day_key in self._daily:
            self._daily[day_key]["signals"] += count

    def add_order(self, count: int = 1) -> None:
        self._order_count += count
        hour_key = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:00")
        day_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if hour_key in self._hourly:
            self._hourly[hour_key]["orders"] += count
        if day_key in self._daily:
            self._daily[day_key]["orders"] += count

    def add_duplicate_signal(self) -> None:
        self._duplicate_signals += 1

    def add_duplicate_order(self) -> None:
        self._duplicate_orders += 1

    def add_api_failure(self) -> None:
        self._api_failures += 1

    def add_db_failure(self) -> None:
        self._db_failures += 1

    def add_restart(self) -> None:
        self._restarts += 1

    def add_recovery_success(self) -> None:
        self._recovery_successes += 1

    def uptime_seconds(self) -> float:
        return time.time() - self._start_time

    def memory_usage_mb(self) -> float:
        try:
            import psutil
            import os
            return psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
        except ImportError:
            return 0.0

    def get_summary(self) -> dict:
        return {
            "cycle_count": self._cycle_count,
            "signal_count": self._signal_count,
            "order_count": self._order_count,
            "duplicate_signals": self._duplicate_signals,
            "duplicate_orders": self._duplicate_orders,
            "api_failures": self._api_failures,
            "db_failures": self._db_failures,
            "restarts": self._restarts,
            "recovery_successes": self._recovery_successes,
            "uptime_s": round(self.uptime_seconds(), 2),
            "memory_mb": round(self.memory_usage_mb(), 2),
        }

    def get_hourly_metrics(self) -> dict[str, dict]:
        return dict(self._hourly)

    def get_daily_metrics(self) -> dict[str, dict]:
        return dict(self._daily)

    def get_cycle_history(self, limit: int = 100) -> list[dict]:
        return self._cycle_metrics[-limit:]