"""Order manager: handles order placement and lifecycle via BinanceAdapter."""

from __future__ import annotations

import logging
from typing import Optional

from src.execution.execution_models import (
    ExecutionRequest,
    ExecutionResult,
    OrderStatus,
    PositionSnapshot,
)
from src.exchanges.binance_adapter import BinanceAdapter, BinanceAdapterError

logger = logging.getLogger("execution.order_manager")


class OrderManagerError(RuntimeError):
    """Order manager specific error."""


class OrderManager:
    """Manages order lifecycle using BinanceAdapter.

    Responsibilities:
    - Place buy/sell orders
    - Query order status
    - Cancel orders
    - Reconcile positions
    """

    def __init__(self, adapter: BinanceAdapter) -> None:
        self.adapter = adapter

    def place_order(self, request: ExecutionRequest) -> ExecutionResult:
        """Place an order based on an ExecutionRequest.

        Args:
            request: ExecutionRequest with order details.

        Returns:
            ExecutionResult with order outcome.
        """
        try:
            if request.side == "BUY":
                order = self.adapter.place_market_buy(request.symbol, request.quantity)
            elif request.side == "SELL":
                order = self.adapter.place_market_sell(request.symbol, request.quantity)
            else:
                return ExecutionResult(
                    order_id="",
                    symbol=request.symbol,
                    side=request.side,
                    quantity=request.quantity,
                    price=0.0,
                    status=OrderStatus.REJECTED,
                    strategy=request.strategy,
                    raw_response={"error": f"Invalid side: {request.side}"},
                )

            result = self._parse_order_response(order, request)
            logger.info(
                "Order placed: %s %s %.8f @ %.2f (id=%s, status=%s)",
                result.side, result.symbol, result.quantity, result.price,
                result.order_id, result.status.value,
            )
            return result

        except BinanceAdapterError as e:
            logger.error("Order failed for %s: %s", request.symbol, e)
            return ExecutionResult(
                order_id="",
                symbol=request.symbol,
                side=request.side,
                quantity=request.quantity,
                price=0.0,
                status=OrderStatus.REJECTED,
                strategy=request.strategy,
                raw_response={"error": str(e)},
            )

    def _parse_order_response(self, order: dict, request: ExecutionRequest) -> ExecutionResult:
        """Parse Binance order response into ExecutionResult."""
        status_str = order.get("status", "UNKNOWN")
        status_map = {
            "FILLED": OrderStatus.FILLED,
            "PARTIALLY_FILLED": OrderStatus.PARTIALLY_FILLED,
            "NEW": OrderStatus.PENDING,
            "CANCELED": OrderStatus.CANCELLED,
            "REJECTED": OrderStatus.REJECTED,
        }
        status = status_map.get(status_str, OrderStatus.PENDING)

        filled_qty = 0.0
        avg_price = 0.0
        commission = 0.0

        # Parse fills
        fills = order.get("fills", [])
        if fills:
            total_qty = sum(float(f.get("qty", 0)) for f in fills)
            total_quote = sum(float(f.get("qty", 0)) * float(f.get("price", 0)) for f in fills)
            filled_qty = total_qty
            avg_price = total_quote / total_qty if total_qty > 0 else 0.0
            commission = sum(float(f.get("commission", 0)) for f in fills)
        else:
            avg_price = float(order.get("price", 0))
            filled_qty = float(order.get("executedQty", 0))

        return ExecutionResult(
            order_id=str(order.get("orderId", "")),
            symbol=order.get("symbol", request.symbol),
            side=request.side,
            quantity=float(order.get("origQty", request.quantity)),
            price=avg_price,
            status=status,
            strategy=request.strategy,
            filled_qty=filled_qty,
            commission=commission,
            raw_response=order,
        )

    def get_order_status(self, order_id: str, symbol: str) -> dict:
        """Query order status from the exchange.

        Args:
            order_id: Exchange order ID.
            symbol: Trading pair.

        Returns:
            Order details dict.
        """
        try:
            order = self.adapter.client.get_order(symbol=symbol, orderId=order_id)
            logger.info("Order %s status: %s", order_id, order.get("status"))
            return order
        except Exception as e:
            logger.error("Failed to query order %s: %s", order_id, e)
            raise OrderManagerError(f"Failed to query order {order_id}: {e}") from e

    def cancel_order(self, order_id: str, symbol: str) -> dict:
        """Cancel an open order.

        Args:
            order_id: Exchange order ID.
            symbol: Trading pair.

        Returns:
            Cancellation result.
        """
        try:
            result = self.adapter.cancel_order(order_id, symbol)
            logger.info("Order %s cancelled for %s", order_id, symbol)
            return result
        except Exception as e:
            logger.error("Failed to cancel order %s: %s", order_id, e)
            raise OrderManagerError(f"Failed to cancel order {order_id}: {e}") from e

    def get_positions(self) -> list[PositionSnapshot]:
        """Get current positions as PositionSnapshot list.

        Returns:
            List of PositionSnapshot objects.
        """
        try:
            balances = self.adapter.get_account_balance()
            positions = []
            for asset, data in balances.items():
                if data["total"] > 0:
                    positions.append(PositionSnapshot(
                        symbol=f"{asset}USDT",
                        asset=asset,
                        free=data["free"],
                        locked=data["locked"],
                        value_usdt=None,
                    ))
            logger.info("Positions retrieved: %d assets", len(positions))
            return positions
        except Exception as e:
            logger.error("Failed to get positions: %s", e)
            raise OrderManagerError(f"Failed to get positions: {e}") from e

    def reconcile_positions(self, expected: dict, actual: dict) -> dict:
        """Compare expected vs actual positions.

        Args:
            expected: Expected {asset: quantity} dict.
            actual: Actual {asset: quantity} dict.

        Returns:
            Dict with "matched", "surplus", "deficit" lists.
        """
        matched = []
        surplus = []
        deficit = []

        all_assets = set(list(expected.keys()) + list(actual.keys()))
        for asset in all_assets:
            exp = expected.get(asset, 0.0)
            act = actual.get(asset, 0.0)
            if abs(exp - act) < 1e-10:
                matched.append(asset)
            elif act > exp:
                surplus.append({"asset": asset, "expected": exp, "actual": act})
            else:
                deficit.append({"asset": asset, "expected": exp, "actual": act})

        result = {
            "matched": matched,
            "surplus": surplus,
            "deficit": deficit,
            "is_balanced": len(surplus) == 0 and len(deficit) == 0,
        }

        logger.info(
            "Reconciliation: matched=%d, surplus=%d, deficit=%d",
            len(matched), len(surplus), len(deficit),
        )
        return result