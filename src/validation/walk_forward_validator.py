"""Walk-forward validation framework for strategy robustness testing."""

from __future__ import annotations

import argparse
import logging
import math
import shutil
import tempfile
from dataclasses import asdict, dataclass
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pandas as pd

from src.backtesting.backtest_engine import PortfolioBacktester
from src.strategies.strategy_registry import StrategyRegistry


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_DIR = PROJECT_ROOT / "data" / "processed"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "walk_forward"
DEFAULT_REPORT_PATH = PROJECT_ROOT / "docs" / "walk_forward_validation.md"
DEFAULT_LOG_PATH = PROJECT_ROOT / "logs" / "walk_forward_validation.log"
INITIAL_CAPITAL = 100_000.0
POSITION_SIZE = 0.10
BROKERAGE_RATE = 0.0005
SLIPPAGE_RATE = 0.0005

# Walk-forward windows: (train_start, train_end, test_start, test_end)
WALK_FORWARD_WINDOWS: list[tuple[str, str, str, str]] = [
    ("2018-01-01", "2020-12-31", "2021-01-01", "2021-12-31"),
    ("2019-01-01", "2021-12-31", "2022-01-01", "2022-12-31"),
    ("2020-01-01", "2022-12-31", "2023-01-01", "2023-12-31"),
    ("2021-01-01", "2023-12-31", "2024-01-01", "2024-12-31"),
    ("2022-01-01", "2024-12-31", "2025-01-01", "2025-12-31"),
]


@dataclass(frozen=True)
class WindowResult:
    """Backtest results for a single walk-forward window and period."""
    window: int
    period: str  # "train" or "test"
    strategy: str
    total_return_pct: float
    cagr_pct: float
    sharpe_ratio: float
    profit_factor: str
    max_drawdown_pct: float
    win_rate_pct: float
    total_trades: int
    start_date: str
    end_date: str


@dataclass(frozen=True)
class StrategyConsistency:
    """Aggregated consistency metrics for a strategy."""
    strategy: str
    avg_test_return: float
    avg_test_sharpe: float
    avg_test_drawdown: float
    std_test_return: float
    std_test_sharpe: float
    std_test_drawdown: float
    positive_return_windows: int
    positive_sharpe_windows: int
    pf_above_one_windows: int
    consistency_score: float
    classification: str


