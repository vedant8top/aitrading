"""Pluggable risk management framework for portfolio backtesting."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable


class RiskMode(Enum):
    """Risk management mode for backtesting."""

    NONE = auto()
    BASIC = auto()
    ADVANCED = auto()


@dataclass(frozen=True)
class RiskControls:
    """Configurable risk limits and constraints."""

    max_risk_per_trade_pct: float = 1.0
    max_portfolio_exposure_pct: float = 80.0
    max_concurrent_positions: int = 25
    daily_loss_limit_pct: float = 3.0
    portfolio_drawdown_limit_pct: float = 25.0
    position_size_pct: float = 10.0
    atr_stop_multiplier: float = 3.0
    percentage_stop_pct: float = 7.0
    time_stop_days: int = 90
    atr_position_size_risk_pct: float = 1.0
    atr_position_size_multiplier: float = 2.0


class PositionSizer:
    """Base position sizing interface."""

    def compute_shares(
        self,
        cash: float,
        price: float,
        brokerage_rate: float,
        atr: float | None = None,
        controls: RiskControls = RiskControls(),
    ) -> int:
        """Return whole number of shares to buy."""
        raise NotImplementedError


class FixedFractionalSizer(PositionSizer):
    """Size positions as a fixed fraction of available cash."""

    def compute_shares(
        self,
        cash: float,
        price: float,
        brokerage_rate: float,
        atr: float | None = None,
        controls: RiskControls = RiskControls(),
    ) -> int:
        allocation = cash * (controls.position_size_pct / 100.0)
        entry_price = price * (1.0 + 0.0005)  # slippage already applied caller-side
        shares = math.floor(allocation / (entry_price * (1.0 + brokerage_rate)))
        return max(shares, 0)


class ATRBasedSizer(PositionSizer):
    """Size positions based on ATR to risk a fixed percentage of capital."""

    def compute_shares(
        self,
        cash: float,
        price: float,
        brokerage_rate: float,
        atr: float | None = None,
        controls: RiskControls = RiskControls(),
    ) -> int:
        if atr is None or atr <= 0:
            return FixedFractionalSizer().compute_shares(cash, price, brokerage_rate, atr, controls)
        risk_per_share = atr * controls.atr_position_size_multiplier
        if risk_per_share <= 0:
            return 0
        risk_capital = cash * (controls.atr_position_size_risk_pct / 100.0)
        shares = math.floor(risk_capital / risk_per_share)
        return max(shares, 0)


class VolatilityAdjustedSizer(PositionSizer):
    """Size inversely proportional to 20-day rolling volatility."""

    def compute_shares(
        self,
        cash: float,
        price: float,
        brokerage_rate: float,
        atr: float | None = None,
        controls: RiskControls = RiskControls(),
    ) -> int:
        base_sizer = FixedFractionalSizer()
        base_shares = base_sizer.compute_shares(cash, price, brokerage_rate, atr, controls)
        if atr is None or atr <= 0 or price <= 0:
            return base_shares
        vol_pct = atr / price * 100.0
        if vol_pct <= 0:
            return base_shares
        # Scale: higher volatility → smaller position
        target_vol = 2.0  # target daily volatility 2%
        scale = target_vol / vol_pct
        scale = max(0.25, min(scale, 2.0))  # clamp between 25% and 200%
        adjusted = int(round(base_shares * scale))
        return max(adjusted, 0)


class StopLoss:
    """Base stop loss interface."""

    def should_exit(
        self,
        entry_price: float,
        current_price: float,
        entry_date: object,
        current_date: object,
        holding_days: int,
        atr: float | None = None,
        controls: RiskControls = RiskControls(),
    ) -> bool:
        """Return True if the position should be closed."""
        raise NotImplementedError


class PercentageStop(StopLoss):
    """Exit when price falls below a fixed percentage of entry."""

    def should_exit(
        self,
        entry_price: float,
        current_price: float,
        entry_date: object,
        current_date: object,
        holding_days: int,
        atr: float | None = None,
        controls: RiskControls = RiskControls(),
    ) -> bool:
        if entry_price <= 0:
            return False
        pct_drop = (entry_price - current_price) / entry_price * 100.0
        return pct_drop >= controls.percentage_stop_pct


class ATRStop(StopLoss):
    """Exit when price moves more than N × ATR against the entry."""

    def should_exit(
        self,
        entry_price: float,
        current_price: float,
        entry_date: object,
        current_date: object,
        holding_days: int,
        atr: float | None = None,
        controls: RiskControls = RiskControls(),
    ) -> bool:
        if entry_price <= 0 or atr is None or atr <= 0:
            return False
        drop = entry_price - current_price
        return drop >= atr * controls.atr_stop_multiplier


class TimeStop(StopLoss):
    """Exit after a fixed number of holding days regardless of price."""

    def should_exit(
        self,
        entry_price: float,
        current_price: float,
        entry_date: object,
        current_date: object,
        holding_days: int,
        atr: float | None = None,
        controls: RiskControls = RiskControls(),
    ) -> bool:
        return holding_days >= controls.time_stop_days


class RiskManager:
    """Orchestrates position sizing, risk controls, and stop losses."""

    def __init__(
        self,
        mode: RiskMode = RiskMode.NONE,
        controls: RiskControls = RiskControls(),
    ) -> None:
        self.mode = mode
        self.controls = controls
        self._sizer: PositionSizer
        self._stops: list[StopLoss]
        self._daily_start_equity: float | None = None
        self._peak_equity: float = 0.0
        self._current_day_pnl: float = 0.0

        if mode == RiskMode.NONE:
            self._sizer = FixedFractionalSizer()
            self._stops = []
        elif mode == RiskMode.BASIC:
            self._sizer = FixedFractionalSizer()
            self._stops = [PercentageStop(), TimeStop()]
        elif mode == RiskMode.ADVANCED:
            self._sizer = VolatilityAdjustedSizer()
            self._stops = [ATRStop(), TimeStop()]
        else:
            self._sizer = FixedFractionalSizer()
            self._stops = []

    @property
    def sizer(self) -> PositionSizer:
        return self._sizer

    @property
    def stops(self) -> list[StopLoss]:
        return self._stops

    @property
    def max_concurrent_positions(self) -> int:
        if self.mode == RiskMode.NONE:
            return 9999  # unlimited in NONE mode
        return self.controls.max_concurrent_positions

    @property
    def max_portfolio_exposure_pct(self) -> float:
        if self.mode == RiskMode.NONE:
            return 100.0  # unlimited
        return self.controls.max_portfolio_exposure_pct

    def compute_position_size(
        self,
        cash: float,
        price: float,
        brokerage_rate: float,
        atr: float | None = None,
    ) -> int:
        """Return number of shares to buy based on the configured sizer."""
        return self._sizer.compute_shares(cash, price, brokerage_rate, atr, self.controls)

    def check_stop_exits(
        self,
        positions: dict,
        current_date: object,
        last_close: dict[str, float],
        atr_lookup: dict[str, float],
        entry_dates: dict[str, object],
        entry_prices: dict[str, float],
    ) -> list[tuple[str, object, float]]:
        """Return list of (ticker, signal_date, exit_price) that should be stopped out."""
        if self.mode == RiskMode.NONE or not self._stops:
            return []

        exits: list[tuple[str, object, float]] = []
        for ticker in list(positions.keys()):
            for stop in self._stops:
                current_price = last_close.get(ticker)
                if current_price is None or current_price <= 0:
                    continue
                entry_price = entry_prices.get(ticker, current_price)
                entry_date = entry_dates.get(ticker, current_date)
                holding_days = 0
                if hasattr(current_date, "__sub__") and hasattr(entry_date, "__sub__"):
                    try:
                        holding_days = (current_date - entry_date).days
                    except (TypeError, AttributeError):
                        holding_days = 0
                atr = atr_lookup.get(ticker)

                if stop.should_exit(
                    entry_price=entry_price,
                    current_price=current_price,
                    entry_date=entry_date,
                    current_date=current_date,
                    holding_days=holding_days,
                    atr=atr,
                    controls=self.controls,
                ):
                    # Use last close as exit price (simulated)
                    exit_price = current_price * (1.0 - 0.0005)  # same slippage as SELL
                    exits.append((ticker, current_date, exit_price))
                    break  # one stop per position per day
        return exits

    def check_daily_loss_limit(self, daily_return_pct: float) -> bool:
        """Return True if daily loss limit is breached (ADVANCED only)."""
        if self.mode != RiskMode.ADVANCED:
            return False
        return daily_return_pct <= -self.controls.daily_loss_limit_pct

    def check_drawdown_limit(self, current_equity: float) -> bool:
        """Return True if portfolio drawdown limit is breached (ADVANCED only)."""
        if self.mode != RiskMode.ADVANCED:
            return False
        if current_equity > self._peak_equity:
            self._peak_equity = current_equity
        if self._peak_equity <= 0:
            return False
        dd_pct = (self._peak_equity - current_equity) / self._peak_equity * 100.0
        return dd_pct >= self.controls.portfolio_drawdown_limit_pct

    def get_max_position_value(
        self,
        cash: float,
        current_exposure: float,
    ) -> float:
        """Return maximum capital deployable for a new position."""
        if self.mode == RiskMode.NONE:
            return cash  # no limit
        total_equity = cash + current_exposure
        max_total_exposure = total_equity * (self.max_portfolio_exposure_pct / 100.0)
        remaining = max_total_exposure - current_exposure
        return max(remaining, 0.0)


def build_risk_manager(mode_name: str) -> RiskManager:
    """Build a RiskManager from a string mode name."""
    mode_map = {
        "none": RiskMode.NONE,
        "basic": RiskMode.BASIC,
        "advanced": RiskMode.ADVANCED,
    }
    mode = mode_map.get(mode_name.lower().strip(), RiskMode.NONE)
    return RiskManager(mode=mode)