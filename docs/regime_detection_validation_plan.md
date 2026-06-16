# Market Regime Detection Framework — Experimental Validation Plan v1

## Objective

Determine whether **regime-aware strategy selection** provides statistically significant performance improvement over the best standalone strategies and naive baselines.

---

## 1. Hypotheses

### Primary Hypothesis (H1)
> A regime-aware portfolio that dynamically selects strategies based on detected market regime (TRENDING / RANGE_BOUND / VOLATILE) achieves **superior risk-adjusted returns** compared to the best single strategy (Donchian) over the full 2018-2026 period and in walk-forward validation.

**Null Hypothesis (H0):** Regime-aware portfolio performance is statistically indistinguishable from Donchian.

### Secondary Hypotheses

| ID | Hypothesis | Null |
|----|------------|------|
| H2 | Regime-aware portfolio has **lower maximum drawdown** than Donchian | Max DD ≥ Donchian |
| H3 | Regime-aware portfolio has **higher win rate** than Donchian | Win rate ≤ Donchian |
| H4 | Regime classification **purity** exceeds 65% average across regimes | Purity ≤ 65% |
| H5 | **Transition costs** do not erode > 2% of gross alpha | Cost drag > 2% |
| H6 | Walk-forward **consistency** ≥ 4/5 positive test windows | ≤ 3/5 positive |

### Exploratory Hypotheses

| ID | Hypothesis |
|----|------------|
| H7 | Regime-aware portfolio outperforms **equal-weight all-strategy** portfolio |
| H8 | **VOLATILE regime** detection reduces tail risk (VaR/ES) |
| H9 | **RANGE_BOUND regime** allocation to mean-reversion strategies captures > 60% of MR alpha |
| H10 | **TRENDING regime** allocation to trend strategies captures > 70% of trend alpha |

---

## 2. Baselines (Control Group)

| Baseline | Description | Expected Performance |
|----------|-------------|---------------------|
| **B1: Donchian** | Best single strategy (85.29% return, 0.812 Sharpe, -20.47% DD) | Primary benchmark |
| **B2: Momentum** | Best trend-following (69.71% return, 0.748 Sharpe) | Trend benchmark |
| **B3: Bollinger Reversion** | Best robust strategy (25.56% return, 0.304 Sharpe, 90.0 WF score) | Mean-reversion benchmark |
| **B4: Equal-Weight Portfolio** | 1/9 allocation to each of 9 strategies | Naive diversification |
| **B5: NIFTY 50 Buy & Hold** | Market benchmark | Passive benchmark |

---

## 3. Success Criteria (Go/No-Go Thresholds)

### Primary Criteria (All Must Pass)

| Metric | Threshold | Rationale |
|--------|-----------|-----------|
| **Total Return** | > 85.29% (beat Donchian) | Must beat best single strategy |
| **Sharpe Ratio** | > 0.90 (beat Donchian 0.812) | Risk-adjusted superiority |
| **Max Drawdown** | < 18% (beat Donchian 20.47%) | Capital preservation |
| **Walk-Forward Consistency** | ≥ 4/5 positive test windows | Robustness |

### Secondary Criteria (At Least 3 of 5 Must Pass)

| Metric | Threshold |
|--------|-----------|
| Win Rate | > 40% |
| CAGR | > 8% |
| VaR (95%, 1-day) | < 2% |
| Expected Shortfall | < 3% |
| Recovery Time (max DD) | < 180 days |

### Regime-Specific Criteria (All Must Pass)

| Metric | Threshold |
|--------|-----------|
| Regime Purity (avg) | > 65% |
| Transition Frequency | < 12/year |
| Transition Cost Drag | < 2% of gross return |
| Minimum Regime Duration | ≥ 5 days |

### Rejection Criteria (Any Single Failure = Reject)

| Condition | Action |
|-----------|--------|
| Look-ahead bias detected | **REJECT** |
| Walk-forward fails (≤ 3/5 positive) | **REJECT** |
| Total return < Donchian - 2% | **REJECT** |
| Max DD > 22% | **REJECT** |
| Transition frequency > 20/year | **REJECT** |
| Regime purity < 55% | **REJECT** |

---

## 4. Statistical Tests

### 4.1 Performance Comparison Tests

