"""Trade journal and reporting for paper trading simulator."""

from __future__ import annotations

from typing import Optional, Any

from src.paper_trading.portfolio_state import PortfolioState


class TradeJournal:
    """Logging and reporting for paper trading activity."""

    def __init__(self, portfolio: PortfolioState) -> None:
        self.portfolio = portfolio

    def log_order(self, order_data: dict) -> None:
        """Log an order via the portfolio state's order recording."""
        self.portfolio.record_order(order_data)

    def log_trade(self, entry_data: dict, exit_data: dict) -> None:
        """Log a completed trade."""
        # Trade is recorded by portfolio_state.close_position()
        pass

    def log_snapshot(
        self,
        snapshot_date: str,
        cash: float,
        market_value: float,
        equity: float,
        daily_pnl: float,
    ) -> None:
        """Log a daily portfolio snapshot."""
        open_positions = len(self.portfolio.get_open_positions())
        total_pnl = equity - 1_000_000.0  # relative to initial capital
        self.portfolio.record_snapshot({
            "snapshot_date": snapshot_date,
            "cash": round(cash, 2),
            "market_value": round(market_value, 2),
            "equity": round(equity, 2),
            "open_positions": open_positions,
            "daily_pnl": round(daily_pnl, 2),
            "total_pnl": round(total_pnl, 2),
        })

    def get_recent_trades(self, n: int = 10) -> list[dict[str, Any]]:
        """Get N most recent completed trades."""
        return self.portfolio.get_trade_history(days=n)

    def get_summary(self) -> dict[str, Any]:
        """Get summary statistics from the trade journal."""
        from datetime import datetime, date

        trades = self.portfolio.get_trade_history(days=10000)
        snapshot = self.portfolio.get_latest_snapshot()

        summary: dict[str, Any] = {
            "total_trades": len(trades),
            "total_pnl": 0.0,
            "current_cash": self.portfolio.cash_balance,
            "open_positions": len(self.portfolio.get_open_positions()),
        }

        if trades:
            wins = [t for t in trades if t["pnl"] > 0]
            losses = [t for t in trades if t["pnl"] < 0]
            summary["winning_trades"] = len(wins)
            summary["losing_trades"] = len(losses)
            summary["win_rate"] = round(len(wins) / len(trades) * 100, 1) if trades else 0.0
            summary["total_pnl"] = round(sum(t["pnl"] for t in trades), 2)
            summary["avg_win"] = round(sum(t["pnl"] for t in wins) / len(wins), 2) if wins else 0.0
            summary["avg_loss"] = round(sum(t["pnl"] for t in losses) / len(losses), 2) if losses else 0.0

        if snapshot:
            summary["portfolio_value"] = snapshot["equity"]
            summary["total_return_pct"] = round((snapshot["equity"] / 1_000_000 - 1) * 100, 2)
            summary["last_snapshot_date"] = snapshot["snapshot_date"]

        return summary

    def generate_report(self, report_date: str) -> str:
        """Generate a daily trading report string."""
        positions = self.portfolio.get_open_positions()
        trades = self.portfolio.get_trade_history(days=1)  # today's trades
        snapshot = self.portfolio.get_latest_snapshot()

        lines = []
        lines.append(f"# Daily Trading Report — {report_date}")
        lines.append("")

        # Portfolio Summary
        lines.append("## Portfolio Summary")
        lines.append("")
        if snapshot:
            lines.append(f"| Metric | Value |")
            lines.append(f"|--------|-------|")
            lines.append(f"| Cash | INR {snapshot['cash']:,.2f} |")
            lines.append(f"| Market Value | INR {snapshot['market_value']:,.2f} |")
            lines.append(f"| Portfolio Value | INR {snapshot['equity']:,.2f} |")
            lines.append(f"| Open Positions | {snapshot['open_positions']} |")
            lines.append(f"| Daily P&L | INR {snapshot['daily_pnl']:+,.2f} |")
            lines.append(f"| Total P&L | INR {snapshot['total_pnl']:+,.2f} |")
            lines.append(f"| Return | {((snapshot['equity'] / 1_000_000 - 1) * 100):+.2f}% |")
        else:
            lines.append("No portfolio snapshot available.")
        lines.append("")

        # Open Positions
        lines.append("## Open Positions")
        lines.append("")
        if positions:
            lines.append("| Ticker | Entry Date | Entry Price | Current Price | Shares | Unrealized P&L |")
            lines.append("|--------|------------|-------------|---------------|--------|----------------|")
            for pos in positions:
                lines.append(
                    f"| {pos['ticker']} | {pos['entry_date']} | "
                    f"{pos['entry_price']:.2f} | {pos['current_price']:.2f} | "
                    f"{pos['shares']} | INR {pos['unrealized_pnl']:+,.2f} |"
                )
        else:
            lines.append("No open positions.")
        lines.append("")

        # Recent Trades
        lines.append("## Recent Trades")
        lines.append("")
        if trades:
            lines.append("| Ticker | Exit Date | Entry Price | Exit Price | Shares | P&L | Return % |")
            lines.append("|--------|-----------|-------------|------------|--------|-----|----------|")
            for t in trades[:10]:
                lines.append(
                    f"| {t['ticker']} | {t['exit_date']} | "
                    f"{t['entry_price']:.2f} | {t['exit_price']:.2f} | "
                    f"{t['shares']} | INR {t['pnl']:+,.2f} | {t['return_pct']:+.2f}% |"
                )
        else:
            lines.append("No trades today.")
        lines.append("")

        return "\n".join(lines)