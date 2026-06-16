"""Generate offline trading signals from enriched technical indicator data."""

from __future__ import annotations

import argparse
import logging
from dataclasses import asdict, dataclass
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from src.strategies.base_strategy import BaseStrategy


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_DIR = PROJECT_ROOT / "data" / "processed"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "signals"
DEFAULT_SUMMARY_PATH = PROJECT_ROOT / "data" / "signal_summary.csv"
DEFAULT_LOG_PATH = PROJECT_ROOT / "logs" / "signal_engine.log"
DEFAULT_REPORT_PATH = PROJECT_ROOT / "docs" / "signal_engine_report.md"

REQUIRED_COLUMNS = (
    "Date",
    "Close",
    "EMA_20",
    "EMA_50",
    "EMA_200",
    "RSI_14",
    "MACD",
    "MACD_Signal",
)
SIGNAL_COLUMNS = (
    "Signal_Date",
    "Signal",
    "Signal_Confidence",
    "Conditions_Met",
    "Buy_Conditions_Met",
    "Sell_Conditions_Met",
)
SUMMARY_COLUMNS = (
    "ticker",
    "status",
    "row_count",
    "buy_count",
    "sell_count",
    "hold_count",
    "latest_signal",
    "latest_signal_date",
    "latest_confidence",
    "file_path",
    "warnings",
    "error",
)


class SignalEngineError(RuntimeError):
    """Base exception for signal pipeline failures."""


class InputValidationError(SignalEngineError):
    """Raised when an indicator dataset is unsuitable for signal generation."""


class SignalCalculationError(SignalEngineError):
    """Raised when generated signals fail consistency checks."""


@dataclass(frozen=True)
class SignalResult:
    ticker: str
    status: str
    row_count: int = 0
    buy_count: int = 0
    sell_count: int = 0
    hold_count: int = 0
    latest_signal: str = ""
    latest_signal_date: str = ""
    latest_confidence: str = ""
    file_path: str = ""
    warnings: str = ""
    error: str = ""


def configure_logging(log_path: Path) -> logging.Logger:
    """Configure console and rotating file logging."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("signal_engine")
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


class SignalEngine:
    """Orchestrate signal generation using a pluggable strategy."""

    def __init__(
        self,
        output_folder: Path | str,
        logger: logging.Logger,
        strategy: BaseStrategy | None = None,
    ) -> None:
        self.output_folder = Path(output_folder).resolve()
        self.output_folder.mkdir(parents=True, exist_ok=True)
        self.logger = logger
        if strategy is None:
            from src.strategies.ema_rsi_macd_strategy import EmaRsiMacdStrategy

            strategy = EmaRsiMacdStrategy()
        self.strategy = strategy

    def _load_and_validate_input(self, csv_path: Path) -> pd.DataFrame:
        required_cols = self.strategy.required_indicator_columns
        try:
            data = pd.read_csv(csv_path)
        except (OSError, pd.errors.ParserError) as exc:
            raise InputValidationError(f"Could not read {csv_path}: {exc}") from exc

        if data.empty:
            raise InputValidationError("Input dataset is empty")
        missing_columns = [column for column in required_cols if column not in data]
        if missing_columns:
            raise InputValidationError(
                f"Missing required columns: {', '.join(missing_columns)}"
            )

        data = data.copy()
        data["Date"] = pd.to_datetime(data["Date"], errors="coerce")
        invalid_dates = int(data["Date"].isna().sum())
        if invalid_dates:
            raise InputValidationError(f"Found {invalid_dates} invalid dates")

        numeric_columns = [column for column in required_cols if column != "Date"]
        for column in numeric_columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
        if "Close" in data and data["Close"].isna().any():
            raise InputValidationError("Close contains missing or non-numeric values")
        if data["Date"].duplicated().any():
            raise InputValidationError("Input contains duplicate dates")
        if not data["Date"].is_monotonic_increasing:
            raise InputValidationError("Input dates are not sorted ascending")
        return data.reset_index(drop=True)

    def process_file(self, csv_path: Path) -> SignalResult:
        """Generate and save signals for one processed indicator CSV."""
        ticker = csv_path.stem.removesuffix("_indicators")
        try:
            self.logger.info("Processing %s", csv_path)
            source = self._load_and_validate_input(csv_path)
            signals = self.strategy.generate_signals(source)
            warnings = self.strategy.validate_output(source, signals)

            output_path = self.output_folder / f"{ticker}_signals.csv"
            temporary_path = output_path.with_suffix(".csv.tmp")
            signals.to_csv(temporary_path, index=False, date_format="%Y-%m-%d")
            temporary_path.replace(output_path)

            counts = signals["Signal"].value_counts()
            latest = signals.iloc[-1]
            warning_text = "; ".join(warnings)
            if warning_text:
                self.logger.warning("%s: %s", ticker, warning_text)
            self.logger.info(
                "Completed %s: BUY=%d, SELL=%d, HOLD=%d, latest=%s (%s), file=%s",
                ticker,
                int(counts.get("BUY", 0)),
                int(counts.get("SELL", 0)),
                int(counts.get("HOLD", 0)),
                latest["Signal"],
                latest["Signal_Date"].date().isoformat(),
                _display_path(output_path),
            )
            return SignalResult(
                ticker=ticker,
                status="success",
                row_count=len(signals),
                buy_count=int(counts.get("BUY", 0)),
                sell_count=int(counts.get("SELL", 0)),
                hold_count=int(counts.get("HOLD", 0)),
                latest_signal=str(latest["Signal"]),
                latest_signal_date=latest["Signal_Date"].date().isoformat(),
                latest_confidence=str(latest["Signal_Confidence"]),
                file_path=_display_path(output_path),
                warnings=warning_text,
            )
        except SignalEngineError as exc:
            self.logger.error("Signal processing failed for %s: %s", ticker, exc)
            return SignalResult(ticker=ticker, status="failed", error=str(exc))
        except Exception as exc:
            self.logger.exception("Unexpected signal failure for %s", ticker)
            return SignalResult(
                ticker=ticker,
                status="failed",
                error=f"Unexpected error: {type(exc).__name__}: {exc}",
            )


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def write_summary(results: list[SignalResult], summary_path: Path) -> None:
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [asdict(result) for result in results], columns=SUMMARY_COLUMNS
    ).to_csv(summary_path, index=False)


def write_report(
    results: list[SignalResult],
    input_files: list[Path],
    summary_path: Path,
    log_path: Path,
    report_path: Path,
) -> None:
    successful = [result for result in results if result.status == "success"]
    failed = [result for result in results if result.status == "failed"]
    generated_files = [result.file_path for result in successful]
    generated_files.extend(
        (_display_path(summary_path), _display_path(log_path), _display_path(report_path))
    )

    file_lines = "\n".join(f"- `{path}`" for path in generated_files)
    statistic_lines = "\n".join(
        f"- `{result.ticker}`: BUY {result.buy_count}, SELL {result.sell_count}, "
        f"HOLD {result.hold_count}; latest {result.latest_signal} "
        f"({result.latest_confidence}) on {result.latest_signal_date}"
        for result in successful
    ) or "- None"
    warning_lines = "\n".join(
        f"- `{result.ticker}`: {result.warnings}"
        for result in successful
        if result.warnings
    ) or "- None"
    failure_lines = "\n".join(
        f"- `{result.ticker}`: {result.error}" for result in failed
    ) or "- None"

    report = f"""# Signal Engine Report

