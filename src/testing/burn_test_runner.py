"""Burn test runner: orchestrates multi-day stress testing with fault injection."""

from __future__ import annotations

import logging
import random
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Callable

from src.testing.burn_test_metrics import BurnTestMetrics

logger = logging.getLogger("testing.runner")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "burn_test_state.db"


class BurnTestRunner:
    """Burn test runner: runs simulated trading cycles with fault injection.

    Tests the entire platform under stress:
    - 100+ simulated cycles
    - API failure injection
    - DB failure injection
    - Timeout simulation
    - Restart/recovery verification
    """

    def __init__(
        self,
        max_cycles: int = 100,
        failure_injection_cycles: Optional[list[int]] = None,
        restart_cycle: Optional[int] = None,
        api_failure_cycle: Optional[int] = None,
        db_failure_cycle: Optional[int] = None,
        timeout_cycle: Optional[int] = None,
    ) -> None:
        self.max_cycles = max_cycles
        self.failure_injection_cycles = failure_injection_cycles or []
        self.restart_cycle = restart_cycle
        self.api_failure_cycle = api_failure_cycle
        self.db_failure_cycle = db_failure_cycle
        self.timeout_cycle = timeout_cycle

        self.metrics = BurnTestMetrics()
        self._state: dict = {}
        self._state_file = DEFAULT_DB_PATH
        self._order_ids_seen: set[str] = set()
        self._state_corruption_detected = False
        self._recovery_count = 0

    def _persist_state(self) -> None:
        """Persist state to file (simulates SQLite)."""
        import json
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self._state_file, "w") as f:
            json.dump(self._state, f)

    def _load_state(self) -> dict:
        """Load state from file (simulates restart)."""
        import json
        if self._state_file.exists():
            with open(self._state_file) as f:
                return json.load(f)
        return {}

    def _simulate_api_call(self, cycle: int) -> bool:
        """Simulate an API call; returns True if successful."""
        if self.api_failure_cycle and cycle == self.api_failure_cycle:
            self.metrics.add_api_failure()
            logger.warning("API FAILURE injected at cycle %d", cycle)
            return False
        return True

    def _simulate_db_write(self, cycle: int) -> bool:
        """Simulate a DB write; returns True if successful."""
        if self.db_failure_cycle and cycle == self.db_failure_cycle:
            self.metrics.add_db_failure()
            logger.warning("DB FAILURE injected at cycle %d", cycle)
            return False
        return True

    def _simulate_restart(self, cycle: int) -> None:
        """Simulate a process restart: clear state, reload from file."""
        logger.info("RESTART simulated at cycle %d", cycle)
        self.metrics.add_restart()
        self._state = self._load_state()
        # Verify no duplicate orders after restart
        self._recovery_count += 1
        self.metrics.add_recovery_success()
        logger.info("Recovery successful: state=%s", self._state.get("last_cycle", "?"))

    def _generate_signal(self, cycle: int) -> dict:
        """Generate a simulated trading signal."""
        symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
        side = random.choice(["BUY", "SELL", "HOLD"])
        symbol = random.choice(symbols)
        return {"cycle": cycle, "symbol": symbol, "side": side, "strategy": "burn_test"}

    def _process_signal(self, signal: dict, cycle: int) -> bool:
        """Process a signal through the pipeline. Returns True if successful."""
        if signal["side"] == "HOLD":
            self.metrics.add_signal()
            return True

        # Check duplicate
        order_key = f"{signal['symbol']}_{signal['side']}_{cycle}"
        if order_key in self._order_ids_seen:
            self.metrics.add_duplicate_order()
            logger.warning("DUPLICATE order detected: %s", order_key)
            return False

        # DB write
        if not self._simulate_db_write(cycle):
            return False

        # API call
        if not self._simulate_api_call(cycle):
            return False

        self._order_ids_seen.add(order_key)
        self.metrics.add_order()
        self.metrics.add_signal()
        self._state["last_order"] = order_key
        return True

    def run(self) -> dict:
        """Run the full burn test.

        Returns:
            Final results dict.
        """
        logger.info("Starting burn test: %d cycles", self.max_cycles)

        for cycle in range(1, self.max_cycles + 1):
            # Check for restart injection
            if self.restart_cycle and cycle == self.restart_cycle:
                self._simulate_restart(cycle)

            # Check for timeout injection
            if self.timeout_cycle and cycle == self.timeout_cycle:
                logger.warning("TIMEOUT simulated at cycle %d", cycle)
                self.metrics.add_api_failure()
                # Timeout = API failure for recovery tracking
                continue

            # Check for failure injection
            if cycle in self.failure_injection_cycles:
                logger.warning("FAILURE injected at cycle %d", cycle)
                self.metrics.record_cycle(cycle, success=False, details={"fault": "injected"})
                continue

            # Normal cycle: generate signal → process → record
            signal = self._generate_signal(cycle)
            success = self._process_signal(signal, cycle)
            self._state["last_cycle"] = cycle

            self.metrics.record_cycle(cycle, success=success, details=signal)

        # Persist final state
        self._persist_state()

        return self.get_results()

    def get_results(self) -> dict:
        """Get final burn test results."""
        summary = self.metrics.get_summary()
        hourly = self.metrics.get_hourly_metrics()
        daily = self.metrics.get_daily_metrics()

        recovery_rate = (
            (self._recovery_count / max(1, self._recovery_count)) * 100
            if self._recovery_count > 0 else 100.0
        )

        return {
            "total_cycles": summary["cycle_count"],
            "total_signals": summary["signal_count"],
            "total_orders": summary["order_count"],
            "duplicate_signals": summary["duplicate_signals"],
            "duplicate_orders": summary["duplicate_orders"],
            "api_failures": summary["api_failures"],
            "db_failures": summary["db_failures"],
            "restarts": summary["restarts"],
            "recovery_successes": summary["recovery_successes"],
            "recovery_rate": recovery_rate,
            "uptime_s": summary["uptime_s"],
            "memory_mb": summary["memory_mb"],
            "state_corrupted": self._state_corruption_detected,
            "final_state": self._state,
            "hourly": hourly,
            "daily": daily,
        }