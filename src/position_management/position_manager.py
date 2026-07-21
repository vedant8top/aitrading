"""Position manager: tracks positions with P&L and persistence."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.position_management.portfolio_limits import PortfolioLimits

logger = logging.getLogger("position_management.manager")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "positions.db"


class PositionManager:
    """Tracks open and closed positions with SQLite persistence.

    Per position:
    - symbol, quantity, avg_entry, current_price
    - unrealized_pnl, realized_pnl
    - holding_days
    """

    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)
        self._init_db()

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS open_positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT UNIQUE NOT NULL,
                quantity REAL NOT NULL,
                avg_entry_price REAL NOT NULL,
                current_price REAL,
                side TEXT DEFAULT 'LONG',
                strategy TEXT,
                opened_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS closed_positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                quantity REAL NOT NULL,
                avg_entry_price REAL NOT NULL,
                exit_price REAL NOT NULL,
                realized_pnl REAL NOT NULL,
                side TEXT,
                strategy TEXT,
                opened_at TEXT NOT NULL,
                closed_at TEXT NOT NULL,
                holding_days INTEGER DEFAULT 0
            )
        """)
        conn.commit()
        conn.close()

    def open_position(self, symbol: str, quantity: float, avg_entry_price: float,
                      side: str = "LONG", strategy: str = "") -> None:
        """Open a new position."""
        now = datetime.now(timezone.utc).isoformat()
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute(
            """INSERT OR REPLACE INTO open_positions
               (symbol, quantity, avg_entry_price, current_price, side, strategy, opened_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (symbol, quantity, avg_entry_price, avg_entry_price, side, strategy, now, now),
        )
        conn.commit()
        conn.close()
        logger.info("Position opened: %s %.4f @ %.2f", symbol, quantity, avg_entry_price)

    def close_position(self, symbol: str, exit_price: float) -> Optional[dict]:
        """Close a position and move to closed_positions."""
        pos = self.get_position(symbol)
        if not pos:
            logger.warning("Cannot close %s: position not found", symbol)
            return None

        from datetime import datetime as dt
        opened = dt.fromisoformat(pos["opened_at"].replace("Z", "+00:00"))
        now = dt.now(timezone.utc)
        holding_days = (now - opened).days

        if pos["side"] == "LONG":
            realized_pnl = (exit_price - pos["avg_entry_price"]) * pos["quantity"]
        else:
            realized_pnl = (pos["avg_entry_price"] - exit_price) * pos["quantity"]

        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute(
            """INSERT INTO closed_positions
               (symbol, quantity, avg_entry_price, exit_price, realized_pnl, side, strategy, opened_at, closed_at, holding_days)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (pos["symbol"], pos["quantity"], pos["avg_entry_price"], exit_price, realized_pnl,
             pos["side"], pos["strategy"], pos["opened_at"], now.isoformat(), holding_days),
        )
        conn.execute("DELETE FROM open_positions WHERE symbol=?", (symbol,))
        conn.commit()
        conn.close()

        result = {**pos, "exit_price": exit_price, "realized_pnl": realized_pnl}
        logger.info("Position closed: %s PnL=%.2f (%d days)", symbol, realized_pnl, holding_days)
        return result

    def get_position(self, symbol: str) -> Optional[dict]:
        """Get an open position by symbol."""
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM open_positions WHERE symbol=?", (symbol,)).fetchone()
        conn.close()
        return dict(row) if row else None

    def get_open_positions(self) -> list[dict]:
        """Get all open positions."""
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM open_positions").fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def update_price(self, symbol: str, current_price: float) -> None:
        """Update current price for an open position."""
        now = datetime.now(timezone.utc).isoformat()
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("UPDATE open_positions SET current_price=?, updated_at=? WHERE symbol=?",
                      (current_price, now, symbol))
        conn.commit()
        conn.close()

    def unrealized_pnl(self, symbol: str) -> Optional[float]:
        """Calculate unrealized P&L for an open position."""
        pos = self.get_position(symbol)
        return self._calc_unrealized_pnl(pos) if pos else None

    def _calc_unrealized_pnl(self, pos: dict) -> float:
        """Helper to calculate unrealized P&L given a position dictionary."""
        current_price = pos.get("current_price")
        if current_price is None:
            return 0.0

        if pos["side"] == "LONG":
            return (current_price - pos["avg_entry_price"]) * pos["quantity"]
        else:
            return (pos["avg_entry_price"] - current_price) * pos["quantity"]

    def total_unrealized_pnl(self) -> float:
        """Sum of all unrealized P&L."""
        total = 0.0
        for pos in self.get_open_positions():
            total += self._calc_unrealized_pnl(pos)
        return total

    def total_realized_pnl(self) -> float:
        """Sum of all realized P&L."""
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL;")
        row = conn.execute("SELECT COALESCE(SUM(realized_pnl), 0) FROM closed_positions").fetchone()
        conn.close()
        return row[0] if row else 0.0

    def position_count(self) -> int:
        """Number of open positions."""
        return len(self.get_open_positions())

    def daily_realized_pnl(self) -> float:
        """Realized P&L for today."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL;")
        row = conn.execute(
            "SELECT COALESCE(SUM(realized_pnl), 0) FROM closed_positions WHERE closed_at LIKE ?",
            (f"{today}%",),
        ).fetchone()
        conn.close()
        return row[0] if row else 0.0