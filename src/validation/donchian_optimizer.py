"""Donchian strategy parameter optimization and validation."""

from __future__ import annotations

import itertools
import logging
import shutil
import tempfile
from dataclasses import dataclass, field
from logging.handlers import RotatingFileHandler
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_DIR = PROJECT_ROOT / "data" / "processed"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "donchian_optimization"
DEFAULT_REPORT_PATH = PROJECT_ROOT / "docs" / "donchian_optimization_results.md"
DEFAULT_LOG_PATH = PROJECT_ROOT / "logs" / "donchian_optimizer.log"
INITIAL_CAPITAL = 100_000.0

# Parameter grid
ENTRY_CHANNELS = [20, 30, 40, 55, 70, 100]
EXIT_CHANNELS = [10, 20, 30, 40]

# Walk-forward windows
WALK_FORWARD_WINDOWS = [
    ("2018-01-01", "2020-12-31", "2021-01-01", "2021-12-31"),
    ("2019-01-01", "2021-12-31", "2022-01-01", "2022-12-31"),
    ("2020-01-01", "2022-12-31", "2023-01-01", "2023-12-31"),
    ("2021-01-01", "2023-12-31", "2024-01-01", "2024-12-31"),
    ("2022-01-01", "2024-12-31", "2025-01-01", "2025-12-31"),
]


