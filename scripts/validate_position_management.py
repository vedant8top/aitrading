"""Validate position management and risk gatekeeper end-to-end."""

import sys
from pathlib import Path

sys.path.insert(0, ".")

from src.position_management.portfolio_limits import PortfolioLimits
from src.position_management.position_manager import PositionManager
from src.position_management.portfolio_snapshot import PortfolioSnapshot
from src.position_management.exposure_tracker import ExposureTracker
from src.position_management.risk_gatekeeper import RiskGatekeeper, GateDecision

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "test_positions.db"
DB_PATH.unlink(missing_ok=True)

print("=" * 60)
print("POSITION MANAGEMENT VALIDATION")
print("=" * 60)

limits = PortfolioLimits(max_open_positions=5, max_position_value_usdt=100, max_total_exposure_usdt=300, daily_loss_limit_usdt=50)
pm = PositionManager(db_path=DB_PATH)
exposure = ExposureTracker(pm)
snapshot = PortfolioSnapshot(pm, initial_capital=1000.0)
gatekeeper = RiskGatekeeper(pm, exposure, snapshot, limits)

# TEST 1: Approved BUY
print("\n[Test 1] Approved BUY...")
d = gatekeeper.evaluate("BTCUSDT", "BUY", quantity=0.001, price=80000, balance=1000)
print(f"  Decision: {d.decision} | Reason: {d.reason} | Value: ${0.001 * 80000:.0f}")
assert d.approved == True
pm.open_position("BTCUSDT", 0.001, 80000, strategy="test")
assert pm.position_count() == 1
print("  PASS")

# TEST 2: Duplicate BUY rejection
print("\n[Test 2] Duplicate BUY rejection...")
d = gatekeeper.evaluate("BTCUSDT", "BUY", quantity=0.001, price=80000, balance=1000)
print(f"  Decision: {d.decision} | Reason: {d.reason}")
assert d.approved == False and d.reason == "duplicate_position"
print("  PASS")

# TEST 3: Max position rejection (max_open_positions=3)
print("\n[Test 3] Max position rejection...")
limits3 = PortfolioLimits(max_open_positions=3, max_position_value_usdt=100, max_total_exposure_usdt=300, daily_loss_limit_usdt=50)
gatekeeper3 = RiskGatekeeper(pm, exposure, snapshot, limits3)
pm.open_position("ETHUSDT", 0.01, 3000, strategy="test")
pm.open_position("BNBUSDT", 0.1, 500, strategy="test")
assert pm.position_count() == 3
d = gatekeeper3.evaluate("SOLUSDT", "BUY", quantity=1, price=100, balance=1000)
print(f"  Decision: {d.decision} | Reason: {d.reason}")
assert d.approved == False and d.reason == "max_positions_exceeded"
print("  PASS")

# TEST 4: Exposure rejection (total_exposure > 300 USDT)
print("\n[Test 4] Exposure rejection...")
for sym in ["BTCUSDT", "ETHUSDT", "BNBUSDT"]:
    pos = pm.get_position(sym)
    if pos:
        pm.close_position(sym, exit_price=pos["avg_entry_price"])
assert pm.position_count() == 0
pm.open_position("BTCUSDT", 0.001, 80000, strategy="test")    # 80 USDT
pm.open_position("ETHUSDT", 0.03, 3000, strategy="test")      # 90 USDT
pm.open_position("SOLUSDT", 10, 10, strategy="test")           # 100 USDT
total_exp = exposure.get_total_exposure()
print(f"  Positions: {pm.position_count()}, Exposure: {total_exp:.0f} USDT")
# 270 + 36 = 306 > 300. 6*6=36 < 100 (position_value OK)
d = gatekeeper.evaluate("BNBUSDT", "BUY", quantity=6, price=6, balance=500)
print(f"  Decision: {d.decision} | Reason: {d.reason}")
assert d.approved == False and d.reason == "total_exposure_exceeded"
print("  PASS")

# TEST 5: Daily loss rejection
print("\n[Test 5] Daily loss rejection...")
for sym in ["BTCUSDT", "ETHUSDT", "SOLUSDT"]:
    pos = pm.get_position(sym)
    if pos:
        pm.close_position(sym, exit_price=pos["avg_entry_price"])
d = gatekeeper.evaluate("ETHUSDT", "BUY", quantity=0.01, price=3000, balance=500, daily_realized_pnl=-60)
print(f"  Decision: {d.decision} | Reason: {d.reason}")
assert d.approved == False and d.reason == "daily_loss_exceeded"
print("  PASS")

# TEST 6: Portfolio snapshot
print("\n[Test 6] Portfolio snapshot generation...")
pm.open_position("TESTUSDT", 10, 50, strategy="test")
pm.close_position("TESTUSDT", exit_price=55)
snap = snapshot.generate()
print(f"  Total equity:  ${snap['total_equity']:.2f}")
print(f"  Cash:          ${snap['cash']:.2f}")
print(f"  Realized PnL:  ${snap['realized_pnl']:.2f}")
print(f"  Return:        {snap['return_pct']}%")
assert "total_equity" in snap and "cash" in snap and "realized_pnl" in snap
print("  PASS")

print("\n" + "=" * 60)
print("ALL 6 TESTS PASSED")
print("=" * 60)