| Comparison | Test | Justification |
|------------|------|---------------|
| Regime-aware vs Donchian (returns) | **Paired t-test** on daily returns | Same dates, paired observations |
| Regime-aware vs Donchian (Sharpe) | **Jobson-Korkie test** (Memmel) | Compare Sharpe ratios with same sample |
| Regime-aware vs Equal-Weight | **Paired t-test** on daily returns | Same dates |
| Regime-aware vs NIFTY 50 | **Paired t-test** on daily returns | Same dates |

### 4.2 Distributional Tests

| Test | Purpose |
|------|---------|
| **Jarque-Bera** | Normality of daily returns |
| **Ljung-Box** | Autocorrelation in returns |
| **Kolmogorov-Smirnov** | Return distribution vs baseline |

### 4.3 Regime Classification Tests

| Test | Purpose |
|------|---------|
| **Confusion Matrix** | Regime purity (ex-post labeling) |
| **Cohen's Kappa** | Agreement vs random classification |
| **Transition Matrix** | Regime persistence / churning |

### 4.4 Significance Levels

| Test Type | α (Significance) | Correction |
|-----------|------------------|------------|
| Primary (H1) | 0.05 | None (single primary) |
| Secondary (H2-H6) | 0.05 | Bonferroni (α/5 = 0.01) |
| Exploratory (H7-H10) | 0.10 | None (hypothesis-generating) |

### 4.5 Effect Size Requirements

| Metric | Minimum Effect Size |
|--------|---------------------|
| Return Difference | > 2% absolute (vs Donchian) |
| Sharpe Difference | > 0.08 absolute |
| Max DD Reduction | > 2% absolute |
| Win Rate Increase | > 3% absolute |

---

## 5. Evaluation Metrics

### 5.1 Primary Metrics (Reported for All Strategies)

| Metric | Formula | Frequency |
|--------|---------|-----------|
| Total Return | (Final Equity / Initial Capital - 1) × 100 | Period |
| CAGR | (Final/Initial)^(1/years) - 1 | Period |
| Sharpe Ratio | mean(daily_ret) / std(daily_ret) × √252 | Period |
| Max Drawdown | min(Equity / cummax(Equity) - 1) | Period |
| Win Rate | Profitable Trades / Total Trades | Period |
| Profit Factor | Gross Profit / Gross Loss | Period |
| Avg Trade | Mean P&L per trade | Period |

### 5.2 Regime-Specific Metrics

| Metric | Description |
|--------|-------------|
| **Regime Purity** | % days in regime where ex-post market matches regime |
| **Strategy Utilization** | % capital deployed to active strategies per regime |
| **Regime Alpha** | Excess return vs regime-matched benchmark |
| **Transition Cost Drag** | Return lost to slippage/brokerage on regime switches |
| **Regime Duration** | Mean/median days per regime episode |

### 5.3 Risk Metrics

| Metric | Formula |
|--------|---------|
| VaR (95%, 1-day) | 5th percentile of daily returns |
| Expected Shortfall | Mean of returns below VaR |
| Sortino Ratio | mean(ret) / std(negative ret) × √252 |
| Calmar Ratio | CAGR / |Max DD| |
| Ulcer Index | RMS of drawdowns |

### 5.4 Walk-Forward Metrics (Per Window)

| Metric | Target |
|--------|--------|
| Test Period Return | > 0% |
| Test Period Sharpe | > 0.5 |
| Test Period Max DD | < 15% |
| Consistency Score | > 60 |

---

## 6. Walk-Forward Methodology

### 6.1 Window Structure (Identical to Existing Framework)

| Window | Train Period | Test Period | Purpose |
|--------|--------------|-------------|---------|
| W1 | 2018-01 to 2020-12 | 2021-01 to 2021-12 | Initial validation |
| W2 | 2019-01 to 2021-12 | 2022-01 to 2022-12 | Regime stability |
| W3 | 2020-01 to 2022-12 | 2023-01 to 2023-12 | Post-COVID |
| W4 | 2021-01 to 2023-12 | 2024-01 to 2024-12 | Election year |
| W5 | 2022-01 to 2024-12 | 2025-01 to 2025-12 | Recent out-of-sample |

### 6.2 No Look-Ahead Protocol

```
FOR each window:
    1. Train regime thresholds on TRAIN period only
    2. Fix thresholds for TEST period
    3. Classify regime at date t using data ≤ t-1
    4. Run regime-aware backtest on TEST period
    5. Record metrics
```

### 6.3 Threshold Stability Analysis

