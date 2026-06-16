# Technical Indicator Engine Report

## Execution Summary

- Input CSV files: 49
- Successful files: 49
- Failed files: 0
- Indicators per successful file: 14
- Total enriched rows: 102262
- Unexpected indicator nulls: 0

## Indicators Created

- `SMA_20`
- `SMA_50`
- `EMA_20`
- `EMA_50`
- `EMA_200`
- `RSI_14`
- `MACD`
- `MACD_Signal`
- `MACD_Histogram`
- `ATR_14`
- `Bollinger_Middle_20`
- `Bollinger_Upper_20`
- `Bollinger_Lower_20`
- `Volume_MA_20`

## Formulas Used

- SMA(n): arithmetic mean of Close over the last n observations.
- EMA(n): exponentially weighted mean of Close with span n.
- RSI(14): Wilder-smoothed average gains and losses, converted to a 0-100 oscillator.
- MACD: EMA(12) minus EMA(26).
- MACD Signal: EMA(9) of MACD.
- MACD Histogram: MACD minus MACD Signal.
- True Range: maximum of High-Low, absolute High-previous Close, and absolute Low-previous Close.
- ATR(14): Wilder-smoothed True Range over 14 observations.
- Bollinger Middle(20): SMA(20) of Close.
- Bollinger Upper/Lower: middle band plus/minus two population standard deviations of Close.
- Volume MA(20): arithmetic mean of Volume over the last 20 observations.

## Files Generated

- `data/processed/ADANIENT_NS_indicators.csv`
- `data/processed/ADANIPORTS_NS_indicators.csv`
- `data/processed/APOLLOHOSP_NS_indicators.csv`
- `data/processed/ASIANPAINT_NS_indicators.csv`
- `data/processed/AXISBANK_NS_indicators.csv`
- `data/processed/BAJAJ-AUTO_NS_indicators.csv`
- `data/processed/BAJAJFINSV_NS_indicators.csv`
- `data/processed/BAJFINANCE_NS_indicators.csv`
- `data/processed/BEL_NS_indicators.csv`
- `data/processed/BHARTIARTL_NS_indicators.csv`
- `data/processed/BPCL_NS_indicators.csv`
- `data/processed/BRITANNIA_NS_indicators.csv`
- `data/processed/CIPLA_NS_indicators.csv`
- `data/processed/COALINDIA_NS_indicators.csv`
- `data/processed/DIVISLAB_NS_indicators.csv`
- `data/processed/DRREDDY_NS_indicators.csv`
- `data/processed/EICHERMOT_NS_indicators.csv`
- `data/processed/GRASIM_NS_indicators.csv`
- `data/processed/HCLTECH_NS_indicators.csv`
- `data/processed/HDFCBANK_NS_indicators.csv`
- `data/processed/HDFCLIFE_NS_indicators.csv`
- `data/processed/HEROMOTOCO_NS_indicators.csv`
- `data/processed/HINDALCO_NS_indicators.csv`
- `data/processed/HINDUNILVR_NS_indicators.csv`
- `data/processed/ICICIBANK_NS_indicators.csv`
- `data/processed/INDUSINDBK_NS_indicators.csv`
- `data/processed/INFY_NS_indicators.csv`
- `data/processed/ITC_NS_indicators.csv`
- `data/processed/JSWSTEEL_NS_indicators.csv`
- `data/processed/KOTAKBANK_NS_indicators.csv`
- `data/processed/LT_NS_indicators.csv`
- `data/processed/M&M_NS_indicators.csv`
- `data/processed/MARUTI_NS_indicators.csv`
- `data/processed/NESTLEIND_NS_indicators.csv`
- `data/processed/NTPC_NS_indicators.csv`
- `data/processed/ONGC_NS_indicators.csv`
- `data/processed/POWERGRID_NS_indicators.csv`
- `data/processed/RELIANCE_NS_indicators.csv`
- `data/processed/SBILIFE_NS_indicators.csv`
- `data/processed/SBIN_NS_indicators.csv`
- `data/processed/SUNPHARMA_NS_indicators.csv`
- `data/processed/TATACONSUM_NS_indicators.csv`
- `data/processed/TATASTEEL_NS_indicators.csv`
- `data/processed/TCS_NS_indicators.csv`
- `data/processed/TECHM_NS_indicators.csv`
- `data/processed/TITAN_NS_indicators.csv`
- `data/processed/TRENT_NS_indicators.csv`
- `data/processed/ULTRACEMCO_NS_indicators.csv`
- `data/processed/WIPRO_NS_indicators.csv`
- `data/indicator_summary.csv`
- `logs/indicator_engine.log`
- `docs/indicator_engine_report.md`

## Validation Results

