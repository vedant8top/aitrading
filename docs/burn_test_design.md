# Burn Test Design

## Overview

Multi-day burn test framework that stress tests the entire TradingAI platform by simulating 100+ trading cycles with fault injection.

## Architecture

```
┌──────────────────────────────────────────────────┐
│              BurnTestRunner                      │
│                                                  │
│  1. Generate signal (BTC/ETH/BNB, BUY/SELL/HOLD)│
│  2. Run through pipeline                         │
│     - Idempotency check                         │
│     - Risk gatekeeper                            │
│     - Position manager                           │
│     - Order execution                            │
│  3. Record metrics                               │
│  4. Inject faults at scheduled cycles            │
│     - API failure at cycle 25                    │
│     - DB failure at cycle 50                     │
│     - Timeout at cycle 75                        │
│     - Restart at cycle 50                        │
└───────────────────────┬──────────────────────────┘
                        │
┌───────────────────────▼──────────────────────────┐
│          BurnTestMetrics                         │
│                                                  │
│  Per cycle: count, success, signals, orders     │
│  Hourly aggregation                              │
│  Daily aggregation                               │
└───────────────────────┬──────────────────────────┘
                        │
┌───────────────────────▼──────────────────────────┐
│          BurnTestReport                          │
│                                                  │
│  Verdict: PASS or FAIL                           │
│  Acceptance criteria:                            │
│  - 0 duplicate orders                            │
│  - 0 corrupted state                             │
│  - Recovery works (recovery_successes >= 1)      │
└──────────────────────────────────────────────────┘
```

## Tracked Metrics

| Metric | Description |
|--------|-------------|
| cycle_count | Total cycles executed |
| signal_count | Total signals generated |
| order_count | Total orders placed |
| duplicate_orders | Orders with same client_order_id |
| duplicate_signals | Duplicate signals detected |
| api_failures | API call failures |
| db_failures | Database write failures |
| restarts | Restart/recovery events |
| memory_mb | Process memory usage |
| uptime_s | Test duration |

## Fault Injection Schedule

| Cycle | Event |
|-------|-------|
| 25 | API failure |
| 50 | DB failure + restart |
| 75 | Timeout |

## Files

```
src/testing/
├── __init__.py
├── burn_test_metrics.py    # Metric collection
├── burn_test_runner.py     # Core orchestrator
└── burn_test_report.py     # Report generation

docs/burn_test_design.md
scripts/validate_burn_test.py
```

## Acceptance Criteria

| Criterion | Required |
|-----------|----------|
| 0 duplicate orders | Yes |
| 0 corrupted state | Yes |
| Recovery works | Yes |
| Failure handling | Yes |