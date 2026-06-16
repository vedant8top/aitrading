"""Bull Trap detection strategy — sells into false breakouts above resistance."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.strategies.base_strategy import BaseStrategy


REQUIRED_INDICATOR_COLUMNS: tuple[str, ...] = (
    "Date",
    "Close",
    "Volume",
    "SMA_20",
    "Volume_MA_20",
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
class BullTrapStrategy(BaseStrategy):
    """Bull Trap strategy — detects false breakouts above resistance.

    SELL (trap detected):
      - Close breaks above the 20-day high (recent resistance).
      - Volume is below the 20-day average (weak breakout).
      - Next period Close closes back below the 20-day high.

    EXIT (HOLD) after trap resolves.
    """

    _name: str = field(default="bull_trap")
    _description: str = field(
        default=(
            "Bull Trap Strategy. "
            "SELL when price breaks above 20-day high with below-average volume "
            "then closes back below resistance."
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

        # 20-day resistance level
        resistance_20 = close.rolling(20, min_periods=20).max().shift(1)

        indicator_columns = [col for col in REQUIRED_INDICATOR_COLUMNS if col != "Date"]
        indicators_ready = enriched[indicator_columns].notna().all(axis=1)

        # Bull trap: price breaks above resistance with low volume, then falls back
        resistance_20_shifted = close.rolling(20, min_periods=20).max().shift(2)
        breakout_above = close > resistance_20_shifted
        low_volume = volume < enriched["Volume_MA_20"]

        # Next period close relative to resistance
        close_next = close.shift(-1)
        close_prev = close.shift(1)
        resistance_same = close.rolling(20, min_periods=20).max().shift(1)

        # Trap fires today if: yesterday there was a weak breakout, and today close is back below resistance
        trap_buy_today = close_prev > close.rolling(20, min_periods=20).max().shift(2)  # yesterday was above
        trap_low_vol_today = enriched["Volume"].shift(1) < enriched["Volume_MA_20"].shift(1)
        trap_fail_today = close < resistance_same  # today back below

        buy_conditions = pd.DataFrame(index=enriched.index)
        sell_conditions = pd.DataFrame(
            {
                "breakout_above_resistance": trap_buy_today & trap_low_vol_today,
                "closed_below_resistance": trap_fail_today,
            },
            index=enriched.index,
        ).fillna(False)

        # SELL requires both: weak breakout yesterday + close back below today
        sell_signal = indicators_ready & sell_conditions.all(axis=1)

        buy_count = pd.Series(0, index=enriched.index)
        sell_count_val = sell_conditions.sum(axis=1).astype(int)

        signal = np.select(
            (sell_signal,), ("SELL",), default="HOLD"
        )
        applicable_count = np.select(
            (sell_signal,), (sell_count_val,), default=0
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
        enriched["Sell_Conditions_Met"] = sell_count_val
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