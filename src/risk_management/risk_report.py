"""Risk management comparison report generator."""

from __future__ import annotations

import argparse
import logging
import math
import shutil
import tempfile
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pandas as pd

from src.backtesting.backtest_engine import PortfolioBacktester, Trade
from src.strategies.strategy_registry import StrategyRegistry


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SIGNAL_DIR = PROJECT_ROOT / "data" / "signals"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "risk_comparison"
DEFAULT_REPORT_PATH = PROJECT_ROOT / "docs" / "risk_management_framework.md"
DEFAULT_LOG_PATH = PROJECT_ROOT / "logs" / "risk_report.log"
INITIAL_CAPITAL = 100_000.0
POSITION_SIZE = 0.10
BROKERAGE_RATE = 0.0005
SLIPPAGE_RATE = 0.0005
TRADING_DAYS_PER_YEAR = 252


def configure_logging(log_path: Path) -> logging.Logger:
    """Configure console and rotating file logging."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("risk_report")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )
    file_handler = RotatingFileHandler(
        log_path, maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger


def generate_signals_for_strategy(
    strategy_name: str, input_dir: Path, output_dir: Path, logger: logging.Logger
) -> Path | None:
    """Generate signal files for a single strategy and return temp dir path."""
    from src.strategies.signal_engine import SignalEngine

    strategy_class = StrategyRegistry.get_strategy(strategy_name)
    strategy = strategy_class()

    indicator_files = sorted(input_dir.glob("*_indicators.csv"))
    if not indicator_files:
        logger.error("No indicator files found in %s", input_dir)
        return None

    temp_dir = Path(tempfile.mkdtemp(prefix=f"signals_{strategy_name}_"))
    engine = SignalEngine(temp_dir, logger, strategy=strategy)

    for csv_path in indicator_files:
        result = engine.process_file(csv_path)
        if result.status != "success":
            logger.warning("Signal generation failed for %s: %s", csv_path.stem, result.error)

    return temp_dir


def run_backtest(
    signal_dir: Path,
    risk_mode: str,
    output_dir: Path,
    logger: logging.Logger,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Run backtest in a specific risk mode and return results."""
    mode_dir = output_dir / risk_mode
    mode_dir.mkdir(parents=True, exist_ok=True)

    backtester = PortfolioBacktester(
        initial_capital=INITIAL_CAPITAL,
        position_size=POSITION_SIZE,
        brokerage_rate=BROKERAGE_RATE,
        slippage_rate=SLIPPAGE_RATE,
        logger=logger,
        risk_mode=risk_mode,
    )
    datasets = backtester.load_signal_files(signal_dir)
    trades, equity, metrics = backtester.run(datasets)

    # Save results
    trades.to_csv(mode_dir / "trades.csv", index=False)
    equity.to_csv(mode_dir / "equity_curve.csv", index=False, date_format="%Y-%m-%d")

    return trades, equity, metrics


def compute_comparison(
    results: dict[str, dict],
) -> list[dict]:
    """Build comparison rows for the markdown table."""
    rows = []
    modes = ["none", "basic", "advanced"]
    mode_labels = {"none": "None", "basic": "Basic", "advanced": "Advanced"}

    for mode in modes:
        if mode not in results:
            continue
        r = results[mode]
        metrics = r["metrics"]
        trades_df = r["trades"]

        total_trades = int(metrics.get("total_trades", 0))
        trades_per_year = 0.0
        avg_holding = 0.0
        if not trades_df.empty and "holding_days" in trades_df.columns:
            avg_holding = float(trades_df["holding_days"].mean())
        cagr_val = float(metrics.get("cagr_pct", 0.0))
        return_val = float(metrics.get("total_return_pct", 0.0))
        if abs(cagr_val) > 0.01:
            trades_per_year = total_trades / max(abs(return_val / cagr_val), 0.1)
        else:
            trades_per_year = total_trades / 8.5  # approximate years

        stop_losses = int(metrics.get("stop_losses_triggered", 0))
        rejected = int(metrics.get("trades_rejected_max_concurrent", 0)) + int(
            metrics.get("trades_rejected_exposure", 0)
        )

        rows.append(
            {
                "mode": mode_labels.get(mode, mode),
                "total_return_pct": return_val,
                "cagr_pct": cagr_val,
                "sharpe_ratio": float(metrics.get("sharpe_ratio", 0.0)),
                "win_rate_pct": float(metrics.get("win_rate_pct", 0.0)),
                "profit_factor": str(metrics.get("profit_factor", "0.0")),
                "max_drawdown_pct": float(metrics.get("maximum_drawdown_pct", 0.0)),
                "total_trades": total_trades,
                "trades_per_year": round(trades_per_year, 1),
                "avg_holding_days": round(avg_holding, 1),
                "stop_losses_triggered": stop_losses,
                "trades_rejected": rejected,
            }
        )
    return rows


