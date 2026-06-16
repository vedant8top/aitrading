# Pluggable Strategy Framework

## Architecture

The strategy framework decouples signal generation logic from the signal orchestration pipeline, allowing new strategies to be added without modifying existing code.

### Directory Layout

```
src/strategies/
├── __init__.py              (optional)
├── base_strategy.py          Abstract base class (ABC)
├── ema_rsi_macd_strategy.py  Concrete EMA + RSI + MACD strategy
├── signal_engine.py          Orchestrator (modified to inject strategy)
└── strategy_registry.py      Central registry
```

### Data Flow

```
market_data_downloader.py
         │
         ▼
technical_indicators.py
         │
         ▼
signal_engine.py ──── uses ────> strategy_registry
         │                            │
         │                     retrieves strategy by name
         │                            │
         ├── calls ──> BaseStrategy (abstract interface)
         │                  │
         │                  ├── required_indicator_columns
         │                  ├── signal_columns
         │                  ├── generate_signals()
         │                  ├── validate_output()
         │                  ├── get_strategy_name()
         │                  └── get_strategy_description()
         │                  │
         │         ema_rsi_macd_strategy.py (concrete)
         │
         ▼
backtest_engine.py   (unchanged — reads *_signals.csv)
```

### Class Responsibilities

| Class / Module | Responsibility |
|---|---|
| `BaseStrategy` (ABC) | Defines the contract every strategy must implement. |
| `EmaRsiMacdStrategy` | Encapsulates the EMA Trend + RSI + MACD confirmation logic. |
| `SignalEngine` | Orchestrates file I/O, validation, and reporting. Delegates signal logic to the injected strategy. |
| `StrategyRegistry` | Stores and retrieves strategy classes by name. |

---

## Adding a New Strategy

### Step 1: Create a new Python file in `src/strategies/`

```python
"""Example: simple moving average crossover strategy."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from src.strategies.base_strategy import BaseStrategy


REQUIRED_INDICATOR_COLUMNS: tuple[str, ...] = (
    "Date",
    "Close",
    "SMA_20",
    "SMA_50",
)

SIGNAL_COLUMNS: tuple[str, ...] = (
    "Signal_Date",
    "Signal",
    "Signal_Confidence",
    "Conditions_Met",
    "Buy_Conditions_Met",
    "Sell_Conditions_Met",
)


@dataclass(frozen=True)
class SmaCrossoverStrategy(BaseStrategy):

    _name: str = field(default="sma_crossover")
    _description: str = field(
        default="Simple moving average crossover. "
        "BUY when SMA_20 crosses above SMA_50. "
        "SELL when SMA_20 crosses below SMA_50."
    )

    @property
    def required_indicator_columns(self) -> tuple[str, ...]:
        return REQUIRED_INDICATOR_COLUMNS

    @property
    def signal_columns(self) -> tuple[str, ...]:
        return SIGNAL_COLUMNS

    def get_strategy_name(self) -> str:
        return self._name

    def get_strategy_description(self) -> str:
        return self._description

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        enriched = data.copy()
        # ... strategy logic here ...
        enriched["Signal_Date"] = enriched["Date"]
        enriched["Signal"] = signal
        enriched["Signal_Confidence"] = confidence
        enriched["Conditions_Met"] = applicable_count
        enriched["Buy_Conditions_Met"] = buy_count
        enriched["Sell_Conditions_Met"] = sell_count
        return enriched

    def validate_output(
        self, source: pd.DataFrame, signals: pd.DataFrame
    ) -> list[str]:
        # ... validation logic here ...
        return warnings
```

### Step 2: Implement the required interface

Every strategy must implement:

