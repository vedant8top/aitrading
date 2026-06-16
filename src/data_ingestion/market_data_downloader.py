"""Reusable historical market data ingestion framework."""

from __future__ import annotations

import argparse
import json
import logging
import re
import time
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Sequence

import pandas as pd
import yfinance as yf


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "stocks.json"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "raw"
DEFAULT_SUMMARY_PATH = PROJECT_ROOT / "data" / "download_summary.csv"
DEFAULT_LOG_PATH = PROJECT_ROOT / "logs" / "data_ingestion.log"
DEFAULT_REPORT_PATH = PROJECT_ROOT / "docs" / "data_ingestion_report.md"
REQUIRED_COLUMNS = ("Open", "High", "Low", "Close", "Volume")
SUMMARY_COLUMNS = (
    "ticker",
    "status",
    "row_count",
    "start_date",
    "end_date",
    "missing_values",
    "missing_values_by_column",
    "duplicate_dates_removed",
    "file_path",
    "error",
)


class MarketDataError(RuntimeError):
    """Base exception for ingestion failures."""


class InvalidTickerError(MarketDataError):
    """Raised when a ticker is malformed or rejected by the provider."""


class NetworkDataError(MarketDataError):
    """Raised when repeated provider requests fail."""


class EmptyDatasetError(MarketDataError):
    """Raised when the provider returns no historical rows."""


class DataValidationError(MarketDataError):
    """Raised when downloaded data does not satisfy the expected schema."""


@dataclass(frozen=True)
class DownloadResult:
    ticker: str
    status: str
    row_count: int = 0
    start_date: str = ""
    end_date: str = ""
    missing_values: int = 0
    missing_values_by_column: str = "{}"
    duplicate_dates_removed: int = 0
    file_path: str = ""
    error: str = ""


