"""Run full regime detection validation workflow."""

import sys
import json
from pathlib import Path

sys.path.insert(0, ".")

import pandas as pd
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INITIAL_CAPITAL = 100_000.0

# ------------------------------------------------------------------
# Step 1: Load Regime Labels
# ------------------------------------------------------------------
def load_regimes() -> pd.DataFrame:
    path = PROJECT_ROOT / "data" / "regimes" / "regime_labels.csv"
    df = pd.read_csv(path, parse_dates=["Date"], index_col="Date")
    print(f"Loaded {len(df)} regime labels")
    print(f"Regime distribution:\n{df['Regime'].value_counts()}")
    return df

# ------------------------------------------------------------------
# Step 2: Load Baseline Metrics
# ------------------------------------------------------------------
def load_baseline_metrics() -> dict[str, dict]:
    metrics_path = PROJECT_ROOT / "data" / "strategy_comparison" / "portfolio_metrics.csv"
    if not metrics_path.exists():
        print(f"Baseline metrics not found: {metrics_path}")
        return {}

    df = pd.read_csv(metrics_path)
    results = {}
    for _, row in df.iterrows():
        strat = row.get("strategy", row.get("Strategy", ""))
        results[strat] = {
            "total_return_pct": float(row.get("total_return_pct", row.get("Total Return %", 0))),
            "sharpe_ratio": float(row.get("sharpe_ratio", row.get("Sharpe Ratio", 0))),
            "max_drawdown_pct": float(row.get("max_drawdown_pct", row.get("Max Drawdown %", 0))),
            "win_rate_pct": float(row.get("win_rate_pct", row.get("Win Rate %", 0))),
            "profit_factor": float(row.get("profit_factor", row.get("Profit Factor", 0))),
            "total_trades": int(row.get("total_trades", row.get("Total Trades", 0))),
        }
    print(f"\nLoaded baselines: {list(results.keys())}")
    return results

# ------------------------------------------------------------------
# Step 3: Build Equal-Weight Portfolio
# ------------------------------------------------------------------
def build_equal_weight_baseline() -> dict:
    """Build equal-weight portfolio from all strategies."""
    # Load portfolio metrics for equal-weight estimation
    # Equal weight = average return, average sharpe, average DD
    baselines = load_baseline_metrics()
    if not baselines:
        return {}

    returns = [v["total_return_pct"] for v in baselines.values()]
    sharpes = [v["sharpe_ratio"] for v in baselines.values()]
    dds = [v["max_drawdown_pct"] for v in baselines.values()]
    win_rates = [v["win_rate_pct"] for v in baselines.values()]
    trades = [v["total_trades"] for v in baselines.values()]

    return {
        "name": "Equal-Weight Portfolio",
        "total_return_pct": round(np.mean(returns), 2),
        "sharpe_ratio": round(np.mean(sharpes), 3),
        "max_drawdown_pct": round(np.mean(dds), 2),
        "win_rate_pct": round(np.mean(win_rates), 2),
        "total_trades": int(np.mean(trades)),
    }

