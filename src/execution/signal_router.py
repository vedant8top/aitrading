"""Signal router: converts trading signals to execution requests."""

from __future__ import annotations

import logging
from typing import Optional

from src.execution.execution_models import ExecutionRequest, SignalSide

logger = logging.getLogger("execution.signal_router")


class SignalRouter:
    """Routes trading signals to execution requests.

    Converts BUY/SELL/HOLD signals into ExecutionRequest objects
    with appropriate parameters.
    """

    def __init__(
        self,
        default_max_value_usdt: float = 100.0,
        default_strategy: str = "",
    ) -> None:
        self.default_max_value_usdt = default_max_value_usdt
        self.default_strategy = default_strategy

    def route(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        strategy: str = "",
        signal_strength: float = 1.0,
        max_value_usdt: Optional[float] = None,
    ) -> Optional[ExecutionRequest]:
        """Convert a signal to an ExecutionRequest.

        Args:
            symbol: Trading pair (e.g. "BTCUSDT").
            side: "BUY", "SELL", or "HOLD".
            quantity: Number of units to trade.
            price: Current price (for value calculation).
            strategy: Strategy name that generated the signal.
            signal_strength: Signal confidence (0.0 to 1.0).
            max_value_usdt: Maximum order value in USDT.

        Returns:
            ExecutionRequest if side is BUY or SELL.
            None if side is HOLD.
        """
        if side.upper() == SignalSide.HOLD.value:
            logger.info("HOLD signal for %s — no execution request", symbol)
            return None

        if side.upper() not in (SignalSide.BUY.value, SignalSide.SELL.value):
            logger.warning("Invalid signal side: %s — ignoring", side)
            return None

        max_value = max_value_usdt or self.default_max_value_usdt
        order_value = price * quantity

        if order_value > max_value:
            logger.warning(
                "Order value %.2f USDT exceeds max %.2f USDT for %s — rejecting",
                order_value, max_value, symbol,
            )
            return None

        request = ExecutionRequest(
            symbol=symbol,
            side=side.upper(),
            quantity=quantity,
            order_type="MARKET",
            strategy=strategy or self.default_strategy,
            signal_strength=signal_strength,
            max_value_usdt=max_value,
        )

        logger.info(
            "Signal routed: %s %s %.8f @ %.2f = %.2f USDT (strategy=%s)",
            side, symbol, quantity, price, order_value, request.strategy,
        )

        return request

    def route_from_dict(self, signal: dict) -> Optional[ExecutionRequest]:
        """Route from a signal dict.

        Expected keys: symbol, side, quantity, price, strategy (optional),
                       signal_strength (optional), max_value_usdt (optional).
        """
        return self.route(
            symbol=signal["symbol"],
            side=signal["side"],
            quantity=signal["quantity"],
            price=signal["price"],
            strategy=signal.get("strategy", ""),
            signal_strength=signal.get("signal_strength", 1.0),
            max_value_usdt=signal.get("max_value_usdt"),
        )