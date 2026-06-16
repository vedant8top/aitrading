"""Analyze skipped BUY signals from risk report logs."""
import re
from collections import Counter
from pathlib import Path

log_path = Path("logs/risk_report.log")
text = log_path.read_text(encoding="utf-8")

# Find all 'Skipped BUY' lines
skip_lines = re.findall(r"Skipped BUY for (\S+) on (\d{4}-\d{2}-\d{2}): (.+)", text)
print(f"Total skipped BUY lines: {len(skip_lines)}")

# By ticker
ticker_counts = Counter(t for t, d, r in skip_lines)
print("\n=== Skipped by Ticker (top 20) ===")
for ticker, count in ticker_counts.most_common(20):
    print(f"  {ticker}: {count}")

# By year
year_counts = Counter(d[:4] for t, d, r in skip_lines)
print("\n=== Skipped by Year ===")
for year in sorted(year_counts.keys()):
    print(f"  {year}: {year_counts[year]}")

# By reason
reason_counts = Counter(r for t, d, r in skip_lines)
print("\n=== Skipped by Reason ===")
for reason, count in reason_counts.most_common():
    print(f"  {reason}: {count}")

# Count Rejected BUY lines too
reject_lines = re.findall(r"Rejected BUY for (\S+) on (\d{4}-\d{2}-\d{2}): (.+)", text)
print(f"\nTotal Rejected BUY (risk limits): {len(reject_lines)}")
reject_reasons = Counter(r for t, d, r in reject_lines)
for reason, count in reject_reasons.most_common():
    print(f"  {reason}: {count}")

# Rejected by ticker
reject_ticker_counts = Counter(t for t, d, r in reject_lines)
print("\n=== Rejected by Ticker (top 20) ===")
for ticker, count in reject_ticker_counts.most_common(20):
    print(f"  {ticker}: {count}")

# Rejected by year
reject_year_counts = Counter(d[:4] for t, d, r in reject_lines)
print("\n=== Rejected by Year ===")
for year in sorted(reject_year_counts.keys()):
    print(f"  {year}: {reject_year_counts[year]}")

# Combined skip + reject
total_skipped = len(skip_lines)
total_rejected = len(reject_lines)
total_blocked = total_skipped + total_rejected
print(f"\n=== SUMMARY ===")
print(f"Total Skipped BUY (allocation): {total_skipped}")
print(f"Total Rejected BUY (risk limits): {total_rejected}")
print(f"Total Blocked: {total_blocked}")

# Top 20 tickers by total blocked
all_blocked = Counter()
for t, d, r in skip_lines:
    all_blocked[t] += 1
for t, d, r in reject_lines:
    all_blocked[t] += 1
print("\n=== Top 20 Tickers by Total Blocked ===")
for ticker, count in all_blocked.most_common(20):
    print(f"  {ticker}: {count}")