# Market Regime Detection Framework v1 — Implementation Plan

## Architecture Overview

### Existing Components (Reuse)
- **PortfolioBacktester** (`src/backtesting/backtest_engine.py`) — Core backtesting logic
- **StrategyRegistry** (`src/strategies/strategy_registry.py`) — Strategy discovery
- **SignalEngine** (`src/strategies/signal_engine.py`) — Signal generation
- **TechnicalIndicatorEngine** (`src/feature_engineering/technical_indicators.py`) — Indicators
- **WalkForwardValidator** (`src/validation/walk_forward_validator.py`) — Validation framework
- **LargeScaleValidator** (`src/validation/large_scale_validator.py`) — Full-period validation

### New Components (Create)
```
src/regime_detection/
├── __init__.py
├── regime_classifier.py      # Compute regime labels (ADX, ATR ratio, breadth, correlation)
├── regime_switcher.py        # Map strategies to regimes + hysteresis
├── regime_aware_backtest.py  # Extend PortfolioBacktester for regime-aware execution
├── regime_metrics.py         # Regime-specific metrics calculation
└── regime_report.py          # Reporting utilities
```

### Data Flow
```
Raw OHLCV (49 stocks + NIFTY index proxy)
    → TechnicalIndicatorEngine (existing)
    → Regime Indicators (ADX, ATR20/ATR100, Breadth, Correlation)
    → RegimeClassifier → regime_labels.csv
    → RegimeSwitcher → strategy weights per regime
    → RegimeAwareBacktester → portfolio results
    → RegimeMetrics → validation reports
```

---

## Implementation Steps

### Phase 1: Core Infrastructure (regime_classifier.py)

**Inputs:** 49 stock OHLCV data (from `data/raw/`) + NIFTY index proxy (use equal-weight portfolio of 49 stocks)

**Indicators to Compute:**
1. **ADX (14)** — Wilder's DMI on NIFTY proxy
2. **ATR Volatility Ratio** — ATR_20 / ATR_100 on NIFTY proxy
3. **Market Breadth** — (Advancing - Declining) / 49 stocks daily
4. **Cross-Sectional Correlation** — 20-day rolling avg pairwise correlation of 49 stocks

**Classification Logic (No VIX for v1):**
```
IF ATR_ratio > 1.5 AND Correlation > 0.7:
    REGIME = VOLATILE
ELIF ADX > 25 AND Breadth > 0.55:
    REGIME = TRENDING
ELIF ADX < 20 AND Breadth BETWEEN 0.40 AND 0.60:
    REGIME = RANGE_BOUND
ELSE:
    REGIME = UNCERTAIN
```

**Hysteresis:**
- Minimum 5-day regime duration
- Enter TRENDING at ADX>25, exit at ADX<20
- Enter VOLATILE at ATR_ratio>1.5, exit at ATR_ratio<1.2
- Enter RANGE_BOUND at ADX<20, exit at ADX>25

**Output:** `data/regimes/regime_labels.csv` with columns: Date, Regime, ADX, ATR_Ratio, Breadth, Correlation

### Phase 2: Strategy Mapping (regime_switcher.py)

**Regime → Strategy Mapping:**

| Regime | Strategies | Weights |
|--------|------------|---------|
| TRENDING | donchian, breakout, momentum, ema_rsi_macd | 0.30, 0.25, 0.25, 0.20 |
| RANGE_BOUND | mean_reversion, bollinger_reversion, bear_trap | 0.40, 0.35, 0.25 |
| VOLATILE | volatility_expansion, bear_trap | 0.70, 0.30 |
| UNCERTAIN | (50% cash, no new entries) | N/A |

**Transition Rules:**
- Existing positions: Continue management (stops, exits) normally
- New entries: Only from current regime's active strategies
- UNCERTAIN: No new entries, manage existing only
- No forced liquidation on regime change

### Phase 3: Regime-Aware Backtester (regime_aware_backtest.py)

