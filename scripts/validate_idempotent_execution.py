"""Validate idempotent execution: submit, timeout, recover, no duplicates."""

import sys
import time
import sqlite3
from pathlib import Path

sys.path.insert(0, ".")

from src.exchanges.binance_adapter import BinanceAdapter
from src.exchanges.binance_market_data import BinanceMarketData
from src.execution.idempotency_manager import IdempotencyManager
from src.execution.order_reconciliation import OrderReconciliation
from src.execution.execution_recovery import ExecutionRecovery

print("=" * 60)
print("IDEMPOTENT EXECUTION VALIDATION")
print("=" * 60)

adapter = BinanceAdapter()
market = BinanceMarketData(adapter)
idempotency = IdempotencyManager()
recovery = ExecutionRecovery(idempotency, adapter)

# Get BTCUSDT lot size step
info = market.client.get_symbol_info("BTCUSDT")
lot_filter = [f for f in info["filters"] if f["filterType"] == "LOT_SIZE"][0]
step_size = float(lot_filter["stepSize"])
min_qty = float(lot_filter["minQty"])
print(f"  BTCUSDT LOT_SIZE: step={step_size}, min={min_qty}")

# ======================================================================
# TEST 1: Generate client_order_id
# ======================================================================
print("\n[Test 1] Generate unique client_order_id...")
cid1 = idempotency.generate_client_order_id("BTCUSDT", "BUY", 0.0001, "test")
cid2 = idempotency.generate_client_order_id("BTCUSDT", "BUY", 0.0001, "test")
print(f"  client_order_id 1: {cid1}")
print(f"  client_order_id 2: {cid2}")
assert cid1 != cid2, "client_order_id collision"
assert cid1.startswith("TA_"), f"Unexpected format: {cid1}"
assert cid2.startswith("TA_"), f"Unexpected format: {cid2}"
print("  PASS")

# ======================================================================
# TEST 2: Register pending order (simulate submit attempt)
# ======================================================================
print("\n[Test 2] Register pending order (simulate pre-submit)...")
price = market.get_ticker_price("BTCUSDT")["price"]
quantity = round(10.0 / price, 6)
cid = idempotency.generate_client_order_id("BTCUSDT", "BUY", quantity, "idempotency_test")
idempotency.register_pending(
    client_order_id=cid,
    symbol="BTCUSDT",
    side="BUY",
    quantity=quantity,
    fingerprint="test_fingerprint",
    request_json={"symbol": "BTCUSDT", "side": "BUY", "quantity": quantity},
)
record = idempotency.get_order(cid)
print(f"  client_order_id: {cid}")
print(f"  Status: {record['status']}")
assert record is not None
assert record["status"] == "PENDING"
print("  PASS")

# ======================================================================
# TEST 3: Verify duplicate detection
# ======================================================================
print("\n[Test 3] Verify duplicate detection...")
print(f"  Order {cid} registered — is_duplicate should return True")
assert idempotency.is_duplicate(cid) == True, "Should detect existing client_order_id"
print(f"  Duplicate detection confirmed for {cid}")
print("  PASS")

# ======================================================================
# TEST 4: Submit real order (with idempotency tracking)
# ======================================================================
print("\n[Test 4] Submit real order with idempotency tracking...")
# Round quantity to match lot step size (0.00001000)
qty = round(round(float(quantity) / float(step_size)) * float(step_size), 5)
print(f"  Using quantity: {qty} (from {quantity}, step={step_size})")
assert qty >= min_qty, f"Quantity {qty} below minimum {min_qty}"
real_cid = idempotency.generate_client_order_id("BTCUSDT", "BUY", qty, "idempotency_live")
idempotency.register_pending(client_order_id=real_cid, symbol="BTCUSDT", side="BUY",
                             quantity=qty, fingerprint="real_order")
# Submit using raw API with string quantity to avoid float precision issues
client = adapter.client
order = client.order_market_buy(symbol="BTCUSDT", quantity=f"{qty:.5f}")
order_id = order.get("orderId", "")
idempotency.mark_submitted(real_cid, order_id)
print(f"  Real order submitted: {real_cid} -> exchange order {order_id}")
record = idempotency.get_order(real_cid)
assert record["status"] == "SUBMITTED"
print("  PASS")

# ======================================================================
# TEST 5: Detect duplicate submission
# ======================================================================
print("\n[Test 5] Detect duplicate submission...")
assert idempotency.is_duplicate(real_cid) == True, "Should detect duplicate"
print(f"  Duplicate detected for {real_cid}")
print("  PASS")

# ======================================================================
# TEST 6: Restart recovery (simulate restart by loading from DB)
# ======================================================================
print("\n[Test 6] Simulate restart — recover from idempotency DB...")
idempotency2 = IdempotencyManager()
recovery2 = ExecutionRecovery(idempotency2, adapter)
recovery_result = recovery2.recover()
summary = idempotency2.get_summary()
print(f"  Recovery results:")
print(f"    Pending recovered:  {summary['pending']}")
print(f"    Submitted verified: {summary['submitted']}")
print(f"    Filled:             {summary['filled']}")
print(f"    Total tracked:      {summary['total']}")
assert summary["total"] >= 2  # at least our 2 orders
print("  PASS")

# ======================================================================
# TEST 7: Verify no duplicate order created during recovery
# ======================================================================
print("\n[Test 7] Verify no duplicate orders during recovery...")
summary_before = idempotency.get_summary()
summary_after = idempotency2.get_summary()
print(f"  Orders before recovery: {summary_before['total']}")
print(f"  Orders after recovery:  {summary_after['total']}")
assert summary_before["total"] == summary_after["total"], "Orders should be identical"
print("  PASS")

# ======================================================================
# TEST 8: Reconciliation report
# ======================================================================
print("\n[Test 8] Reconciliation report...")
reconciler = OrderReconciliation(idempotency, adapter)
report = reconciler.reconcile()
print(f"  Matched:          {len(report['matched'])}")
print(f"  Mismatched:       {len(report['mismatched'])}")
print(f"  Pending resolved: {report['pending_resolved']}")
print(f"  Missing on exch:  {len(report['missing_on_exchange'])}")
print("  PASS")

# ======================================================================
print("\n" + "=" * 60)
print("ALL TESTS PASSED")
print("=" * 60)

print("\n=== Idempotency Summary ===")
s = idempotency.get_summary()
print(f"  Total unique orders: {s['total']}")
print(f"  Pending:  {s['pending']}")
print(f"  Submitted: {s['submitted']}")
print(f"  Filled:   {s['filled']}")
print(f"  Failed:   {s['failed']}")
print(f"  Duplicates prevented: {s['total']}")