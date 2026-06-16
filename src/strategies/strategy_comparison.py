"""Compare the performance of multiple registered trading strategies."""

from __future__ import annotations

import argparse
import logging
import shutil
import tempfile
from dataclasses import asdict, dataclass
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pandas as pd

from src.backtesting.backtest_engine import PortfolioBacktester
from src.strategies.strategy_registry import StrategyRegistry


COMPARISON_TICKER_COLUMNS = (
    "strategy",
    "ticker",
    "buy_signals",
    "sell_signals",
    "hold_signals",
    "trades",
    "status",
)

COMPARISON_STRATEGY_COLUMNS = (
    "strategy",
    "total_buy_signals",
    "total_sell_signals",
    "total_hold_signals",
    "total_trades",
    "win_rate_pct",
    "total_return_pct",
    "cagr_pct",
    "max_drawdown_pct",
    "sharpe_ratio",
    "profit_factor",
    "avg_win",
    "avg_loss",
)

DEFAULT_INPUT_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"
DEFAULT_OUTPUT_DIR = (
    Path(__file__).resolve().parents[2] / "data" / "strategy_comparison"
)
DEFAULT_LOG_PATH = (
    Path(__file__).resolve().parents[2] / "logs" / "strategy_comparison.log"
)
PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class TickerSignalCounts:
    """Per-ticker signal counts for a strategy."""

    strategy: str
    ticker: str
    buy_signals: int = 0
    sell_signals: int = 0
    hold_signals: int = 0
    trades: int = 0
    status: str = "success"


@dataclass(frozen=True)
class StrategyPortfolioMetrics:
    """Aggregate portfolio-level metrics for a strategy."""

    strategy: str
    total_buy_signals: int = 0
    total_sell_signals: int = 0
    total_hold_signals: int = 0
    total_trades: int = 0
    win_rate_pct: float = 0.0
    total_return_pct: float = 0.0
    cagr_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    sharpe_ratio: float = 0.0
    profit_factor: str = "0.0"
    avg_win: float = 0.0
    avg_loss: float = 0.0


class ComparisonError(RuntimeError):
    """Base exception for comparison pipeline failures."""


