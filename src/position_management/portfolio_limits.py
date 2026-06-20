"""Portfolio limits: configurable risk limits for the position manager."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PortfolioLimits:
    """Configurable risk limits for the position manager.

    Defaults can be overridden per instance.
    """

    max_open_positions: int = 3
    max_position_value_usdt: float = 100.0
    max_total_exposure_usdt: float = 300.0
    max_daily_loss_pct: float = 2.0
    max_symbol_exposure_pct: float = 40.0
    max_leverage: float = 1.0
    min_order_value_usdt: float = 10.0
    daily_loss_limit_usdt: float = 50.0

    def to_dict(self) -> dict:
        return {
            "max_open_positions": self.max_open_positions,
            "max_position_value_usdt": self.max_position_value_usdt,
            "max_total_exposure_usdt": self.max_total_exposure_usdt,
            "max_daily_loss_pct": self.max_daily_loss_pct,
            "max_symbol_exposure_pct": self.max_symbol_exposure_pct,
            "max_leverage": self.max_leverage,
            "min_order_value_usdt": self.min_order_value_usdt,
            "daily_loss_limit_usdt": self.daily_loss_limit_usdt,
        }