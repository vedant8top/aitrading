"""Continuous runner: orchestrates scan cycles with health monitoring."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Optional

from src.exchanges.binance_adapter import BinanceAdapter
from src.exchanges.binance_market_data import BinanceMarketData
from src.live_trading.live_strategy_runner import LiveStrategyRunner
from src.runtime.runtime_state import RuntimeState
from src.runtime.heartbeat_monitor import HeartbeatMonitor
from src.runtime.health_manager import HealthManager, HealthStatus

logger = logging.getLogger("runtime.continuous_runner")


class ContinuousRunner:
    """Orchestrates continuous scan cycles with health monitoring.

    Responsibilities:
    - Start LiveStrategyRunner
    - Execute scan cycle every 5 minutes
    - Prevent overlapping executions
    - Track runtime duration / cycle count
    - Recover after transient exceptions
    """

    def __init__(
        self,
        adapter: BinanceAdapter,
        market: BinanceMarketData,
        strategy_runner: Optional[LiveStrategyRunner] = None,
        runtime_state: Optional[RuntimeState] = None,
        heartbeat_monitor: Optional[HeartbeatMonitor] = None,
        health_manager: Optional[HealthManager] = None,
        cycle_interval: int = 300,
        max_cycles: int = 0,
    ) -> None:
        self.adapter = adapter
        self.market = market
        self.runner = strategy_runner or LiveStrategyRunner(adapter, market)
        self.state = runtime_state or RuntimeState()
        self.heartbeat = heartbeat_monitor or HeartbeatMonitor()
        self.health = health_manager or HealthManager(self.heartbeat, self.state)
        self.cycle_interval = cycle_interval
        self.max_cycles = max_cycles
        self._is_running = False
        self._cycle_count = 0

    @property
    def is_running(self) -> bool:
        return self._is_running

    @property
    def cycle_count(self) -> int:
        return self._cycle_count

    def start(self) -> None:
        """Start the continuous runner."""
        now = datetime.now(timezone.utc).isoformat()
        self.state.set_startup_time(now)
        self.state.set_process_id(__import__("os").getpid())
        self.state.set_current_status("STARTING")
        self._is_running = True
        logger.info("Continuous runner started at %s (max_cycles=%s)", now, self.max_cycles or "unlimited")

    def run_cycle(self) -> dict:
        """Execute one scan cycle.

        Returns:
            Dict with cycle results.
        """
        self._cycle_count += 1
        cycle_num = self._cycle_count
        start_time = time.time()

        try:
            logger.info("Cycle #%d starting", cycle_num)

            # Run strategy
            results = self.runner.run_once()

            # Record heartbeat
            hb = self.heartbeat.beat(status="running", cycle_number=cycle_num)

            # Increment successful cycle
            self.state.increment_cycle(success=True)
            self.state.set_last_heartbeat(hb["timestamp"])

            # Assess health
            health_status = self.health.assess()

            elapsed = time.time() - start_time
            logger.info(
                "Cycle #%d complete: %d symbols, %s, %.1fs",
                cycle_num, len(results), health_status.value, elapsed,
            )

            return {
                "cycle_number": cycle_num,
                "symbols_scanned": len(results),
                "signals": results,
                "heartbeat": hb,
                "health_status": health_status.value,
                "elapsed_seconds": elapsed,
                "success": True,
            }

        except Exception as e:
            logger.error("Cycle #%d failed: %s", cycle_num, e)
            self.state.increment_cycle(success=False)
            self.heartbeat.beat(status="error", cycle_number=cycle_num)
            health_status = self.health.assess()

            return {
                "cycle_number": cycle_num,
                "error": str(e),
                "health_status": health_status.value,
                "success": False,
            }

    def run_continuous(self) -> None:
        """Run continuously until max_cycles or interrupted."""
        self.start()
        try:
            while self._is_running:
                if self.max_cycles > 0 and self._cycle_count >= self.max_cycles:
                    logger.info("Reached max cycles (%d), stopping", self.max_cycles)
                    break

                result = self.run_cycle()
                if not result["success"]:
                    logger.warning("Cycle failed, continuing...")

                if self._is_running and not self._check_exit_condition():
                    logger.info("Sleeping %ds until next cycle...", self.cycle_interval)
                    for _ in range(self.cycle_interval):
                        if not self._is_running:
                            break
                        time.sleep(1)

        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt received, stopping runner")
        finally:
            self.stop()

    def stop(self) -> dict:
        """Stop the continuous runner and persist final state."""
        self._is_running = False
        self.state.set_current_status("STOPPED")
        summary = self.state.get_summary()
        logger.info("Continuous runner stopped. Summary: %s", summary)
        return summary

    def _check_exit_condition(self) -> bool:
        return not self._is_running

    def get_summary(self) -> dict:
        return {
            "running": self._is_running,
            "cycle_count": self._cycle_count,
            "state": self.state.get_summary(),
            "health": self.health.get_summary(),
            "heartbeat": self.heartbeat.get_latest_heartbeat(),
        }