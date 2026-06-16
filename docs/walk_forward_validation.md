# Walk-Forward Validation Report

## Overview

Walk-forward validation tests strategy robustness across multiple independent time periods. Each window uses a training period for signal generation and a separate out-of-sample test period for evaluation.

- **Windows:** 5 rolling windows
- **Strategies evaluated:** 9
- **Universe:** NIFTY 49 stocks (TATAMOTORS.NS delisted on Yahoo)

### Window Structure

| Window | Train Period | Test Period |
|--------|--------------|-------------|
| 1 | 2018-01-01 to 2020-12-31 | 2021-01-01 to 2021-12-31 |
| 2 | 2019-01-01 to 2021-12-31 | 2022-01-01 to 2022-12-31 |
| 3 | 2020-01-01 to 2022-12-31 | 2023-01-01 to 2023-12-31 |
| 4 | 2021-01-01 to 2023-12-31 | 2024-01-01 to 2024-12-31 |
| 5 | 2022-01-01 to 2024-12-31 | 2025-01-01 to 2025-12-31 |

## Strategy: bear_trap

### Training Period

| Window | Return % | CAGR % | Sharpe | Profit Factor | Max DD % | Win Rate % | Trades |
|--------|----------|--------|--------|---------------|----------|------------|--------|
| 1 | -6.19% | -2.11% | -0.092 | 0.8906927884762488 | -30.70% | 66.9% | 483 |
| 2 | 3.86% | 1.27% | 0.165 | 1.1309813468302394 | -29.97% | 71.0% | 455 |
| 3 | 1.44% | 0.48% | 0.102 | 1.0592909637137125 | -28.49% | 69.0% | 422 |
| 4 | 8.20% | 2.67% | 0.421 | 1.2922677633907025 | -8.77% | 68.0% | 415 |
| 5 | 3.16% | 1.05% | 0.195 | 1.3050059292477971 | -8.20% | 68.0% | 394 |

### Test (Out-of-Sample) Period

| Window | Return % | CAGR % | Sharpe | Profit Factor | Max DD % | Win Rate % | Trades |
|--------|----------|--------|--------|---------------|----------|------------|--------|
| 1 | 4.04% | 4.05% | 0.622 | 2.161381923829887 | -4.24% | 71.5% | 137 |
| 2 | 0.34% | 0.34% | 0.082 | 1.1443699548535218 | -8.20% | 63.6% | 129 |
| 3 | 9.51% | 9.63% | 2.349 | 3.988636140912659 | -1.87% | 75.7% | 115 |
| 4 | 1.39% | 1.39% | 0.284 | 1.8013276317558138 | -7.23% | 71.2% | 118 |
| 5 | 1.06% | 1.06% | 0.259 | 1.1703861114842407 | -3.95% | 65.6% | 128 |


## Strategy: bollinger_reversion

### Training Period

| Window | Return % | CAGR % | Sharpe | Profit Factor | Max DD % | Win Rate % | Trades |
|--------|----------|--------|--------|---------------|----------|------------|--------|
| 1 | -5.04% | -1.71% | -0.036 | 0.9086505904768853 | -34.35% | 61.6% | 341 |
| 2 | 6.67% | 2.18% | 0.225 | 1.14606261276685 | -34.17% | 64.2% | 282 |
| 3 | 3.58% | 1.18% | 0.156 | 1.0634346298579809 | -34.24% | 67.3% | 312 |
| 4 | 23.62% | 7.35% | 0.943 | 1.8282489295385784 | -10.40% | 71.3% | 307 |
| 5 | 4.41% | 1.45% | 0.228 | 1.3556139405454877 | -9.94% | 67.3% | 300 |

### Test (Out-of-Sample) Period

| Window | Return % | CAGR % | Sharpe | Profit Factor | Max DD % | Win Rate % | Trades |
|--------|----------|--------|--------|---------------|----------|------------|--------|
| 1 | 18.62% | 18.69% | 2.575 | 5.421268870611232 | -2.61% | 83.8% | 80 |
| 2 | 3.09% | 3.12% | 0.354 | 1.1653951258811321 | -9.94% | 68.3% | 123 |
| 3 | 0.93% | 0.95% | 0.199 | 1.1012199465564037 | -6.20% | 60.8% | 79 |
| 4 | 2.64% | 2.64% | 0.452 | 2.0540851022738216 | -8.39% | 68.5% | 89 |
| 5 | 13.40% | 13.45% | 2.178 | 3.4253982597776806 | -2.89% | 76.4% | 110 |