def configure_logging(log_path: Path) -> logging.Logger:
    """Configure console and rotating file logging."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("strategy_comparison")
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


def _display_path(path: Path) -> str:
    """Format a path for display, showing relative path when possible."""
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def load_indicator_data(input_folder: Path) -> dict[str, pd.DataFrame]:
    """Load all indicator CSV files from the input folder.

    Args:
        input_folder: Directory containing *_indicators.csv files.

    Returns:
        Dictionary mapping ticker to its indicator DataFrame.

    Raises:
        ComparisonError: If no indicator files are found.
    """
    files = sorted(input_folder.glob("*_indicators.csv"))
    if not files:
        raise ComparisonError(
            f"No processed indicator CSV files found in {input_folder}"
        )

    datasets: dict[str, pd.DataFrame] = {}
    for path in files:
        ticker = path.stem.removesuffix("_indicators")
        try:
            data = pd.read_csv(path)
        except (OSError, pd.errors.ParserError) as exc:
            raise ComparisonError(f"Could not read {path}: {exc}") from exc
        if data.empty:
            raise ComparisonError(f"{ticker} indicator dataset is empty")
        data = data.copy()
        data["Date"] = pd.to_datetime(data["Date"], errors="coerce")
        datasets[ticker] = data.reset_index(drop=True)
    return datasets


def run_strategy_comparison(
    input_folder: Path,
    logger: logging.Logger,
    output_dir: Path | None = None,
) -> tuple[list[TickerSignalCounts], list[StrategyPortfolioMetrics]]:
    """Run all registered strategies through signal generation and backtesting.

    For each strategy:
      1. Generate signals on every ticker.
      2. Run the portfolio backtester across all tickers.
      3. Record per-ticker signal counts and aggregate portfolio metrics.

    Args:
        input_folder: Directory containing *_indicators.csv files.
        logger: Configured logger instance.

    Returns:
        Tuple of (ticker_counts, portfolio_metrics).
    """
    from src.strategies.signal_engine import SignalEngine

    indicator_data = load_indicator_data(input_folder)
    tickers = sorted(indicator_data.keys())
    strategy_names = StrategyRegistry.list_strategies()

    if not strategy_names:
        raise ComparisonError(
            "No strategies registered. "
            "Call StrategyRegistry.register() before running comparison."
        )

    logger.info(
        "Starting comparison: strategies=%d, tickers=%d",
        len(strategy_names),
        len(tickers),
    )

    all_ticker_counts: list[TickerSignalCounts] = []
    all_portfolio_metrics: list[StrategyPortfolioMetrics] = []

    for strategy_name in strategy_names:
        strategy_class = StrategyRegistry.get_strategy(strategy_name)
        strategy = strategy_class()
        logger.info("Evaluating strategy: %s", strategy_name)

        temp_dir = Path(tempfile.mkdtemp(prefix=f"signals_{strategy_name}_"))
        try:
            signal_engine = SignalEngine(temp_dir, logger, strategy=strategy)
            ticker_signal_counts: list[TickerSignalCounts] = []

            for ticker in tickers:
                data_path = input_folder / f"{ticker}_indicators.csv"
                signal_result = signal_engine.process_file(data_path)
                if signal_result.status != "success":
                    ticker_signal_counts.append(
                        TickerSignalCounts(
                            strategy=strategy_name,
                            ticker=ticker,
                            status=f"signal_failed: {signal_result.error}",
                        )
                    )
                    logger.warning(
                        "Signal generation failed for %s on %s: %s",
                        strategy_name,
                        ticker,
                        signal_result.error,
                    )
                    continue

            # Run portfolio backtest on all generated signal files
            backtester = PortfolioBacktester()
            signal_datasets = backtester.load_signal_files(temp_dir)
            if not signal_datasets:
                logger.warning(
                    "No valid signal files generated for strategy %s",
                    strategy_name,
                )
                continue

            trades, equity, metrics = backtester.run(signal_datasets)

            # Persist trade-level data for validation
            if not trades.empty and output_dir is not None:
                trades_path = output_dir / f"trades_{strategy_name}.csv"
                trades.to_csv(trades_path, index=False)
                logger.info("Persisted %d trades to %s", len(trades), _display_path(trades_path))

            # Build per-ticker signal counts
            for ticker in tickers:
                if ticker not in signal_datasets:
                    continue
                ticker_data = signal_datasets[ticker]
                signal_counts = ticker_data["Signal"].value_counts()

                # Count ticker-level trades
                ticker_trade_count = 0
                if not trades.empty:
                    ticker_trades = trades[trades["ticker"] == ticker]
                    ticker_trade_count = len(ticker_trades)

                ticker_signal_counts.append(
                    TickerSignalCounts(
                        strategy=strategy_name,
                        ticker=ticker,
                        buy_signals=int(signal_counts.get("BUY", 0)),
                        sell_signals=int(signal_counts.get("SELL", 0)),
                        hold_signals=int(signal_counts.get("HOLD", 0)),
                        trades=ticker_trade_count,
                    )
                )
                logger.info(
                    "  %s on %s: BUY=%d, SELL=%d, HOLD=%d, trades=%d",
                    strategy_name,
                    ticker,
                    int(signal_counts.get("BUY", 0)),
                    int(signal_counts.get("SELL", 0)),
                    int(signal_counts.get("HOLD", 0)),
                    ticker_trade_count,
                )

            # Aggregate portfolio metrics (strategy-level, not per-ticker)
            total_buys = sum(t.buy_signals for t in ticker_signal_counts
                             if t.status == "success")
            total_sells = sum(t.sell_signals for t in ticker_signal_counts
                              if t.status == "success")
            total_holds = sum(t.hold_signals for t in ticker_signal_counts
                              if t.status == "success")
            total_trades = int(metrics.get("total_trades", 0))
            win_rate = float(metrics.get("win_rate_pct", 0.0))
            total_return = float(metrics.get("total_return_pct", 0.0))
            cagr = float(metrics.get("cagr_pct", 0.0))
            max_dd = float(metrics.get("maximum_drawdown_pct", 0.0))
            sharpe = float(metrics.get("sharpe_ratio", 0.0))
            pf = metrics.get("profit_factor", "0.0")
            pf_str = str(pf) if isinstance(pf, str) else f"{pf:.4f}"
            avg_win = float(metrics.get("average_win", 0.0))
            avg_loss = float(metrics.get("average_loss", 0.0))

            portfolio_metrics = StrategyPortfolioMetrics(
                strategy=strategy_name,
                total_buy_signals=total_buys,
                total_sell_signals=total_sells,
                total_hold_signals=total_holds,
                total_trades=total_trades,
                win_rate_pct=round(win_rate, 2),
                total_return_pct=round(total_return, 4),
                cagr_pct=round(cagr, 4),
                max_drawdown_pct=round(max_dd, 4),
                sharpe_ratio=round(sharpe, 4),
                profit_factor=pf_str,
                avg_win=round(avg_win, 2),
                avg_loss=round(avg_loss, 2),
            )

            all_ticker_counts.extend(ticker_signal_counts)
            all_portfolio_metrics.append(portfolio_metrics)

            logger.info(
                "Strategy %s portfolio: return=%.2f%%, trades=%d, win_rate=%.1f%%",
                strategy_name,
                total_return,
                total_trades,
                win_rate,
            )

        except Exception as exc:
            logger.error(
                "Comparison failed for strategy %s: %s", strategy_name, exc
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    return all_ticker_counts, all_portfolio_metrics


def write_ticker_csv(
    ticker_counts: list[TickerSignalCounts], output_path: Path
) -> None:
    """Write per-ticker signal counts to a CSV file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [asdict(t) for t in ticker_counts], columns=COMPARISON_TICKER_COLUMNS
    ).to_csv(output_path, index=False)


