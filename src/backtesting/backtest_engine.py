"""Portfolio backtesting engine for generated daily trading signals."""

from __future__ import annotations

import argparse
import logging
import math
from dataclasses import asdict, dataclass
from logging.handlers import RotatingFileHandler
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_DIR = PROJECT_ROOT / "data" / "signals"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "backtests"
DEFAULT_REPORT_PATH = PROJECT_ROOT / "docs" / "backtest_report.md"
DEFAULT_LOG_PATH = PROJECT_ROOT / "logs" / "backtest_engine.log"
INITIAL_CAPITAL = 100_000.0
POSITION_SIZE = 0.10
BROKERAGE_RATE = 0.0005
SLIPPAGE_RATE = 0.0005
TRADING_DAYS_PER_YEAR = 252
REQUIRED_COLUMNS = ("Date", "Open", "Close", "Signal")


class BacktestError(RuntimeError):
    """Base exception for backtesting failures."""


class InputValidationError(BacktestError):
    """Raised when signal input cannot be safely backtested."""


@dataclass
class Position:
    ticker: str
    entry_signal_date: pd.Timestamp
    entry_date: pd.Timestamp
    entry_raw_open: float
    entry_price: float
    shares: int
    entry_value: float
    entry_brokerage: float
    entry_slippage: float
    entry_cash_outflow: float


@dataclass(frozen=True)
class Trade:
    ticker: str
    entry_signal_date: str
    entry_date: str
    exit_signal_date: str
    exit_date: str
    entry_raw_open: float
    exit_raw_open: float
    entry_price: float
    exit_price: float
    shares_purchased: int
    entry_value: float
    exit_value: float
    entry_brokerage: float
    exit_brokerage: float
    entry_slippage: float
    exit_slippage: float
    total_costs: float
    pnl: float
    return_pct: float
    holding_days: int
    exit_reason: str = "signal"