| Method / Property | Returns | Description |
|---|---|---|
| `required_indicator_columns` | `tuple[str, ...]` | Columns the input CSV must contain. |
| `signal_columns` | `tuple[str, ...]` | Columns the output CSV will contain. Must include at minimum `"Signal_Date"`, `"Signal"`, `"Signal_Confidence"`. |
| `get_strategy_name()` | `str` | Unique name used for registry lookup (e.g. `"sma_crossover"`). |
| `get_strategy_description()` | `str` | Human-readable description of the strategy. |
| `generate_signals(data)` | `pd.DataFrame` | Core signal generation logic. Must return a copy of `data` with signal columns appended. |
| `validate_output(source, signals)` | `list[str]` | Consistency checks. Return warnings list (may be empty). Raise `SignalCalculationError` on critical failures. |

### Step 3: Signal output contract

The `Signal` column must contain only `"BUY"`, `"SELL"`, or `"HOLD"` values.

The `Signal_Confidence` column must contain only `"Low"`, `"Medium"`, or `"High"` values.

These requirements ensure backward compatibility with `backtest_engine.py`.

---

## Registering a Strategy

### Automatic Registration (via `__main__`)

When `signal_engine.py` is run directly, it auto-registers the default `EmaRsiMacdStrategy`. You can add additional registrations in the `__main__` block:

```python
if __name__ == "__main__":
    from src.strategies.ema_rsi_macd_strategy import EmaRsiMacdStrategy
    from src.strategies.strategy_registry import StrategyRegistry

    StrategyRegistry.register(EmaRsiMacdStrategy)
    # StrategyRegistry.register(SmaCrossoverStrategy)  # <-- add new strategies here
    raise SystemExit(main())
```

### Manual Registration

```python
from src.strategies.strategy_registry import StrategyRegistry
from src.strategies.sma_crossover_strategy import SmaCrossoverStrategy

StrategyRegistry.register(SmaCrossoverStrategy)

# Retrieve later
strategy_class = StrategyRegistry.get_strategy("sma_crossover")
strategy = strategy_class()
```

### Registry API

| Method | Description |
|---|---|
| `register(strategy_class)` | Register a strategy class. |
| `get_strategy(name)` | Return the strategy class for *name*. Raises `StrategyNotFoundError` if not found. |
| `list_strategies()` | Return sorted list of registered strategy names. |
| `clear()` | Clear all registrations (useful for testing). |

### Using a specific strategy with SignalEngine

```python
from src.strategies.sma_crossover_strategy import SmaCrossoverStrategy

strategy = SmaCrossoverStrategy()
engine = SignalEngine(output_folder, logger, strategy=strategy)
engine.process_file(csv_path)
```

If no strategy is provided, `SignalEngine` defaults to `EmaRsiMacdStrategy`.

---

## Design Principles

1. **Open/Closed**: The strategy framework is open for extension (new strategies) but closed for modification (existing code is not changed).
2. **No new dependencies**: Strategies use only `pandas` and `numpy` (already in `requirements.txt`).
3. **Preserved behavior**: The existing EMA + RSI + MACD strategy produces exactly the same output as before.
4. **Backtester agnostic**: `backtest_engine.py` reads only the `Signal` column and is unaware of which strategy produced it.
5. **Deterministic**: Signal generation must be reproducible given the same input data.

## Backward Compatibility

- `SignalEngine()` with no `strategy` argument defaults to `EmaRsiMacdStrategy`.
- The `REQUIRED_COLUMNS` and `SIGNAL_COLUMNS` module-level constants are kept in `signal_engine.py` for any external code that may reference them.
- CSV output format is unchanged. The backtest engine reads `*_signals.csv` files identically.
- All existing CLI flags (`--input-folder`, `--output-folder`, `--summary`, `--log-file`, `--report`) behave identically.
</｜｜DSML｜｜parameter>
<task_progress>
- [x] Analyze current architecture (signal_engine.py, backtest_engine.py)
- [x] Design pluggable strategy framework plan
- [x] Present implementation plan for approval
- [x] Create base_strategy.py
- [x] Create ema_rsi_macd_strategy.py
- [x] Create strategy_registry.py
- [x] Modify signal_engine.py to use strategy injection
- [x] Create docs/strategy_framework.md
- [ ] Verify no behavior changes
</task_progress>
</write_to_file>