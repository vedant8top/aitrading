"""Execution engine: orchestrates signal validation, order placement, and persistence."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.execution.execution_models import (
    ExecutionRequest,
    ExecutionResult,
    OrderStatus,
)
from src.execution.signal_router import SignalRouter
from src.execution.order_manager import OrderManager
from src.exchanges.binance_adapter import BinanceAdapter
from src.exchanges.binance_market_data import BinanceMarketData

logger = logging.getLogger("execution.engine")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "execution_log.db"


class ExecutionEngineError(RuntimeError):
    """Execution engine specific error."""


class ExecutionEngine:
    """Orchestrates the full execution flow.

    Flow:
    1. Receive signal
    2. Validate symbol
    3. Validate balance
    4. Validate order value (max 100 USDT)
    5. Create order via OrderManager
    6. Persist result to SQLite
    """

    def __init__(
        self,
        adapter: BinanceAdapter,
        market: BinanceMarketData,
        router: Optional[SignalRouter] = None,
        order_manager: Optional[OrderManager] = None,
        db_path: Path | str = DEFAULT_DB_PATH,
        max_order_value_usdt: float = 100.0,
    ) -> None:
        self.adapter = adapter
        self.market = market
        self.router = router or SignalRouter(default_max_value_usdt=max_order_value_usdt)
        self.order_manager = order_manager or OrderManager(adapter)
        self.db_path = Path(db_path)
        self.max_order_value_usdt = max_order_value_usdt
        self._init_db()

    def _init_db(self) -> None:
        """Initialize SQLite execution log database."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS execution_log (
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
            )
        """)
        conn.commit()
        conn.close()
        logger.info("Execution log database initialized: %s", self.db_path)

    def _persist_result(self, result: ExecutionResult) -> None:
        """Persist an ExecutionResult to SQLite."""
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute(
                """INSERT INTO execution_log
                   (order_id, symbol, side, quantity, price, status, strategy, timestamp, pnl, commission, raw_response)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    result.order_id,
                    result.symbol,
                    result.side,
                    result.quantity,
                    result.price,
                    result.status.value if isinstance(result.status, OrderStatus) else result.status,
                    result.strategy,
                    result.timestamp,
                    result.pnl,
                    result.commission,
                    json.dumps(result.raw_response) if result.raw_response else None,
                ),
            )
            conn.commit()
            conn.close()
            logger.info("Execution result persisted: order_id=%s", result.order_id)
        except Exception as e:
            logger.error("Failed to persist execution result: %s", e)

    def validate_symbol(self, symbol: str) -> bool:
        """Validate that a symbol exists and is trading."""
        is_valid = self.market.validate_symbol(symbol)
        if not is_valid:
            logger.warning("Symbol validation failed: %s", symbol)
        return is_valid

    def validate_order_value(self, price: float, quantity: float) -> bool:
        """Validate order value does not exceed max allowed."""
        value = price * quantity
        if value > self.max_order_value_usdt:
            logger.warning(
                "Order value %.2f USDT exceeds max %.2f USDT — rejecting",
                value, self.max_order_value_usdt,
            )
            return False
        return True

    def validate_balance(self, symbol: str, side: str, quantity: float) -> bool:
        """Validate sufficient balance for the order."""
        try:
            balances = self.adapter.get_account_balance()
            asset = symbol.replace("USDT", "")

            if side == "SELL":
                balance = balances.get(asset, {}).get("free", 0.0)
                if balance < quantity:
                    logger.warning(
                        "Insufficient %s balance: have %.8f, need %.8f",
                        asset, balance, quantity,
                    )
                    return False
            elif side == "BUY":
                usdt_balance = balances.get("USDT", {}).get("free", 0.0)
                price = self.market.get_ticker_price(symbol)["price"]
                needed = price * quantity
                if usdt_balance < needed:
                    logger.warning(
                        "Insufficient USDT: have %.2f, need %.2f",
                        usdt_balance, needed,
                    )
                    return False

            return True
        except Exception as e:
            logger.error("Balance validation failed: %s", e)
            return False

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        """Execute a validated order.

        Args:
            request: Validated ExecutionRequest.

        Returns:
            ExecutionResult with order outcome.
        """
        # Step 1: Validate symbol
        if not self.validate_symbol(request.symbol):
            return ExecutionResult(
                order_id="",
                symbol=request.symbol,
                side=request.side,
                quantity=request.quantity,
                price=0.0,
                status=OrderStatus.REJECTED,
                strategy=request.strategy,
                raw_response={"error": "Symbol validation failed"},
            )

        # Step 2: Validate order value
        try:
            price = self.market.get_ticker_price(request.symbol)["price"]
        except Exception:
            price = 0.0

        if not self.validate_order_value(price, request.quantity):
            return ExecutionResult(
                order_id="",
                symbol=request.symbol,
                side=request.side,
                quantity=request.quantity,
                price=price,
                status=OrderStatus.REJECTED,
                strategy=request.strategy,
                raw_response={"error": "Order value exceeds max allowed"},
            )

        # Step 3: Validate balance
        if not self.validate_balance(request.symbol, request.side, request.quantity):
            return ExecutionResult(
                order_id="",
                symbol=request.symbol,
                side=request.side,
                quantity=request.quantity,
                price=price,
                status=OrderStatus.REJECTED,
                strategy=request.strategy,
                raw_response={"error": "Insufficient balance"},
            )

        # Step 4: Place order
        result = self.order_manager.place_order(request)

        # Step 5: Persist result
        self._persist_result(result)

        return result

    def execute_signal(
        self,
        symbol: str,
        side: str,
        quantity: float,
        strategy: str = "manual",
    ) -> ExecutionResult:
        """Full execution flow from signal to result.

        Args:
            symbol: Trading pair (e.g. "BTCUSDT").
            side: "BUY", "SELL", or "HOLD".
            quantity: Number of units.
            strategy: Strategy name.

        Returns:
            ExecutionResult with order outcome.
        """
        # Get price for routing
        try:
            price = self.market.get_ticker_price(symbol)["price"]
        except Exception as e:
            logger.error("Failed to get price for %s: %s", symbol, e)
            return ExecutionResult(
                order_id="",
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=0.0,
                status=OrderStatus.REJECTED,
                strategy=strategy,
                raw_response={"error": f"Price fetch failed: {e}"},
            )

        # Route signal
        request = self.router.route(
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            strategy=strategy,
            max_value_usdt=self.max_order_value_usdt,
        )

        if request is None:
            return ExecutionResult(
                order_id="",
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=price,
                status=OrderStatus.REJECTED,
                strategy=strategy,
                raw_response={"error": "Router rejected request (HOLD or value exceeded)"},
            )

        # Execute
        return self.execute(request)

    def get_execution_history(self, limit: int = 100) -> list[dict]:
        """Get recent execution history from SQLite."""
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM execution_log ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            conn.close()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error("Failed to get execution history: %s", e)
            return []