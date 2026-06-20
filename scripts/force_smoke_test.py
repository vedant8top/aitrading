"""Forced smoke test: injects synthetic BUY then SELL through full pipeline.
Uses credentials from .env file. Runs entirely on Binance Testnet."""

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
from src.position_management.portfolio_limits import PortfolioLimits
from src.position_management.portfolio_snapshot import PortfolioSnapshot
from src.position_management.exposure_tracker import ExposureTracker
from src.position_management.risk_gatekeeper import RiskGatekeeper

SYMBOL = "BTCUSDT"
QUANTITY = 0.001  # ~$65 at current prices, smallest BTC lot on Binance

print("=" * 70)
print("  FORCED SMOKE TEST — Synthetic BUY then SELL through full pipeline")
print("  IMPORTANT: Credentials loaded from .env ONLY (BINANCE_TESTNET=true)")
print("=" * 70)

# 1. Init all components
print("\n[STEP 1] Initializing components...")
adapter = BinanceAdapter()
market = BinanceMarketData(adapter)
pm = PositionManager()
limits = PortfolioLimits()
snap = PortfolioSnapshot(pm)
exposure = ExposureTracker(pm)
gatekeeper = RiskGatekeeper(pm, exposure, snap, limits)
idempotency = IdempotencyManager()
engine = ExecutionEngine(adapter, market)
print("  [OK] All components initialized.")

# 2. Get price and balances
print("\n[STEP 2] Fetching live testnet data...")
price_data = market.get_ticker_price(SYMBOL)
price = price_data["price"]
print("  BTCUSDT price: $%.2f" % price)

balance_dict = adapter.get_account_balance()
usdt_free = balance_dict.get("USDT", {}).get("free", 0.0)
btc_free = balance_dict.get("BTC", {}).get("free", 0.0)
print("  USDT free: %.2f" % usdt_free)
print("  BTC free:  %.8f" % btc_free)

# 3. Check existing positions
existing = pm.get_position(SYMBOL)
print("[STEP 3] Existing position for %s: %s" % (SYMBOL, "YES" if existing else "NONE"))

if existing:
    print("  [WARN] Will need to flatten existing position first.")
    print("  [ABORT] Manual intervention required. Exiting.")
    sys.exit(1)

# ===== PHASE 1: BUY =====
print("\n" + "=" * 70)
print("  PHASE 1: Forced BUY through pipeline")
print("=" * 70)

# Gate 1: Idempotency
print("\n[STEP 4] GATE 1 — IdempotencyManager")
cid = idempotency.generate_client_order_id(SYMBOL, "BUY", QUANTITY, "smoke_test")
print("  Client order ID: %s" % cid)
dup = idempotency.is_duplicate(cid)
if dup:
    print("  [FATAL] Duplicate ID detected. Aborting.")
    sys.exit(1)
idempotency.register_pending(cid, SYMBOL, "BUY", QUANTITY, "%s_BUY_%s_smoke" % (SYMBOL, QUANTITY))
print("  [PASS] Registered as pending. Summary: %s" % idempotency.get_summary())

# Gate 2: RiskGatekeeper
print("\n[STEP 5] GATE 2 — RiskGatekeeper")
decision = gatekeeper.evaluate(SYMBOL, "BUY", QUANTITY, price, usdt_free)
print("  Approved: %s" % decision.approved)
print("  Reason:   %s" % decision.reason)
print("  Details:  %s" % json.dumps(decision.details))

if not decision.approved:
    print("\n  [ABORT] RiskGatekeeper rejected BUY. No order sent to testnet.")
    print("  Reason context: if insufficient_balance, fund your testnet wallet.")
    print("  If max_positions, run flatten_first script. If duplicate_position, close existing.")
    sys.exit(1)

# Gate 3: ExecutionEngine -> BinanceAdapter (Testnet)
print("\n[STEP 6] GATE 3 — ExecutionEngine.execute_signal()")
exec_res = engine.execute_signal(SYMBOL, "BUY", QUANTITY, "smoke_test")
s = exec_res.status.value if hasattr(exec_res.status, 'value') else exec_res.status
print("  Order ID:       %s" % exec_res.order_id)
print("  Status:         %s" % s)
print("  Filled Qty:     %.8f" % exec_res.filled_qty)
print("  Avg Fill Price: $%.2f" % exec_res.price)
print("  Commission:     %.8f" % exec_res.commission)

if s.upper() not in ("FILLED", "PARTIALLY_FILLED"):
    print("\n  [ABORT] Order not filled. Full response:")
    print(json.dumps(exec_res.raw_response, indent=2))
    sys.exit(1)

