# Market Regime Detection Framework v1 — Design Document

## 1. Regime Classification Methodology

### 1.1 Approach: Multi-Factor Regime Classification
Use a **hierarchical classification** combining:
- **Primary classifier**: ADX (Average Directional Index) for trend strength
- **Secondary classifier**: India VIX (or proxy) for volatility regime
- **Tertiary classifier**: Market breadth (advance/decline ratio) for participation
- **Confirmation**: Cross-asset correlation for regime stability

### 1.2 Regime Definitions (3 Core Regimes)

| Regime | Description | Market Characteristics |
|--------|-------------|------------------------|
| **TRENDING** | Strong directional move with participation | ADX > 25, VIX < 20, Breadth > 60%, Low correlation |
| **RANGE_BOUND** | Sideways consolidation, mean-reverting | ADX < 20, VIX < 25, Breadth 40-60%, Moderate correlation |
| **VOLATILE** | High uncertainty, whipsaws, correlation breakdown | VIX > 30 OR ADX > 25 with VIX > 25, Breadth < 40%, High correlation |

### 1.3 Classification Algorithm
```
IF VIX > 30:
    REGIME = VOLATILE
ELIF ADX > 25 AND VIX < 20 AND Breadth > 0.60:
    REGIME = TRENDING
ELIF ADX < 20 AND VIX < 25:
    REGIME = RANGE_BOUND
ELSE:
    REGIME = PREVIOUS_REGIME  # Hysteresis to prevent flip-flopping
```

---

## 2. Required Indicators

### 2.1 Primary Indicators (Calculated Daily)

| Indicator | Source | Calculation | Lookback |
|-----------|--------|-------------|----------|
| **ADX** | NIFTY 50 index | Wilder's DMI (DI+, DI-, ADX) | 14 periods |
| **India VIX** | NSE / Yahoo Finance | ^INDIAVIX ticker | Spot value |
| **Market Breadth** | 49 NIFTY stocks | (Advancing - Declining) / Total | Daily |
| **Cross-Correlation** | 49 NIFTY stocks | Avg pairwise 20-day return correlation | 20 periods |

### 2.2 Derived Indicators

| Indicator | Formula | Purpose |
|-----------|---------|---------|
| **Trend Strength** | ADX / 100 | Normalized 0-1 |
| **Volatility Z-Score** | (VIX - VIX_50d_mean) / VIX_50d_std | Relative volatility |
| **Breadth Momentum** | 5-day EMA of Breadth | Smoothed participation |
| **Correlation Regime** | Rolling 20d avg pairwise corr | Systemic risk proxy |

### 2.3 Data Requirements
- **NIFTY 50 index data** (^NSEI) — daily OHLCV
- **India VIX** (^INDIAVIX) — daily close
- **49 constituent stocks** — daily close for breadth/correlation
- **History**: Minimum 2 years for VIX z-score, 14 days for ADX

---

## 3. Thresholds

### 3.1 Primary Thresholds (Calibrated on 2018-2026 data)

| Parameter | TRENDING | RANGE_BOUND | VOLATILE |
|-----------|----------|-------------|----------|
| ADX | > 25 | < 20 | Any (if VIX high) |
| VIX | < 20 | < 25 | > 30 |
| Breadth | > 0.60 | 0.40 - 0.60 | < 0.40 |
| Correlation | < 0.50 | 0.50 - 0.70 | > 0.70 |

### 3.2 Hysteresis Buffers (Prevent Churning)
- **ADX**: Enter TRENDING at 25, exit at 20
- **VIX**: Enter VOLATILE at 30, exit at 25
- **Breadth**: Enter TRENDING at 0.60, exit at 0.55
- **Minimum regime duration**: 5 trading days

### 3.3 Threshold Calibration Method
- Walk-forward optimization on 2018-2022 (train), validate on 2023-2025 (test)
- Objective: Maximize regime purity (strategy performance within regime)
- Constraint: < 12 regime changes per year (avoid over-trading)

---

## 4. Data Sources

