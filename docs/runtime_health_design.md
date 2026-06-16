# Runtime Health Design

## Overview

Health monitoring framework that generates system status based on heartbeat freshness and failure rates.

## Health States

```
HEALTHY ──(heartbeat > 10 min)──────▶ WARNING
HEALTHY ──(failure rate > 5%)───────▶ WARNING
WARNING ──(heartbeat > 30 min)──────▶ CRITICAL
WARNING ──(failure rate > 20%)──────▶ CRITICAL
* ────────(recovery)────────────────▶ HEALTHY
```

## Decision Matrix

| Condition | Status |
|-----------|--------|
| heartbeat < 10 min AND failure rate < 5% | HEALTHY |
| heartbeat > 10 min OR failure rate > 5% | WARNING |
| heartbeat > 30 min OR failure rate > 20% | CRITICAL |

## Components

### HeartbeatMonitor
- Records timestamp, status, cycle number, memory, uptime
- Persists to `runtime_state.db` (heartbeats table)

### HealthManager
- Queries latest heartbeat
- Reads cycle counts from RuntimeState
- Computes failure rate
- Returns HEALTHY / WARNING / CRITICAL

### RuntimeState
- Persists startup_time, last_heartbeat, cycle_count, successful_cycles, failed_cycles, current_status

## Health History

Each health assessment is recorded in memory:
```python
{
    "timestamp": "2026-06-16T22:00:00+00:00",
    "status": "HEALTHY",
    "seconds_since_heartbeat": 120.0,
    "failure_rate": 0.0,
    "total_cycles": 3,
    "failed_cycles": 0
}
```

## Files

```
src/runtime/
├── heartbeat_monitor.py    # Cycle-level heartbeat tracking
├── health_manager.py       # HEALTHY/WARNING/CRITICAL assessment
├── runtime_state.py        # SQLite state persistence
└── continuous_runner.py    # Integration with health checks
```

## SQLite Schema

```sql
-- Runtime state key-value store
CREATE TABLE runtime_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Heartbeat history
CREATE TABLE heartbeats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    status TEXT NOT NULL,
    cycle_number INTEGER,
    memory_mb REAL,
    uptime_seconds REAL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

## Recovery

On restart:
1. RuntimeState reads persisted values
2. HeartbeatMonitor reads latest heartbeat
3. HealthManager assesses current status
4. ContinuousRunner resumes from persisted state