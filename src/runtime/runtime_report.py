"""Runtime report: generates runtime test report from harness results."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("runtime.harness.report")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORT_PATH = PROJECT_ROOT / "docs" / "runtime_test_report.md"


class RuntimeReport:
    """Generates report from RuntimeHarness results."""

    def __init__(self, results: dict) -> None:
        self.results = results

    @property
    def passed(self) -> bool:
        summary = self.results.get("summary", {})
        return (
            summary.get("cycle_count", 0) > 0
            and summary.get("failure_count", 0) == 0
            and summary.get("heartbeat_count", 0) > 0
        )

    def save_markdown(self, path: Optional[Path] = None) -> Path:
        path = path or DEFAULT_REPORT_PATH
        summary = self.results.get("summary", {})
        state = self.results.get("state", {})
        verdict = "PASS" if self.passed else "FAIL"

        md = f"""# Runtime Harness Test Report

**Date**: {datetime.now(timezone.utc).isoformat()}
**Verdict**: **{verdict}**
**Mode**: {self.results.get('mode', 'SIGNAL_ONLY')}
**Symbols**: {', '.join(self.results.get('symbols', []))}

---

## Summary

| Metric | Value |
|--------|-------|
| Total Cycles | {summary.get('cycle_count', 0)} |
| Signals | {summary.get('signal_count', 0)} |
| Failures | {summary.get('failure_count', 0)} |
| Heartbeats | {summary.get('heartbeat_count', 0)} |
| API Errors | {summary.get('api_error_count', 0)} |
| Restarts | {summary.get('restart_count', 0)} |
| Uptime | {summary.get('uptime_s', 0):.1f}s |
| Memory | {summary.get('memory_mb', 0):.1f} MB |

## State

| Key | Value |
|-----|-------|
| Last Cycle | {state.get('last_cycle', 0)} |
| Status | {state.get('status', 'N/A')} |
| Start Time | {state.get('start_time', 'N/A')} |
| Stop Time | {state.get('stop_time', 'N/A')} |

## Acceptance Criteria

| Criterion | Result |
|-----------|--------|
| Metrics recorded | {'PASS' if summary.get('cycle_count', 0) > 0 else 'FAIL'} |
| Heartbeats recorded | {'PASS' if summary.get('heartbeat_count', 0) > 0 else 'FAIL'} |
| State recovery works | {'PASS' if state.get('last_cycle', 0) > 0 else 'FAIL'} |
| 0 failures | {'PASS' if summary.get('failure_count', 0) == 0 else 'FAIL'} |

## Conclusion

{'All tests passed. Runtime harness is stable under continuous operation.' if self.passed else 'One or more tests failed.'}
"""

        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(md)
        return path