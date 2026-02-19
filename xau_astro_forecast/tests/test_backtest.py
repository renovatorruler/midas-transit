"""Tests for backtest module."""

import pytest
from unittest.mock import patch, MagicMock
from datetime import date

from xau_astro_forecast.backtest import (
    BacktestTrade,
    BacktestMetrics,
    compute_metrics_from_trades,
    compute_forward_returns,
    monte_carlo_baseline,
    format_summary,
    MIN_SIGNALS,
)
from xau_astro_forecast.modules.signal import SignalResult

import pandas as pd
import numpy as np


# --- compute_forward_returns ---

def test_compute_forward_returns_basic() -> None:
    """Forward returns computed correctly."""
    df = pd.DataFrame({
        "close": [100.0, 105.0, 110.0, 108.0, 112.0, 115.0, 120.0, 118.0],
    })
    result = compute_forward_returns(df, n=3)
    assert "fwd_return" in result.columns
    # row 0: close[3]/close[0] - 1 = 108/100 - 1 = 0.08
    assert abs(result["fwd_return"].iloc[0] - 0.08) < 1e-6
    # last 3 should be NaN
    assert pd.isna(result["fwd_return"].iloc[-1])
    assert pd.isna(result["fwd_return"].iloc[-2])
    assert pd.isna(result["fwd_return"].iloc[-3])


def test_compute_forward_returns_preserves_original() -> None:
    """Original dataframe not modified."""
    df = pd.DataFrame({"close": [100.0, 110.0, 120.0]})
    result = compute_forward_returns(df, n=1)
    assert "fwd_return" not in df.columns
    assert "fwd_return" in result.columns


# --- compute_metrics_from_trades ---

def _make_trade(signal: str, fwd: float, size: int = 100) -> BacktestTrade:
    if signal == "LONG":
        pnl = fwd * size / 100.0
    elif signal == "SHORT":
        pnl = -fwd * size / 100.0
    else:
        pnl = 0.0
    return BacktestTrade(
        date="2024-01-01", signal=signal, position_size=size,
        forward_return=fwd, pnl=pnl,
    )


def test_metrics_empty_trades() -> None:
    """Empty trades return zero metrics."""
    m = compute_metrics_from_trades([])
    assert m.total_signals == 0
    assert m.active_trades == 0
    assert m.win_rate == 0.0


def test_metrics_all_neutral() -> None:
    """All neutral trades -> 0 active."""
    trades = [_make_trade("NEUTRAL", 0.05) for _ in range(5)]
    m = compute_metrics_from_trades(trades)
    assert m.total_signals == 5
    assert m.active_trades == 0
    assert m.win_rate == 0.0


def test_metrics_win_rate() -> None:
    """Win rate calculated correctly."""
    trades = [
        _make_trade("LONG", 0.05),   # win
        _make_trade("LONG", -0.03),  # loss
        _make_trade("LONG", 0.02),   # win
        _make_trade("SHORT", 0.01),  # short + positive return = loss
        _make_trade("SHORT", -0.04), # short + negative return = win
    ]
    m = compute_metrics_from_trades(trades)
    assert m.active_trades == 5
    # wins: LONG+0.05, LONG+0.02, SHORT-0.04 = 3 wins
    assert abs(m.win_rate - 0.6) < 1e-6


def test_metrics_profit_factor() -> None:
    """Profit factor = gross profit / gross loss."""
    trades = [
        _make_trade("LONG", 0.10),   # pnl = +0.10
        _make_trade("LONG", -0.05),  # pnl = -0.05
    ]
    m = compute_metrics_from_trades(trades)
    assert abs(m.profit_factor - 2.0) < 1e-6


def test_metrics_profit_factor_no_loss() -> None:
    """Profit factor is inf when no losses."""
    trades = [_make_trade("LONG", 0.05)]
    m = compute_metrics_from_trades(trades)
    assert m.profit_factor == float("inf")


def test_metrics_sharpe_ratio() -> None:
    """Sharpe ratio calculated with annualization."""
    trades = [
        _make_trade("LONG", 0.02),
        _make_trade("LONG", 0.03),
        _make_trade("LONG", 0.01),
    ]
    m = compute_metrics_from_trades(trades)
    pnls = [0.02, 0.03, 0.01]
    mean = np.mean(pnls)
    std = np.std(pnls, ddof=1)
    expected = mean / std * np.sqrt(252)
    assert abs(m.sharpe_ratio - expected) < 1e-4


