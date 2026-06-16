# Binance Integration Design

## Overview

This document describes the architecture and design of the Binance Spot Testnet integration layer for TradingAI.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        TradingAI System                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │   Strategy   │  │    Paper     │  │   Portfolio State    │  │
│  │   Engine     │  │   Trading    │  │   (SQLite)           │  │
│  │              │  │   System     │  │                      │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘  │
│         │                 │                      │              │
│         └─────────────────┼──────────────────────┘              │
│                           │                                     │
│                    ┌──────▼───────┐                             │
│                    │  Exchange    │                             │
│                    │  Interface   │  (Abstract Base Class)      │
│                    │              │                             │
│                    └──────┬───────┘                             │
│                           │                                     │
│              ┌────────────┼────────────┐                        │
│              │            │            │                        │
│       ┌──────▼──────┐ ┌──▼────────┐ ┌─▼──────────────┐        │
│       │  Binance    │ │  Binance  │ │  Future        │        │
│       │  Adapter    │ │  Market   │ │  Exchange      │        │
│       │             │ │  Data     │ │  Adapters      │        │
│       └──────┬──────┘ └──┬────────┘ └────────────────┘        │
│              │            │                                     │
│              └────────────┼─────────────┘                       │
│                           │                                     │
└───────────────────────────┼─────────────────────────────────────┘
                            │
                    ┌───────▼───────┐
                    │   Binance     │
                    │   Spot        │
                    │   Testnet     │
                    │   API         │
                    └───────────────┘
```

---

## Authentication Flow

```
1. Load .env file
   ├── BINANCE_API_KEY
   ├── BINANCE_SECRET_KEY
   └── BINANCE_TESTNET=true

2. Validate credentials
   ├── Check for placeholder values
   ├── Check for empty values
   └── Raise BinanceAdapterError if invalid

3. Initialize Binance Client
   ├── client = Client(api_key, secret_key, testnet=True)
   └── Client connects to testnet.binance.vision

4. Verify authentication
   ├── client.ping() → server time
   └── client.get_account() → account info
```

---

## Market Data Flow

```
┌──────────────┐     ┌──────────────────┐     ┌──────────────┐
│  Strategy    │────▶│  BinanceMarket   │────▶│  Binance     │
│  Engine      │     │  Data            │     │  API         │
│              │     │                  │     │              │
│  get_price() │     │  get_ticker()    │     │  /api/v3/    │
│  get_candles │     │  get_klines()    │     │  ticker      │
│  validate()  │     │  validate()      │     │  klines      │
└──────────────┘     └──────────────────┘     └──────────────┘
```

### Methods

| Method | Description | Returns |
|--------|-------------|---------|
| `get_ticker_price(symbol)` | Current price | `{"symbol": str, "price": float}` |
| `get_klines(symbol, interval, limit)` | Historical OHLCV | `pd.DataFrame` |
| `get_top_symbols(quote, top)` | Top symbols by volume | `list[dict]` |
| `validate_symbol(symbol)` | Check if symbol is trading | `bool` |
| `get_24hr_ticker(symbol)` | 24hr statistics | `dict` |
| `get_exchange_info()` | Exchange rules | `dict` |

---

## Order Execution Flow

```
┌──────────────┐     ┌──────────────────┐     ┌──────────────┐
│  Strategy    │────▶│  BinanceAdapter  │────▶│  Binance     │
│  Engine      │     │                  │     │  API         │
│              │     │  place_market_   │     │              │
│  signal()    │     │  buy/sell()      │     │  /api/v3/    │
│  execute()   │     │                  │     │  order       │
└──────────────┘     └──────────────────┘     └──────────────┘
```

### Order Methods

| Method | Description | Parameters |
|--------|-------------|------------|
| `place_market_buy(symbol, quantity)` | Market buy | symbol, quantity |
| `place_market_sell(symbol, quantity)` | Market sell | symbol, quantity |
| `cancel_order(order_id, symbol)` | Cancel order | order_id, symbol |
| `get_open_orders(symbol)` | List open orders | symbol (optional) |

### Order Safety

- All orders are logged with WARNING level
- Orders are only placed on TESTNET (never live)
- Exception handling wraps all order methods
- `BinanceAdapterError` raised on failure

---

## Error Handling Strategy

```
┌─────────────────────────────────────────────────────────┐
│                    Error Handling                        │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  1. BinanceAPIException                                 │
│     ├── Log error message and status code               │
│     └── Raise BinanceAdapterError                       │
│                                                         │
│  2. BinanceRequestException                             │
│     ├── Log request error                               │
│     └── Raise BinanceAdapterError                       │
│                                                         │
│  3. Generic Exception                                   │
│     ├── Log unexpected error                            │
│     └── Raise BinanceAdapterError                       │
│                                                         │
│  4. Credential Errors                                   │
│     ├── Missing .env file                               │
│     ├── Missing API keys                                │
│     └── Placeholder values                              │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## Future Integration Points

### Paper Trading Integration

```
Paper Trading System
├── Uses BinanceAdapter for live price data
├── Replaces Yahoo Finance data source
├── Maintains same portfolio state (SQLite)
└── Same execution logic (next-day open)
```

### Strategy Engine Integration

```
Strategy Engine
├── Uses BinanceMarketData for real-time prices
├── Generates signals from live data
├── Calls BinanceAdapter for order execution
└── Maintains strategy state in SQLite
```

### Portfolio State Integration

```
Portfolio State
├── BinanceAdapter.get_account_balance()
├── Syncs with SQLite portfolio_state table
├── Tracks open positions
└── Records trade history
```

---

## File Structure

```
src/exchanges/
├── __init__.py                   # Package init, exports key classes
├── exchange_interface.py         # Abstract base class (ExchangeInterface)
├── binance_adapter.py            # Binance ExchangeInterface implementation
└── binance_market_data.py        # Market data subsystem

.env                              # API credentials (not committed)
test_binance_connection.py        # Connectivity test script
```

---

## Testing

### Validation Script

```python
# scripts/validate_binance_integration.py
from src.exchanges.binance_adapter import BinanceAdapter
from src.exchanges.binance_market_data import BinanceMarketData

adapter = BinanceAdapter()
market = BinanceMarketData(adapter)

# Test 1: Ping
result = adapter.ping()
assert result["status"] == "connected"

# Test 2: Account balance
balances = adapter.get_account_balance()
assert len(balances) > 0

# Test 3: BTCUSDT price
price = adapter.get_latest_price("BTCUSDT")
assert price > 0

# Test 4: Historical candles
candles = adapter.get_historical_candles("BTCUSDT", "1d", 5)
assert len(candles) == 5
```

### Run Validation

```bash
.venv\Scripts\python.exe scripts/validate_binance_integration.py
```

---

## Security Notes

- API keys are stored in `.env` (not committed to git)
- Never log API keys or secrets
- Testnet only (no live trading)
- All order methods log warnings before execution
- Exception handling prevents silent failures