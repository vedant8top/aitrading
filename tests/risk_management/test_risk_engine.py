import pytest
from datetime import datetime, timedelta

from src.risk_management.risk_engine import TimeStop, RiskControls

def test_time_stop_should_exit():
    """Test the should_exit method of the TimeStop class."""
    stop = TimeStop()

    # default time_stop_days is 30. Let's create our own controls to be explicit.
    controls = RiskControls(time_stop_days=10)

    # Dummy parameters for the other fields, as they are not used by TimeStop
    entry_price = 100.0
    current_price = 90.0
    entry_date = datetime(2023, 1, 1)
    current_date = datetime(2023, 1, 5)
    atr = 5.0

    # Test case 1: holding_days < time_stop_days
    assert not stop.should_exit(
        entry_price=entry_price,
        current_price=current_price,
        entry_date=entry_date,
        current_date=current_date,
        holding_days=5,
        atr=atr,
        controls=controls
    )

    # Test case 2: holding_days == time_stop_days
    assert stop.should_exit(
        entry_price=entry_price,
        current_price=current_price,
        entry_date=entry_date,
        current_date=current_date,
        holding_days=10,
        atr=atr,
        controls=controls
    )

    # Test case 3: holding_days > time_stop_days
    assert stop.should_exit(
        entry_price=entry_price,
        current_price=current_price,
        entry_date=entry_date,
        current_date=current_date,
        holding_days=15,
        atr=atr,
        controls=controls
    )
