"""Backtesting engine for the Midas Transit System.

Iterates historical dates from CSV, generates signals, compares to actual
price moves (5-day forward return). Computes win rate, profit factor,
Sharpe ratio, max drawdown. Includes Monte Carlo baseline (10k permutations).
"""

import argparse
import os
import sys
import random
from dataclasses import dataclass
from datetime import date, datetime
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd

from xau_astro_forecast.modules.ephemeris import compute_positions
from xau_astro_forecast.modules.natal import compute_natal_chart
from xau_astro_forecast.modules.aspects import compute_all_aspects
from xau_astro_forecast.modules.moon import get_moon_phase
from xau_astro_forecast.modules.price_analysis import (
    load_prices,
    compute_metrics,
    get_metrics_for_date,
    PriceMetrics,
)
from xau_astro_forecast.modules.scoring import score_aspects
from xau_astro_forecast.modules.direction import compute_direction
from xau_astro_forecast.modules.signal import generate_signal, SignalResult


MIN_SIGNALS = 200
MONTE_CARLO_PERMUTATIONS = 10000
FORWARD_DAYS = 5


@dataclass
class BacktestTrade:
    """A single backtest trade record."""
    date: str
    signal: str        # LONG, SHORT, NEUTRAL
    position_size: int
    forward_return: float  # 5-day % return
    pnl: float             # signed P&L (position_size * return * direction)


@dataclass
class BacktestMetrics:
    """Aggregate backtest metrics."""
    total_signals: int
    active_trades: int  # non-NEUTRAL
    win_rate: float
    profit_factor: float
    sharpe_ratio: float
    max_drawdown: float
    total_return: float


def compute_forward_returns(df: pd.DataFrame, n: int = FORWARD_DAYS) -> pd.DataFrame:
    """Add forward N-day return column to price dataframe."""
    df = df.copy()
    df["fwd_return"] = df["close"].shift(-n) / df["close"] - 1.0
    return df


def generate_signal_for_date(
    target_date: date,
    price_df: pd.DataFrame,
) -> Optional[SignalResult]:
    """Run the full pipeline for a single date and return the signal."""
    try:
        positions = compute_positions(target_date)
        natal = compute_natal_chart()
        aspects = compute_all_aspects(
            transit_positions=positions,
            natal_planets=natal.planets,
            asc=natal.asc,
            mc=natal.mc,
        )
        metrics = get_metrics_for_date(
            price_df, target_date.strftime("%Y-%m-%d")
        )
        scoring = score_aspects(aspects)
        direction = compute_direction(aspects, metrics)
        signal = generate_signal(direction, scoring, metrics)
        return signal
    except Exception:
        return None


def run_backtest(
    csv_path: str,
    forward_days: int = FORWARD_DAYS,
    verbose: bool = False,
) -> Tuple[List[BacktestTrade], BacktestMetrics]:
    """Run backtest over all dates in CSV.

    Args:
        csv_path: Path to XAU OHLCV CSV.
        forward_days: Number of days forward for return calculation.
        verbose: Print progress.

    Returns:
        Tuple of (trades, metrics).
    """
    df = load_prices(csv_path)
    df = compute_metrics(df)
    df = compute_forward_returns(df, forward_days)

    # Drop rows without forward return (last N days)
    valid_df = df.dropna(subset=["fwd_return"])

    trades: List[BacktestTrade] = []

    for i, row in valid_df.iterrows():
        date_str = str(row["date"]) if "date" in row else str(row.name)
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            continue

        signal = generate_signal_for_date(target_date, df)
        if signal is None:
            continue

        fwd_ret = float(row["fwd_return"])

        if signal.signal == "NEUTRAL":
            pnl = 0.0
        elif signal.signal == "LONG":
            pnl = fwd_ret * signal.position_size / 100.0
        else:  # SHORT
            pnl = -fwd_ret * signal.position_size / 100.0

        trades.append(BacktestTrade(
            date=date_str,
            signal=signal.signal,
            position_size=signal.position_size,
            forward_return=fwd_ret,
            pnl=pnl,
        ))

        if verbose and len(trades) % 20 == 0:
            print(f"  Processed {len(trades)} dates...", file=sys.stderr)

    metrics = compute_metrics_from_trades(trades)
    return trades, metrics


