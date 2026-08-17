"""Tests for Binance Spot Testnet adapter."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceRequestException

from src.exchanges.binance_adapter import BinanceAdapter, BinanceAdapterError


@pytest.fixture
def mock_env():
    """Mock the .env file and os.getenv."""
    with patch("src.exchanges.binance_adapter.Path.exists", return_value=True):
        with patch("src.exchanges.binance_adapter.load_dotenv"):
            with patch.dict(os.environ, {
                "BINANCE_API_KEY": "test_api_key",
                "BINANCE_SECRET_KEY": "test_secret_key",
                "BINANCE_TESTNET": "true"
            }):
                yield


def test_init_loads_credentials(mock_env):
    """Test successful initialization with valid credentials."""
    adapter = BinanceAdapter()
    assert adapter._api_key == "test_api_key"
    assert adapter._secret_key == "test_secret_key"
    assert adapter._testnet is True
    assert adapter._client is None


def test_init_missing_env_file():
    """Test initialization fails if .env is missing."""
    with patch("src.exchanges.binance_adapter.Path.exists", return_value=False):
        with pytest.raises(BinanceAdapterError, match=".env not found at"):
            BinanceAdapter()


def test_init_missing_credentials():
    """Test initialization fails if API keys are missing."""
    with patch("src.exchanges.binance_adapter.Path.exists", return_value=True):
        with patch("src.exchanges.binance_adapter.load_dotenv"):
            with patch.dict(os.environ, {}, clear=True):
                with pytest.raises(BinanceAdapterError, match="BINANCE_API_KEY and BINANCE_SECRET_KEY must be set"):
                    BinanceAdapter()


def test_init_placeholder_credentials():
    """Test initialization fails if API keys are placeholders."""
    with patch("src.exchanges.binance_adapter.Path.exists", return_value=True):
        with patch("src.exchanges.binance_adapter.load_dotenv"):
            with patch.dict(os.environ, {
                "BINANCE_API_KEY": "PASTE_YOUR_API_KEY_HERE",
                "BINANCE_SECRET_KEY": "test_secret_key"
            }, clear=True):
                with pytest.raises(BinanceAdapterError, match="Placeholder BINANCE_API_KEY detected"):
                    BinanceAdapter()


def test_handle_exception_binance_api(mock_env):
    """Test _handle_exception maps BinanceAPIException to BinanceAdapterError."""
    adapter = BinanceAdapter()
    dummy_response = MagicMock()
    dummy_response.status_code = 400
    dummy_response.json.return_value = {"code": -1121, "msg": "Invalid symbol"}
    dummy_response.text = '{"code": -1121, "msg": "Invalid symbol"}'
    api_exc = BinanceAPIException(dummy_response, 400, "Invalid symbol")

    # We should match the dynamically constructed error message using regex .* or exact match
    with pytest.raises(BinanceAdapterError, match="Binance API error in test_context:.*"):
        adapter._handle_exception(api_exc, "test_context")


def test_handle_exception_binance_request(mock_env):
    """Test _handle_exception maps BinanceRequestException to BinanceAdapterError."""
    adapter = BinanceAdapter()
    req_exc = BinanceRequestException("Request timeout")

    with pytest.raises(BinanceAdapterError, match="Binance request error in test_context: BinanceRequestException: Request timeout"):
        adapter._handle_exception(req_exc, "test_context")


def test_handle_exception_generic(mock_env):
    """Test _handle_exception maps generic Exception to BinanceAdapterError."""
    adapter = BinanceAdapter()
    exc = ValueError("Some value error")

    with pytest.raises(BinanceAdapterError, match="Unexpected error in test_context: Some value error"):
        adapter._handle_exception(exc, "test_context")


@pytest.fixture
def adapter(mock_env):
    """Provide a BinanceAdapter with a mocked client."""
    adapter_instance = BinanceAdapter()
    adapter_instance._client = MagicMock(spec=Client)
    return adapter_instance


def test_ping(adapter):
    """Test ping returns formatted status."""
    adapter._client.ping.return_value = {}
    adapter._client.get_server_time.return_value = {"serverTime": 1234567890}

    result = adapter.ping()

    assert result == {
        "status": "connected",
        "server_time": 1234567890,
        "network": "testnet"
    }


def test_get_account_balance(adapter):
    """Test get_account_balance filters out zero balances and calculates total."""
    adapter._client.get_account.return_value = {
        "balances": [
            {"asset": "BTC", "free": "0.1", "locked": "0.05"},
            {"asset": "USDT", "free": "100.0", "locked": "0.0"},
            {"asset": "ETH", "free": "0.0", "locked": "0.0"},  # Should be filtered
        ]
    }

    balances = adapter.get_account_balance()

    assert len(balances) == 2
    assert balances["BTC"]["free"] == 0.1
    assert balances["BTC"]["locked"] == 0.05
    assert balances["BTC"]["total"] == pytest.approx(0.15)

    assert balances["USDT"]["free"] == 100.0
    assert balances["USDT"]["locked"] == 0.0
    assert balances["USDT"]["total"] == pytest.approx(100.0)


def test_get_open_orders_no_symbol(adapter):
    """Test get_open_orders without symbol."""
    mock_orders = [{"orderId": 1}, {"orderId": 2}]
    adapter._client.get_open_orders.return_value = mock_orders

    orders = adapter.get_open_orders()

    adapter._client.get_open_orders.assert_called_once_with()
    assert orders == mock_orders


def test_get_open_orders_with_symbol(adapter):
    """Test get_open_orders with symbol."""
    mock_orders = [{"orderId": 1}]
    adapter._client.get_open_orders.return_value = mock_orders

    orders = adapter.get_open_orders(symbol="BTCUSDT")

    adapter._client.get_open_orders.assert_called_once_with(symbol="BTCUSDT")
    assert orders == mock_orders


def test_get_latest_price(adapter):
    """Test get_latest_price returns a float price."""
    adapter._client.get_symbol_ticker.return_value = {"symbol": "BTCUSDT", "price": "50000.5"}

    price = adapter.get_latest_price("BTCUSDT")

    adapter._client.get_symbol_ticker.assert_called_once_with(symbol="BTCUSDT")
    assert price == 50000.5


def test_get_positions(adapter):
    """Test get_positions maps get_account_balance to positions."""
    adapter._client.get_account.return_value = {
        "balances": [
            {"asset": "BTC", "free": "0.1", "locked": "0.05"},
            {"asset": "USDT", "free": "100.0", "locked": "0.0"},
            {"asset": "ETH", "free": "0.0", "locked": "0.0"},  # Should be filtered by balance
            {"asset": "BNB", "free": "0.0", "locked": "10.0"}, # Should be filtered by positions free > 0
        ]
    }

    positions = adapter.get_positions()

    assert len(positions) == 2

    assert positions[0]["asset"] == "BTC"
    assert positions[0]["free"] == 0.1
    assert positions[0]["locked"] == 0.05
    assert positions[0]["total"] == pytest.approx(0.15)

    assert positions[1]["asset"] == "USDT"
    assert positions[1]["free"] == 100.0
    assert positions[1]["locked"] == 0.0
    assert positions[1]["total"] == pytest.approx(100.0)


def test_get_historical_candles(adapter):
    """Test get_historical_candles maps list of lists to dicts."""
    adapter._client.get_klines.return_value = [
        [
            1499040000000,      # Open time
            "0.01634790",       # Open
            "0.80000000",       # High
            "0.01575800",       # Low
            "0.01577100",       # Close
            "148976.11427815",  # Volume
            1499644799999,      # Close time
            "2434.19055334",    # Quote asset volume
            308,                # Number of trades
            "1756.87402397",    # Taker buy base asset volume
            "28.46694368",      # Taker buy quote asset volume
            "17928899.62484339" # Ignore.
        ]
    ]

    candles = adapter.get_historical_candles("BTCUSDT", interval="1d", limit=1)

    adapter._client.get_klines.assert_called_once_with(symbol="BTCUSDT", interval="1d", limit=1)
    assert len(candles) == 1
    assert candles[0] == {
        "open_time": 1499040000000,
        "open": 0.0163479,
        "high": 0.8,
        "low": 0.015758,
        "close": 0.015771,
        "volume": 148976.11427815,
        "close_time": 1499644799999,
        "quote_volume": 2434.19055334,
        "trades": 308,
    }


def test_get_order_book(adapter):
    """Test get_order_book calls client correctly."""
    mock_depth = {"bids": [["50000.0", "1.0"]], "asks": [["50010.0", "0.5"]]}
    adapter._client.get_order_book.return_value = mock_depth

    depth = adapter.get_order_book("BTCUSDT", limit=10)

    adapter._client.get_order_book.assert_called_once_with(symbol="BTCUSDT", limit=10)
    assert depth == mock_depth


def test_place_market_buy(adapter):
    """Test place_market_buy calls correct client method."""
    mock_order = {"orderId": "12345", "status": "FILLED"}
    adapter._client.order_market_buy.return_value = mock_order

    result = adapter.place_market_buy("BTCUSDT", 0.5)

    adapter._client.order_market_buy.assert_called_once_with(symbol="BTCUSDT", quantity=0.5)
    assert result == mock_order


def test_place_market_sell(adapter):
    """Test place_market_sell calls correct client method."""
    mock_order = {"orderId": "67890", "status": "FILLED"}
    adapter._client.order_market_sell.return_value = mock_order

    result = adapter.place_market_sell("BTCUSDT", 0.5)

    adapter._client.order_market_sell.assert_called_once_with(symbol="BTCUSDT", quantity=0.5)
    assert result == mock_order


def test_cancel_order_with_symbol(adapter):
    """Test cancel_order with symbol calls client correctly."""
    mock_result = {"status": "CANCELED"}
    adapter._client.cancel_order.return_value = mock_result

    result = adapter.cancel_order("12345", symbol="BTCUSDT")

    adapter._client.cancel_order.assert_called_once_with(symbol="BTCUSDT", orderId="12345")
    assert result == mock_result


def test_cancel_order_without_symbol(adapter):
    """Test cancel_order returns error when symbol is omitted."""
    result = adapter.cancel_order("12345")

    assert result == {"error": "symbol is required for cancel_order"}
    adapter._client.cancel_order.assert_not_called()
