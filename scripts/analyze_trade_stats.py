"""Compare trade statistics for 55/20 and 20/40 Donchian configurations."""

import pandas as pd

for entry, exit in [(55, 20), (20, 40)]:
    t = pd.read_csv(f"data/donchian_audit/trades_{entry}_{exit}.csv")
    e = pd.read_csv(f"data/donchian_audit/equity_{entry}_{exit}.csv")

    final_equity = e.iloc[-1]["Equity"]
    total_return = (final_equity / 100000 - 1) * 100
    wins = t[t["pnl"] > 0]
    losses = t[t["pnl"] < 0]
    total_pnl = t["pnl"].sum()
    profit_factor = abs(wins["pnl"].sum() / losses["pnl"].sum()) if len(losses) > 0 else float("inf")
    total_invested = t["entry_value"].sum() + t["entry_brokerage"].sum()
    active_days = int((e["Market_Value"] > 0).sum())
    total_days = len(e)
    
    peak = e["Equity"].cummax()
    max_dd = (e["Equity"] / peak - 1).min() * 100
    
    print(f"\n=== {entry}/{exit} ===")
    print(f"Final Equity: INR {final_equity:.2f}")
    print(f"Total Return: {total_return:.2f}%")
    print(f"Max Drawdown: {max_dd:.2f}%")
    print(f"Trades: {len(t)}")
    print(f"Wins: {len(wins)} ({len(wins)/len(t)*100:.1f}%)")
    print(f"Losses: {len(losses)} ({len(losses)/len(t)*100:.1f}%)")
    print(f"Avg Win: INR {wins['pnl'].mean():.2f}" if len(wins) > 0 else "Avg Win: N/A")
    print(f"Avg Loss: INR {losses['pnl'].mean():.2f}" if len(losses) > 0 else "Avg Loss: N/A")
    print(f"Total PnL: INR {total_pnl:.2f}")
    print(f"Profit Factor: {profit_factor:.2f}")
    print(f"Avg Holding: {t['holding_days'].mean():.1f} days")
    print(f"Total Invested: INR {total_invested:.2f}")
    print(f"Turnover: {total_invested / 100000:.1f}x")
    print(f"Days in Market: {active_days}/{total_days} ({active_days/total_days*100:.1f}%)")