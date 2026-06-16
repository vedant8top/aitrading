"""Reusable technical indicator calculation and validation pipeline."""

from __future__ import annotations

import argparse
import logging
from dataclasses import asdict, dataclass
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_DIR = PROJECT_ROOT / "data" / "raw"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "processed"
DEFAULT_SUMMARY_PATH = PROJECT_ROOT / "data" / "indicator_summary.csv"
DEFAULT_LOG_PATH = PROJECT_ROOT / "logs" / "indicator_engine.log"
DEFAULT_REPORT_PATH = PROJECT_ROOT / "docs" / "indicator_engine_report.md"

REQUIRED_COLUMNS = ("Date", "Open", "High", "Low", "Close", "Volume")
INDICATOR_COLUMNS = (
    "SMA_20",
    "SMA_50",
    "EMA_20",
    "EMA_50",
    "EMA_200",
    "RSI_14",
    "MACD",
    "MACD_Signal",
    "MACD_Histogram",
    "ATR_14",
    "Bollinger_Middle_20",
    "Bollinger_Upper_20",
    "Bollinger_Lower_20",
    "Volume_MA_20",
)
EXPECTED_WARMUP = {
    "SMA_20": 19,
    "SMA_50": 49,
    "EMA_20": 19,
    "EMA_50": 49,
    "EMA_200": 199,
    "RSI_14": 14,
    "MACD": 25,
    "MACD_Signal": 33,
    "MACD_Histogram": 33,
    "ATR_14": 13,
    "Bollinger_Middle_20": 19,
    "Bollinger_Upper_20": 19,
    "Bollinger_Lower_20": 19,
    "Volume_MA_20": 19,
}
SUMMARY_COLUMNS = (
    "ticker",
    "status",
    "row_count",
    "indicator_count",
    "null_count",
    "expected_warmup_nulls",
    "unexpected_null_count",
    "date_alignment_valid",
    "file_path",
    "warnings",
    "error",
)


class IndicatorEngineError(RuntimeError):
    """Base exception for indicator pipeline failures."""


class InputValidationError(IndicatorEngineError):
    """Raised when an input dataset cannot be safely processed."""


class IndicatorCalculationError(IndicatorEngineError):
    """Raised when an indicator calculation produces invalid output."""


@dataclass(frozen=True)
class IndicatorResult:
    ticker: str
    status: str
    row_count: int = 0
    indicator_count: int = 0
    null_count: int = 0
    expected_warmup_nulls: int = 0
    unexpected_null_count: int = 0
    date_alignment_valid: bool = False
    file_path: str = ""
    warnings: str = ""
    error: str = ""


