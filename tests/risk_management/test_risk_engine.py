from datetime import date
from src.risk_management.risk_engine import RiskManager, RiskMode, RiskControls

def test_check_stop_exits_early_return():
    manager = RiskManager(mode=RiskMode.NONE)
    positions = {"AAPL": 100}
    exits = manager.check_stop_exits(
        positions=positions,
        current_date=date(2023, 10, 2),
        last_close={"AAPL": 150.0},
        atr_lookup={},
        entry_dates={"AAPL": date(2023, 10, 1)},
        entry_prices={"AAPL": 140.0}
    )
    assert exits == []

def test_check_stop_exits_skip_missing_prices():
    manager = RiskManager(mode=RiskMode.BASIC)
    positions = {"AAPL": 100, "MSFT": 50, "GOOG": 10}
    # MSFT is missing from last_close, GOOG has non-positive price
    exits = manager.check_stop_exits(
        positions=positions,
        current_date=date(2023, 10, 2),
        last_close={"AAPL": 150.0, "GOOG": 0.0},
        atr_lookup={},
        entry_dates={"AAPL": date(2023, 10, 1), "GOOG": date(2023, 10, 1)},
        entry_prices={"AAPL": 140.0, "GOOG": 140.0}
    )
    assert exits == []

def test_check_stop_exits_successful_stop_trigger():
    # PercentageStop default is 7.0%
    controls = RiskControls(percentage_stop_pct=7.0)
    manager = RiskManager(mode=RiskMode.BASIC, controls=controls)
    positions = {"AAPL": 100}

    # AAPL dropped > 7% from entry
    entry_price = 100.0
    current_price = 92.0 # 8% drop

    current_dt = date(2023, 10, 2)
    exits = manager.check_stop_exits(
        positions=positions,
        current_date=current_dt,
        last_close={"AAPL": current_price},
        atr_lookup={},
        entry_dates={"AAPL": date(2023, 10, 1)},
        entry_prices={"AAPL": entry_price}
    )

    expected_exit_price = current_price * (1.0 - 0.0005)
    assert exits == [("AAPL", current_dt, expected_exit_price)]

def test_check_stop_exits_holding_days_time_stop():
    # TimeStop default is 90 days
    controls = RiskControls(time_stop_days=90)
    manager = RiskManager(mode=RiskMode.BASIC, controls=controls)
    positions = {"AAPL": 100}

    entry_price = 100.0
    current_price = 110.0 # Profit, not triggered by PercentageStop

    entry_dt = date(2023, 1, 1)
    current_dt = date(2023, 5, 1) # ~120 days

    exits = manager.check_stop_exits(
        positions=positions,
        current_date=current_dt,
        last_close={"AAPL": current_price},
        atr_lookup={},
        entry_dates={"AAPL": entry_dt},
        entry_prices={"AAPL": entry_price}
    )

    expected_exit_price = current_price * (1.0 - 0.0005)
    assert exits == [("AAPL", current_dt, expected_exit_price)]

def test_check_stop_exits_holding_days_exception_handling():
    # Exception handling for date types that don't support subtraction or don't have .days
    controls = RiskControls(time_stop_days=90)
    manager = RiskManager(mode=RiskMode.BASIC, controls=controls)
    positions = {"AAPL": 100}

    entry_price = 100.0
    current_price = 110.0

    class DummyDate:
        def __sub__(self, other):
            raise TypeError("Cannot subtract")

    current_dt = DummyDate()
    entry_dt = DummyDate()

    exits = manager.check_stop_exits(
        positions=positions,
        current_date=current_dt,
        last_close={"AAPL": current_price},
        atr_lookup={},
        entry_dates={"AAPL": entry_dt},
        entry_prices={"AAPL": entry_price}
    )

    # Should fallback to holding_days = 0, which < 90, and price drop is not > 7%, so no exit
    assert exits == []
