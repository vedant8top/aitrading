"""Bear Trap detection strategy — buys into false breakdowns below support."""

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
class BearTrapStrategy(BaseStrategy):
    """Bear Trap strategy — detects false breakdowns below support.

    BUY (trap detected):
      - Close breaks below the 20-day low (recent support).
      - Volume is below the 20-day average (weak breakdown).
      - Next period Close recovers back above the 20-day low.

    SELL (exit after recovery):
      - Close moves back above the 20-day SMA (recovery target achieved).
    """

    _name: str = field(default="bear_trap")
    _description: str = field(
        default=(
            "Bear Trap Strategy. "
            "BUY when price breaks below 20-day low with below-average volume "
            "then recovers back above support. SELL when Close > SMA20."
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

        support_20 = close.rolling(20, min_periods=20).min().shift(1)
        close_prev = close.shift(1)

        indicator_columns = [col for col in REQUIRED_INDICATOR_COLUMNS if col != "Date"]
        indicators_ready = enriched[indicator_columns].notna().all(axis=1)

        # Bear trap: yesterday broke below support with low volume, today recovered above
        trap_down_yesterday = close_prev < close.rolling(20, min_periods=20).min().shift(2)
        trap_low_vol_yesterday = enriched["Volume"].shift(1) < enriched["Volume_MA_20"].shift(1)
        trap_recovery_today = close > support_20

        buy_conditions = pd.DataFrame(
            {
                "broke_below_support": trap_down_yesterday & trap_low_vol_yesterday,
                "recovered_above_support": trap_recovery_today,
            },
            index=enriched.index,
        ).fillna(False)

        sell_conditions = pd.DataFrame(
            {
                "above_sma_20": close > enriched["SMA_20"],
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