# Strategy Expansion Report — v1

## Overview

This report evaluates all 9 trading strategies across:
- **Large-scale validation**: Full 8.5-year period (2018-01 to 2026-06), 49 NIFTY stocks
- **Walk-forward validation**: 5 rolling windows with out-of-sample test periods
- **Consistency scoring**: 0-100 robustness classification

## Strategy Library

| # | Strategy | Family | BUY Logic | SELL Logic |
|---|----------|--------|-----------|------------|
| 1 | momentum | Trend Following | RSI>70, MACD>Signal, Close>EMA20 | RSI<45 or MACD<Signal |
| 2 | ema_rsi_macd | Trend Following | EMA20>EMA50, Close>EMA200, RSI[55,70], MACD>Signal | EMA20<EMA50 or RSI<45 or MACD<Signal |
| 3 | breakout | Breakout | Close > 20-day high + Volume > MA20 | Close < 10-day low |
| 4 | donchian | Breakout | Close > 55-day high | Close < 20-day low |
| 5 | mean_reversion | Mean Reversion | RSI<30, Close<Bollinger Lower | RSI>60 or Close>SMA20 |
| 6 | bollinger_reversion | Mean Reversion | Close<Lower Band, RSI<35 | Close>Middle Band |
| 7 | bear_trap | Trap Detection | False breakdown below support + recovery | Close>SMA20 |
| 8 | bull_trap | Trap Detection | N/A (SELL-only) | False breakout above resistance + failure |
| 9 | volatility_expansion | Volatility | ATR↑, Volume↑, Close>SMA50 | ATR↓ or Close<SMA20 |

## Combined Results

| Rank | Strategy | Return % | CAGR % | Sharpe | Win Rate | Trades | Profit Factor | Max DD % | WF Score | Classification |
|------|----------|----------|--------|--------|----------|--------|---------------|----------|----------|----------------|
| 1 | **donchian** | **85.29%** | **7.58%** | **0.812** | 9.2% | 1012 | 1.5071 | -20.47% | 64.0 | ✅ Moderate |
| 2 | momentum | 69.71% | 6.46% | 0.748 | 37.6% | 2144 | 1.2665 | -18.72% | 48.0 | ⚠️ Moderate |
| 3 | ema_rsi_macd | 57.30% | 5.51% | 0.725 | 39.3% | 2276 | 1.2391 | -18.27% | 48.0 | ⚠️ Moderate |
| 4 | breakout | 56.91% | 5.48% | 0.619 | 18.4% | 2033 | 1.3234 | -17.63% | 64.0 | ✅ Moderate |
| 5 | bollinger_reversion | 25.56% | 2.73% | 0.304 | 37.4% | 920 | 1.1110 | -34.35% | **90.0** | ✅ **Robust** |
| 6 | volatility_expansion | 15.97% | 1.77% | 0.238 | 42.2% | 6532 | 1.0802 | -21.45% | 48.0 | ⚠️ Moderate |
| 7 | **mean_reversion** | **15.34%** | **1.70%** | **0.220** | **63.1%** | **507** | **1.2066** | **-35.44%** | **82.0** | ✅ **Robust** |
| 8 | bear_trap | 4.05% | 0.47% | 0.098 | 49.0% | 1259 | 1.0296 | -30.70% | **95.0** | ✅ **Robust** |
| 9 | bull_trap | 0.00% | 0.00% | 0.000 | 0.0% | 0 | 0.0000 | 0.00% | 20.0 | ❌ Unstable |

## Walk-Forward Test Performance (Out-of-Sample)

| Strategy | W1 2021 | W2 2022 | W3 2023 | W4 2024 | W5 2025 | Pos Wins | Avg Return |
|----------|---------|---------|---------|---------|---------|----------|------------|
| bear_trap | +4.04% | +0.34% | +9.51% | +1.39% | +1.06% | **5/5** | +3.27% |
| bollinger_reversion | +18.62% | +3.09% | +0.93% | +2.64% | +13.40% | **5/5** | +7.74% |
| mean_reversion | +11.31% | +5.24% | +1.83% | -0.59% | +10.32% | 4/5 | +5.62% |
| breakout | +17.88% | +1.61% | +18.91% | -2.46% | -3.06% | 3/5 | +6.58% |
| donchian | +12.21% | -2.86% | +24.94% | +1.30% | -0.02% | 3/5 | +7.11% |
| momentum | +24.87% | -1.97% | +14.14% | -5.74% | -6.04% | 2/5 | +5.05% |
| ema_rsi_macd | +26.58% | -0.46% | +14.69% | -2.93% | -5.89% | 2/5 | +6.40% |
| volatility_expansion | +19.22% | -9.53% | +11.02% | -1.97% | -1.79% | 2/5 | +3.39% |
| bull_trap | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% | 0/5 | 0.00% |