| Analysis | Method |
|----------|--------|
| Threshold drift | Compare optimal thresholds across windows |
| Parameter sensitivity | Grid search ±20% around chosen thresholds |
| Regime label stability | Compare regime labels from different train periods |

### 6.4 Out-of-Sample Validation

- **Primary OOS**: Window 5 (2025) — completely unseen during design
- **Secondary OOS**: 2026 YTD (Jan-Jun) — live validation period
- **Purged K-Fold**: 5-fold with 20-day purge between folds (robustness check)

---

## 7. Ablation Studies

### 7.1 Component Ablation (Remove One Component at a Time)

| Ablation | Description | Expected Impact |
|----------|-------------|-----------------|
| **A1: No Regime Detection** | Equal-weight all 9 strategies | Baseline B4 |
| **A2: No Hysteresis** | Raw threshold classification | ↑ Transitions, ↑ costs |
| **A3: No VOLATILE Regime** | Only TRENDING / RANGE_BOUND | ↑ Tail risk |
| **A4: No Transition Costs** | Zero slippage/brokerage on switches | Overestimate returns |
| **A5: Fixed Weights** | Equal weight within regime | Suboptimal allocation |
| **A6: Single Indicator** | ADX only (no VIX, breadth, correlation) | ↓ Purity |
| **A7: No Bear Trap** | Remove defensive strategy | ↑ VOLATILE drawdown |
| **A8: Perfect Foresight** | Ex-post true regime labels | Upper bound |

### 7.2 Regime Definition Ablation

| Variant | Regimes | Thresholds |
|---------|---------|------------|
| **V1: 2-Regime** | TRENDING / NOT_TRENDING | ADX only |
| **V2: 3-Regime (Primary)** | TRENDING / RANGE_BOUND / VOLATILE | ADX + VIX + Breadth |
| **V3: 4-Regime** | + CRISIS (VIX > 50) | Add crisis regime |
| **V4: Continuous** | Regime probability (0-1) | Soft allocation |

### 7.3 Strategy Mapping Ablation

| Variant | Mapping |
|---------|---------|
| **M1: Full** | All 3 regime strategy sets (design) |
| **M2: Trend Only** | Only TRENDING has active strategies |
| **M3: MR Only** | Only RANGE_BOUND has active strategies |
| **M4: Best Per Regime** | Single best strategy per regime |
| **M5: Top-2 Per Regime** | Two best strategies per regime |

### 7.4 Ablation Success Criteria

| Ablation | Must Not Degrade |
|----------|------------------|
| A1 (No Regime) | Regime-aware > Equal-weight by > 2% return |
| A2 (No Hysteresis) | Transition freq < 12/yr with hysteresis |
| A3 (No VOLATILE) | Max DD < 18% with VOLATILE |
| A6 (Single Indicator) | Purity > 65% with multi-factor |

---

## 8. Overfitting Detection

### 8.1 In-Sample vs Out-of-Sample Gap

| Metric | Acceptable Gap |
|--------|----------------|
| Return | < 5% absolute |
| Sharpe | < 0.15 absolute |
| Max DD | < 3% absolute |
| Win Rate | < 5% absolute |

### 8.2 Parameter Sensitivity

- **Grid search**: ADX [20, 25, 30], VIX [15, 20, 25, 30], Breadth [0.50, 0.55, 0.60, 0.65]
- **Stability region**: Performance must be positive across ≥ 80% of parameter combinations
- **No cliff effects**: Small parameter changes → small performance changes

### 8.3 Data Snooping Controls

| Control | Implementation |
|---------|----------------|
| **Pre-registration** | This document = pre-registration |
| **Fixed thresholds** | No optimization on test windows |
| **Purged CV** | 20-day purge between train/test |
| **Multiple testing correction** | Bonferroni for secondary hypotheses |
| **Out-of-sample holdout** | 2025 + 2026 YTD never used in design |

### 8.4 Synthetic Data Tests

| Test | Purpose |
|------|---------|
| **Random regime labels** | Regime-aware should not beat random |
| **Shuffled returns** | Strategy mapping should not create alpha from noise |
| **Phase-randomized** | Preserve autocorrelation, destroy regime structure |

### 8.5 Overfitting Red Flags (Auto-Reject)

| Red Flag | Detection |
|----------|-----------|
| In-sample Sharpe > 2.0, OOS < 0.5 | Curve fitting |
| Optimal thresholds at boundary | Over-optimization |
| Single window drives all alpha | Luck, not skill |
| Performance degrades with more data | Spurious pattern |