def compute_metrics_from_trades(trades: List[BacktestTrade]) -> BacktestMetrics:
    """Compute aggregate metrics from a list of trades."""
    active = [t for t in trades if t.signal != "NEUTRAL"]
    total_signals = len(trades)
    active_trades = len(active)

    if active_trades == 0:
        return BacktestMetrics(
            total_signals=total_signals,
            active_trades=0,
            win_rate=0.0,
            profit_factor=0.0,
            sharpe_ratio=0.0,
            max_drawdown=0.0,
            total_return=0.0,
        )

    # Win rate
    wins = [t for t in active if t.pnl > 0]
    win_rate = len(wins) / active_trades

    # Profit factor
    gross_profit = sum(t.pnl for t in active if t.pnl > 0)
    gross_loss = abs(sum(t.pnl for t in active if t.pnl < 0))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    # Sharpe ratio (annualized, assuming ~252 trading days)
    pnls = np.array([t.pnl for t in active])
    mean_pnl = float(np.mean(pnls))
    std_pnl = float(np.std(pnls, ddof=1)) if len(pnls) > 1 else 0.0
    sharpe_ratio = (mean_pnl / std_pnl * np.sqrt(252)) if std_pnl > 0 else 0.0

    # Max drawdown
    cumulative = np.cumsum(pnls)
    running_max = np.maximum.accumulate(cumulative)
    drawdowns = running_max - cumulative
    max_drawdown = float(np.max(drawdowns)) if len(drawdowns) > 0 else 0.0

    total_return = float(np.sum(pnls))

    return BacktestMetrics(
        total_signals=total_signals,
        active_trades=active_trades,
        win_rate=win_rate,
        profit_factor=profit_factor,
        sharpe_ratio=float(sharpe_ratio),
        max_drawdown=max_drawdown,
        total_return=total_return,
    )


def monte_carlo_baseline(
    trades: List[BacktestTrade],
    n_permutations: int = MONTE_CARLO_PERMUTATIONS,
    seed: Optional[int] = None,
) -> BacktestMetrics:
    """Run Monte Carlo baseline by randomly permuting signal directions.

    Keeps the same dates and forward returns but randomly assigns
    LONG/SHORT/NEUTRAL with the same distribution as actual signals.

    Args:
        trades: Original backtest trades.
        n_permutations: Number of random permutations.
        seed: Random seed for reproducibility.

    Returns:
        Average metrics across all permutations.
    """
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)

    if not trades:
        return compute_metrics_from_trades([])

    # Extract signal distribution
    signals = [t.signal for t in trades]
    position_sizes = [t.position_size for t in trades]

    all_win_rates: List[float] = []
    all_profit_factors: List[float] = []
    all_sharpes: List[float] = []
    all_drawdowns: List[float] = []

    for _ in range(n_permutations):
        # Shuffle signals randomly
        shuffled_signals = signals.copy()
        random.shuffle(shuffled_signals)
        shuffled_sizes = position_sizes.copy()
        random.shuffle(shuffled_sizes)

        perm_trades: List[BacktestTrade] = []
        for j, t in enumerate(trades):
            sig = shuffled_signals[j]
            size = shuffled_sizes[j]
            if sig == "NEUTRAL":
                pnl = 0.0
            elif sig == "LONG":
                pnl = t.forward_return * size / 100.0
            else:
                pnl = -t.forward_return * size / 100.0

            perm_trades.append(BacktestTrade(
                date=t.date,
                signal=sig,
                position_size=size,
                forward_return=t.forward_return,
                pnl=pnl,
            ))

        m = compute_metrics_from_trades(perm_trades)
        all_win_rates.append(m.win_rate)
        all_profit_factors.append(min(m.profit_factor, 100.0))  # cap inf
        all_sharpes.append(m.sharpe_ratio)
        all_drawdowns.append(m.max_drawdown)

    return BacktestMetrics(
        total_signals=len(trades),
        active_trades=len([t for t in trades if t.signal != "NEUTRAL"]),
        win_rate=float(np.mean(all_win_rates)),
        profit_factor=float(np.mean(all_profit_factors)),
        sharpe_ratio=float(np.mean(all_sharpes)),
        max_drawdown=float(np.mean(all_drawdowns)),
        total_return=0.0,  # not meaningful for baseline
    )