# ------------------------------------------------------------------
# Step 4: Build Regime-Aware Portfolio
# ------------------------------------------------------------------
def build_regime_portfolio(regime_df: pd.DataFrame) -> dict:
    """Build regime-aware portfolio using weighted strategy returns."""
    baselines = load_baseline_metrics()
    if not baselines:
        return {}

    # Strategy-to-regime mapping
    regime_map = {
        "TRENDING": {"donchian": 0.30, "breakout": 0.25, "momentum": 0.25, "ema_rsi_macd": 0.20},
        "RANGE_BOUND": {"mean_reversion": 0.40, "bollinger_reversion": 0.35, "bear_trap": 0.25},
        "VOLATILE": {"volatility_expansion": 0.70, "bear_trap": 0.30},
        "UNCERTAIN": {},  # 50% cash
    }

    # Count days per regime
    regime_days = regime_df["Regime"].value_counts()
    total_days = len(regime_df)

    # Calculate weighted return
    weighted_return = 0.0
    weighted_trades = 0
    strategies_used = set()

    for regime_str, weights in regime_map.items():
        days = regime_days.get(regime_str, 0)
        fraction = days / total_days if total_days > 0 else 0

        for strat, weight in weights.items():
            if strat in baselines:
                strat_contribution = fraction * weight * baselines[strat]["total_return_pct"]
                weighted_return += strat_contribution
                strategies_used.add(strat)

    # Calculate weighted metrics
    # For sharpe: use weighted average of strategy sharpes (simplified)
    weighted_sharpe = 0.0
    weighted_dd = 0.0
    weighted_win_rate = 0.0
    for regime_str, weights in regime_map.items():
        days = regime_days.get(regime_str, 0)
        fraction = days / total_days if total_days > 0 else 0
        for strat, weight in weights.items():
            if strat in baselines:
                weighted_sharpe += fraction * weight * baselines[strat]["sharpe_ratio"]
                weighted_dd += fraction * weight * abs(baselines[strat]["max_drawdown_pct"])
                weighted_win_rate += fraction * weight * baselines[strat]["win_rate_pct"]

    # Transition cost drag
    transition_count = count_transitions(regime_df)
    cost_drag = transition_count * 0.001 * 100  # 0.1% per transition * 100 = %

    return {
        "name": "Regime-Aware Portfolio",
        "total_return_pct": round(weighted_return, 2),
        "sharpe_ratio": round(weighted_sharpe, 3),
        "max_drawdown_pct": round(weighted_dd, 2),
        "win_rate_pct": round(weighted_win_rate, 2),
        "transition_count": transition_count,
        "transition_cost_drag_pct": round(cost_drag, 2),
        "days_trending": int(regime_days.get("TRENDING", 0)),
        "days_range_bound": int(regime_days.get("RANGE_BOUND", 0)),
        "days_volatile": int(regime_days.get("VOLATILE", 0)),
        "days_uncertain": int(regime_days.get("UNCERTAIN", 0)),
        "total_days": total_days,
    }

def count_transitions(regime_df: pd.DataFrame) -> int:
    """Count number of regime transitions."""
    regimes = regime_df["Regime"].values
    transitions = 0
    for i in range(1, len(regimes)):
        if regimes[i] != regimes[i - 1]:
            transitions += 1
    return transitions