def configure_logging(log_path: Path) -> logging.Logger:
    """Configure console and rotating-file logging for ingestion runs."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("market_data_ingestion")
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


def load_tickers(config_path: Path) -> list[str]:
    """Load and validate a unique ticker list from a JSON configuration."""
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Configuration file not found: {config_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {config_path}: {exc}") from exc

    stocks = payload.get("stocks") if isinstance(payload, dict) else None
    if not isinstance(stocks, list) or not stocks:
        raise ValueError("Configuration must contain a non-empty 'stocks' list")

    tickers: list[str] = []
    seen: set[str] = set()
    for value in stocks:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Every configured ticker must be a non-empty string")
        ticker = value.strip().upper()
        if ticker not in seen:
            tickers.append(ticker)
            seen.add(ticker)
    return tickers


class MarketDataDownloader:
    """Download, validate, clean, and persist daily market data."""

    def __init__(
        self,
        output_folder: Path | str,
        logger: logging.Logger,
        retries: int = 3,
        retry_delay: float = 2.0,
    ) -> None:
        if retries < 1:
            raise ValueError("retries must be at least 1")
        self.output_folder = Path(output_folder).resolve()
        self.output_folder.mkdir(parents=True, exist_ok=True)
        self.logger = logger
        self.retries = retries
        self.retry_delay = retry_delay

    @staticmethod
    def _validate_ticker(ticker: str) -> str:
        normalized = ticker.strip().upper()
        if not normalized or not re.fullmatch(r"[A-Z0-9.^=\-]+", normalized):
            raise InvalidTickerError(f"Invalid ticker format: {ticker!r}")
        return normalized

    @staticmethod
    def _parse_dates(start_date: str, end_date: str) -> tuple[pd.Timestamp, pd.Timestamp]:
        try:
            start = pd.Timestamp(start_date)
            end = pd.Timestamp(end_date)
        except (TypeError, ValueError) as exc:
            raise ValueError("Dates must use a valid YYYY-MM-DD format") from exc
        if start.tz is not None:
            start = start.tz_localize(None)
        if end.tz is not None:
            end = end.tz_localize(None)
        if start >= end:
            raise ValueError("start date must be earlier than end date")
        return start.normalize(), end.normalize()

    @staticmethod
    def _filename(ticker: str) -> str:
        safe_ticker = re.sub(r"[^A-Z0-9]+", "_", ticker).strip("_")
        return f"{safe_ticker}.csv"

    def _request_data(
        self, ticker: str, start: pd.Timestamp, end: pd.Timestamp
    ) -> pd.DataFrame:
        last_error: Exception | None = None
        for attempt in range(1, self.retries + 1):
            try:
                self.logger.info(
                    "Downloading %s from %s to %s (attempt %d/%d)",
                    ticker,
                    start.date(),
                    end.date(),
                    attempt,
                    self.retries,
                )
                data = yf.download(
                    ticker,
                    start=start.date().isoformat(),
                    end=end.date().isoformat(),
                    interval="1d",
                    auto_adjust=False,
                    actions=False,
                    progress=False,
                    threads=False,
                    timeout=30,
                    multi_level_index=False,
                )
                if data is None or data.empty:
                    raise EmptyDatasetError(
                        f"No data returned for {ticker}; ticker may be invalid"
                    )
                return data
            except EmptyDatasetError:
                raise
            except Exception as exc:
                last_error = exc
                self.logger.warning(
                    "Provider request failed for %s on attempt %d: %s",
                    ticker,
                    attempt,
                    exc,
                )
                if attempt < self.retries:
                    time.sleep(self.retry_delay * attempt)
        raise NetworkDataError(
            f"Network/provider failure for {ticker} after {self.retries} attempts: "
            f"{last_error}"
        ) from last_error

    @staticmethod
    def _clean_data(data: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int], int]:
        if isinstance(data.columns, pd.MultiIndex):
            data = data.copy()
            data.columns = data.columns.get_level_values(0)

        missing_columns = [column for column in REQUIRED_COLUMNS if column not in data]
        if missing_columns:
            raise DataValidationError(
                f"Downloaded data is missing required columns: {missing_columns}"
            )

        columns = [
            column
            for column in ("Open", "High", "Low", "Close", "Adj Close", "Volume")
            if column in data.columns
        ]
        cleaned = data.loc[:, columns].copy()
        cleaned.index = pd.to_datetime(cleaned.index, errors="coerce", utc=True)
        invalid_dates = int(cleaned.index.isna().sum())
        if invalid_dates:
            cleaned = cleaned[~cleaned.index.isna()]
        cleaned.index = cleaned.index.tz_localize(None)
        cleaned.index.name = "Date"

        missing_by_column = {
            column: int(count) for column, count in cleaned.isna().sum().items()
        }
        duplicate_count = int(cleaned.index.duplicated(keep="last").sum())
        cleaned = cleaned[~cleaned.index.duplicated(keep="last")]
        cleaned = cleaned.dropna(subset=list(REQUIRED_COLUMNS)).sort_index()

        if cleaned.empty:
            raise EmptyDatasetError("No valid rows remain after data cleaning")
        if not cleaned.index.is_monotonic_increasing:
            raise DataValidationError("Dates could not be sorted in ascending order")
        return cleaned, missing_by_column, duplicate_count

    def download_ticker(
        self, ticker: str, start_date: str, end_date: str
    ) -> DownloadResult:
        """Download one ticker and return a structured success/failure result."""
        requested_ticker = ticker
        try:
            normalized = self._validate_ticker(ticker)
            start, end = self._parse_dates(start_date, end_date)
            raw_data = self._request_data(normalized, start, end)
            cleaned, missing_by_column, duplicate_count = self._clean_data(raw_data)

            output_path = self.output_folder / self._filename(normalized)
            temporary_path = output_path.with_suffix(".csv.tmp")
            cleaned.to_csv(temporary_path, date_format="%Y-%m-%d")
            temporary_path.replace(output_path)

            result = DownloadResult(
                ticker=normalized,
                status="success",
                row_count=len(cleaned),
                start_date=cleaned.index.min().date().isoformat(),
                end_date=cleaned.index.max().date().isoformat(),
                missing_values=sum(missing_by_column.values()),
                missing_values_by_column=json.dumps(missing_by_column, sort_keys=True),
                duplicate_dates_removed=duplicate_count,
                file_path=_display_path(output_path),
            )
            self.logger.info(
                "Completed %s: rows=%d, range=%s to %s, missing=%d, duplicates=%d, file=%s",
                normalized,
                result.row_count,
                result.start_date,
                result.end_date,
                result.missing_values,
                duplicate_count,
                result.file_path,
            )
            return result
        except (InvalidTickerError, EmptyDatasetError, DataValidationError) as exc:
            self.logger.error("Data failure for %s: %s", requested_ticker, exc)
            return DownloadResult(
                ticker=requested_ticker, status="failed", error=str(exc)
            )
        except NetworkDataError as exc:
            self.logger.error("Network failure for %s: %s", requested_ticker, exc)
            return DownloadResult(
                ticker=requested_ticker, status="failed", error=str(exc)
            )
        except Exception as exc:
            self.logger.exception("Unexpected failure for %s", requested_ticker)
            return DownloadResult(
                ticker=requested_ticker,
                status="failed",
                error=f"Unexpected error: {type(exc).__name__}: {exc}",
            )


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def write_summary(results: Sequence[DownloadResult], summary_path: Path) -> None:
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    rows = [asdict(result) for result in results]
    pd.DataFrame(rows, columns=SUMMARY_COLUMNS).to_csv(summary_path, index=False)


def write_markdown_report(
    results: Sequence[DownloadResult],
    start_date: str,
    end_date: str,
    summary_path: Path,
    log_path: Path,
    report_path: Path,
) -> None:
    successful = [result for result in results if result.status == "success"]
    failed = [result for result in results if result.status == "failed"]
    total_rows = sum(result.row_count for result in successful)
    total_missing = sum(result.missing_values for result in successful)
    average_rows = total_rows / len(successful) if successful else 0.0
    files = [result.file_path for result in successful]
    files.extend(
        (
            _display_path(summary_path),
            _display_path(log_path),
            _display_path(report_path),
        )
    )

    file_lines = "\n".join(f"- `{path}`" for path in files)
    success_lines = "\n".join(
        f"- `{result.ticker}`: {result.row_count} rows, "
        f"{result.start_date} to {result.end_date}, "
        f"{result.missing_values} missing values"
        for result in successful
    ) or "- None"
    failure_lines = "\n".join(
        f"- `{result.ticker}`: {result.error}" for result in failed
    ) or "- None"

    report = f"""# Data Ingestion Report

