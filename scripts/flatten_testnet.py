"""Quick flatten: sell BTCUSDT from pre-existing testnet position (from aborted smoke test)."""

from __future__ import annotations
import json, logging, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

from src.exchanges.binance_adapter import BinanceAdapter
from src.exchanges.binance_market_data import BinanceMarketData
from src.execution.execution_engine import ExecutionEngine
from src.execution.idempotency_manager import IdempotencyManager
from src.position_management.position_manager import PositionManager

adapter = BinanceAdapter()
market = BinanceMarketData(adapter)
pm = PositionManager()
idempotency = IdempotencyManager()
engine = ExecutionEngine(adapter, market)

print("=" * 60)
print("  FLATTEN SCRIPT — Sell testnet BTCUSDT position")
print("=" * 60)

price_data = market.get_ticker_price("BTCUSDT")
price = price_data["price"]
balance = adapter.get_account_balance()
btc = balance.get("BTC", {}).get("free", 0.0)
print("  BTC free: %.8f | Price: $%.2f" % (btc, price))

if btc > 0:
    qty = btc  # sell all
    cid = idempotency.generate_client_order_id("BTCUSDT", "SELL", qty, "flatten")
    if not idempotency.is_duplicate(cid):
        idempotency.register_pending(cid, "BTCUSDT", "SELL", qty, "flatten_all")
        print("  Placing SELL %.8f BTCUSDT on Testnet..." % qty)
        res = engine.execute_signal("BTCUSDT", "SELL", qty, "flatten")
        s = res.status.value if hasattr(res.status, 'value') else res.status
        print("  Order ID: %s" % res.order_id)
        print("  Status: %s" % s)
        print("  Filled: %.8f @ $%.2f" % (res.filled_qty, res.price))
        if isinstance(s, str) and s.upper() in ("FILLED", "PARTIALLY_FILLED"):
            idempotency.mark_submitted(cid, res.order_id)
            pm.close_position("BTCUSDT", res.filled_qty, res.price)
            print("  [OK] Position closed.")
        else:
            print("  [WARN] SELL not fully filled. Raw: %s" % json.dumps(res.raw_response, indent=2))
    else:
        print("  [WARN] Duplicate SELL ID.")
else:
    print("  No BTC balance to sell.")
print("Done.")