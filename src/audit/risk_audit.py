"""Risk audit: assesses operational and trading risk controls."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger("audit.risk")

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class RiskAudit:
    """Assesses operational and trading risk controls."""

    def run(self) -> dict:
        checks = []
        score = 0
        max_score = 100

        # 1. Position limits (20 points)
        limits_file = PROJECT_ROOT / "src" / "position_management" / "portfolio_limits.py"
        limits_pass = limits_file.exists()
        checks.append({
            "check": "Position Limits Defined",
            "passed": limits_pass,
            "score": 20 if limits_pass else 0,
            "max": 20,
            "detail": "PortfolioLimits dataclass exists" if limits_pass else "Missing portfolio limits",
        })
        score += 20 if limits_pass else 0

        # 2. Risk gatekeeper (20 points)
        gk_file = PROJECT_ROOT / "src" / "position_management" / "risk_gatekeeper.py"
        gk_pass = gk_file.exists()
        checks.append({
            "check": "Risk Gatekeeper",
            "passed": gk_pass,
            "score": 20 if gk_pass else 0,
            "max": 20,
            "detail": "RiskGatekeeper class exists" if gk_pass else "Missing risk gatekeeper",
        })
        score += 20 if gk_pass else 0

        # 3. Idempotent execution (20 points)
        idem_file = PROJECT_ROOT / "src" / "execution" / "idempotency_manager.py"
        idem_pass = idem_file.exists()
        checks.append({
            "check": "Idempotent Execution",
            "passed": idem_pass,
            "score": 20 if idem_pass else 0,
            "max": 20,
            "detail": "IdempotencyManager exists" if idem_pass else "Missing idempotency manager",
        })
        score += 20 if idem_pass else 0

        # 4. Heartbeat monitoring (20 points)
        hb_file = PROJECT_ROOT / "src" / "runtime" / "heartbeat_monitor.py"
        hb_pass = hb_file.exists()
        checks.append({
            "check": "Heartbeat Monitoring",
            "passed": hb_pass,
            "score": 20 if hb_pass else 0,
            "max": 20,
            "detail": "HeartbeatMonitor exists" if hb_pass else "Missing heartbeat monitor",
        })
        score += 20 if hb_pass else 0

        # 5. Health manager (20 points)
        hm_file = PROJECT_ROOT / "src" / "runtime" / "health_manager.py"
        hm_pass = hm_file.exists()
        checks.append({
            "check": "Health Manager",
            "passed": hm_pass,
            "score": 20 if hm_pass else 0,
            "max": 20,
            "detail": "HealthManager exists" if hm_pass else "Missing health manager",
        })
        score += 20 if hm_pass else 0

        risks = []
        if not idem_pass:
            risks.append({"level": "critical", "detail": "No idempotent execution — duplicate orders possible"})
        if not gk_pass:
            risks.append({"level": "critical", "detail": "No risk gatekeeper — no trade-level protection"})
        if not hb_pass:
            risks.append({"level": "medium", "detail": "No heartbeat monitoring — silent failures possible"})
        if not hm_pass:
            risks.append({"level": "medium", "detail": "No health manager — no health status tracking"})

        return {
            "audit": "Risk",
            "total_score": score,
            "max_score": max_score,
            "pct": round(score / max_score * 100, 1),
            "checks": checks,
            "risks": risks,
        }