"""Validate the market-data-to-CSV-to-chart pipeline."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
import yfinance as yf


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
REPORT_PATH = PROJECT_ROOT / "docs" / "market_data_validation.md"
CHART_PATH = DATA_DIR / "nifty_1y_chart.png"
SYMBOLS = (
    ("^NSEI", "NIFTY 50", DATA_DIR / "nifty_1y.csv"),
    ("RELIANCE.NS", "Reliance Industries", DATA_DIR / "reliance_1y.csv"),
)
REQUIRED_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]


def download_market_data() -> tuple[str, str, Path, pd.DataFrame, list[str]]:
    """Download one year of daily data, using Reliance as a fallback."""
    errors: list[str] = []

    for symbol, name, csv_path in SYMBOLS:
        print(f"Downloading 1 year of daily data for {name} ({symbol})...")
        try:
            data = yf.download(
                symbol,
                period="1y",
                interval="1d",
                auto_adjust=False,
                progress=False,
                threads=False,
                timeout=30,
            )
            if data.empty:
                raise ValueError("download returned no rows")

            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)

            missing_columns = [
                column for column in REQUIRED_COLUMNS if column not in data.columns
            ]
            if missing_columns:
                raise ValueError(f"missing required columns: {missing_columns}")

            return symbol, name, csv_path, data, errors
        except Exception as exc:  # Continue to the explicitly requested fallback.
            message = f"{symbol}: {type(exc).__name__}: {exc}"
            errors.append(message)
            print(f"Download failed: {message}")

    raise RuntimeError("All market data downloads failed: " + " | ".join(errors))


def clean_data(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, int]:
    """Normalize the date index and remove incomplete or duplicate rows."""
    selected = data[REQUIRED_COLUMNS].copy()
    selected.index = pd.to_datetime(selected.index, utc=True).tz_localize(None)
    selected.index.name = "Date"
    selected = selected.sort_index()

    missing_before = selected.isna().sum()
    duplicate_count = int(selected.index.duplicated(keep="last").sum())
    cleaned = selected[~selected.index.duplicated(keep="last")].dropna()
    return cleaned, missing_before, duplicate_count


def create_chart(data: pd.DataFrame, name: str, symbol: str) -> None:
    """Save a Close-price chart without opening an interactive window."""
    figure, axis = plt.subplots(figsize=(12, 6))
    axis.plot(data.index, data["Close"], color="tab:blue", linewidth=1.5)
    axis.set_title(f"{name} ({symbol}) - Daily Close Price (1 Year)")
    axis.set_xlabel("Date")
    axis.set_ylabel("Close Price")
    axis.grid(True, alpha=0.3)
    figure.autofmt_xdate()
    figure.tight_layout()
    figure.savefig(CHART_PATH, dpi=150)
    plt.close(figure)


def create_report(
    symbol: str,
    name: str,
    data: pd.DataFrame,
    missing_before: pd.Series,
    duplicate_count: int,
    csv_path: Path,
    errors: list[str],
) -> None:
    """Write a compact report containing results from this execution."""
    missing_lines = "\n".join(
        f"- `{column}`: {int(count)}" for column, count in missing_before.items()
    )
    error_lines = "\n".join(f"- `{error}`" for error in errors) or "- None"
    report = f"""# Market Data Validation

## Result

- Instrument: {name} (`{symbol}`)
- Rows downloaded after cleaning: {len(data)}
- Date range: {data.index.min().date()} to {data.index.max().date()}
- Duplicate dates removed: {duplicate_count}
- Pipeline status: Successful

## Missing Values Before Cleaning

{missing_lines}

## Output Files

- CSV: `{csv_path.relative_to(PROJECT_ROOT).as_posix()}`
- Chart: `{CHART_PATH.relative_to(PROJECT_ROOT).as_posix()}`
- Report: `{REPORT_PATH.relative_to(PROJECT_ROOT).as_posix()}`

## Download Errors

{error_lines}
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    symbol, name, csv_path, raw_data, errors = download_market_data()
    cleaned, missing_before, duplicate_count = clean_data(raw_data)
    if cleaned.empty:
        raise RuntimeError("No complete rows remain after cleaning")

    print("\nValidation results")
    print("------------------")
    print(f"Instrument: {name} ({symbol})")
    print(f"Raw row count: {len(raw_data)}")
    print(f"Cleaned row count: {len(cleaned)}")
    print(f"Date range: {cleaned.index.min().date()} to {cleaned.index.max().date()}")
    print(f"Duplicate dates removed: {duplicate_count}")
    print("Missing values before cleaning:")
    print(missing_before.to_string())
    print(f"Missing values after cleaning: {int(cleaned.isna().sum().sum())}")
    print("\nFirst 5 rows:")
    print(cleaned.head().to_string())
    print("\nLast 5 rows:")
    print(cleaned.tail().to_string())

    cleaned.to_csv(csv_path, date_format="%Y-%m-%d")
    create_chart(cleaned, name, symbol)
    create_report(
        symbol,
        name,
        cleaned,
        missing_before,
        duplicate_count,
        csv_path,
        errors,
    )

    print("\nOutput verification")
    print("-------------------")
    for output_path in (csv_path, CHART_PATH, REPORT_PATH):
        exists = output_path.is_file() and output_path.stat().st_size > 0
        print(f"{output_path.relative_to(PROJECT_ROOT)}: {'OK' if exists else 'MISSING'}")
        if not exists:
            raise RuntimeError(f"Expected output was not created: {output_path}")
    print("Market data pipeline validation completed successfully.")


if __name__ == "__main__":
    main()
