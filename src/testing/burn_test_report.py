"""Burn test report: generates pass/fail verdict from burn test results."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("testing.report")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORT_PATH = PROJECT_ROOT / "docs" / "burn_test_report.md"


class BurnTestReport:
    """Generates a pass/fail report from burn test results."""

    def __init__(self, results: dict) -> None:
        self.results = results
        self.db_path = DEFAULT_REPORT_PATH

    @property
    def passed(self) -> bool:
        """Check if all acceptance criteria are met."""
        return (
            self.results["duplicate_orders"] == 0
            and self.results["state_corrupted"] == False
            and self.results["recovery_successes"] >= 1
        )

    def generate(self) -> dict:
        """Generate the full report."""
        verdict = "PASS" if self.passed else "FAIL"
        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "verdict": verdict,
            "summary": {
                "total_cycles": self.results["total_cycles"],
                "total_signals": self.results["total_signals"],
                "total_orders": self.results["total_orders"],
                "duplicate_orders": self.results["duplicate_orders"],
                "duplicate_signals": self.results["duplicate_signals"],
            },
            "failures": {
                "api_failures": self.results["api_failures"],
                "db_failures": self.results["db_failures"],
                "restarts": self.results["restarts"],
                "recovery_successes": self.results["recovery_successes"],
                "recovery_rate": self.results["recovery_rate"],
            },
            "performance": {
                "uptime_s": self.results["uptime_s"],
                "memory_mb": self.results["memory_mb"],
                "state_corrupted": self.results["state_corrupted"],
            },
            "hourly": self.results.get("hourly", {}),
            "daily": self.results.get("daily", {}),
            "acceptance": {
                "zero_duplicate_orders": self.results["duplicate_orders"] == 0,
                "no_state_corruption": self.results["state_corrupted"] == False,
                "recovery_works": self.results["recovery_successes"] >= 1,
            },
        }
        return report

    def save_markdown(self, path: Optional[Path] = None) -> Path:
        """Save report as markdown file."""
        path = path or DEFAULT_REPORT_PATH
        report = self.generate()
        verdict = report["verdict"]
        acc = report["acceptance"]

        md = f"""# Burn Test Report

**Date**: {report['timestamp']}
**Verdict**: **{verdict}**

---

## Summary

| Metric | Value |
|--------|-------|
| Total Cycles | {report['summary']['total_cycles']} |
| Total Signals | {report['summary']['total_signals']} |
| Total Orders | {report['summary']['total_orders']} |
| Duplicate Orders | {report['summary']['duplicate_orders']} |
| Duplicate Signals | {report['summary']['duplicate_signals']} |

## Failures Injected

| Event | Count |
|-------|-------|
| API Failures | {report['failures']['api_failures']} |
| DB Failures | {report['failures']['db_failures']} |
| Restarts | {report['failures']['restarts']} |
| Recovery Successes | {report['failures']['recovery_successes']} |
| Recovery Rate | {report['failures']['recovery_rate']:.0f}% |

## Performance

| Metric | Value |
|--------|-------|
| Uptime | {report['performance']['uptime_s']:.1f}s |
| Memory Usage | {report['performance']['memory_mb']:.1f} MB |
| State Corrupted | {report['performance']['state_corrupted']} |

## Acceptance Criteria

| Criterion | Result |
|-----------|--------|
| 0 duplicate orders | {'PASS' if acc['zero_duplicate_orders'] else 'FAIL'} |
| 0 corrupted state | {'PASS' if acc['no_state_corruption'] else 'FAIL'} |
| Recovery works | {'PASS' if acc['recovery_works'] else 'FAIL'} |

## Conclusion

{'All acceptance criteria met. Platform is stable under stress.' if self.passed else 'One or more acceptance criteria failed. Review and fix.'}
"""

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(md)

        return path