**Extend PortfolioBacktester:**
- Accept `regime_labels: pd.Series` and `regime_weights: dict`
- Override `get_active_strategies(date)` → returns strategy weights for regime
- Modify signal processing: filter signals by active strategies
- Position sizing: `base_size * strategy_weight * regime_weight`
- Reuse all risk management, position management, metrics calculation

### Phase 4: Regime Metrics (regime_metrics.py)

**Calculate:**
- Regime purity (ex-post validation)
- Regime utilization (% capital deployed)
- Transition count & cost drag
- Strategy contribution by regime
- Regime alpha (vs regime-matched benchmark)

### Phase 5: Validation Workflow

**Run:**
1. Full-period validation (2018-2026)
2. Walk-forward validation (5 windows)
3. Regime metrics validation
4. Compare vs baselines: Donchian, Momentum, Bollinger Reversion, Equal-Weight, NIFTY 50

### Phase 6: Documentation & Decision

**Generate:**
- `docs/regime_detection_architecture.md`
- `docs/regime_detection_results.md`
- Final recommendation: GO / CONDITIONAL GO / NO GO

---

## Technical Details

### NIFTY Index Proxy Construction
Since no NIFTY index data exists in `data/raw/`, construct equal-weight portfolio:
```python
# For each date, average Close across all 49 stocks
nifty_proxy = pd.concat([df.set_index('Date')['Close'] for df in all_stocks], axis=1).mean(axis=1)
```

### ADX Calculation (Wilder's DMI)
```python
def calculate_adx(high, low, close, period=14):
    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm < 0] = 0
    
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)
    
    atr = tr.ewm(alpha=1/period, adjust=False).mean()
    plus_di = 100 * (plus_dm.ewm(alpha=1/period, adjust=False).mean() / atr)
    minus_di = 100 * (minus_dm.ewm(alpha=1/period, adjust=False).mean() / atr)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    adx = dx.ewm(alpha=1/period, adjust=False).mean()
    return adx
```

### Cross-Sectional Correlation
```python
# 20-day rolling correlation matrix of 49 stocks' daily returns
returns = pd.DataFrame({ticker: df.set_index('Date')['Close'].pct_change() for ticker, df in all_stocks})
corr_matrix = returns.rolling(20).corr()
# Average pairwise correlation (upper triangle)
avg_corr = corr_matrix.groupby(level=0).apply(lambda x: x.values[np.triu_indices_from(x.values, k=1)].mean())
```

### Market Breadth
```python
# Daily: (advancing - declining) / total
daily_returns = returns.loc[date]
advancing = (daily_returns > 0).sum()
declining = (daily_returns < 0).sum()
breadth = (advancing - declining) / 49
```

---

## Acceptance Criteria (from Validation Plan)

| Metric | Threshold |
|--------|-----------|
| Total Return | > 85.29% (beat Donchian) |
| Sharpe Ratio | > 0.90 |
| Max Drawdown | < 18% |
| Walk-Forward Consistency | ≥ 4/5 positive windows |
| Regime Purity | > 65% |
| Transition Frequency | < 12/year |
| Transition Cost Drag | < 2% |

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| No NIFTY index data | Equal-weight proxy from 49 stocks |
| Look-ahead bias | Strict t-1 data only, regime at t uses data ≤ t-1 |
| Overfitting | Fixed thresholds, no optimization on test windows |
| Transition costs | Explicit 0.1% cost model (slippage + brokerage) |
| VIX unavailable | ATR volatility ratio as proxy |

---

## Timeline

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| 1. Regime Classifier | 1 day | regime_classifier.py + regime_labels.csv |
| 2. Regime Switcher | 0.5 day | regime_switcher.py |
| 3. Regime-Aware Backtester | 1 day | regime_aware_backtest.py |
| 4. Regime Metrics | 0.5 day | regime_metrics.py |
| 5. Validation Runs | 1 day | Full + WF results |
| 6. Documentation | 0.5 day | Architecture + Results docs |
| **Total** | **~4.5 days** | **Complete framework + decision** |

---

*Implementation Plan Version: 1.0*  
*Date: 2026-06-15*