def configure_logging(log_path: Path) -> logging.Logger:
    """Configure console and rotating file logs for indicator runs."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("technical_indicator_engine")
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


class TechnicalIndicatorEngine:
    """Calculate and validate technical indicators for OHLCV datasets."""

    def __init__(self, output_folder: Path | str, logger: logging.Logger) -> None:
        self.output_folder = Path(output_folder).resolve()
        self.output_folder.mkdir(parents=True, exist_ok=True)
        self.logger = logger

    @staticmethod
    def _load_and_validate_input(csv_path: Path) -> pd.DataFrame:
        try:
            data = pd.read_csv(csv_path)
        except (OSError, pd.errors.ParserError) as exc:
            raise InputValidationError(f"Could not read {csv_path}: {exc}") from exc

        missing_columns = [column for column in REQUIRED_COLUMNS if column not in data]
        if missing_columns:
            raise InputValidationError(
                f"Missing required columns: {', '.join(missing_columns)}"
            )
        if data.empty:
            raise InputValidationError("Input dataset is empty")

        data = data.copy()
        data["Date"] = pd.to_datetime(data["Date"], errors="coerce")
        invalid_dates = int(data["Date"].isna().sum())
        if invalid_dates:
            raise InputValidationError(f"Found {invalid_dates} invalid dates")

        numeric_columns = ("Open", "High", "Low", "Close", "Volume")
        for column in numeric_columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
        source_nulls = int(data[list(numeric_columns)].isna().sum().sum())
        if source_nulls:
            raise InputValidationError(
                f"Found {source_nulls} missing or non-numeric OHLCV values"
            )

        duplicate_dates = int(data["Date"].duplicated(keep="last").sum())
        if duplicate_dates:
            data = data.drop_duplicates(subset="Date", keep="last")
        data = data.sort_values("Date").reset_index(drop=True)
        if not data["Date"].is_monotonic_increasing:
            raise InputValidationError("Dates could not be sorted in ascending order")
        if (data["High"] < data["Low"]).any():
            raise InputValidationError("Found rows where High is below Low")
        return data

    @staticmethod
    def _safe_calculation(
        name: str, calculation: Callable[[], pd.Series], index: pd.Index
    ) -> pd.Series:
        try:
            values = calculation()
        except Exception as exc:
            raise IndicatorCalculationError(f"{name} calculation failed: {exc}") from exc
        if not isinstance(values, pd.Series):
            raise IndicatorCalculationError(f"{name} did not return a pandas Series")
        if not values.index.equals(index):
            raise IndicatorCalculationError(f"{name} is not aligned with source rows")
        values = values.replace([np.inf, -np.inf], np.nan)
        return values.astype(float)

    @staticmethod
    def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
        delta = close.diff()
        gains = delta.clip(lower=0.0)
        losses = -delta.clip(upper=0.0)
        average_gain = gains.ewm(
            alpha=1 / period, adjust=False, min_periods=period
        ).mean()
        average_loss = losses.ewm(
            alpha=1 / period, adjust=False, min_periods=period
        ).mean()
        relative_strength = average_gain / average_loss
        rsi = 100.0 - (100.0 / (1.0 + relative_strength))
        rsi = rsi.mask((average_loss == 0) & (average_gain > 0), 100.0)
        return rsi.mask((average_loss == 0) & (average_gain == 0), 50.0)

    @staticmethod
    def _true_range(data: pd.DataFrame) -> pd.Series:
        previous_close = data["Close"].shift(1)
        ranges = pd.concat(
            (
                data["High"] - data["Low"],
                (data["High"] - previous_close).abs(),
                (data["Low"] - previous_close).abs(),
            ),
            axis=1,
        )
        return ranges.max(axis=1)

    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """Return a copy of data enriched with the configured indicators."""
        enriched = data.copy()
        close = enriched["Close"]
        volume = enriched["Volume"]
        index = enriched.index

        calculations: dict[str, Callable[[], pd.Series]] = {
            "SMA_20": lambda: close.rolling(20, min_periods=20).mean(),
            "SMA_50": lambda: close.rolling(50, min_periods=50).mean(),
            "EMA_20": lambda: close.ewm(span=20, adjust=False, min_periods=20).mean(),
            "EMA_50": lambda: close.ewm(span=50, adjust=False, min_periods=50).mean(),
            "EMA_200": lambda: close.ewm(
                span=200, adjust=False, min_periods=200
            ).mean(),
            "RSI_14": lambda: self._rsi(close, 14),
        }
        for name, calculation in calculations.items():
            enriched[name] = self._safe_calculation(name, calculation, index)

        ema_12 = close.ewm(span=12, adjust=False, min_periods=12).mean()
        ema_26 = close.ewm(span=26, adjust=False, min_periods=26).mean()
        macd = ema_12 - ema_26
        macd_signal = macd.ewm(span=9, adjust=False, min_periods=9).mean()
        enriched["MACD"] = self._safe_calculation("MACD", lambda: macd, index)
        enriched["MACD_Signal"] = self._safe_calculation(
            "MACD_Signal", lambda: macd_signal, index
        )
        enriched["MACD_Histogram"] = self._safe_calculation(
            "MACD_Histogram", lambda: macd - macd_signal, index
        )

        true_range = self._true_range(enriched)
        enriched["ATR_14"] = self._safe_calculation(
            "ATR_14",
            lambda: true_range.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean(),
            index,
        )

        middle_band = close.rolling(20, min_periods=20).mean()
        standard_deviation = close.rolling(20, min_periods=20).std(ddof=0)
        enriched["Bollinger_Middle_20"] = self._safe_calculation(
            "Bollinger_Middle_20", lambda: middle_band, index
        )
        enriched["Bollinger_Upper_20"] = self._safe_calculation(
            "Bollinger_Upper_20",
            lambda: middle_band + (2.0 * standard_deviation),
            index,
        )
        enriched["Bollinger_Lower_20"] = self._safe_calculation(
            "Bollinger_Lower_20",
            lambda: middle_band - (2.0 * standard_deviation),
            index,
        )
        enriched["Volume_MA_20"] = self._safe_calculation(
            "Volume_MA_20",
            lambda: volume.rolling(20, min_periods=20).mean(),
            index,
        )
        return enriched

    @staticmethod
    def _validate_output(
        source: pd.DataFrame, enriched: pd.DataFrame
    ) -> tuple[int, int, list[str]]:
        if len(source) != len(enriched):
            raise IndicatorCalculationError("Row count changed during calculation")
        if not source["Date"].equals(enriched["Date"]):
            raise IndicatorCalculationError("Date alignment changed during calculation")

        missing_indicators = [
            column for column in INDICATOR_COLUMNS if column not in enriched
        ]
        if missing_indicators:
            raise IndicatorCalculationError(
                f"Missing calculated indicators: {', '.join(missing_indicators)}"
            )

        nulls_by_indicator = enriched[list(INDICATOR_COLUMNS)].isna().sum()
        total_nulls = int(nulls_by_indicator.sum())
        expected_nulls = sum(
            min(EXPECTED_WARMUP[column], len(enriched)) for column in INDICATOR_COLUMNS
        )
        unexpected_nulls = max(total_nulls - expected_nulls, 0)

        warnings: list[str] = []
        if len(enriched) < max(EXPECTED_WARMUP.values()) + 1:
            warnings.append("Dataset is too short to fully initialize every indicator")
        if unexpected_nulls:
            warnings.append(f"Found {unexpected_nulls} unexpected indicator null values")

        for column in INDICATOR_COLUMNS:
            first_valid = enriched[column].first_valid_index()
            if first_valid is None:
                continue
            if enriched.loc[first_valid:, column].isna().any():
                warnings.append(f"{column} contains nulls after its warm-up period")

        finite_values = enriched[list(INDICATOR_COLUMNS)].dropna(how="all")
        if np.isinf(finite_values.to_numpy(dtype=float)).any():
            raise IndicatorCalculationError("Indicator output contains infinite values")
        return total_nulls, unexpected_nulls, list(dict.fromkeys(warnings))

    def process_file(self, csv_path: Path) -> IndicatorResult:
        """Process one raw CSV and return a structured result."""
        ticker = csv_path.stem
        try:
            self.logger.info("Processing %s", csv_path)
            source = self._load_and_validate_input(csv_path)
            enriched = self.calculate_indicators(source)
            null_count, unexpected_nulls, warnings = self._validate_output(
                source, enriched
            )

            output_path = self.output_folder / f"{ticker}_indicators.csv"
            temporary_path = output_path.with_suffix(".csv.tmp")
            enriched.to_csv(temporary_path, index=False, date_format="%Y-%m-%d")
            temporary_path.replace(output_path)

            expected_nulls = sum(
                min(EXPECTED_WARMUP[column], len(enriched))
                for column in INDICATOR_COLUMNS
            )
            warning_text = "; ".join(warnings)
            if warning_text:
                self.logger.warning("%s: %s", ticker, warning_text)
            self.logger.info(
                "Completed %s: rows=%d, indicators=%d, nulls=%d, unexpected_nulls=%d, file=%s",
                ticker,
                len(enriched),
                len(INDICATOR_COLUMNS),
                null_count,
                unexpected_nulls,
                _display_path(output_path),
            )
            return IndicatorResult(
                ticker=ticker,
                status="success",
                row_count=len(enriched),
                indicator_count=len(INDICATOR_COLUMNS),
                null_count=null_count,
                expected_warmup_nulls=expected_nulls,
                unexpected_null_count=unexpected_nulls,
                date_alignment_valid=True,
                file_path=_display_path(output_path),
                warnings=warning_text,
            )
        except IndicatorEngineError as exc:
            self.logger.error("Indicator processing failed for %s: %s", ticker, exc)
            return IndicatorResult(ticker=ticker, status="failed", error=str(exc))
        except Exception as exc:
            self.logger.exception("Unexpected indicator failure for %s", ticker)
            return IndicatorResult(
                ticker=ticker,
                status="failed",
                error=f"Unexpected error: {type(exc).__name__}: {exc}",
            )


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def write_summary(results: list[IndicatorResult], summary_path: Path) -> None:
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [asdict(result) for result in results], columns=SUMMARY_COLUMNS
    ).to_csv(summary_path, index=False)


def write_report(
    results: list[IndicatorResult],
    input_files: list[Path],
    summary_path: Path,
    log_path: Path,
    report_path: Path,
) -> None:
    successful = [result for result in results if result.status == "success"]
    failed = [result for result in results if result.status == "failed"]
    warnings = [result for result in successful if result.warnings]
    generated_files = [result.file_path for result in successful]
    generated_files.extend(
        (_display_path(summary_path), _display_path(log_path), _display_path(report_path))
    )

    indicator_lines = "\n".join(f"- `{name}`" for name in INDICATOR_COLUMNS)
    file_lines = "\n".join(f"- `{path}`" for path in generated_files)
    validation_lines = "\n".join(
        f"- `{result.ticker}`: {result.row_count} rows, "
        f"{result.null_count} expected warm-up nulls, "
        f"{result.unexpected_null_count} unexpected nulls, alignment valid"
        for result in successful
    ) or "- None"
    failure_lines = "\n".join(
        f"- `{result.ticker}`: {result.error}" for result in failed
    ) or "- None"
    warning_lines = "\n".join(
        f"- `{result.ticker}`: {result.warnings}" for result in warnings
    ) or "- None"

    report = f"""# Technical Indicator Engine Report

