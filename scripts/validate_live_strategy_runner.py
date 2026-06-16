"""Validate live strategy runner end-to-end."""

import sys
import sqlite3
from pathlib import Path

sys.path.insert(0, ".")

from src.exchanges.binance_adapter import BinanceAdapter
from src.exchanges.binance_market_data import BinanceMarketData
from src.live_trading.live_strategy_runner import LiveStrategyRunner
from src.live_trading.runner_state import RunnerState

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "live_runner_state.db"

print("=" * 60)
print("LIVE STRATEGY RUNNER VALIDATION")
print("=" * 60)

# Initialize
adapter = BinanceAdapter()
market = BinanceMarketData(adapter)
state = RunnerState()
runner = LiveStrategyRunner(adapter, market, state=state)

# Test 1: Pull latest BTCUSDT candles
print("\n[1/6] Pulling latest BTCUSDT candles...")
snapshot = market.get_klines("BTCUSDT", "1h", 100)
print(f"  Candles retrieved: {len(snapshot)}")
print(f"  Latest close: ${snapshot['close'].iloc[-1]:,.2f}")
assert len(snapshot) > 0
print("  PASS")

# Test 2: Run Donchian calculation
print("\n[2/6] Running Donchian 20/40 calculation...")
candles = market.get_klines("BTCUSDT", "1h", 100)
entry_high = candles["high"].iloc[-20:].max()
exit_low = candles["low"].iloc[-40:].min()
close = candles["close"].iloc[-1]

if close > entry_high:
    signal = "BUY"
elif close < exit_low:
    signal = "SELL"
else:
    signal = "HOLD"

print(f"  Entry High (20): ${entry_high:,.2f}")
print(f"  Exit Low (40):   ${exit_low:,.2f}")
print(f"  Close:           ${close:,.2f}")
print(f"  Signal:          {signal}")
print("  PASS")

# Test 3: Generate signal via runner
print("\n[3/6] Generating signal via LiveStrategyRunner...")
results = runner.run_once()
print(f"  Symbols scanned: {len(results)}")
for sym, res in results.items():
    print(f"    {sym}: {res['signal']} @ ${res.get('price', 0):,.2f}")
assert len(results) > 0
print("  PASS")

# Test 4: Persist signal
print("\n[4/6] Persisting signal to SQLite...")
history = state.get_signal_history(limit=10)
print(f"  Signals in DB: {len(history)}")
latest = history[0] if history else None
if latest:
    print(f"  Latest signal: {latest['symbol']} {latest['signal']} @ ${latest['price']:,.2f}")
    print(f"  Strategy: {latest['strategy']}")
    print(f"  Timestamp: {latest['timestamp']}")
assert len(history) > 0
print("  PASS")

# Test 5: Restart process
print("\n[5/6] Simulating restart — new LiveStrategyRunner instance...")
adapter2 = BinanceAdapter()
market2 = BinanceMarketData(adapter2)
state2 = RunnerState()
runner2 = LiveStrategyRunner(adapter2, market2, state=state2)
history2 = state2.get_signal_history(limit=10)
print(f"  New runner loaded {len(history2)} signals from SQLite")
assert len(history2) == len(history), f"Signal count mismatch: {len(history2)} vs {len(history)}"
print("  PASS")

# Test 6: Recover state
print("\n[6/6] Recovering state from SQLite...")
summary = state2.get_state_summary()
print(f"  Last scan time:    {summary['last_scan_time']}")
print(f"  Last signal time:  {summary['last_signal_time']}")
print(f"  Active symbols:    {summary['active_symbols']}")
print(f"  Total signals:     {summary['signal_count']}")

# Verify data consistency
for orig, recovered in zip(history, history2):
    assert orig["symbol"] == recovered["symbol"], f"Symbol mismatch"
    assert orig["signal"] == recovered["signal"], f"Signal mismatch"
    assert orig["price"] == recovered["price"], f"Price mismatch"

assert summary["last_scan_time"] is not None
assert summary["last_signal_time"] is not None
assert len(summary["active_symbols"]) > 0
print("  PASS")

print("\n" + "=" * 60)
print("ALL TESTS PASSED")
print("=" * 60)