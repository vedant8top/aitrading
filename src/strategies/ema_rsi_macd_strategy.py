"""EMA Trend + RSI + MACD Confirmation trading strategy."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from src.strategies.base_strategy import BaseStrategy


REQUIRED_INDICATOR_COLUMNS: tuple[str, ...] = (
    "Date",
    "Close",
    "EMA_20",
    "EMA_50",
    "EMA_200",
    "RSI_14",
    "MACD",
    "MACD_Signal",
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
class EmaRsiMacdStrategy(BaseStrategy):
    """EMA trend, RSI, and MACD confirmation strategy.

    BUY requires all four conditions:
      - EMA 20 is above EMA 50.
      - Close is above EMA 200.
      - RSI 14 is between 55 and 70, inclusive.
      - MACD is above the MACD Signal line.

    SELL requires at least one condition, provided the BUY rule did not match:
      - EMA 20 is below EMA 50, or
      - RSI 14 is below 45, or
      - MACD is below the MACD Signal line.

    All other rows are HOLD.

    Confidence:
      - High:  4 applicable conditions met.
      - Medium: 3 applicable conditions met.
      - Low:   fewer than 3 applicable conditions met.
    """

    # Allow frozen dataclass to have these set by __init__.
    _name: str = field(default="ema_rsi_macd")
    _description: str = field(
        default=(
            "EMA Trend + RSI + MACD Confirmation. "
            "BUY when EMA20 > EMA50, Close > EMA200, RSI14 in [55,70], "
            "and MACD > Signal. SELL when EMA20 < EMA50 or RSI14 < 45 "
            "or MACD < Signal."
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
        """Return the source data with deterministic signal columns appended."""
        enriched = data.copy()
        indicator_columns = [
            col for col in REQUIRED_INDICATOR_COLUMNS if col != "Date"
        ]
        indicators_ready = enriched[indicator_columns].notna().all(axis=1)

        buy_conditions = pd.DataFrame(
            {
                "ema_trend": enriched["EMA_20"] > enriched["EMA_50"],
                "above_ema_200": enriched["Close"] > enriched["EMA_200"],
                "rsi_buy_range": enriched["RSI_14"].between(
                    55, 70, inclusive="both"
                ),
                "macd_confirmation": enriched["MACD"] > enriched["MACD_Signal"],
            },
            index=enriched.index,
        ).fillna(False)
        sell_conditions = pd.DataFrame(
            {
                "ema_bearish": enriched["EMA_20"] < enriched["EMA_50"],
                "rsi_weak": enriched["RSI_14"] < 45,
                "macd_bearish": enriched["MACD"] < enriched["MACD_Signal"],
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
            (applicable_count >= 4, applicable_count == 3),
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
        """Validate the output produced by generate_signals.

        Args:
            source: The original input DataFrame.
            signals: The output DataFrame from generate_signals.

        Returns:
            A list of warning strings (may be empty).

        Raises:
            SignalCalculationError: If a critical consistency check fails.
        """
        from src.strategies.signal_engine import SignalEngineError
        from src.strategies.signal_engine import SignalCalculationError

        if len(source) != len(signals):
            raise SignalCalculationError(
                "Row count changed during signal generation"
            )
        if not source["Date"].equals(signals["Date"]):
            raise SignalCalculationError("Source date alignment changed")
        if not signals["Date"].equals(signals["Signal_Date"]):
            raise SignalCalculationError(
                "Signal dates are not aligned with source dates"
            )

        missing_cols = [
            col for col in SIGNAL_COLUMNS if col not in signals
        ]
        if missing_cols:
            raise SignalCalculationError(
                f"Missing signal columns: {', '.join(missing_cols)}"
            )
        if not signals["Signal"].isin(("BUY", "SELL", "HOLD")).all():
            raise SignalCalculationError("Unexpected signal value generated")
        if not signals["Signal_Confidence"].isin(
            ("Low", "Medium", "High")
        ).all():
            raise SignalCalculationError(
                "Unexpected confidence value generated"
            )

        warnings: list[str] = []
        unavailable = signals[
            [col for col in REQUIRED_INDICATOR_COLUMNS if col != "Date"]
        ].isna().any(axis=1)
        warmup_holds = int(
            (unavailable & signals["Signal"].eq("HOLD")).sum()
        )
        if warmup_holds:
            warnings.append(
                f"{warmup_holds} warm-up rows were assigned HOLD "
                "due to unavailable indicators"
            )
        if (unavailable & ~signals["Signal"].eq("HOLD")).any():
            raise SignalCalculationError(
                "A signal was generated with unavailable indicators"
            )

        buy_rows = signals["Signal"].eq("BUY")
        if (signals.loc[buy_rows, "Conditions_Met"] != 4).any():
            raise SignalCalculationError(
                "BUY generated without all four confirmations"
            )
        sell_rows = signals["Signal"].eq("SELL")
        if (signals.loc[sell_rows, "Sell_Conditions_Met"] < 1).any():
            raise SignalCalculationError(
                "SELL generated without a sell condition"
            )
        return warnings
