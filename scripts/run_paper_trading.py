"""Run paper trading simulation with Donchian 20/40."""

import sys
import os
from pathlib import Path

sys.path.insert(0, ".")

from src.paper_trading.daily_runner import DailyRunner

DB_PATH = Path("data/paper_trading.db")


def main():
    # Remove old database to start fresh simulation
    if DB_PATH.exists():
        os.remove(DB_PATH)
        print(f"Deleted old database: {DB_PATH}")

    # Initialize runner
    runner = DailyRunner()
    print(f"Starting Donchian 20/40 paper trading simulation")
    print(f"Initial capital: INR 1,000,000")
    print(f"Period: 2018-01-01 to 2026-06-14")
    print(f"Database: {DB_PATH}")

    # Run full historical simulation
    runner.run_simulation(
        start_date="2018-01-01",
        end_date="2026-06-14",
    )

    # Save results
    runner.save_results()

    # Generate daily report for last day
    report = runner.generate_daily_report()
    runner.save_daily_report(report)

    # Print summary
    summary = runner.journal.get_summary()
    print(f"\n{'='*60}")
    print(f"SIMULATION COMPLETE")
    print(f"{'='*60}")
    print(f"Total Trades: {summary.get('total_trades', 0)}")
    print(f"Win Rate: {summary.get('win_rate', 0):.1f}%")
    print(f"Total P&L: INR {summary.get('total_pnl', 0):+,.2f}")
    print(f"Portfolio Value: INR {summary.get('portfolio_value', 0):,.2f}")
    print(f"Return: {summary.get('total_return_pct', 0):+.2f}%")
    print(f"Open Positions: {summary.get('open_positions', 0)}")

    runner.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())