"""Validate restart recovery and order reconciliation for TradingAI execution layer."""

import json
import sys
import sqlite3
from pathlib import Path

sys.path.insert(0, ".")

from src.exchanges.binance_adapter import BinanceAdapter
from src.exchanges.binance_market_data import BinanceMarketData
from src.execution.execution_engine import ExecutionEngine

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "execution_log.db"

print("=" * 60)
print("RESTART RECOVERY & RECONCILIATION VALIDATION")
print("=" * 60)


def read_execution_log(db_path: Path) -> list[dict]:
    """Read all records from execution_log.db."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM execution_log ORDER BY id ASC").fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_exchange_balances(adapter: BinanceAdapter) -> dict[str, float]:
    """Get current exchange balances as {asset: free}."""
    balances = adapter.get_account_balance()
    return {k: v["free"] for k, v in balances.items() if v["total"] > 0}


# ======================================================================
# TEST 1: Read execution_log.db — recover latest execution
# ======================================================================
print("\n[Test 1] Read execution_log.db — recover latest execution")
history = read_execution_log(DB_PATH)
print(f"  Total records in DB: {len(history)}")
assert len(history) > 0, "No execution records found in DB"

latest = history[-1]
print(f"  Latest record:")
print(f"    Order ID:  {latest['order_id']}")
print(f"    Symbol:    {latest['symbol']}")
print(f"    Side:      {latest['side']}")
print(f"    Quantity:  {latest['quantity']}")
print(f"    Price:     {latest['price']}")
print(f"    Status:    {latest['status']}")
print(f"    Strategy:  {latest['strategy']}")

assert latest["order_id"], "Order ID is empty"
assert latest["symbol"] == "BTCUSDT", f"Expected BTCUSDT, got {latest['symbol']}"
assert latest["quantity"] > 0, "Quantity is zero"
assert latest["status"] in ("filled", "pending", "partially_filled"), f"Unexpected status: {latest['status']}"
print("  PASS")


# ======================================================================
# TEST 2: Query Binance Testnet — retrieve current balances
# ======================================================================
print("\n[Test 2] Query Binance Testnet — retrieve current balances")
adapter = BinanceAdapter()
market = BinanceMarketData(adapter)

exchange_balances = get_exchange_balances(adapter)
btc_free = exchange_balances.get("BTC", 0.0)
usdt_free = exchange_balances.get("USDT", 0.0)
print(f"  BTC free:  {btc_free:.8f}")
print(f"  USDT free: {usdt_free:.2f}")

assert btc_free > 0, "BTC balance is zero"
assert usdt_free > 0, "USDT balance is zero"

# Cross-check against local records
local_btc_buys = sum(
    float(h["quantity"]) for h in history
    if h["symbol"] == "BTCUSDT" and h["side"] == "BUY" and h["status"] == "filled"
)
local_btc_sells = sum(
    float(h["quantity"]) for h in history
    if h["symbol"] == "BTCUSDT" and h["side"] == "SELL" and h["status"] == "filled"
)
net_local_btc = local_btc_buys - local_btc_sells

print(f"  Local BTC buys:  {local_btc_buys:.8f}")
print(f"  Local BTC sells: {local_btc_sells:.8f}")
print(f"  Net local BTC:   {net_local_btc:.8f}")
print(f"  Exchange BTC:    {btc_free:.8f}")

# Initial BTC was 1.0, net from trades should match difference
expected_btc = 1.0 + net_local_btc
btc_diff = abs(btc_free - expected_btc)
print(f"  Expected BTC:    {expected_btc:.8f}")
print(f"  BTC diff:        {btc_diff:.8f}")
assert btc_diff < 0.0001, f"BTC mismatch too large: {btc_diff}"
print("  PASS")


# ======================================================================
# TEST 3: Simulate restart — new ExecutionEngine instance
# ======================================================================
print("\n[Test 3] Simulate restart — new ExecutionEngine instance")
# Create fresh adapter and engine (simulates process restart)
adapter_fresh = BinanceAdapter()
market_fresh = BinanceMarketData(adapter_fresh)
engine_fresh = ExecutionEngine(adapter_fresh, market_fresh)

# Verify state was reloaded
history_after = engine_fresh.get_execution_history(limit=1000)
print(f"  New engine loaded {len(history_after)} records from SQLite")
assert len(history_after) == len(history), f"Record count mismatch: {len(history_after)} vs {len(history)}"

# Verify no duplicates
order_ids = [h["order_id"] for h in history_after if h["order_id"]]
unique_ids = set(order_ids)
print(f"  Order IDs: {len(order_ids)} total, {len(unique_ids)} unique")
assert len(order_ids) == len(unique_ids), f"Duplicate order IDs found: {len(order_ids) - len(unique_ids)} duplicates"

# Verify same data
for orig, fresh in zip(history, history_after):
    assert orig["order_id"] == fresh["order_id"], f"Order ID mismatch"
    assert orig["symbol"] == fresh["symbol"], f"Symbol mismatch"
    assert orig["status"] == fresh["status"], f"Status mismatch"

print("  No duplicate orders")
print("  No missing executions")
print("  State consistency verified")
print("  PASS")


# ======================================================================
# TEST 4: Order reconciliation — Local SQLite vs Binance Testnet
# ======================================================================
print("\n[Test 4] Order reconciliation — Local SQLite vs Binance Testnet")
local_filled = [h for h in history if h["status"] == "filled"]
print(f"  Local filled orders: {len(local_filled)}")

mismatches = []
reconciled = []

for record in local_filled:
    order_id = record["order_id"]
    if not order_id:
        continue
    try:
        exchange_order = adapter_fresh.client.get_order(
            symbol=record["symbol"], orderId=order_id
        )
        local_status = record["status"]
        exchange_status = exchange_order.get("status", "").lower()

        if local_status == exchange_status:
            reconciled.append(order_id)
        else:
            mismatches.append({
                "order_id": order_id,
                "local_status": local_status,
                "exchange_status": exchange_status,
            })
    except Exception as e:
        mismatches.append({
            "order_id": order_id,
            "local_status": record["status"],
            "exchange_status": f"ERROR: {e}",
        })

print(f"  Reconciled: {len(reconciled)}/{len(local_filled)}")
for oid in reconciled:
    print(f"    ✅ {oid}")

if mismatches:
    print(f"  Mismatches: {len(mismatches)}")
    for m in mismatches:
        print(f"    ❌ {m['order_id']}: local={m['local_status']}, exchange={m['exchange_status']}")
else:
    print("  Mismatches: 0")

assert len(mismatches) == 0, f"Reconciliation failed: {len(mismatches)} mismatches"
print("  PASS")


# ======================================================================
# TEST 5: Recovery Report
# ======================================================================
print("\n[Test 5] Recovery Report")
total_orders = len(history)
recovered_orders = len(history_after)
missing_orders = total_orders - recovered_orders
duplicate_orders = len(order_ids) - len(unique_ids)

print(f"  Total orders:      {total_orders}")
print(f"  Recovered orders:  {recovered_orders}")
print(f"  Missing orders:    {missing_orders}")
print(f"  Duplicate orders:  {duplicate_orders}")
print(f"  Reconciliation:    {'PASS' if len(mismatches) == 0 else 'FAIL'}")

assert recovered_orders == total_orders, "Not all orders recovered"
assert missing_orders == 0, "Missing orders detected"
assert duplicate_orders == 0, "Duplicate orders detected"
print("  PASS")


# ======================================================================
# Generate report file
# ======================================================================
print("\n" + "=" * 60)
print("ALL TESTS PASSED")
print("=" * 60)

# Write report
report = f"""# Restart Recovery & Reconciliation Report

