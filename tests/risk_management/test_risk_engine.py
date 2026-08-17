import pytest
from datetime import datetime

from src.risk_management.risk_engine import (
    StopLoss,
    PercentageStop,
    ATRStop,
    TimeStop,
    RiskControls,
)

def test_stoploss_raises_not_implemented():
    stop_loss = StopLoss()
    with pytest.raises(NotImplementedError):
        stop_loss.should_exit(
            entry_price=100.0,
            current_price=95.0,
            entry_date=datetime(2023, 1, 1),
            current_date=datetime(2023, 1, 2),
            holding_days=1,
            atr=2.0,
            controls=RiskControls(),
        )

def test_percentagestop_should_exit_true():
    stop_loss = PercentageStop()
    controls = RiskControls(percentage_stop_pct=7.0)
    # Entry 100, drops to 92 (8% drop)
    assert stop_loss.should_exit(
        entry_price=100.0,
        current_price=92.0,
        entry_date=datetime(2023, 1, 1),
        current_date=datetime(2023, 1, 2),
        holding_days=1,
        atr=2.0,
        controls=controls,
    ) is True

def test_percentagestop_should_exit_false():
    stop_loss = PercentageStop()
    controls = RiskControls(percentage_stop_pct=7.0)
    # Entry 100, drops to 95 (5% drop)
    assert stop_loss.should_exit(
        entry_price=100.0,
        current_price=95.0,
        entry_date=datetime(2023, 1, 1),
        current_date=datetime(2023, 1, 2),
        holding_days=1,
        atr=2.0,
        controls=controls,
    ) is False

def test_percentagestop_entry_zero_or_negative():
    stop_loss = PercentageStop()
    controls = RiskControls(percentage_stop_pct=7.0)
    assert stop_loss.should_exit(
        entry_price=0.0,
        current_price=-5.0,
        entry_date=datetime(2023, 1, 1),
        current_date=datetime(2023, 1, 2),
        holding_days=1,
        atr=2.0,
        controls=controls,
    ) is False

def test_atrstop_should_exit_true():
    stop_loss = ATRStop()
    controls = RiskControls(atr_stop_multiplier=3.0)
    # Entry 100, ATR 2.0 (drop allowed 6.0)
    # Current 93, drop is 7.0 (>= 6.0)
    assert stop_loss.should_exit(
        entry_price=100.0,
        current_price=93.0,
        entry_date=datetime(2023, 1, 1),
        current_date=datetime(2023, 1, 2),
        holding_days=1,
        atr=2.0,
        controls=controls,
    ) is True

def test_atrstop_should_exit_false():
    stop_loss = ATRStop()
    controls = RiskControls(atr_stop_multiplier=3.0)
    # Entry 100, ATR 2.0 (drop allowed 6.0)
    # Current 95, drop is 5.0 (< 6.0)
    assert stop_loss.should_exit(
        entry_price=100.0,
        current_price=95.0,
        entry_date=datetime(2023, 1, 1),
        current_date=datetime(2023, 1, 2),
        holding_days=1,
        atr=2.0,
        controls=controls,
    ) is False

def test_atrstop_invalid_inputs():
    stop_loss = ATRStop()
    controls = RiskControls(atr_stop_multiplier=3.0)

    # Entry <= 0
    assert stop_loss.should_exit(
        entry_price=0.0,
        current_price=-10.0,
        entry_date=datetime(2023, 1, 1),
        current_date=datetime(2023, 1, 2),
        holding_days=1,
        atr=2.0,
        controls=controls,
    ) is False

    # ATR is None
    assert stop_loss.should_exit(
        entry_price=100.0,
        current_price=90.0,
        entry_date=datetime(2023, 1, 1),
        current_date=datetime(2023, 1, 2),
        holding_days=1,
        atr=None,
        controls=controls,
    ) is False

    # ATR <= 0
    assert stop_loss.should_exit(
        entry_price=100.0,
        current_price=90.0,
        entry_date=datetime(2023, 1, 1),
        current_date=datetime(2023, 1, 2),
        holding_days=1,
        atr=0.0,
        controls=controls,
    ) is False

def test_timestop_should_exit_true():
    stop_loss = TimeStop()
    controls = RiskControls(time_stop_days=90)
    assert stop_loss.should_exit(
        entry_price=100.0,
        current_price=90.0,
        entry_date=datetime(2023, 1, 1),
        current_date=datetime(2023, 4, 2),
        holding_days=90,
        atr=2.0,
        controls=controls,
    ) is True

def test_timestop_should_exit_false():
    stop_loss = TimeStop()
    controls = RiskControls(time_stop_days=90)
    assert stop_loss.should_exit(
        entry_price=100.0,
        current_price=90.0,
        entry_date=datetime(2023, 1, 1),
        current_date=datetime(2023, 1, 15),
        holding_days=14,
        atr=2.0,
        controls=controls,
    ) is False
