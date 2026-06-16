# Backtest Report

## Portfolio Results

- Signal files processed: 5
- Period: 2025-06-13 to 2026-06-12
- Initial capital: INR 100000.00
- Final equity: INR 99518.80
- Total return: -0.4812%
- CAGR: -0.4828%
- Win rate: 0.00%
- Profit factor: 0.0000
- Average win: INR 0.00
- Average loss: INR -481.20
- Maximum drawdown: -0.4812%
- Sharpe ratio: -1.5249
- Total completed trades: 1
- Open positions at end: 0

## Simulation Assumptions

- Long-only portfolio with shared starting cash of INR 100,000.
- BUY enters at the next available session's Open plus 0.05% adverse slippage.
- SELL exits at the next available session's Open minus 0.05% adverse slippage.
- Brokerage is 0.05% of traded value on both entry and exit.
- Each entry targets 10% of cash available immediately before that entry.
- Whole shares only; repeated BUY signals are ignored while already long.
- SELL signals are ignored while flat; same-open exits are processed before entries.
- Daily equity is cash plus open positions marked at that session's Close.
- Sharpe ratio uses daily portfolio returns, zero risk-free rate, and 252 sessions/year.
- CAGR uses elapsed calendar time. No taxes, dividends, or short selling are modeled.

## Completed Trades

- `RELIANCE_NS`: 2026-05-07 to 2026-05-13, 6 shares, PnL INR -481.20, return -5.57%

## Generated Files

- `data/backtests/trades.csv`
- `data/backtests/performance_summary.csv`
- `data/backtests/equity_curve.csv`
- `data/backtests/equity_curve.png`
- `docs/backtest_report.md`
