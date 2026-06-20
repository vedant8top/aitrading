# Runtime Test Plan

## Overview

24-hour testnet runtime harness that runs TradingAI continuously on Binance Testnet in SIGNAL_ONLY mode. Collects operational metrics and validates system stability.

## Configuration

| Setting | Value |
|---------|-------|
| MODE | SIGNAL_ONLY |
| Cycle Interval | 5 minutes (300s) |
| Symbols | BTCUSDT, ETHUSDT, BNBUSDT |
| Order Placement | NONE |

## Tracked Metrics

| Metric | Description |
|--------|-------------|
| uptime | Total run duration |
| cycles | Completed scan cycles |
| signals | Signals generated (BUY/SELL/HOLD) |
| failures | Failed cycles |
| memory_usage | Process memory (MB) |
| heartbeat_count | Heartbeats recorded |
| api_errors | API call failures |
| restart_count | Restart events |

## Files

```
src/runtime/
├── runtime_metrics.py     # Metric collection
├── runtime_harness.py     # Core harness (SIGNAL_ONLY)
└── runtime_report.py      # Report generation

docs/runtime_test_plan.md
scripts/validate_runtime_harness.py
```

## Validation

Run 10 accelerated cycles (cycle_interval=0), verify:
1. Metrics recorded
2. Heartbeats recorded
3. State recovery works