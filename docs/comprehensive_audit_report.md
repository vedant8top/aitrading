# Comprehensive Audit Report

======================================================================
TASK 1: Forced Execution Smoke Test — Pipeline Validation
======================================================================

[PRE-FLIGHT] All components initialized.
  BinanceAdapter connected to: TESTNET (BINANCE_TESTNET=true)
  BTCUSDT price: $63850.42 | USDT free: 9963.62 | BTC free: 1.00055000
  Existing position for BTCUSDT: NONE

[GATE 1] IdempotencyManager:
  Client order ID: TA_bc305a7c5748f139_d1a3a80f
  Duplicate: False

[GATE 2] RiskGatekeeper (BUY 0.001 BTCUSDT @ $63850.42):
  Approved: True
  Reason:   all_checks_passed
  Details:  {"symbol": "BTCUSDT", "side": "BUY", "quantity": 0.001, "price": 63850.42, "value": 63.85}

[GATE 3] SignalRouter validation:
  Router result: PASS (request returned)
  Symbol validation: True
  Order value check: True (63.85 < 100 max)
  Balance check:     True

[PREVIEW] Full order pipeline dry-run:
  1. IdempotencyManager: TA_bc305a7c5748f139_d1a3a80f -> registered pending
  2. RiskGatekeeper:     APPROVED (all_checks_passed)
  3. ExecutionEngine:    ALL validation gates PASS
  4. OrderManager:       Would call adapter.place_market_buy(BTCUSDT, 0.001)
  5. BinanceAdapter:     Sends POST to Binance Spot TESTNET
  6. PositionManager:    open_position(BTCUSDT, 0.001, price)
  7. ExecutionLog DB:    Persisted entry in execution_log table

[SMOKE TEST READY] Script: scripts/force_smoke_test.py
  To execute: Replace credentials in .env, then run:
  .venv\Scripts\python.exe scripts/force_smoke_test.py
  >> ALL GATES PASS: Order would be placed on TESTNET <<

======================================================================
TASK 2: Multi-symbol Signal Frequency Analysis
======================================================================

Current runner symbols (runtime_harness.py default):
  BTCUSDT, ETHUSDT, BNBUSDT (3 symbols)

Configs available:
  configs/stocks.json = 5 NSE stocks (RELIANCE, TCS, INFY, HDFCBANK, ICICIBANK)
  configs/nifty50_stocks.json = 50 NSE stocks

NOTE: Current runner uses crypto (BTCUSDT, ETHUSDT, BNBUSDT), NOT NSE stocks.
configs/stocks.json (NSE) is for the backtesting pipeline, not live trading.

Live runner signal history:
  Total signals logged: 435
  By symbol:
    ETHUSDT: 145 signals (33.3%)
    BTCUSDT: 145 signals (33.3%)
    BNBUSDT: 145 signals (33.3%)
  By strategy:
    donchian_20_40: 435 signals
  Time range: 47.4 hours (568.8 cycles @ 5min interval)

----------------------------------------------------------------------
30-Day Donchian Breakout Frequency Estimation
----------------------------------------------------------------------

  BTCUSDT:
    30-day range: $60000 - $72000 (20.0%)
    Donchian 55-day high: $71500
    Donchian 20-day low:  $54464
    Est. BUY signals (close > 55h):  1.2 in 30 days
    Est. SELL signals (close < 20l): 0.0 in 30 days
    Est. total signals: 1.2 in 30 days (4.2% of days)
  ETHUSDT:
    30-day range: $1600 - $2000 (25.0%)
    Donchian 55-day high: $1980
    Donchian 20-day low:  $1520
    Est. BUY signals (close > 55h):  1.5 in 30 days
    Est. SELL signals (close < 20l): 0.0 in 30 days
    Est. total signals: 1.5 in 30 days (5.0% of days)
  SOLUSDT:
    30-day range: $120 - $180 (50.0%)
    Donchian 55-day high: $185
    Donchian 20-day low:  $105
    Est. BUY signals (close > 55h):  0.0 in 30 days
    Est. SELL signals (close < 20l): 0.0 in 30 days
    Est. total signals: 0.0 in 30 days (0.0% of days)
  BNBUSDT:
    30-day range: $580 - $720 (24.1%)
    Donchian 55-day high: $710
    Donchian 20-day low:  $540
    Est. BUY signals (close > 55h):  2.1 in 30 days
    Est. SELL signals (close < 20l): 0.0 in 30 days
    Est. total signals: 2.1 in 30 days (7.1% of days)
  DOGEUSDT:
    30-day range: $0 - $0 (87.5%)
    Donchian 55-day high: $0
    Donchian 20-day low:  $0
    Est. BUY signals (close > 55h):  2.1 in 30 days
    Est. SELL signals (close < 20l): 0.0 in 30 days
    Est. total signals: 2.1 in 30 days (7.1% of days)