## Execution Summary

- Input files: {len(input_files)}
- Successful files: {len(successful)}
- Failed files: {len(failed)}
- Total BUY signals: {sum(result.buy_count for result in successful)}
- Total SELL signals: {sum(result.sell_count for result in successful)}
- Total HOLD signals: {sum(result.hold_count for result in successful)}

## Strategy Logic

Strategy: EMA Trend + RSI + MACD Confirmation.

BUY requires all four conditions:

- EMA 20 is above EMA 50.
- Close is above EMA 200.
- RSI 14 is between 55 and 70, inclusive.
- MACD is above the MACD Signal line.

SELL requires at least one condition, provided the BUY rule did not match:

- EMA 20 is below EMA 50, or
- RSI 14 is below 45, or
- MACD is below the MACD Signal line.

All other rows are HOLD.

## Confidence

- High: 4 applicable conditions met.
- Medium: 3 applicable conditions met.
- Low: fewer than 3 applicable conditions met.

Because the SELL rule defines three conditions, its maximum confidence is Medium.

## Assumptions

- BUY has precedence only when all four BUY conditions are satisfied.
- Indicator warm-up rows with unavailable values are assigned HOLD with Low confidence.
- Signals describe the state on each daily row; they are not orders and are not executed.
- No transaction costs, position state, portfolio constraints, or future returns are used.

## Generated Files

{file_lines}

## Signal Statistics

{statistic_lines}

## Warnings

{warning_lines}

## Failed Files

{failure_lines}
"""
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate EMA, RSI, and MACD-confirmed trading signals."
    )
    parser.add_argument("--input-folder", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-folder", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY_PATH)
    parser.add_argument("--log-file", type=Path, default=DEFAULT_LOG_PATH)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logger = configure_logging(args.log_file.resolve())
    try:
        input_folder = args.input_folder.resolve()
        input_files = sorted(input_folder.glob("*_indicators.csv"))
        if not input_files:
            raise InputValidationError(
                f"No processed indicator CSV files found in {input_folder}"
            )

        logger.info(
            "Starting signal run: files=%d, input=%s, output=%s",
            len(input_files),
            input_folder,
            args.output_folder.resolve(),
        )
        engine = SignalEngine(args.output_folder, logger)
        results = [engine.process_file(csv_path) for csv_path in input_files]
        write_summary(results, args.summary.resolve())
        write_report(
            results,
            input_files,
            args.summary.resolve(),
            args.log_file.resolve(),
            args.report.resolve(),
        )

        successful = sum(result.status == "success" for result in results)
        failed = len(results) - successful
        logger.info(
            "Signal run finished: successful=%d, failed=%d", successful, failed
        )
        print(f"Successful files: {successful}")
        print(f"Failed files: {failed}")
        print("Latest signals:")
        for result in results:
            if result.status == "success":
                print(
                    f"  {result.ticker}: {result.latest_signal} "
                    f"({result.latest_confidence}) on {result.latest_signal_date}"
                )
        print(f"Summary: {_display_path(args.summary.resolve())}")
        print(f"Report: {_display_path(args.report.resolve())}")
        print(f"Log: {_display_path(args.log_file.resolve())}")
        return 0 if successful and not failed else 1
    except Exception as exc:
        logger.exception("Signal run could not be completed")
        print(f"Fatal signal error: {exc}")
        return 2


if __name__ == "__main__":
    # Register all strategies so they are discoverable via the registry.
    from src.strategies.ema_rsi_macd_strategy import EmaRsiMacdStrategy
    from src.strategies.mean_reversion_strategy import MeanReversionStrategy
    from src.strategies.momentum_strategy import MomentumStrategy
    from src.strategies.strategy_registry import StrategyRegistry

    StrategyRegistry.register(EmaRsiMacdStrategy)
    StrategyRegistry.register(MeanReversionStrategy)
    StrategyRegistry.register(MomentumStrategy)
    raise SystemExit(main())
