"""Runner state: persists runner state to SQLite for restart recovery."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("live_trading.runner_state")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "live_runner_state.db"


class RunnerState:
    """Persists runner state to SQLite for restart recovery.

    Persists:
    - last scan time
    - last signal time
    - last execution time
    - active symbols
    - signal history
    """

    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize SQLite database."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS runner_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS signal_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                signal TEXT NOT NULL,
                price REAL,
                strategy TEXT,
                timestamp TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()
        logger.info("Runner state database initialized: %s", self.db_path)

    def set_state(self, key: str, value: str) -> None:
        """Set a state value."""
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL;")
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT OR REPLACE INTO runner_state (key, value, updated_at) VALUES (?, ?, ?)",
            (key, value, now),
        )
        conn.commit()
        conn.close()

    def get_state(self, key: str) -> Optional[str]:
        """Get a state value."""
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL;")
        row = conn.execute("SELECT value FROM runner_state WHERE key = ?", (key,)).fetchone()
        conn.close()
        return row[0] if row else None

    def set_last_scan_time(self, timestamp: str) -> None:
        """Set last scan time."""
        self.set_state("last_scan_time", timestamp)

    def get_last_scan_time(self) -> Optional[str]:
        """Get last scan time."""
        return self.get_state("last_scan_time")

    def set_last_signal_time(self, timestamp: str) -> None:
        """Set last signal time."""
        self.set_state("last_signal_time", timestamp)

    def get_last_signal_time(self) -> Optional[str]:
        """Get last signal time."""
        return self.get_state("last_signal_time")

    def set_last_execution_time(self, timestamp: str) -> None:
        """Set last execution time."""
        self.set_state("last_execution_time", timestamp)

    def get_last_execution_time(self) -> Optional[str]:
        """Get last execution time."""
        return self.get_state("last_execution_time")

    def set_active_symbols(self, symbols: list[str]) -> None:
        """Set active symbols."""
        self.set_state("active_symbols", json.dumps(symbols))

    def get_active_symbols(self) -> list[str]:
        """Get active symbols."""
        val = self.get_state("active_symbols")
        if val:
            return json.loads(val)
        return []

    def log_signal(self, symbol: str, signal: str, price: float, strategy: str = "") -> None:
        """Log a signal to the database."""
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL;")
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO signal_log (symbol, signal, price, strategy, timestamp) VALUES (?, ?, ?, ?, ?)",
            (symbol, signal, price, strategy, now),
        )
        conn.commit()
        conn.close()
        logger.info("Signal logged: %s %s @ %.2f (strategy=%s)", symbol, signal, price, strategy)

    def get_signal_history(self, limit: int = 100) -> list[dict]:
        """Get recent signal history."""
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM signal_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_state_summary(self) -> dict:
        """Get full state summary."""
        return {
            "last_scan_time": self.get_last_scan_time(),
            "last_signal_time": self.get_last_signal_time(),
            "last_execution_time": self.get_last_execution_time(),
            "active_symbols": self.get_active_symbols(),
            "signal_count": len(self.get_signal_history(limit=10000)),
        }