- `ADANIENT_NS`: 2087 rows, 529 expected warm-up nulls, 0 unexpected nulls, alignment valid
- `ADANIPORTS_NS`: 2087 rows, 529 expected warm-up nulls, 0 unexpected nulls, alignment valid
- `APOLLOHOSP_NS`: 2087 rows, 529 expected warm-up nulls, 0 unexpected nulls, alignment valid
- `ASIANPAINT_NS`: 2087 rows, 529 expected warm-up nulls, 0 unexpected nulls, alignment valid
- `AXISBANK_NS`: 2087 rows, 529 expected warm-up nulls, 0 unexpected nulls, alignment valid
- `BAJAJ-AUTO_NS`: 2087 rows, 529 expected warm-up nulls, 0 unexpected nulls, alignment valid
- `BAJAJFINSV_NS`: 2087 rows, 529 expected warm-up nulls, 0 unexpected nulls, alignment valid
- `BAJFINANCE_NS`: 2087 rows, 529 expected warm-up nulls, 0 unexpected nulls, alignment valid
- `BEL_NS`: 2087 rows, 529 expected warm-up nulls, 0 unexpected nulls, alignment valid
- `BHARTIARTL_NS`: 2087 rows, 529 expected warm-up nulls, 0 unexpected nulls, alignment valid
- `BPCL_NS`: 2087 rows, 529 expected warm-up nulls, 0 unexpected nulls, alignment valid
- `BRITANNIA_NS`: 2087 rows, 529 expected warm-up nulls, 0 unexpected nulls, alignment valid
- `CIPLA_NS`: 2087 rows, 529 expected warm-up nulls, 0 unexpected nulls, alignment valid
- `COALINDIA_NS`: 2087 rows, 529 expected warm-up nulls, 0 unexpected nulls, alignment valid
- `DIVISLAB_NS`: 2086 rows, 529 expected warm-up nulls, 0 unexpected nulls, alignment valid
- `DRREDDY_NS`: 2087 rows, 529 expected warm-up nulls, 0 unexpected nulls, alignment valid
- `EICHERMOT_NS`: 2087 rows, 529 expected warm-up nulls, 0 unexpected nulls, alignment valid
- `GRASIM_NS`: 2087 rows, 529 expected warm-up nulls, 0 unexpected nulls, alignment valid
- `HCLTECH_NS`: 2087 rows, 529 expected warm-up nulls, 0 unexpected nulls, alignment valid
- `HDFCBANK_NS`: 2087 rows, 529 expected warm-up nulls, 0 unexpected nulls, alignment valid
- `HDFCLIFE_NS`: 2087 rows, 529 expected warm-up nulls, 0 unexpected nulls, alignment valid
- `HEROMOTOCO_NS`: 2087 rows, 529 expected warm-up nulls, 0 unexpected nulls, alignment valid
- `HINDALCO_NS`: 2087 rows, 529 expected warm-up nulls, 0 unexpected nulls, alignment valid
- `HINDUNILVR_NS`: 2087 rows, 529 expected warm-up nulls, 0 unexpected nulls, alignment valid
- `ICICIBANK_NS`: 2087 rows, 529 expected warm-up nulls, 0 unexpected nulls, alignment valid
- `INDUSINDBK_NS`: 2087 rows, 529 expected warm-up nulls, 0 unexpected nulls, alignment valid
- `INFY_NS`: 2087 rows, 529 expected warm-up nulls, 0 unexpected nulls, alignment valid
- `ITC_NS`: 2087 rows, 529 expected warm-up nulls, 0 unexpected nulls, alignment valid
- `JSWSTEEL_NS`: 2087 rows, 529 expected warm-up nulls, 0 unexpected nulls, alignment valid
- `KOTAKBANK_NS`: 2087 rows, 529 expected warm-up nulls, 0 unexpected nulls, alignment valid
- `LT_NS`: 2087 rows, 529 expected warm-up nulls, 0 unexpected nulls, alignment valid
- `M&M_NS`: 2087 rows, 529 expected warm-up nulls, 0 unexpected nulls, alignment valid
- `MARUTI_NS`: 2087 rows, 529 expected warm-up nulls, 0 unexpected nulls, alignment valid
- `NESTLEIND_NS`: 2087 rows, 529 expected warm-up nulls, 0 unexpected nulls, alignment valid
- `NTPC_NS`: 2087 rows, 529 expected warm-up nulls, 0 unexpected nulls, alignment valid
- `ONGC_NS`: 2087 rows, 529 expected warm-up nulls, 0 unexpected nulls, alignment valid
- `POWERGRID_NS`: 2087 rows, 529 expected warm-up nulls, 0 unexpected nulls, alignment valid
- `RELIANCE_NS`: 2087 rows, 529 expected warm-up nulls, 0 unexpected nulls, alignment valid
- `SBILIFE_NS`: 2087 rows, 529 expected warm-up nulls, 0 unexpected nulls, alignment valid
- `SBIN_NS`: 2087 rows, 529 expected warm-up nulls, 0 unexpected nulls, alignment valid
- `SUNPHARMA_NS`: 2087 rows, 529 expected warm-up nulls, 0 unexpected nulls, alignment valid
- `TATACONSUM_NS`: 2087 rows, 529 expected warm-up nulls, 0 unexpected nulls, alignment valid
- `TATASTEEL_NS`: 2087 rows, 529 expected warm-up nulls, 0 unexpected nulls, alignment valid
- `TCS_NS`: 2087 rows, 529 expected warm-up nulls, 0 unexpected nulls, alignment valid
- `TECHM_NS`: 2087 rows, 529 expected warm-up nulls, 0 unexpected nulls, alignment valid
- `TITAN_NS`: 2087 rows, 529 expected warm-up nulls, 0 unexpected nulls, alignment valid
- `TRENT_NS`: 2087 rows, 529 expected warm-up nulls, 0 unexpected nulls, alignment valid
- `ULTRACEMCO_NS`: 2087 rows, 529 expected warm-up nulls, 0 unexpected nulls, alignment valid
- `WIPRO_NS`: 2087 rows, 529 expected warm-up nulls, 0 unexpected nulls, alignment valid

Validation checks cover required OHLCV columns, numeric source data, ascending unique dates,
row/date alignment, all requested indicator columns, infinite values, and nulls appearing
after each indicator's expected warm-up period.

## Warnings

- None

## Failed Files

- None
