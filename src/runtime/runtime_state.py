"""Runtime state: persisted state for the continuous runner."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("runtime.runtime_state")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "runtime_state.db"


class RuntimeState:
    """Persists runtime state to SQLite for restart recovery."""

    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)
        self._init_db()

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS runtime_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()

    def set(self, key: str, value: str) -> None:
        conn = sqlite3.connect(str(self.db_path))
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT OR REPLACE INTO runtime_state (key, value, updated_at) VALUES (?, ?, ?)",
            (key, value, now),
        )
        conn.commit()
        conn.close()

    def get(self, key: str) -> Optional[str]:
        conn = sqlite3.connect(str(self.db_path))
        row = conn.execute("SELECT value FROM runtime_state WHERE key = ?", (key,)).fetchone()
        conn.close()
        return row[0] if row else None

    def set_startup_time(self, timestamp: str) -> None:
        self.set("startup_time", timestamp)

    def get_startup_time(self) -> Optional[str]:
        return self.get("startup_time")

    def set_last_heartbeat(self, timestamp: str) -> None:
        self.set("last_heartbeat", timestamp)

    def get_last_heartbeat(self) -> Optional[str]:
        return self.get("last_heartbeat")

    def set_cycle_count(self, count: int) -> None:
        self.set("cycle_count", str(count))

    def get_cycle_count(self) -> int:
        val = self.get("cycle_count")
        return int(val) if val else 0

    def set_successful_cycles(self, count: int) -> None:
        self.set("successful_cycles", str(count))

    def get_successful_cycles(self) -> int:
        val = self.get("successful_cycles")
        return int(val) if val else 0

    def set_failed_cycles(self, count: int) -> None:
        self.set("failed_cycles", str(count))

    def get_failed_cycles(self) -> int:
        val = self.get("failed_cycles")
        return int(val) if val else 0

    def set_current_status(self, status: str) -> None:
        self.set("current_status", status)

    def get_current_status(self) -> str:
        return self.get("current_status") or "UNKNOWN"

    def set_process_id(self, pid: int) -> None:
        self.set("process_id", str(pid))

    def get_process_id(self) -> Optional[int]:
        val = self.get("process_id")
        return int(val) if val else None

    def increment_cycle(self, success: bool = True) -> tuple[int, int]:
        cycles = self.get_cycle_count() + 1
        self.set_cycle_count(cycles)
        if success:
            succ = self.get_successful_cycles() + 1
            self.set_successful_cycles(succ)
        else:
            fail = self.get_failed_cycles() + 1
            self.set_failed_cycles(fail)
        return (self.get_successful_cycles(), self.get_failed_cycles())

    def get_summary(self) -> dict:
        return {
            "startup_time": self.get_startup_time(),
            "last_heartbeat": self.get_last_heartbeat(),
            "cycle_count": self.get_cycle_count(),
            "successful_cycles": self.get_successful_cycles(),
            "failed_cycles": self.get_failed_cycles(),
            "current_status": self.get_current_status(),
            "process_id": self.get_process_id(),
        }