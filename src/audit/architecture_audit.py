"""Architecture audit: checks code structure, modularity, separation of concerns."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger("audit.architecture")

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Expected module structure
EXPECTED_PACKAGES = {
    "src/exchanges": ["__init__.py", "exchange_interface.py", "binance_adapter.py", "binance_market_data.py"],
    "src/execution": ["__init__.py", "execution_models.py", "signal_router.py", "order_manager.py",
                       "execution_engine.py", "idempotency_manager.py", "order_reconciliation.py",
                       "execution_recovery.py"],
    "src/live_trading": ["__init__.py", "market_scanner.py", "signal_scheduler.py",
                          "runner_state.py", "live_strategy_runner.py"],
    "src/runtime": ["__init__.py", "runtime_state.py", "heartbeat_monitor.py",
                     "health_manager.py", "continuous_runner.py", "graceful_shutdown.py"],
    "src/position_management": ["__init__.py", "portfolio_limits.py", "position_manager.py",
                                  "portfolio_snapshot.py", "exposure_tracker.py", "risk_gatekeeper.py"],
    "src/testing": ["__init__.py", "burn_test_metrics.py", "burn_test_runner.py", "burn_test_report.py"],
    "src/audit": ["__init__.py", "readiness_audit.py", "architecture_audit.py", "risk_audit.py"],
}

# Expected docs
EXPECTED_DOCS = [
    "docs/binance_integration_design.md",
    "docs/testnet_execution_design.md",
    "docs/idempotent_execution_design.md",
    "docs/live_strategy_runner_design.md",
    "docs/continuous_runner_design.md",
    "docs/position_management_design.md",
    "docs/burn_test_design.md",
]


class ArchitectureAudit:
    """Checks architecture quality and completeness."""

    def run(self) -> dict:
        """Run architecture audit."""
        checks = []
        score = 0
        max_score = 100

        # 1. Module structure (40 points)
        module_score = 0
        total_modules = sum(len(files) for files in EXPECTED_PACKAGES.values())
        found_modules = 0
        for package, files in EXPECTED_PACKAGES.items():
            pkg_dir = PROJECT_ROOT / package
            for f in files:
                if (pkg_dir / f).exists():
                    found_modules += 1

        module_score = int(found_modules / total_modules * 40)
        score += module_score
        checks.append({
            "check": "Module Structure",
            "passed": found_modules == total_modules,
            "score": module_score,
            "max": 40,
            "detail": f"{found_modules}/{total_modules} files found",
        })

        # 2. Documentation (30 points)
        doc_score = 0
        found_docs = sum(1 for d in EXPECTED_DOCS if (PROJECT_ROOT / d).exists())
        doc_score = int(found_docs / len(EXPECTED_DOCS) * 30)
        score += doc_score
        checks.append({
            "check": "Documentation",
            "passed": found_docs >= 5,
            "score": doc_score,
            "max": 30,
            "detail": f"{found_docs}/{len(EXPECTED_DOCS)} docs found",
        })

        # 3. Separation of concerns (15 points)
        strategy_dir = PROJECT_ROOT / "src" / "strategies"
        execution_dir = PROJECT_ROOT / "src" / "execution"
        risk_dir = PROJECT_ROOT / "src" / "risk_management"
        soc_pass = strategy_dir.exists() and execution_dir.exists() and risk_dir.exists()
        soc_score = 15 if soc_pass else 0
        score += soc_score
        checks.append({
            "check": "Separation of Concerns",
            "passed": soc_pass,
            "score": soc_score,
            "max": 15,
            "detail": "Strategy / Execution / Risk directories exist" if soc_pass else "Missing separate directories",
        })

        # 4. Configuration (15 points)
        configs = PROJECT_ROOT / "configs"
        env_file = PROJECT_ROOT / ".env"
        config_pass = configs.exists() and env_file.exists()
        config_score = 15 if config_pass else 0
        score += config_score
        checks.append({
            "check": "Configuration Management",
            "passed": config_pass,
            "score": config_score,
            "max": 15,
            "detail": f"configs/={configs.exists()}, .env={env_file.exists()}",
        })

        return {
            "audit": "Architecture",
            "total_score": score,
            "max_score": max_score,
            "pct": round(score / max_score * 100, 1),
            "checks": checks,
        }