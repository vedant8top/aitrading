import pytest
import datetime
from src.risk_management.risk_engine import (
    RiskMode,
    RiskControls,
    FixedFractionalSizer,
    ATRBasedSizer,
    VolatilityAdjustedSizer,
    PercentageStop,
    ATRStop,
    TimeStop,
    RiskManager,
    build_risk_manager
)

def test_risk_controls_default():
    controls = RiskControls()
    assert controls.max_risk_per_trade_pct == 1.0
    assert controls.max_portfolio_exposure_pct == 80.0
    assert controls.max_concurrent_positions == 25
    assert controls.daily_loss_limit_pct == 3.0
    assert controls.portfolio_drawdown_limit_pct == 25.0
    assert controls.position_size_pct == 10.0
    assert controls.atr_stop_multiplier == 3.0
    assert controls.percentage_stop_pct == 7.0
    assert controls.time_stop_days == 90
    assert controls.atr_position_size_risk_pct == 1.0
    assert controls.atr_position_size_multiplier == 2.0

def test_risk_mode():
    assert RiskMode.NONE
    assert RiskMode.BASIC
    assert RiskMode.ADVANCED

def test_fixed_fractional_sizer():
    sizer = FixedFractionalSizer()
    controls = RiskControls(position_size_pct=10.0)
    # cash: 10000, allocation = 1000
    # price: 100, entry_price: 100 * 1.0005 = 100.05
    # brokerage: 0.01 (1%)
    # total cost per share = 100.05 * 1.01 = 101.0505
    # shares = 1000 / 101.0505 = 9.896 -> 9
    shares = sizer.compute_shares(
        cash=10000.0,
        price=100.0,
        brokerage_rate=0.01,
        controls=controls
    )
    assert shares == 9

def test_fixed_fractional_sizer_zero_cash():
    sizer = FixedFractionalSizer()
    assert sizer.compute_shares(cash=0.0, price=100.0, brokerage_rate=0.01) == 0

def test_atr_based_sizer_with_atr():
    sizer = ATRBasedSizer()
    controls = RiskControls(
        atr_position_size_multiplier=2.0,
        atr_position_size_risk_pct=1.0
    )
    # ATR = 5.0, risk_per_share = 10.0
    # cash = 10000, risk_capital = 100.0
    # shares = 100.0 / 10.0 = 10
    shares = sizer.compute_shares(
        cash=10000.0,
        price=100.0,
        brokerage_rate=0.01,
        atr=5.0,
        controls=controls
    )
    assert shares == 10

def test_atr_based_sizer_fallback():
    sizer = ATRBasedSizer()
    # Without ATR, it falls back to FixedFractionalSizer
    controls = RiskControls(position_size_pct=10.0)
    shares = sizer.compute_shares(
        cash=10000.0,
        price=100.0,
        brokerage_rate=0.01,
        atr=0.0,
        controls=controls
    )
    # Expected: 9, same as FixedFractionalSizer
    assert shares == 9

def test_volatility_adjusted_sizer():
    sizer = VolatilityAdjustedSizer()
    controls = RiskControls(position_size_pct=10.0)

    # Base shares would be 9
    # ATR = 1.0, price = 100.0 => vol_pct = 1.0%
    # scale = 2.0 / 1.0 = 2.0 (target vol = 2.0%)
    # adjusted = 9 * 2.0 = 18
    shares = sizer.compute_shares(
        cash=10000.0,
        price=100.0,
        brokerage_rate=0.01,
        atr=1.0,
        controls=controls
    )
    assert shares == 18

    # ATR = 4.0, price = 100.0 => vol_pct = 4.0%
    # scale = 2.0 / 4.0 = 0.5
    # adjusted = round(9 * 0.5) = 4 or 5
    shares_high_atr = sizer.compute_shares(
        cash=10000.0,
        price=100.0,
        brokerage_rate=0.01,
        atr=4.0,
        controls=controls
    )
    assert shares_high_atr == 4

