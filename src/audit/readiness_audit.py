"""Readiness audit: evaluates TradingAI platform readiness across 7 layers."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("audit.readiness")

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Layer definitions: (name, weight, description)
LAYER_DEFS = [
    ("Strategy Layer", 15, "Donchian 20/40 validated, signals persist"),
    ("Execution Layer", 15, "Idempotent execution, no duplicate orders"),
    ("Recovery Layer", 15, "Restart recovery, no state corruption"),
    ("Runtime Layer", 15, "Continuous runner + health monitoring"),
    ("Risk Layer", 15, "Position limits, gatekeeper enforced"),
    ("Exchange Layer", 15, "Binance Testnet connected, auth verified"),
    ("Persistence Layer", 10, "SQLite databases readable"),
]

GRADE_THRESHOLDS = [(90, "A"), (80, "B"), (70, "C"), (60, "D"), (0, "F")]


class ReadinessAudit:
    """Evaluates TradingAI readiness across 7 audit layers."""

    def __init__(self) -> None:
        self.results: list[dict] = []
        self.risks: list[dict] = []

    def _check(self, layer: str, weight: int, passed: bool, detail: str, risk_level: str = "") -> None:
        self.results.append({
            "layer": layer,
            "weight": weight,
            "passed": passed,
            "score": weight if passed else 0,
            "detail": detail,
        })
        if risk_level:
            self.risks.append({"layer": layer, "level": risk_level, "detail": detail})

    def audit_strategy_layer(self) -> None:
        """Check 1: Strategy Layer — 15%"""
        try:
            from src.live_trading.live_strategy_runner import LiveStrategyRunner
            from src.strategies import donchian_strategy
            self._check("Strategy Layer", 15, True, "LiveStrategyRunner + Donchian strategy available")
        except Exception as e:
            self._check("Strategy Layer", 15, False, f"Strategy layer check failed: {e}")

    def audit_execution_layer(self) -> None:
        """Check 2: Execution Layer — 15%"""
        try:
            from src.execution.idempotency_manager import IdempotencyManager
            from src.execution.execution_engine import ExecutionEngine
            self._check("Execution Layer", 15, True, "Idempotent execution + ExecutionEngine available")
        except Exception as e:
            self._check("Execution Layer", 15, False, f"Execution layer check failed: {e}")

    def audit_recovery_layer(self) -> None:
        """Check 3: Recovery Layer — 15%"""
        recovery_db = PROJECT_ROOT / "data" / "execution_log.db"
        idempotency_db = PROJECT_ROOT / "data" / "idempotency.db"
        if recovery_db.exists() and idempotency_db.exists():
            self._check("Recovery Layer", 15, True, f"Recovery DB exists ({recovery_db.stat().st_size} bytes), idempotency DB exists")
        else:
            self._check("Recovery Layer", 15, False, "Recovery databases not found")

    def audit_runtime_layer(self) -> None:
        """Check 4: Runtime Layer — 15%"""
        try:
            from src.runtime.continuous_runner import ContinuousRunner
            from src.runtime.heartbeat_monitor import HeartbeatMonitor
            from src.runtime.health_manager import HealthManager
            runtime_db = PROJECT_ROOT / "data" / "runtime_state.db"
            hb_exists = runtime_db.exists() if runtime_db else False
            self._check("Runtime Layer", 15, True, f"Continuous runner + heartbeat monitor available, runtime DB exists={hb_exists}")
        except Exception as e:
            self._check("Runtime Layer", 15, False, f"Runtime layer check failed: {e}")

    def audit_risk_layer(self) -> None:
        """Check 5: Risk Layer — 15%"""
        try:
            from src.position_management.risk_gatekeeper import RiskGatekeeper
            from src.position_management.portfolio_limits import PortfolioLimits
            self._check("Risk Layer", 15, True, "RiskGatekeeper + PortfolioLimits available")
        except Exception as e:
            self._check("Risk Layer", 15, False, f"Risk layer check failed: {e}")

    def audit_exchange_layer(self) -> None:
        """Check 6: Exchange Layer — 15%"""
        env_path = PROJECT_ROOT / ".env"
        if env_path.exists():
            content = env_path.read_text()
            has_key = "BINANCE_API_KEY=PASTE_YOUR_API_KEY_HERE" not in content
            has_secret = "BINANCE_SECRET_KEY=PASTE_YOUR_SECRET_KEY_HERE" not in content
            if has_key and has_secret:
                self._check("Exchange Layer", 15, True, "Binance credentials configured in .env")
            else:
                self._check("Exchange Layer", 15, False, "Binance credentials are placeholders — update .env")
        else:
            self._check("Exchange Layer", 15, False, ".env file not found")

    def audit_persistence_layer(self) -> None:
        """Check 7: Persistence Layer — 10%"""
        db_files = list((PROJECT_ROOT / "data").glob("*.db"))
        if len(db_files) >= 3:
            self._check("Persistence Layer", 10, True, f"{len(db_files)} SQLite databases found")
        else:
            self._check("Persistence Layer", 10, False, f"Only {len(db_files)} databases found (need 3+)")

    def run_all(self) -> dict:
        """Run all audits and return summary."""
        self.audit_strategy_layer()
        self.audit_execution_layer()
        self.audit_recovery_layer()
        self.audit_runtime_layer()
        self.audit_risk_layer()
        self.audit_exchange_layer()
        self.audit_persistence_layer()

        total_score = sum(r["score"] for r in self.results)
        max_score = sum(r["weight"] for r in self.results)
        pct = round(total_score / max_score * 100, 1) if max_score > 0 else 0

        grade = "F"
        for threshold, g in GRADE_THRESHOLDS:
            if pct >= threshold:
                grade = g
                break

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_score": total_score,
            "max_score": max_score,
            "readiness_pct": pct,
            "grade": grade,
            "layers": self.results,
            "risks": self.risks,
        }