def configure_logging(log_path: Path) -> logging.Logger:
    """Configure console and rotating file logging."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("walk_forward_validation")
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


def load_indicator_data(input_folder: Path) -> dict[str, pd.DataFrame]:
    """Load all indicator CSV files."""
    files = sorted(input_folder.glob("*_indicators.csv"))
    datasets: dict[str, pd.DataFrame] = {}
    for path in files:
        ticker = path.stem.removesuffix("_indicators")
        data = pd.read_csv(path)
        data["Date"] = pd.to_datetime(data["Date"], errors="coerce")
        datasets[ticker] = data
    return datasets


def filter_by_date(
    data: dict[str, pd.DataFrame],
    start_date: str,
    end_date: str,
) -> dict[str, pd.DataFrame]:
    """Filter all ticker dataframes to a date range."""
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)
    filtered: dict[str, pd.DataFrame] = {}
    for ticker, df in data.items():
        mask = (df["Date"] >= start) & (df["Date"] <= end)
        subset = df[mask].copy().reset_index(drop=True)
        if not subset.empty:
            filtered[ticker] = subset
    return filtered


def generate_signals(
    indicator_data: dict[str, pd.DataFrame],
    strategy_name: str,
    logger: logging.Logger,
) -> Path | None:
    """Generate signal files for a strategy on given indicator data."""
    from src.strategies.signal_engine import SignalEngine

    strategy_class = StrategyRegistry.get_strategy(strategy_name)
    strategy = strategy_class()

    temp_dir = Path(tempfile.mkdtemp(prefix=f"wf_signals_{strategy_name}_"))
    engine = SignalEngine(temp_dir, logger, strategy=strategy)

    for ticker, df in indicator_data.items():
        csv_path = temp_dir / f"{ticker}_indicators.csv"
        df.to_csv(csv_path, index=False, date_format="%Y-%m-%d")
        result = engine.process_file(csv_path)
        if result.status != "success":
            logger.warning("Signal gen failed for %s in window: %s", ticker, result.error)
        csv_path.unlink()  # clean up temp indicator file

    return temp_dir


def run_window_backtest(
    signal_dir: Path,
    strategy_name: str,
    window: int,
    period: str,
    logger: logging.Logger,
) -> WindowResult | None:
    """Run backtest on generated signals and return window result."""
    try:
        backtester = PortfolioBacktester(
            initial_capital=INITIAL_CAPITAL,
            position_size=POSITION_SIZE,
            brokerage_rate=BROKERAGE_RATE,
            slippage_rate=SLIPPAGE_RATE,
            logger=logger,
        )
        datasets = backtester.load_signal_files(signal_dir)
        if not datasets:
            return None
        _, _, metrics = backtester.run(datasets)

        return WindowResult(
            window=window,
            period=period,
            strategy=strategy_name,
            total_return_pct=float(metrics.get("total_return_pct", 0.0)),
            cagr_pct=float(metrics.get("cagr_pct", 0.0)),
            sharpe_ratio=float(metrics.get("sharpe_ratio", 0.0)),
            profit_factor=str(metrics.get("profit_factor", "0.0")),
            max_drawdown_pct=float(metrics.get("maximum_drawdown_pct", 0.0)),
            win_rate_pct=float(metrics.get("win_rate_pct", 0.0)),
            total_trades=int(metrics.get("total_trades", 0)),
            start_date=str(metrics.get("start_date", "")),
            end_date=str(metrics.get("end_date", "")),
        )
    except Exception as exc:
        logger.error("Backtest failed for %s window %d %s: %s", strategy_name, window, period, exc)
        return None


def parse_profit_factor(pf: object) -> float:
    """Convert profit factor to numeric."""
    if isinstance(pf, str):
        if pf in ("Infinity", "inf", "infinity"):
            return float("inf")
        try:
            return float(pf)
        except (ValueError, TypeError):
            return 0.0
    return float(pf) if pf is not None else 0.0


def compute_consistency(
    test_results: list[WindowResult],
) -> StrategyConsistency:
    """Compute consistency scores for a strategy based on test period results."""
    if not test_results:
        return StrategyConsistency(
            strategy="unknown",
            avg_test_return=0, avg_test_sharpe=0, avg_test_drawdown=0,
            std_test_return=0, std_test_sharpe=0, std_test_drawdown=0,
            positive_return_windows=0, positive_sharpe_windows=0,
            pf_above_one_windows=0, consistency_score=0, classification="Insufficient Data",
        )

    returns = [r.total_return_pct for r in test_results]
    sharpes = [r.sharpe_ratio for r in test_results]
    drawdowns = [r.max_drawdown_pct for r in test_results]
    pfs = [parse_profit_factor(r.profit_factor) for r in test_results]
    n = len(test_results)

    avg_ret = sum(returns) / n
    avg_shp = sum(sharpes) / n
    avg_dd = sum(drawdowns) / n
    std_ret = (sum((r - avg_ret) ** 2 for r in returns) / n) ** 0.5 if n > 1 else 0
    std_shp = (sum((s - avg_shp) ** 2 for s in sharpes) / n) ** 0.5 if n > 1 else 0
    std_dd = (sum((d - avg_dd) ** 2 for d in drawdowns) / n) ** 0.5 if n > 1 else 0

    pos_ret = sum(1 for r in returns if r > 0)
    pos_shp = sum(1 for s in sharpes if s > 0)
    pf_above_1 = sum(1 for p in pfs if math.isfinite(p) and p > 1.0)

    # Consistency score (0-100)
    score = 0.0

    # Positive returns in test windows: up to 25 points
    score += (pos_ret / n) * 25

    # Sharpe stability: up to 20 points if average > 0 and std is low
    if avg_shp > 0:
        score += 10
        if std_shp < 0.5:
            score += 10
        elif std_shp < 1.0:
            score += 5

    # Drawdown stability: up to 20 points
    if std_dd < 5:
        score += 15
    elif std_dd < 10:
        score += 10
    elif std_dd < 15:
        score += 5
    # Bonus for low average drawdown
    if avg_dd > -15:
        score += 5

    # Profit factor consistency: up to 20 points
    score += (pf_above_1 / n) * 20

    # Return consistency (all same sign): up to 15 points
    if all(r > 0 for r in returns) or all(r < 0 for r in returns):
        score += 15
    elif pos_ret >= n * 0.6:
        score += 7

    # Clamp to 0-100
    score = max(0, min(100, score))

    # Classification
    if score >= 70:
        classification = "Robust"
    elif score >= 40:
        classification = "Moderate"
    elif score >= 20:
        classification = "Unstable"
    else:
        classification = "Overfit / Reject"

    return StrategyConsistency(
        strategy=test_results[0].strategy,
        avg_test_return=round(avg_ret, 2),
        avg_test_sharpe=round(avg_shp, 3),
        avg_test_drawdown=round(avg_dd, 2),
        std_test_return=round(std_ret, 2),
        std_test_sharpe=round(std_shp, 3),
        std_test_drawdown=round(std_dd, 2),
        positive_return_windows=pos_ret,
        positive_sharpe_windows=pos_shp,
        pf_above_one_windows=pf_above_1,
        consistency_score=round(score, 1),
        classification=classification,
    )


def generate_report(
    all_results: list[WindowResult],
    consistencies: list[StrategyConsistency],
    output_path: Path,
    log_path: Path,
) -> None:
    """Generate the walk-forward validation markdown report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    strategy_names = sorted(set(r.strategy for r in all_results))
    n_windows = len(WALK_FORWARD_WINDOWS)

    lines: list[str] = [
        "# Walk-Forward Validation Report",
        "",
        "## Overview",
        "",
        "Walk-forward validation tests strategy robustness across multiple independent "
        "time periods. Each window uses a training period for signal generation and "
        "a separate out-of-sample test period for evaluation.",
        "",
        f"- **Windows:** {n_windows} rolling windows",
        f"- **Strategies evaluated:** {len(strategy_names)}",
        f"- **Universe:** NIFTY 49 stocks (TATAMOTORS.NS delisted on Yahoo)",
        "",
        "### Window Structure",
        "",
        "| Window | Train Period | Test Period |",
        "|--------|--------------|-------------|",
    ]
    for i, (tr_s, tr_e, te_s, te_e) in enumerate(WALK_FORWARD_WINDOWS, 1):
        lines.append(f"| {i} | {tr_s} to {tr_e} | {te_s} to {te_e} |")
    lines.append("")

    # Per-strategy, per-window tables
    for strategy_name in strategy_names:
        lines.append(f"## Strategy: {strategy_name}")
        lines.append("")

        strategy_results = [r for r in all_results if r.strategy == strategy_name]

        for period_label, period_key in [("Training", "train"), ("Test (Out-of-Sample)", "test")]:
            period_results = [r for r in strategy_results if r.period == period_key]
            if not period_results:
                continue

            lines.append(f"### {period_label} Period")
            lines.append("")
            lines.append(
                "| Window | Return % | CAGR % | Sharpe | Profit Factor | "
                "Max DD % | Win Rate % | Trades |"
            )
            lines.append(
                "|--------|----------|--------|--------|---------------|"
                "----------|------------|--------|"
            )
            for r in sorted(period_results, key=lambda x: x.window):
                lines.append(
                    f"| {r.window} | {r.total_return_pct:.2f}% "
                    f"| {r.cagr_pct:.2f}% | {r.sharpe_ratio:.3f} "
                    f"| {r.profit_factor} | {r.max_drawdown_pct:.2f}% "
                    f"| {r.win_rate_pct:.1f}% | {r.total_trades} |"
                )
            lines.append("")

        lines.append("")

    # Consistency comparison
    lines.append("## Consistency Score Comparison")
    lines.append("")
    lines.append(
        "| Strategy | Score | Classification | Avg Return % | Avg Sharpe | "
        "Avg DD % | Std Return | Std Sharpe | Pos Return Wds | Pf>1 Wds |"
    )
    lines.append(
        "|----------|-------|----------------|--------------|------------|"
        "----------|------------|------------|----------------|----------|"
    )
    for c in sorted(consistencies, key=lambda x: x.consistency_score, reverse=True):
        lines.append(
            f"| {c.strategy} | {c.consistency_score:.1f} | {c.classification} "
            f"| {c.avg_test_return:.2f}% | {c.avg_test_sharpe:.3f} "
            f"| {c.avg_test_drawdown:.2f}% | {c.std_test_return:.2f} "
            f"| {c.std_test_sharpe:.3f} | {c.positive_return_windows}/{len(WALK_FORWARD_WINDOWS)} "
            f"| {c.pf_above_one_windows}/{len(WALK_FORWARD_WINDOWS)} |"
        )
    lines.append("")

    # Robustness assessment
    lines.append("## Robustness Assessment")
    lines.append("")

    for c in sorted(consistencies, key=lambda x: x.consistency_score, reverse=True):
        if c.classification == "Robust":
            lines.append(f"- **{c.strategy}**: ✅ **Robust** — "
                         f"Consistently positive returns across {c.positive_return_windows}/{len(WALK_FORWARD_WINDOWS)} "
                         f"test windows with stable risk metrics.")
        elif c.classification == "Moderate":
            lines.append(f"- **{c.strategy}**: ⚠️ **Moderate** — "
                         f"Shows some consistency but with notable variance. "
                         f"Score: {c.consistency_score:.1f}.")
        elif c.classification == "Unstable":
            lines.append(f"- **{c.strategy}**: ❌ **Unstable** — "
                         f"High variance in returns across windows. "
                         f"May be period-dependent.")
        else:
            lines.append(f"- **{c.strategy}**: ❌ **Overfit / Reject** — "
                         f"Performance is inconsistent or negative across test windows. "
                         f"Not suitable for deployment without significant changes.")
    lines.append("")

    # Final ranking
    lines.append("## Final Strategy Ranking (Walk-Forward)")
    lines.append("")
    lines.append("| Rank | Strategy | Consistency Score | Classification |")
    lines.append("|------|----------|------------------|----------------|")
    for rank, c in enumerate(sorted(consistencies, key=lambda x: x.consistency_score, reverse=True), 1):
        lines.append(f"| {rank} | {c.strategy} | {c.consistency_score:.1f} | {c.classification} |")
    lines.append("")

    # Recommendation
    lines.append("## Recommendation")
    lines.append("")

    best = max(consistencies, key=lambda c: c.consistency_score) if consistencies else None
    if best:
        if best.classification == "Robust":
            lines.append(
                f"**{best.strategy}** is the most robust strategy with a consistency "
                f"score of {best.consistency_score:.1f}. It demonstrates stable "
                f"out-of-sample performance across {len(WALK_FORWARD_WINDOWS)} independent "
                f"test periods."
            )
            lines.append("")
            lines.append("**Is Momentum robust?** — See ranking above.")
            lines.append("**Is EMA robust?** — See ranking above.")
            lines.append("**Is Mean Reversion robust?** — See ranking above.")
        else:
            lines.append(
                "No strategy achieved Robust classification. The highest scoring "
                f"strategy is **{best.strategy}** with a consistency score of "
                f"{best.consistency_score:.1f} ({best.classification})."
            )

    lines.append("")

    # Limitations
    lines.append("## Limitations")
    lines.append("")
    lines.append(
        "- **Look-ahead bias in indicator calculation**: Indicators are calculated "
        "on the full dataset, then filtered by date. This introduces minor look-ahead "
        "bias in the training period. A true walk-forward would recalculate indicators "
        "on each training window independently."
    )
    lines.append(
        "- **Annual test windows**: One-year test periods may be too short to capture "
        "full market cycles. Multi-year test windows would provide more robust estimates."
    )
    lines.append(
        "- **Fixed parameters**: Strategy parameters (e.g., RSI thresholds, EMA periods) "
        "are fixed across all windows. Parameter optimization within each training window "
        "would be a more rigorous test."
    )
    lines.append(
        "- **Survivorship bias**: Current NIFTY 50 constituents only. Stocks that were "
        "delisted or replaced are not included."
    )
    lines.append("")

    # Generated files
    lines.append("## Generated Files")
    lines.append("")
    lines.append(f"- `{output_path.relative_to(PROJECT_ROOT).as_posix()}`")
    lines.append(f"- `{log_path.relative_to(PROJECT_ROOT).as_posix()}`")
    lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Walk-forward validation report: {_display_path(output_path)}")


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run walk-forward validation on all registered strategies."
    )
    parser.add_argument("--input-folder", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--log-file", type=Path, default=DEFAULT_LOG_PATH)
    parser.add_argument("--strategies", type=str, nargs="*",
                        help="Strategies to validate (default: all registered)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logger = configure_logging(args.log_file.resolve())

    try:
        logger.info("=" * 60)
        logger.info("Walk-Forward Validation Started")
        logger.info("=" * 60)

        # Register all strategies
        from src.strategies.ema_rsi_macd_strategy import EmaRsiMacdStrategy
        from src.strategies.mean_reversion_strategy import MeanReversionStrategy
        from src.strategies.momentum_strategy import MomentumStrategy
        from src.strategies.breakout_strategy import BreakoutStrategy
        from src.strategies.donchian_strategy import DonchianStrategy
        from src.strategies.bull_trap_strategy import BullTrapStrategy
        from src.strategies.bear_trap_strategy import BearTrapStrategy
        from src.strategies.bollinger_reversion_strategy import BollingerReversionStrategy
        from src.strategies.volatility_expansion_strategy import VolatilityExpansionStrategy

        StrategyRegistry.register(EmaRsiMacdStrategy)
        StrategyRegistry.register(MeanReversionStrategy)
        StrategyRegistry.register(MomentumStrategy)
        StrategyRegistry.register(BreakoutStrategy)
        StrategyRegistry.register(DonchianStrategy)
        StrategyRegistry.register(BullTrapStrategy)
        StrategyRegistry.register(BearTrapStrategy)
        StrategyRegistry.register(BollingerReversionStrategy)
        StrategyRegistry.register(VolatilityExpansionStrategy)

        strategy_names = args.strategies or StrategyRegistry.list_strategies()
        logger.info("Strategies to validate: %s", ", ".join(strategy_names))

        # Load all indicator data once
        indicator_data = load_indicator_data(args.input_folder.resolve())
        logger.info("Loaded indicator data for %d tickers", len(indicator_data))

        all_results: list[WindowResult] = []

        for strategy_name in strategy_names:
            logger.info("Validating strategy: %s", strategy_name)

            for window_idx, (tr_s, tr_e, te_s, te_e) in enumerate(WALK_FORWARD_WINDOWS, 1):
                logger.info("  Window %d: train=%s to %s, test=%s to %s",
                            window_idx, tr_s, tr_e, te_s, te_e)

                for period_label, period_start, period_end in [
                    ("train", tr_s, tr_e),
                    ("test", te_s, te_e),
                ]:
                    # Filter data to period
                    period_data = filter_by_date(indicator_data, period_start, period_end)
                    if not period_data:
                        logger.warning("    No data for %s period", period_label)
                        continue

                    logger.info("    %s: %d tickers with data", period_label, len(period_data))

                    # Generate signals
                    signal_dir = generate_signals(period_data, strategy_name, logger)
                    if signal_dir is None:
                        continue

                    try:
                        # Run backtest
                        result = run_window_backtest(
                            signal_dir, strategy_name, window_idx, period_label, logger
                        )
                        if result is not None:
                            all_results.append(result)
                            logger.info(
                                "    %s result: return=%.2f%%, sharpe=%.3f, dd=%.2f%%, trades=%d",
                                period_label,
                                result.total_return_pct, result.sharpe_ratio,
                                result.max_drawdown_pct, result.total_trades,
                            )
                    finally:
                        shutil.rmtree(signal_dir, ignore_errors=True)

        # Compute consistency scores
        consistencies: list[StrategyConsistency] = []
        for strategy_name in strategy_names:
            test_results = [
                r for r in all_results
                if r.strategy == strategy_name and r.period == "test"
            ]
            if test_results:
                consistency = compute_consistency(test_results)
                consistencies.append(consistency)
                logger.info(
                    "Strategy %s consistency: score=%.1f, classification=%s",
                    strategy_name, consistency.consistency_score, consistency.classification,
                )

        # Generate report
        generate_report(all_results, consistencies, args.report.resolve(), args.log_file.resolve())

        # Print summary to console
        print("\n" + "=" * 80)
        print("WALK-FORWARD VALIDATION RESULTS")
        print("=" * 80)

        for strategy_name in strategy_names:
            print(f"\n--- {strategy_name} ---")
            test_results = [
                r for r in all_results
                if r.strategy == strategy_name and r.period == "test"
            ]
            print(f"{'Window':<8} {'Return%':<10} {'Sharpe':<8} {'DD%':<8} {'PF':<10} {'Trades':<8}")
            print("-" * 54)
            for r in sorted(test_results, key=lambda x: x.window):
                print(
                    f"{r.window:<8} {r.total_return_pct:<10.2f} "
                    f"{r.sharpe_ratio:<8.3f} {r.max_drawdown_pct:<8.2f} "
                    f"{r.profit_factor:<10} {r.total_trades:<8}"
                )

        print("\n" + "=" * 80)
        print("CONSISTENCY RANKING")
        print("=" * 80)
        print(f"{'Rank':<6} {'Strategy':<20} {'Score':<8} {'Classification':<20}")
        print("-" * 54)
        for rank, c in enumerate(sorted(consistencies, key=lambda x: x.consistency_score, reverse=True), 1):
            print(f"{rank:<6} {c.strategy:<20} {c.consistency_score:<8.1f} {c.classification:<20}")
        print("=" * 80)

        logger.info("Walk-forward validation complete")
        return 0

    except Exception as exc:
        logger.exception("Walk-forward validation failed")
        print(f"Fatal error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())