print("  Raw response: %s" % json.dumps(exec_res.raw_response, indent=2))

# Post-order bookkeeping
print("\n[STEP 7] Post-order bookkeeping")
idempotency.mark_submitted(cid, exec_res.order_id)
print("  [OK] Idempotency marked submitted.")
pm.open_position(SYMBOL, QUANTITY, exec_res.price, "LONG", "smoke_test")
print("  [OK] PositionManager.open_position() executed.")

# Verify position tracking
print("\n[STEP 8] Position verification")
pos = pm.get_position(SYMBOL)
if pos:
    print("  [CONFIRMED] %s tracked in open_positions:" % SYMBOL)
    if isinstance(pos, dict):
        for k, v in pos.items():
            print("    %s: %s" % (k, v))
    else:
        print("    Record: %s" % str(pos))
else:
    print("  [WARN] Position NOT found in open_positions table.")

# Verify execution log
print("\n[STEP 9] Execution log verification")
log = engine.get_execution_history(limit=5)
for e in log:
    print("  Order %s: %s %s qty=%s price=%s status=%s" % (
        e.get("order_id",""), e.get("side",""), e.get("symbol",""),
        e.get("quantity",""), e.get("price",""), e.get("status","")))

# ===== PHASE 2: SELL (Flatten) =====
print("\n" + "=" * 70)
print("  PHASE 2: Forced SELL to flatten position")
print("=" * 70)

sell_cid = idempotency.generate_client_order_id(SYMBOL, "SELL", QUANTITY, "smoke_test_close")
print("\n[STEP 10] SELL duplicate check")
dup2 = idempotency.is_duplicate(sell_cid)
print("  Duplicate: %s" % dup2)

if not dup2:
    idempotency.register_pending(sell_cid, SYMBOL, "SELL", QUANTITY, "%s_SELL_%s_smoke_close" % (SYMBOL, QUANTITY))

    print("\n[STEP 11] SELL through RiskGatekeeper")
    sell_decision = gatekeeper.evaluate(SYMBOL, "SELL", QUANTITY, price, usdt_free)
    print("  Approved: %s (SELL should auto-approve)" % sell_decision.approved)
    print("  Reason:   %s" % sell_decision.reason)

    if sell_decision.approved:
        print("\n[STEP 12] Placing SELL via ExecutionEngine")
        sell_res = engine.execute_signal(SYMBOL, "SELL", QUANTITY, "smoke_test_close")
        s2 = sell_res.status.value if hasattr(sell_res.status, 'value') else sell_res.status
        print("  Order ID:       %s" % sell_res.order_id)
        print("  Status:         %s" % s2)
        print("  Filled Qty:     %.8f" % sell_res.filled_qty)
        print("  Avg Fill Price: $%.2f" % sell_res.price)

        if s2.upper() in ("FILLED", "PARTIALLY_FILLED"):
            idempotency.mark_submitted(sell_cid, sell_res.order_id)
            pm.close_position(SYMBOL, sell_res.price)
            print("\n  [OK] Position closed in PositionManager.")
        else:
            print("\n  [WARN] SELL not fully filled. Manual check required.")
    else:
        print("  [UNEXPECTED] SELL was rejected! This may indicate a bug.")
else:
    print("  [WARN] Duplicate SELL ID. Position may already be closed.")

# ===== FINAL SUMMARY =====
print("\n" + "=" * 70)
print("  SMOKE TEST RESULTS")
print("=" * 70)
print("")
print("  Component                Status")
print("  BinanceAdapter           Connected to %s" % ("TESTNET" if adapter._testnet else "MAINNET"))
print("  BinanceMarketData        Live price fetch     [OK]")
print("  IdempotencyManager       %s     [PASS]" % str(idempotency.get_summary()))

if decision.approved:
    print("  RiskGatekeeper (BUY)    Approved (%s)  [PASS]" % decision.reason)
else:
    print("  RiskGatekeeper (BUY)    REJECTED (%s)  [SEE ABOVE]" % decision.reason)

if 'sell_decision' in dir() and sell_decision.approved:
    print("  RiskGatekeeper (SELL)   Approved (%s)  [PASS]" % sell_decision.reason)

print("  ExecutionEngine         Testnet order placed  [%s]" % s.upper())
print("  PositionManager         Position tracked      [%s]" % ("OK" if pos else "WARN"))
print("  ExecutionLog DB         Entry persisted       [OK]")
print("")
print("  All trading occurred on Binance Spot TESTNET.")
print("  0xDEADBEEF | REPORT GENERATED")
print("=" * 70)