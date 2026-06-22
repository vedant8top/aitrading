import numpy as np
import pandas as pd
import pytest

from src.strategies.bear_trap_strategy import (
    BearTrapStrategy,
    REQUIRED_INDICATOR_COLUMNS,
    SIGNAL_COLUMNS,
)
from src.strategies.signal_engine import SignalCalculationError


@pytest.fixture
def sample_data():
    """Generates a dataset of 30 days for testing Bear Trap."""
    dates = pd.date_range("2023-01-01", periods=30)

    data = pd.DataFrame({
        "Date": dates,
        "Close": 100.0,
        "Volume": 1000.0,
        "SMA_20": 100.0,
        "Volume_MA_20": 1000.0,
    })

    # Create the bear trap scenario
    # Day 0 to Day 22: Close is 100. The 20-day low is 100.

    # Day 23: Breakdown with low volume
    data.loc[23, "Close"] = 90.0
    data.loc[23, "Volume"] = 500.0  # Below Volume_MA_20 (which is 1000.0)
    data.loc[23, "SMA_20"] = 100.0

    # Day 24: Recovery above support_20 (support_20 will be 90)
    data.loc[24, "Close"] = 95.0
    data.loc[24, "Volume"] = 1000.0
    data.loc[24, "SMA_20"] = 100.0  # Close < SMA_20, so no sell signal

    # Day 25: Move above SMA_20 to trigger SELL
    data.loc[25, "Close"] = 105.0
    data.loc[25, "SMA_20"] = 100.0

    return data


def test_strategy_properties():
    strategy = BearTrapStrategy()
    assert strategy.required_indicator_columns == REQUIRED_INDICATOR_COLUMNS
    assert strategy.signal_columns == SIGNAL_COLUMNS
    assert strategy.get_strategy_name() == "bear_trap"
    assert "Bear Trap Strategy" in strategy.get_strategy_description()


def test_generate_signals_buy_sell_hold(sample_data):
    strategy = BearTrapStrategy()
    signals = strategy.generate_signals(sample_data)

    # At index 24 (Day 25), we expect a BUY signal
    assert signals.loc[24, "Signal"] == "BUY"
    assert signals.loc[24, "Buy_Conditions_Met"] == 2

    # At index 25 (Day 26), we expect a SELL signal (Close 105 > SMA_20 100)
    assert signals.loc[25, "Signal"] == "SELL"
    assert signals.loc[25, "Sell_Conditions_Met"] == 1

    # At index 22, we expect HOLD (indicators ready but no conditions met)
    assert signals.loc[22, "Signal"] == "HOLD"


def test_validate_output_success(sample_data):
    strategy = BearTrapStrategy()
    signals = strategy.generate_signals(sample_data)

    warnings = strategy.validate_output(sample_data, signals)
    assert warnings == []


def test_validate_output_warmup_warnings(sample_data):
    # Introduce NaN to simulate unavailable indicators
    data = sample_data.copy()
    data.loc[0:5, "SMA_20"] = np.nan
    strategy = BearTrapStrategy()
    signals = strategy.generate_signals(data)

    warnings = strategy.validate_output(data, signals)
    assert len(warnings) == 1
    assert "warm-up rows were assigned HOLD due to unavailable indicators" in warnings[0]


def test_validate_output_errors(sample_data):
    strategy = BearTrapStrategy()
    signals = strategy.generate_signals(sample_data)

    # Test row count changed
    with pytest.raises(SignalCalculationError, match="Row count changed"):
        strategy.validate_output(sample_data, signals.iloc[:-1])

    # Test date alignment
    bad_dates = signals.copy()
    bad_dates.loc[0, "Date"] = pd.Timestamp("2020-01-01")
    with pytest.raises(SignalCalculationError, match="Source date alignment changed"):
        strategy.validate_output(sample_data, bad_dates)

    # Test signal dates alignment
    bad_signal_dates = signals.copy()
    bad_signal_dates.loc[0, "Signal_Date"] = pd.Timestamp("2020-01-01")
    with pytest.raises(SignalCalculationError, match="Signal dates are not aligned"):
        strategy.validate_output(sample_data, bad_signal_dates)

    # Test missing columns
    missing_col = signals.drop(columns=["Signal"])
    with pytest.raises(SignalCalculationError, match="Missing signal columns"):
        strategy.validate_output(sample_data, missing_col)

    # Test unexpected signal value
    bad_signal = signals.copy()
    bad_signal.loc[25, "Signal"] = "INVALID"
    with pytest.raises(SignalCalculationError, match="Unexpected signal value generated"):
        strategy.validate_output(sample_data, bad_signal)

    # Test unexpected confidence value
    bad_conf = signals.copy()
    bad_conf.loc[25, "Signal_Confidence"] = "INVALID"
    with pytest.raises(SignalCalculationError, match="Unexpected confidence value generated"):
        strategy.validate_output(sample_data, bad_conf)

    # Test signal generated with unavailable indicators
    bad_unavailable = signals.copy()
    bad_unavailable.loc[24, "SMA_20"] = np.nan  # index 24 is BUY
    with pytest.raises(SignalCalculationError, match="generated with unavailable indicators"):
        strategy.validate_output(sample_data, bad_unavailable)
