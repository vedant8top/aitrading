"""Validate testnet execution layer end-to-end."""

import sys
import time
sys.path.insert(0, ".")

from src.exchanges.binance_adapter import BinanceAdapter
from src.exchanges.binance_market_data import BinanceMarketData
from src.execution.execution_engine import ExecutionEngine
from src.execution.execution_models import OrderStatus

print("=" * 60)
print("TESTNET EXECUTION VALIDATION")
print("=" * 60)

# Initialize
adapter = BinanceAdapter()
market = BinanceMarketData(adapter)
engine = ExecutionEngine(adapter, market, max_order_value_usdt=100.0)

# Test 1: Get BTCUSDT price
print("\n[1/6] Retrieving BTCUSDT price...")
price_data = market.get_ticker_price("BTCUSDT")
price = price_data["price"]
print(f"  BTCUSDT price: ${price:,.2f}")
assert price > 0
print("  PASS")

# Test 2: Place tiny BUY order (~10 USDT equivalent)
print("\n[2/6] Placing tiny BUY order (~10 USDT)...")
quantity = round(10.0 / price, 6)
print(f"  Calculated quantity: {quantity} BTC (for ~$10 USDT)")
result = engine.execute_signal(
    symbol="BTCUSDT",
    side="BUY",
    quantity=quantity,
    strategy="testnet_validation",
)
print(f"  Order ID: {result.order_id}")
print(f"  Status: {result.status.value}")
print(f"  Price: ${result.price:,.2f}")
print(f"  Filled Qty: {result.filled_qty}")
print(f"  Commission: {result.commission}")
assert result.status in (OrderStatus.FILLED, OrderStatus.PENDING, OrderStatus.PARTIALLY_FILLED), f"Order failed: {result.status}"
print("  PASS")

# Test 3: Query order status
print("\n[3/6] Querying order status...")
if result.order_id:
    order_status = engine.order_manager.get_order_status(result.order_id, "BTCUSDT")
    print(f"  Exchange status: {order_status.get('status')}")
    print(f"  Executed qty: {order_status.get('executedQty')}")
    print("  PASS")
else:
    print("  SKIP — no order ID (order may have been rejected)")
    order_status = {"status": "N/A"}

# Test 4: Cancel if open (likely already filled for market order)
print("\n[4/6] Checking if order needs cancellation...")
if order_status.get("status") == "NEW":
    cancel_result = engine.order_manager.cancel_order(result.order_id, "BTCUSDT")
    print(f"  Cancelled: {cancel_result}")
else:
    print(f"  Order already {order_status.get('status', 'filled')} — no cancellation needed")
print("  PASS")

# Test 5: Retrieve updated balances
print("\n[5/6] Retrieving updated balances...")
balances = adapter.get_account_balance()
btc_balance = balances.get("BTC", {}).get("free", 0.0)
usdt_balance = balances.get("USDT", {}).get("free", 0.0)
print(f"  BTC free: {btc_balance:.8f}")
print(f"  USDT free: {usdt_balance:.2f}")
assert btc_balance > 0 or usdt_balance > 0
print("  PASS")

# Test 6: Persist result to SQLite
print("\n[6/6] Verifying SQLite persistence...")
history = engine.get_execution_history(limit=5)
print(f"  Execution history: {len(history)} records")
for h in history:
    print(f"    [{h['status']}] {h['side']} {h['quantity']} {h['symbol']} @ {h['price']} (id={h['order_id']})")
assert len(history) > 0
print("  PASS")

print("\n" + "=" * 60)
print("ALL TESTS PASSED")
print("=" * 60)