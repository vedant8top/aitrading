"""Audit Donchian optimization results for metric accuracy."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, ".")

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = PROJECT_ROOT / "data" / "processed"
OUTPUT_DIR = PROJECT_ROOT / "data" / "donchian_audit"


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Generate signals for both parameter sets
    params = [(55, 20), (20, 40)]

    for entry_ch, exit_ch in params:
        print(f"\n{'='*60}")
        print(f"AUDITING: entry={entry_ch}, exit={exit_ch}")
        print('='*60)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            processed_files = sorted(INPUT_DIR.glob("*_indicators.csv"))

            for csv_path in processed_files:
                ticker = csv_path.stem.removesuffix("_indicators")
                data = pd.read_csv(csv_path)
                data["Date"] = pd.to_datetime(data["Date"])
                if len(data) < max(entry_ch, exit_ch) + 10:
                    continue
                close = data["Close"]
                upper = close.rolling(entry_ch, min_periods=entry_ch).max().shift(1)
                lower = close.rolling(exit_ch, min_periods=exit_ch).min().shift(1)
                data["Signal"] = np.where(
                    close > upper, "BUY",
                    np.where(close < lower, "SELL", "HOLD")
                )
                data["Signal_Date"] = data["Date"]
                data["Signal_Confidence"] = "High"
                data["Conditions_Met"] = np.where(data["Signal"] != "HOLD", 1, 0)
                data["Buy_Conditions_Met"] = (close > upper).astype(int)
                data["Sell_Conditions_Met"] = (close < lower).astype(int)
                out_path = tmp_path / f"{ticker}_signals.csv"
                data.to_csv(out_path, index=False)

            # 2. Run backtest with full output
            from src.backtesting.backtest_engine import PortfolioBacktester

            backtester = PortfolioBacktester(
                initial_capital=100_000.0, position_size=0.10,
                brokerage_rate=0.0005, slippage_rate=0.0005, risk_mode="none"
            )
            datasets = PortfolioBacktester.load_signal_files(tmp_path)
            trades, equity, metrics = backtester.run(datasets)

            # 3. Print ALL available keys in metrics
            print(f"\n  Raw metrics keys: {sorted(metrics.keys())}")

            # 4. Check drawdown specifically
            dd_key = None
            for k in metrics:
                if 'drawdown' in k.lower():
                    dd_key = k
                    break

            if dd_key:
                print(f"  Drawdown key found: '{dd_key}' = {metrics[dd_key]}")
            else:
                print("  ERROR: No drawdown key found in metrics!")
                # Check if equity curve has drawdown
                print(f"  Equity columns: {equity.columns.tolist()}")

            # 5. Compute drawdown manually from equity curve
            if not equity.empty:
                peak = equity["Equity"].cummax()
                dd_series = equity["Equity"] / peak - 1.0
                max_dd = float(dd_series.min() * 100.0)
                print(f"  Manually computed max DD: {max_dd:.4f}%")
                print(f"  Equity curve: start={equity.iloc[0]['Equity']:.2f}, end={equity.iloc[-1]['Equity']:.2f}")
                print(f"  Min equity: {equity['Equity'].min():.2f}")
                print(f"  Max equity: {equity['Equity'].max():.2f}")

                # Find the drawdown period
                min_dd_idx = dd_series.idxmin()
                print(f"  Min drawdown date: {equity.loc[min_dd_idx, 'Date']}")
                print(f"  Min drawdown value: {equity.loc[min_dd_idx, 'Equity']:.2f}")

                # Save equity curve
                equity.to_csv(OUTPUT_DIR / f"equity_{entry_ch}_{exit_ch}.csv", index=False)

            # 6. Trade statistics
            if not trades.empty:
                print(f"\n  Trade count: {len(trades)}")
                wins = trades[trades["pnl"] > 0]
                losses = trades[trades["pnl"] < 0]
                print(f"  Wins: {len(wins)}, Losses: {len(losses)}")
                if len(wins) > 0:
                    print(f"  Avg win: {wins['pnl'].mean():.2f}")
                    print(f"  Total win: {wins['pnl'].sum():.2f}")
                if len(losses) > 0:
                    print(f"  Avg loss: {losses['pnl'].mean():.2f}")
                    print(f"  Total loss: {losses['pnl'].sum():.2f}")
                print(f"  Win rate: {len(wins)/len(trades)*100:.2f}%")
                print(f"  Profit factor: {abs(wins['pnl'].sum() / losses['pnl'].sum()) if len(losses) > 0 else 'inf'}")
                print(f"  Avg holding days: {trades['holding_days'].mean():.1f}")
                print(f"  Total PnL: {trades['pnl'].sum():.2f}")

                # Save trades
                trades.to_csv(OUTPUT_DIR / f"trades_{entry_ch}_{exit_ch}.csv", index=False)

            # 7. What does the optimizer actually see?
            print(f"\n  OPTIMIZER's view (what it reads from metrics dict):")
            for key in ["max_drawdown_pct", "maximum_drawdown_pct", "total_return_pct",
                        "sharpe_ratio", "win_rate_pct", "total_trades", "profit_factor",
                        "cagr_pct", "avg_holding_days"]:
                val = metrics.get(key, f"NOT FOUND (metrics has: {list(metrics.keys())})")
                print(f"    metrics['{key}'] = {val}")

    # Print summary findings
    print(f"\n{'='*60}")
    print(f"AUDIT FINDINGS SUMMARY")
    print(f"{'='*60}")
    print(f"\nFiles saved to: {OUTPUT_DIR}")
    print(f"  - equity_55_20.csv")
    print(f"  - equity_20_40.csv")
    print(f"  - trades_55_20.csv")
    print(f"  - trades_20_40.csv")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())