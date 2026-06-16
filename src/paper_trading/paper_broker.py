"""Simulated broker for paper trading — executes BUY/SELL orders."""

from __future__ import annotations

import logging
from typing import Optional

from src.paper_trading.portfolio_state import PortfolioState

SLIPPAGE_RATE = 0.0005
BROKERAGE_RATE = 0.0005
POSITION_SIZE = 0.10


class PaperBroker:
    """Simulate trade execution without real market integration."""

    def __init__(
        self,
        portfolio: PortfolioState,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.portfolio = portfolio
        self.logger = logger or logging.getLogger("paper_broker")

    def process_signal(
        self,
        ticker: str,
        signal: str,
        signal_date: str,
        execution_date: str,
        open_price: float,
    ) -> dict:
        """Process a BUY or SELL signal.

        Args:
            ticker: Stock symbol
            signal: "BUY" or "SELL"
            signal_date: Date signal was generated
            execution_date: Date order is executed (next day)
            open_price: Next day's open price

        Returns:
            Dict with execution result

        Raises:
            ValueError: If signal is not BUY or SELL
        """
        if signal == "BUY":
            return self._buy(ticker, signal_date, execution_date, open_price)
        elif signal == "SELL":
            return self._sell(ticker, signal_date, execution_date, open_price)
        else:
            raise ValueError(f"Unknown signal: {signal}")

    def _buy(
        self,
        ticker: str,
        signal_date: str,
        execution_date: str,
        open_price: float,
    ) -> dict:
        """Execute a BUY order.

        Calculates position size (10% of cash), buys whole shares.
        """
        cash = self.portfolio.cash_balance

        # Calculate shares to buy
        effective_price = open_price * (1.0 + SLIPPAGE_RATE)
        max_allocation = cash * POSITION_SIZE
        shares = int(max_allocation / (effective_price * (1.0 + BROKERAGE_RATE)))

        if shares < 1:
            # Cannot buy even 1 share
            order_data = {
                "ticker": ticker,
                "order_type": "BUY",
                "signal_date": signal_date,
                "execution_date": execution_date,
                "requested_shares": 0,
                "executed_shares": 0,
                "price": open_price,
                "slippage": 0.0,
                "brokerage": 0.0,
                "total_value": 0.0,
                "status": "REJECTED",
                "reason": "allocation cannot buy one share",
            }
            self.portfolio.record_order(order_data)
            self.logger.info("REJECTED BUY %s: allocation too small", ticker)
            return order_data

        # Calculate costs
        entry_price = open_price * (1.0 + SLIPPAGE_RATE)
        entry_value = shares * entry_price
        brokerage_val = entry_value * BROKERAGE_RATE
        total_cost = entry_value + brokerage_val

        if total_cost > cash:
            order_data = {
                "ticker": ticker,
                "order_type": "BUY",
                "signal_date": signal_date,
                "execution_date": execution_date,
                "requested_shares": shares,
                "executed_shares": 0,
                "price": open_price,
                "slippage": 0.0,
                "brokerage": 0.0,
                "total_value": 0.0,
                "status": "REJECTED",
                "reason": f"insufficient cash (need {total_cost:.2f}, have {cash:.2f})",
            }
            self.portfolio.record_order(order_data)
            self.logger.info("REJECTED BUY %s: insufficient cash", ticker)
            return order_data

        # Execute buy
        self.portfolio.deduct_cash(total_cost)
        self.portfolio.save_position(
            ticker=ticker,
            entry_date=execution_date,
            entry_price=entry_price,
            shares=shares,
            signal_date=signal_date,
        )

        # Record order
        order_data = {
            "ticker": ticker,
            "order_type": "BUY",
            "signal_date": signal_date,
            "execution_date": execution_date,
            "requested_shares": shares,
            "executed_shares": shares,
            "price": entry_price,
            "slippage": open_price * SLIPPAGE_RATE,
            "brokerage": brokerage_val,
            "total_value": total_cost,
            "status": "EXECUTED",
            "reason": "",
        }
        self.portfolio.record_order(order_data)

        self.logger.info(
            "EXECUTED BUY %s: %d shares @ %.2f = %.2f (cash: %.2f)",
            ticker, shares, entry_price, total_cost, self.portfolio.cash_balance,
        )
        return order_data

    def _sell(
        self,
        ticker: str,
        signal_date: str,
        execution_date: str,
        open_price: float,
    ) -> dict:
        """Execute a SELL order.

        Closes the entire open position.
        """
        position = self.portfolio.get_position(ticker)
        if position is None:
            order_data = {
                "ticker": ticker,
                "order_type": "SELL",
                "signal_date": signal_date,
                "execution_date": execution_date,
                "requested_shares": 0,
                "executed_shares": 0,
                "price": open_price,
                "slippage": 0.0,
                "brokerage": 0.0,
                "total_value": 0.0,
                "status": "REJECTED",
                "reason": "no open position",
            }
            self.portfolio.record_order(order_data)
            return order_data

        shares = position["shares"]
        exit_price = open_price * (1.0 - SLIPPAGE_RATE)
        exit_value = shares * exit_price
        brokerage_val = exit_value * BROKERAGE_RATE
        total_proceeds = exit_value - brokerage_val

        # Close position (records the trade)
        trade = self.portfolio.close_position(ticker, execution_date, exit_price)
        self.portfolio.add_cash(total_proceeds)

        # Record order
        order_data = {
            "ticker": ticker,
            "order_type": "SELL",
            "signal_date": signal_date,
            "execution_date": execution_date,
            "requested_shares": shares,
            "executed_shares": shares,
            "price": exit_price,
            "slippage": open_price * SLIPPAGE_RATE,
            "brokerage": brokerage_val,
            "total_value": total_proceeds,
            "status": "EXECUTED",
            "reason": "",
        }
        self.portfolio.record_order(order_data)

        pnl_info = f"PnL: {trade['pnl']:.2f}" if trade else "N/A"
        self.logger.info(
            "EXECUTED SELL %s: %d shares @ %.2f = %.2f (%s, cash: %.2f)",
            ticker, shares, exit_price, total_proceeds, pnl_info,
            self.portfolio.cash_balance,
        )
        return order_data