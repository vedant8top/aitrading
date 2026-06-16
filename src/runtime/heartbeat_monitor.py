"""Heartbeat monitor: persists periodic heartbeats to SQLite."""

from __future__ import annotations

import logging
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("runtime.heartbeat")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "runtime_state.db"


class HeartbeatMonitor:
    """Persists heartbeat every cycle.

    Tracks:
    - timestamp
    - runner status
    - cycle number
    - memory usage
    - process uptime
    """

    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)
        self._start_time = time.time()
        self._init_db()

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS heartbeats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                status TEXT NOT NULL,
                cycle_number INTEGER,
                memory_mb REAL,
                uptime_seconds REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

    def _get_memory_mb(self) -> float:
        try:
            import psutil
            process = psutil.Process(os.getpid())
            return process.memory_info().rss / (1024 * 1024)
        except ImportError:
            return 0.0

    def beat(self, status: str = "running", cycle_number: int = 0) -> dict:
        """Record a heartbeat."""
        now = datetime.now(timezone.utc).isoformat()
        uptime = time.time() - self._start_time
        memory = self._get_memory_mb()

        conn = sqlite3.connect(str(self.db_path))
        conn.execute(
            """INSERT INTO heartbeats (timestamp, status, cycle_number, memory_mb, uptime_seconds)
               VALUES (?, ?, ?, ?, ?)""",
            (now, status, cycle_number, memory, uptime),
        )
        conn.commit()
        conn.close()

        logger.info(
            "Heartbeat #%d: status=%s, uptime=%.1fs, memory=%.1fMB",
            cycle_number, status, uptime, memory,
        )

        return {
            "timestamp": now,
            "status": status,
            "cycle_number": cycle_number,
            "memory_mb": memory,
            "uptime_seconds": uptime,
        }

    def get_latest_heartbeat(self) -> Optional[dict]:
        """Get the most recent heartbeat."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM heartbeats ORDER BY id DESC LIMIT 1"
        ).fetchone()
        conn.close()
        if row:
            return dict(row)
        return None

    def get_heartbeat_history(self, limit: int = 100) -> list[dict]:
        """Get recent heartbeat history."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM heartbeats ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def seconds_since_last_beat(self) -> Optional[float]:
        """Seconds since last heartbeat."""
        latest = self.get_latest_heartbeat()
        if latest is None:
            return None
        from datetime import datetime as dt
        last_time = dt.fromisoformat(latest["timestamp"]).replace(tzinfo=timezone.utc).timestamp()
        return time.time() - last_time

    def uptime_seconds(self) -> float:
        """Current process uptime in seconds."""
        return time.time() - self._start_time