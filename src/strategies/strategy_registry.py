"""Central registry for discovering and retrieving trading strategies."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.strategies.base_strategy import BaseStrategy


class StrategyNotFoundError(LookupError):
    """Raised when an unknown strategy name is requested."""


class StrategyRegistry:
    """A singleton-like registry of available strategy classes.

    Usage::

        from src.strategies.strategy_registry import StrategyRegistry
        from src.strategies.ema_rsi_macd_strategy import EmaRsiMacdStrategy

        StrategyRegistry.register(EmaRsiMacdStrategy)
        strategy = StrategyRegistry.get_strategy("ema_rsi_macd")
        print(strategy.get_strategy_name())
    """

    _strategies: dict[str, type[BaseStrategy]] = {}

    @classmethod
    def register(cls, strategy_class: type[BaseStrategy]) -> None:
        """Register a strategy class under its :meth:`~BaseStrategy.get_strategy_name`.

        Args:
            strategy_class: A concrete subclass of
                :class:`~src.strategies.base_strategy.BaseStrategy`.

        Raises:
            TypeError: If *strategy_class* is not a :class:`BaseStrategy` subclass.
        """
        if not hasattr(strategy_class, "get_strategy_name"):
            raise TypeError(
                f"{strategy_class.__name__} does not implement get_strategy_name"
            )
        name = strategy_class.get_strategy_name(strategy_class)
        cls._strategies[name] = strategy_class

    @classmethod
    def get_strategy(cls, name: str) -> type[BaseStrategy]:
        """Return the strategy class registered under *name*.

        Args:
            name: The strategy name (e.g. ``"ema_rsi_macd"``).

        Returns:
            The strategy class.

        Raises:
            StrategyNotFoundError: If *name* is not registered.
        """
        try:
            return cls._strategies[name]
        except KeyError:
            raise StrategyNotFoundError(
                f"No strategy registered for '{name}'. "
                f"Available: {', '.join(sorted(cls._strategies))}"
            )

    @classmethod
    def list_strategies(cls) -> list[str]:
        """Return the names of all registered strategies."""
        return sorted(cls._strategies)

    @classmethod
    def clear(cls) -> None:
        """Clear all registered strategies (useful for testing)."""
        cls._strategies.clear()