def configure_logging(log_path: Path) -> logging.Logger:
    """Configure console and rotating file logging."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("backtest_engine")
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


class PortfolioBacktester:
    """Run a long-only, next-open portfolio simulation."""

    def __init__(
        self,
        initial_capital: float = INITIAL_CAPITAL,
        position_size: float = POSITION_SIZE,
        brokerage_rate: float = BROKERAGE_RATE,
        slippage_rate: float = SLIPPAGE_RATE,
        logger: logging.Logger | None = None,
        risk_mode: str = "none",
    ) -> None:
        if initial_capital <= 0:
            raise ValueError("initial_capital must be positive")
        if not 0 < position_size <= 1:
            raise ValueError("position_size must be between 0 and 1")
        if brokerage_rate < 0 or slippage_rate < 0:
            raise ValueError("trading cost rates cannot be negative")
        self.initial_capital = float(initial_capital)
        self.position_size = float(position_size)
        self.brokerage_rate = float(brokerage_rate)
        self.slippage_rate = float(slippage_rate)
        self.logger = logger or logging.getLogger("backtest_engine")
        self.risk_mode_name = risk_mode.lower().strip()

        from src.risk_management.risk_engine import RiskControls, RiskManager, build_risk_manager
        self.risk_manager = build_risk_manager(self.risk_mode_name)
        self.risk_stats: dict[str, int | float] = {
            "stop_losses_triggered": 0,
            "trades_rejected_max_concurrent": 0,
            "trades_rejected_exposure": 0,
            "daily_loss_limit_hits": 0,
            "drawdown_limit_hits": 0,
            "risk_mode": self.risk_mode_name,
        }

    @staticmethod
    def load_signal_files(input_folder: Path) -> dict[str, pd.DataFrame]:
        """Load and validate all signal files in deterministic order."""
        files = sorted(input_folder.glob("*_signals.csv"))
        if not files:
            raise InputValidationError(f"No signal CSV files found in {input_folder}")

        datasets: dict[str, pd.DataFrame] = {}
        for path in files:
            ticker = path.stem.removesuffix("_signals")
            try:
                data = pd.read_csv(path)
            except (OSError, pd.errors.ParserError) as exc:
                raise InputValidationError(f"Could not read {path}: {exc}") from exc
            missing = [column for column in REQUIRED_COLUMNS if column not in data]
            if missing:
                raise InputValidationError(
                    f"{ticker} is missing required columns: {', '.join(missing)}"
                )
            if data.empty:
                raise InputValidationError(f"{ticker} signal dataset is empty")

            data = data.copy()
            data["Date"] = pd.to_datetime(data["Date"], errors="coerce")
            data["Open"] = pd.to_numeric(data["Open"], errors="coerce")
            data["Close"] = pd.to_numeric(data["Close"], errors="coerce")
            if data[["Date", "Open", "Close"]].isna().any().any():
                raise InputValidationError(
                    f"{ticker} contains invalid Date, Open, or Close values"
                )
            if data["Date"].duplicated().any():
                raise InputValidationError(f"{ticker} contains duplicate dates")
            if not data["Date"].is_monotonic_increasing:
                raise InputValidationError(f"{ticker} dates are not ascending")
            if not data["Signal"].isin(("BUY", "SELL", "HOLD")).all():
                raise InputValidationError(f"{ticker} contains invalid signals")
            if (data[["Open", "Close"]] <= 0).any().any():
                raise InputValidationError(f"{ticker} contains non-positive prices")
            datasets[ticker] = data.reset_index(drop=True)
        return datasets

    @staticmethod
    def _execution_events(
        datasets: dict[str, pd.DataFrame],
    ) -> dict[pd.Timestamp, list[tuple[str, str, pd.Timestamp, float]]]:
        """Map each actionable signal to that ticker's next available open."""
        events: dict[pd.Timestamp, list[tuple[str, str, pd.Timestamp, float]]] = {}
        for ticker, data in datasets.items():
            for index in range(len(data) - 1):
                signal = str(data.at[index, "Signal"])
                if signal not in ("BUY", "SELL"):
                    continue
                execution_date = data.at[index + 1, "Date"]
                events.setdefault(execution_date, []).append(
                    (
                        ticker,
                        signal,
                        data.at[index, "Date"],
                        float(data.at[index + 1, "Open"]),
                    )
                )
        return events

    def _close_position(
        self,
        positions: dict[str, Position],
        trades: list[Trade],
        cash: float,
        ticker: str,
        exit_date: object,
        exit_price: float,
        signal_date: object | None = None,
        exit_reason: str = "signal",
    ) -> float:
        """Close a position and return updated cash."""
        position = positions.pop(ticker)
        actual_exit_price = exit_price * (1.0 - self.slippage_rate)
        exit_slippage_val = position.shares * (exit_price - actual_exit_price)
        exit_value = position.shares * actual_exit_price
        exit_brokerage_val = exit_value * self.brokerage_rate
        cash_proceeds = exit_value - exit_brokerage_val
        cash += cash_proceeds
        pnl = cash_proceeds - position.entry_cash_outflow
        return_pct_val = pnl / position.entry_cash_outflow * 100.0

        sig_date = signal_date if signal_date is not None else position.entry_signal_date
        trade = Trade(
            ticker=ticker,
            entry_signal_date=position.entry_signal_date.date().isoformat(),
            entry_date=position.entry_date.date().isoformat(),
            exit_signal_date=sig_date.date().isoformat() if hasattr(sig_date, 'date') else str(sig_date),
            exit_date=exit_date.date().isoformat() if hasattr(exit_date, 'date') else str(exit_date),
            entry_raw_open=position.entry_raw_open,
            exit_raw_open=exit_price,
            entry_price=position.entry_price,
            exit_price=actual_exit_price,
            shares_purchased=position.shares,
            entry_value=position.entry_value,
            exit_value=exit_value,
            entry_brokerage=position.entry_brokerage,
            exit_brokerage=exit_brokerage_val,
            entry_slippage=position.entry_slippage,
            exit_slippage=exit_slippage_val,
            total_costs=position.entry_brokerage + exit_brokerage_val + position.entry_slippage + exit_slippage_val,
            pnl=pnl,
            return_pct=return_pct_val,
            holding_days=(
                (exit_date - position.entry_date).days
                if hasattr(exit_date, '__sub__') and hasattr(position.entry_date, '__sub__')
                else 0
            ),
            exit_reason=exit_reason,
        )
        trades.append(trade)
        self.logger.info(
            "EXIT %s: reason=%s, date=%s, price=%.4f, shares=%d, pnl=%.2f",
            ticker, exit_reason, exit_date.date() if hasattr(exit_date, 'date') else exit_date,
            actual_exit_price, position.shares, pnl,
        )
        return cash

    def run(
        self, datasets: dict[str, pd.DataFrame]
    ) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, float | int | str]]:
        """Execute the portfolio simulation and calculate performance metrics."""
        events = self._execution_events(datasets)
        all_dates = sorted(
            set().union(*(set(data["Date"].tolist()) for data in datasets.values()))
        )
        close_lookup = {
            ticker: data.set_index("Date")["Close"] for ticker, data in datasets.items()
        }
        cash = self.initial_capital
        positions: dict[str, Position] = {}
        trades: list[Trade] = []
        equity_rows: list[dict[str, float | int | pd.Timestamp]] = []
        last_close: dict[str, float] = {}

        # Build ATR lookup from signal files (use the raw data if ATR_14 column present)
        atr_lookup: dict[str, float] = {}
        for ticker, data in datasets.items():
            if "ATR_14" in data.columns and not data["ATR_14"].isna().all():
                atr_lookup[ticker] = float(data["ATR_14"].iloc[-1])
            else:
                atr_lookup[ticker] = 0.0

        entry_prices: dict[str, float] = {}
        entry_dates: dict[str, object] = {}
        previous_equity: float | None = None
        daily_loss_halt_until: object | None = None

        for current_date in all_dates:
            for ticker, series in close_lookup.items():
                if current_date in series.index:
                    last_close[ticker] = float(series.loc[current_date])

            # Check daily loss halt
            if daily_loss_halt_until is not None and current_date < daily_loss_halt_until:
                # Skip all trading for the day
                market_value = sum(
                    position.shares * last_close.get(position.ticker, 0)
                    for position in positions.values()
                )
                equity_rows.append({
                    "Date": current_date,
                    "Cash": cash,
                    "Market_Value": market_value,
                    "Equity": cash + market_value,
                    "Open_Positions": len(positions),
                })
                continue

            # Process stop losses before signal events (using previous close)
            if positions:
                stop_exits = self.risk_manager.check_stop_exits(
                    positions=positions,
                    current_date=current_date,
                    last_close=last_close,
                    atr_lookup=atr_lookup,
                    entry_dates=entry_dates,
                    entry_prices=entry_prices,
                )
                for ticker, stop_date, stop_price in stop_exits:
                    if ticker in positions:
                        self.risk_stats["stop_losses_triggered"] += 1
                        cash = self._close_position(
                            positions, trades, cash, ticker,
                            exit_date=stop_date, exit_price=stop_price,
                            signal_date=stop_date, exit_reason="stop_loss",
                        )
                        if ticker in entry_prices:
                            del entry_prices[ticker]
                        if ticker in entry_dates:
                            del entry_dates[ticker]

            daily_events = events.get(current_date, [])
            # Release capital before evaluating same-open entries.
            for ticker, signal, signal_date, raw_open in sorted(daily_events):
                if signal != "SELL" or ticker not in positions:
                    continue
                cash = self._close_position(
                    positions, trades, cash, ticker,
                    exit_date=current_date, exit_price=raw_open,
                    signal_date=signal_date, exit_reason="signal",
                )
                if ticker in entry_prices:
                    del entry_prices[ticker]
                if ticker in entry_dates:
                    del entry_dates[ticker]

            for ticker, signal, signal_date, raw_open in sorted(daily_events):
                if signal != "BUY" or ticker in positions:
                    continue

                # Enforce max concurrent positions
                if len(positions) >= self.risk_manager.max_concurrent_positions:
                    self.risk_stats["trades_rejected_max_concurrent"] += 1
                    if self.risk_mode_name != "none":
                        self.logger.info(
                            "Rejected BUY for %s on %s: max concurrent positions (%d) reached",
                            ticker, current_date.date() if hasattr(current_date, 'date') else current_date,
                            self.risk_manager.max_concurrent_positions,
                        )
                    continue

                # Compute position size using risk manager
                atr_val = atr_lookup.get(ticker, 0.0)
                shares = self.risk_manager.compute_position_size(
                    cash=cash,
                    price=raw_open,
                    brokerage_rate=self.brokerage_rate,
                    atr=atr_val if atr_val > 0 else None,
                )

                # Enforce max portfolio exposure
                if self.risk_mode_name != "none":
                    current_exposure = sum(
                        p.shares * last_close.get(p.ticker, 0)
                        for p in positions.values()
                    )
                    max_position_val = self.risk_manager.get_max_position_value(cash, current_exposure)
                    estimated_entry = shares * raw_open * (1.0 + self.slippage_rate) * (1.0 + self.brokerage_rate)
                    if estimated_entry > max_position_val:
                        self.risk_stats["trades_rejected_exposure"] += 1
                        self.logger.info(
                            "Rejected BUY for %s on %s: exposure limit (max=%.2f, estimated=%.2f)",
                            ticker,
                            current_date.date() if hasattr(current_date, 'date') else current_date,
                            max_position_val, estimated_entry,
                        )
                        continue

                if shares < 1:
                    self.logger.warning(
                        "Skipped BUY for %s on %s: allocation cannot buy one share",
                        ticker,
                        current_date.date() if hasattr(current_date, 'date') else current_date,
                    )
                    continue

                entry_price = raw_open * (1.0 + self.slippage_rate)
                entry_value = shares * entry_price
                entry_slippage_val = shares * (entry_price - raw_open)
                entry_brokerage_val = entry_value * self.brokerage_rate
                cash_outflow = entry_value + entry_brokerage_val
                cash -= cash_outflow
                positions[ticker] = Position(
                    ticker=ticker,
                    entry_signal_date=signal_date,
                    entry_date=current_date,
                    entry_raw_open=raw_open,
                    entry_price=entry_price,
                    shares=shares,
                    entry_value=entry_value,
                    entry_brokerage=entry_brokerage_val,
                    entry_slippage=entry_slippage_val,
                    entry_cash_outflow=cash_outflow,
                )
                entry_prices[ticker] = entry_price
                entry_dates[ticker] = current_date
                self.logger.info(
                    "ENTRY %s: date=%s, price=%.4f, shares=%d, cash_outflow=%.2f",
                    ticker,
                    current_date.date() if hasattr(current_date, 'date') else current_date,
                    entry_price, shares, cash_outflow,
                )

            market_value = sum(
                position.shares * last_close.get(position.ticker, 0)
                for position in positions.values()
            )
            current_equity = cash + market_value
            equity_rows.append({
                "Date": current_date,
                "Cash": cash,
                "Market_Value": market_value,
                "Equity": current_equity,
                "Open_Positions": len(positions),
            })

            # Check daily loss limit (ADVANCED mode)
            if previous_equity is not None and previous_equity > 0:
                daily_return = (current_equity - previous_equity) / previous_equity * 100.0
                if self.risk_manager.check_daily_loss_limit(daily_return):
                    self.risk_stats["daily_loss_limit_hits"] += 1
                    self.logger.warning(
                        "Daily loss limit hit on %s: return=%.2f%%",
                        current_date.date() if hasattr(current_date, 'date') else current_date,
                        daily_return,
                    )
                    daily_loss_halt_until = None
                    # Halt for 1 trading day
                    try:
                        idx = all_dates.index(current_date)
                        if idx + 1 < len(all_dates):
                            daily_loss_halt_until = all_dates[idx + 1]
                    except (ValueError, IndexError):
                        pass

            # Check drawdown limit (ADVANCED mode)
            if self.risk_manager.check_drawdown_limit(current_equity):
                self.risk_stats["drawdown_limit_hits"] += 1
                self.logger.warning("Portfolio drawdown limit breached on %s", current_date)

            previous_equity = current_equity

        equity = pd.DataFrame(equity_rows)
        trade_frame = pd.DataFrame([asdict(trade) for trade in trades])
        metrics = self.calculate_metrics(equity, trade_frame, len(positions))
        # Add risk stats to metrics
        metrics["risk_mode"] = self.risk_mode_name
        metrics["stop_losses_triggered"] = self.risk_stats["stop_losses_triggered"]
        metrics["trades_rejected_max_concurrent"] = self.risk_stats["trades_rejected_max_concurrent"]
        metrics["trades_rejected_exposure"] = self.risk_stats["trades_rejected_exposure"]
        metrics["daily_loss_limit_hits"] = self.risk_stats["daily_loss_limit_hits"]
        metrics["drawdown_limit_hits"] = self.risk_stats["drawdown_limit_hits"]
        return trade_frame, equity, metrics

    def calculate_metrics(
        self, equity: pd.DataFrame, trades: pd.DataFrame, open_positions: int
    ) -> dict[str, float | int | str]:
        """Calculate portfolio and closed-trade performance metrics."""
        if equity.empty:
            raise BacktestError("Equity curve is empty")
        final_equity = float(equity.iloc[-1]["Equity"])
        total_return = (final_equity / self.initial_capital - 1.0) * 100.0
        elapsed_days = max((equity.iloc[-1]["Date"] - equity.iloc[0]["Date"]).days, 1)
        years = elapsed_days / 365.25
        cagr = ((final_equity / self.initial_capital) ** (1.0 / years) - 1.0) * 100.0

        daily_returns = equity.set_index("Date")["Equity"].pct_change().dropna()
        volatility = float(daily_returns.std(ddof=1))
        sharpe = (
            float(daily_returns.mean() / volatility * math.sqrt(TRADING_DAYS_PER_YEAR))
            if volatility > 0
            else 0.0
        )
        running_peak = equity["Equity"].cummax()
        drawdown = equity["Equity"] / running_peak - 1.0
        maximum_drawdown = float(drawdown.min() * 100.0)

        if trades.empty:
            wins = pd.Series(dtype=float)
            losses = pd.Series(dtype=float)
            total_trades = 0
        else:
            wins = trades.loc[trades["pnl"] > 0, "pnl"]
            losses = trades.loc[trades["pnl"] < 0, "pnl"]
            total_trades = len(trades)
        win_rate = len(wins) / total_trades * 100.0 if total_trades else 0.0
        gross_profit = float(wins.sum())
        gross_loss = float(abs(losses.sum()))
        if gross_loss > 0:
            profit_factor: float | str = gross_profit / gross_loss
        elif gross_profit > 0:
            profit_factor = "Infinity"
        else:
            profit_factor = 0.0

        avg_holding_days = 0.0
        if not trades.empty and "holding_days" in trades.columns:
            avg_holding_days = float(trades["holding_days"].mean())

        return {
            "initial_capital": self.initial_capital,
            "final_equity": final_equity,
            "total_return_pct": total_return,
            "cagr_pct": cagr,
            "win_rate_pct": win_rate,
            "profit_factor": profit_factor,
            "average_win": float(wins.mean()) if not wins.empty else 0.0,
            "average_loss": float(losses.mean()) if not losses.empty else 0.0,
            "maximum_drawdown_pct": maximum_drawdown,
            "sharpe_ratio": sharpe,
            "total_trades": total_trades,
            "avg_holding_days": round(avg_holding_days, 1),
            "open_positions_at_end": open_positions,
            "start_date": equity.iloc[0]["Date"].date().isoformat(),
            "end_date": equity.iloc[-1]["Date"].date().isoformat(),
            "brokerage_rate_pct": self.brokerage_rate * 100.0,
            "slippage_rate_pct": self.slippage_rate * 100.0,
            "position_size_pct": self.position_size * 100.0,
        }