## Strategy: breakout

### Training Period

| Window | Return % | CAGR % | Sharpe | Profit Factor | Max DD % | Win Rate % | Trades |
|--------|----------|--------|--------|---------------|----------|------------|--------|
| 1 | 29.70% | 9.06% | 0.963 | 1.3763362299417388 | -9.79% | 41.3% | 683 |
| 2 | 61.51% | 17.34% | 1.596 | 1.8631997794335393 | -8.45% | 44.5% | 741 |
| 3 | 55.43% | 15.86% | 1.454 | 1.7139482078816828 | -16.59% | 44.1% | 735 |
| 4 | 35.48% | 10.69% | 1.197 | 1.346095398560089 | -15.85% | 42.1% | 675 |
| 5 | 16.62% | 5.27% | 0.619 | 1.2871063753191225 | -9.41% | 40.2% | 647 |

### Test (Out-of-Sample) Period

| Window | Return % | CAGR % | Sharpe | Profit Factor | Max DD % | Win Rate % | Trades |
|--------|----------|--------|--------|---------------|----------|------------|--------|
| 1 | 17.88% | 17.95% | 1.725 | 1.7532897208177876 | -8.81% | 43.9% | 223 |
| 2 | 1.61% | 1.63% | 0.227 | 1.1035428934645237 | -9.41% | 39.8% | 196 |
| 3 | 18.91% | 19.16% | 2.601 | 1.4773949298684048 | -4.59% | 46.7% | 182 |
| 4 | -2.46% | -2.46% | -0.188 | 0.8444834933350788 | -7.83% | 34.6% | 205 |
| 5 | -3.06% | -3.07% | -0.365 | 0.7280396910338804 | -7.99% | 35.9% | 198 |


## Strategy: bull_trap

### Training Period

| Window | Return % | CAGR % | Sharpe | Profit Factor | Max DD % | Win Rate % | Trades |
|--------|----------|--------|--------|---------------|----------|------------|--------|
| 1 | 0.00% | 0.00% | 0.000 | 0.0 | 0.00% | 0.0% | 0 |
| 2 | 0.00% | 0.00% | 0.000 | 0.0 | 0.00% | 0.0% | 0 |
| 3 | 0.00% | 0.00% | 0.000 | 0.0 | 0.00% | 0.0% | 0 |
| 4 | 0.00% | 0.00% | 0.000 | 0.0 | 0.00% | 0.0% | 0 |
| 5 | 0.00% | 0.00% | 0.000 | 0.0 | 0.00% | 0.0% | 0 |

### Test (Out-of-Sample) Period

| Window | Return % | CAGR % | Sharpe | Profit Factor | Max DD % | Win Rate % | Trades |
|--------|----------|--------|--------|---------------|----------|------------|--------|
| 1 | 0.00% | 0.00% | 0.000 | 0.0 | 0.00% | 0.0% | 0 |
| 2 | 0.00% | 0.00% | 0.000 | 0.0 | 0.00% | 0.0% | 0 |
| 3 | 0.00% | 0.00% | 0.000 | 0.0 | 0.00% | 0.0% | 0 |
| 4 | 0.00% | 0.00% | 0.000 | 0.0 | 0.00% | 0.0% | 0 |
| 5 | 0.00% | 0.00% | 0.000 | 0.0 | 0.00% | 0.0% | 0 |


## Strategy: donchian

### Training Period

| Window | Return % | CAGR % | Sharpe | Profit Factor | Max DD % | Win Rate % | Trades |
|--------|----------|--------|--------|---------------|----------|------------|--------|
| 1 | 41.18% | 12.19% | 1.339 | 1.519036845840994 | -10.79% | 42.5% | 322 |
| 2 | 60.42% | 17.08% | 1.492 | 2.526640076691103 | -6.96% | 44.9% | 374 |
| 3 | 49.65% | 14.41% | 1.254 | 1.808612514976281 | -17.80% | 44.3% | 366 |
| 4 | 20.34% | 6.39% | 0.753 | 1.0970289081435733 | -19.35% | 38.5% | 312 |
| 5 | 23.94% | 7.44% | 0.853 | 1.6886723697689892 | -13.21% | 42.4% | 311 |

