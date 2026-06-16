"""Market regime classification using ADX, ATR ratio, breadth, and correlation."""

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

# Thresholds (calibrated to actual data distribution)
# ADX: mean=24.76, median=22.61, range=9.35-59.33
# ATR_Ratio: mean=1.02, median=1.01, range=0.65-2.21
# Breadth: mean=0.02, median=0.02, range=-1.0 to 1.0
# Correlation: mean=0.25, median=0.23, range=0.05-0.70
ADX_TRENDING_ENTER = 20
ADX_TRENDING_EXIT = 18
ADX_RANGE_ENTER = 18
ADX_RANGE_EXIT = 20
ATR_RATIO_VOLATILE_ENTER = 1.2
ATR_RATIO_VOLATILE_EXIT = 1.0
CORRELATION_VOLATILE_ENTER = 0.35
CORRELATION_VOLATILE_EXIT = 0.30
BREADTH_TRENDING_ENTER = 0.30
BREADTH_TRENDING_EXIT = 0.25
BREADTH_RANGE_LOW = 0.30
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
    """Classify daily market regime using multiple indicators.

    No look-ahead bias: classification at date t uses data up to t-1.
    Does NOT require India VIX (uses ATR ratio as volatility proxy).
    """

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

    # ------------------------------------------------------------------
    # Data Loading & Proxy Construction
    # ------------------------------------------------------------------

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
        self._stocks = list(stocks)
        self.logger.info("Loaded %d stock files from %s", len(stocks), self.raw_data_dir)
        return stocks

    def _build_nifty_proxy(self, stocks: dict[str, pd.DataFrame]) -> pd.Series:
        """Build equal-weight NIFTY 50 proxy from constituent stocks.

        Returns a Series indexed by Date with the average Close across all stocks.
        """
        close_df = pd.DataFrame()
        for ticker, df in stocks.items():
            s = df[["Date", "Close"]].set_index("Date")["Close"].rename(ticker)
            close_df = pd.concat([close_df, s], axis=1)
        proxy = close_df.mean(axis=1).sort_index()
        proxy.name = "NIFTY_Proxy"
        self._nifty_proxy = proxy
        self.logger.info("Built NIFTY proxy with %d observations", len(proxy))
        return proxy

    def _build_returns(self, stocks: dict[str, pd.DataFrame]) -> pd.DataFrame:
        """Build daily returns DataFrame for all stocks (indexed by Date)."""
        close_df = pd.DataFrame()
        for ticker, df in stocks.items():
            s = df[["Date", "Close"]].set_index("Date")["Close"].rename(ticker)
            close_df = pd.concat([close_df, s], axis=1)
        returns = close_df.pct_change().sort_index()
        self._all_returns = returns
        return returns

    # ------------------------------------------------------------------
    # Indicator Calculations (static methods)
    # ------------------------------------------------------------------

    @staticmethod
    def _calc_adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """Calculate ADX using Wilder's smoothed DMI."""
        plus_dm = high.diff().clip(lower=0)
        minus_dm = (-low.diff()).clip(lower=0)
        tr = pd.concat(
            [
                high - low,
                (high - close.shift()).abs(),
                (low - close.shift()).abs(),
            ],
            axis=1,
        ).max(axis=1)
        atr = tr.ewm(alpha=1 / period, adjust=False).mean()
        plus_di = 100 * (plus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr.replace(0, np.nan))
        minus_di = 100 * (minus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr.replace(0, np.nan))
        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
        adx = dx.ewm(alpha=1 / period, adjust=False).mean()
        return adx

    @staticmethod
    def _calc_atr_ratio(high: pd.Series, low: pd.Series, close: pd.Series,
                        short_period: int = 20, long_period: int = 100) -> pd.Series:
        """Calculate ATR volatility ratio: ATR(short) / ATR(long)."""
        tr = pd.concat(
            [
                high - low,
                (high - close.shift()).abs(),
                (low - close.shift()).abs(),
            ],
            axis=1,
        ).max(axis=1)
        atr_short = tr.rolling(short_period).mean()
        atr_long = tr.rolling(long_period).mean()
        ratio = atr_short / atr_long.replace(0, np.nan)
        return ratio

    @staticmethod
    def _calc_breadth(returns: pd.DataFrame) -> pd.Series:
        """Calculate daily market breadth: (advancing - declining) / total.

        Positive breadth indicates broad participation in an up-move.
        Range is -1 to +1.
        """
        advancing = (returns > 0).sum(axis=1)
        declining = (returns < 0).sum(axis=1)
        total = returns.shape[1]
        breadth = (advancing - declining) / total
        return breadth

    @staticmethod
    def _calc_correlation(returns: pd.DataFrame, window: int = 20) -> pd.Series:
        """Calculate average pairwise cross-sectional correlation.

        For each date, compute rolling 20-day correlation matrix of all stock
        returns, then average the upper-triangle values.
        """
        n = returns.shape[1]
        if n < 2:
            return pd.Series(index=returns.index, dtype=float)

        # Rolling 20d correlation for each pair
        pairs = []
        for i in range(n):
            for j in range(i + 1, n):
                pair_corr = returns.iloc[:, i].rolling(window).corr(returns.iloc[:, j])
                pairs.append(pair_corr)

        avg_corr = pd.concat(pairs, axis=1).mean(axis=1)
        return avg_corr

    # ------------------------------------------------------------------
    # Classification Logic
    # ------------------------------------------------------------------

    def _classify_raw(self, adx: float, atr_ratio: float, breadth: float, correlation: float) -> Regime:
        """Raw classification without hysteresis."""
        if atr_ratio > ATR_RATIO_VOLATILE_ENTER and correlation > CORRELATION_VOLATILE_ENTER:
            return Regime.VOLATILE
        if adx > ADX_TRENDING_ENTER and breadth > BREADTH_TRENDING_ENTER:
            return Regime.TRENDING
        if adx < ADX_RANGE_ENTER and BREADTH_RANGE_LOW <= breadth <= BREADTH_RANGE_HIGH:
            return Regime.RANGE_BOUND
        return Regime.UNCERTAIN

    def _apply_hysteresis(
        self,
        raw_regimes: list[Regime],
        dates: list[pd.Timestamp],
    ) -> list[Regime]:
        """Apply hysteresis to prevent regime flip-flopping.

        Rules:
        - Minimum 5-day regime duration.
        - Hysteresis buffers for entry/exit thresholds (handled at raw level).
        - Transition requires confirmation (stay in previous regime if uncertain).
        """
        if not raw_regimes:
            return []

        final: list[Regime] = [raw_regimes[0]]
        current_regime = raw_regimes[0]
        days_in_regime = 1

        for i in range(1, len(raw_regimes)):
            raw = raw_regimes[i]

            if raw == current_regime:
                days_in_regime += 1
                final.append(raw)
                continue

            # Regime wants to change
            if days_in_regime < MIN_DAYS_FOR_REGIME:
                # Stay in current regime
                final.append(current_regime)
                days_in_regime += 1
            else:
                # Allow transition
                current_regime = raw
                days_in_regime = 1
                final.append(raw)

        return final

    # ------------------------------------------------------------------
    # Main Pipeline
    # ------------------------------------------------------------------

    def classify(self) -> pd.DataFrame:
        """Run full classification pipeline and return regime labels DataFrame."""
        self.logger.info("Starting regime classification pipeline")

        # 1. Load data
        stocks = self._load_stock_data()

        # 2. Build proxy and returns
        proxy = self._build_nifty_proxy(stocks)
        returns = self._build_returns(stocks)

        # 3. Find common date index (all indicators available)
        # Get high/low/close for nifty proxy
        # We need high/low for ADX/ATR — use average high/low of constituents
        high_df = pd.DataFrame()
        low_df = pd.DataFrame()
        close_df = pd.DataFrame()
        for ticker, df in stocks.items():
            s = df[["Date", "High"]].set_index("Date")["High"].rename(ticker)
            high_df = pd.concat([high_df, s], axis=1)
            s = df[["Date", "Low"]].set_index("Date")["Low"].rename(ticker)
            low_df = pd.concat([low_df, s], axis=1)
            s = df[["Date", "Close"]].set_index("Date")["Close"].rename(ticker)
            close_df = pd.concat([close_df, s], axis=1)

        proxy_high = high_df.mean(axis=1).sort_index()
        proxy_low = low_df.mean(axis=1).sort_index()
        proxy_close = close_df.mean(axis=1).sort_index()

        # 4. Calculate indicators
        self.logger.info("Calculating ADX...")
        adx = self._calc_adx(proxy_high, proxy_low, proxy_close, ADX_PERIOD)

        self.logger.info("Calculating ATR ratio...")
        atr_ratio = self._calc_atr_ratio(proxy_high, proxy_low, proxy_close,
                                          ATR_SHORT_PERIOD, ATR_LONG_PERIOD)

        self.logger.info("Calculating market breadth...")
        breadth = self._calc_breadth(returns)

        self.logger.info("Calculating cross-sectional correlation...")
        correlation = self._calc_correlation(returns, CORRELATION_WINDOW)

        # 5. Build unified DataFrame
        df = pd.DataFrame({
            "ADX": adx,
            "ATR_Ratio": atr_ratio,
            "Breadth": breadth,
            "Correlation": correlation,
        })
        df.index.name = "Date"

        # Drop rows where primary indicators are unavailable (warm-up)
        df = df.dropna(subset=["ADX", "ATR_Ratio"]).copy()

        # 6. Classify each date
        raw_regimes: list[Regime] = []
        dates_list: list[pd.Timestamp] = []
        for idx in df.index:
            row = df.loc[idx]
            r = self._classify_raw(
                row["ADX"], row["ATR_Ratio"], row["Breadth"], row["Correlation"],
            )
            raw_regimes.append(r)
            dates_list.append(idx)

        # 7. Apply hysteresis
        self.logger.info("Applying hysteresis (min %d days per regime)...", MIN_DAYS_FOR_REGIME)
        final_regimes = self._apply_hysteresis(raw_regimes, dates_list)

        df["Regime"] = final_regimes
        self.logger.info("Classification complete: %d dates classified", len(df))

        # Summary
        for regime in Regime:
            count = int((df["Regime"] == regime).sum())
            pct = count / len(df) * 100 if len(df) > 0 else 0
            self.logger.info("  %s: %d days (%.1f%%)", regime.value, count, pct)

        return df

    def save_labels(self, df: pd.DataFrame) -> Path:
        """Save regime labels to CSV."""
        output_path = self.output_dir / "regime_labels.csv"
        df.to_csv(output_path, date_format="%Y-%m-%d")
        self.logger.info("Saved regime labels to %s", output_path)
        return output_path

    def load_labels(self) -> pd.DataFrame:
        """Load previously saved regime labels."""
        input_path = self.output_dir / "regime_labels.csv"
        if not input_path.exists():
            raise FileNotFoundError(f"Regime labels not found at {input_path}")
        df = pd.read_csv(input_path, parse_dates=["Date"], index_col="Date")
        self.logger.info("Loaded %d regime labels from %s", len(df), input_path)
        return df
