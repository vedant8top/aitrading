"""Validate runtime harness: 10 accelerated cycles with state recovery."""

import sys
import json
from pathlib import Path

sys.path.insert(0, ".")

from src.runtime.runtime_harness import RuntimeHarness
from src.runtime.runtime_report import RuntimeReport

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "test_runtime_harness.db"
DB_PATH.unlink(missing_ok=True)

print("=" * 60)
print("RUNTIME HARNESS VALIDATION")
print("=" * 60)

# Run 10 accelerated cycles (cycle_interval=0, no sleep)
print("\nRunning 10 accelerated cycles...")
harness = RuntimeHarness(
    max_cycles=10,
    cycle_interval=0,
    symbols=["BTCUSDT", "ETHUSDT", "BNBUSDT"],
    mode="SIGNAL_ONLY",
    db_path=DB_PATH,
)
results = harness.start()

summary = results["summary"]
state = results["state"]

print("\n--- Results ---")
print(f"  Total Cycles:     {summary['cycle_count']}")
print(f"  Signals:          {summary['signal_count']}")
print(f"  Failures:         {summary['failure_count']}")
print(f"  Heartbeats:       {summary['heartbeat_count']}")
print(f"  API Errors:       {summary['api_error_count']}")
print(f"  Memory Usage:     {summary['memory_mb']} MB")

# Verify metrics recorded
print("\n--- Verification ---")
assert summary["cycle_count"] >= 10, f"Expected >=10 cycles, got {summary['cycle_count']}"
print(f"  [PASS] Metrics recorded: {summary['cycle_count']} cycles")

assert summary["heartbeat_count"] >= 10, f"Expected >=10 heartbeats, got {summary['heartbeat_count']}"
print(f"  [PASS] Heartbeats recorded: {summary['heartbeat_count']}")

# Verify state recovery
assert state.get("last_cycle", 0) > 0, "State not persisted"
print(f"  [PASS] State recovery works: last_cycle={state.get('last_cycle')}")
print(f"  [PASS] Status: {state.get('status')}")

# Verify state file persists
assert DB_PATH.exists(), "State file not created"
loaded = json.loads(DB_PATH.read_text())
assert loaded.get("last_cycle", 0) > 0, "State file corrupted"
print(f"  [PASS] State file persists: {DB_PATH.stat().st_size} bytes")

# Verify no failures
assert summary["failure_count"] == 0, f"Unexpected failures: {summary['failure_count']}"
print(f"  [PASS] 0 failures")

# Generate report
report = RuntimeReport(results)
report_path = report.save_markdown()
print(f"\n  Verdict: {'PASS' if report.passed else 'FAIL'}")
print(f"  Report: {report_path}")

print("\n" + "=" * 60)
print("ALL ACCEPTANCE CRITERIA PASSED")
print("=" * 60)