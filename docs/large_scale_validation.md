# Large-Scale Statistical Validation Report

## Overview

This report evaluates all registered trading strategies over an expanded NIFTY 50 universe with 5+ years of historical daily data. The goal is to determine whether any strategy exhibits a statistically meaningful edge.

### Dataset

- **Universe:** NIFTY 50 stocks
- **Period:** 2018-01-01 to latest available date
- **Timeframe:** Daily
- **Data source:** Yahoo Finance (via yfinance)
- **Backtest assumptions:** Long-only, next-open execution, 0.05% brokerage, 0.05% slippage, 10% position sizing

## Final Strategy Leaderboard

| Rank | Strategy | Return % | CAGR % | Sharpe | Win Rate | Trades | Trades/Yr | Avg Hold Days | Profit Factor | Max DD % | Confidence |
|------|----------|----------|--------|--------|----------|--------|-----------|----------------|---------------|----------|------------|
| 1 | momentum | 69.71% | 6.46% | 0.748 | 37.6% | 2144 | 198.8 | 22 | 1.2665 | -18.72% | High Confidence |
| 2 | ema_rsi_macd | 57.30% | 5.51% | 0.725 | 39.3% | 2276 | 218.9 | 15 | 1.2391 | -18.27% | High Confidence |
| 3 | mean_reversion | 15.34% | 1.70% | 0.220 | 63.1% | 507 | 56.3 | 24 | 1.2066 | -35.44% | High Confidence |

## Per-Strategy Analysis

### 1. momentum

**Performance Metrics:**

- Total trades: 2144
- Trades per year: 198.8
- Average holding period: 22 days
- Win rate: 37.6%
- Total return: 69.71%
- CAGR: 6.46%
- Sharpe ratio: 0.748
- Profit factor: 1.2665
- Maximum drawdown: -18.72%
- Average win: INR 387.75
- Average loss: INR -184.79

**Confidence Level:** High Confidence

**Rankings:**
- Return rank: 1
- Sharpe rank: 1
- Profit factor rank: 1
- Drawdown rank: 2
- Composite score: 1.2 (lower is better)

### 2. ema_rsi_macd

**Performance Metrics:**

- Total trades: 2276
- Trades per year: 218.9
- Average holding period: 15 days
- Win rate: 39.3%
- Total return: 57.30%
- CAGR: 5.51%
- Sharpe ratio: 0.725
- Profit factor: 1.2391
- Maximum drawdown: -18.27%
- Average win: INR 332.07
- Average loss: INR -173.68

**Confidence Level:** High Confidence

**Rankings:**
- Return rank: 2
- Sharpe rank: 2
- Profit factor rank: 2
- Drawdown rank: 1
- Composite score: 1.8 (lower is better)

### 3. mean_reversion

**Performance Metrics:**

- Total trades: 507
- Trades per year: 56.3
- Average holding period: 24 days
- Win rate: 63.1%
- Total return: 15.34%
- CAGR: 1.70%
- Sharpe ratio: 0.220
- Profit factor: 1.2066
- Maximum drawdown: -35.44%
- Average win: INR 275.99
- Average loss: INR -391.41

**Confidence Level:** High Confidence

**Rankings:**
- Return rank: 3
- Sharpe rank: 3
- Profit factor rank: 3
- Drawdown rank: 3
- Composite score: 3.0 (lower is better)

## Best-in-Class Summary

- **Best return:** momentum (69.71%)
- **Best Sharpe:** momentum (0.748)
- **Best profit factor:** momentum (1.2665)
- **Lowest drawdown:** ema_rsi_macd (-18.27%)

## Confidence Assessment

Confidence is determined by the number of completed trades:

- **High Confidence:** 100+ trades
- **Medium Confidence:** 30–99 trades
- **Low Confidence:** fewer than 30 trades

- **momentum:** High Confidence
- **ema_rsi_macd:** High Confidence
- **mean_reversion:** High Confidence

## Recommendation

### Advance to Risk-Management Testing

**momentum** — ranked #1 overall with a composite score of 1.2. It achieved 69.71% return across 2144 trades with a Sharpe of 0.748 and win rate of 37.6%. Confidence: High Confidence.

## Caveats & Limitations

- **Survivorship bias:** The NIFTY 50 composition changes over time. Constituents that were replaced during 2018–2026 are not included.
- **Look-ahead bias:** Indicators are calculated on the full历史 dataset without walk-forward validation. Future work should implement expanding or rolling window validation.
- **Single time frame:** All results are based on daily data. Intraday or multi-timeframe analysis may yield different conclusions.
- **Parameter overfitting:** Current strategy parameters are fixed. Robustness should be verified via sensitivity analysis.
- **No transaction costs beyond brokerage/slippage:** Market impact, STT, SEBI charges, and GST are not modeled.
- **Yahoo Finance data quality:** Splits, dividends, and corporate actions are handled by yfinance's auto_adjust=False mode. Manual verification of individual ticker data is recommended.

## Generated Files

- `data/strategy_comparison/portfolio_metrics.csv`
- `data/strategy_comparison/signal_counts.csv`
- `data/strategy_comparison/comparison_report.md`
- `docs/large_scale_validation.md`
- `logs/large_scale_validation.log`
