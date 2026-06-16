# Paper Trading Simulator v1 — Design Document

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    daily_runner.py                       │
│  Main orchestrator: runs daily workflow, generates      │
│  reports, handles restart recovery                      │
└──────────┬──────────────┬──────────────┬────────────────┘
           │              │              │
     ┌─────▼──────┐ ┌────▼─────┐ ┌──────▼───────┐
     │paper_broker│ │portfolio │ │trade_journal │
     │ .py        │ │_state.py │ │.py           │
     │ Execute    │ │ SQLite   │ │ Log trades   │
     │ orders     │ │ CRUD     │ │ P&L tracking │
     │ Simulate   │ │ positions │ │ Journal      │
     └─────┬──────┘ └────┬─────┘ └──────┬───────┘
           │              │              │
           └──────────────┴──────────────┘
                          │
                    ┌─────▼──────┐
                    │ SQLite DB  │
                    │paper_trading│
                    │.db         │
                    └────────────┘
```

## Data Flow

### Daily Workflow
1. **Download**: Fetch latest OHLCV for 49 NIFTY stocks from Yahoo Finance
2. **Indicators**: Calculate SMA_20 (required by Donchian)
3. **Signals**: Run Donchian 20/40 on each stock
4. **Simulate**: Process BUY/SELL signals
   - BUY: Check cash, allocate 10%, buy whole shares at next-day open + slippage
   - SELL: Close position, calculate P&L, update cash
5. **Snapshot**: Record portfolio state (cash, equity, open positions)
6. **Report**: Generate daily report

### Restart Recovery
1. Read open positions from `positions` table
2. Read cash balance from latest `portfolio_snapshots`
3. Reconstruct in-memory state
4. Resume daily processing

---

## SQLite Schema

### Tables

#### positions
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| ticker | TEXT | Stock symbol |
| entry_date | TEXT | Entry date (ISO format) |
| entry_price | REAL | Entry price per share |
| shares | INTEGER | Number of shares held |
| current_price | REAL | Last known price |
| unrealized_pnl | REAL | Current unrealized P&L |
| entry_signal_date | TEXT | Signal date that triggered entry |
| status | TEXT | OPEN / CLOSED |
| created_at | TEXT | Record creation timestamp |
| updated_at | TEXT | Last update timestamp |

#### orders
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| ticker | TEXT | Stock symbol |
| order_type | TEXT | BUY / SELL |
| signal_date | TEXT | Date signal was generated |
| execution_date | TEXT | Date order was executed |
| requested_shares | INTEGER | Shares requested |
| executed_shares | INTEGER | Shares actually executed |
| price | REAL | Execution price |
| slippage | REAL | Slippage per share |
| brokerage | REAL | Brokerage charged |
| total_value | REAL | Total transaction value |
| status | TEXT | PENDING / EXECUTED / REJECTED |
| reason | TEXT | Rejection reason (if rejected) |
| created_at | TEXT | Record creation timestamp |

#### trades
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| ticker | TEXT | Stock symbol |
| entry_date | TEXT | Entry date |
| exit_date | TEXT | Exit date |
| entry_price | REAL | Entry price |
| exit_price | REAL | Exit price |
| shares | INTEGER | Shares traded |
| entry_value | REAL | Total entry value |
| exit_value | REAL | Total exit value |
| brokerage | REAL | Total brokerage (entry + exit) |
| slippage | REAL | Total slippage (entry + exit) |
| pnl | REAL | Net P&L |
| return_pct | REAL | Return percentage |
| holding_days | INTEGER | Days held |
| created_at | TEXT | Record creation timestamp |

#### portfolio_snapshots
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| snapshot_date | TEXT | Date of snapshot |
| cash | REAL | Cash balance |
| market_value | REAL | Market value of open positions |
| equity | REAL | Total portfolio value (cash + market value) |
| open_positions | INTEGER | Number of open positions |
| daily_pnl | REAL | P&L for the day |
| total_pnl | REAL | Cumulative P&L |
| created_at | TEXT | Record creation timestamp |

---

## Module Specifications

### 1. portfolio_state.py

**Class: PortfolioState**

| Method | Description |
|--------|-------------|
| `__init__(db_path)` | Connect to SQLite, create tables if not exist |
| `load_state()` | Load open positions and cash from DB |
| `save_position(ticker, entry_date, entry_price, shares, signal_date)` | Insert new position |
| `close_position(ticker, exit_date, exit_price)` | Mark position as CLOSED, record trade |
| `update_position_price(ticker, price)` | Update current price and unrealized P&L |
| `update_cash(new_cash)` | Update cash balance |
| `record_order(order_data)` | Insert order record |
| `record_snapshot(snapshot_data)` | Insert portfolio snapshot |
| `get_open_positions()` | Return list of open positions |
| `get_cash()` | Return current cash balance |
| `get_trade_history(days)` | Return recent trades |
| `get_portfolio_history(days)` | Return recent snapshots |
| `get_latest_snapshot()` | Return most recent snapshot |
| `close()` | Close database connection |

**Initialization**: 
- Start with INR 1,000,000 initial capital
- If positions table has OPEN rows, restore portfolio
- If no state exists, create initial snapshot

### 2. paper_broker.py

**Class: PaperBroker**

| Method | Description |
|--------|-------------|
| `__init__(portfolio_state, slippage=0.0005, brokerage=0.0005)` | Initialize broker |
| `process_signal(ticker, signal, signal_date, open_price, cash)` | Process BUY/SELL signal |
| `buy(ticker, signal_date, open_price, cash)` | Execute buy order |
| `sell(ticker, position, signal_date, open_price)` | Execute sell order |
| `get_position_size(cash, price)` | Calculate shares to buy (10% allocation) |

**Buy Logic**:
- Allocate 10% of available cash
- `shares = int(cash * 0.10 / (price * (1 + slippage) * (1 + brokerage)))`
- If shares < 1, skip (log reason)
- Record order as EXECUTED

**Sell Logic**:
- Close entire position
- Calculate P&L
- Record order as EXECUTED

**Execution**:
- Price = next-day open + 0.05% slippage
- Brokerage = 0.05% of trade value

### 3. trade_journal.py

**Class: TradeJournal**

| Method | Description |
|--------|-------------|
| `__init__(portfolio_state)` | Initialize journal |
| `log_order(order_data)` | Log order execution |
| `log_trade(entry_data, exit_data)` | Log completed trade |
| `log_snapshot(date, cash, market_value, equity, daily_pnl)` | Log daily snapshot |
| `get_recent_trades(n=10)` | Get N most recent trades |
| `get_daily_pnl(date)` | Get P&L for a specific date |
| `get_summary()` | Get summary statistics |
| `generate_report(date)` | Generate daily report string |

### 4. daily_runner.py

**Class: DailyRunner**

| Method | Description |
|--------|-------------|
| `__init__(config)` | Initialize all components |
| `run_daily()` | Execute one day of simulation |
| `run_simulation(start_date, end_date)` | Run simulation over date range |
| `download_data(tickers)` | Download OHLCV for all tickers |
| `calculate_indicators(data)` | Calculate required indicators |
| `generate_signals(data)` | Run Donchian 20/40 |
| `process_signals(signals, current_date)` | Execute signals via broker |
| `take_snapshot(date)` | Record daily portfolio state |
| `generate_report(date)` | Generate daily report |
| `recover_state()` | Load state from DB on startup |
| `generate_markdown_report()` | Generate daily_report.md |

---

## Key Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| Initial Capital | INR 1,000,000 | Starting cash |
| Position Size | 10% | Per-stock allocation |
| Entry Channel | 20 | Donchian entry period |
| Exit Channel | 40 | Donchian exit period |
| Slippage | 0.05% | Per-trade slippage |
| Brokerage | 0.05% | Per-trade brokerage |
| Universe | 49 NIFTY stocks | From config |

---

## Run Modes

1. **Historical Simulation**: Run over past dates (download not needed — use cached data)
2. **Live Daily**: Run once per day with latest market data
3. **Restart Recovery**: Load from DB and continue

---

## File Structure

```
src/paper_trading/
├── __init__.py
├── portfolio_state.py     # SQLite CRUD for portfolio state
├── paper_broker.py        # Simulated execution engine
├── trade_journal.py       # Trade logging and reporting
└── daily_runner.py        # Main orchestrator

data/
└── paper_trading.db       # SQLite database

docs/
├── paper_trading_design.md    # This document
└── paper_trading_results.md   # Generated after simulation
```

---

## Design Decisions

1. **SQLite over CSV**: Crash-safe, concurrent reads, queryable
2. **10% position size**: Matches existing backtester
3. **Donchian 20/40**: Optimized champion from strategy optimization
4. **Whole shares only**: Matches Indian market reality
5. **Next-day open execution**: Matches existing backtester
6. **No risk management in v1**: Paper trading without stop losses for simplicity
7. **1M initial capital**: Allows buying higher-priced stocks (MARUTI at INR 10K)
8. **Restart recovery**: Essential for long-running paper trading