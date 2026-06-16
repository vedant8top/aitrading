"""Test Binance Spot Testnet connectivity and authentication."""

import os
import sys
import logging
from pathlib import Path

from dotenv import load_dotenv
from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceRequestException

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("binance_test")


def load_credentials() -> tuple[str, str, bool]:
    """Load Binance API credentials from .env file."""
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        logger.error(".env file not found at %s", env_path)
        logger.error("Expected .env in the same directory as this script.")
        sys.exit(1)

    load_dotenv(env_path)

    api_key = os.getenv("BINANCE_API_KEY", "").strip()
    secret_key = os.getenv("BINANCE_SECRET_KEY", "").strip()
    testnet = os.getenv("BINANCE_TESTNET", "true").lower() == "true"

    if not api_key or not secret_key:
        logger.error(
            "BINANCE_API_KEY or BINANCE_SECRET_KEY not set in .env file."
        )
        logger.error(
            "Please update .env with your Binance Spot Testnet API credentials."
        )
        logger.error(
            "1. Go to https://testnet.binance.vision/ and create an API key"
        )
        logger.error(
            "2. Copy the API Key and Secret Key into the .env file"
        )
        sys.exit(1)

    if api_key == "PASTE_YOUR_API_KEY_HERE" or secret_key == "PASTE_YOUR_SECRET_KEY_HERE":
        logger.error("Placeholder credentials detected in .env file.")
        logger.error("Please replace with real Binance Spot Testnet API credentials.")
        sys.exit(1)

    return api_key, secret_key, testnet


def main() -> int:
    """Test Binance Spot Testnet connection."""
    logger.info("Loading Binance credentials...")
    api_key, secret_key, testnet = load_credentials()

    if testnet:
        logger.info("Connecting to Binance Spot Testnet...")
    else:
        logger.info("Connecting to Binance Spot (LIVE)...")
        logger.warning("LIVE MODE DETECTED. Ensure this is intentional!")

    try:
        client = Client(api_key, secret_key, testnet=testnet)
        account = client.get_account()

        can_trade = account.get("canTrade", False)
        can_withdraw = account.get("canWithdraw", False)
        can_deposit = account.get("canDeposit", False)
        account_type = account.get("accountType", "N/A")

        print("\n=== Binance Connection Test ===")
        print("Connected Successfully")
        print(f"Can Trade: {can_trade}")
        print(f"Can Withdraw: {can_withdraw}")
        print(f"Can Deposit: {can_deposit}")
        print(f"Account Type: {account_type}")
        print(f"Network: {'Testnet' if testnet else 'LIVE'}")

        balances = account.get("balances", [])
        non_zero = [
            b
            for b in balances
            if float(b.get("free", 0)) > 0 or float(b.get("locked", 0)) > 0
        ]

        if non_zero:
            print(f"\nBalances ({len(non_zero)} assets):")
            print(f"{'Asset':<10} {'Free':<20} {'Locked':<20} {'Total':<20}")
            print("-" * 70)
            for b in non_zero:
                asset = b["asset"]
                free = float(b["free"])
                locked = float(b["locked"])
                total = free + locked
                print(f"{asset:<10} {free:<20.8f} {locked:<20.8f} {total:<20.8f}")
        else:
            print("\nNo non-zero balances found.")

        logger.info("Connection test completed successfully.")
        return 0

    except BinanceAPIException as e:
        logger.error("Binance API error: %s", e)
        print(f"\n=== Connection FAILED ===")
        print(f"Error: {e.message}")
        print(f"Status code: {e.status_code}")
        return 1

    except BinanceRequestException as e:
        logger.error("Binance request error: %s", e)
        print(f"\n=== Connection FAILED ===")
        print(f"Request error: {e}")
        return 1

    except Exception as e:
        logger.exception("Unexpected error: %s", e)
        print(f"\n=== Connection FAILED ===")
        print(f"Unexpected error: {type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())