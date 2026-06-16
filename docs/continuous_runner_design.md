# Continuous Runner Design

## Overview

The Continuous Runner orchestrates automated scan cycles with health monitoring and restart recovery for uninterrupted operation.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    ContinuousRunner                         │
│                                                             │
│  ┌──────────────────┐  ┌──────────────────┐                │
│  │  LiveStrategy    │  │  Heartbeat       │                │
│  │  Runner          │  │  Monitor         │                │
│  │                  │  │                  │                │
│  │  - signals       │  │  - timestamps    │                │
│  │  - candles       │  │  - memory        │                │
│  │  - prices        │  │  - uptime        │                │
│  └────────┬─────────┘  └────────┬─────────┘                │
│           │                     │                          │
│           └──────────┬──────────┘                          │
│                      │                                     │
│  ┌───────────────────▼──────────────┐  ┌────────────────┐  │
│  │           HealthManager          │  │ Graceful       │  │
│  │                                  │  │ Shutdown       │  │
│  │  HEALTHY / WARNING / CRITICAL    │  │                │  │
│  │  based on heartbeat + failures   │  │ SIGINT/SIGTERM │  │
│  └───────────────────┬──────────────┘  └────────┬───────┘  │
│                      │                          │          │
│                      └──────────┬───────────────┘          │
│                                 │                          │
│  ┌──────────────────────────────▼──────────────┐           │
│  │              RuntimeState                   │           │
│  │              (SQLite)                       │           │
│  │  startup_time, heartbeat, cycles, status    │           │
│  └─────────────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────────┘
```

## Cycle Flow

```
1. ContinuousRunner.start()
   ├── Persist startup_time
   ├── Set status = "STARTING"
   └── Record process_id

2. Loop (every 300s):
   ├── Cycle #N
   │   ├── LiveStrategyRunner.run_once()
   │   ├── HeartbeatMonitor.beat()
   │   ├── RuntimeState.increment_cycle()
   │   ├── HealthManager.assess()
   │   └── Log results
   │
   ├── On success → continue
   ├── On failure → log error, continue
   └── On interrupt → graceful shutdown

3. GracefulShutdown
   ├── Persist final state
   └── Stop runner
```

## Files

```
src/runtime/
├── __init__.py              # Package init
├── runtime_state.py         # SQLite-backed state
├── heartbeat_monitor.py     # Cycle heartbeats
├── health_manager.py        # HEALTHY/WARNING/CRITICAL
├── continuous_runner.py     # Orchestrator
└── graceful_shutdown.py     # Signal handlers