def configure_logging(log_path: Path) -> logging.Logger:
    """Configure console and rotating file logging."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("donchian_optimizer")
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


@dataclass
class ParameterResult:
    """Results for a single parameter combination."""
    entry_channel: int
    exit_channel: int
    total_return_pct: float = 0.0
    cagr_pct: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    win_rate_pct: float = 0.0
    total_trades: int = 0
    profit_factor: float = 0.0
    # Walk-forward results
    wf_positive_windows: int = 0
    wf_avg_test_return: float = 0.0
    wf_avg_test_sharpe: float = 0.0
    wf_score: float = 0.0
    # Classification
    is_return: float = 0.0
    oos_return: float = 0.0
    overfitting_flag: str = ""


class DonchianOptimizer:
    """Optimize Donchian strategy parameters using grid search.

    Tests all combinations of entry and exit channel lengths,
    runs full-period backtests and walk-forward validation.
    """

    def __init__(
        self,
        input_dir: Path | str = DEFAULT_INPUT_DIR,
        output_dir: Path | str = DEFAULT_OUTPUT_DIR,
        logger: logging.Logger | None = None,
    ) -> None:
        self.input_dir = Path(input_dir).resolve()
        self.output_dir = Path(output_dir).resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logger or configure_logging(DEFAULT_LOG_PATH)
        self.results: list[ParameterResult] = []

    # ------------------------------------------------------------------
    # Signal Generation
    # ------------------------------------------------------------------

    def generate_donchian_signals(
        self, data: pd.DataFrame, entry_period: int, exit_period: int
    ) -> pd.DataFrame:
        """Generate Donchian signals with specified channel parameters."""
        enriched = data.copy()
        close = enriched["Close"]

        # Donchian channels
        upper = close.rolling(entry_period, min_periods=entry_period).max().shift(1)
        lower = close.rolling(exit_period, min_periods=exit_period).min().shift(1)

        # Signals
        buy_signal = close > upper
        sell_signal = close < lower

        signal = np.where(buy_signal, "BUY", np.where(sell_signal, "SELL", "HOLD"))

        enriched["Signal_Date"] = enriched["Date"]
        enriched["Signal"] = signal
        enriched["Signal_Confidence"] = "High"
        enriched["Conditions_Met"] = np.where(buy_signal | sell_signal, 1, 0)
        enriched["Buy_Conditions_Met"] = buy_signal.astype(int)
        enriched["Sell_Conditions_Met"] = sell_signal.astype(int)

        return enriched

    # ------------------------------------------------------------------
    # Backtest Execution
    # ------------------------------------------------------------------

    def run_backtest(self, signal_dir: Path) -> dict:
        """Run backtest on signal files and return metrics."""
        from src.backtesting.backtest_engine import PortfolioBacktester

        backtester = PortfolioBacktester(
            initial_capital=INITIAL_CAPITAL,
            position_size=0.10,
            brokerage_rate=0.0005,
            slippage_rate=0.0005,
            risk_mode="none",
        )

        try:
            datasets = PortfolioBacktester.load_signal_files(signal_dir)
            if not datasets:
                return {"error": "No signal files"}

            trade_frame, equity, metrics = backtester.run(datasets)
            return metrics
        except Exception as e:
            self.logger.error("Backtest failed: %s", e)
            return {"error": str(e)}

    # ------------------------------------------------------------------
    # Full-Period Optimization
    # ------------------------------------------------------------------

    def run_full_period_optimization(self) -> list[ParameterResult]:
        """Run full-period backtests for all parameter combinations."""
        self.logger.info("Starting full-period optimization")
        self.logger.info(
            "Parameter grid: entry=%s, exit=%s (%d combinations)",
            ENTRY_CHANNELS, EXIT_CHANNELS,
            len(ENTRY_CHANNELS) * len(EXIT_CHANNELS),
        )

        # Load all processed data
        processed_files = sorted(self.input_dir.glob("*_indicators.csv"))
        if not processed_files:
            raise FileNotFoundError(f"No indicator files found in {self.input_dir}")

        self.logger.info("Loaded %d indicator files", len(processed_files))

        results: list[ParameterResult] = []

        for entry_ch, exit_ch in itertools.product(ENTRY_CHANNELS, EXIT_CHANNELS):
            self.logger.info("Testing entry=%d, exit=%d", entry_ch, exit_ch)

            # Create temp directory for signal files
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_path = Path(tmpdir)

                # Generate signals for each ticker
                for csv_path in processed_files:
                    ticker = csv_path.stem.removesuffix("_indicators")
                    data = pd.read_csv(csv_path)
                    data["Date"] = pd.to_datetime(data["Date"])

                    # Skip if not enough data
                    if len(data) < max(entry_ch, exit_ch) + 10:
                        continue

                    signals = self.generate_donchian_signals(data, entry_ch, exit_ch)
                    output_path = tmp_path / f"{ticker}_signals.csv"
                    signals.to_csv(output_path, index=False)

                # Run backtest
                metrics = self.run_backtest(tmp_path)

                if "error" not in metrics:
                    result = ParameterResult(
                        entry_channel=entry_ch,
                        exit_channel=exit_ch,
                        total_return_pct=float(metrics.get("total_return_pct", 0)),
                        cagr_pct=float(metrics.get("cagr_pct", 0)),
                        sharpe_ratio=float(metrics.get("sharpe_ratio", 0)),
                        max_drawdown_pct=float(metrics.get("max_drawdown_pct", 0)),
                        win_rate_pct=float(metrics.get("win_rate_pct", 0)),
                        total_trades=int(metrics.get("total_trades", 0)),
                        profit_factor=float(metrics.get("profit_factor", 0)),
                    )
                    results.append(result)
                    self.logger.info(
                        "  entry=%d, exit=%d: return=%.2f%%, sharpe=%.3f, dd=%.2f%%",
                        entry_ch, exit_ch,
                        result.total_return_pct,
                        result.sharpe_ratio,
                        result.max_drawdown_pct,
                    )
                else:
                    self.logger.warning(
                        "  entry=%d, exit=%d: FAILED - %s",
                        entry_ch, exit_ch, metrics["error"],
                    )

        self.results = results
        return results

    # ------------------------------------------------------------------
    # Walk-Forward Validation
    # ------------------------------------------------------------------

    def run_walk_forward(self, entry_ch: int, exit_ch: int) -> dict:
        """Run walk-forward validation for a single parameter combination."""
        self.logger.info("Walk-forward: entry=%d, exit=%d", entry_ch, exit_ch)

        test_returns: list[float] = []
        test_sharpes: list[float] = []
        positive_windows = 0

        for i, (train_start, train_end, test_start, test_end) in enumerate(WALK_FORWARD_WINDOWS):
            # Generate signals for test period
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_path = Path(tmpdir)

                processed_files = sorted(self.input_dir.glob("*_indicators.csv"))
                for csv_path in processed_files:
                    ticker = csv_path.stem.removesuffix("_indicators")
                    data = pd.read_csv(csv_path)
                    data["Date"] = pd.to_datetime(data["Date"])

                    # Filter to test period
                    test_data = data[
                        (data["Date"] >= test_start) & (data["Date"] <= test_end)
                    ].copy()

                    if len(test_data) < max(entry_ch, exit_ch) + 5:
                        continue

                    # Generate signals using full history (no look-ahead)
                    full_data = data[data["Date"] <= test_end].copy()
                    if len(full_data) < max(entry_ch, exit_ch) + 10:
                        continue

                    signals = self.generate_donchian_signals(full_data, entry_ch, exit_ch)
                    # Keep only test period signals
                    test_signals = signals[
                        (signals["Date"] >= test_start) & (signals["Date"] <= test_end)
                    ]

                    if not test_signals.empty:
                        output_path = tmp_path / f"{ticker}_signals.csv"
                        test_signals.to_csv(output_path, index=False)

                # Run backtest on test period
                metrics = self.run_backtest(tmp_path)
                if "error" not in metrics:
                    ret = float(metrics.get("total_return_pct", 0))
                    sharpe = float(metrics.get("sharpe_ratio", 0))
                    test_returns.append(ret)
                    test_sharpes.append(sharpe)
                    if ret > 0:
                        positive_windows += 1

        return {
            "test_returns": test_returns,
            "test_sharpes": test_sharpes,
            "positive_windows": positive_windows,
            "avg_return": np.mean(test_returns) if test_returns else 0,
            "avg_sharpe": np.mean(test_sharpes) if test_sharpes else 0,
        }

    def run_walk_forward_validation(self) -> None:
        """Run walk-forward validation for all parameter combinations."""
        self.logger.info("Starting walk-forward validation")

        for result in self.results:
            wf = self.run_walk_forward(result.entry_channel, result.exit_channel)
            result.wf_positive_windows = wf["positive_windows"]
            result.wf_avg_test_return = round(wf["avg_return"], 2)
            result.wf_avg_test_sharpe = round(wf["avg_sharpe"], 3)
            result.wf_score = wf["positive_windows"] * 20  # 0-100 scale

            self.logger.info(
                "  entry=%d, exit=%d: WF positive=%d/5, avg_return=%.2f%%, score=%.0f",
                result.entry_channel, result.exit_channel,
                result.wf_positive_windows,
                result.wf_avg_test_return,
                result.wf_score,
            )

    # ------------------------------------------------------------------
    # Overfitting Detection
    # ------------------------------------------------------------------

    def detect_overfitting(self) -> None:
        """Detect overfitting by comparing IS vs OOS performance."""
        self.logger.info("Detecting overfitting...")

        for result in self.results:
            # IS = full-period return, OOS = walk-forward avg return
            result.is_return = result.total_return_pct
            result.oos_return = result.wf_avg_test_return

            # Overfitting flag
            if result.is_return > 0 and result.oos_return < 0:
                result.overfitting_flag = "OVERFIT"
            elif result.is_return > 0 and result.oos_return < result.is_return * 0.3:
                result.overfitting_flag = "WEAK"
            else:
                result.overfitting_flag = "OK"

            self.logger.info(
                "  entry=%d, exit=%d: IS=%.2f%%, OOS=%.2f%%, flag=%s",
                result.entry_channel, result.exit_channel,
                result.is_return, result.oos_return, result.overfitting_flag,
            )

    # ------------------------------------------------------------------
    # Ranking & Reporting
    # ------------------------------------------------------------------

    def rank_results(self) -> list[ParameterResult]:
        """Rank all parameter combinations by multiple criteria."""
        # Sort by Sharpe ratio (primary), then by WF score (secondary)
        return sorted(
            self.results,
            key=lambda r: (r.sharpe_ratio, r.wf_score, r.total_return_pct),
            reverse=True,
        )

    def generate_report(self) -> str:
        """Generate comprehensive optimization report."""
        ranked = self.rank_results()

        lines = []
        lines.append("# Donchian Strategy Parameter Optimization Results\n")

        # Summary
        lines.append("## Summary\n")
        lines.append(f"- Parameter combinations tested: {len(ranked)}")
        lines.append(f"- Entry channels: {ENTRY_CHANNELS}")
        lines.append(f"- Exit channels: {EXIT_CHANNELS}")
        lines.append(f"- Walk-forward windows: {len(WALK_FORWARD_WINDOWS)}")
        lines.append("")

        # Full ranking table
        lines.append("## All Parameter Combinations (Ranked by Sharpe)\n")
        lines.append("| Rank | Entry | Exit | Return % | Sharpe | Max DD % | Win Rate % | Trades | WF Score | Overfit |")
        lines.append("|------|-------|------|----------|--------|----------|------------|--------|----------|---------|")

        for i, r in enumerate(ranked, 1):
            lines.append(
                f"| {i} | {r.entry_channel} | {r.exit_channel} | "
                f"{r.total_return_pct:.2f} | {r.sharpe_ratio:.3f} | "
                f"{r.max_drawdown_pct:.2f} | {r.win_rate_pct:.2f} | "
                f"{r.total_trades} | {r.wf_score:.0f} | {r.overfitting_flag} |"
            )

        lines.append("")

        # Best configurations
        lines.append("## Best Configurations\n")

        # Best Return
        best_return = max(ranked, key=lambda r: r.total_return_pct)
        lines.append(f"### Best Return: {best_return.entry_channel}/{best_return.exit_channel}")
        lines.append(f"- Return: {best_return.total_return_pct:.2f}%")
        lines.append(f"- Sharpe: {best_return.sharpe_ratio:.3f}")
        lines.append(f"- Max DD: {best_return.max_drawdown_pct:.2f}%")
        lines.append(f"- WF Score: {best_return.wf_score:.0f}")
        lines.append(f"- Overfit: {best_return.overfitting_flag}")
        lines.append("")

        # Best Sharpe
        best_sharpe = max(ranked, key=lambda r: r.sharpe_ratio)
        lines.append(f"### Best Sharpe: {best_sharpe.entry_channel}/{best_sharpe.exit_channel}")
        lines.append(f"- Return: {best_sharpe.total_return_pct:.2f}%")
        lines.append(f"- Sharpe: {best_sharpe.sharpe_ratio:.3f}")
        lines.append(f"- Max DD: {best_sharpe.max_drawdown_pct:.2f}%")
        lines.append(f"- WF Score: {best_sharpe.wf_score:.0f}")
        lines.append(f"- Overfit: {best_sharpe.overfitting_flag}")
        lines.append("")

        # Best Robust (highest WF score with positive return)
        robust_candidates = [r for r in ranked if r.total_return_pct > 0 and r.overfitting_flag != "OVERFIT"]
        if robust_candidates:
            best_robust = max(robust_candidates, key=lambda r: r.wf_score)
            lines.append(f"### Best Robust: {best_robust.entry_channel}/{best_robust.exit_channel}")
            lines.append(f"- Return: {best_robust.total_return_pct:.2f}%")
            lines.append(f"- Sharpe: {best_robust.sharpe_ratio:.3f}")
            lines.append(f"- Max DD: {best_robust.max_drawdown_pct:.2f}%")
            lines.append(f"- WF Score: {best_robust.wf_score:.0f}")
            lines.append(f"- Overfit: {best_robust.overfitting_flag}")
            lines.append("")

        # Current champion comparison
        lines.append("## Current Champion (55/20)\n")
        current = next((r for r in ranked if r.entry_channel == 55 and r.exit_channel == 20), None)
        if current:
            lines.append(f"- Return: {current.total_return_pct:.2f}%")
            lines.append(f"- Sharpe: {current.sharpe_ratio:.3f}")
            lines.append(f"- Max DD: {current.max_drawdown_pct:.2f}%")
            lines.append(f"- WF Score: {current.wf_score:.0f}")
            lines.append(f"- Overfit: {current.overfitting_flag}")
        lines.append("")

        # Overfitting analysis
        lines.append("## Overfitting Analysis\n")
        overfit_count = sum(1 for r in ranked if r.overfitting_flag == "OVERFIT")
        weak_count = sum(1 for r in ranked if r.overfitting_flag == "WEAK")
        ok_count = sum(1 for r in ranked if r.overfitting_flag == "OK")
        lines.append(f"- OVERFIT: {overfit_count}/{len(ranked)}")
        lines.append(f"- WEAK: {weak_count}/{len(ranked)}")
        lines.append(f"- OK: {ok_count}/{len(ranked)}")
        lines.append("")

        # Recommendation
        lines.append("## Recommendation\n")
        if current and best_sharpe:
            if best_sharpe.sharpe_ratio > current.sharpe_ratio and best_sharpe.overfitting_flag != "OVERFIT":
                lines.append(f"**REPLACE CURRENT** with {best_sharpe.entry_channel}/{best_sharpe.exit_channel}")
                lines.append(f"\nSharpe improvement: {best_sharpe.sharpe_ratio:.3f} vs {current.sharpe_ratio:.3f}")
            else:
                lines.append("**KEEP CURRENT** (55/20)")
                lines.append("\nNo statistically meaningful improvement found.")
        else:
            lines.append("**KEEP CURRENT** (55/20)")
            lines.append("\nInsufficient data for comparison.")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Main Run
    # ------------------------------------------------------------------

    def run(self) -> str:
        """Run the full optimization pipeline."""
        self.logger.info("Starting Donchian optimization pipeline")

        # 1. Full-period optimization
        self.run_full_period_optimization()

        # 2. Walk-forward validation
        self.run_walk_forward_validation()

        # 3. Overfitting detection
        self.detect_overfitting()

        # 4. Generate report
        report = self.generate_report()

        # 5. Save report
        report_path = DEFAULT_REPORT_PATH
        report_path.write_text(report, encoding="utf-8")
        self.logger.info("Report saved to %s", report_path)

        return report
