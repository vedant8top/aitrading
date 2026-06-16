"""Signal scheduler: runs strategy at fixed intervals with duplicate prevention."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("live_trading.signal_scheduler")


class SignalScheduler:
    """Runs strategy at fixed intervals with duplicate prevention.

    Responsibilities:
    - Run every N seconds (default 300 = 5 minutes)
    - Track last execution time
    - Prevent duplicate runs
    """

    def __init__(self, interval_seconds: int = 300) -> None:
        self.interval_seconds = interval_seconds
        self._last_run_time: Optional[float] = None
        self._run_count: int = 0

    @property
    def last_run_time(self) -> Optional[float]:
        """Last run timestamp (epoch seconds)."""
        return self._last_run_time

    @property
    def last_run_iso(self) -> Optional[str]:
        """Last run as ISO string."""
        if self._last_run_time is None:
            return None
        return datetime.fromtimestamp(self._last_run_time, tz=timezone.utc).isoformat()

    @property
    def run_count(self) -> int:
        """Number of runs completed."""
        return self._run_count

    def should_run(self) -> bool:
        """Check if enough time has passed since last run.

        Returns:
            True if it's time to run, False otherwise.
        """
        now = time.time()
        if self._last_run_time is None:
            return True
        elapsed = now - self._last_run_time
        return elapsed >= self.interval_seconds

    def mark_run(self) -> None:
        """Mark that a run has been completed."""
        self._last_run_time = time.time()
        self._run_count += 1
        logger.info("Scheduler run #%d completed at %s", self._run_count, self.last_run_iso)

    def time_until_next(self) -> float:
        """Seconds until next allowed run.

        Returns:
            Seconds remaining (0 if ready now).
        """
        if self._last_run_time is None:
            return 0.0
        elapsed = time.time() - self._last_run_time
        remaining = self.interval_seconds - elapsed
        return max(0.0, remaining)

    def reset(self) -> None:
        """Reset scheduler state."""
        self._last_run_time = None
        self._run_count = 0
        logger.info("Scheduler reset")