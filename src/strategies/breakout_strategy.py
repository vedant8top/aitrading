"""Breakout trading strategy — buys when price breaks above resistance with volume confirmation."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.strategies.base_strategy import BaseStrategy


REQUIRED_INDICATOR_COLUMNS: tuple[str, ...] = (
    "Date",
    "Close",
    "Volume",
    "Volume_MA_20",
    "SMA_20",
)

SIGNAL_COLUMNS: tuple[str, ...] = (
    "Signal_Date",
    "Signal",
    "Signal_Confidence",
    "Conditions_Met",
    "Buy_Conditions_Met",
    "Sell_Conditions_Met",
)


@dataclass(frozen=True)
class BreakoutStrategy(BaseStrategy):
    """Breakout strategy — buys when Close breaks above the 20-day high with volume confirmation.

    BUY requires both conditions:
      - Close is above the highest high of the previous 20 days.
      - Volume is above the 20-day average volume.

    SELL requires:
      - Close is below the lowest low of the previous 10 days (bearish breakdown).

    All other rows are HOLD.
    """

    _name: str = field(default="breakout")
    _description: str = field(
        default=(
            "Breakout Strategy. "
            "BUY when Close > 20-day high AND Volume > Volume_MA20. "
            "SELL when Close < 10-day low."
        )
    )

    @property
    def required_indicator_columns(self) -> tuple[str, ...]:
        return REQUIRED_INDICATOR_COLUMNS

    @property
    def signal_columns(self) -> tuple[str, ...]:
        return SIGNAL_COLUMNS

    def get_strategy_name(self) -> str:
        return self._name

    def get_strategy_description(self) -> str:
        return self._description

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        enriched = data.copy()
        close = enriched["Close"]
        volume = enriched["Volume"]

        # Compute rolling highs and lows
        highest_20 = close.rolling(20, min_periods=20).max().shift(1)
        lowest_10 = close.rolling(10, min_periods=10).min().shift(1)

        indicator_columns = [col for col in REQUIRED_INDICATOR_COLUMNS if col != "Date"]
        indicators_ready = enriched[indicator_columns].notna().all(axis=1)

        buy_conditions = pd.DataFrame(
            {
                "price_breakout": close > highest_20,
                "volume_surge": volume > enriched["Volume_MA_20"],
            },
            index=enriched.index,
        ).fillna(False)

        sell_conditions = pd.DataFrame(
            {
                "price_breakdown": close < lowest_10,
            },
            index=enriched.index,
        ).fillna(False)

        buy_count = buy_conditions.sum(axis=1).astype(int)
        sell_count = sell_conditions.sum(axis=1).astype(int)
        buy_signal = indicators_ready & buy_conditions.all(axis=1)
        sell_signal = indicators_ready & ~buy_signal & sell_conditions.any(axis=1)

        signal = np.select(
            (buy_signal, sell_signal), ("BUY", "SELL"), default="HOLD"
        )
        applicable_count = np.select(
            (buy_signal, sell_signal), (buy_count, sell_count), default=0
        ).astype(int)
        confidence = np.select(
            (applicable_count >= 2, applicable_count == 1),
            ("High", "Medium"),
            default="Low",
        )

        enriched["Signal_Date"] = enriched["Date"]
        enriched["Signal"] = signal
        enriched["Signal_Confidence"] = confidence
        enriched["Conditions_Met"] = applicable_count
        enriched["Buy_Conditions_Met"] = buy_count
        enriched["Sell_Conditions_Met"] = sell_count
        return enriched

    def validate_output(
        self, source: pd.DataFrame, signals: pd.DataFrame
    ) -> list[str]:
        from src.strategies.signal_engine import SignalCalculationError

        if len(source) != len(signals):
            raise SignalCalculationError("Row count changed during signal generation")
        if not source["Date"].equals(signals["Date"]):
            raise SignalCalculationError("Source date alignment changed")
        if not signals["Date"].equals(signals["Signal_Date"]):
            raise SignalCalculationError("Signal dates are not aligned with source dates")

        missing_cols = [col for col in SIGNAL_COLUMNS if col not in signals]
        if missing_cols:
            raise SignalCalculationError(f"Missing signal columns: {', '.join(missing_cols)}")
        if not signals["Signal"].isin(("BUY", "SELL", "HOLD")).all():
            raise SignalCalculationError("Unexpected signal value generated")
        if not signals["Signal_Confidence"].isin(("Low", "Medium", "High")).all():
            raise SignalCalculationError("Unexpected confidence value generated")

        warnings: list[str] = []
        unavailable = signals[
            [col for col in REQUIRED_INDICATOR_COLUMNS if col != "Date"]
        ].isna().any(axis=1)
        warmup_holds = int((unavailable & signals["Signal"].eq("HOLD")).sum())
        if warmup_holds:
            warnings.append(
                f"{warmup_holds} warm-up rows were assigned HOLD "
                "due to unavailable indicators"
            )
        if (unavailable & ~signals["Signal"].eq("HOLD")).any():
            raise SignalCalculationError(
                "A signal was generated with unavailable indicators"
            )
        return warnings