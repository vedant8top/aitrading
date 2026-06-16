# Live Strategy Runner Design

## Overview

The Live Strategy Runner continuously evaluates market data from Binance Testnet and generates Donchian 20/40 signals. It does NOT place orders — only generates and persists signals.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  LiveStrategyRunner                      │
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Market     │  │   Signal     │  │   Runner     │  │
│  │   Scanner    │  │   Scheduler  │  │   State      │  │
│  │              │  │              │  │              │  │
│  │  candles     │  │  5 min       │  │  SQLite      │  │
│  │  prices      │  │  interval    │  │  persistence │  │
│  │  validation  │  │  dedup       │  │              │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │
│         │                 │                  │           │
│         └─────────────────┼──────────────────┘           │
│                           │                              │
│                    ┌──────▼───────┐                      │
│                    │  Donchian    │                      │
│                    │  20/40       │                      │
│                    │  Signal      │                      │
│                    │  Engine      │                      │
│                    └──────┬───────┘                      │
│                           │                              │
│                    ┌──────▼───────┐                      │
│                    │  Signal Log  │                      │
│                    │  (SQLite)    │                      │
│                    └──────────────┘                      │
└─────────────────────────────────────────────────────────┘
```

---

## Data Flow

```
1. MarketScanner.scan()
   ├── Get latest price for each symbol
   ├── Get 100 hourly candles
   └── Return {symbol: MarketSnapshot}

2. LiveStrategyRunner._compute_donchian()
   ├── Entry High = max(high[-20:])
   ├── Exit Low = min(low[-40:])
   ├── Close = last close
   ├── BUY if close > entry_high
   ├── SELL if close < exit_low
   └── HOLD otherwise

3. RunnerState.log_signal()
   └── INSERT into signal_log (SQLite)

4. SignalScheduler.mark_run()
   └── Update last_run_time (prevent duplicate)
```

---

## File Structure

```
src/live_trading/
├── __init__.py              # Package init
├── market_scanner.py        # Pulls candles and prices
├── signal_scheduler.py      # 5-minute interval with dedup
├── runner_state.py          # SQLite state persistence
└── live_strategy_runner.py  # Donchian 20/40 signal engine

docs/live_strategy_runner_design.md  # This file
```

---

## SQLite Schema

### runner_state table
```sql
CREATE TABLE runner_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

### signal_log table
```sql
CREATE TABLE signal_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    signal TEXT NOT NULL,
    price REAL,
    strategy TEXT,
    timestamp TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

---

## Validation

Run the validation script:

```bash
.venv\Scripts\python.exe scripts/validate_live_strategy_runner.py
```

Tests:
1. Pull latest BTCUSDT candles
2. Run Donchian calculation
3. Generate signal
4. Persist signal
5. Restart process
6. Recover state