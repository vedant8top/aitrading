"""Binance Spot Testnet adapter implementing ExchangeInterface."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceRequestException

from src.exchanges.exchange_interface import ExchangeInterface

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENV_PATH = PROJECT_ROOT / ".env"


class BinanceAdapterError(RuntimeError):
    """Base exception for Binance adapter failures."""


class BinanceAdapter(ExchangeInterface):
    """Binance Spot Testnet adapter.

    Loads credentials from .env and connects to Binance Spot Testnet.
    Implements all ExchangeInterface methods.
    """

    def __init__(
        self,
        env_path: Path | str = DEFAULT_ENV_PATH,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.logger = logger or self._configure_logging()
        self._api_key, self._secret_key, self._testnet = self._load_credentials(env_path)
        self._client: Optional[Client] = None

    def _configure_logging(self) -> logging.Logger:
        logger = logging.getLogger("binance_adapter")
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter(
                "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
            ))
            logger.addHandler(handler)
        return logger

    def _load_credentials(self, env_path: Path | str) -> tuple[str, str, bool]:
        """Load API credentials from .env file."""
        env_path = Path(env_path).resolve()
        if not env_path.exists():
            raise BinanceAdapterError(f".env not found at {env_path}")

        load_dotenv(env_path)

        api_key = os.getenv("BINANCE_API_KEY", "").strip()
        secret_key = os.getenv("BINANCE_SECRET_KEY", "").strip()
        testnet = os.getenv("BINANCE_TESTNET", "true").lower() == "true"

        if not api_key or not secret_key:
            raise BinanceAdapterError(
                "BINANCE_API_KEY and BINANCE_SECRET_KEY must be set in .env"
            )

        if api_key == "PASTE_YOUR_API_KEY_HERE":
            raise BinanceAdapterError(
                "Placeholder BINANCE_API_KEY detected. Replace with real credentials."
            )

        return api_key, secret_key, testnet

    @property
    def client(self) -> Client:
        """Lazy-initialized Binance client."""
        if self._client is None:
            self._client = Client(self._api_key, self._secret_key, testnet=self._testnet)
        return self._client

    def _handle_exception(self, e: Exception, context: str) -> None:
        """Log and wrap exchange exceptions."""
        if isinstance(e, BinanceAPIException):
            self.logger.error("Binance API error in %s: %s (code=%s)", context, e.message, e.status_code)
            raise BinanceAdapterError(f"Binance API error in {context}: {e.message}") from e
        elif isinstance(e, BinanceRequestException):
            self.logger.error("Binance request error in %s: %s", context, e)
            raise BinanceAdapterError(f"Binance request error in {context}: {e}") from e
        else:
            self.logger.error("Unexpected error in %s: %s", context, e)
            raise BinanceAdapterError(f"Unexpected error in {context}: {e}") from e

    # ------------------------------------------------------------------
    # ExchangeInterface Implementation
    # ------------------------------------------------------------------

    def ping(self) -> dict:
        """Test connectivity. Returns server time."""
        try:
            result = self.client.ping()
            server_time = self.client.get_server_time()
            self.logger.info("Ping successful. Server time: %s", server_time.get("serverTime"))
            return {
                "status": "connected",
                "server_time": server_time.get("serverTime"),
                "network": "testnet" if self._testnet else "live",
            }
        except Exception as e:
            return self._handle_exception(e, "ping")

    def get_account_balance(self) -> dict[str, dict]:
        """Return all non-zero balances."""
        try:
            account = self.client.get_account()
            balances: dict[str, dict] = {}
            for b in account.get("balances", []):
                free = float(b["free"])
                locked = float(b["locked"])
                total = free + locked
                if total > 0:
                    balances[b["asset"]] = {
                        "free": free,
                        "locked": locked,
                        "total": round(total, 8),
                    }
            self.logger.info("Account balance retrieved: %d assets", len(balances))
            return balances
        except Exception as e:
            return self._handle_exception(e, "get_account_balance")

    def get_open_orders(self, symbol: Optional[str] = None) -> list[dict]:
        """Return open orders."""
        try:
            if symbol:
                orders = self.client.get_open_orders(symbol=symbol)
            else:
                orders = self.client.get_open_orders()
            self.logger.info("Open orders: %d", len(orders))
            return orders
        except Exception as e:
            return self._handle_exception(e, "get_open_orders")

    def get_positions(self) -> list[dict]:
        """Return positions (spot = non-zero balances with free > 0)."""
        try:
            balances = self.get_account_balance()
            positions = [
                {"asset": asset, "free": data["free"], "locked": data["locked"], "total": data["total"]}
                for asset, data in balances.items()
                if data["free"] > 0
            ]
            return positions
        except Exception as e:
            return self._handle_exception(e, "get_positions")

    def get_latest_price(self, symbol: str) -> float:
        """Get latest price for a trading pair."""
        try:
            ticker = self.client.get_symbol_ticker(symbol=symbol)
            price = float(ticker["price"])
            self.logger.info("Latest price %s: %.8f", symbol, price)
            return price
        except Exception as e:
            return self._handle_exception(e, f"get_latest_price({symbol})")

    def get_historical_candles(
        self, symbol: str, interval: str = "1d", limit: int = 100
    ) -> list[dict]:
        """Get historical OHLCV candles."""
        try:
            klines = self.client.get_klines(symbol=symbol, interval=interval, limit=limit)
            candles = []
            for k in klines:
                candles.append({
                    "open_time": int(k[0]),
                    "open": float(k[1]),
                    "high": float(k[2]),
                    "low": float(k[3]),
                    "close": float(k[4]),
                    "volume": float(k[5]),
                    "close_time": int(k[6]),
                    "quote_volume": float(k[7]),
                    "trades": int(k[8]),
                })
            self.logger.info("Historical candles retrieved: %s, interval=%s, count=%d", symbol, interval, len(candles))
            return candles
        except Exception as e:
            return self._handle_exception(e, f"get_historical_candles({symbol})")

    def place_market_buy(self, symbol: str, quantity: float) -> dict:
        """Place a market buy order."""
        try:
            self.logger.warning("PLACING MARKET BUY ORDER: %s %s (TESTNET)", symbol, quantity)
            order = self.client.order_market_buy(symbol=symbol, quantity=quantity)
            self.logger.info("Market buy executed: %s", order.get("orderId"))
            return order
        except Exception as e:
            return self._handle_exception(e, f"place_market_buy({symbol})")

    def place_market_sell(self, symbol: str, quantity: float) -> dict:
        """Place a market sell order."""
        try:
            self.logger.warning("PLACING MARKET SELL ORDER: %s %s (TESTNET)", symbol, quantity)
            order = self.client.order_market_sell(symbol=symbol, quantity=quantity)
            self.logger.info("Market sell executed: %s", order.get("orderId"))
            return order
        except Exception as e:
            return self._handle_exception(e, f"place_market_sell({symbol})")

    def cancel_order(self, order_id: str, symbol: Optional[str] = None) -> dict:
        """Cancel an open order."""
        try:
            if symbol:
                result = self.client.cancel_order(symbol=symbol, orderId=order_id)
            else:
                result = {"error": "symbol is required for cancel_order"}
            self.logger.info("Order cancelled: %s", order_id)
            return result
        except Exception as e:
            return self._handle_exception(e, f"cancel_order({order_id})")

    def get_order_book(self, symbol: str, limit: int = 100) -> dict:
        """Get order book depth."""
        try:
            depth = self.client.get_order_book(symbol=symbol, limit=limit)
            self.logger.info("Order book retrieved: %s, bids=%d, asks=%d", symbol, len(depth["bids"]), len(depth["asks"]))
            return depth
        except Exception as e:
            return self._handle_exception(e, f"get_order_book({symbol})")