def test_volatility_adjusted_sizer_clamp():
    sizer = VolatilityAdjustedSizer()
    controls = RiskControls(position_size_pct=10.0)

    # Very low volatility: ATR=0.1, price=100.0 => 0.1%
    # scale = 2.0 / 0.1 = 20.0 -> clamped to 2.0
    # adjusted = 9 * 2.0 = 18
    shares_low_vol = sizer.compute_shares(
        cash=10000.0,
        price=100.0,
        brokerage_rate=0.01,
        atr=0.1,
        controls=controls
    )
    assert shares_low_vol == 18

    # Very high volatility: ATR=20.0, price=100.0 => 20.0%
    # scale = 2.0 / 20.0 = 0.1 -> clamped to 0.25
    # adjusted = round(9 * 0.25) = round(2.25) = 2
    shares_high_vol = sizer.compute_shares(
        cash=10000.0,
        price=100.0,
        brokerage_rate=0.01,
        atr=20.0,
        controls=controls
    )
    assert shares_high_vol == 2

def test_volatility_adjusted_sizer_fallback():
    sizer = VolatilityAdjustedSizer()
    controls = RiskControls(position_size_pct=10.0)
    shares = sizer.compute_shares(
        cash=10000.0,
        price=100.0,
        brokerage_rate=0.01,
        atr=0.0,  # Fallback
        controls=controls
    )
    assert shares == 9


def test_percentage_stop():
    stop = PercentageStop()
    controls = RiskControls(percentage_stop_pct=7.0)

    # 10% drop, should exit
    assert stop.should_exit(
        entry_price=100.0,
        current_price=90.0,
        entry_date=None,
        current_date=None,
        holding_days=5,
        controls=controls
    ) is True

    # 5% drop, should not exit
    assert stop.should_exit(
        entry_price=100.0,
        current_price=95.0,
        entry_date=None,
        current_date=None,
        holding_days=5,
        controls=controls
    ) is False

    # Gain, should not exit
    assert stop.should_exit(
        entry_price=100.0,
        current_price=110.0,
        entry_date=None,
        current_date=None,
        holding_days=5,
        controls=controls
    ) is False

def test_percentage_stop_zero_entry():
    stop = PercentageStop()
    assert stop.should_exit(0.0, 90.0, None, None, 5) is False

def test_atr_stop():
    stop = ATRStop()
    controls = RiskControls(atr_stop_multiplier=3.0)

    # ATR = 2.0, max drop = 6.0. Price drops by 7.0 -> should exit
    assert stop.should_exit(
        entry_price=100.0,
        current_price=93.0,
        entry_date=None,
        current_date=None,
        holding_days=5,
        atr=2.0,
        controls=controls
    ) is True

    # Drops by 5.0 -> should not exit
    assert stop.should_exit(
        entry_price=100.0,
        current_price=95.0,
        entry_date=None,
        current_date=None,
        holding_days=5,
        atr=2.0,
        controls=controls
    ) is False

def test_atr_stop_invalid_inputs():
    stop = ATRStop()
    # Missing ATR
    assert stop.should_exit(100.0, 90.0, None, None, 5, atr=None) is False
    # Zero/negative ATR
    assert stop.should_exit(100.0, 90.0, None, None, 5, atr=0.0) is False
    # Zero entry price
    assert stop.should_exit(0.0, 90.0, None, None, 5, atr=2.0) is False

def test_time_stop():
    stop = TimeStop()
    controls = RiskControls(time_stop_days=30)

    assert stop.should_exit(
        entry_price=100.0,
        current_price=110.0,
        entry_date=None,
        current_date=None,
        holding_days=30,
        controls=controls
    ) is True

    assert stop.should_exit(
        entry_price=100.0,
        current_price=110.0,
        entry_date=None,
        current_date=None,
        holding_days=29,
        controls=controls
    ) is False

def test_risk_manager_init():
    rm_none = RiskManager(mode=RiskMode.NONE)
    assert isinstance(rm_none.sizer, FixedFractionalSizer)
    assert len(rm_none.stops) == 0
    assert rm_none.max_concurrent_positions == 9999
    assert rm_none.max_portfolio_exposure_pct == 100.0

    rm_basic = RiskManager(mode=RiskMode.BASIC)
    assert isinstance(rm_basic.sizer, FixedFractionalSizer)
    assert len(rm_basic.stops) == 2
    assert isinstance(rm_basic.stops[0], PercentageStop)
    assert isinstance(rm_basic.stops[1], TimeStop)

    rm_advanced = RiskManager(mode=RiskMode.ADVANCED)
    assert isinstance(rm_advanced.sizer, VolatilityAdjustedSizer)
    assert len(rm_advanced.stops) == 2
    assert isinstance(rm_advanced.stops[0], ATRStop)
    assert isinstance(rm_advanced.stops[1], TimeStop)

