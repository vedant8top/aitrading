"""Map strategies to market regimes for regime-aware portfolio construction."""

from __future__ import annotations

from typing import Optional

from src.regime_detection.regime_classifier import Regime

# ------------------------------------------------------------------
# Regime-to-Strategy Mapping (Immutable Configuration)
# ------------------------------------------------------------------

# Weights sum to 1.0 within each regime's active strategy set.
# UNCERTAIN regime: 50% cash, no new entries — handled by backtester.
REGIME_STRATEGY_MAP: dict[Regime, dict[str, float]] = {
    Regime.TRENDING: {
        "donchian": 0.30,
        "breakout": 0.25,
        "momentum": 0.25,
        "ema_rsi_macd": 0.20,
    },
    Regime.RANGE_BOUND: {
        "mean_reversion": 0.40,
        "bollinger_reversion": 0.35,
        "bear_trap": 0.25,
    },
    Regime.VOLATILE: {
        "volatility_expansion": 0.70,
        "bear_trap": 0.30,
    },
    Regime.UNCERTAIN: {},  # No active strategies — 50% cash
}


class RegimeSwitcher:
    """Manages strategy-to-regime mapping and transition rules.

    Responsibilities:
    - Provide active strategies for a given regime.
    - Enforce weight normalization.
    - Track regime transitions for cost accounting.
    - No forced liquidation — existing positions continue management.
    """

    def __init__(self) -> None:
        self._previous_regime: Optional[Regime] = None
        self._transition_count: int = 0
        self._transition_dates: list[str] = []

    # ------------------------------------------------------------------
    # Query Methods
    # ------------------------------------------------------------------

    def get_active_strategies(self, regime: Regime) -> dict[str, float]:
        """Return {strategy_name: weight} for the given regime.

        Returns empty dict for UNCERTAIN (no new entries).
        """
        return dict(REGIME_STRATEGY_MAP.get(regime, {}))

    def get_normalized_weights(self, regime: Regime) -> dict[str, float]:
        """Return normalized strategy weights that sum to 1.0."""
        raw = self.get_active_strategies(regime)
        total = sum(raw.values())
        if total <= 0:
            return {}
        return {name: w / total for name, w in raw.items()}

    def is_regime_active(self, regime: Regime) -> bool:
        """Returns True if the regime has any active strategies."""
        return len(REGIME_STRATEGY_MAP.get(regime, {})) > 0

    # ------------------------------------------------------------------
    # Transition Tracking
    # ------------------------------------------------------------------

    def record_transition(self, current_regime: Regime, date: str) -> bool:
        """Record a regime transition. Returns True if transition occurred."""
        if self._previous_regime is not None and current_regime != self._previous_regime:
            self._transition_count += 1
            self._transition_dates.append(
                f"{date}: {self._previous_regime.value} -> {current_regime.value}"
            )
            self._previous_regime = current_regime
            return True
        self._previous_regime = current_regime
        return False

    @property
    def transition_count(self) -> int:
        """Total number of regime transitions tracked."""
        return self._transition_count

    @property
    def transition_log(self) -> list[str]:
        """Log of transition events."""
        return list(self._transition_dates)

    def reset(self) -> None:
        """Reset transition tracking (for walk-forward windows)."""
        self._previous_regime = None
        self._transition_count = 0
        self._transition_dates = []