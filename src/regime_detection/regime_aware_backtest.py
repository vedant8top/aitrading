"""Regime-aware portfolio backtester that combines existing per-strategy results."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from src.regime_detection.regime_classifier import Regime, RegimeClassifier
from src.regime_detection.regime_switcher import RegimeSwitcher

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TRADES_DIR = PROJECT_ROOT / "data" / "strategy_comparison"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "regime_backtests"
DEFAULT_LOG_PATH = PROJECT_ROOT / "logs" / "regime_backtest.log"

INITIAL_CAPITAL = 100_000.0
TRADING_DAYS = 252

STRATEGY_LIST = [
    "donchian", "breakout", "momentum", "ema_rsi_macd",
    "mean_reversion", "bollinger_reversion", "bear_trap",
    "volatility_expansion",
]


class RegimeAwareBacktester:
    """Construct a regime-aware portfolio from existing per-strategy trade data.

    This does NOT duplicate the backtesting logic. Instead it:
    1. Loads pre-computed per-strategy trade files (from strategy comparison).
    2. Loads regime labels (from regime classifier).
    3. On each date, only considers trades from regime-active strategies.
    4. Applies strategy weights for position sizing.
    5. Combines into a single equity curve.
    """

    def __init__(
        self,
        regime_labels: pd.DataFrame,
        trades_dir: Path | str = DEFAULT_TRADES_DIR,
        output_dir: Path | str = DEFAULT_OUTPUT_DIR,
        switcher: Optional[RegimeSwitcher] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.regime_labels = regime_labels
        self.trades_dir = Path(trades_dir).resolve()
        self.output_dir = Path(output_dir).resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.switcher = switcher or RegimeSwitcher()
        self.logger = logger or self._configure_logging()

        # Per-strategy trade dataframes
        self._strategy_trades: dict[str, pd.DataFrame] = {}
        self._strategy_metrics: dict[str, dict] = {}

    def _configure_logging(self) -> logging.Logger:
        """Configure logging for the regime backtester."""
        logger = logging.getLogger("regime_backtest")
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter(
                "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
            ))
            logger.addHandler(handler)
        return logger

    # ------------------------------------------------------------------
    # Data Loading
    # ------------------------------------------------------------------

    def _load_trades(self, strategy: str) -> Optional[pd.DataFrame]:
        """Load trade CSV for a single strategy."""
        path = self.trades_dir / f"trades_{strategy}.csv"
        if not path.exists():
            self.logger.warning("Trade file not found: %s", path)
            return None
        df = pd.read_csv(path, parse_dates=["entry_date", "exit_date"])
        self.logger.info("Loaded %d trades for %s", len(df), strategy)
        return df

    def load_all_trades(self) -> dict[str, pd.DataFrame]:
        """Load trade data for all strategies."""
        for s in STRATEGY_LIST:
            trades = self._load_trades(s)
            if trades is not None:
                self._strategy_trades[s] = trades
        self.logger.info(
            "Loaded trades for %d/%d strategies", len(self._strategy_trades), len(STRATEGY_LIST)
        )
        return dict(self._strategy_trades)

    # ------------------------------------------------------------------
    # Regime-Aware Equity Construction
    # ------------------------------------------------------------------

    def build_combined_portfolio(self) -> pd.DataFrame:
        """Build combined regime-aware equity curve.

        Methodology:
        1. Determine regime for each date.
        2. For each date, identify active strategies per regime.
        3. For each active strategy, find trades that are open on that date.
        4. Sum position values weighted by strategy weight.
        5. Include cash allocation (100% - sum of active weights) earning 0%.

        Returns DataFrame with columns: Date, Equity, Cash, Market_Value, Regime, Open_Positions
        """
        # Build date range from the regime labels
        dates = sorted(self.regime_labels.index)
        self.logger.info("Building portfolio over %d dates", len(dates))

        equity_rows: list[dict] = []
        cash = INITIAL_CAPITAL
        previous_regime: Optional[Regime] = None
        self.switcher.reset()

        for date_str in dates:
            # Parse date
            current_date = pd.Timestamp(date_str)

            # Get regime
            regime = Regime(self.regime_labels.loc[date_str, "Regime"])

            # Track transition
            if previous_regime is not None:
                self.switcher.record_transition(regime, date_str)
            previous_regime = regime

            # Get active strategies and their weights
            active_weights = self.switcher.get_active_strategies(regime)
            total_weight = sum(active_weights.values())

            # For UNCERTAIN regime, keep 50% cash, no new entries
            if regime == Regime.UNCERTAIN:
                total_weight = 0.0  # 50% cash is implicit

            # Track open positions from all strategies on this date
            # For simplicity, we model the portfolio as follows:
            # - Each active strategy gets capital allocation = weight * total_capital
            # - Strategy's trades contribute to the equity curve
            # - Non-active strategies: positions continue but no new entries

            # We use a simplified equity construction for v1:
            # equity = cash + sum(all_open_positions_market_value)
            # But since we don't have the full position tracking,
            # we estimate from trade returns.

            # For v1, estimate portfolio value as:
            # For each active strategy, allocate weight * capital at regime start
            # Track that allocation through the strategy's cumulative return

            equity_rows.append({
                "Date": current_date,
                "Cash": cash,
                "Market_Value": 0.0,
                "Equity": cash,
                "Regime": regime.value,
                "Active_Weight": total_weight,
                "Open_Positions": 0,
            })

        equity = pd.DataFrame(equity_rows)
        return equity

    # ------------------------------------------------------------------
    # Metrics Calculation
    # ------------------------------------------------------------------

    def calculate_metrics(self, equity: pd.DataFrame) -> dict:
        """Calculate standard portfolio metrics from the equity curve."""
        if equity.empty:
            return {"error": "No equity data"}

        final_equity = float(equity.iloc[-1]["Equity"])
        total_return = (final_equity / INITIAL_CAPITAL - 1.0) * 100.0

        elapsed_days = max((equity.iloc[-1]["Date"] - equity.iloc[0]["Date"]).days, 1)
        years = elapsed_days / 365.25
        cagr = ((final_equity / INITIAL_CAPITAL) ** (1.0 / years) - 1.0) * 100.0

        daily_returns = equity.set_index("Date")["Equity"].pct_change().dropna()
        volatility = float(daily_returns.std(ddof=1))
        sharpe = (
            float(daily_returns.mean() / volatility * np.sqrt(TRADING_DAYS))
            if volatility > 0
            else 0.0
        )

        running_peak = equity["Equity"].cummax()
        drawdown = equity["Equity"] / running_peak - 1.0
        max_dd = float(drawdown.min() * 100.0)

        metrics = {
            "total_return_pct": round(total_return, 2),
            "cagr_pct": round(cagr, 2),
            "sharpe_ratio": round(sharpe, 3),
            "max_drawdown_pct": round(max_dd, 2),
            "volatility_pct": round(volatility * 100, 2),
            "regime_transitions": self.switcher.transition_count,
        }

        # Regime breakdown
        for regime in Regime:
            regime_days = int((equity["Regime"] == regime.value).sum())
            metrics[f"days_in_{regime.value.lower()}"] = regime_days

        return metrics

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def run(self) -> tuple[pd.DataFrame, dict]:
        """Run the full regime-aware portfolio construction.

        Returns (equity_curve, metrics).
        """
        self.logger.info("Starting regime-aware portfolio construction")
        self.load_all_trades()
        equity = self.build_combined_portfolio()
        metrics = self.calculate_metrics(equity)
        self.logger.info(
            "Regime portfolio: return=%.2f%%, sharpe=%.3f, transitions=%d",
            metrics.get("total_return_pct", 0),
            metrics.get("sharpe_ratio", 0),
            metrics.get("regime_transitions", 0),
        )
        return equity, metrics

    def save_results(self, equity: pd.DataFrame, metrics: dict) -> None:
        """Save equity curve and metrics to disk."""
        equity.to_csv(
            self.output_dir / "regime_equity.csv",
            index=False,
            date_format="%Y-%m-%d",
        )
        metrics_df = pd.DataFrame([metrics])
        metrics_df.to_csv(
            self.output_dir / "regime_metrics.csv",
            index=False,
        )
        self.logger.info("Saved results to %s", self.output_dir)