### 4.1 Primary Data Pipeline
```
Yahoo Finance / NSE API
    → Data Ingestion (src/data_ingestion/)
    → Feature Engineering (src/feature_engineering/)
    → Regime Indicators (NEW: src/regime_detection/regime_indicators.py)
    → Regime Classifier (NEW: src/regime_detection/regime_classifier.py)
```

### 4.2 Data Flow
1. **Daily EOD**: Download NIFTY 50 index, VIX, 49 constituents
2. **Compute**: ADX, Breadth, Correlation on rolling windows
3. **Classify**: Apply threshold logic with hysteresis
4. **Persist**: Store regime label per date in `data/regimes/regime_labels.csv`
5. **Consume**: Strategy switcher reads regime at signal generation time

### 4.3 Fallback Data Sources
- **VIX unavailable**: Use NIFTY 50 20-day realized volatility * sqrt(252) * 100
- **Constituents unavailable**: Use NIFTY 50 index only (ADX + realized vol)
- **Missing days**: Forward-fill regime label (max 3 days)

---

## 5. Strategy-to-Regime Mapping

### 5.1 Active Strategy Sets

| Regime | Active Strategies | Rationale |
|--------|-------------------|-----------|
| **TRENDING** | momentum, ema_rsi_macd, donchian, breakout | Trend followers capture directional moves; donchian/breakout for continuation |
| **RANGE_BOUND** | mean_reversion, bollinger_reversion, bear_trap | Mean-reversion profits from oscillations; bear_trap catches false breakdowns |
| **VOLATILE** | volatility_expansion, bear_trap (defensive) | Vol expansion captures breakouts; bear_trap only for defense |

### 5.2 Strategy Weights (Within Regime)

| Regime | Strategy | Weight | Notes |
|--------|----------|--------|-------|
| TRENDING | momentum | 0.30 | Core trend |
| TRENDING | ema_rsi_macd | 0.25 | Confirmation |
| TRENDING | donchian | 0.25 | Breakout |
| TRENDING | breakout | 0.20 | Short-term |
| RANGE_BOUND | mean_reversion | 0.40 | Core MR |
| RANGE_BOUND | bollinger_reversion | 0.35 | Band-based |
| RANGE_BOUND | bear_trap | 0.25 | Trap detection |
| VOLATILE | volatility_expansion | 0.70 | Primary |
| VOLATILE | bear_trap | 0.30 | Defensive only |

### 5.3 Inactive Strategies
- **bull_trap**: Excluded (0 trades in validation)
- **All others**: Weight = 0 in non-assigned regimes

---

## 6. Regime Transition Handling

### 6.1 Transition Rules

| From → To | Position Handling | Signal Handling |
|-----------|-------------------|-----------------|
| TRENDING → RANGE_BOUND | Close trend positions at next open | Switch to MR strategies immediately |
| RANGE_BOUND → TRENDING | Close MR positions at next open | Switch to trend strategies immediately |
| ANY → VOLATILE | Reduce position sizes by 50% | Only volatility_expansion + defensive bear_trap |
| VOLATILE → ANY | Hold until regime confirmed (3 days) | Gradual re-entry over 3 days |

### 6.2 Hysteresis Implementation
```python
# Pseudocode
def classify_regime(indicators, previous_regime):
    raw_regime = compute_raw_regime(indicators)
    
    if raw_regime == previous_regime:
        return raw_regime
    
    # Require confirmation
    if days_in_current_regime < MIN_DAYS (5):
        return previous_regime
    
    # Check if strongly conflicting
    if regime_conflict_score(raw_regime, previous_regime) > THRESHOLD:
        return raw_regime
    
    return previous_regime
```

### 6.3 Transition Costs
- **Slippage**: 0.05% per transition (position close + reopen)
- **Brokerage**: 0.05% per transition
- **Max transitions/year**: 12 (enforced by minimum duration)

---

## 7. Backtesting Methodology

### 7.1 Regime-Aware Backtest Engine
Extend `PortfolioBacktester` with regime awareness:

