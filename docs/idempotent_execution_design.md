# Idempotent Execution Design

## Overview

Idempotent execution framework prevents duplicate order submissions and recovers pending orders after process restart or crash. Uses `client_order_id` (newClientOrderId) to uniquely identify each order request.

## Architecture

```
                    ┌──────────────────────────────────────────┐
                    │         Idempotent Order Flow            │
                    │                                          │
                    │  1. Generate client_order_id             │
                    │     (SHA256 fingerprint + UUID)          │
                    │                                          │
                    │  2. Persist with status=PENDING          │
                    │     ┌──────────────────────────┐        │
                    │     │  idempotency.db (SQLite) │        │
                    │     └──────────────────────────┘        │
                    │                                          │
                    │  3. Submit order to Binance              │
                    │     (newClientOrderId=client_order_id)   │
                    │                                          │
                    │  4. Update status=SUBMITTED              │
                    │     ┌──────────────────────────┐        │
                    │     │  order_id from exchange   │        │
                    │     └──────────────────────────┘        │
                    │                                          │
                    │  ─── CRASH / RESTART ───                │
                    │                                          │
                    │  5. ExecutionRecovery.recover()          │
                    │     ├── Check PENDING/SUBMITTED orders  │
                    │     ├── Query Binance by order_id       │
                    │     ├── Update local status             │
                    │     └── Auto-fill if exchange says so   │
                    └──────────────────────────────────────────┘
```

## Components

### IdempotencyManager
- Generate unique `client_order_id` per request
- Persist before submission (status=PENDING)
- Update status after submission (SUBMITTED)
- Detect duplicates: reject if same `client_order_id` exists
- Track filled/cancelled/failed

### OrderReconciliation
- Compare SQLite records against Binance Testnet
- Detect status mismatches
- Detect orders on exchange but not in SQLite
- Detect orders in SQLite but not on exchange

### ExecutionRecovery
- On startup: scan all PENDING/SUBMITTED orders
- Query exchange for each order's current status
- Auto-resolve: fill orders exchange says are filled
- Timeout handling: if not found on exchange, mark failed
- No duplicate orders created during recovery

## Idempotency Flow

```
1. Generate client_order_id("BTCUSDT", "BUY", 0.001)
   → "TA_a1b2c3d4e5f6g7h8_87654321"

2. Register PENDING in SQLite
   INSERT INTO idempotency (client_order_id="TA_...", status="PENDING", ...)

3. Check if duplicate
   is_duplicate("TA_...") → False

4. Submit to Binance
   client.order_market_buy(symbol="BTCUSDT", quantity=0.001, newClientOrderId="TA_...")

5. Update to SUBMITTED
   UPDATE idempotency SET status="SUBMITTED", order_id="12345"

6. On restart:
   ExecutionRecovery.recover()
   → Queries exchange for order 12345
   → Updates status to FILLED if exchange says so
   → No duplicate order created
```

## SQLite Schema

```sql
CREATE TABLE idempotency (
    client_order_id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    quantity REAL NOT NULL,
    status TEXT NOT NULL,          -- PENDING | SUBMITTED | FILLED | CANCELLED | FAILED
    fingerprint TEXT NOT NULL,
    order_id TEXT,                 -- Binance exchange order ID
    exchange_status TEXT,          -- From Binance API
    request_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

## Files

```
src/execution/
├── idempotency_manager.py     # client_order_id generation, persistence, duplicate detection
├── order_reconciliation.py    # SQLite vs Binance comparison
└── execution_recovery.py      # Post-crash recovery of pending orders

docs/idempotent_execution_design.md
```

## Validation

1. Submit order
2. Simulate timeout (don't update status)
3. Restart process
4. Recover order state via ExecutionRecovery
5. Verify no duplicate order created