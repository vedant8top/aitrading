"""Abstract base class for exchange integrations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional


class ExchangeInterface(ABC):
    """Abstract interface for crypto exchange connectivity.

    All exchange adapters must implement these methods.
    """

    @abstractmethod
    def ping(self) -> dict:
        """Test exchange connectivity.

        Returns:
            Dict with server time or connection status.
        """
        ...

    @abstractmethod
    def get_account_balance(self) -> dict[str, dict]:
        """Return all non-zero balances.

        Returns:
            {asset: {"free": float, "locked": float, "total": float}}
        """
        ...

    @abstractmethod
    def get_open_orders(self, symbol: Optional[str] = None) -> list[dict]:
        """Return list of open orders.

        Args:
            symbol: Optional trading pair (e.g. "BTCUSDT").
                   If None, return orders for all symbols.

        Returns:
            List of order dicts.
        """
        ...

    @abstractmethod
    def get_positions(self) -> list[dict]:
        """Return current positions.

        For spot trading, this is the same as non-zero balances.
        For futures, return active position details.

        Returns:
            List of position dicts.
        """
        ...

    @abstractmethod
    def get_latest_price(self, symbol: str) -> float:
        """Get latest price for a trading pair.

        Args:
            symbol: Trading pair (e.g. "BTCUSDT").

        Returns:
            Current price as float.
        """
        ...

    @abstractmethod
    def get_historical_candles(
        self, symbol: str, interval: str = "1d", limit: int = 100
    ) -> list[dict]:
        """Get historical OHLCV candles.

        Args:
            symbol: Trading pair (e.g. "BTCUSDT").
            interval: Candle interval (1m, 5m, 1h, 1d, etc.).
            limit: Number of candles to return.

        Returns:
            List of candle dicts with keys:
            open_time, open, high, low, close, volume, close_time.
        """
        ...

    @abstractmethod
    def place_market_buy(self, symbol: str, quantity: float) -> dict:
        """Place a market buy order.

        Args:
            symbol: Trading pair.
            quantity: Quantity to buy in base asset units.

        Returns:
            Order execution result dict.
        """
        ...

    @abstractmethod
    def place_market_sell(self, symbol: str, quantity: float) -> dict:
        """Place a market sell order.

        Args:
            symbol: Trading pair.
            quantity: Quantity to sell in base asset units.

        Returns:
            Order execution result dict.
        """
        ...

    @abstractmethod
    def cancel_order(self, order_id: str, symbol: Optional[str] = None) -> dict:
        """Cancel an open order.

        Args:
            order_id: Exchange order ID.
            symbol: Optional trading pair.

        Returns:
            Cancellation result dict.
        """
        ...

    @abstractmethod
    def get_order_book(self, symbol: str, limit: int = 100) -> dict:
        """Get order book depth.

        Args:
            symbol: Trading pair.
            limit: Depth level.

        Returns:
            Dict with "bids" and "asks" lists.
        """
        ...