---

## 9. Experimental Design Summary

### 9.1 Experiment Matrix

| Experiment | Description | Comparisons |
|------------|-------------|-------------|
| **E1: Main** | Regime-aware (design) vs B1-B5 | H1, H2, H3, H7 |
| **E2: Walk-Forward** | 5 windows, fixed thresholds | H6, H4, H5 |
| **E3: Ablation A1-A8** | Component removal | Component necessity |
| **E4: Variant V1-V4** | Regime definition variants | Robustness to definition |
| **E5: Mapping M1-M5** | Strategy mapping variants | Mapping optimality |
| **E6: Sensitivity** | Parameter grid search | Stability region |
| **E7: Synthetic** | Random/shuffled data | Overfitting control |

### 9.2 Sample Size & Power

| Aspect | Specification |
|--------|---------------|
| **Observations** | ~2,100 trading days (2018-2026) |
| **Test Period Days** | ~250 per window × 5 = 1,250 |
| **Minimum Detectable Effect** | 2% return, 0.08 Sharpe (α=0.05, power=0.8) |
| **Required Trades** | > 500 for win rate test (binomial) |

### 9.3 Reporting Requirements

| Report | Contents |
|--------|----------|
| **Main Results** | All metrics for E1, statistical tests, effect sizes |
| **Walk-Forward** | Per-window metrics, consistency score, regime labels |
| **Ablation** | Component contribution table, necessity ranking |
| **Sensitivity** | Heatmaps, stability regions, cliff detection |
| **Overfitting** | IS/OOS gaps, synthetic test results, red flags |
| **Decision** | Go/No-Go with evidence |

---

## 10. Decision Framework

### 10.1 Go Decision (Implement)

**ALL Primary Criteria PASS** AND **≥ 3 Secondary Criteria PASS** AND **No Rejection Criteria Triggered**

Evidence required:
- Statistically significant outperformance vs Donchian (p < 0.05)
- Effect size > minimum thresholds
- Walk-forward consistency ≥ 4/5
- Regime purity > 65%
- No overfitting red flags

### 10.2 Conditional Go (Iterate)

**Primary Criteria MARGINAL** (e.g., return > Donchian but Sharpe < 0.90) OR **1 Rejection Criteria MARGINAL**

Action: Refine thresholds, adjust strategy weights, add kill switches, re-test

### 10.3 No-Go (Reject)

**ANY Primary Criteria FAIL** OR **ANY Rejection Criteria TRIGGERED** OR **Overfitting Detected**

Evidence for rejection:
- Return ≤ Donchian - 2%
- Max DD ≥ 22%
- Walk-forward ≤ 3/5 positive
- Regime purity < 55%
- IS/OOS gap > thresholds
- Synthetic tests show spurious alpha

### 10.4 Decision Timeline

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| Implementation | 2 weeks | Code + regime labels |
| Backtest | 1 week | Full period results |
| Walk-Forward | 1 week | 5-window results |
| Ablation/Sensitivity | 1 week | Component analysis |
| Overfitting Audit | 1 week | Synthetic tests, IS/OOS |
| **Decision** | **Week 6** | **Go / Conditional / No-Go** |

---

## 11. Reproducibility Requirements

| Requirement | Specification |
|-------------|---------------|
| **Random Seeds** | Fixed for all stochastic components |
| **Data Version** | Snapshot of 49-ticker data (2018-2026) |
| **Code Version** | Git commit hash for all experiments |
| **Parameters** | All thresholds, weights, configs in YAML |
| **Environment** | Python 3.11, requirements.txt pinned |
| **Artifacts** | All intermediate CSVs, logs, regime labels |

---

## 12. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| VIX data unavailable | Medium | High | Realized vol fallback implemented |
| Regime misclassification | High | Medium | Hysteresis, 2-of-3 confirmation |
| Transition costs underestimated | Medium | Medium | Explicit 0.1% cost model |
| Overfitting to 2018-2026 | High | Critical | Synthetic tests, purged CV, holdout |
| Strategy mapping suboptimal | Medium | Medium | Ablation M1-M5, weight optimization |
| Look-ahead bias | Low | Critical | Strict t-1 protocol, automated checks |

---

*Validation Plan Version: 1.0*  
*Author: TradingAI Research Team*  
*Date: 2026-06-15*  
*Status: Pre-Registration — No Code Executed*