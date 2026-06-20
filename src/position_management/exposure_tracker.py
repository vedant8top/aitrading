"""Exposure tracker: tracks exposure per symbol and concentration risk."""

from __future__ import annotations

import logging
from typing import Optional

from src.position_management.position_manager import PositionManager

logger = logging.getLogger("position_management.exposure")


class ExposureTracker:
    """Tracks exposure by symbol and concentration risk.

    - Exposure by symbol (absolute USDT and percentage)
    - Total exposure (sum of all position values)
    - Concentration risk (max single-symbol exposure as % of total)
    """

    def __init__(self, position_manager: PositionManager) -> None:
        self.pm = position_manager

    def get_symbol_exposure(self, symbol: str) -> float:
        """Get current exposure for a symbol in USDT."""
        pos = self.pm.get_position(symbol)
        if not pos:
            return 0.0
        price = pos.get("current_price") or pos.get("avg_entry_price", 0)
        return pos["quantity"] * price

    def get_total_exposure(self) -> float:
        """Get total portfolio exposure in USDT."""
        return sum(
            p["quantity"] * (p.get("current_price") or p.get("avg_entry_price", 0))
            for p in self.pm.get_open_positions()
        )

    def get_symbol_exposure_pct(self, symbol: str) -> float:
        """Get symbol exposure as percentage of total exposure."""
        total = self.get_total_exposure()
        if total <= 0:
            return 0.0
        return self.get_symbol_exposure(symbol) / total * 100

    def get_concentration_risk(self) -> dict:
        """Calculate concentration risk metrics."""
        positions = self.pm.get_open_positions()
        if not positions:
            return {"max_symbol_pct": 0.0, "max_symbol": "", "herfindahl_index": 0.0, "diversification_ratio": 1.0}

        total = self.get_total_exposure()
        if total <= 0:
            return {"max_symbol_pct": 0.0, "max_symbol": "", "herfindahl_index": 0.0, "diversification_ratio": 1.0}

        symbols = [p["symbol"] for p in positions]
        exposures = {p["symbol"]: p["quantity"] * (p.get("current_price") or p.get("avg_entry_price", 0))
                     for p in positions}

        max_symbol = max(exposures, key=exposures.get)
        max_symbol_pct = exposures[max_symbol] / total * 100

        # Herfindahl-Hirschman Index (HHI)
        hhi = sum((exposures[s] / total) ** 2 for s in symbols)

        # Diversification ratio: 1.0 = perfectly diversified, 0.0 = all in one stock
        n = len(symbols)
        diversification_ratio = 1.0 - hhi if n > 1 else 0.0

        return {
            "max_symbol_pct": round(max_symbol_pct, 2),
            "max_symbol": max_symbol,
            "herfindahl_index": round(hhi, 4),
            "diversification_ratio": round(diversification_ratio, 4),
            "num_positions": n,
        }

    def check_symbol_limit(self, symbol: str, pct_limit: float = 40.0) -> bool:
        """Check if adding a new position would exceed symbol % limit."""
        current_pct = self.get_symbol_exposure_pct(symbol)
        return current_pct < pct_limit