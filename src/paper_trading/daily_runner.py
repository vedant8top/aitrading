"""Paper trading daily runner — orchestrates data download, signal generation, and execution."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from src.paper_trading.portfolio_state import PortfolioState, INITIAL_CAPITAL
from src.paper_trading.paper_broker import PaperBroker, SLIPPAGE_RATE, BROKERAGE_RATE, POSITION_SIZE
from src.paper_trading.trade_journal import TradeJournal

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RAW_DIR = PROJECT_ROOT / "data" / "raw"
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "paper_trading.db"
DEFAULT_REPORT_DIR = PROJECT_ROOT / "docs"

INITIAL_CAPITAL_SIM = 1_000_000.0

DONCHIAN_ENTRY = 20
DONCHIAN_EXIT = 40


class DailyRunner:
    """Orchestrate daily paper trading workflow.

    Handles:
    - Loading historical data from cached CSVs
    - Generating Donchian 20/40 signals
    - Executing trades via PaperBroker
    - Recording portfolio snapshots
    - Generating reports
    - Restart recovery
    """

    def __init__(
        self,
        raw_data_dir: Path | str = DEFAULT_RAW_DIR,
        db_path: Path | str = DEFAULT_DB_PATH,
        report_dir: Path | str = DEFAULT_REPORT_DIR,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.raw_data_dir = Path(raw_data_dir).resolve()
        self.report_dir = Path(report_dir).resolve()
        self.report_dir.mkdir(parents=True, exist_ok=True)

        self.logger = logger or self._configure_logging()

        # Initialize persistence layer
        self.portfolio = PortfolioState(db_path)

        # Initialize broker and journal
        self.broker = PaperBroker(self.portfolio, self.logger)
        self.journal = TradeJournal(self.portfolio)

        # State recovery
        self._recovered = self.portfolio._initialized
        if self._recovered:
            self.logger.info(
                "Portfolio state recovered: cash=%.2f, positions=%d",
                self.portfolio.cash_balance,
                len(self.portfolio.get_open_positions()),
            )
        else:
            self.logger.info("Starting fresh portfolio with INR %.2f", INITIAL_CAPITAL_SIM)

    def _configure_logging(self) -> logging.Logger:
        logger = logging.getLogger("paper_trading")
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

    def load_stock_data(self, tickers: Optional[list[str]] = None) -> dict[str, pd.DataFrame]:
        """Load raw OHLCV data for all stocks.

        Uses cached CSV files from data/raw/ directory.
        """
        all_files = sorted(self.raw_data_dir.glob("*_NS.csv"))
        stocks: dict[str, pd.DataFrame] = {}

        for csv_path in all_files:
            ticker = csv_path.stem
            if tickers and ticker not in tickers:
                continue

            cache_path = csv_path.with_suffix(".pkl")
            if cache_path.exists() and cache_path.stat().st_mtime >= csv_path.stat().st_mtime:
                df = pd.read_pickle(cache_path)
            else:
                df = pd.read_csv(csv_path, parse_dates=["Date"])
                df = df.sort_values("Date").reset_index(drop=True)
                df.to_pickle(cache_path)

            stocks[ticker] = df

        self.logger.info("Loaded %d stock files", len(stocks))
        return stocks

    # ------------------------------------------------------------------
    # Indicator & Signal Generation
    # ------------------------------------------------------------------

    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate SMA_20 required by Donchian strategy."""
        enriched = data.copy()
        enriched["SMA_20"] = enriched["Close"].rolling(20, min_periods=20).mean()
        return enriched

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """Generate Donchian 20/40 signals."""
        enriched = data.copy()
        close = enriched["Close"]

        upper = close.rolling(DONCHIAN_ENTRY, min_periods=DONCHIAN_ENTRY).max().shift(1)
        lower = close.rolling(DONCHIAN_EXIT, min_periods=DONCHIAN_EXIT).min().shift(1)

        buy_signal = close > upper
        sell_signal = close < lower
        signal = np.where(buy_signal, "BUY", np.where(sell_signal, "SELL", "HOLD"))

        enriched["Signal"] = signal
        enriched["Signal_Date"] = enriched["Date"]
        return enriched

    # ------------------------------------------------------------------
    # Simulation Execution
    # ------------------------------------------------------------------

    def run_simulation(
        self,
        start_date: str = "2018-01-01",
        end_date: str = "2026-06-14",
        tickers: Optional[list[str]] = None,
    ) -> None:
        """Run full historical simulation over a date range.

        This replays the Donchian 20/40 strategy day by day,
        executing trades and recording portfolio state.
        """
        self.logger.info(
            "Starting paper trading simulation: %s to %s", start_date, end_date
        )

        # Load data
        stocks = self.load_stock_data(tickers)

        # Calculate indicators for all stocks
        for ticker in list(stocks.keys()):
            stocks[ticker] = self.calculate_indicators(stocks[ticker])

        # Generate signals for all stocks
        for ticker in list(stocks.keys()):
            stocks[ticker] = self.generate_signals(stocks[ticker])

        # Get all unique dates across all stocks
        all_dates = sorted(
            set().union(
                *(set(df["Date"].dt.date.astype(str).tolist()) for df in stocks.values())
            )
        )

        # Filter to simulation range
        sim_dates = [d for d in all_dates if start_date <= d <= end_date]
        self.logger.info("Running simulation over %d trading days", len(sim_dates))

        # Build close lookup for position marking
        close_lookup: dict[str, pd.Series] = {}
        for ticker, df in stocks.items():
            s = df.set_index("Date")["Close"]
            close_lookup[ticker] = s

        # Build signals lookup by date
        # { date: [(ticker, signal, signal_date, next_open)] }
        events: dict[str, list[tuple[str, str, str, float]]] = {}
        for ticker, df in stocks.items():
            for i in range(len(df) - 1):
                sig = df.iloc[i]["Signal"]
                if sig not in ("BUY", "SELL"):
                    continue
                next_row = df.iloc[i + 1]
                exec_date = next_row["Date"].date().isoformat()
                if exec_date not in events:
                    events[exec_date] = []
                events[exec_date].append((
                    ticker,
                    sig,
                    df.iloc[i]["Date"].date().isoformat(),
                    float(next_row["Open"]),
                ))

        # Run day by day
        last_portfolio_value = INITIAL_CAPITAL_SIM

        for date_str in sim_dates:
            current_date = datetime.fromisoformat(date_str).date()

            # Update position prices
            market_value = 0.0
            prices_to_update = {}
            for pos in self.portfolio.get_open_positions():
                ticker = pos["ticker"]
                if ticker in close_lookup and date_str in close_lookup[ticker].index:
                    close_price = float(close_lookup[ticker].loc[date_str])
                    prices_to_update[ticker] = close_price
                    market_value += close_price * pos["shares"]

            if prices_to_update:
                self.portfolio.update_position_prices(prices_to_update)

            # Process events for this date
            daily_events = events.get(date_str, [])
            if daily_events:
                # SELLs first (release capital)
                sell_events = [e for e in daily_events if e[1] == "SELL"]
                buy_events = [e for e in daily_events if e[1] == "BUY"]

                for ticker, sig, sig_date, open_price in sell_events:
                    if self.portfolio.get_position(ticker):
                        self.broker.process_signal(
                            ticker, sig, sig_date, date_str, open_price
                        )

                for ticker, sig, sig_date, open_price in buy_events:
                    if not self.portfolio.get_position(ticker):
                        self.broker.process_signal(
                            ticker, sig, sig_date, date_str, open_price
                        )

            # Recalculate market value after trades
            market_value = 0.0
            for pos in self.portfolio.get_open_positions():
                ticker = pos["ticker"]
                if ticker in close_lookup and date_str in close_lookup[ticker].index:
                    close_price = float(close_lookup[ticker].loc[date_str])
                    market_value += close_price * pos["shares"]

            equity = self.portfolio.cash_balance + market_value
            daily_pnl = equity - last_portfolio_value
            last_portfolio_value = equity

            # Record snapshot
            self.journal.log_snapshot(
                snapshot_date=date_str,
                cash=self.portfolio.cash_balance,
                market_value=market_value,
                equity=equity,
                daily_pnl=daily_pnl,
            )

        self.logger.info(
            "Simulation complete: final_equity=%.2f, cash=%.2f, positions=%d",
            last_portfolio_value, self.portfolio.cash_balance,
            len(self.portfolio.get_open_positions()),
        )

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def generate_daily_report(self, report_date: Optional[str] = None) -> str:
        """Generate daily markdown report."""
        from datetime import date

        if report_date is None:
            report_date = date.today().isoformat()

        report = self.journal.generate_report(report_date)
        return report

    def save_daily_report(self, report: str) -> Path:
        """Save daily report to file."""
        report_path = self.report_dir / "paper_trading_report.md"
        report_path.write_text(report, encoding="utf-8")
        self.logger.info("Report saved to %s", report_path)
        return report_path

    def save_results(self) -> Path:
        """Save simulation results."""
        summary = self.journal.get_summary()
        results_path = PROJECT_ROOT / "docs" / "paper_trading_results.md"

        lines = []
        lines.append("# Paper Trading Simulation Results\n")
        lines.append("## Summary\n")
        lines.append(f"| Metric | Value |")
        lines.append(f"|--------|-------|")
        lines.append(f"| Total Trades | {summary.get('total_trades', 0)} |")
        lines.append(f"| Win Rate | {summary.get('win_rate', 0):.1f}% |")
        lines.append(f"| Avg Win | INR {summary.get('avg_win', 0):,.2f} |")
        lines.append(f"| Avg Loss | INR {summary.get('avg_loss', 0):,.2f} |")
        lines.append(f"| Total P&L | INR {summary.get('total_pnl', 0):+,.2f} |")
        lines.append(f"| Current Cash | INR {summary.get('current_cash', 0):,.2f} |")
        lines.append(f"| Portfolio Value | INR {summary.get('portfolio_value', 0):,.2f} |")
        lines.append(f"| Return | {summary.get('total_return_pct', 0):+.2f}% |")
        lines.append(f"| Open Positions | {summary.get('open_positions', 0)} |")

        if summary.get("last_snapshot_date"):
            lines.append(f"| Last Snapshot | {summary['last_snapshot_date']} |")
        lines.append("")

        # Recent trades
        trades = self.portfolio.get_trade_history(days=10)
        if trades:
            lines.append("## Recent Trades\n")
            lines.append("| Ticker | Exit | Entry | Exit | Shares | P&L | Return % | Held |")
            lines.append("|--------|------|-------|------|--------|-----|----------|------|")
            for t in trades[:10]:
                lines.append(
                    f"| {t['ticker']} | {t['exit_date']} | {t['entry_price']:.2f} | "
                    f"{t['exit_price']:.2f} | {t['shares']} | INR {t['pnl']:+,.2f} | "
                    f"{t['return_pct']:+.2f}% | {t['holding_days']}d |"
                )

        results_path.write_text("\n".join(lines), encoding="utf-8")
        self.logger.info("Results saved to %s", results_path)
        return results_path

    def close(self) -> None:
        """Clean up resources."""
        self.portfolio.close()