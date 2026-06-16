import sys
sys.path.insert(0, ".")

from src.validation.donchian_optimizer import DonchianOptimizer

def main():
    optimizer = DonchianOptimizer()
    report = optimizer.run()
    print("\n" + report)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())