def save_performance_summary(
    metrics: dict[str, float | int | str], output_path: Path
) -> None:
    pd.DataFrame([metrics]).to_csv(output_path, index=False)


def create_equity_chart(equity: pd.DataFrame, chart_path: Path) -> None:
    figure, axis = plt.subplots(figsize=(12, 6))
    axis.plot(equity["Date"], equity["Equity"], color="tab:blue", linewidth=1.6)
    axis.axhline(INITIAL_CAPITAL, color="tab:gray", linestyle="--", linewidth=1)
    axis.set_title("Portfolio Equity Curve")
    axis.set_xlabel("Date")
    axis.set_ylabel("Portfolio Equity (INR)")
    axis.grid(True, alpha=0.3)
    figure.autofmt_xdate()
    figure.tight_layout()
    figure.savefig(chart_path, dpi=150)
    plt.close(figure)


def write_report(
    metrics: dict[str, float | int | str],
    trades: pd.DataFrame,
    input_files: int,
    output_dir: Path,
    report_path: Path,
) -> None:
    profit_factor = metrics["profit_factor"]
    profit_factor_text = (
        profit_factor if isinstance(profit_factor, str) else f"{profit_factor:.4f}"
    )
    if trades.empty:
        trade_lines = "- No completed trades."
    else:
        trade_lines = "\n".join(
            f"- `{row.ticker}`: {row.entry_date} to {row.exit_date}, "
            f"{row.shares_purchased} shares, PnL INR {row.pnl:.2f}, "
            f"return {row.return_pct:.2f}%"
            for row in trades.itertuples()
        )

    report = f"""# Backtest Report

## Portfolio Results

- Signal files processed: {input_files}
- Period: {metrics['start_date']} to {metrics['end_date']}
- Risk mode: {metrics.get('risk_mode', 'none')}
- Initial capital: INR {metrics['initial_capital']:.2f}
- Final equity: INR {metrics['final_equity']:.2f}
- Total return: {metrics['total_return_pct']:.4f}%
- CAGR: {metrics['cagr_pct']:.4f}%
- Win rate: {metrics['win_rate_pct']:.2f}%
- Profit factor: {profit_factor_text}
- Average win: INR {metrics['average_win']:.2f}
- Average loss: INR {metrics['average_loss']:.2f}
- Maximum drawdown: {metrics['maximum_drawdown_pct']:.4f}%
- Sharpe ratio: {metrics['sharpe_ratio']:.4f}
- Total completed trades: {metrics['total_trades']}
- Average holding days: {metrics.get('avg_holding_days', 'N/A')}
- Open positions at end: {metrics['open_positions_at_end']}
- Stop losses triggered: {metrics.get('stop_losses_triggered', 0)}
- Trades rejected (max concurrent): {metrics.get('trades_rejected_max_concurrent', 0)}
- Trades rejected (exposure): {metrics.get('trades_rejected_exposure', 0)}
- Daily loss limit hits: {metrics.get('daily_loss_limit_hits', 0)}
- Drawdown limit hits: {metrics.get('drawdown_limit_hits', 0)}

## Simulation Assumptions

- Long-only portfolio with shared starting cash of INR 100,000.
- BUY enters at the next available session's Open plus 0.05% adverse slippage.
- SELL exits at the next available session's Open minus 0.05% adverse slippage.
- Brokerage is 0.05% of traded value on both entry and exit.
- Whole shares only; repeated BUY signals are ignored while already long.
- SELL signals are ignored while flat; same-open exits are processed before entries.
- Daily equity is cash plus open positions marked at that session's Close.
- Sharpe ratio uses daily portfolio returns, zero risk-free rate, and 252 sessions/year.
- CAGR uses elapsed calendar time. No taxes, dividends, or short selling are modeled.

## Completed Trades

{trade_lines}

## Generated Files

- `{_display_path(output_dir / 'trades.csv')}`
- `{_display_path(output_dir / 'performance_summary.csv')}`
- `{_display_path(output_dir / 'equity_curve.csv')}`
- `{_display_path(output_dir / 'equity_curve.png')}`
- `{_display_path(report_path)}`
"""
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backtest generated daily signals.")
    parser.add_argument("--input-folder", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-folder", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--log-file", type=Path, default=DEFAULT_LOG_PATH)
    parser.add_argument("--initial-capital", type=float, default=INITIAL_CAPITAL)
    parser.add_argument("--position-size", type=float, default=POSITION_SIZE)
    parser.add_argument("--brokerage", type=float, default=BROKERAGE_RATE)
    parser.add_argument("--slippage", type=float, default=SLIPPAGE_RATE)
    parser.add_argument("--risk-mode", type=str, default="none",
                        choices=["none", "basic", "advanced"],
                        help="Risk management mode")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logger = configure_logging(args.log_file.resolve())
    try:
        output_dir = args.output_folder.resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        datasets = PortfolioBacktester.load_signal_files(args.input_folder.resolve())
        logger.info(
            "Starting backtest: tickers=%d, capital=%.2f, risk_mode=%s",
            len(datasets), args.initial_capital, args.risk_mode,
        )
        backtester = PortfolioBacktester(
            initial_capital=args.initial_capital,
            position_size=args.position_size,
            brokerage_rate=args.brokerage,
            slippage_rate=args.slippage,
            logger=logger,
            risk_mode=args.risk_mode,
        )
        trades, equity, metrics = backtester.run(datasets)

        trade_columns = [field.name for field in Trade.__dataclass_fields__.values()]
        if trades.empty:
            trades = pd.DataFrame(columns=trade_columns)
        trades.to_csv(output_dir / "trades.csv", index=False)
        equity.to_csv(output_dir / "equity_curve.csv", index=False, date_format="%Y-%m-%d")
        save_performance_summary(metrics, output_dir / "performance_summary.csv")
        create_equity_chart(equity, output_dir / "equity_curve.png")
        write_report(
            metrics,
            trades,
            len(datasets),
            output_dir,
            args.report.resolve(),
        )

        logger.info(
            "Backtest finished: final_equity=%.2f, return=%.4f%%, trades=%d",
            metrics["final_equity"], metrics["total_return_pct"], metrics["total_trades"],
        )
        print(f"Risk mode: {args.risk_mode}")
        print(f"Final equity: INR {metrics['final_equity']:.2f}")
        print(f"Total return: {metrics['total_return_pct']:.4f}%")
        print(f"CAGR: {metrics['cagr_pct']:.4f}%")
        print(f"Win rate: {metrics['win_rate_pct']:.2f}%")
        print(f"Profit factor: {metrics['profit_factor']}")
        print(f"Maximum drawdown: {metrics['maximum_drawdown_pct']:.4f}%")
        print(f"Sharpe ratio: {metrics['sharpe_ratio']:.4f}")
        print(f"Total trades: {metrics['total_trades']}")
        print(f"Stop losses triggered: {metrics.get('stop_losses_triggered', 0)}")
        return 0
    except Exception as exc:
        logger.exception("Backtest failed")
        print(f"Fatal backtest error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())