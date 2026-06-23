import numpy as np
import pandas as pd
import pytest

from src.strategies.momentum_strategy import (
    REQUIRED_INDICATOR_COLUMNS,
    SIGNAL_COLUMNS,
    MomentumStrategy,
)


@pytest.fixture
def sample_data() -> pd.DataFrame:
    """Fixture providing a basic dataframe with required columns."""
    return pd.DataFrame(
        {
            "Date": pd.to_datetime(["2023-01-01", "2023-01-02", "2023-01-03"]),
            "Close": [100.0, 105.0, 95.0],
            "SMA_50": [90.0, 90.0, 90.0],
            "RSI_14": [55.0, 65.0, 45.0],
            "Volume": [1000, 1500, 800],
            "Volume_MA_20": [900, 900, 900],
            "SMA_20": [95.0, 95.0, 95.0],
        }
    )


def test_momentum_strategy_properties():
    """Test that the strategy properties match expected values."""
    strategy = MomentumStrategy()

    assert strategy.get_strategy_name() == "momentum"
    assert "Momentum Strategy" in strategy.get_strategy_description()
    assert strategy.required_indicator_columns == REQUIRED_INDICATOR_COLUMNS
    assert strategy.signal_columns == SIGNAL_COLUMNS

def test_momentum_strategy_buy_signal():
    """Test BUY signal when all conditions are met."""
    strategy = MomentumStrategy()
    data = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2023-01-01"]),
            "Close": [110.0],          # > SMA_50 (100)
            "SMA_50": [100.0],
            "RSI_14": [65.0],          # > 60
            "Volume": [2000],          # > Volume_MA_20 (1500)
            "Volume_MA_20": [1500],
            "SMA_20": [105.0],
        }
    )
    result = strategy.generate_signals(data)

    assert len(result) == 1
    assert result.iloc[0]["Signal"] == "BUY"
    assert result.iloc[0]["Signal_Confidence"] == "High"
    assert result.iloc[0]["Conditions_Met"] == 3


def test_momentum_strategy_sell_signal_rsi():
    """Test SELL signal when RSI drops below 50."""
    strategy = MomentumStrategy()
    data = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2023-01-01"]),
            "Close": [110.0],          # > SMA_50 (100)
            "SMA_50": [100.0],
            "RSI_14": [45.0],          # < 50 (Triggers SELL)
            "Volume": [2000],          # > Volume_MA_20 (1500)
            "Volume_MA_20": [1500],
            "SMA_20": [105.0],         # Close > SMA_20, so not triggered by this
        }
    )
    result = strategy.generate_signals(data)

    assert len(result) == 1
    assert result.iloc[0]["Signal"] == "SELL"


def test_momentum_strategy_sell_signal_trend_broken():
    """Test SELL signal when Close drops below SMA 20."""
    strategy = MomentumStrategy()
    data = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2023-01-01"]),
            "Close": [100.0],          # < SMA_20 (105) (Triggers SELL)
            "SMA_50": [90.0],
            "RSI_14": [55.0],          # Not < 50, Not > 60
            "Volume": [2000],
            "Volume_MA_20": [1500],
            "SMA_20": [105.0],
        }
    )
    result = strategy.generate_signals(data)

    assert len(result) == 1
    assert result.iloc[0]["Signal"] == "SELL"


def test_momentum_strategy_hold_signal():
    """Test HOLD signal when neither BUY nor SELL conditions are met."""
    strategy = MomentumStrategy()
    data = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2023-01-01"]),
            "Close": [110.0],          # > SMA_50
            "SMA_50": [100.0],
            "RSI_14": [55.0],          # Between 50 and 60 (No BUY, No SELL)
            "Volume": [2000],          # > Volume_MA_20
            "Volume_MA_20": [1500],
            "SMA_20": [105.0],         # Close > SMA_20
        }
    )
    result = strategy.generate_signals(data)

    assert len(result) == 1
    assert result.iloc[0]["Signal"] == "HOLD"

def test_momentum_strategy_warmup_holds():
    """Test that rows with missing data are assigned HOLD."""
    strategy = MomentumStrategy()
    data = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2023-01-01"]),
            "Close": [np.nan],
            "SMA_50": [np.nan],
            "RSI_14": [np.nan],
            "Volume": [np.nan],
            "Volume_MA_20": [np.nan],
            "SMA_20": [np.nan],
        }
    )
    result = strategy.generate_signals(data)

    assert len(result) == 1
    assert result.iloc[0]["Signal"] == "HOLD"

    warnings = strategy.validate_output(data, result)
    assert len(warnings) == 1
    assert "warm-up rows were assigned HOLD due to unavailable indicators" in warnings[0]


def test_validate_output_success():
    """Test validate_output passes on correctly formatted output."""
    strategy = MomentumStrategy()
    data = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2023-01-01"]),
            "Close": [110.0],
            "SMA_50": [100.0],
            "RSI_14": [65.0],
            "Volume": [2000],
            "Volume_MA_20": [1500],
            "SMA_20": [105.0],
        }
    )
    result = strategy.generate_signals(data)
    warnings = strategy.validate_output(data, result)
    assert not warnings


def test_validate_output_missing_signal():
    """Test validate_output raises an error if signal columns are missing."""
    from src.strategies.signal_engine import SignalCalculationError

    strategy = MomentumStrategy()
    data = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2023-01-01"]),
            "Close": [110.0],
            "SMA_50": [100.0],
            "RSI_14": [65.0],
            "Volume": [2000],
            "Volume_MA_20": [1500],
            "SMA_20": [105.0],
        }
    )
    result = strategy.generate_signals(data)
    result = result.drop(columns=["Signal"])

    with pytest.raises(SignalCalculationError) as exc_info:
        strategy.validate_output(data, result)

    assert "Missing signal columns: Signal" in str(exc_info.value)