def write_portfolio_csv(
    portfolio_metrics: list[StrategyPortfolioMetrics], output_path: Path
) -> None:
    """Write portfolio-level metrics to a CSV file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [asdict(p) for p in portfolio_metrics], columns=COMPARISON_STRATEGY_COLUMNS
    ).to_csv(output_path, index=False)


def write_comparison_report(
    ticker_counts: list[TickerSignalCounts],
    portfolio_metrics: list[StrategyPortfolioMetrics],
    output_dir: Path,
    log_path: Path,
) -> None:
    """Write a human-readable comparison report."""
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "comparison_report.md"

    strategy_names = sorted(set(t.strategy for t in ticker_counts))

    lines: list[str] = [
        "# Strategy Comparison Report",
        "",
        "## Summary",
        "",
        f"- Strategies compared: {len(strategy_names)}",
        f"- Tickers evaluated: {len(set(t.ticker for t in ticker_counts))}",
        f"- Total signal runs: {len(ticker_counts)}",
        "",
    ]

    # Portfolio-level comparison table
    lines.append("## Portfolio Performance Comparison")
    lines.append("")
    lines.append(
        "| Strategy | Return % | CAGR % | Max DD % | Sharpe | Win Rate | "
        "Trades | Profit Factor | Avg Win | Avg Loss |"
    )
    lines.append(
        "|----------|----------|--------|----------|--------|----------|"
        "--------|---------------|---------|----------|"
    )
    for pm in sorted(portfolio_metrics, key=lambda x: x.total_return_pct, reverse=True):
        lines.append(
            f"| {pm.strategy} | {pm.total_return_pct:.2f}% "
            f"| {pm.cagr_pct:.2f}% | {pm.max_drawdown_pct:.2f}% "
            f"| {pm.sharpe_ratio:.3f} | {pm.win_rate_pct:.1f}% "
            f"| {pm.total_trades} | {pm.profit_factor} "
            f"| INR {pm.avg_win:.2f} | INR {pm.avg_loss:.2f} |"
        )
    lines.append("")

    # Per-strategy detail sections
    for strategy_name in strategy_names:
        lines.append(f"## {strategy_name}")
        lines.append("")

        pm = next((p for p in portfolio_metrics if p.strategy == strategy_name), None)
        if pm:
            lines.append("**Portfolio Metrics:**")
            lines.append(f"- Total return: {pm.total_return_pct:.2f}%")
            lines.append(f"- CAGR: {pm.cagr_pct:.2f}%")
            lines.append(f"- Max drawdown: {pm.max_drawdown_pct:.2f}%")
            lines.append(f"- Sharpe ratio: {pm.sharpe_ratio:.3f}")
            lines.append(f"- Win rate: {pm.win_rate_pct:.1f}%")
            lines.append(f"- Total trades: {pm.total_trades}")
            lines.append(f"- Profit factor: {pm.profit_factor}")
            lines.append("")

        # Per-ticker signal counts table
        strategy_tickers = [
            t for t in ticker_counts
            if t.strategy == strategy_name and t.status == "success"
        ]
        if strategy_tickers:
            lines.append("**Signal Counts by Ticker:**")
            lines.append("")
            lines.append("| Ticker | BUY | SELL | HOLD | Trades |")
            lines.append("|--------|-----|------|------|--------|")
            for t in strategy_tickers:
                lines.append(
                    f"| {t.ticker} | {t.buy_signals} | {t.sell_signals} "
                    f"| {t.hold_signals} | {t.trades} |"
                )
            lines.append("")

        failed = [
            t for t in ticker_counts
            if t.strategy == strategy_name and t.status != "success"
        ]
        if failed:
            lines.append("**Failed:**")
            for t in failed:
                lines.append(f"- {t.ticker}: {t.status}")
            lines.append("")

    lines.append("## Generated Files")
    lines.append("")
    lines.append(f"- `{_display_path(output_dir / 'signal_counts.csv')}`")
    lines.append(f"- `{_display_path(output_dir / 'portfolio_metrics.csv')}`")
    lines.append(f"- `{_display_path(report_path)}`")
    lines.append(f"- `{_display_path(log_path)}`")
    lines.append("")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Compare trading strategy performance across registered strategies."
    )
    parser.add_argument(
        "--input-folder",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help="Folder containing *_indicators.csv files (default: data/processed/)",
    )
    parser.add_argument(
        "--output-folder",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Folder to save comparison results (default: data/strategy_comparison/)",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=DEFAULT_LOG_PATH,
        help="Log file path (default: logs/strategy_comparison.log)",
    )
    return parser.parse_args()


def main() -> int:
    """Main entry point for strategy comparison.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    args = parse_args()
    logger = configure_logging(args.log_file.resolve())

    # Register all available strategies
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

    logger.info("=" * 60)
    logger.info("Strategy Comparison Started")
    logger.info("=" * 60)
    logger.info(
        "Registered strategies: %s",
        ", ".join(StrategyRegistry.list_strategies()),
    )

    try:
        output_dir = args.output_folder.resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        ticker_counts, portfolio_metrics = run_strategy_comparison(
            args.input_folder.resolve(),
            logger,
            output_dir=output_dir,
        )

        if not portfolio_metrics and not ticker_counts:
            logger.error("No comparison results generated")
            return 1

        # Write outputs
        write_ticker_csv(ticker_counts, output_dir / "signal_counts.csv")
        write_portfolio_csv(portfolio_metrics, output_dir / "portfolio_metrics.csv")
        write_comparison_report(
            ticker_counts,
            portfolio_metrics,
            output_dir,
            args.log_file.resolve(),
        )

        logger.info(
            "Comparison complete: %d strategies, %d ticker-signal runs",
            len(portfolio_metrics),
            len(ticker_counts),
        )
        print("\nStrategy Comparison Complete")
        print(f"Signal counts:  {_display_path(output_dir / 'signal_counts.csv')}")
        print(f"Portfolio metrics: {_display_path(output_dir / 'portfolio_metrics.csv')}")
        print(f"Report: {_display_path(output_dir / 'comparison_report.md')}")

        # Print quick summary to console
        print("\nPortfolio Performance Summary:")
        print(f"{'Strategy':<20} {'Return%':<10} {'CAGR%':<10} {'MaxDD%':<10} {'Sharpe':<8} {'Trades':<8}")
        print("-" * 66)
        for pm in sorted(portfolio_metrics, key=lambda x: x.total_return_pct, reverse=True):
            print(
                f"{pm.strategy:<20} {pm.total_return_pct:<10.2f} "
                f"{pm.cagr_pct:<10.2f} {pm.max_drawdown_pct:<10.2f} "
                f"{pm.sharpe_ratio:<8.3f} {pm.total_trades:<8}"
            )
        return 0

    except Exception as exc:
        logger.exception("Comparison failed")
        print(f"Fatal comparison error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())