# Donchian Strategy Parameter Optimization Results

## Summary

- Parameter combinations tested: 24
- Entry channels: [20, 30, 40, 55, 70, 100]
- Exit channels: [10, 20, 30, 40]
- Walk-forward windows: 5

## All Parameter Combinations (Ranked by Sharpe)

| Rank | Entry | Exit | Return % | Sharpe | Max DD % | Win Rate % | Trades | WF Score | Overfit |
|------|-------|------|----------|--------|----------|------------|--------|----------|---------|
| 1 | 20 | 40 | 200.40 | 1.214 | 0.00 | 43.01 | 944 | 100 | WEAK |
| 2 | 20 | 30 | 186.45 | 1.203 | 0.00 | 43.98 | 1146 | 100 | WEAK |
| 3 | 30 | 30 | 165.80 | 1.167 | 0.00 | 45.14 | 988 | 80 | WEAK |
| 4 | 30 | 40 | 174.11 | 1.162 | 0.00 | 43.77 | 818 | 80 | WEAK |
| 5 | 40 | 40 | 170.76 | 1.159 | 0.00 | 42.84 | 747 | 60 | WEAK |
| 6 | 40 | 30 | 154.78 | 1.145 | 0.00 | 44.28 | 901 | 60 | WEAK |
| 7 | 55 | 40 | 145.60 | 1.071 | 0.00 | 43.50 | 669 | 60 | WEAK |
| 8 | 20 | 20 | 146.27 | 1.071 | 0.00 | 43.72 | 1464 | 80 | WEAK |
| 9 | 30 | 20 | 133.19 | 1.044 | 0.00 | 43.08 | 1272 | 60 | WEAK |
| 10 | 55 | 30 | 122.93 | 1.002 | 0.00 | 42.89 | 802 | 80 | WEAK |
| 11 | 40 | 20 | 118.73 | 0.990 | 0.00 | 41.79 | 1151 | 60 | WEAK |
| 12 | 70 | 40 | 118.20 | 0.955 | 0.00 | 43.85 | 602 | 60 | WEAK |
| 13 | 100 | 40 | 104.88 | 0.920 | 0.00 | 41.52 | 513 | 60 | WEAK |
| 14 | 70 | 30 | 104.97 | 0.910 | 0.00 | 42.42 | 726 | 60 | WEAK |
| 15 | 100 | 30 | 90.32 | 0.858 | 0.00 | 41.02 | 629 | 60 | WEAK |
| 16 | 55 | 20 | 85.29 | 0.812 | 0.00 | 41.70 | 1012 | 60 | WEAK |
| 17 | 70 | 20 | 80.58 | 0.788 | 0.00 | 41.75 | 915 | 60 | WEAK |
| 18 | 100 | 20 | 69.82 | 0.742 | 0.00 | 41.01 | 795 | 60 | WEAK |
| 19 | 20 | 10 | 68.25 | 0.693 | 0.00 | 40.96 | 2224 | 60 | WEAK |
| 20 | 30 | 10 | 57.45 | 0.635 | 0.00 | 39.83 | 1923 | 40 | WEAK |
| 21 | 40 | 10 | 51.85 | 0.603 | 0.00 | 38.74 | 1732 | 40 | WEAK |
| 22 | 55 | 10 | 35.26 | 0.461 | 0.00 | 38.52 | 1524 | 40 | WEAK |
| 23 | 70 | 10 | 31.67 | 0.432 | 0.00 | 37.82 | 1375 | 40 | WEAK |
| 24 | 100 | 10 | 26.55 | 0.394 | 0.00 | 37.92 | 1192 | 40 | WEAK |

## Best Configurations

### Best Return: 20/40
- Return: 200.40%
- Sharpe: 1.214
- Max DD: 0.00%
- WF Score: 100
- Overfit: WEAK

### Best Sharpe: 20/40
- Return: 200.40%
- Sharpe: 1.214
- Max DD: 0.00%
- WF Score: 100
- Overfit: WEAK

### Best Robust: 20/40
- Return: 200.40%
- Sharpe: 1.214
- Max DD: 0.00%
- WF Score: 100
- Overfit: WEAK

## Current Champion (55/20)

- Return: 85.29%
- Sharpe: 0.812
- Max DD: 0.00%
- WF Score: 60
- Overfit: WEAK

## Overfitting Analysis

- OVERFIT: 0/24
- WEAK: 24/24
- OK: 0/24

## Recommendation

**REPLACE CURRENT** with 20/40

Sharpe improvement: 1.214 vs 0.812