## Robustness Classification

### ✅ Robust (3 strategies)
1. **bear_trap** (95.0) — Positive in ALL 5 test windows. Low variance. Reliable but modest returns.
2. **bollinger_reversion** (90.0) — Positive in ALL 5 test windows. Strong mean-reversion edge.
3. **mean_reversion** (82.0) — Positive in 4/5 windows. Most consistent strategy family overall.

### ⚠️ Moderate (5 strategies)
4. **breakout** (64.0) — 3/5 positive windows but large variance (+18.9% to -3.1%).
5. **donchian** (64.0) — 3/5 positive windows, extreme variance (+24.9% to -2.9%).
6. **momentum** (48.0) — 2/5 positive windows. Works in trending years, fails in others.
7. **ema_rsi_macd** (48.0) — Mirrors momentum. Period-dependent.
8. **volatility_expansion** (48.0) — 2/5 positive windows. High trade count but inconsistent.

### ❌ Unstable (1 strategy)
9. **bull_trap** (20.0) — Generates zero trades. Logic never triggers.

## Final Leaderboard

| Rank | Strategy | Score | Classification | Action |
|------|----------|-------|----------------|--------|
| 1 | bear_trap | 95.0 | ✅ Robust | ✅ **SURVIVE** — Advance to market regime detection |
| 2 | bollinger_reversion | 90.0 | ✅ Robust | ✅ **SURVIVE** — Advance to market regime detection |
| 3 | mean_reversion | 82.0 | ✅ Robust | ✅ **SURVIVE** — Already advanced |
| 4 | breakout | 64.0 | ⚠️ Moderate | ⏳ Retain — Needs parameter tuning |
| 5 | donchian | 64.0 | ⚠️ Moderate | ⏳ Retain — Needs parameter tuning |
| 6 | ema_rsi_macd | 48.0 | ⚠️ Moderate | ⏳ Retain — Needs regime filter |
| 7 | momentum | 48.0 | ⚠️ Moderate | ⏳ Retain — Needs regime filter |
| 8 | volatility_expansion | 48.0 | ⚠️ Moderate | ⏳ Retain — Needs volatility filter |
| 9 | bull_trap | 20.0 | ❌ Unstable | ❌ **DISCARD** — Zero trades generated |

## Recommendations

### Strategies to Survive (Advance to Market Regime Detection)
1. **bear_trap** — Most robust strategy (95.0). Positive returns in all 5 test windows. Low variance. Ideal for mean-reverting / range-bound regimes.
2. **bollinger_reversion** — Robust (90.0). Positive in all windows. Strong mean-reversion edge. Good for oversold bounces.
3. **mean_reversion** — Original robust strategy (82.0). Complementary to bollinger_reversion.

### Strategies to Reject
- **bull_trap** — Zero trades across all windows and full period. Logic never triggers.

### Strategies to Retain with Tuning
- **breakout** and **donchian** — Show promise (highest total returns) but high variance across windows. Need walk-forward parameter optimization.
- **momentum** and **ema_rsi_macd** — Period-dependent. Could be deployed with a trend regime filter.
- **volatility_expansion** — High trade count but inconsistent. Needs volatility threshold tuning.

### Key Insight
The **three Robust strategies are all mean-reversion / trap-detection** approaches that profit from false moves. The **trend-following strategies (momentum, ema_rsi_macd, donchian)** generate higher absolute returns but fail in 3 of 5 out-of-sample years. A combined portfolio using regime detection could select between these families based on market conditions.

## Generated Files
- `data/strategy_comparison/portfolio_metrics.csv` — Full-period metrics for all 9 strategies
- `docs/walk_forward_validation.md` — Detailed walk-forward results
- `docs/strategy_expansion_report.md` — This report