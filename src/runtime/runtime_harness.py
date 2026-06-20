"""Runtime harness: runs TradingAI continuously on Binance Testnet (SIGNAL_ONLY)."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.runtime.runtime_metrics import RuntimeMetrics

logger = logging.getLogger("runtime.harness")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "runtime_harness_state.db"


class RuntimeHarness:
    """24-hour testnet runtime harness in SIGNAL_ONLY mode.

    Runs every 5 minutes, collects market data, generates signals.
    No order placement.
    Persists metrics and state every cycle.
    """

    def __init__(
        self,
        max_cycles: int = 0,
        cycle_interval: int = 300,
        symbols: Optional[list[str]] = None,
        mode: str = "SIGNAL_ONLY",
        db_path: Optional[Path] = None,
    ) -> None:
        self.max_cycles = max_cycles
        self.cycle_interval = cycle_interval
        self.symbols = symbols or ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
        self.mode = mode
        self.db_path = db_path or DEFAULT_DB_PATH
        self.metrics = RuntimeMetrics()
        self._is_running = False
        self._state: dict = {"last_cycle": 0, "status": "INIT"}
        self._adapter = None
        self._market = None
        self._live_runner = None

    def _init_components(self) -> None:
        from src.exchanges.binance_adapter import BinanceAdapter
        from src.exchanges.binance_market_data import BinanceMarketData
        from src.live_trading.live_strategy_runner import LiveStrategyRunner
        from src.position_management.position_manager import PositionManager
        from src.position_management.portfolio_limits import PortfolioLimits
        from src.position_management.portfolio_snapshot import PortfolioSnapshot
        from src.position_management.exposure_tracker import ExposureTracker
        from src.position_management.risk_gatekeeper import RiskGatekeeper
        from src.execution.idempotency_manager import IdempotencyManager
        from src.execution.execution_engine import ExecutionEngine

        self._adapter = BinanceAdapter()
        self._market = BinanceMarketData(self._adapter)
        self._live_runner = LiveStrategyRunner(self._adapter, self._market)
        
        self._position_mgr = PositionManager()
        self._limits = PortfolioLimits()
        self._snapshot = PortfolioSnapshot(self._position_mgr)
        self._exposure = ExposureTracker(self._position_mgr)
        self._gatekeeper = RiskGatekeeper(self._position_mgr, self._exposure, self._snapshot, self._limits)
        self._idempotency = IdempotencyManager()
        self._execution = ExecutionEngine(self._adapter, self._market)

    def _persist_state(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.db_path, "w") as f:
            json.dump(self._state, f)

    def _load_state(self) -> dict:
        if self.db_path.exists():
            with open(self.db_path) as f:
                return json.load(f)
        return {}

    def _run_cycle(self, cycle: int) -> dict:
        """Execute one scan cycle."""
        try:
            self._live_runner.scanner.symbols = self.symbols
            results = self._live_runner.run_once()
            signals = sum(1 for r in results.values() if r.get("signal") in ("BUY", "SELL"))
            
            # Full Execution Mode Logic
            if self.mode == "EXECUTION":
                for symbol, data in results.items():
                    sig = data.get("signal")
                    if sig in ("BUY", "SELL"):
                        price = data.get("price", 0.0)
                        qty = 0.001 if symbol == "BTCUSDT" else (0.01 if symbol == "ETHUSDT" else 0.1)
                        client_order_id = self._idempotency.generate_client_order_id(symbol, sig, qty, "harness")
                        fingerprint = f"{symbol}_{sig}_{qty}_harness"
                        
                        # Idempotency Gate
                        if not self._idempotency.is_duplicate(client_order_id):
                            self._idempotency.register_pending(client_order_id, symbol, sig, qty, fingerprint)
                            
                            # Risk Gatekeeper Gate
                            balance_dict = self._adapter.get_account_balance()
                            usdt_free = balance_dict.get("USDT", {}).get("free", 0.0)
                            decision = self._gatekeeper.evaluate(symbol, sig, qty, price, usdt_free)
                            
                            if decision.approved:
                                print(f"[INFO] Signal APPROVED. Placing REAL testnet order for {symbol} {sig} qty={qty} via ExecutionEngine...")
                                exec_res = self._execution.execute_signal(symbol, sig, qty, "donchian")
                                if exec_res.order_id:
                                    self._idempotency.mark_submitted(client_order_id, exec_res.order_id)
                                    self._position_mgr.open_position(symbol, qty, price, "donchian")
                            else:
                                print(f"[WARNING] Risk Gatekeeper REJECTED signal: {decision.reason}")
                                self._idempotency.mark_failed(client_order_id, decision.reason)
            
            self.metrics.record_cycle(cycle, success=True, signals=signals, details=results)
            self._state["last_cycle"] = cycle
            self._state["status"] = "RUNNING"
            logger.info("Cycle %d: %d signals from %d symbols", cycle, signals, len(results))
            return results
        except Exception as e:
            logger.error("Cycle %d failed: %s", cycle, e)
            self.metrics.record_cycle(cycle, success=False, api_errors=1, details={"error": str(e)})
            return {"error": str(e)}

    def start(self) -> dict:
        """Run the harness for max_cycles or until interrupted."""
        self._is_running = True
        self._state["start_time"] = datetime.now(timezone.utc).isoformat()
        self._state["status"] = "RUNNING"
        self._persist_state()

        print("=" * 60)
        print("  TRADINGAI RUNTIME HARNESS STARTING")
        print(f"  Mode: {self.mode}")
        print(f"  Symbols: {self.symbols}")
        print(f"  Interval: {self.cycle_interval}s")
        print("=" * 60)

        try:
            self._init_components()
            self.metrics.record_heartbeat()
            logger.info("Runtime harness started: mode=%s, symbols=%s", self.mode, self.symbols)
            print("[INFO] Runtime harness started and components initialized successfully.")

            cycle = 1
            while self._is_running:
                if self.max_cycles > 0 and cycle > self.max_cycles:
                    break
                self._run_cycle(cycle)
                print(f"[INFO] Cycle {cycle} completed successfully.")
                self.metrics.record_heartbeat()
                self._state["last_cycle"] = cycle
                self._persist_state()
                if self._is_running and (self.max_cycles == 0 or cycle < self.max_cycles):
                    time.sleep(self.cycle_interval)
                cycle += 1

        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt: stopping harness")
            print("\n[INFO] KeyboardInterrupt received. Gracefully shutting down...")
        finally:
            self.stop()

        return self.get_results()

    def stop(self) -> dict:
        self._is_running = False
        self._state["status"] = "STOPPED"
        self._state["stop_time"] = datetime.now(timezone.utc).isoformat()
        self._persist_state()
        logger.info("Runtime harness stopped")
        print("=" * 60)
        print("  RUNTIME HARNESS SHUTDOWN COMPLETE")
        print("=" * 60)
        return self.get_results()

    def get_results(self) -> dict:
        summary = self.metrics.get_summary()
        return {
            "mode": self.mode,
            "symbols": self.symbols,
            "cycle_interval_s": self.cycle_interval,
            "summary": summary,
            "hourly": self.metrics.get_hourly(),
            "daily": self.metrics.get_daily(),
            "state": self._state,
        }

if __name__ == "__main__":
    import sys
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )

    # Production Defaults (Run forever, every 5 minutes/300 seconds)
    cycles = 0
    interval = 300

    # Command line overrides
    if "--once" in sys.argv:
        cycles = 1
        interval = 0
        print("[INFO] Running in ONCE mode (1 cycle, 0s interval).")
    elif "--verify" in sys.argv:
        cycles = 3
        interval = 2
        print("[INFO] Running in VERIFY mode (3 cycles, 2s interval).")
    else:
        print("[INFO] Running in PRODUCTION mode (Continuous, 300s interval).")

    harness = RuntimeHarness(max_cycles=cycles, cycle_interval=interval)
    harness.start()
