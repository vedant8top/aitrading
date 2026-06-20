"""Validate burn test framework: 100 cycles with fault injection."""

import sys
from pathlib import Path

sys.path.insert(0, ".")

from src.testing.burn_test_runner import BurnTestRunner
from src.testing.burn_test_report import BurnTestReport

print("=" * 60)
print("BURN TEST VALIDATION")
print("=" * 60)

# Run 100 cycles with fault injection at cycles 25, 50, 75
runner = BurnTestRunner(
    max_cycles=100,
    failure_injection_cycles=[50, 75],
    restart_cycle=50,
    api_failure_cycle=25,
    timeout_cycle=75,
)

print("\nRunning 100 cycles with fault injection...")
results = runner.run()

print("\n--- Results ---")
for key in ["total_cycles", "total_signals", "total_orders", "duplicate_orders",
            "api_failures", "db_failures", "restarts", "recovery_successes",
            "memory_mb", "state_corrupted"]:
    print(f"  {key}: {results[key]}")

# Verify acceptance criteria
print("\n--- Acceptance Criteria ---")
assert results["duplicate_orders"] == 0, f"Duplicate orders: {results['duplicate_orders']}"
print("  [PASS] 0 duplicate orders")

assert results["state_corrupted"] == False, "State corrupted"
print("  [PASS] 0 corrupted state")

assert results["recovery_successes"] >= 1, "Recovery not demonstrated"
print(f"  [PASS] Recovery works ({results['recovery_successes']} restarts recovered)")

assert results["api_failures"] >= 1, "API failure not injected"
print(f"  [PASS] API failures handled ({results['api_failures']})")

assert results["restarts"] >= 1, "Restart not executed"
print(f"  [PASS] Restart executed ({results['restarts']})")

assert results["total_cycles"] >= 99, f"Expected ~100, got {results['total_cycles']}"
print(f"  [PASS] {results['total_cycles']} cycles executed (timeout/skip excluded)")

# Generate report
report = BurnTestReport(results)
verdict = "PASS" if report.passed else "FAIL"
print(f"\n  Verdict: {verdict}")
assert report.passed, "Burn test FAILED"

report_path = report.save_markdown()
print(f"  Report saved: {report_path}")

# Print hourly summary
hourly = results.get("hourly", {})
if hourly:
    print(f"\n  Hourly windows: {len(hourly)}")

print("\n" + "=" * 60)
print("ALL ACCEPTANCE CRITERIA PASSED")
print("=" * 60)