"""Live strategy runner: runs Donchian 20/40 on live Binance Testnet data."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import pandas as pd

from src.exchanges.binance_adapter import BinanceAdapter
from src.exchanges.binance_market_data import BinanceMarketData
from src.live_trading.market_scanner import MarketScanner, MarketSnapshot
from src.live_trading.signal_scheduler import SignalScheduler
from src.live_trading.runner_state import RunnerState

logger = logging.getLogger("live_trading.runner")


class LiveStrategyRunner:
    """Runs Donchian 20/40 strategy on live Binance Testnet data.

    Responsibilities:
    - Pull candles via MarketScanner
    - Run Donchian 20/40 calculation
    - Generate BUY/SELL/HOLD signals
    - Log signals to SQLite
    - Persist runner state

    Does NOT place orders.
    """

    def __init__(
        self,
        adapter: BinanceAdapter,
        market: BinanceMarketData,
        scanner: Optional[MarketScanner] = None,
        scheduler: Optional[SignalScheduler] = None,
        state: Optional[RunnerState] = None,
        entry_period: int = 20,
        exit_period: int = 40,
        interval_seconds: int = 300,
    ) -> None:
        self.adapter = adapter
        self.market = market
        self.scanner = scanner or MarketScanner(adapter, market)
        self.scheduler = scheduler or SignalScheduler(interval_seconds=interval_seconds)
        self.state = state or RunnerState()
        self.entry_period = entry_period
        self.exit_period = exit_period

    def _compute_donchian(self, candles: pd.DataFrame) -> dict:
        """Compute Donchian channel signals.

        Args:
            candles: DataFrame with 'high', 'low', 'close' columns.

        Returns:
            Dict with signal, entry_high, exit_low, close.
        """
        if len(candles) < self.exit_period:
            return {"signal": "HOLD", "reason": "insufficient data"}

        # Donchian entry: highest high of last N bars
        entry_high = candles["high"].iloc[-self.entry_period:].max()
        # Donchian exit: lowest low of last N bars
        exit_low = candles["low"].iloc[-self.exit_period:].min()
        # Current close
        close = candles["close"].iloc[-1]

        if close > entry_high:
            signal = "BUY"
            reason = f"Close {close:.2f} > Entry High {entry_high:.2f}"
        elif close < exit_low:
            signal = "SELL"
            reason = f"Close {close:.2f} < Exit Low {exit_low:.2f}"
        else:
            signal = "HOLD"
            reason = f"Close {close:.2f} between {exit_low:.2f} and {entry_high:.2f}"

        return {
            "signal": signal,
            "reason": reason,
            "entry_high": entry_high,
            "exit_low": exit_low,
            "close": close,
        }

    def run_once(self) -> dict[str, dict]:
        """Run one scan cycle: pull data, compute signals, log results.

        Returns:
            {symbol: signal_result}
        """
        now = datetime.now(timezone.utc).isoformat()
        self.state.set_last_scan_time(now)

        # Scan market
        snapshots = self.scanner.scan()

        results: dict[str, dict] = {}
        for symbol, snapshot in snapshots.items():
            if not snapshot.is_valid:
                results[symbol] = {"signal": "HOLD", "reason": "invalid snapshot"}
                continue

            # Compute Donchian signal
            signal_result = self._compute_donchian(snapshot.candles)
            signal_result["symbol"] = symbol
            signal_result["price"] = snapshot.price
            signal_result["timestamp"] = now

            # Log signal
            self.state.log_signal(
                symbol=symbol,
                signal=signal_result["signal"],
                price=snapshot.price,
                strategy=f"donchian_{self.entry_period}_{self.exit_period}",
            )

            results[symbol] = signal_result
            logger.info(
                "Signal: %s %s @ %.2f (%s)",
                symbol, signal_result["signal"], snapshot.price, signal_result.get("reason", ""),
            )

        # Update state
        self.state.set_last_signal_time(now)
        self.state.set_active_symbols(list(snapshots.keys()))
        self.scheduler.mark_run()

        return results

    def run(self, max_cycles: int = 1) -> list[dict]:
        """Run the strategy for N cycles.

        Args:
            max_cycles: Maximum number of cycles to run.

        Returns:
            List of signal results per cycle.
        """
        all_results = []
        for cycle in range(max_cycles):
            if not self.scheduler.should_run():
                logger.info("Scheduler not ready, skipping cycle %d", cycle + 1)
                continue

            logger.info("Running cycle %d/%d", cycle + 1, max_cycles)
            results = self.run_once()
            all_results.append(results)

        return all_results

    def get_state_summary(self) -> dict:
        """Get current runner state summary."""
        return self.state.get_state_summary()

    def get_signal_history(self, limit: int = 100) -> list[dict]:
        """Get recent signal history."""
        return self.state.get_signal_history(limit=limit)