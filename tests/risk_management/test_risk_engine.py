import pytest
from datetime import datetime, timedelta

from src.risk_management.risk_engine import RiskManager, RiskMode, RiskControls

def test_check_stop_exits_mode_none():
    """In NONE mode, check_stop_exits should always return an empty list."""
    manager = RiskManager(mode=RiskMode.NONE)
    positions = {"AAPL": 100}
    current_date = datetime(2023, 1, 15)
    last_close = {"AAPL": 90.0}
    atr_lookup = {"AAPL": 2.0}
    entry_dates = {"AAPL": datetime(2023, 1, 1)}
    entry_prices = {"AAPL": 100.0}

    exits = manager.check_stop_exits(
        positions=positions,
        current_date=current_date,
        last_close=last_close,
        atr_lookup=atr_lookup,
        entry_dates=entry_dates,
        entry_prices=entry_prices,
    )
    assert exits == []

def test_check_stop_exits_basic_percentage_stop():
    """In BASIC mode, PercentageStop should trigger if price drops by configured percentage."""
    controls = RiskControls(percentage_stop_pct=7.0)
    manager = RiskManager(mode=RiskMode.BASIC, controls=controls)

    positions = {"AAPL": 100}
    current_date = datetime(2023, 1, 15)
    # Entry is 100, drop of 7% would be 93. At 92, drop is 8%, which is >= 7%.
    last_close = {"AAPL": 92.0}
    atr_lookup = {"AAPL": 2.0}
    entry_dates = {"AAPL": datetime(2023, 1, 1)}
    entry_prices = {"AAPL": 100.0}

    exits = manager.check_stop_exits(
        positions=positions,
        current_date=current_date,
        last_close=last_close,
        atr_lookup=atr_lookup,
        entry_dates=entry_dates,
        entry_prices=entry_prices,
    )

    # Expect 1 exit for AAPL. Exit price is current_price * (1.0 - 0.0005)
    assert len(exits) == 1
    ticker, signal_date, exit_price = exits[0]
    assert ticker == "AAPL"
    assert signal_date == current_date
    assert exit_price == 92.0 * (1.0 - 0.0005)

def test_check_stop_exits_basic_time_stop():
    """In BASIC mode, TimeStop should trigger if holding days >= time_stop_days."""
    controls = RiskControls(percentage_stop_pct=7.0, time_stop_days=90)
    manager = RiskManager(mode=RiskMode.BASIC, controls=controls)

    positions = {"MSFT": 50}
    entry_date = datetime(2023, 1, 1)
    current_date = datetime(2023, 4, 15) # 104 days later
    last_close = {"MSFT": 100.0}
    atr_lookup = {"MSFT": 2.0}
    entry_dates = {"MSFT": entry_date}
    entry_prices = {"MSFT": 100.0}

    exits = manager.check_stop_exits(
        positions=positions,
        current_date=current_date,
        last_close=last_close,
        atr_lookup=atr_lookup,
        entry_dates=entry_dates,
        entry_prices=entry_prices,
    )

    assert len(exits) == 1
    ticker, signal_date, exit_price = exits[0]
    assert ticker == "MSFT"
    assert signal_date == current_date
    assert exit_price == 100.0 * (1.0 - 0.0005)

def test_check_stop_exits_advanced_atr_stop():
    """In ADVANCED mode, ATRStop should trigger if price drops more than N*ATR."""
    controls = RiskControls(atr_stop_multiplier=3.0)
    manager = RiskManager(mode=RiskMode.ADVANCED, controls=controls)

    positions = {"TSLA": 10}
    current_date = datetime(2023, 1, 15)
    # Entry 100, ATR 2.0. Stop distance is 3 * 2.0 = 6.0.
    # Price drop >= 6 triggers stop. At 93, drop is 7, which is > 6.
    last_close = {"TSLA": 93.0}
    atr_lookup = {"TSLA": 2.0}
    entry_dates = {"TSLA": datetime(2023, 1, 1)}
    entry_prices = {"TSLA": 100.0}

    exits = manager.check_stop_exits(
        positions=positions,
        current_date=current_date,
        last_close=last_close,
        atr_lookup=atr_lookup,
        entry_dates=entry_dates,
        entry_prices=entry_prices,
    )

    assert len(exits) == 1
    ticker, signal_date, exit_price = exits[0]
    assert ticker == "TSLA"
    assert signal_date == current_date
    assert exit_price == 93.0 * (1.0 - 0.0005)

def test_check_stop_exits_missing_or_negative_price():
    """Should continue to next position if last close is missing or <= 0."""
    controls = RiskControls(percentage_stop_pct=7.0, time_stop_days=90)
    manager = RiskManager(mode=RiskMode.BASIC, controls=controls)

    positions = {"AAPL": 100, "MSFT": 50, "TSLA": 10}
    current_date = datetime(2023, 4, 15) # 104 days later to trigger time stop
    entry_date = datetime(2023, 1, 1)

    # Missing AAPL, negative MSFT, valid TSLA
    last_close = {"MSFT": -10.0, "TSLA": 100.0}
    atr_lookup = {"AAPL": 2.0, "MSFT": 2.0, "TSLA": 2.0}
    entry_dates = {"AAPL": entry_date, "MSFT": entry_date, "TSLA": entry_date}
    entry_prices = {"AAPL": 100.0, "MSFT": 100.0, "TSLA": 100.0}

    exits = manager.check_stop_exits(
        positions=positions,
        current_date=current_date,
        last_close=last_close,
        atr_lookup=atr_lookup,
        entry_dates=entry_dates,
        entry_prices=entry_prices,
    )

    # AAPL is skipped (missing price)
    # MSFT is skipped (negative price)
    # TSLA triggers TimeStop
    assert len(exits) == 1
    ticker, _, _ = exits[0]
    assert ticker == "TSLA"

def test_check_stop_exits_date_type_error():
    """Should handle non-subtractable date objects gracefully."""
    controls = RiskControls(percentage_stop_pct=7.0, time_stop_days=90)
    manager = RiskManager(mode=RiskMode.BASIC, controls=controls)

    positions = {"AAPL": 100}
    # Pass integers instead of datetime objects to simulate TypeError on subtraction
    # Or an object that has __sub__ but raises TypeError or AttributeError
    class BadDate:
        def __sub__(self, other):
            raise TypeError("Cannot subtract")

    current_date = BadDate()
    entry_date = BadDate()

    # Ensure it doesn't trigger TimeStop because holding_days should default to 0
    # Also don't trigger PercentageStop
    last_close = {"AAPL": 99.0}
    atr_lookup = {"AAPL": 2.0}
    entry_dates = {"AAPL": entry_date}
    entry_prices = {"AAPL": 100.0}

    exits = manager.check_stop_exits(
        positions=positions,
        current_date=current_date,
        last_close=last_close,
        atr_lookup=atr_lookup,
        entry_dates=entry_dates,
        entry_prices=entry_prices,
    )

    assert len(exits) == 0
