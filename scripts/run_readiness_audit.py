"""Run TradingAI readiness audit and generate final report."""

import sys
from pathlib import Path

sys.path.insert(0, ".")

from src.audit.readiness_audit import ReadinessAudit
from src.audit.architecture_audit import ArchitectureAudit
from src.audit.risk_audit import RiskAudit

print("=" * 60)
print("TRADINGAI READINESS AUDIT")
print("=" * 60)

# 1. Run 7-layer readiness audit
print("\n--- 7-Layer Readiness Audit ---")
readiness = ReadinessAudit()
readiness_result = readiness.run_all()

for layer in readiness_result["layers"]:
    status = "PASS" if layer["passed"] else "FAIL"
    print(f"  [{status}] {layer['layer']}: {layer['detail']} ({layer['score']}/{layer['weight']})")

print(f"\n  Readiness Score: {readiness_result['readiness_pct']}%")
print(f"  Grade: {readiness_result['grade']}")

# 2. Run architecture audit
print("\n--- Architecture Audit ---")
arch = ArchitectureAudit()
arch_result = arch.run()
for check in arch_result["checks"]:
    status = "PASS" if check["passed"] else "FAIL"
    print(f"  [{status}] {check['check']}: {check['detail']} ({check['score']}/{check['max']})")
print(f"  Architecture Score: {arch_result['pct']}%")

# 3. Run risk audit
print("\n--- Risk Audit ---")
risk = RiskAudit()
risk_result = risk.run()
for check in risk_result["checks"]:
    status = "PASS" if check["passed"] else "FAIL"
    print(f"  [{status}] {check['check']}: {check['detail']} ({check['score']}/{check['max']})")
print(f"  Risk Score: {risk_result['pct']}%")

if risk_result.get("risks"):
    print("\n  Risks:")
    for r in risk_result["risks"]:
        print(f"    [{r['level'].upper()}] {r['detail']}")

# 4. Overall summary
overall = round((readiness_result["readiness_pct"] + arch_result["pct"] + risk_result["pct"]) / 3, 1)
grade = "F"
for threshold, g in [(90, "A"), (80, "B"), (70, "C"), (60, "D")]:
    if overall >= threshold:
        grade = g
        break

print(f"\n{'='*60}")
print(f"OVERALL READINESS SCORE: {overall}% — Grade: {grade}")
print(f"{'='*60}")

# 5. Recommendations
print("\n--- Recommendations ---")
if overall >= 80:
    print("  TESTNET READY: YES")
else:
    print("  TESTNET READY: PARTIAL — review failing checks")

if overall >= 90:
    print("  REAL MONEY READY: YES (with additional monitoring)")
elif overall >= 80:
    print("  REAL MONEY READY: NOT YET — add monitoring before live")
else:
    print("  REAL MONEY READY: NO — address critical issues first")

# Missing controls
missing = []
if not risk_result["checks"][3]["passed"]:
    missing.append("heartbeat monitoring")
if not risk_result["checks"][4]["passed"]:
    missing.append("health status tracking")
if missing:
    print(f"  MISSING CONTROLS: {', '.join(missing)}")
else:
    print("  MISSING CONTROLS: None")

print("  MISSING MONITORING: Add Prometheus/Grafana before live trading")

print(f"\n{'='*60}")
print("AUDIT COMPLETE")
print(f"{'='*60}")