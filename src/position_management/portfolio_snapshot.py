"""Portfolio snapshot: generates portfolio state summary."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from src.position_management.position_manager import PositionManager

logger = logging.getLogger("position_management.snapshot")


class PortfolioSnapshot:
    """Generates portfolio state summary from PositionManager data."""

    def __init__(self, position_manager: PositionManager, initial_capital: float = 1000.0) -> None:
        self.pm = position_manager
        self.initial_capital = initial_capital

    def generate(self) -> dict:
        """Generate current portfolio snapshot."""
        open_positions = self.pm.get_open_positions()
        unrealized = self.pm.total_unrealized_pnl()
        realized = self.pm.total_realized_pnl()
        num_positions = len(open_positions)
        total_exposure = sum(p["quantity"] * (p.get("current_price") or p["avg_entry_price"]) for p in open_positions)
        cash = self.initial_capital + realized - total_exposure
        total_equity = cash + total_exposure + unrealized
        daily_pnl = self.pm.daily_realized_pnl()

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "initial_capital": self.initial_capital,
            "total_equity": round(total_equity, 2),
            "cash": round(cash, 2),
            "total_exposure": round(total_exposure, 2),
            "exposure_pct": round((total_exposure / total_equity * 100) if total_equity > 0 else 0, 2),
            "num_open_positions": num_positions,
            "unrealized_pnl": round(unrealized, 2),
            "realized_pnl": round(realized, 2),
            "daily_realized_pnl": round(daily_pnl, 2),
            "total_pnl": round(unrealized + realized, 2),
            "return_pct": round((total_equity - self.initial_capital) / self.initial_capital * 100, 2),
        }