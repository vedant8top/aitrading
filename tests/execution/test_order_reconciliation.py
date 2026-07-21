import pytest
from unittest.mock import MagicMock

from src.execution.order_reconciliation import OrderReconciliation
from src.execution.idempotency_manager import IdempotencyManager
from src.exchanges.binance_adapter import BinanceAdapter

@pytest.fixture
def order_reconciliation():
    """Fixture providing an OrderReconciliation instance with mocked dependencies."""
    mock_idempotency = MagicMock(spec=IdempotencyManager)
    mock_adapter = MagicMock(spec=BinanceAdapter)
    return OrderReconciliation(idempotency=mock_idempotency, adapter=mock_adapter)

def test_statuses_match_submitted(order_reconciliation):
    """Test _statuses_match when local status is SUBMITTED."""
    assert order_reconciliation._statuses_match(IdempotencyManager.STATUS_SUBMITTED, "NEW") is True
    assert order_reconciliation._statuses_match(IdempotencyManager.STATUS_SUBMITTED, "SUBMITTED") is True
    assert order_reconciliation._statuses_match(IdempotencyManager.STATUS_SUBMITTED, "FILLED") is False
    assert order_reconciliation._statuses_match(IdempotencyManager.STATUS_SUBMITTED, "CANCELED") is False
    assert order_reconciliation._statuses_match(IdempotencyManager.STATUS_SUBMITTED, "UNKNOWN") is False

def test_statuses_match_pending(order_reconciliation):
    """Test _statuses_match when local status is PENDING."""
    assert order_reconciliation._statuses_match(IdempotencyManager.STATUS_PENDING, "NEW") is True
    assert order_reconciliation._statuses_match(IdempotencyManager.STATUS_PENDING, "SUBMITTED") is True
    assert order_reconciliation._statuses_match(IdempotencyManager.STATUS_PENDING, "FILLED") is True
    assert order_reconciliation._statuses_match(IdempotencyManager.STATUS_PENDING, "PARTIALLY_FILLED") is False
    assert order_reconciliation._statuses_match(IdempotencyManager.STATUS_PENDING, "CANCELED") is False

def test_statuses_match_filled(order_reconciliation):
    """Test _statuses_match when local status is FILLED."""
    assert order_reconciliation._statuses_match(IdempotencyManager.STATUS_FILLED, "FILLED") is True
    assert order_reconciliation._statuses_match(IdempotencyManager.STATUS_FILLED, "NEW") is False
    assert order_reconciliation._statuses_match(IdempotencyManager.STATUS_FILLED, "CANCELED") is False

def test_statuses_match_cancelled(order_reconciliation):
    """Test _statuses_match when local status is CANCELLED."""
    assert order_reconciliation._statuses_match(IdempotencyManager.STATUS_CANCELLED, "CANCELED") is True
    assert order_reconciliation._statuses_match(IdempotencyManager.STATUS_CANCELLED, "CANCELLED") is False
    assert order_reconciliation._statuses_match(IdempotencyManager.STATUS_CANCELLED, "NEW") is False
    assert order_reconciliation._statuses_match(IdempotencyManager.STATUS_CANCELLED, "FILLED") is False

def test_statuses_match_unknown(order_reconciliation):
    """Test _statuses_match with unknown/fallback statuses."""
    assert order_reconciliation._statuses_match("UNKNOWN_LOCAL", "UNKNOWN_LOCAL") is True
    assert order_reconciliation._statuses_match("UNKNOWN_LOCAL", "DIFFERENT_EXCHANGE") is False

def test_statuses_match_case_insensitivity(order_reconciliation):
    """Test _statuses_match case insensitivity."""
    assert order_reconciliation._statuses_match(IdempotencyManager.STATUS_SUBMITTED.lower(), "new") is True
    assert order_reconciliation._statuses_match(IdempotencyManager.STATUS_PENDING.lower(), "filled") is True
    assert order_reconciliation._statuses_match(IdempotencyManager.STATUS_FILLED.lower(), "FILLED") is True
    assert order_reconciliation._statuses_match(IdempotencyManager.STATUS_CANCELLED.lower(), "canceled") is True
    assert order_reconciliation._statuses_match("unknown", "UNKNOWN") is True
