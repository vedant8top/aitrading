"""Execution recovery: recovers pending/submitted orders after restart or crash."""

from __future__ import annotations

import logging
from typing import Optional

from src.exchanges.binance_adapter import BinanceAdapter
from src.execution.idempotency_manager import IdempotencyManager
from src.execution.order_reconciliation import OrderReconciliation

logger = logging.getLogger("execution.recovery")


class ExecutionRecovery:
    """Recovers pending/submitted orders after restart or crash.

    On startup:
    1. Load all PENDING and SUBMITTED orders from idempotency DB
    2. Query Binance for their current status using client_order_id
    3. Update local state to match exchange state
    4. Auto-resolve: fill orders that exchange says are filled
    5. Cancel orders that exchange says never arrived (timeout)
    6. Report recovery results
    """

    def __init__(self, idempotency: IdempotencyManager, adapter: BinanceAdapter) -> None:
        self.idempotency = idempotency
        self.adapter = adapter
        self.reconciler = OrderReconciliation(idempotency, adapter)

    def recover(self) -> dict:
        """Run full recovery process.

        Returns:
            Dict with recovery results:
            - pending_recovered: orders found in PENDING state
            - submitted_verified: orders confirmed SUBMITTED
            - auto_filled: orders that exchange reported as filled
            - timed_out: orders lost due to timeout
            - errors: failed queries
        """
        results = {
            "pending_recovered": 0,
            "submitted_verified": 0,
            "auto_filled": 0,
            "timed_out": 0,
            "errors": [],
            "details": [],
        }

        # Run reconciliation
        reconciliation_report = self.reconciler.reconcile()

        results["pending_recovered"] = len(self.idempotency.get_pending_orders())
        results["submitted_verified"] = len(self.idempotency.get_submitted_orders())
        results["auto_filled"] = reconciliation_report["pending_resolved"]

        for m in reconciliation_report["mismatched"]:
            results["details"].append({
                "client_order_id": m["client_order_id"],
                "local": m["local_status"],
                "exchange": m["exchange_status"],
                "action": "auto_filled" if m["exchange_status"] in ("FILLED", "PARTIALLY_FILLED") else "mismatch",
            })

        for mid in reconciliation_report["missing_on_exchange"]:
            results["timed_out"] += 1
            results["details"].append({
                "client_order_id": mid,
                "action": "timed_out",
            })

        logger.info("Recovery complete: %d pending, %d submitted, %d auto-filled, %d timed out",
                     results["pending_recovered"], results["submitted_verified"],
                     results["auto_filled"], results["timed_out"])

        return results

    def check_and_resubmit(self, client_order_id: str) -> Optional[dict]:
        """Check if a specific order needs resubmission.

        Used for handling timeout scenarios:
        1. Query exchange by order_id or client_order_id
        2. If not found on exchange and local status is PENDING → resubmit
        3. If found on exchange → update local status
        4. If filled → mark as filled, do not resubmit
        """
        record = self.idempotency.get_order(client_order_id)
        if not record:
            logger.warning("No idempotency record for %s", client_order_id)
            return None

        result = {
            "client_order_id": client_order_id,
            "local_status": record["status"],
            "exchange_status": None,
            "needs_resubmit": False,
        }

        exchange_status = self.reconciler._query_exchange_status(record)

        if exchange_status is None:
            # Order not found on exchange
            if record["status"] == IdempotencyManager.STATUS_PENDING:
                # Timeout: order was submitted but never arrived
                result["exchange_status"] = "NOT_FOUND"
                result["needs_resubmit"] = True
                result["action"] = "resubmit_needed"
                logger.warning("Order %s not found on exchange — needs resubmit", client_order_id)
            else:
                result["exchange_status"] = "NOT_FOUND"
                result["action"] = "mark_failed"
                self.idempotency.mark_failed(client_order_id, "Not found on exchange after restart")
        else:
            result["exchange_status"] = exchange_status
            self.idempotency.update_exchange_status(client_order_id, exchange_status)

            if exchange_status in ("FILLED",):
                result["action"] = "already_filled"
                self.idempotency.mark_filled(client_order_id)
            elif exchange_status in ("CANCELED",):
                result["action"] = "already_cancelled"
                self.idempotency.mark_cancelled(client_order_id)
            elif exchange_status in ("NEW", "PARTIALLY_FILLED"):
                result["action"] = "still_active"
                result["needs_resubmit"] = False

        return result

    def resolve_timeout(self, client_order_id: str) -> bool:
        """Handle timeout scenario: check exchange, resubmit if needed.

        Returns:
            True if order was resolved (found on exchange or already processed).
            False if resubmit is needed.
        """
        result = self.check_and_resubmit(client_order_id)
        if result is None:
            return True
        return not result["needs_resubmit"]