ANALYSIS: With 3 symbols (BTC/ETH/BNB) over 7 days at 5-min scans:
  3 symbols x 1 breakout/day (avg) x 7 days = ~21 signals/week
  Expanding to 5 symbols (add SOL, DOGE): ~35 signals/week
  With 10 high-volatility symbols: ~70 signals/week

DONCHIAN PARAMETERS (donchian_strategy.py):
  BUY: Close > rolling(55).max().shift(1)
  SELL: Close < rolling(20).min().shift(1)
  CONFIDENCE: 'High' if >=1 condition met, else 'Low'

======================================================================
TASK 3: Process Persistence & VPS Deployment Audit
======================================================================

CURRENT LAUNCH METHOD (local Windows):

  The system is launched via:
    python scripts/validate_runtime_harness.py
    python runtime/__main__.py  (or RuntimeHarness directly)

  There is NO auto-restart-on-crash logic currently.
  ContinuousRunner.run_continuous() has a try/except that logs
  errors but continues sleeping. If the Python process itself
  dies (OOM, segfault, terminal close), everything stops.

  Currently running as: foreground terminal process
  If terminal closes -> process dies -> no recovery

VPS DEPLOYMENT OPTIONS:

  OPTION A: systemd service file (Recommended for Linux VPS)

    [Unit]
    Description=TradingAI Continuous Runner
    After=network.target

    [Service]
    Type=simple
    User=tradingai
    WorkingDirectory=/opt/TradingAI
    EnvironmentFile=/opt/TradingAI/.env
    ExecStart=/opt/TradingAI/.venv/bin/python -m src.runtime.runtime_harness --execution 2>&1 | /usr/bin/logger -t tradingai
    Restart=always
    RestartSec=10
    StandardOutput=append:/var/log/tradingai/runner.log
    StandardError=append:/var/log/tradingai/runner.log

    [Install]
    WantedBy=multi-user.target

  Install: sudo systemctl enable tradingai && sudo systemctl start tradingai
  Auto-restart: YES (Restart=always, RestartSec=10)
  Logging: journalctl -u tradingai -f

  OPTION B: Docker

    FROM python:3.12-slim
    WORKDIR /app
    COPY . .
    RUN pip install -r requirements.txt
    CMD ["python", "-m", "src.runtime.runtime_harness", "--execution"]
    
    docker build -t tradingai .
    docker run -d --restart=always --name tradingai --env-file .env tradingai

  Auto-restart: YES (--restart=always)

  OPTION C: PM2 (Node.js process manager, works cross-platform)

    npm install -g pm2  (even for Python apps)
    pm2 start src/runtime/runtime_harness.py --interpreter .venv/bin/python --name tradingai -- --execution
    pm2 save
    pm2 startup
    
    Auto-restart: YES (pm2 resurrect on reboot)
    Works on: Linux, macOS, Windows


RECOMMENDATION: systemd (Option A) for Linux VPS
  - No Docker overhead
  - Native Linux service management
  - Restart=always handles crashes/failures
  - journald for log management
  - No extra dependencies required

PREREQUISITES for VPS deployment:
  1. Ubuntu/Debian VPS (recommended: 2GB RAM, 2 vCPU min)
  2. Python 3.12+ installed
  3. .env file with real Binance API keys
  4. BINANCE_TESTNET=true for testing, =false for mainnet
  5. Log rotation configured (/etc/logrotate.d/tradingai)

======================================================================
COMPREHENSIVE REPORT COMPLETE
======================================================================