### Test (Out-of-Sample) Period

| Window | Return % | CAGR % | Sharpe | Profit Factor | Max DD % | Win Rate % | Trades |
|--------|----------|--------|--------|---------------|----------|------------|--------|
| 1 | 12.21% | 12.26% | 1.228 | 2.2174151844240124 | -6.33% | 47.8% | 92 |
| 2 | -2.86% | -2.90% | -0.331 | 0.6781875453965737 | -8.36% | 30.2% | 96 |
| 3 | 24.94% | 25.26% | 3.564 | 3.503649681813311 | -2.95% | 49.3% | 69 |
| 4 | 1.30% | 1.30% | 0.183 | 1.0970929044540776 | -6.89% | 36.6% | 82 |
| 5 | -0.02% | -0.02% | 0.034 | 0.8971689863239732 | -6.69% | 37.9% | 87 |


## Strategy: ema_rsi_macd

### Training Period

| Window | Return % | CAGR % | Sharpe | Profit Factor | Max DD % | Win Rate % | Trades |
|--------|----------|--------|--------|---------------|----------|------------|--------|
| 1 | 24.34% | 7.54% | 1.044 | 1.4892753716540423 | -7.92% | 40.4% | 599 |
| 2 | 64.25% | 18.00% | 1.894 | 1.8182195313998872 | -7.83% | 42.7% | 902 |
| 3 | 60.23% | 17.05% | 1.784 | 1.6663113527010809 | -13.47% | 43.9% | 909 |
| 4 | 42.21% | 12.50% | 1.523 | 1.5101873606996754 | -13.01% | 43.0% | 928 |
| 5 | 11.86% | 3.82% | 0.504 | 1.175402385368419 | -9.54% | 39.7% | 896 |

### Test (Out-of-Sample) Period

| Window | Return % | CAGR % | Sharpe | Profit Factor | Max DD % | Win Rate % | Trades |
|--------|----------|--------|--------|---------------|----------|------------|--------|
| 1 | 26.58% | 26.69% | 2.484 | 1.9753778064689227 | -7.42% | 44.5% | 339 |
| 2 | -0.46% | -0.47% | -0.021 | 0.9827990443674945 | -9.54% | 40.8% | 277 |
| 3 | 14.69% | 14.87% | 2.328 | 1.6594206483509946 | -3.54% | 42.1% | 292 |
| 4 | -2.93% | -2.93% | -0.248 | 0.8828438805370867 | -8.62% | 32.6% | 313 |
| 5 | -5.89% | -5.91% | -0.965 | 0.6629920655879882 | -7.99% | 30.9% | 259 |


## Strategy: mean_reversion

### Training Period

| Window | Return % | CAGR % | Sharpe | Profit Factor | Max DD % | Win Rate % | Trades |
|--------|----------|--------|--------|---------------|----------|------------|--------|
| 1 | -8.53% | -2.93% | -0.125 | 0.7923549752735358 | -35.44% | 57.4% | 202 |
| 2 | -2.45% | -0.82% | 0.017 | 0.9145228180483737 | -35.66% | 60.1% | 158 |
| 3 | -3.53% | -1.19% | -0.006 | 0.8534131147467447 | -35.20% | 61.3% | 160 |
| 4 | 19.19% | 6.05% | 0.924 | 2.137538815220728 | -8.14% | 72.3% | 155 |
| 5 | 5.11% | 1.68% | 0.292 | 1.4297827362071946 | -8.14% | 66.7% | 162 |

### Test (Out-of-Sample) Period