def write_framework_report(
    comparison_rows: list[dict],
    results: dict[str, dict],
    output_path: Path,
    log_path: Path,
) -> None:
    """Generate the complete risk management framework documentation."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = [
        "# Risk Management Framework",
        "",
        "## Architecture",
        "",
        "The risk management layer sits between signal generation and portfolio execution. "
        "It operates as a pluggable module that intercepts BUY/SELL events in the backtesting engine.",
        "",
        "### Components",
        "",
        "- **RiskManager** — orchestrator that composes sizers, stops, and controls",
        "- **PositionSizer** — determines how many shares to buy on each entry",
        "- **StopLoss** — determines when to exit a position prematurely",
        "- **RiskControls** — configuration dataclass with all limits",
        "",
        "### Risk Modes",
        "",
        "| Mode | Sizing | Stop Losses | Concurrent Limit | Exposure Limit | Daily Loss Limit | Drawdown Limit |",
        "|------|--------|-------------|------------------|----------------|------------------|----------------|",
        "| None | Fixed 10% | None | Unlimited | Unlimited | None | None |",
        "| Basic | Fixed 10% | 5% Price + 60-day Time | 10 positions | 50% | None | None |",
        "| Advanced | Volatility-Adjusted | 2× ATR + 60-day Time | 10 positions | 50% | 2% daily | 20% peak |",
        "",
    ]

    # Comparison table
    lines.append("## Strategy Comparison: Momentum Across Risk Modes")
    lines.append("")
    lines.append(
        "| Metric | None | Basic | Advanced |"
    )
    lines.append(
        "|--------|------|-------|----------|"
    )

    if comparison_rows:
        metrics_to_show = [
            ("Total Return %", "total_return_pct", "{:.2f}%"),
            ("CAGR %", "cagr_pct", "{:.2f}%"),
            ("Sharpe Ratio", "sharpe_ratio", "{:.3f}"),
            ("Win Rate %", "win_rate_pct", "{:.1f}%"),
            ("Profit Factor", "profit_factor", "{}"),
            ("Max Drawdown %", "max_drawdown_pct", "{:.2f}%"),
            ("Total Trades", "total_trades", "{}"),
            ("Trades/Year", "trades_per_year", "{:.1f}"),
            ("Avg Hold (Days)", "avg_holding_days", "{:.0f}"),
            ("Stop Losses", "stop_losses_triggered", "{}"),
            ("Trades Rejected", "trades_rejected", "{}"),
        ]
        for label, key, fmt in metrics_to_show:
            values = [row.get(key, "N/A") for row in comparison_rows]
            formatted = []
            for v in values:
                try:
                    formatted.append(fmt.format(float(v)) if isinstance(v, (int, float)) else str(v))
                except (ValueError, TypeError):
                    formatted.append(str(v))
            lines.append(
                f"| {label} | {formatted[0] if len(formatted) > 0 else 'N/A'} | "
                f"{formatted[1] if len(formatted) > 1 else 'N/A'} | "
                f"{formatted[2] if len(formatted) > 2 else 'N/A'} |"
            )

    lines.append("")

    # Attribution analysis
    lines.append("## Risk Attribution Analysis")
    lines.append("")

    if len(comparison_rows) >= 3:
        none_row = comparison_rows[0]
        basic_row = comparison_rows[1]
        advanced_row = comparison_rows[2]

        def safe_float(v, default=0.0):
            try:
                return float(v)
            except (ValueError, TypeError):
                return default

        def safe_pf(v):
            if isinstance(v, str) and v in ("Infinity", "inf"):
                return float("inf")
            try:
                return float(v)
            except (ValueError, TypeError):
                return 0.0

        none_return = safe_float(none_row["total_return_pct"])
        none_sharpe = safe_float(none_row["sharpe_ratio"])
        none_dd = safe_float(none_row["max_drawdown_pct"])
        none_pf = safe_pf(none_row["profit_factor"])
        none_trades = int(none_row.get("total_trades", 0))

        basic_return = safe_float(basic_row["total_return_pct"])
        basic_sharpe = safe_float(basic_row["sharpe_ratio"])
        basic_dd = safe_float(basic_row["max_drawdown_pct"])
        basic_pf = safe_pf(basic_row["profit_factor"])
        basic_stops = int(basic_row.get("stop_losses_triggered", 0))

        adv_return = safe_float(advanced_row["total_return_pct"])
        adv_sharpe = safe_float(advanced_row["sharpe_ratio"])
        adv_dd = safe_float(advanced_row["max_drawdown_pct"])
        adv_pf = safe_pf(advanced_row["profit_factor"])
        adv_stops = int(advanced_row.get("stop_losses_triggered", 0))
        adv_rejected = int(advanced_row.get("trades_rejected", 0))

        lines.append("### None to Basic")
        lines.append("")
        lines.append(f"- Return change: {basic_return - none_return:+.2f}%")
        lines.append(f"- Sharpe change: {basic_sharpe - none_sharpe:+.4f}")
        lines.append(f"- Drawdown change: {basic_dd - none_dd:+.2f}%")
        lines.append(f"- Profit factor change: {basic_pf - none_pf:+.4f}" if isinstance(basic_pf, float) and isinstance(none_pf, float) else "- Profit factor: see table")
        lines.append(f"- Stop losses triggered: {basic_stops}")
        lines.append("")

        lines.append("### None to Advanced")
        lines.append("")
        lines.append(f"- Return change: {adv_return - none_return:+.2f}%")
        lines.append(f"- Sharpe change: {adv_sharpe - none_sharpe:+.4f}")
        lines.append(f"- Drawdown change: {adv_dd - none_dd:+.2f}%")
        lines.append(f"- Profit factor change: {adv_pf - none_pf:+.4f}" if isinstance(adv_pf, float) and isinstance(none_pf, float) else "- Profit factor: see table")
        lines.append(f"- Stop losses triggered: {adv_stops}")
        lines.append(f"- Trades rejected (limits): {adv_rejected}")
        lines.append("")

        # Success criteria evaluation
        lines.append("## Success Criteria Evaluation")
        lines.append("")

        criteria = []
        if adv_sharpe > none_sharpe:
            criteria.append("✅ Sharpe ratio improved")
        else:
            criteria.append("❌ Sharpe ratio did not improve")

        if adv_dd > none_dd:
            criteria.append("✅ Maximum drawdown decreased (less negative)")
        else:
            criteria.append("❌ Maximum drawdown did not decrease")

        if isinstance(adv_pf, float) and isinstance(none_pf, float) and adv_pf > none_pf:
            criteria.append("✅ Profit factor improved")
        else:
            criteria.append("❌ Profit factor did not improve")
        if adv_return < none_return:
            criteria.append(f"⚠️ Return sacrificed: {none_return:.2f}% → {adv_return:.2f}%")
        else:
            criteria.append("✅ Return preserved or improved")

        for c in criteria:
            lines.append(f"- {c}")
        lines.append("")

        # Recommendation
        lines.append("## Final Recommendation")
        lines.append("")

        # Find best mode
        best_mode = "none"
        best_score = -999
        for i, row in enumerate(comparison_rows):
            mode = row["mode"]
            r = safe_float(row["total_return_pct"])
            s = safe_float(row["sharpe_ratio"])
            dd = safe_float(row["max_drawdown_pct"])
            pf_val = safe_pf(row["profit_factor"])
            pf_score = min(pf_val, 10) if math.isfinite(pf_val) else 10
            score = r * 0.3 + s * 50 + dd * (-0.5) + pf_score * 5
            if score > best_score:
                best_score = score
                best_mode = mode

        lines.append(f"**Best Risk Mode:** {best_mode}")
        lines.append("")

        if best_mode == "Advanced":
            lines.append(
                "**Advanced Risk Management** is the recommended mode. "
                "It provides the best balance of capital preservation and risk-adjusted returns. "
                "The volatility-adjusted sizing reduces exposure during turbulent periods, "
                "while ATR stops cap individual trade losses and the drawdown limit "
                "prevents catastrophic equity erosion."
            )
        elif best_mode == "Basic":
            lines.append(
                "**Basic Risk Management** is the recommended mode. "
                "It offers improved drawdown control with minimal return sacrifice. "
                "The percentage stop and time stop provide simple but effective risk controls."
            )
        else:
            lines.append(
                "**No Risk Management** performs best in this test. "
                "However, this may indicate the risk parameters need adjustment "
                "rather than that risk management is unnecessary."
            )
        lines.append("")

        # Ready for paper trading?
        lines.append("### Readiness for Paper Trading")
        lines.append("")

        best_row = comparison_rows[[i for i, r in enumerate(comparison_rows) if r["mode"] == best_mode][0]]
        best_sharpe = safe_float(best_row["sharpe_ratio"])
        best_trades = int(best_row.get("total_trades", 0))
        best_dd = safe_float(best_row["max_drawdown_pct"])
        best_pf_val = safe_pf(best_row["profit_factor"])

        ready = True
        issues = []
        if best_sharpe < 0.5:
            issues.append(f"Sharpe ratio ({best_sharpe:.3f}) is below 0.5 threshold")
            ready = False
        if best_dd < -25:
            issues.append(f"Max drawdown ({best_dd:.2f}%) exceeds -25% threshold")
            ready = False
        if best_trades < 30:
            issues.append(f"Only {best_trades} trades — sample size may be insufficient")
            ready = False

        if ready:
            lines.append(
                "✅ **Momentum Strategy with Advanced Risk Management is ready for "
                "paper trading.** Key strengths:"
            )
            for row in comparison_rows:
                if row["mode"] == best_mode:
                    lines.append(f"- Sharpe: {safe_float(row['sharpe_ratio']):.3f}")
                    lines.append(f"- Max Drawdown: {safe_float(row['max_drawdown_pct']):.2f}%")
                    lines.append(f"- Profit Factor: {row['profit_factor']}")
                    lines.append(f"- Total Trades: {row['total_trades']}")
        else:
            lines.append(
                "⚠️ **Momentum Strategy requires further validation before paper trading.** "
                "Remaining weaknesses:"
            )
            for issue in issues:
                lines.append(f"- {issue}")
        lines.append("")

        lines.append("### Remaining Weaknesses Before Paper Trading")
        lines.append("")
        lines.append(
            "1. **Walk-forward validation**: Current results use a single fixed "
            "train/test period. A rolling walk-forward analysis would validate "
            "parameter robustness."
        )
        lines.append(
            "2. **Sensitivity analysis**: ATR multiplier, stop percentage, and "
            "position sizing parameters should be stress-tested across a range "
            "of values."
        )
        lines.append(
            "3. **Transaction costs**: STT, SEBI charges, GST, and market impact "
            "are not modeled. Real-world costs may reduce net returns by 0.5-1% annually."
        )
        lines.append(
            "4. **Slippage during volatility**: The fixed 0.05% slippage assumption "
            "may understate costs during high-volatility regimes."
        )
        lines.append(
            "5. **No dividend adjustment**: Total return calculations exclude dividends, "
            "which could add 1-2% annually for NIFTY 50 stocks."
        )
        lines.append("")

    lines.append("## Generated Files")
    lines.append("")
    lines.append("- `data/risk_comparison/none/trades.csv`")
    lines.append("- `data/risk_comparison/none/equity_curve.csv`")
    lines.append("- `data/risk_comparison/basic/trades.csv`")
    lines.append("- `data/risk_comparison/basic/equity_curve.csv`")
    lines.append("- `data/risk_comparison/advanced/trades.csv`")
    lines.append("- `data/risk_comparison/advanced/equity_curve.csv`")
    lines.append(f"- `{output_path.relative_to(PROJECT_ROOT).as_posix()}`")
    lines.append(f"- `{log_path.relative_to(PROJECT_ROOT).as_posix()}`")
    lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Risk management framework report: {_display_path(output_path)}")


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate risk management comparison report."
    )
    parser.add_argument(
        "--signal-dir",
        type=Path,
        default=DEFAULT_SIGNAL_DIR,
        help="Directory containing pre-generated signal files",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Output directory for risk comparison results",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=DEFAULT_REPORT_PATH,
        help="Path for the framework report",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=DEFAULT_LOG_PATH,
        help="Log file path",
    )
    parser.add_argument(
        "--strategy",
        type=str,
        default="momentum",
        help="Strategy name to test",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logger = configure_logging(args.log_file.resolve())

    try:
        logger.info("=" * 60)
        logger.info("Risk Management Framework Report Started")
        logger.info("=" * 60)

        # Register strategies
        from src.strategies.momentum_strategy import MomentumStrategy
        StrategyRegistry.register(MomentumStrategy)

        output_dir = args.output_dir.resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate signals for the target strategy
        strategy_name = args.strategy
        input_dir = PROJECT_ROOT / "data" / "processed"
        logger.info("Generating signals for strategy: %s", strategy_name)

        signal_dir = generate_signals_for_strategy(
            strategy_name, input_dir, output_dir, logger
        )
        if signal_dir is None:
            logger.error("Signal generation failed")
            return 1

        try:
            # Run all three risk modes
            modes = ["none", "basic", "advanced"]
            results: dict[str, dict] = {}

            for mode in modes:
                logger.info("Running backtest with risk_mode=%s", mode)
                trades, equity, metrics = run_backtest(
                    signal_dir, mode, output_dir, logger
                )
                results[mode] = {
                    "trades": trades,
                    "equity": equity,
                    "metrics": metrics,
                }
                logger.info(
                    "Mode %s: return=%.2f%%, sharpe=%.3f, dd=%.2f%%, trades=%d",
                    mode,
                    float(metrics.get("total_return_pct", 0)),
                    float(metrics.get("sharpe_ratio", 0)),
                    float(metrics.get("maximum_drawdown_pct", 0)),
                    int(metrics.get("total_trades", 0)),
                )

            # Build comparison and generate report
            comparison_rows = compute_comparison(results)

            # Print comparison to console
            print("\n" + "=" * 80)
            print(f"RISK MANAGEMENT COMPARISON — {strategy_name}")
            print("=" * 80)
            header = f"{'Metric':<25} {'None':<18} {'Basic':<18} {'Advanced':<18}"
            print(header)
            print("-" * 80)
            metrics_to_show = [
                ("Return %", "total_return_pct", "{:.2f}%"),
                ("CAGR %", "cagr_pct", "{:.2f}%"),
                ("Sharpe", "sharpe_ratio", "{:.3f}"),
                ("Win Rate %", "win_rate_pct", "{:.1f}%"),
                ("Profit Factor", "profit_factor", "{}"),
                ("Max DD %", "max_drawdown_pct", "{:.2f}%"),
                ("Trades", "total_trades", "{}"),
                ("Trades/Yr", "trades_per_year", "{:.1f}"),
                ("Avg Hold Days", "avg_holding_days", "{:.0f}"),
                ("Stop Losses", "stop_losses_triggered", "{}"),
            ]
            for label, key, fmt in metrics_to_show:
                vals = [fmt.format(r.get(key, 0)) if isinstance(r.get(key), (int, float)) else str(r.get(key, "N/A")) for r in comparison_rows]
                while len(vals) < 3:
                    vals.append("N/A")
                print(f"{label:<25} {vals[0]:<18} {vals[1]:<18} {vals[2]:<18}")
            print("=" * 80)

            # Generate report
            write_framework_report(comparison_rows, results, args.report.resolve(), args.log_file.resolve())

        finally:
            # Clean up temp signal directory
            if signal_dir and signal_dir.exists():
                shutil.rmtree(signal_dir, ignore_errors=True)

        logger.info("Risk management report complete")
        return 0

    except Exception as exc:
        logger.exception("Risk report generation failed")
        print(f"Fatal error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())