#!/bin/bash
# TradingAI — Fresh Ubuntu VPS Deployment Script
# Run as root or with sudo on Oracle Cloud Ubuntu

set -euo pipefail

echo "=== Phase 1: System Dependencies ==="
apt update && apt upgrade -y
apt install -y python3 python3-venv python3-pip git logrotate curl

echo "=== Phase 2: Create User ==="
id -u tradingai &>/dev/null || useradd -m -s /bin/bash tradingai

echo "=== Phase 3: Clone Repository ==="
cd /opt
git clone https://github.com/YOUR_REPO/TradingAI.git
chown -R tradingai:tradingai /opt/TradingAI

echo "=== Phase 4: Python Environment ==="
cd /opt/TradingAI
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "=== Phase 5: Configuration ==="
cp .env.template .env
echo "  >> IMPORTANT: Edit .env with your real Binance API keys"
echo "BINANCE_TESTNET=true" >> .env

echo "=== Phase 6: Logging ==="
mkdir -p /var/log/tradingai
chown -R tradingai:tradingai /var/log/tradingai
cp /opt/TradingAI/deploy/logrotate.conf /etc/logrotate.d/tradingai

echo "=== Phase 7: Systemd Service ==="
cp /opt/TradingAI/deploy/tradingai.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable tradingai

echo ""
echo "=== DEPLOYMENT COMPLETE ==="
echo "  To start:   sudo systemctl start tradingai"
echo "  To monitor: sudo journalctl -u tradingai -f"
echo "  Pre-flight: cd /opt/TradingAI && source .venv/bin/activate && python scripts/validate_runtime_harness.py --once"
echo "  To configure API keys: nano /opt/TradingAI/.env"
echo ""