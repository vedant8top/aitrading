"""Abstract base class for pluggable trading strategies."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import pandas as pd


class BaseStrategy(ABC):
    """Interface that every trading strategy must implement.

    A strategy defines:
      - Which indicator columns it requires as input.
      - Which signal columns it appends as output.
      - The deterministic signal generation logic.
      - Validation rules for its own output.
    """

    @property
    @abstractmethod
    def required_indicator_columns(self) -> tuple[str, ...]:
        """Columns that must be present in the input DataFrame.

        These typically include ``"Date"`` plus any technical indicators
        that the strategy depends on (e.g. ``"EMA_20"``, ``"RSI_14"``).
        """

    @property
    @abstractmethod
    def signal_columns(self) -> tuple[str, ...]:
        """Columns that the strategy appends to the output DataFrame.

        Every strategy must produce at minimum a ``"Signal"`` column
        whose values are ``"BUY"``, ``"SELL"``, or ``"HOLD"``.
        """

    @abstractmethod
    def get_strategy_name(self) -> str:
        """Human-readable name for the strategy (e.g. ``"ema_rsi_macd"``)."""

    @abstractmethod
    def get_strategy_description(self) -> str:
        """Short description of the strategy logic and entry/exit rules."""

    @abstractmethod
    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """Return a copy of *data* with signal columns appended.

        The caller is responsible for having validated that *data*
        contains all columns listed in :attr:`required_indicator_columns`.

        Args:
            data: Input DataFrame with at least the required indicator columns.

        Returns:
            A new DataFrame that includes every column from *data* plus the
            columns listed in :attr:`signal_columns`.
        """

    @abstractmethod
    def validate_output(
        self, source: pd.DataFrame, signals: pd.DataFrame
    ) -> list[str]:
        """Validate the output produced by :meth:`generate_signals`.

        Args:
            source: The original input DataFrame that was passed to
                :meth:`generate_signals`.
            signals: The DataFrame returned by :meth:`generate_signals`.

        Returns:
            A list of warning strings (may be empty). Non-fatal issues
            that do not prevent the result from being saved are reported
            as warnings.

        Raises:
            SignalCalculationError: If the output fails a critical
                consistency check.
        """