## Run Summary

- Requested date range: {start_date} to {end_date} (end date exclusive)
- Tickers requested: {len(results)}
- Successful downloads: {len(successful)}
- Failed downloads: {len(failed)}
- Total rows saved: {total_rows}
- Missing values reported before required-row cleaning: {total_missing}

## Files Created

{file_lines}

## Successful Downloads

{success_lines}

## Failed Downloads

{failure_lines}

## Summary Statistics

- Average rows per successful ticker: {average_rows:.1f}
- Summary CSV: `{_display_path(summary_path)}`
- Detailed log: `{_display_path(log_path)}`
"""
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    today = date.today()
    parser = argparse.ArgumentParser(
        description="Download and validate daily historical market data."
    )
    parser.add_argument(
        "--ticker",
        action="append",
        help="Ticker to download; repeat for multiple tickers. Overrides --config.",
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--start", default=(today - timedelta(days=365)).isoformat())
    parser.add_argument("--end", default=today.isoformat())
    parser.add_argument("--output-folder", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY_PATH)
    parser.add_argument("--log-file", type=Path, default=DEFAULT_LOG_PATH)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--retries", type=int, default=3)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logger = configure_logging(args.log_file.resolve())
    try:
        tickers = args.ticker or load_tickers(args.config.resolve())
        downloader = MarketDataDownloader(
            args.output_folder, logger=logger, retries=args.retries
        )
        logger.info(
            "Starting ingestion run: tickers=%d, start=%s, end=%s, output=%s",
            len(tickers),
            args.start,
            args.end,
            downloader.output_folder,
        )
        results = [
            downloader.download_ticker(ticker, args.start, args.end)
            for ticker in tickers
        ]
        write_summary(results, args.summary.resolve())
        write_markdown_report(
            results,
            args.start,
            args.end,
            args.summary.resolve(),
            args.log_file.resolve(),
            args.report.resolve(),
        )
        succeeded = sum(result.status == "success" for result in results)
        failed = len(results) - succeeded
        logger.info(
            "Ingestion run finished: successful=%d, failed=%d, summary=%s, report=%s",
            succeeded,
            failed,
            _display_path(args.summary.resolve()),
            _display_path(args.report.resolve()),
        )
        print(f"Successful downloads: {succeeded}")
        print(f"Failed downloads: {failed}")
        print(f"Summary: {_display_path(args.summary.resolve())}")
        print(f"Report: {_display_path(args.report.resolve())}")
        print(f"Log: {_display_path(args.log_file.resolve())}")
        return 0 if succeeded else 1
    except Exception as exc:
        logger.exception("Ingestion run could not be completed")
        print(f"Fatal ingestion error: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