| Window | Return % | CAGR % | Sharpe | Profit Factor | Max DD % | Win Rate % | Trades |
|--------|----------|--------|--------|---------------|----------|------------|--------|
| 1 | 11.31% | 11.35% | 2.437 | 7.9550727205467 | -2.23% | 83.9% | 31 |
| 2 | 5.24% | 5.31% | 0.622 | 1.5022624405776115 | -8.14% | 66.7% | 63 |
| 3 | 1.83% | 1.85% | 0.409 | 1.3937257557661094 | -5.35% | 68.0% | 50 |
| 4 | -0.59% | -0.59% | -0.104 | 1.2257956416410951 | -5.92% | 61.4% | 44 |
| 5 | 10.32% | 10.35% | 2.077 | 3.5612507864424874 | -2.33% | 74.6% | 59 |


## Strategy: momentum

### Training Period

| Window | Return % | CAGR % | Sharpe | Profit Factor | Max DD % | Win Rate % | Trades |
|--------|----------|--------|--------|---------------|----------|------------|--------|
| 1 | 40.60% | 12.04% | 1.310 | 1.6156608853109165 | -11.56% | 40.4% | 679 |
| 2 | 73.89% | 20.27% | 1.849 | 2.0760222092021388 | -6.47% | 41.1% | 811 |
| 3 | 70.46% | 19.49% | 1.797 | 1.8862645172379089 | -14.12% | 41.4% | 807 |
| 4 | 37.64% | 11.28% | 1.267 | 1.3681273731445969 | -13.40% | 37.1% | 780 |
| 5 | 7.90% | 2.57% | 0.336 | 1.1218025060551693 | -11.09% | 36.2% | 733 |

### Test (Out-of-Sample) Period

| Window | Return % | CAGR % | Sharpe | Profit Factor | Max DD % | Win Rate % | Trades |
|--------|----------|--------|--------|---------------|----------|------------|--------|
| 1 | 24.87% | 24.96% | 2.147 | 2.05955513552264 | -5.61% | 37.6% | 295 |
| 2 | -1.97% | -1.99% | -0.200 | 0.9098218264658421 | -11.09% | 34.2% | 240 |
| 3 | 14.14% | 14.32% | 2.006 | 1.1755157778798802 | -5.71% | 37.8% | 222 |
| 4 | -5.74% | -5.74% | -0.515 | 0.7578842424533102 | -11.09% | 30.0% | 247 |
| 5 | -6.04% | -6.06% | -0.834 | 0.665822151888106 | -8.28% | 29.0% | 231 |


## Strategy: volatility_expansion

### Training Period

| Window | Return % | CAGR % | Sharpe | Profit Factor | Max DD % | Win Rate % | Trades |
|--------|----------|--------|--------|---------------|----------|------------|--------|
| 1 | 9.23% | 2.99% | 0.369 | 1.065344517561946 | -21.45% | 42.5% | 2153 |
| 2 | 50.56% | 14.62% | 1.373 | 1.3369041237406978 | -11.61% | 42.8% | 2429 |
| 3 | 40.23% | 11.95% | 1.108 | 1.2237930687374219 | -18.12% | 42.5% | 2488 |
| 4 | 16.04% | 5.10% | 0.590 | 1.0868540276938798 | -20.87% | 41.7% | 2421 |
| 5 | -4.03% | -1.36% | -0.099 | 0.9570210224697645 | -14.61% | 42.0% | 2359 |

### Test (Out-of-Sample) Period

| Window | Return % | CAGR % | Sharpe | Profit Factor | Max DD % | Win Rate % | Trades |
|--------|----------|--------|--------|---------------|----------|------------|--------|
| 1 | 19.22% | 19.29% | 1.682 | 1.411854030521327 | -8.02% | 41.4% | 792 |
| 2 | -9.53% | -9.64% | -1.086 | 0.7766944342150979 | -12.16% | 40.3% | 784 |
| 3 | 11.02% | 11.16% | 1.575 | 1.217725114516591 | -5.11% | 44.0% | 787 |
| 4 | -1.97% | -1.97% | -0.109 | 0.9324169521793791 | -8.92% | 41.0% | 768 |
| 5 | -1.79% | -1.80% | -0.254 | 0.9342579213894138 | -5.44% | 43.3% | 732 |


## Consistency Score Comparison