def format_summary(
    actual: BacktestMetrics,
    baseline: BacktestMetrics,
) -> str:
    """Format comparison summary table."""
    lines = []
    lines.append("=" * 60)
    lines.append("  MIDAS TRANSIT SYSTEM - BACKTEST RESULTS")
    lines.append("=" * 60)
    lines.append("")

    if actual.total_signals < MIN_SIGNALS:
        lines.append(
            f"  ⚠️  WARNING: Only {actual.total_signals} signals generated "
            f"(minimum {MIN_SIGNALS} recommended for statistical significance)"
        )
        lines.append("")

    lines.append(f"  Total Signals:   {actual.total_signals}")
    lines.append(f"  Active Trades:   {actual.active_trades}")
    lines.append(f"  Forward Period:  {FORWARD_DAYS} days")
    lines.append("")
    lines.append(f"  {'Metric':<20} {'Actual':>12} {'MC Baseline':>12} {'Edge':>12}")
    lines.append(f"  {'-'*20} {'-'*12} {'-'*12} {'-'*12}")

    def fmt_pct(v: float) -> str:
        return f"{v*100:.1f}%"

    def fmt_f(v: float) -> str:
        return f"{v:.3f}"

    rows = [
        ("Win Rate", fmt_pct(actual.win_rate), fmt_pct(baseline.win_rate),
         fmt_pct(actual.win_rate - baseline.win_rate)),
        ("Profit Factor", fmt_f(actual.profit_factor), fmt_f(baseline.profit_factor),
         fmt_f(actual.profit_factor - baseline.profit_factor)),
        ("Sharpe Ratio", fmt_f(actual.sharpe_ratio), fmt_f(baseline.sharpe_ratio),
         fmt_f(actual.sharpe_ratio - baseline.sharpe_ratio)),
        ("Max Drawdown", fmt_pct(actual.max_drawdown), fmt_pct(baseline.max_drawdown),
         fmt_pct(actual.max_drawdown - baseline.max_drawdown)),
    ]

    for name, act, base, edge in rows:
        lines.append(f"  {name:<20} {act:>12} {base:>12} {edge:>12}")

    lines.append("")
    lines.append(f"  Total Return:    {fmt_pct(actual.total_return)}")
    lines.append(f"  MC Permutations: {MONTE_CARLO_PERMUTATIONS:,}")
    lines.append("=" * 60)

    return "\n".join(lines)


def _default_csv_path() -> str:
    """Return default path to xau_prices.csv."""
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "xau_astro_forecast", "data", "xau_prices.csv")


def main(argv: Optional[List[str]] = None) -> None:
    """Entry point for backtesting."""
    parser = argparse.ArgumentParser(
        prog="midas-backtest",
        description="Midas Transit System - Backtesting Engine",
    )
    parser.add_argument(
        "--csv",
        type=str,
        default=None,
        help="Path to XAU OHLCV CSV file",
    )
    parser.add_argument(
        "--forward-days",
        type=int,
        default=FORWARD_DAYS,
        help=f"Forward return period in days (default: {FORWARD_DAYS})",
    )
    parser.add_argument(
        "--mc-perms",
        type=int,
        default=MONTE_CARLO_PERMUTATIONS,
        help=f"Monte Carlo permutations (default: {MONTE_CARLO_PERMUTATIONS})",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print progress",
    )
    args = parser.parse_args(argv)

    csv_path = args.csv if args.csv else _default_csv_path()
    if not os.path.exists(csv_path):
        print(f"Error: CSV file not found: {csv_path}", file=sys.stderr)
        sys.exit(1)

    mc_perms = args.mc_perms

    print("Running backtest...", file=sys.stderr)
    trades, actual = run_backtest(csv_path, args.forward_days, args.verbose)

    if not trades:
        print("No trades generated. Check CSV data.", file=sys.stderr)
        sys.exit(1)

    print(f"Generated {len(trades)} signals. Running Monte Carlo baseline...", file=sys.stderr)
    baseline = monte_carlo_baseline(trades, mc_perms)

    summary = format_summary(actual, baseline)
    print(summary)


if __name__ == "__main__":
    main()
