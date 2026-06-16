"""Data models for the testnet execution layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class OrderStatus(str, Enum):
    """Status of an order."""
    PENDING = "pending"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class SignalSide(str, Enum):
    """Trading signal side."""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass
class ExecutionRequest:
    """Request to execute a trade."""
    symbol: str
    side: str  # "BUY" or "SELL"
    quantity: float
    order_type: str = "MARKET"  # "MARKET" or "LIMIT"
    strategy: str = ""
    signal_strength: float = 1.0
    max_value_usdt: float = 100.0  # Safety: max order value in USDT
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "order_type": self.order_type,
            "strategy": self.strategy,
            "signal_strength": self.signal_strength,
            "max_value_usdt": self.max_value_usdt,
            "timestamp": self.timestamp,
        }


@dataclass
class ExecutionResult:
    """Result of an executed trade."""
    order_id: str
    symbol: str
    side: str
    quantity: float
    price: float
    status: OrderStatus
    strategy: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    pnl: Optional[float] = None
    filled_qty: Optional[float] = None
    commission: Optional[float] = None
    raw_response: Optional[dict] = None

    def to_dict(self) -> dict:
        return {
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "price": self.price,
            "status": self.status.value if isinstance(self.status, OrderStatus) else self.status,
            "strategy": self.strategy,
            "timestamp": self.timestamp,
            "pnl": self.pnl,
            "filled_qty": self.filled_qty,
            "commission": self.commission,
        }


@dataclass
class PositionSnapshot:
    """Snapshot of a position."""
    symbol: str
    asset: str
    free: float
    locked: float
    value_usdt: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "asset": self.asset,
            "free": self.free,
            "locked": self.locked,
            "total": self.free + self.locked,
            "value_usdt": self.value_usdt,
        }