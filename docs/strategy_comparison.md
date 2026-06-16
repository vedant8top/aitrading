# Strategy Comparison Guide

## Overview

The strategy comparison system validates the pluggable strategy framework by running multiple strategies against the same market data and comparing their performance.

## Architecture

```
data/processed/*_indicators.csv
            │
            ▼
  strategy_comparison.py
            │
            ├── StrategyRegistry.list_strategies()
            │       │
            │       ├── "ema_rsi_macd"     → EmaRsiMacdStrategy
            │       ├── "mean_reversion"   → MeanReversionStrategy
            │       └── "momentum"         → MomentumStrategy
            │
            ├── for each strategy:
            │     ├── SignalEngine(strategy) → generates *_signals.csv
            │     └── PortfolioBacktester.run() → performance metrics
            │
            └── outputs:
                  ├── data/strategy_comparison/signal_counts.csv
                  ├── data/strategy_comparison/portfolio_metrics.csv
                  └── data/strategy_comparison/comparison_report.md
```

## Current Registered Strategies

| Strategy Name | Class | Type | Indicators Required |
|---|---|---|---|
| `ema_rsi_macd` | `EmaRsiMacdStrategy` | Trend Following | EMA_20, EMA_50, EMA_200, RSI_14, MACD, MACD_Signal |
| `mean_reversion` | `MeanReversionStrategy` | Mean Reversion | RSI_14, Bollinger_Lower_20, SMA_20 |
| `momentum` | `MomentumStrategy` | Momentum | SMA_50, SMA_20, RSI_14, Volume, Volume_MA_20 |

## Strategy Rules

### ema_rsi_macd
- **BUY**: EMA20 > EMA50 AND Close > EMA200 AND RSI14 in [55,70] AND MACD > Signal
- **SELL**: EMA20 < EMA50 OR RSI14 < 45 OR MACD < Signal

### mean_reversion
- **BUY**: RSI14 < 30 (oversold) AND Close < Bollinger Lower Band
- **SELL**: RSI14 > 60 (overbought) OR Close > SMA20 (return to mean)

### momentum
- **BUY**: Close > SMA50 (uptrend) AND RSI14 > 60 (strong momentum) AND Volume > Volume_MA20 (confirmation)
- **SELL**: RSI14 < 50 (fading) OR Close < SMA20 (trend broken)

## Comparison Metrics

The comparison produces two output files:

### 1. Signal Counts (`signal_counts.csv`)
Per-ticker, per-strategy signal distribution:

| Column | Description |
|---|---|
| `strategy` | Strategy name |
| `ticker` | Stock ticker |
| `buy_signals` | Number of BUY signals generated |
| `sell_signals` | Number of SELL signals generated |
| `hold_signals` | Number of HOLD signals (no action) |
| `trades` | Number of completed trades |
| `status` | `"success"` or error description |

### 2. Portfolio Metrics (`portfolio_metrics.csv`)
Aggregate strategy-level performance:

| Column | Description |
|---|---|
| `strategy` | Strategy name |
| `total_buy_signals` | Total BUY signals across all tickers |
| `total_sell_signals` | Total SELL signals across all tickers |
| `total_hold_signals` | Total HOLD signals across all tickers |
| `total_trades` | Total completed trades |
| `win_rate_pct` | Percentage of winning trades |
| `total_return_pct` | Portfolio total return percentage |
| `cagr_pct` | Compound Annual Growth Rate |
| `max_drawdown_pct` | Maximum peak-to-trough drawdown |
| `sharpe_ratio` | Risk-adjusted return (annualized) |
| `profit_factor` | Gross profit / gross loss |
| `avg_win` | Average winning trade PnL (INR) |
| `avg_loss` | Average losing trade PnL (INR) |

## Running the Comparison

```bash
# Run with default settings (reads from data/processed/)
python src/strategies/strategy_comparison.py

# Specify custom paths
python src/strategies/strategy_comparison.py \
    --input-folder data/processed/ \
    --output-folder data/strategy_comparison/ \
    --log-file logs/strategy_comparison.log
```

## Adding a New Strategy to the Comparison

### Step 1: Create the strategy file
Create `src/strategies/my_strategy.py` implementing `BaseStrategy`. See [strategy_framework.md](strategy_framework.md) for details.

### Step 2: Register in `strategy_comparison.py`
In the `main()` function of `strategy_comparison.py`, add:

```python
from src.strategies.my_strategy import MyStrategy

StrategyRegistry.register(MyStrategy)
```

The comparison engine automatically discovers all registered strategies and runs them.

### Step 3: Run the comparison
```bash
python src/strategies/strategy_comparison.py
```

## Output Location

All comparison outputs are saved to:
```
data/strategy_comparison/
├── signal_counts.csv          # Per-ticker signal counts
├── portfolio_metrics.csv      # Strategy-level portfolio metrics
├── comparison_report.md       # Human-readable report
└── (no signal files - cleaned up after each run)
```

## Example Report Output

```
# Strategy Comparison Report

## Portfolio Performance Comparison

| Strategy | Return % | CAGR % | Max DD % | Sharpe | Win Rate | Trades | Profit Factor |
|----------|----------|--------|----------|--------|----------|--------|---------------|
| momentum | +12.45%  | 8.23%  | -15.20%  | 0.89   | 48.2%    | 56     | 1.45          |
| ema_rsi_macd | +8.72% | 5.91% | -11.34% | 0.72   | 52.1%    | 42     | 1.32          |
| mean_reversion | +3.15% | 2.10% | -9.87% | 0.45   | 38.5%    | 28     | 1.12          |
```

## Design Notes

1. **Shared portfolio model**: All tickers share a single capital pool ($100,000) as implemented in `backtest_engine.py`. This means portfolio-level metrics (return, drawdown, Sharpe) reflect the combined multi-ticker portfolio, not individual tickers.

2. **No modifications to backtest_engine.py**: The comparison engine uses `PortfolioBacktester` exactly as-is.

3. **Temporary files**: Signal CSV files are generated in temporary directories that are automatically cleaned up. Only the comparison results are persisted.

4. **Deterministic**: Given the same input data, comparison results are reproducible.