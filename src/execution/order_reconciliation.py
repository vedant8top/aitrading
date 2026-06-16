"""Order reconciliation: compares SQLite records against Binance Testnet."""

from __future__ import annotations

import logging
from typing import Optional

from src.exchanges.binance_adapter import BinanceAdapter
from src.execution.idempotency_manager import IdempotencyManager

logger = logging.getLogger("execution.reconciliation")


class OrderReconciliation:
    """Compares idempotency records (SQLite) against Binance Testnet order state.

    Detects:
    - Orders on exchange not in SQLite
    - Orders in SQLite not on exchange
    - Status mismatches (SQLite says PENDING, exchange says FILLED)
    - Partial fills
    """

    def __init__(self, idempotency: IdempotencyManager, adapter: BinanceAdapter) -> None:
        self.idempotency = idempotency
        self.adapter = adapter

    def reconcile(self) -> dict:
        """Run full reconciliation and return report."""
        report = {
            "matched": [],
            "mismatched": [],
            "missing_on_exchange": [],
            "exchange_only": [],
            "pending_resolved": 0,
            "total_checked": 0,
        }

        # 1. Check all SUBMITTED and PENDING orders against exchange
        for record in self.idempotency.get_submitted_orders() + self.idempotency.get_pending_orders():
            client_id = record["client_order_id"]
            exchange_status = self._query_exchange_status(record)

            report["total_checked"] += 1

            if exchange_status is None:
                # Order not found on exchange
                if record["status"] == IdempotencyManager.STATUS_PENDING:
                    report["pending_resolved"] += 1
                    self.idempotency.mark_failed(client_id, "Not found on exchange")
                    report["missing_on_exchange"].append(client_id)
                continue

            # Update exchange status in idempotency
            self.idempotency.update_exchange_status(client_id, exchange_status)

            # Check for status mismatch
            local_status = record["status"]
            if self._statuses_match(local_status, exchange_status):
                report["matched"].append({
                    "client_order_id": client_id,
                    "local_status": local_status,
                    "exchange_status": exchange_status,
                })
            else:
                report["mismatched"].append({
                    "client_order_id": client_id,
                    "local_status": local_status,
                    "exchange_status": exchange_status,
                })
                # Auto-resolve: if exchange says filled, update local
                if exchange_status in ("FILLED", "PARTIALLY_FILLED"):
                    self.idempotency.mark_filled(client_id)
                    report["pending_resolved"] += 1

        # 2. Check recently closed orders on exchange
        try:
            open_orders = self.adapter.get_open_orders()
            order_ids_on_exchange = {o["orderId"] for o in open_orders}
            local_order_ids = {
                r["order_id"] for r in self.idempotency.get_submitted_orders()
                if r["order_id"]
            }
            exchange_only = order_ids_on_exchange - local_order_ids
            for oid in exchange_only:
                report["exchange_only"].append(str(oid))
        except Exception as e:
            logger.error("Failed to fetch open orders from exchange: %s", e)

        return report

    def _query_exchange_status(self, record: dict) -> Optional[str]:
        """Query Binance for order status using order_id or client_order_id."""
        order_id = record.get("order_id")
        symbol = record.get("symbol", "")
        client_id = record.get("client_order_id", "")

        if not symbol:
            return None

        try:
            if order_id:
                order = self.adapter.client.get_order(symbol=symbol, orderId=order_id)
                return order.get("status")
            else:
                # Try querying by client_order_id (newClientOrderId)
                orders = self.adapter.client.get_all_orders(symbol=symbol, limit=5)
                for o in orders:
                    if o.get("clientOrderId") == client_id:
                        return o.get("status")
            return None
        except Exception as e:
            logger.warning("Failed to query exchange for %s: %s", client_id, e)
            return None

    def _statuses_match(self, local: str, exchange: str) -> bool:
        """Check if local status matches exchange status."""
        exchange_upper = exchange.upper()
        local_upper = local.upper()

        if local_upper == IdempotencyManager.STATUS_SUBMITTED:
            return exchange_upper in ("NEW", "SUBMITTED")
        if local_upper == IdempotencyManager.STATUS_PENDING:
            return exchange_upper in ("NEW", "SUBMITTED", "FILLED")
        if local_upper == IdempotencyManager.STATUS_FILLED:
            return exchange_upper in ("FILLED",)
        if local_upper == IdempotencyManager.STATUS_CANCELLED:
            return exchange_upper in ("CANCELED",)
        return local_upper == exchange_upper