## Execution Summary

- Input CSV files: {len(input_files)}
- Successful files: {len(successful)}
- Failed files: {len(failed)}
- Indicators per successful file: {len(INDICATOR_COLUMNS)}
- Total enriched rows: {sum(result.row_count for result in successful)}
- Unexpected indicator nulls: {sum(result.unexpected_null_count for result in successful)}

## Indicators Created

{indicator_lines}

## Formulas Used

- SMA(n): arithmetic mean of Close over the last n observations.
- EMA(n): exponentially weighted mean of Close with span n.
- RSI(14): Wilder-smoothed average gains and losses, converted to a 0-100 oscillator.
- MACD: EMA(12) minus EMA(26).
- MACD Signal: EMA(9) of MACD.
- MACD Histogram: MACD minus MACD Signal.
- True Range: maximum of High-Low, absolute High-previous Close, and absolute Low-previous Close.
- ATR(14): Wilder-smoothed True Range over 14 observations.
- Bollinger Middle(20): SMA(20) of Close.
- Bollinger Upper/Lower: middle band plus/minus two population standard deviations of Close.
- Volume MA(20): arithmetic mean of Volume over the last 20 observations.

## Files Generated

{file_lines}

## Validation Results

{validation_lines}

Validation checks cover required OHLCV columns, numeric source data, ascending unique dates,
row/date alignment, all requested indicator columns, infinite values, and nulls appearing
after each indicator's expected warm-up period.

## Warnings

{warning_lines}

## Failed Files

{failure_lines}
"""
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Calculate and validate technical indicators for raw OHLCV CSV files."
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
        input_files = sorted(input_folder.glob("*.csv"))
        if not input_files:
            raise InputValidationError(f"No CSV files found in {input_folder}")

        logger.info(
            "Starting indicator run: files=%d, input=%s, output=%s",
            len(input_files),
            input_folder,
            args.output_folder.resolve(),
        )
        engine = TechnicalIndicatorEngine(args.output_folder, logger)
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
        warning_count = sum(bool(result.warnings) for result in results)
        logger.info(
            "Indicator run finished: successful=%d, failed=%d, warnings=%d",
            successful,
            failed,
            warning_count,
        )
        print(f"Successful files: {successful}")
        print(f"Failed files: {failed}")
        print(f"Files with warnings: {warning_count}")
        print(f"Summary: {_display_path(args.summary.resolve())}")
        print(f"Report: {_display_path(args.report.resolve())}")
        print(f"Log: {_display_path(args.log_file.resolve())}")
        return 0 if successful and not failed else 1
    except Exception as exc:
        logger.exception("Indicator run could not be completed")
        print(f"Fatal indicator error: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
