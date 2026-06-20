"""Idempotency manager: prevents duplicate order submission using client_order_id."""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("execution.idempotency")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "idempotency.db"


class IdempotencyManager:
    """Idempotency manager using client_order_id to prevent duplicate orders.

    Flow:
    1. Generate unique client_order_id from request fingerprint
    2. Persist client_order_id with status=PENDING before submission
    3. Submit order to Binance with client_order_id
    4. Update status to SUBMITTED after submission
    5. On restart: recover pending orders and check exchange status
    """

    STATUS_PENDING = "PENDING"
    STATUS_SUBMITTED = "SUBMITTED"
    STATUS_FILLED = "FILLED"
    STATUS_CANCELLED = "CANCELLED"
    STATUS_FAILED = "FAILED"

    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)
        self._init_db()

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS idempotency (
                client_order_id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                quantity REAL NOT NULL,
                status TEXT NOT NULL,
                fingerprint TEXT NOT NULL,
                order_id TEXT,
                exchange_status TEXT,
                request_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()

    def generate_client_order_id(self, symbol: str, side: str, quantity: float, strategy: str = "") -> str:
        """Generate a unique client_order_id from request fingerprint.

        Combines request parameters with a UUID for uniqueness.
        """
        raw = f"{symbol}_{side}_{quantity}_{strategy}_{time.time_ns()}"
        fingerprint = hashlib.sha256(raw.encode()).hexdigest()[:16]
        uid = uuid.uuid4().hex[:8]
        client_order_id = f"TA_{fingerprint}_{uid}"
        return client_order_id

    def register_pending(self, client_order_id: str, symbol: str, side: str, quantity: float,
                          fingerprint: str = "", request_json: Optional[dict] = None) -> None:
        """Register a pending order before submission."""
        now = datetime.now(timezone.utc).isoformat()
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute(
            """INSERT OR REPLACE INTO idempotency
               (client_order_id, symbol, side, quantity, status, fingerprint, request_json, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (client_order_id, symbol, side, quantity, self.STATUS_PENDING,
             fingerprint, json.dumps(request_json) if request_json else None, now, now),
        )
        conn.commit()
        conn.close()
        logger.info("Registered pending order: %s (%s %s %s)", client_order_id, side, quantity, symbol)

    def mark_submitted(self, client_order_id: str, order_id: str) -> None:
        """Mark order as submitted after successful exchange submission."""
        now = datetime.now(timezone.utc).isoformat()
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute(
            "UPDATE idempotency SET status=?, order_id=?, updated_at=? WHERE client_order_id=?",
            (self.STATUS_SUBMITTED, order_id, now, client_order_id),
        )
        conn.commit()
        conn.close()
        logger.info("Order submitted: %s -> exchange order %s", client_order_id, order_id)

    def mark_filled(self, client_order_id: str) -> None:
        """Mark order as filled."""
        now = datetime.now(timezone.utc).isoformat()
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute(
            "UPDATE idempotency SET status=?, updated_at=? WHERE client_order_id=?",
            (self.STATUS_FILLED, now, client_order_id),
        )
        conn.commit()
        conn.close()

    def mark_cancelled(self, client_order_id: str) -> None:
        """Mark order as cancelled."""
        now = datetime.now(timezone.utc).isoformat()
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute(
            "UPDATE idempotency SET status=?, updated_at=? WHERE client_order_id=?",
            (self.STATUS_CANCELLED, now, client_order_id),
        )
        conn.commit()
        conn.close()

    def mark_failed(self, client_order_id: str, error: str = "") -> None:
        """Mark order as failed."""
        now = datetime.now(timezone.utc).isoformat()
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute(
            "UPDATE idempotency SET status=?, updated_at=? WHERE client_order_id=?",
            (self.STATUS_FAILED, now, client_order_id),
        )
        conn.commit()
        conn.close()
        logger.error("Order failed: %s (%s)", client_order_id, error)

    def is_duplicate(self, client_order_id: str) -> bool:
        """Check if a client_order_id already exists (duplicate detection)."""
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL;")
        row = conn.execute(
            "SELECT status FROM idempotency WHERE client_order_id=?",
            (client_order_id,),
        ).fetchone()
        conn.close()
        if row:
            logger.warning("Duplicate client_order_id detected: %s (status=%s)", client_order_id, row[0])
            return True
        return False

    def get_order(self, client_order_id: str) -> Optional[dict]:
        """Get idempotency record for a client_order_id."""
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM idempotency WHERE client_order_id=?",
            (client_order_id,),
        ).fetchone()
        conn.close()
        if row:
            return dict(row)
        return None

    def get_pending_orders(self) -> list[dict]:
        """Get all orders in PENDING status (recovery candidates)."""
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM idempotency WHERE status=? ORDER BY created_at ASC",
            (self.STATUS_PENDING,),
        ).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_submitted_orders(self) -> list[dict]:
        """Get all orders in SUBMITTED status (check if filled)."""
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM idempotency WHERE status=? ORDER BY created_at ASC",
            (self.STATUS_SUBMITTED,),
        ).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def update_exchange_status(self, client_order_id: str, exchange_status: str) -> None:
        """Update exchange status for an idempotency record."""
        now = datetime.now(timezone.utc).isoformat()
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute(
            "UPDATE idempotency SET exchange_status=?, updated_at=? WHERE client_order_id=?",
            (exchange_status, now, client_order_id),
        )
        conn.commit()
        conn.close()

    def get_summary(self) -> dict:
        """Get summary of all idempotency records."""
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL;")
        total = conn.execute("SELECT COUNT(*) FROM idempotency").fetchone()[0]
        pending = conn.execute("SELECT COUNT(*) FROM idempotency WHERE status=?", (self.STATUS_PENDING,)).fetchone()[0]
        submitted = conn.execute("SELECT COUNT(*) FROM idempotency WHERE status=?", (self.STATUS_SUBMITTED,)).fetchone()[0]
        filled = conn.execute("SELECT COUNT(*) FROM idempotency WHERE status=?", (self.STATUS_FILLED,)).fetchone()[0]
        failed = conn.execute("SELECT COUNT(*) FROM idempotency WHERE status=?", (self.STATUS_FAILED,)).fetchone()[0]
        conn.close()
        return {
            "total": total,
            "pending": pending,
            "submitted": submitted,
            "filled": filled,
            "failed": failed,
        }