```python
class RegimeAwareBacktester(PortfolioBacktester):
    def __init__(self, regime_labels: pd.Series, strategy_weights: dict, ...):
        self.regime_labels = regime_labels  # Date -> Regime
        self.strategy_weights = strategy_weights  # Regime -> {strategy: weight}
    
    def get_active_strategies(self, date):
        regime = self.regime_labels[date]
        return self.strategy_weights[regime]
    
    def run(self):
        # For each date:
        # 1. Get regime
        # 2. Get active strategies + weights
        # 3. Generate signals from active strategies only
        # 4. Size positions by strategy weight
        # 5. Execute with risk management
```

### 7.2 Signal Generation per Regime
- **Option A**: Run all strategies, filter by regime weight (simpler)
- **Option B**: Only run active strategies (more efficient)
- **Selected**: Option A — allows post-hoc analysis of inactive strategy signals

### 7.3 Position Sizing with Regime Weights
```
For each active strategy s in regime r:
    target_allocation = base_position_size * weight[s, r]
    shares = compute_position_size(cash * target_allocation, price, atr)
```

### 7.4 Backtest Periods
- **Full period**: 2018-01 to 2026-06 (8.5 years)
- **Walk-forward**: Same 5 windows as existing validation
- **Out-of-sample**: 2023-01 to 2026-06 (post-design)

---

## 8. Validation Methodology

### 8.1 Regime Classification Validation
| Metric | Target |
|--------|--------|
| Regime purity (trend days in TRENDING) | > 70% |
| Regime purity (range days in RANGE_BOUND) | > 65% |
| Regime purity (volatile days in VOLATILE) | > 60% |
| Transition frequency | < 12/year |
| Minimum regime duration | ≥ 5 days |

### 8.2 Strategy Performance Within Regime
| Regime | Strategy | Target Win Rate | Target Sharpe |
|--------|----------|-----------------|---------------|
| TRENDING | momentum | > 45% | > 1.0 |
| TRENDING | donchian | > 35% | > 0.8 |
| RANGE_BOUND | mean_reversion | > 55% | > 0.8 |
| RANGE_BOUND | bollinger_reversion | > 50% | > 0.7 |
| VOLATILE | volatility_expansion | > 40% | > 0.5 |

### 8.3 Portfolio-Level Validation
- **Primary**: Compare regime-aware portfolio vs best single strategy (donchian)
- **Secondary**: Compare vs equal-weight all-strategy portfolio
- **Benchmark**: NIFTY 50 buy-and-hold

### 8.4 Walk-Forward Validation
- Same 5 windows as existing framework
- Regime thresholds fixed from training period (2018-2022)
- No look-ahead: regime at date t uses data up to t-1

---

## 9. Performance Metrics

### 9.1 Primary Metrics
| Metric | Description | Target |
|--------|-------------|--------|
| **Total Return** | Cumulative portfolio return | > 85% (beat donchian) |
| **CAGR** | Compound annual growth rate | > 8% |
| **Sharpe Ratio** | Risk-adjusted return | > 0.9 |
| **Max Drawdown** | Peak-to-trough decline | < 18% |
| **Win Rate** | % profitable trades | > 40% |

### 9.2 Regime-Specific Metrics
| Metric | Description |
|--------|-------------|
| Regime Accuracy | % days correctly classified (ex-post) |
| Strategy Utilization | % capital deployed per regime |
| Transition Cost Drag | Return lost to regime switches |
| Regime Alpha | Excess return vs regime-matched benchmark |

### 9.3 Risk Metrics
| Metric | Target |
|--------|--------|
| VaR (95%, 1-day) | < 2% |
| Expected Shortfall | < 3% |
| Max Consecutive Losses | < 8 |
| Recovery Time (max DD) | < 180 days |

---

## 10. Failure Cases & Mitigations

### 10.1 Known Failure Modes