def test_metrics_max_drawdown() -> None:
    """Max drawdown from peak."""
    trades = [
        _make_trade("LONG", 0.05),   # cum: 0.05
        _make_trade("LONG", 0.03),   # cum: 0.08
        _make_trade("LONG", -0.10),  # cum: -0.02, dd from 0.08 = 0.10
        _make_trade("LONG", 0.01),   # cum: -0.01, dd from 0.08 = 0.09
    ]
    m = compute_metrics_from_trades(trades)
    assert abs(m.max_drawdown - 0.10) < 1e-6


def test_metrics_total_return() -> None:
    """Total return is sum of PnLs."""
    trades = [
        _make_trade("LONG", 0.05),
        _make_trade("LONG", -0.02),
    ]
    m = compute_metrics_from_trades(trades)
    assert abs(m.total_return - 0.03) < 1e-6


# --- monte_carlo_baseline ---

def test_monte_carlo_returns_metrics() -> None:
    """Monte Carlo baseline returns valid metrics."""
    trades = [_make_trade("LONG", 0.02 * (i % 3 - 1)) for i in range(20)]
    baseline = monte_carlo_baseline(trades, n_permutations=100, seed=42)
    assert isinstance(baseline, BacktestMetrics)
    assert baseline.total_signals == 20
    assert 0.0 <= baseline.win_rate <= 1.0


def test_monte_carlo_empty() -> None:
    """Monte Carlo with no trades returns zero metrics."""
    baseline = monte_carlo_baseline([], n_permutations=10)
    assert baseline.total_signals == 0


def test_monte_carlo_deterministic() -> None:
    """Same seed produces same results."""
    trades = [_make_trade("LONG", 0.01 * i) for i in range(-5, 5)]
    b1 = monte_carlo_baseline(trades, n_permutations=50, seed=123)
    b2 = monte_carlo_baseline(trades, n_permutations=50, seed=123)
    assert abs(b1.win_rate - b2.win_rate) < 1e-6
    assert abs(b1.sharpe_ratio - b2.sharpe_ratio) < 1e-6


# --- format_summary ---

def test_format_summary_contains_metrics() -> None:
    """Summary output contains key metric labels."""
    actual = BacktestMetrics(100, 80, 0.55, 1.2, 0.8, 0.05, 0.10)
    baseline = BacktestMetrics(100, 80, 0.50, 1.0, 0.0, 0.06, 0.0)
    summary = format_summary(actual, baseline)
    assert "Win Rate" in summary
    assert "Profit Factor" in summary
    assert "Sharpe Ratio" in summary
    assert "Max Drawdown" in summary
    assert "BACKTEST RESULTS" in summary


def test_format_summary_warning_few_signals() -> None:
    """Warning shown when signals < MIN_SIGNALS."""
    actual = BacktestMetrics(50, 40, 0.5, 1.0, 0.0, 0.0, 0.0)
    baseline = BacktestMetrics(50, 40, 0.5, 1.0, 0.0, 0.0, 0.0)
    summary = format_summary(actual, baseline)
    assert "WARNING" in summary
    assert str(MIN_SIGNALS) in summary


def test_format_summary_no_warning_enough_signals() -> None:
    """No warning when signals >= MIN_SIGNALS."""
    actual = BacktestMetrics(250, 200, 0.5, 1.0, 0.0, 0.0, 0.0)
    baseline = BacktestMetrics(250, 200, 0.5, 1.0, 0.0, 0.0, 0.0)
    summary = format_summary(actual, baseline)
    assert "WARNING" not in summary


# --- Edge cases ---

def test_single_trade_metrics() -> None:
    """Single trade produces valid metrics."""
    trades = [_make_trade("LONG", 0.05)]
    m = compute_metrics_from_trades(trades)
    assert m.win_rate == 1.0
    assert m.active_trades == 1
    assert m.sharpe_ratio == 0.0  # std=0 with 1 trade


def test_position_size_scaling() -> None:
    """Position size properly scales PnL."""
    t50 = _make_trade("LONG", 0.10, size=50)
    t100 = _make_trade("LONG", 0.10, size=100)
    assert abs(t50.pnl - 0.05) < 1e-6
    assert abs(t100.pnl - 0.10) < 1e-6


def test_short_signal_pnl() -> None:
    """Short signal profits from negative returns."""
    t = _make_trade("SHORT", -0.05)
    assert t.pnl > 0  # short + negative return = profit
    t2 = _make_trade("SHORT", 0.05)
    assert t2.pnl < 0  # short + positive return = loss
