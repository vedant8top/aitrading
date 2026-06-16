"""Large-scale statistical validation of all registered trading strategies."""

from __future__ import annotations

import argparse
import logging
import math
from dataclasses import asdict, dataclass
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_DIR = PROJECT_ROOT / "data" / "strategy_comparison"
DEFAULT_REPORT_PATH = PROJECT_ROOT / "docs" / "large_scale_validation.md"
DEFAULT_LOG_PATH = PROJECT_ROOT / "logs" / "large_scale_validation.log"
TRADING_DAYS_PER_YEAR = 252
MIN_TRADES_HIGH_CONFIDENCE = 100
MIN_TRADES_MEDIUM_CONFIDENCE = 30


@dataclass(frozen=True)
class StrategyValidation:
    """Validated metrics for a single strategy."""

    name: str
    total_trades: int
    trades_per_year: float
    avg_holding_days: float
    win_rate_pct: float
    total_return_pct: float
    cagr_pct: float
    sharpe_ratio: float
    profit_factor: str
    max_drawdown_pct: float
    avg_win: float
    avg_loss: float
    confidence: str
    rank_return: int
    rank_sharpe: int
    rank_profit_factor: int
    rank_drawdown: int
    composite_score: float


def configure_logging(log_path: Path) -> logging.Logger:
    """Configure console and rotating file logging."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("large_scale_validation")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )
    file_handler = RotatingFileHandler(
        log_path, maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger


def load_portfolio_metrics(input_dir: Path) -> pd.DataFrame:
    """Load the portfolio metrics CSV produced by strategy_comparison."""
    path = input_dir / "portfolio_metrics.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"portfolio_metrics.csv not found in {input_dir}. "
            "Run strategy comparison first."
        )
    df = pd.read_csv(path)
    if df.empty:
        raise ValueError("portfolio_metrics.csv is empty")
    return df


def load_trades_for_strategy(input_dir: Path, strategy_name: str) -> pd.DataFrame:
    """Load trade-level data for a given strategy, if available."""
    path = input_dir / f"trades_{strategy_name}.csv"
    if path.exists():
        df = pd.read_csv(path)
        if not df.empty:
            return df
    return pd.DataFrame()


def determine_confidence(total_trades: int) -> str:
    """Assign confidence level based on trade count."""
    if total_trades >= MIN_TRADES_HIGH_CONFIDENCE:
        return "High Confidence"
    elif total_trades >= MIN_TRADES_MEDIUM_CONFIDENCE:
        return "Medium Confidence"
    else:
        return "Low Confidence"


def compute_trades_per_year(
    total_trades: int, cagr_pct: float, total_return_pct: float
) -> float:
    """Estimate trades per year from available metrics."""
    if abs(cagr_pct) > 0.01:
        years = abs(total_return_pct / cagr_pct) if cagr_pct != 0 else 1.0
    else:
        years = 1.0
    if years < 0.1:
        years = 1.0
    return round(total_trades / max(years, 0.1), 1)


def parse_profit_factor(pf: object) -> float:
    """Convert profit factor string or float to numeric value."""
    if isinstance(pf, str):
        if pf in ("Infinity", "inf", "infinity"):
            return float("inf")
        try:
            return float(pf)
        except (ValueError, TypeError):
            return 0.0
    return float(pf) if pf is not None else 0.0


def validate_strategies(
    metrics_df: pd.DataFrame, input_dir: Path, logger: logging.Logger
) -> list[StrategyValidation]:
    """Build a validated record for each strategy."""
    results: list[StrategyValidation] = []

    for _, row in metrics_df.iterrows():
        name = str(row["strategy"])
        total_trades = int(row.get("total_trades", 0))
        win_rate = float(row.get("win_rate_pct", 0.0))
        total_return = float(row.get("total_return_pct", 0.0))
        cagr = float(row.get("cagr_pct", 0.0))
        sharpe = float(row.get("sharpe_ratio", 0.0))
        pf_raw = row.get("profit_factor", "0.0")
        max_dd = float(row.get("max_drawdown_pct", 0.0))
        avg_win = float(row.get("avg_win", 0.0))
        avg_loss = float(row.get("avg_loss", 0.0))

        # Load trade data for additional metrics
        trades_df = load_trades_for_strategy(input_dir, name)
        if not trades_df.empty and "holding_days" in trades_df.columns:
            avg_holding = float(trades_df["holding_days"].mean())
        else:
            avg_holding = 0.0

        confidence = determine_confidence(total_trades)
        trades_per_year = compute_trades_per_year(total_trades, cagr, total_return)

        logger.info(
            "Strategy %s: trades=%d, win_rate=%.1f%%, return=%.2f%%, "
            "sharpe=%.3f, confidence=%s",
            name,
            total_trades,
            win_rate,
            total_return,
            sharpe,
            confidence,
        )

        results.append(
            StrategyValidation(
                name=name,
                total_trades=total_trades,
                trades_per_year=trades_per_year,
                avg_holding_days=round(avg_holding, 1),
                win_rate_pct=round(win_rate, 2),
                total_return_pct=round(total_return, 4),
                cagr_pct=round(cagr, 4),
                sharpe_ratio=round(sharpe, 4),
                profit_factor=str(pf_raw),
                max_drawdown_pct=round(max_dd, 4),
                avg_win=round(avg_win, 2),
                avg_loss=round(avg_loss, 2),
                confidence=confidence,
                rank_return=0,
                rank_sharpe=0,
                rank_profit_factor=0,
                rank_drawdown=0,
                composite_score=0.0,
            )
        )

    return results


def rank_strategies(
    results: list[StrategyValidation],
) -> list[StrategyValidation]:
    """Rank strategies across multiple dimensions and compute composite score."""
    if not results:
        return results

    # Rank each metric (lower rank = better)
    # Total return: higher is better
    sorted_return = sorted(results, key=lambda r: r.total_return_pct, reverse=True)
    return_ranks = {s.name: i + 1 for i, s in enumerate(sorted_return)}

    # Sharpe: higher is better
    sorted_sharpe = sorted(results, key=lambda r: r.sharpe_ratio, reverse=True)
    sharpe_ranks = {s.name: i + 1 for i, s in enumerate(sorted_sharpe)}

    # Profit factor: higher is better (ignore infinity)
    def pf_sort_key(r: StrategyValidation) -> float:
        pf = parse_profit_factor(r.profit_factor)
        return pf if math.isfinite(pf) else 1e9

    sorted_pf = sorted(results, key=pf_sort_key, reverse=True)
    pf_ranks = {s.name: i + 1 for i, s in enumerate(sorted_pf)}

    # Max drawdown: less negative (higher) is better
    sorted_dd = sorted(results, key=lambda r: r.max_drawdown_pct, reverse=True)
    dd_ranks = {s.name: i + 1 for i, s in enumerate(sorted_dd)}

    ranked: list[StrategyValidation] = []
    for r in results:
        rank_r = return_ranks.get(r.name, len(results))
        rank_s = sharpe_ranks.get(r.name, len(results))
        rank_p = pf_ranks.get(r.name, len(results))
        rank_d = dd_ranks.get(r.name, len(results))

        # Composite: weighted average of ranks (lower is better)
        # Weights: return=30%, sharpe=30%, profit_factor=20%, drawdown=20%
        composite = rank_r * 0.30 + rank_s * 0.30 + rank_p * 0.20 + rank_d * 0.20

        ranked.append(
            StrategyValidation(
                name=r.name,
                total_trades=r.total_trades,
                trades_per_year=r.trades_per_year,
                avg_holding_days=r.avg_holding_days,
                win_rate_pct=r.win_rate_pct,
                total_return_pct=r.total_return_pct,
                cagr_pct=r.cagr_pct,
                sharpe_ratio=r.sharpe_ratio,
                profit_factor=r.profit_factor,
                max_drawdown_pct=r.max_drawdown_pct,
                avg_win=r.avg_win,
                avg_loss=r.avg_loss,
                confidence=r.confidence,
                rank_return=rank_r,
                rank_sharpe=rank_s,
                rank_profit_factor=rank_p,
                rank_drawdown=rank_d,
                composite_score=round(composite, 2),
            )
        )

    # Sort by composite score (ascending = better)
    ranked.sort(key=lambda r: r.composite_score)
    return ranked


def generate_report(
    results: list[StrategyValidation],
    output_path: Path,
    log_path: Path,
) -> None:
    """Generate the large-scale validation markdown report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = [
        "# Large-Scale Statistical Validation Report",
        "",
        "## Overview",
        "",
        "This report evaluates all registered trading strategies over an expanded "
        "NIFTY 50 universe with 5+ years of historical daily data. The goal is to "
        "determine whether any strategy exhibits a statistically meaningful edge.",
        "",
    ]

    # Dataset description
    lines.append("### Dataset")
    lines.append("")
    lines.append("- **Universe:** NIFTY 50 stocks")
    lines.append("- **Period:** 2018-01-01 to latest available date")
    lines.append("- **Timeframe:** Daily")
    lines.append("- **Data source:** Yahoo Finance (via yfinance)")
    lines.append("- **Backtest assumptions:** Long-only, next-open execution, 0.05% brokerage, 0.05% slippage, 10% position sizing")
    lines.append("")

    # Leaderboard
    lines.append("## Final Strategy Leaderboard")
    lines.append("")
    lines.append(
        "| Rank | Strategy | Return % | CAGR % | Sharpe | Win Rate | Trades | "
        "Trades/Yr | Avg Hold Days | Profit Factor | Max DD % | Confidence |"
    )
    lines.append(
        "|------|----------|----------|--------|--------|----------|--------|"
        "-----------|----------------|---------------|----------|------------|"
    )
    for rank, r in enumerate(results, 1):
        lines.append(
            f"| {rank} | {r.name} | {r.total_return_pct:.2f}% "
            f"| {r.cagr_pct:.2f}% | {r.sharpe_ratio:.3f} "
            f"| {r.win_rate_pct:.1f}% | {r.total_trades} "
            f"| {r.trades_per_year:.1f} | {r.avg_holding_days:.0f} "
            f"| {r.profit_factor} | {r.max_drawdown_pct:.2f}% "
            f"| {r.confidence} |"
        )
    lines.append("")

    # Per-strategy detailed analysis
    lines.append("## Per-Strategy Analysis")
    lines.append("")
    for rank, r in enumerate(results, 1):
        lines.append(f"### {rank}. {r.name}")
        lines.append("")
        lines.append("**Performance Metrics:**")
        lines.append("")
        lines.append(f"- Total trades: {r.total_trades}")
        lines.append(f"- Trades per year: {r.trades_per_year:.1f}")
        lines.append(f"- Average holding period: {r.avg_holding_days:.0f} days")
        lines.append(f"- Win rate: {r.win_rate_pct:.1f}%")
        lines.append(f"- Total return: {r.total_return_pct:.2f}%")
        lines.append(f"- CAGR: {r.cagr_pct:.2f}%")
        lines.append(f"- Sharpe ratio: {r.sharpe_ratio:.3f}")
        lines.append(f"- Profit factor: {r.profit_factor}")
        lines.append(f"- Maximum drawdown: {r.max_drawdown_pct:.2f}%")
        lines.append(f"- Average win: INR {r.avg_win:.2f}")
        lines.append(f"- Average loss: INR {r.avg_loss:.2f}")
        lines.append("")
        lines.append(f"**Confidence Level:** {r.confidence}")
        lines.append("")
        lines.append("**Rankings:**")
        lines.append(f"- Return rank: {r.rank_return}")
        lines.append(f"- Sharpe rank: {r.rank_sharpe}")
        lines.append(f"- Profit factor rank: {r.rank_profit_factor}")
        lines.append(f"- Drawdown rank: {r.rank_drawdown}")
        lines.append(f"- Composite score: {r.composite_score} (lower is better)")
        lines.append("")

    # Best-in-class summary
    lines.append("## Best-in-Class Summary")
    lines.append("")

    if results:
        best_return = max(results, key=lambda r: r.total_return_pct)
        best_sharpe = max(results, key=lambda r: r.sharpe_ratio)
        best_pf = max(
            results,
            key=lambda r: parse_profit_factor(r.profit_factor)
            if math.isfinite(parse_profit_factor(r.profit_factor))
            else 0,
        )
        best_dd = max(results, key=lambda r: r.max_drawdown_pct)

        lines.append(f"- **Best return:** {best_return.name} ({best_return.total_return_pct:.2f}%)")
        lines.append(f"- **Best Sharpe:** {best_sharpe.name} ({best_sharpe.sharpe_ratio:.3f})")
        lines.append(f"- **Best profit factor:** {best_pf.name} ({best_pf.profit_factor})")
        lines.append(f"- **Lowest drawdown:** {best_dd.name} ({best_dd.max_drawdown_pct:.2f}%)")
        lines.append("")

    # Confidence assessment
    lines.append("## Confidence Assessment")
    lines.append("")
    lines.append(
        "Confidence is determined by the number of completed trades:"
    )
    lines.append("")
    lines.append(f"- **High Confidence:** {MIN_TRADES_HIGH_CONFIDENCE}+ trades")
    lines.append(f"- **Medium Confidence:** {MIN_TRADES_MEDIUM_CONFIDENCE}–{MIN_TRADES_HIGH_CONFIDENCE - 1} trades")
    lines.append(f"- **Low Confidence:** fewer than {MIN_TRADES_MEDIUM_CONFIDENCE} trades")
    lines.append("")

    for r in results:
        flag = ""
        if r.total_trades < MIN_TRADES_MEDIUM_CONFIDENCE:
            flag = " ⚠️ Insufficient trades for reliable inference"
        elif r.total_trades < MIN_TRADES_HIGH_CONFIDENCE:
            flag = " ⚠️ Moderate trade count — results should be interpreted cautiously"
        lines.append(f"- **{r.name}:** {r.confidence}{flag}")
    lines.append("")

    # Recommendation
    lines.append("## Recommendation")
    lines.append("")

    if results:
        top = results[0]
        lines.append(f"### Advance to Risk-Management Testing")
        lines.append("")
        if top.total_trades >= MIN_TRADES_MEDIUM_CONFIDENCE and top.total_return_pct > 0:
            lines.append(
                f"**{top.name}** — ranked #1 overall with a composite score of "
                f"{top.composite_score}. It achieved {top.total_return_pct:.2f}% return "
                f"across {top.total_trades} trades with a Sharpe of {top.sharpe_ratio:.3f} "
                f"and win rate of {top.win_rate_pct:.1f}%. Confidence: {top.confidence}."
            )
        else:
            lines.append(
                f"**{top.name}** — ranked #1 but with limited statistical confidence "
                f"({top.total_trades} trades). Further data collection is recommended "
                "before advancing to risk-management testing."
            )
        lines.append("")

        # Rejected strategies
        rejected = [r for r in results if r.total_return_pct <= 0 or r.total_trades < MIN_TRADES_MEDIUM_CONFIDENCE]
        if rejected:
            lines.append("### Reject or Require Further Validation")
            lines.append("")
            for r in results[1:]:
                reasons = []
                if r.total_return_pct <= 0:
                    reasons.append("negative or zero return")
                if r.total_trades < MIN_TRADES_MEDIUM_CONFIDENCE:
                    reasons.append(f"only {r.total_trades} trades (insufficient sample size)")
                if r.sharpe_ratio < 0:
                    reasons.append(f"negative Sharpe ratio ({r.sharpe_ratio:.3f})")
                reason_str = "; ".join(reasons) if reasons else "underperformed on composite ranking"
                lines.append(f"- **{r.name}:** {reason_str}")
            lines.append("")

    # Caveats
    lines.append("## Caveats & Limitations")
    lines.append("")
    lines.append(
        "- **Survivorship bias:** The NIFTY 50 composition changes over time. "
        "Constituents that were replaced during 2018–2026 are not included."
    )
    lines.append(
        "- **Look-ahead bias:** Indicators are calculated on the full历史 dataset "
        "without walk-forward validation. Future work should implement expanding "
        "or rolling window validation."
    )
    lines.append(
        "- **Single time frame:** All results are based on daily data. "
        "Intraday or multi-timeframe analysis may yield different conclusions."
    )
    lines.append(
        "- **Parameter overfitting:** Current strategy parameters are fixed. "
        "Robustness should be verified via sensitivity analysis."
    )
    lines.append(
        "- **No transaction costs beyond brokerage/slippage:** Market impact, "
        "STT, SEBI charges, and GST are not modeled."
    )
    lines.append(
        "- **Yahoo Finance data quality:** Splits, dividends, and corporate actions "
        "are handled by yfinance's auto_adjust=False mode. Manual verification "
        "of individual ticker data is recommended."
    )
    lines.append("")

    # Generated files
    lines.append("## Generated Files")
    lines.append("")
    lines.append(f"- `data/strategy_comparison/portfolio_metrics.csv`")
    lines.append(f"- `data/strategy_comparison/signal_counts.csv`")
    lines.append(f"- `data/strategy_comparison/comparison_report.md`")
    lines.append(f"- `{output_path.relative_to(PROJECT_ROOT).as_posix()}`")
    lines.append(f"- `{log_path.relative_to(PROJECT_ROOT).as_posix()}`")
    lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Validation report: {output_path.relative_to(PROJECT_ROOT).as_posix()}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run large-scale statistical validation on all strategies."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help="Directory containing strategy comparison outputs",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=DEFAULT_REPORT_PATH,
        help="Path for the validation markdown report",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=DEFAULT_LOG_PATH,
        help="Log file path",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logger = configure_logging(args.log_file.resolve())

    try:
        logger.info("=" * 60)
        logger.info("Large-Scale Statistical Validation Started")
        logger.info("=" * 60)

        metrics_df = load_portfolio_metrics(args.input_dir.resolve())
        logger.info(
            "Loaded portfolio metrics for %d strategies", len(metrics_df)
        )

        results = validate_strategies(
            metrics_df, args.input_dir.resolve(), logger
        )
        ranked = rank_strategies(results)

        generate_report(ranked, args.report.resolve(), args.log_file.resolve())

        # Print leaderboard to console
        print("\n" + "=" * 80)
        print("STRATEGY LEADERBOARD")
        print("=" * 80)
        print(
            f"{'Rank':<6} {'Strategy':<20} {'Return%':<10} {'Sharpe':<8} "
            f"{'WinRate':<8} {'Trades':<8} {'Confidence':<18}"
        )
        print("-" * 80)
        for rank, r in enumerate(ranked, 1):
            print(
                f"{rank:<6} {r.name:<20} {r.total_return_pct:<10.2f} "
                f"{r.sharpe_ratio:<8.3f} {r.win_rate_pct:<8.1f} "
                f"{r.total_trades:<8} {r.confidence:<18}"
            )
        print("=" * 80)

        logger.info(
            "Validation complete: %d strategies validated, report written",
            len(ranked),
        )
        return 0

    except Exception as exc:
        logger.exception("Validation failed")
        print(f"Fatal validation error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())