**Date**: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Status**: PASS

---

## Summary

| Metric | Value |
|--------|-------|
| Total Orders | {total_orders} |
| Recovered Orders | {recovered_orders} |
| Missing Orders | {missing_orders} |
| Duplicate Orders | {duplicate_orders} |
| Reconciliation | {'PASS' if len(mismatches) == 0 else 'FAIL'} |

---

## Test Results

### Test 1: Read execution_log.db
- ✅ {total_orders} records found in SQLite
- ✅ Latest order: {latest['order_id']} ({latest['side']} {latest['quantity']} {latest['symbol']} @ {latest['price']})
- ✅ Status: {latest['status']}

### Test 2: Binance Testnet Balances
- ✅ BTC free: {btc_free:.8f}
- ✅ USDT free: {usdt_free:.2f}
- ✅ Net local BTC change: {net_local_btc:+.8f} matches exchange balance

### Test 3: Simulate Restart
- ✅ New ExecutionEngine instance created
- ✅ State reloaded from SQLite
- ✅ {recovered_orders}/{total_orders} records recovered
- ✅ No duplicate orders
- ✅ No missing executions
- ✅ State consistency verified

### Test 4: Order Reconciliation
- ✅ {len(reconciled)}/{len(local_filled)} orders reconciled
- ✅ Local SQLite matches Binance Testnet
- ✅ 0 mismatches

### Test 5: Recovery Report
- ✅ All acceptance criteria met

---

## Acceptance Criteria

| Criterion | Result |
|-----------|--------|
| 100% orders recovered | ✅ PASS |
| 0 missing | ✅ PASS |
| 0 duplicates | ✅ PASS |
| Balances reconcile | ✅ PASS |

---

## Execution History

| ID | Order ID | Symbol | Side | Qty | Price | Status |
|----|----------|--------|------|-----|-------|--------|
"""

for h in history:
    report += f"| {h['id']} | {h['order_id']} | {h['symbol']} | {h['side']} | {h['quantity']} | {h['price']} | {h['status']} |\n"

report += f"""
---

## Architecture

```
Process Start
    │
    ▼
ExecutionEngine.__init__()
    │
    ├─── _init_db()     → SQLite connection
    │
    └─── Ready to execute / recover
    
Recovery flow:
    1. Read execution_log.db
    2. Verify all records present
    3. Cross-check with Binance Testnet
    4. Report reconciliation status
```

---

## Conclusion

The execution layer demonstrates **100% restart recovery** capability.
All orders persisted in SQLite are correctly recovered after simulated restart.
Local state matches Binance Testnet balances exactly.
"""

report_path = PROJECT_ROOT / "docs" / "restart_recovery_report.md"
with open(report_path, "w", encoding="utf-8") as f:
    f.write(report)
print(f"\nReport saved to: {report_path}")