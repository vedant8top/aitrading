# Testnet Execution Design

## Overview

This document describes the architecture of the Binance Testnet execution layer for TradingAI.

---

## Architecture

```
                    ┌───────────────────┐
                    │  Strategy Engine  │
                    │  (Donchian 20/40) │
                    └────────┬──────────┘
                             │ Signal: BUY/SELL/HOLD
                             ▼
                    ┌───────────────────┐
                    │   SignalRouter     │
                    │                   │
                    │  signal → ExecutionRequest
                    └────────┬──────────┘
                             │ ExecutionRequest
                             ▼
                    ┌───────────────────┐
                    │  ExecutionEngine  │
                    │                   │
                    │  validate symbol   │
                    │  validate balance  │
                    │  validate value    │
                    │  create order      │
                    │  persist result    │
                    └────────┬──────────┘
                             │ ExecutionRequest
                             ▼
                    ┌───────────────────┐
                    │   OrderManager    │
                    │                   │
                    │  BinanceAdapter   │
                    │  → place/cancel   │
                    │  → query status   │
                    └────────┬──────────┘
                             │ ExecutionResult
                             ▼
                    ┌───────────────────┐
                    │  SQLite DB        │
                    │  execution_log    │
                    └───────────────────┘
```

---

## Data Flow

### Signal → Execution

```
1. Strategy generates signal
   ├── BUY (symbol, quantity)
   ├── SELL (symbol, quantity)
   └── HOLD (no action)

2. SignalRouter validates signal
   ├── Check side is valid
   ├── Calculate order value (price × quantity)
   ├── Compare against max_value_usdt (100 USDT)
   └── Return ExecutionRequest or None

3. ExecutionEngine validates request
   ├── validate_symbol() — check symbol exists
   ├── validate_order_value() — check ≤ 100 USDT
   ├── validate_balance() — check sufficient funds
   └── Reject if any validation fails

4. OrderManager places order
   ├── BinanceAdapter.place_market_buy/sell()
   ├── Parse order response
   └── Return ExecutionResult

5. ExecutionEngine persists result
   └── SQLite INSERT into execution_log
```

---

## Safety Rules

| Rule | Value | Enforcement |
|------|-------|-------------|
| Network | TESTNET ONLY | BinanceAdapter.testnet=True |
| Max order value | 100 USDT | SignalRouter + ExecutionEngine |
| Balance check | Required | ExecutionEngine.validate_balance() |
| Symbol validation | Required | ExecutionEngine.validate_symbol() |
| Order logging | WARNING level | OrderManager |
| No live orders | Hardcoded | Testnet only |

---

## File Structure

```
src/execution/
├── __init__.py              # Package init
├── execution_models.py      # Dataclasses (ExecutionRequest, ExecutionResult, etc.)
├── signal_router.py         # Signal → ExecutionRequest
├── order_manager.py         # Order lifecycle management
└── execution_engine.py      # Orchestrator with validation

docs/testnet_execution_design.md  # This file
```

---

## Integration Points

### Strategy Engine

```python
# Future: Strategy calls ExecutionEngine
from src.execution import ExecutionEngine

engine = ExecutionEngine(adapter, market)
result = engine.execute_signal(
    symbol="BTCUSDT",
    side="BUY",
    quantity=0.0001,
    strategy="donchian_20_40",
)
```

### Paper Trading

```python
# Future: Paper trading can use same signal format
signal = {"symbol": "BTCUSDT", "side": "BUY", "quantity": 0.0001}
request = router.route_from_dict(signal)
result = engine.execute(request)
```

### Portfolio State

```python
# Future: SQLite execution_log can sync with portfolio_state
history = engine.get_execution_history(limit=100)
```

---

## SQLite Schema

```sql
CREATE TABLE execution_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    quantity REAL NOT NULL,
    price REAL,
    status TEXT NOT NULL,
    strategy TEXT,
    timestamp TEXT NOT NULL,
    pnl REAL,
    commission REAL,
    raw_response TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

---

## Validation

Run the validation script:

```bash
.venv\Scripts\python.exe scripts/validate_testnet_execution.py
```

Tests:
1. Retrieve BTCUSDT price
2. Place tiny BUY order (~$10 USDT)
3. Query order status
4. Cancel if open
5. Retrieve updated balances
6. Persist result to SQLite