import sys
sys.path.insert(0, '.')
import pandas as pd

df = pd.read_csv('data/regimes/regime_labels.csv', parse_dates=['Date'], index_col='Date')

print("=== Indicator Statistics ===")
for col in ['ADX', 'ATR_Ratio', 'Breadth', 'Correlation']:
    print(f"\n{col}:")
    desc = df[col].describe()
    print(f"  mean: {desc['mean']:.4f}")
    print(f"  std: {desc['std']:.4f}")
    print(f"  min: {desc['min']:.4f}")
    print(f"  max: {desc['max']:.4f}")
    for p in [10, 25, 50, 75, 90]:
        print(f"  {p}th: {df[col].quantile(p/100):.4f}")

print("\n=== Current Regime Distribution ===")
print(df['Regime'].value_counts())

# Check how many days meet each threshold
print("\n=== Threshold Analysis ===")
print(f"ADX > 25: {(df['ADX'] > 25).sum()} days")
print(f"ADX > 20: {(df['ADX'] > 20).sum()} days")
print(f"ADX < 20: {(df['ADX'] < 20).sum()} days")
print(f"ATR_Ratio > 1.5: {(df['ATR_Ratio'] > 1.5).sum()} days")
print(f"ATR_Ratio > 1.2: {(df['ATR_Ratio'] > 1.2).sum()} days")
print(f"Breadth > 0.55: {(df['Breadth'] > 0.55).sum()} days")
print(f"Breadth > 0.50: {(df['Breadth'] > 0.50).sum()} days")
print(f"Breadth > 0.40: {(df['Breadth'] > 0.40).sum()} days")
print(f"Correlation > 0.7: {(df['Correlation'] > 0.7).sum()} days")
print(f"Correlation > 0.6: {(df['Correlation'] > 0.6).sum()} days")

# Test with relaxed thresholds
print("\n=== Relaxed Threshold Analysis ===")
trending = (df['ADX'] > 20) & (df['Breadth'] > 0.35)
volatile = (df['ATR_Ratio'] > 1.2) & (df['Correlation'] > 0.5)
r = (df['ADX'] < 20) & (df['Breadth'].between(0.35, 0.60))
print(f"TRENDING (ADX>20, Breadth>0.35): {trending.sum()} days")
print(f"VOLATILE (ATR>1.2, Corr>0.5): {volatile.sum()} days")
print(f"RANGE_BOUND (ADX<20, Breadth 0.35-0.60): {r.sum()} days")
print(f"Unclassified: {len(df) - trending.sum() - volatile.sum() - r.sum()} days")

# Test with even more relaxed thresholds
print("\n=== Very Relaxed Threshold Analysis ===")
t2 = (df['ADX'] > 18) & (df['Breadth'] > 0.30)
v2 = (df['ATR_Ratio'] > 1.1) & (df['Correlation'] > 0.45)
r2 = (df['ADX'] < 18) & (df['Breadth'].between(0.30, 0.65))
print(f"TRENDING (ADX>18, Breadth>0.30): {t2.sum()} days")
print(f"VOLATILE (ATR>1.1, Corr>0.45): {v2.sum()} days")
print(f"RANGE_BOUND (ADX<18, Breadth 0.30-0.65): {r2.sum()} days")
print(f"Unclassified: {len(df) - t2.sum() - v2.sum() - r2.sum()} days")