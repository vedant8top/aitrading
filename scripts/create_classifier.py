"""Generate regime_classifier.py."""
import os

os.makedirs("src/regime_detection", exist_ok=True)

code = r'''"""Market regime classification using ADX, ATR ratio, breadth, and correlation."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RAW_DIR = PROJECT_ROOT / "data" / "raw"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "regimes"
DEFAULT_LOG_PATH = PROJECT_ROOT / "logs" / "regime_classifier.log"

MIN_DAYS_FOR_REGIME = 5
ADX_PERIOD = 14
ATR_SHORT_PERIOD = 20
ATR_LONG_PERIOD = 100
CORRELATION_WINDOW = 20

# Thresholds
ADX_TRENDING_ENTER = 25
ADX_TRENDING_EXIT = 20
ADX_RANGE_ENTER = 20
ADX_RANGE_EXIT = 25
ATR_RATIO_VOLATILE_ENTER = 1.5
ATR_RATIO_VOLATILE_EXIT = 1.2
CORRELATION_VOLATILE_ENTER = 0.7
CORRELATION_VOLATILE_EXIT = 0.6
BREADTH_TRENDING_ENTER = 0.55
BREADTH_TRENDING_EXIT = 0.50
BREADTH_RANGE_LOW = 0.40
BREADTH_RANGE_HIGH = 0.60


class Regime(str, Enum):
    """Market regime classification."""
    TRENDING = "TRENDING"
    RANGE_BOUND = "RANGE_BOUND"
    VOLATILE = "VOLATILE"
    UNCERTAIN = "UNCERTAIN"


@dataclass
class RegimeIndicators:
    """Container for regime classification indicators."""
    date: pd.Timestamp
    adx: float
    atr_ratio: float
    breadth: float
    correlation: float
    regime: Regime


def configure_logging(log_path: Path) -> logging.Logger:
    """Configure console and rotating file logging."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("regime_classifier")
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


class RegimeClassifier:
    """Classify daily market regime using multiple indicators."""

    def __init__(
        self,
        raw_data_dir: Path | str = DEFAULT_RAW_DIR,
        output_dir: Path | str = DEFAULT_OUTPUT_DIR,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.raw_data_dir = Path(raw_data_dir).resolve()
        self.output_dir = Path(output_dir).resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logger or configure_logging(DEFAULT_LOG_PATH)
        self._stocks: list[str] = []
        self._nifty_proxy: Optional[pd.Series] = None
        self._all_returns: Optional[pd.DataFrame] = None

    def _load_stock_data(self) -> dict[str, pd.DataFrame]:
        """Load all stock CSV files from raw data directory."""
        csv_files = sorted(self.raw_data_dir.glob("*_NS.csv"))
        if not csv_files:
            raise FileNotFoundError(
                f"No stock CSV files found in {self.raw_data_dir}"
            )

        stocks: dict[str, pd.DataFrame] = {}
        for csv_path in csv_files:
            ticker = csv_path.stem
            df = pd.read_csv(csv_path, parse_dates=["Date"])
            df = df.sort_values("Date").reset_index(drop=True)
            stocks[ticker] = df

        self.logger.info("Loaded %d stock files from %s", len(stocks), self.raw_data_dir)
        return stocks

    def _build_nifty_proxy(self, stocks: dict[str, pd.DataFrame]) -> pd.Series:
        """Build equal-weight NIFTY 50 proxy from constituent stocks."""
        close_dfs = []
        for ticker, df in stocks.items():
            s = df[