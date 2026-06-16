# Signal Engine Report

## Execution Summary

- Input files: 5
- Successful files: 5
- Failed files: 0
- Total BUY signals: 3
- Total SELL signals: 246
- Total HOLD signals: 996

## Strategy Logic

Strategy: EMA Trend + RSI + MACD Confirmation.

BUY requires all four conditions:

- EMA 20 is above EMA 50.
- Close is above EMA 200.
- RSI 14 is between 55 and 70, inclusive.
- MACD is above the MACD Signal line.

SELL requires at least one condition, provided the BUY rule did not match:

- EMA 20 is below EMA 50, or
- RSI 14 is below 45, or
- MACD is below the MACD Signal line.

All other rows are HOLD.

## Confidence

- High: 4 applicable conditions met.
- Medium: 3 applicable conditions met.
- Low: fewer than 3 applicable conditions met.

Because the SELL rule defines three conditions, its maximum confidence is Medium.

## Assumptions

- BUY has precedence only when all four BUY conditions are satisfied.
- Indicator warm-up rows with unavailable values are assigned HOLD with Low confidence.
- Signals describe the state on each daily row; they are not orders and are not executed.
- No transaction costs, position state, portfolio constraints, or future returns are used.

## Generated Files

- `data/signals/HDFCBANK_NS_signals.csv`
- `data/signals/ICICIBANK_NS_signals.csv`
- `data/signals/INFY_NS_signals.csv`
- `data/signals/RELIANCE_NS_signals.csv`
- `data/signals/TCS_NS_signals.csv`
- `data/signal_summary.csv`
- `logs/signal_engine.log`
- `docs/signal_engine_report.md`

## Signal Statistics

- `HDFCBANK_NS`: BUY 0, SELL 50, HOLD 199; latest SELL (Low) on 2026-06-12
- `ICICIBANK_NS`: BUY 0, SELL 50, HOLD 199; latest SELL (Low) on 2026-06-12
- `INFY_NS`: BUY 0, SELL 50, HOLD 199; latest SELL (Medium) on 2026-06-12
- `RELIANCE_NS`: BUY 3, SELL 46, HOLD 200; latest SELL (Medium) on 2026-06-12
- `TCS_NS`: BUY 0, SELL 50, HOLD 199; latest SELL (Medium) on 2026-06-12

## Warnings

- `HDFCBANK_NS`: 199 warm-up rows were assigned HOLD due to unavailable indicators
- `ICICIBANK_NS`: 199 warm-up rows were assigned HOLD due to unavailable indicators
- `INFY_NS`: 199 warm-up rows were assigned HOLD due to unavailable indicators
- `RELIANCE_NS`: 199 warm-up rows were assigned HOLD due to unavailable indicators
- `TCS_NS`: 199 warm-up rows were assigned HOLD due to unavailable indicators

## Failed Files

- None
