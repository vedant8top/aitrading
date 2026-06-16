"""Regime-specific metrics calculation for regime-aware portfolio evaluation."""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from src.regime_detection.regime_classifier import Regime


class RegimeMetrics:
    """Calculate regime-specific performance metrics.

    Metrics:
    - Regime purity: % days correctly classified (ex-post validation)
    - Regime utilization: % capital deployed per regime
    - Transition count & cost drag
    - Strategy contribution by regime
    - Regime alpha: excess return vs regime-matched benchmark
    """

    def __init__(self, regime_labels: pd.DataFrame) -> None:
        self.regime_labels = regime_labels  # Date-indexed with Regime column

    # ------------------------------------------------------------------
    # Regime Purity
    # ------------------------------------------------------------------

    def calculate_purity(self, ex_post_labels: pd.Series) -> dict[str, float]:
        """Calculate regime purity against ex-post labels.

        Purity = % of days where regime matches ex-post classification.
        """
        common_dates = self.regime_labels.index.intersection(ex_post_labels.index)
        if len(common_dates) == 0:
            return {"purity_overall": 0.0}

        aligned = pd.DataFrame({
            "predicted": self.regime_labels.loc[common_dates, "Regime"],
            "ex_post": ex_post_labels.loc[common_dates],
        })

        overall = (aligned["predicted"] == aligned["ex_post"]).mean()

        per_regime = {}
        for regime in Regime:
            mask = aligned["ex_post"] == regime.value
            if mask.sum() > 0:
                per_regime[f"purity_{regime.value.lower()}"] = (
                    (aligned.loc[mask, "predicted"] == aligned.loc[mask, "ex_post"]).mean()
                )
            else:
                per_regime[f"purity_{regime.value.lower()}"] = 0.0

        return {"purity_overall": round(float(overall), 4), **per_regime}

    # ------------------------------------------------------------------
    # Regime Utilization
    # ------------------------------------------------------------------

    def calculate_utilization(self, equity: pd.DataFrame) -> dict[str, float]:
        """Calculate capital utilization per regime.

        Utilization = average active weight per regime.
        """
        if "Regime" not in equity.columns or "Active_Weight" not in equity.columns:
            return {}

        utilization = {}
        for regime in Regime:
            mask = equity["Regime"] == regime.value
            if mask.sum() > 0:
                utilization[f"utilization_{regime.value.lower()}"] = round(
                    float(equity.loc[mask, "Active_Weight"].mean()), 4
                )
            else:
                utilization[f"utilization_{regime.value.lower()}"] = 0.0

        return utilization

    # ------------------------------------------------------------------
    # Transition Analysis
    # ------------------------------------------------------------------

    def calculate_transition_metrics(
        self, transition_count: int, total_days: int, cost_per_transition: float = 0.001
    ) -> dict[str, float]:
        """Calculate transition frequency and cost drag.

        cost_per_transition: 0.1% (slippage + brokerage) per transition.
        """
        years = total_days / 252
        freq_per_year = transition_count / years if years > 0 else 0
        cost_drag = transition_count * cost_per_transition * 100  # as % of capital

        return {
            "transition_count": transition_count,
            "transitions_per_year": round(freq_per_year, 2),
            "transition_cost_drag_pct": round(cost_drag, 2),
        }

    # ------------------------------------------------------------------
    # Strategy Contribution by Regime
    # ------------------------------------------------------------------

    def calculate_strategy_contribution(
        self,
        strategy_trades: dict[str, pd.DataFrame],
        regime_labels: pd.Series,
    ) -> dict[str, dict[str, float]]:
        """Calculate each strategy's P&L contribution within each regime.

        Returns {regime: {strategy: total_pnl}}.
        """
        contribution: dict[str, dict[str, float]] = {
            r.value: {} for r in Regime
        }

        for strategy, trades in strategy_trades.items():
            if trades.empty:
                continue

            # Assign each trade to a regime based on its entry date
            for _, trade in trades.iterrows():
                entry_date = trade.get("entry_date", None)
                if entry_date is None:
                    continue

                entry_str = pd.Timestamp(entry_date).date().isoformat()
                if entry_str not in regime_labels.index:
                    continue

                regime = regime_labels.loc[entry_str]
                pnl = float(trade.get("pnl", 0))

                if regime not in contribution:
                    contribution[regime] = {}
                if strategy not in contribution[regime]:
                    contribution[regime][strategy] = 0.0
                contribution[regime][strategy] += pnl

        return contribution

    # ------------------------------------------------------------------
    # Regime Alpha
    # ------------------------------------------------------------------

    def calculate_regime_alpha(
        self,
        portfolio_returns: pd.Series,
        benchmark_returns: pd.Series,
    ) -> dict[str, float]:
        """Calculate alpha (excess return) per regime vs benchmark.

        Alpha = portfolio_return - benchmark_return within each regime.
        """
        if "Regime" not in self.regime_labels.columns:
            return {}

        alpha = {}
        for regime in Regime:
            regime_dates = self.regime_labels[
                self.regime_labels["Regime"] == regime.value
            ].index

            common = regime_dates.intersection(portfolio_returns.index)
            common = common.intersection(benchmark_returns.index)

            if len(common) == 0:
                alpha[f"alpha_{regime.value.lower()}"] = 0.0
                continue

            port_ret = portfolio_returns.loc[common].sum()
            bench_ret = benchmark_returns.loc[common].sum()
            alpha[f"alpha_{regime.value.lower()}"] = round(
                float(port_ret - bench_ret) * 100, 2
            )

        return alpha

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def summary(
        self,
        equity: pd.DataFrame,
        portfolio_returns: pd.Series,
        benchmark_returns: pd.Series,
        transition_count: int,
        strategy_trades: Optional[dict[str, pd.DataFrame]] = None,
        ex_post_labels: Optional[pd.Series] = None,
    ) -> dict:
        """Compute all regime metrics and return a summary dict."""
        result: dict = {}

        # Utilization
        result.update(self.calculate_utilization(equity))

        # Transitions
        total_days = len(equity)
        result.update(self.calculate_transition_metrics(transition_count, total_days))

        # Regime alpha
        result.update(self.calculate_regime_alpha(portfolio_returns, benchmark_returns))

        # Purity (if ex-post labels available)
        if ex_post_labels is not None:
            result.update(self.calculate_purity(ex_post_labels))

        # Strategy contribution (if trades available)
        if strategy_trades is not None:
            regime_labels = self.regime_labels["Regime"]
            contrib = self.calculate_strategy_contribution(strategy_trades, regime_labels)
            for regime, strategies in contrib.items():
                for strategy, pnl in strategies.items():
                    result[f"pnl_{regime.lower()}_{strategy}"] = round(pnl, 2)

        return result