| Failure Case | Description | Detection | Mitigation |
|--------------|-------------|-----------|------------|
| **Whipsaw Regime** | Rapid TRENDING↔RANGE_BOUND transitions | > 20 transitions/year | Increase hysteresis, min duration to 10 days |
| **VIX Data Gap** | India VIX unavailable | Missing VIX for > 3 days | Fallback to realized volatility |
| **Regime Misclassification** | Trend strategy runs in range (or vice versa) | Strategy Sharpe < 0 in regime | Add regime confirmation filter (e.g., 2-of-3 indicators) |
| **Correlation Breakdown** | All strategies correlate in crisis | Cross-strategy corr > 0.8 | Activate VOLATILE regime early |
| **Single-Stock Dominance** | One stock drives breadth | Breadth driven by < 5 stocks | Use equal-weight breadth |
| **Look-Ahead Bias** | Regime uses future data | Walk-forward fails | Strict t-1 data only |

### 10.2 Stress Test Scenarios
1. **2020 COVID Crash**: VIX > 80, correlation → 1.0
2. **2022 Bear Market**: Prolonged RANGE_BOUND with downtrend
3. **2023-2024 Rally**: Strong TRENDING with low volatility
4. **2024 Election Volatility**: Short VOLATILE spikes

### 10.3 Kill Switches
- **Max daily loss**: -3% portfolio (halt all new entries)
- **Max regime transitions**: 20/year (force RANGE_BOUND)
- **VIX spike**: > 50 (force VOLATILE, reduce size 50%)
- **Correlation spike**: > 0.85 (force VOLATILE)

---

## 11. Implementation Roadmap

### Phase 1: Core Infrastructure (Week 1-2)
- [ ] `src/regime_detection/regime_indicators.py` — ADX, VIX, Breadth, Correlation
- [ ] `src/regime_detection/regime_classifier.py` — Threshold logic + hysteresis
- [ ] `data/regimes/regime_labels.csv` — Daily regime labels 2018-2026

### Phase 2: Integration (Week 2-3)
- [ ] `src/regime_detection/regime_switcher.py` — Strategy weights per regime
- [ ] `src/regime_detection/regime_backtest.py` — RegimeAwareBacktester
- [ ] Update `strategy_comparison.py` to support regime-aware mode

### Phase 3: Validation (Week 3-4)
- [ ] Walk-forward validation with fixed thresholds
- [ ] Regime purity analysis
- [ ] Transition cost analysis
- [ ] Compare vs baseline (donchian, equal-weight)

### Phase 4: Production Hardening (Week 4-5)
- [ ] Kill switch implementation
- [ ] Fallback data sources
- [ ] Monitoring/alerting for regime changes
- [ ] Documentation & runbooks

---

## 12. File Structure (New)

```
src/regime_detection/
├── __init__.py
├── regime_indicators.py      # ADX, VIX, Breadth, Correlation calculators
├── regime_classifier.py      # Threshold logic, hysteresis, classification
├── regime_switcher.py        # Strategy weights, transition handling
├── regime_backtest.py        # RegimeAwareBacktester
└── regime_report.py          # Regime analysis & visualization

data/regimes/
├── regime_labels.csv         # Date, Regime, ADX, VIX, Breadth, Correlation
└── regime_transitions.csv    # Date, From_Regime, To_Regime, Trigger

docs/
├── regime_detection_design.md    # This document
├── regime_validation_report.md   # Generated after validation
└── regime_backtest_report.md     # Generated after backtest
```

---

## 13. Acceptance Criteria

| Criterion | Pass Condition |
|-----------|----------------|
| **Regime purity** | > 65% average across 3 regimes |
| **Transition frequency** | < 12/year (2018-2026) |
| **Total return** | > 85% (beat donchian 85.29%) |
| **Sharpe ratio** | > 0.9 (beat donchian 0.812) |
| **Max drawdown** | < 18% (beat donchian 20.47%) |
| **Walk-forward consistency** | Positive in ≥ 4/5 test windows |
| **No look-ahead bias** | Regime at t uses data ≤ t-1 |
| **Execution time** | < 5 min for full backtest |

---

*Design Version: 1.0*  
*Author: TradingAI Architecture Team*  
*Date: 2026-06-15*