# Position Management Design

## Overview

Portfolio-level trade control framework that evaluates signals before execution. Introduces risk limits, position tracking, exposure monitoring, and a gatekeeper that approves or rejects trades.

## Architecture

```
                    ┌─────────────────────────────┐
                    │         Signal              │
                    │   (BTCUSDT, BUY, 0.001)    │
                    └──────────┬──────────────────┘
                               │
                    ┌──────────▼──────────────────┐
                    │     RiskGatekeeper           │
                    │                              │
                    │  1. SELL? → auto approve     │
                    │  2. Duplicate position?      │
                    │  3. Max positions exceeded?  │
                    │  4. Position value exceeded? │
                    │  5. Total exposure exceeded? │
                    │  6. Daily loss limit?        │
                    │  7. Insufficient balance?    │
                    │                              │
                    │  → GateDecision              │
                    │    APPROVED / REJECTED       │
                    │    + reason                  │
                    └──────────┬──────────────────┘
                               │
                    ┌──────────▼──────────────────┐
                    │      PositionManager         │
                    │      (SQLite persistence)   │
                    │  - open/close/update         │
                    │  - P&L tracking              │
                    └──────────┬──────────────────┘
                               │
                    ┌──────────▼──────────────────┐
                    │      ExposureTracker         │
                    │  - per-symbol exposure       │
                    │  - concentration risk (HHI)  │
                    └──────────┬──────────────────┘
                               │
                    ┌──────────▼──────────────────┐
                    │     PortfolioSnapshot        │
                    │  - total equity              │
                    │  - cash                      │
                    │  - exposure                  │
                    │  - unrealized/realized P&L   │
                    └─────────────────────────────┘
```

## Risk Limits (Defaults)

| Limit | Value |
|-------|-------|
| Max open positions | 3 |
| Max position value | 100 USDT |
| Max total exposure | 300 USDT |
| Max daily loss | 2% or 50 USDT |
| Max symbol exposure | 40% |
| Min order value | 10 USDT |

## Gatekeeper Decision Flow

```
Signal → Gatekeeper.evaluate()
  │
  ├─ SELL → APPROVED (always)
  │
  ├─ Duplicate? → REJECTED (duplicate_position)
  │
  ├─ Max positions? → REJECTED (max_positions_exceeded)
  │
  ├─ Position value > max? → REJECTED (position_value_exceeded)
  │
  ├─ Total exposure > max? → REJECTED (total_exposure_exceeded)
  │
  ├─ Daily loss > limit? → REJECTED (daily_loss_exceeded)
  │
  ├─ Balance < value? → REJECTED (insufficient_balance)
  │
  └─ All pass → APPROVED (all_checks_passed)
```

## Files

```
src/position_management/
├── __init__.py              # Package init
├── portfolio_limits.py      # Configurable risk limits
├── position_manager.py      # Position tracking + SQLite
├── portfolio_snapshot.py    # Portfolio state summary
├── exposure_tracker.py      # Exposure + concentration risk
└── risk_gatekeeper.py       # APPROVED/REJECTED gate

docs/position_management_design.md
```

## Validation

Run: `.venv\Scripts\python.exe scripts/validate_position_management.py`

Tests:
1. Approved BUY
2. Duplicate BUY rejection
3. Max position rejection
4. Exposure rejection
5. Daily loss rejection
6. Portfolio snapshot generation