def test_risk_manager_build():
    rm = build_risk_manager("BASIC")
    assert rm.mode == RiskMode.BASIC
    rm = build_risk_manager("invalid")
    assert rm.mode == RiskMode.NONE

def test_risk_manager_compute_position_size():
    rm = RiskManager(mode=RiskMode.BASIC)
    # Just checking it proxies to sizer successfully
    shares = rm.compute_position_size(10000.0, 100.0, 0.01)
    assert shares == 9

def test_risk_manager_check_stop_exits():
    rm = RiskManager(mode=RiskMode.BASIC)  # Has PercentageStop and TimeStop
    rm.controls = RiskControls(percentage_stop_pct=10.0, time_stop_days=5)

    positions = {"AAPL": 10, "MSFT": 5, "TSLA": 15}
    entry_dates = {
        "AAPL": datetime.date(2023, 1, 1),
        "MSFT": datetime.date(2023, 1, 5),
        "TSLA": datetime.date(2023, 1, 10),
    }
    current_date = datetime.date(2023, 1, 12)
    entry_prices = {"AAPL": 100.0, "MSFT": 200.0, "TSLA": 50.0}
    last_close = {"AAPL": 85.0, "MSFT": 210.0, "TSLA": 40.0}
    atr_lookup = {}

    # AAPL: drop is 15%, should exit via PercentageStop
    # MSFT: holding days = 7 > 5, should exit via TimeStop
    # TSLA: drop is 20%, should exit via PercentageStop (holding days = 2 < 5)

    exits = rm.check_stop_exits(
        positions, current_date, last_close, atr_lookup, entry_dates, entry_prices
    )

    assert len(exits) == 3
    exit_tickers = {e[0] for e in exits}
    assert exit_tickers == {"AAPL", "MSFT", "TSLA"}

    # Check exit price is adjusted for simulated slippage
    # AAPL exit = 85.0 * (1 - 0.0005) = 84.9575
    aapl_exit = next(e for e in exits if e[0] == "AAPL")
    assert aapl_exit[1] == current_date
    assert aapl_exit[2] == 85.0 * 0.9995

def test_risk_manager_limits():
    rm = RiskManager(mode=RiskMode.ADVANCED, controls=RiskControls(daily_loss_limit_pct=3.0, portfolio_drawdown_limit_pct=20.0))

    # check_daily_loss_limit
    assert rm.check_daily_loss_limit(-3.5) is True
    assert rm.check_daily_loss_limit(-2.5) is False

    # check_drawdown_limit
    assert rm.check_drawdown_limit(10000.0) is False  # sets peak to 10000
    assert rm.check_drawdown_limit(11000.0) is False  # sets peak to 11000
    assert rm.check_drawdown_limit(9000.0) is False   # drawdown = 18.18% < 20%
    assert rm.check_drawdown_limit(8000.0) is True    # drawdown = 27.27% >= 20%

def test_risk_manager_limits_non_advanced():
    rm = RiskManager(mode=RiskMode.BASIC)
    assert rm.check_daily_loss_limit(-10.0) is False
    assert rm.check_drawdown_limit(5000.0) is False

def test_get_max_position_value():
    controls = RiskControls(max_portfolio_exposure_pct=80.0)
    rm = RiskManager(mode=RiskMode.BASIC, controls=controls)

    # cash = 10000, exposure = 10000, total = 20000
    # max exposure = 20000 * 0.8 = 16000
    # remaining = 16000 - 10000 = 6000
    val = rm.get_max_position_value(cash=10000.0, current_exposure=10000.0)
    assert val == 6000.0

    # None mode has no limit
    rm_none = RiskManager(mode=RiskMode.NONE)
    assert rm_none.get_max_position_value(cash=10000.0, current_exposure=10000.0) == 10000.0
