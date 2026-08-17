"""SQLite-backed portfolio state management for paper trading."""

from __future__ import annotations

import sqlite3
from datetime import datetime, date
from pathlib import Path
from typing import Optional, Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "paper_trading.db"
INITIAL_CAPITAL = 1_000_000.0


def _now() -> str:
    return datetime.now().isoformat()


def _today() -> str:
    return date.today().isoformat()


class PortfolioState:
    """Manages paper trading state using SQLite for persistence."""

    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.row_factory = sqlite3.Row
        self._create_tables()
        self._cash_balance: float = INITIAL_CAPITAL
        self._initialized = self._load_state()

    def _create_tables(self) -> None:
        """Create database tables if they don't exist."""
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                entry_date TEXT NOT NULL,
                entry_price REAL NOT NULL,
                shares INTEGER NOT NULL,
                current_price REAL NOT NULL,
                unrealized_pnl REAL DEFAULT 0.0,
                entry_signal_date TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'OPEN',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                order_type TEXT NOT NULL,
                signal_date TEXT NOT NULL,
                execution_date TEXT,
                requested_shares INTEGER NOT NULL,
                executed_shares INTEGER DEFAULT 0,
                price REAL,
                slippage REAL DEFAULT 0.0,
                brokerage REAL DEFAULT 0.0,
                total_value REAL DEFAULT 0.0,
                status TEXT NOT NULL DEFAULT 'PENDING',
                reason TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                entry_date TEXT NOT NULL,
                exit_date TEXT NOT NULL,
                entry_price REAL NOT NULL,
                exit_price REAL NOT NULL,
                shares INTEGER NOT NULL,
                entry_value REAL NOT NULL,
                exit_value REAL NOT NULL,
                brokerage REAL NOT NULL,
                slippage REAL NOT NULL,
                pnl REAL NOT NULL,
                return_pct REAL NOT NULL,
                holding_days INTEGER NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_date TEXT NOT NULL,
                cash REAL NOT NULL,
                market_value REAL NOT NULL,
                equity REAL NOT NULL,
                open_positions INTEGER NOT NULL,
                daily_pnl REAL DEFAULT 0.0,
                total_pnl REAL DEFAULT 0.0,
                created_at TEXT NOT NULL
            );
        """)
        self._conn.commit()

    def _load_state(self) -> bool:
        """Load existing portfolio state from DB. Returns True if state found."""
        # Load open positions
        cursor = self._conn.execute(
            "SELECT COUNT(*) FROM positions WHERE status = 'OPEN'"
        )
        open_count = cursor.fetchone()[0]

        # Load latest cash balance from snapshot
        latest = self.get_latest_snapshot()
        if latest:
            self._cash_balance = float(latest["cash"])
            return True
        elif open_count > 0:
            # Positions exist but no snapshots — start fresh
            self._cash_balance = INITIAL_CAPITAL
            return False
        else:
            self._cash_balance = INITIAL_CAPITAL
            return False

    # ------------------------------------------------------------------
    # Position Management
    # ------------------------------------------------------------------

    def save_position(
        self,
        ticker: str,
        entry_date: str,
        entry_price: float,
        shares: int,
        signal_date: str,
    ) -> int:
        """Insert a new open position. Returns position ID."""
        now = _now()
        cursor = self._conn.execute(
            """INSERT INTO positions
               (ticker, entry_date, entry_price, shares, current_price,
                unrealized_pnl, entry_signal_date, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, 0.0, ?, 'OPEN', ?, ?)""",
            (ticker, entry_date, entry_price, shares, entry_price,
             signal_date, now, now),
        )
        self._conn.commit()
        return cursor.lastrowid  # type: ignore

    def close_position(self, ticker: str, exit_date: str, exit_price: float) -> Optional[dict]:
        """Close an open position and record the trade.

        Returns the trade record dict if successful, None otherwise.
        """
        cursor = self._conn.execute(
            "SELECT * FROM positions WHERE ticker = ? AND status = 'OPEN'",
            (ticker,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        pos = dict(row)
        shares = pos["shares"]
        entry_price = pos["entry_price"]
        entry_date = pos["entry_date"]

        entry_value = shares * entry_price
        exit_value = shares * exit_price
        slippage_val = (exit_price - entry_price) * shares * 0.0005  # simplified
        brokerage_val = (entry_value + exit_value) * 0.0005
        pnl = exit_value - entry_value - brokerage_val - slippage_val
        return_pct = pnl / entry_value * 100 if entry_value > 0 else 0
        holding_days = (datetime.fromisoformat(exit_date) - datetime.fromisoformat(entry_date)).days

        # Mark position as CLOSED
        now = _now()
        self._conn.execute(
            "UPDATE positions SET status = 'CLOSED', updated_at = ? WHERE id = ?",
            (now, pos["id"]),
        )

        # Record trade
        self._conn.execute(
            """INSERT INTO trades
               (ticker, entry_date, exit_date, entry_price, exit_price,
                shares, entry_value, exit_value, brokerage, slippage,
                pnl, return_pct, holding_days, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (ticker, entry_date, exit_date, entry_price, exit_price,
             shares, entry_value, exit_value, brokerage_val, slippage_val,
             round(pnl, 2), round(return_pct, 2), holding_days, now),
        )
        self._conn.commit()

        return {
            "ticker": ticker,
            "entry_date": entry_date,
            "exit_date": exit_date,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "shares": shares,
            "pnl": round(pnl, 2),
            "return_pct": round(return_pct, 2),
        }

    def update_position_price(self, ticker: str, price: float) -> None:
        """Update current market price and unrealized P&L for a position."""
        cursor = self._conn.execute(
            "SELECT * FROM positions WHERE ticker = ? AND status = 'OPEN'",
            (ticker,),
        )
        row = cursor.fetchone()
        if row:
            pos = dict(row)
            unrealized = (price - pos["entry_price"]) * pos["shares"]
            now = _now()
            self._conn.execute(
                "UPDATE positions SET current_price = ?, unrealized_pnl = ?, updated_at = ? WHERE id = ?",
                (price, round(unrealized, 2), now, pos["id"]),
            )
            self._conn.commit()

    def update_position_prices(self, prices: dict[str, float]) -> None:
        """Update current market price and unrealized P&L for multiple positions in batch."""
        if not prices:
            return

        cursor = self._conn.execute(
            "SELECT * FROM positions WHERE status = 'OPEN'",
        )

        updates = []
        now = _now()
        for row in cursor.fetchall():
            pos = dict(row)
            ticker = pos["ticker"]
            if ticker in prices:
                price = prices[ticker]
                unrealized = (price - pos["entry_price"]) * pos["shares"]
                updates.append((price, round(unrealized, 2), now, pos["id"]))

        if updates:
            self._conn.executemany(
                "UPDATE positions SET current_price = ?, unrealized_pnl = ?, updated_at = ? WHERE id = ?",
                updates,
            )
            self._conn.commit()

    def get_open_positions(self) -> list[dict[str, Any]]:
        """Return all open positions."""
        cursor = self._conn.execute(
            "SELECT * FROM positions WHERE status = 'OPEN' ORDER BY entry_date"
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_position(self, ticker: str) -> Optional[dict[str, Any]]:
        """Get open position for a specific ticker."""
        cursor = self._conn.execute(
            "SELECT * FROM positions WHERE ticker = ? AND status = 'OPEN'",
            (ticker,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    # ------------------------------------------------------------------
    # Cash Management
    # ------------------------------------------------------------------

    @property
    def cash_balance(self) -> float:
        return self._cash_balance

    @cash_balance.setter
    def cash_balance(self, value: float) -> None:
        self._cash_balance = value

    def deduct_cash(self, amount: float) -> None:
        self._cash_balance -= amount

    def add_cash(self, amount: float) -> None:
        self._cash_balance += amount

    # ------------------------------------------------------------------
    # Order Recording
    # ------------------------------------------------------------------

    def record_order(self, order_data: dict) -> int:
        """Record an order. Returns order ID."""
        now = _now()
        cursor = self._conn.execute(
            """INSERT INTO orders (ticker, order_type, signal_date, execution_date,
               requested_shares, executed_shares, price, slippage, brokerage,
               total_value, status, reason, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                order_data["ticker"],
                order_data["order_type"],
                order_data.get("signal_date", ""),
                order_data.get("execution_date", ""),
                order_data.get("requested_shares", 0),
                order_data.get("executed_shares", 0),
                order_data.get("price", 0.0),
                order_data.get("slippage", 0.0),
                order_data.get("brokerage", 0.0),
                order_data.get("total_value", 0.0),
                order_data.get("status", "PENDING"),
                order_data.get("reason", ""),
                now,
            ),
        )
        self._conn.commit()
        return cursor.lastrowid  # type: ignore

    # ------------------------------------------------------------------
    # Snapshot Management
    # ------------------------------------------------------------------

    def record_snapshot(self, snapshot_data: dict) -> int:
        """Record a portfolio snapshot. Returns snapshot ID."""
        now = _now()
        cursor = self._conn.execute(
            """INSERT INTO portfolio_snapshots
               (snapshot_date, cash, market_value, equity, open_positions,
                daily_pnl, total_pnl, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                snapshot_data["snapshot_date"],
                snapshot_data["cash"],
                snapshot_data["market_value"],
                snapshot_data["equity"],
                snapshot_data["open_positions"],
                snapshot_data.get("daily_pnl", 0.0),
                snapshot_data.get("total_pnl", 0.0),
                now,
            ),
        )
        self._conn.commit()
        return cursor.lastrowid  # type: ignore

    def get_latest_snapshot(self) -> Optional[dict[str, Any]]:
        """Return most recent portfolio snapshot."""
        cursor = self._conn.execute(
            "SELECT * FROM portfolio_snapshots ORDER BY id DESC LIMIT 1"
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_portfolio_history(self, days: int = 30) -> list[dict[str, Any]]:
        """Return recent portfolio snapshots."""
        cursor = self._conn.execute(
            "SELECT * FROM portfolio_snapshots ORDER BY snapshot_date DESC LIMIT ?",
            (days,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_trade_history(self, days: int = 30) -> list[dict[str, Any]]:
        """Return recent trades."""
        cursor = self._conn.execute(
            "SELECT * FROM trades ORDER BY exit_date DESC LIMIT ?",
            (days,),
        )
        return [dict(row) for row in cursor.fetchall()]

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close database connection."""
        self._conn.close()

    def __enter__(self) -> PortfolioState:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()