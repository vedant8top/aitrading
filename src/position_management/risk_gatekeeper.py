"""Risk gatekeeper: portfolio-level trade control before execution."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from src.position_management.portfolio_limits import PortfolioLimits
from src.position_management.position_manager import PositionManager
from src.position_management.exposure_tracker import ExposureTracker
from src.position_management.portfolio_snapshot import PortfolioSnapshot

logger = logging.getLogger("position_management.risk_gatekeeper")


class GateDecision:
    """Result of a risk gate check."""

    def __init__(self, approved: bool, reason: str = "", details: Optional[dict] = None) -> None:
        self.approved = approved
        self.reason = reason
        self.details = details or {}

    @property
    def decision(self) -> str:
        return "APPROVED" if self.approved else "REJECTED"

    def __repr__(self) -> str:
        return f"GateDecision({self.decision}, reason={self.reason!r})"


class RiskGatekeeper:
    """Portfolio-level risk gatekeeper.

    Approves or rejects trade signals before execution.

    Checks (in order):
    1. BUY only (SELL signals always approved)
    2. Duplicate position (already have open position in same symbol)
    3. Max open positions exceeded
    4. Position value exceeds max
    5. Total exposure would exceed max
    6. Daily loss limit exceeded
    7. Insufficient balance
    """

    def __init__(
        self,
        position_manager: PositionManager,
        exposure_tracker: ExposureTracker,
        snapshot: PortfolioSnapshot,
        limits: Optional[PortfolioLimits] = None,
    ) -> None:
        self.pm = position_manager
        self.exposure = exposure_tracker
        self.snapshot = snapshot
        self.limits = limits or PortfolioLimits()
        self._trade_log: list[dict] = []

    def evaluate(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        balance: float = 0.0,
        daily_realized_pnl: float = 0.0,
    ) -> GateDecision:
        """Evaluate a trade signal and return approval/rejection with reason.

        Args:
            symbol: Trading pair (e.g. "BTCUSDT").
            side: "BUY" or "SELL".
            quantity: Number of units.
            price: Current price.
            balance: Available cash balance.
            daily_realized_pnl: Today's realized P&L (negative = loss).

        Returns:
            GateDecision with approved=True/False and reason.
        """
        order_value = quantity * price

        # Rule 1: SELL signals always approved
        if side.upper() == "SELL":
            return GateDecision(True, "sell_approved", {"symbol": symbol, "quantity": quantity})

        # Rule 2: Duplicate position check
        existing = self.pm.get_position(symbol)
        if existing:
            self._log(symbol, side, "REJECTED", "duplicate_position", existing)
            return GateDecision(False, "duplicate_position", {"symbol": symbol})

        # Rule 3: Max open positions check
        current_count = self.pm.position_count()
        if current_count >= self.limits.max_open_positions:
            self._log(symbol, side, "REJECTED", "max_positions_exceeded", {"count": current_count})
            return GateDecision(False, "max_positions_exceeded", {"count": current_count, "limit": self.limits.max_open_positions})

        # Rule 4: Position value limit check
        if order_value > self.limits.max_position_value_usdt:
            self._log(symbol, side, "REJECTED", "position_value_exceeded", {"value": order_value})
            return GateDecision(False, "position_value_exceeded", {"value": order_value, "limit": self.limits.max_position_value_usdt})

        # Rule 5: Total exposure check
        total_exposure = self.exposure.get_total_exposure()
        projected = total_exposure + order_value
        if projected > self.limits.max_total_exposure_usdt:
            self._log(symbol, side, "REJECTED", "total_exposure_exceeded", {"projected": projected})
            return GateDecision(False, "total_exposure_exceeded", {"projected": projected, "limit": self.limits.max_total_exposure_usdt})

        # Rule 6: Daily loss limit check
        if daily_realized_pnl < -self.limits.daily_loss_limit_usdt:
            self._log(symbol, side, "REJECTED", "daily_loss_exceeded", {"daily_pnl": daily_realized_pnl})
            return GateDecision(False, "daily_loss_exceeded", {"daily_pnl": daily_realized_pnl, "limit": -self.limits.daily_loss_limit_usdt})

        # Rule 7: Insufficient balance check
        if order_value > balance:
            self._log(symbol, side, "REJECTED", "insufficient_balance", {"order_value": order_value, "balance": balance})
            return GateDecision(False, "insufficient_balance", {"order_value": order_value, "balance": balance})

        # All checks passed
        self._log(symbol, side, "APPROVED", "all_checks_passed", {"value": order_value})
        return GateDecision(True, "all_checks_passed", {
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": price,
            "value": round(order_value, 2),
        })

    def _log(self, symbol: str, side: str, decision: str, reason: str, details: dict) -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "symbol": symbol,
            "side": side,
            "decision": decision,
            "reason": reason,
            "details": details,
        }
        self._trade_log.append(entry)
        if decision == "REJECTED":
            logger.warning("TRADE REJECTED: %s %s %s — %s", side, symbol, reason, details)
        else:
            logger.info("TRADE APPROVED: %s %s — %s", side, symbol, details)

    def get_trade_log(self, limit: int = 100) -> list[dict]:
        """Get recent trade log entries."""
        return self._trade_log[-limit:]