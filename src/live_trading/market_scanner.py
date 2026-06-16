"""Market scanner: pulls latest candles and prices from Binance Testnet."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import pandas as pd

from src.exchanges.binance_adapter import BinanceAdapter
from src.exchanges.binance_market_data import BinanceMarketData

logger = logging.getLogger("live_trading.market_scanner")

# Default universe for live scanning
DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]


@dataclass
class MarketSnapshot:
    """Snapshot of market data for a symbol."""
    symbol: str
    price: float
    candles: pd.DataFrame
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    is_valid: bool = True

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "price": self.price,
            "candle_count": len(self.candles),
            "timestamp": self.timestamp,
            "is_valid": self.is_valid,
        }


class MarketScanner:
    """Pulls latest candles and prices from Binance Testnet.

    Responsibilities:
    - Pull latest candles for each symbol
    - Pull latest prices
    - Validate symbols
    - Return market snapshot
    """

    def __init__(
        self,
        adapter: BinanceAdapter,
        market: BinanceMarketData,
        symbols: Optional[list[str]] = None,
        candle_interval: str = "1h",
        candle_limit: int = 100,
    ) -> None:
        self.adapter = adapter
        self.market = market
        self.symbols = symbols or DEFAULT_SYMBOLS
        self.candle_interval = candle_interval
        self.candle_limit = candle_limit

    def scan(self) -> dict[str, MarketSnapshot]:
        """Scan all symbols and return market snapshots.

        Returns:
            {symbol: MarketSnapshot}
        """
        snapshots: dict[str, MarketSnapshot] = {}
        for symbol in self.symbols:
            try:
                snapshot = self._scan_symbol(symbol)
                snapshots[symbol] = snapshot
                logger.info("Scanned %s: price=%.2f, candles=%d", symbol, snapshot.price, len(snapshot.candles))
            except Exception as e:
                logger.error("Failed to scan %s: %s", symbol, e)
                snapshots[symbol] = MarketSnapshot(
                    symbol=symbol,
                    price=0.0,
                    candles=pd.DataFrame(),
                    is_valid=False,
                )
        return snapshots

    def _scan_symbol(self, symbol: str) -> MarketSnapshot:
        """Scan a single symbol."""
        # Validate symbol
        if not self.market.validate_symbol(symbol):
            logger.warning("Symbol %s is not valid or not trading", symbol)
            return MarketSnapshot(
                symbol=symbol,
                price=0.0,
                candles=pd.DataFrame(),
                is_valid=False,
            )

        # Get latest price
        price_data = self.market.get_ticker_price(symbol)
        price = price_data["price"]

        # Get historical candles
        candles = self.market.get_klines(
            symbol=symbol,
            interval=self.candle_interval,
            limit=self.candle_limit,
        )

        return MarketSnapshot(
            symbol=symbol,
            price=price,
            candles=candles,
            is_valid=True,
        )

    def get_snapshot(self, symbol: str) -> MarketSnapshot:
        """Get snapshot for a single symbol."""
        return self._scan_symbol(symbol)