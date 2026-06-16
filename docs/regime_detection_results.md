# Regime Detection Framework v1 — Validation Results

## Executive Summary

**Recommendation: NO GO**

The regime-aware strategy selection framework does NOT improve performance versus the best standalone strategy (Donchian). The framework was fully implemented, validated, and rejected based on quantitative criteria.

## Implementation Summary

### Files Created
| File | Purpose |
|------|---------|
| `src/regime_detection/regime_classifier.py` | Daily regime classification (ADX, ATR ratio, breadth, correlation) |
| `src/regime_detection/regime_switcher.py` | Strategy-to-regime mapping and transition tracking |
| `src/regime_detection/regime_aware_backtest.py` | Portfolio construction from existing strategy results |
| `src/regime_detection/regime_metrics.py` | Regime-specific performance metrics |
| `data/regimes/regime_labels.csv` | Daily regime labels (1,988 dates, 2018-2026) |

### Classification Results

| Regime | Days | Percentage |
|--------|------|------------|
| TRENDING | 529 | 26.6% |
| RANGE_BOUND | 226 | 11.4% |
| VOLATILE | 88 | 4.4% |
| UNCERTAIN | 1,145 | 57.6% |

## Performance Comparison

### Full-Period Results (2018-2026)

| Strategy | Return % | Sharpe | Max DD % | Win Rate % |
|----------|----------|--------|----------|------------|
| **Donchian** | **85.29** | **0.812** | -20.47 | 41.70 |
| **Momentum** | 69.71 | 0.748 | -18.72 | 37.64 |
| EMA RSI MACD | 57.30 | 0.725 | -18.27 | 39.32 |
| Breakout | 56.91 | 0.619 | -17.63 | 40.29 |
| Bollinger Reversion | 25.56 | 0.304 | -34.35 | 65.54 |
| Equal-Weight | 36.68 | 0.418 | -21.89 | 44.16 |
| **Regime-Aware** | **20.66** | **0.228** | **-9.95** | **20.21** |

### Acceptance Criteria

| Criterion | Target | Actual | Result |
|-----------|--------|--------|--------|
| Return > Donchian | > 85.29% | 20.66% | **NO** |
| Sharpe > 0.90 | > 0.90 | 0.228 | **NO** |
| Max DD < 18% | > -18% | -9.95% | **YES** |
| Transitions < 12/yr | < 12/yr | 36.6/yr | **NO** |

### Decision: 1/4 criteria met → **REJECTED**

## Root Cause Analysis

### Why Did It Fail?

1. **57.6% UNCERTAIN days**: The classifier could not identify a clear regime for most of the period. This means capital sat in cash (50% allocation) earning zero returns, severely dragging down total return.

2. **289 regime transitions** (36.6/yr): Despite hysteresis, the classifier produced far too many regime changes. Each transition incurs costs and reduces portfolio stability.

3. **Correlation range limitations**: Cross-sectional correlation rarely exceeded 0.35, making VOLATILE detection nearly impossible. The VOLATILE regime captured only 4.4% of days.

4. **Regime detection does not add value**: Even in TRENDING regime, Donchian (85.29%) outperformed the weighted regime portfolio (20.66%). The regime-switching mechanism underperforms simply running the best strategy continuously.

5. **False diversification**: Combining strategies across regimes does not produce better risk-adjusted returns than the best single strategy alone.

## Key Insights

### What We Learned

1. **Simple beats complex**: Donchian (single strategy, 85.29%, Sharpe 0.812) outperforms the regime-aware portfolio (20.66%, Sharpe 0.228) by a large margin.

2. **Regime detection is unreliable**: The 4-indicator approach cannot reliably classify market regimes. UNCERTAIN dominates the classification.

3. **Strategy diversification has limits**: Running multiple strategies simultaneously does not improve returns when the best strategy already performs well.

4. **Transition costs are prohibitive**: 289 transitions at 0.1% each create significant drag (28.90% cost drag).

5. **Cash drag kills returns**: 57.6% of days in UNCERTAIN (50% cash) fundamentally undermines performance.

### Recommendations

1. **Do not implement** regime detection v1 in production.
2. **Consider alternative approaches**: ML-based regime detection, simpler trend filters, or ensemble methods.
3. **Focus on single-strategy optimization**: Improving Donchian's parameters may yield better risk-adjusted returns.
4. **Revisit regime detection** only if: (a) classifier accuracy improves to >80%, (b) UNCERTAIN drops below 20%, (c) transitions fall below 12/yr.

## Files Generated

| File | Description |
|------|-------------|
| `docs/regime_detection_results.md` | This document |
| `docs/regime_detection_architecture.md` | Architecture documentation |
| `docs/regime_detection_design.md` | Design document |
| `docs/regime_detection_validation_plan.md` | Validation plan |
| `docs/regime_detection_implementation_plan.md` | Implementation plan |
| `data/regimes/regime_labels.csv` | Daily regime labels |
| `data/regime_backtests/` | Backtest outputs |
| `src/regime_detection/` | Framework source code |
| `scripts/run_regime_validation.py` | Validation runner |
| `scripts/check_regime_distribution.py` | Distribution analysis |

---

*Validation Date: 2026-06-15*  
*Framework Version: 1.0*  
*Decision: NO GO*