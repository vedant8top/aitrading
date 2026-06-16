"""Validate Binance integration layer against live Testnet."""

import sys
sys.path.insert(0, ".")

from src.exchanges.binance_adapter import BinanceAdapter
from src.exchanges.binance_market_data import BinanceMarketData

print("=" * 60)
print("BINANCE INTEGRATION VALIDATION")
print("=" * 60)

# Initialize
adapter = BinanceAdapter()
market = BinanceMarketData(adapter)

# Test 1: Ping
print("\n[1/4] Testing ping()...")
result = adapter.ping()
print(f"  Status: {result['status']}")
print(f"  Server time: {result['server_time']}")
print(f"  Network: {result['network']}")
assert result["status"] == "connected", "Ping failed"
print("  PASS")

# Test 2: Account balance
print("\n[2/4] Testing get_account_balance()...")
balances = adapter.get_account_balance()
print(f"  Non-zero assets: {len(balances)}")
for asset, data in list(balances.items())[:5]:
    print(f"    {asset}: {data['total']}")
assert len(balances) > 0, "No balances found"
print("  PASS")

# Test 3: BTCUSDT price
print("\n[3/4] Testing get_latest_price('BTCUSDT')...")
price = adapter.get_latest_price("BTCUSDT")
print(f"  BTCUSDT price: {price:.2f}")
assert price > 0, "Price is zero or negative"
print("  PASS")

# Test 4: Historical candles
print("\n[4/4] Testing get_historical_candles('BTCUSDT', '1d', 5)...")
candles = adapter.get_historical_candles("BTCUSDT", "1d", 5)
print(f"  Candles retrieved: {len(candles)}")
for c in candles[:3]:
    print(f"    {c['open_time']} O={c['open']:.2f} H={c['high']:.2f} L={c['low']:.2f} C={c['close']:.2f}")
assert len(candles) == 5, f"Expected 5 candles, got {len(candles)}"
print("  PASS")

print("\n" + "=" * 60)
print("ALL TESTS PASSED")
print("=" * 60)