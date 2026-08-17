from src.risk_management.risk_engine import RiskManager, RiskMode, PercentageStop, TimeStop, ATRStop

def test_risk_manager_stops_property():
    manager_none = RiskManager(mode=RiskMode.NONE)
    assert manager_none.stops == []

    manager_basic = RiskManager(mode=RiskMode.BASIC)
    assert len(manager_basic.stops) == 2
    assert isinstance(manager_basic.stops[0], PercentageStop)
    assert isinstance(manager_basic.stops[1], TimeStop)

    manager_advanced = RiskManager(mode=RiskMode.ADVANCED)
    assert len(manager_advanced.stops) == 2
    assert isinstance(manager_advanced.stops[0], ATRStop)
    assert isinstance(manager_advanced.stops[1], TimeStop)
