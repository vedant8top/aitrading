# Market Regime Detection Framework v1 — Architecture Documentation

## Overview

The regime detection framework classifies daily market conditions into four regimes (TRENDING, RANGE_BOUND, VOLATILE, UNCERTAIN) using four indicators computed from the NIFTY 50 constituent stocks.

## Classification Methodology

### Indicators

| Indicator | Source | Calculation | Lookback |
|-----------|--------|-------------|----------|
| **ADX** | Equal-weight NIFTY 50 proxy | Wilder's DMI (DI+, DI-, ADX) | 14 periods |
| **ATR Ratio** | Equal-weight NIFTY 50 proxy | ATR(20) / ATR(100) | 20/100 periods |
| **Market Breadth** | 49 constituent stocks | (Advancing - Declining) / 49 | Daily |
| **Cross-Correlation** | 49 constituent stocks | Average pairwise 20-day return correlation | 20 periods |

### Regime Definitions

| Regime | Classification Logic |
|--------|---------------------|
| **VOLATILE** | ATR_Ratio > 1.2 AND Correlation > 0.35 |
| **TRENDING** | ADX > 20 AND Breadth > 0.30 |
| **RANGE_BOUND** | ADX < 18 AND Breadth between 0.30-0.60 |
| **UNCERTAIN** | All other conditions |

### Hysteresis

- Minimum 5-day regime duration
- Prevents flip-flopping between regimes
- Transitions only allowed after minimum duration

## Strategy-to-Regime Mapping

| Regime | Strategies | Weights |
|--------|------------|---------|
| TRENDING | donchian (0.30), breakout (0.25), momentum (0.25), ema_rsi_macd (0.20) |
| RANGE_BOUND | mean_reversion (0.40), bollinger_reversion (0.35), bear_trap (0.25) |
| VOLATILE | volatility_expansion (0.70), bear_trap (0.30) |
| UNCERTAIN | (50% cash, no new entries) |

## Transition Handling

- No forced liquidation on regime change
- Existing positions continue management normally
- New entries only from current regime's active strategies
- UNCERTAIN: 50% cash, no new entries
- Transition costs: 0.1% (slippage + brokerage)

## Limitations

1. **High UNCERTAIN percentage** (57.6%): Most of the time the classifier cannot identify a clear regime, leading to capital being held in cash
2. **Excessive transitions** (289 total, 36.6/yr): Despite hysteresis, the classifier produces too many regime changes
3. **Correlation range**: Cross-correlation rarely exceeds 0.35, making VOLATILE detection unreliable
4. **Proxy construction**: Equal-weight NIFTY proxy may not accurately represent index behavior
5. **No look-ahead bias**: Classification uses only historical data (t-1), but thresholds were calibrated on full dataset

## Generated Files

- `src/regime_detection/regime_classifier.py` — Classification engine
- `src/regime_detection/regime_switcher.py` — Strategy mapping
- `src/regime_detection/regime_aware_backtest.py` — Portfolio construction
- `src/regime_detection/regime_metrics.py` — Metrics calculation
- `data/regimes/regime_labels.csv` — Daily regime labels
- `data/regime_backtests/` — Backtest outputs
- `docs/regime_detection_results.md` — Validation results
- `docs/regime_detection_design.md` — Design document
- `docs/regime_detection_validation_plan.md` — Validation plan
- `docs/regime_detection_implementation_plan.md` — Implementation plan