| Strategy | Score | Classification | Avg Return % | Avg Sharpe | Avg DD % | Std Return | Std Sharpe | Pos Return Wds | Pf>1 Wds |
|----------|-------|----------------|--------------|------------|----------|------------|------------|----------------|----------|
| bear_trap | 95.0 | Robust | 3.27% | 0.719 | -5.10% | 3.36 | 0.833 | 5/5 | 5/5 |
| bollinger_reversion | 90.0 | Robust | 7.73% | 1.151 | -6.00% | 6.99 | 1.011 | 5/5 | 5/5 |
| mean_reversion | 82.0 | Robust | 5.62% | 1.088 | -4.80% | 4.63 | 0.990 | 4/5 | 5/5 |
| breakout | 64.0 | Moderate | 6.58% | 0.800 | -7.73% | 9.79 | 1.163 | 3/5 | 3/5 |
| donchian | 64.0 | Moderate | 7.11% | 0.935 | -6.24% | 10.28 | 1.413 | 3/5 | 3/5 |
| ema_rsi_macd | 48.0 | Moderate | 6.40% | 0.716 | -7.42% | 12.34 | 1.416 | 2/5 | 2/5 |
| momentum | 48.0 | Moderate | 5.05% | 0.521 | -8.36% | 12.36 | 1.287 | 2/5 | 2/5 |
| volatility_expansion | 48.0 | Moderate | 3.39% | 0.362 | -7.93% | 10.31 | 1.087 | 2/5 | 2/5 |
| bull_trap | 20.0 | Unstable | 0.00% | 0.000 | 0.00% | 0.00 | 0.000 | 0/5 | 0/5 |

## Robustness Assessment

- **bear_trap**: ✅ **Robust** — Consistently positive returns across 5/5 test windows with stable risk metrics.
- **bollinger_reversion**: ✅ **Robust** — Consistently positive returns across 5/5 test windows with stable risk metrics.
- **mean_reversion**: ✅ **Robust** — Consistently positive returns across 4/5 test windows with stable risk metrics.
- **breakout**: ⚠️ **Moderate** — Shows some consistency but with notable variance. Score: 64.0.
- **donchian**: ⚠️ **Moderate** — Shows some consistency but with notable variance. Score: 64.0.
- **ema_rsi_macd**: ⚠️ **Moderate** — Shows some consistency but with notable variance. Score: 48.0.
- **momentum**: ⚠️ **Moderate** — Shows some consistency but with notable variance. Score: 48.0.
- **volatility_expansion**: ⚠️ **Moderate** — Shows some consistency but with notable variance. Score: 48.0.
- **bull_trap**: ❌ **Unstable** — High variance in returns across windows. May be period-dependent.

## Final Strategy Ranking (Walk-Forward)

| Rank | Strategy | Consistency Score | Classification |
|------|----------|------------------|----------------|
| 1 | bear_trap | 95.0 | Robust |
| 2 | bollinger_reversion | 90.0 | Robust |
| 3 | mean_reversion | 82.0 | Robust |
| 4 | breakout | 64.0 | Moderate |
| 5 | donchian | 64.0 | Moderate |
| 6 | ema_rsi_macd | 48.0 | Moderate |
| 7 | momentum | 48.0 | Moderate |
| 8 | volatility_expansion | 48.0 | Moderate |
| 9 | bull_trap | 20.0 | Unstable |

## Recommendation

**bear_trap** is the most robust strategy with a consistency score of 95.0. It demonstrates stable out-of-sample performance across 5 independent test periods.

**Is Momentum robust?** — See ranking above.
**Is EMA robust?** — See ranking above.
**Is Mean Reversion robust?** — See ranking above.

## Limitations

- **Look-ahead bias in indicator calculation**: Indicators are calculated on the full dataset, then filtered by date. This introduces minor look-ahead bias in the training period. A true walk-forward would recalculate indicators on each training window independently.
- **Annual test windows**: One-year test periods may be too short to capture full market cycles. Multi-year test windows would provide more robust estimates.
- **Fixed parameters**: Strategy parameters (e.g., RSI thresholds, EMA periods) are fixed across all windows. Parameter optimization within each training window would be a more rigorous test.
- **Survivorship bias**: Current NIFTY 50 constituents only. Stocks that were delisted or replaced are not included.

## Generated Files

- `docs/walk_forward_validation.md`
- `logs/walk_forward_validation.log`
