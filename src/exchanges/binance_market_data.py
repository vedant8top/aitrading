"""Binance market data subsystem for TradingAI."""

from __future__ import annotations

import logging
from typing import Any, Optional

import pandas as pd

from src.exchanges.binance_adapter import BinanceAdapter

logger = logging.getLogger("binance_market_data")


class BinanceMarketData:
    """Market data utilities for Binance Spot Testnet.

    Provides methods for fetching ticker prices, klines,
    top symbols, and symbol validation.
    """

    def __init__(self, adapter: BinanceAdapter) -> None:
        self.adapter = adapter

    @property
    def client(self):
        """Access the underlying Binance client."""
        return self.adapter.client

    def get_ticker_price(self, symbol: str) -> dict:
        """Get current ticker price for a symbol.

        Args:
            symbol: Trading pair (e.g. "BTCUSDT").

        Returns:
            {"symbol": str, "price": float}
        """
        try:
            ticker = self.client.get_symbol_ticker(symbol=symbol)
            return {"symbol": ticker["symbol"], "price": float(ticker["price"])}
        except Exception as e:
            logger.error("Failed to get ticker price for %s: %s", symbol, e)
            raise

    def get_klines(
        self,
        symbol: str,
        interval: str = "1d",
        limit: int = 100,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> pd.DataFrame:
        """Get historical klines as a DataFrame.

        Args:
            symbol: Trading pair (e.g. "BTCUSDT").
            interval: Candle interval (1m, 5m, 1h, 1d, etc.).
            limit: Number of candles.
            start_time: Optional start time in milliseconds.
            end_time: Optional end time in milliseconds.

        Returns:
            DataFrame with columns:
            open_time, open, high, low, close, volume, close_time,
            quote_volume, trades, taker_buy_base, taker_buy_quote, ignore.
        """
        try:
            kwargs: dict[str, Any] = {"symbol": symbol, "interval": interval, "limit": limit}
            if start_time is not None:
                kwargs["start_time"] = start_time
            if end_time is not None:
                kwargs["end_time"] = end_time

            klines = self.client.get_klines(**kwargs)

            df = pd.DataFrame(klines, columns=[
                "open_time", "open", "high", "low", "close", "volume",
                "close_time", "quote_volume", "trades",
                "taker_buy_base", "taker_buy_quote", "ignore",
            ])

            # Convert numeric columns
            numeric_cols = ["open", "high", "low", "close", "volume", "quote_volume"]
            for col in numeric_cols:
                df[col] = pd.to_numeric(df[col], errors="coerce")

            df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
            df["close_time"] = pd.to_datetime(df["close_time"], unit="ms")
            df["trades"] = df["trades"].astype(int)

            logger.info("Klines retrieved: %s, interval=%s, count=%d", symbol, interval, len(df))
            return df

        except Exception as e:
            logger.error("Failed to get klines for %s: %s", symbol, e)
            raise

    def get_top_symbols(self, quote: str = "USDT", top: int = 20) -> list[dict]:
        """Get top symbols by 24hr quote volume.

        Args:
            quote: Quote currency (e.g. "USDT").
            top: Number of top symbols to return.

        Returns:
            List of dicts with keys: symbol, price, quote_volume, change_pct.
        """
        try:
            tickers = self.client.get_ticker()
            usdt_tickers = [t for t in tickers if t["symbol"].endswith(quote)]

            # Sort by quote volume
            usdt_tickers.sort(key=lambda x: float(x.get("quoteVolume", 0)), reverse=True)

            top_symbols = []
            for t in usdt_tickers[:top]:
                top_symbols.append({
                    "symbol": t["symbol"],
                    "price": float(t["lastPrice"]),
                    "quote_volume": float(t["quoteVolume"]),
                    "change_pct": float(t["priceChangePercent"]),
                })

            logger.info("Top %d %s symbols retrieved", top, quote)
            return top_symbols

        except Exception as e:
            logger.error("Failed to get top symbols: %s", e)
            raise

    def validate_symbol(self, symbol: str) -> bool:
        """Check if a symbol exists and is trading.

        Args:
            symbol: Trading pair (e.g. "BTCUSDT").

        Returns:
            True if symbol is valid and trading.
        """
        try:
            info = self.client.get_symbol_info(symbol)
            if info is None:
                logger.warning("Symbol %s not found", symbol)
                return False
            is_trading = info.get("status") == "TRADING"
            logger.info("Symbol %s validation: %s", symbol, "TRADING" if is_trading else "NOT_TRADING")
            return is_trading
        except Exception as e:
            logger.error("Failed to validate symbol %s: %s", symbol, e)
            return False

    def get_24hr_ticker(self, symbol: str) -> dict:
        """Get 24hr ticker statistics.

        Args:
            symbol: Trading pair (e.g. "BTCUSDT").

        Returns:
            Dict with 24hr stats: price, volume, change, etc.
        """
        try:
            ticker = self.client.get_ticker(symbol=symbol)
            return {
                "symbol": ticker["symbol"],
                "price": float(ticker["lastPrice"]),
                "high": float(ticker["highPrice"]),
                "low": float(ticker["lowPrice"]),
                "volume": float(ticker["volume"]),
                "quote_volume": float(ticker["quoteVolume"]),
                "change_pct": float(ticker["priceChangePercent"]),
                "trades": int(ticker["count"]),
            }
        except Exception as e:
            logger.error("Failed to get 24hr ticker for %s: %s", symbol, e)
            raise

    def get_exchange_info(self) -> dict:
        """Get exchange rules and limits.

        Returns:
            Dict with exchange info including symbols, rate limits, etc.
        """
        try:
            info = self.client.get_exchange_info()
            logger.info("Exchange info retrieved: %d symbols", len(info.get("symbols", [])))
            return info
        except Exception as e:
            logger.error("Failed to get exchange info: %s", e)
            raise