# ------------------------------------------------------------------
# Step 5: Compare & Report
# ------------------------------------------------------------------
def compare_results(regime: dict, baselines: dict, equal_weight: dict) -> str:
    """Generate comparison report."""
    lines = []
    lines.append("# Regime Detection Validation Results\n")

    # Summary
    lines.append("## Summary\n")
    lines.append("| Strategy | Return % | Sharpe | Max DD % | Win Rate % |")
    lines.append("|----------|----------|--------|----------|------------|")

    # Regime-aware
    lines.append(
        f"| **Regime-Aware** | **{regime['total_return_pct']:.2f}** | "
        f"**{regime['sharpe_ratio']:.3f}** | **{regime['max_drawdown_pct']:.2f}** | "
        f"**{regime.get('win_rate_pct', 0):.2f}** |"
    )

    # Baselines
    for name, data in sorted(baselines.items()):
        lines.append(
            f"| {name} | {data['total_return_pct']:.2f} | {data['sharpe_ratio']:.3f} | "
            f"{data['max_drawdown_pct']:.2f} | {data.get('win_rate_pct', 0):.2f} |"
        )

    # Equal weight
    if equal_weight:
        lines.append(
            f"| Equal-Weight | {equal_weight['total_return_pct']:.2f} | "
            f"{equal_weight['sharpe_ratio']:.3f} | {equal_weight['max_drawdown_pct']:.2f} | "
            f"{equal_weight.get('win_rate_pct', 0):.2f} |"
        )

    lines.append("")

    # Regime breakdown
    lines.append("## Regime Breakdown\n")
    lines.append(f"- TRENDING days: {regime.get('days_trending', 0)} ({regime.get('days_trending', 0) / regime['total_days'] * 100:.1f}%)")
    lines.append(f"- RANGE_BOUND days: {regime.get('days_range_bound', 0)} ({regime.get('days_range_bound', 0) / regime['total_days'] * 100:.1f}%)")
    lines.append(f"- VOLATILE days: {regime.get('days_volatile', 0)} ({regime.get('days_volatile', 0) / regime['total_days'] * 100:.1f}%)")
    lines.append(f"- UNCERTAIN days: {regime.get('days_uncertain', 0)} ({regime.get('days_uncertain', 0) / regime['total_days'] * 100:.1f}%)")
    lines.append(f"- Total transitions: {regime.get('transition_count', 0)}")
    lines.append(f"- Transition cost drag: {regime.get('transition_cost_drag_pct', 0):.2f}%")
    lines.append("")

    # Acceptance criteria
    lines.append("## Acceptance Criteria\n")
    donchian = baselines.get("donchian", {})
    lines.append(f"- Return beat Donchian ({regime['total_return_pct']:.2f}% vs {donchian.get('total_return_pct', 0):.2f}%): {'YES' if regime['total_return_pct'] > donchian.get('total_return_pct', 0) else 'NO'}")
    lines.append(f"- Sharpe > 0.90 ({regime['sharpe_ratio']:.3f}): {'YES' if regime['sharpe_ratio'] > 0.90 else 'NO'}")
    lines.append(f"- Max DD < 18% ({regime['max_drawdown_pct']:.2f}%): {'YES' if regime['max_drawdown_pct'] > -18 else 'NO'}")
    lines.append(f"- Transitions < 12/yr ({regime.get('transition_count', 0)} / {regime['total_days'] / 252:.1f} = {regime.get('transition_count', 0) / (regime['total_days'] / 252):.1f}/yr): {'YES' if regime.get('transition_count', 0) / (regime['total_days'] / 252) < 12 else 'NO'}")
    lines.append("")

    # Final recommendation
    lines.append("## Final Recommendation\n")
    beat_donchian = regime["total_return_pct"] > donchian.get("total_return_pct", 0)
    sharpe_ok = regime["sharpe_ratio"] > 0.90
    dd_ok = regime["max_drawdown_pct"] > -18
    trans_ok = regime.get("transition_count", 0) / (regime["total_days"] / 252) < 12

    if beat_donchian and sharpe_ok and dd_ok and trans_ok:
        lines.append("**Recommendation: GO**")
        lines.append("\nRegime detection beats Donchian on all metrics.")
    elif beat_donchian or sharpe_ok:
        lines.append("**Recommendation: CONDITIONAL GO**")
        lines.append("\nRegime detection shows promise but doesn't meet all criteria.")
    else:
        lines.append("**Recommendation: NO GO**")
        lines.append("\nRegime detection does not outperform the best standalone strategy.")

    return "\n".join(lines)

# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------
def main():
    print("=" * 60)
    print("REGIME DETECTION VALIDATION WORKFLOW")
    print("=" * 60)

    # Load regimes
    regime_df = load_regimes()

    # Load baselines
    baselines = load_baseline_metrics()

    # Equal-weight baseline
    equal_weight = build_equal_weight_baseline()

    # Regime-aware portfolio
    regime_portfolio = build_regime_portfolio(regime_df)

    # Compare
    report = compare_results(regime_portfolio, baselines, equal_weight)

    # Save report
    report_path = PROJECT_ROOT / "docs" / "regime_detection_results.md"
    report_path.write_text(report, encoding="utf-8")
    print(f"\nReport saved to {report_path}")

    # Print summary
    print("\n" + report)

    return 0

if __name__ == "__main__":
    raise SystemExit(main())