"""Price analysis module for XAU OHLCV data."""

from dataclasses import dataclass
from typing import Optional

import pandas as pd


@dataclass
class PriceMetrics:
    """Computed price metrics for a given date."""
    date: str
    close: float
    close_pos60: float  # percentile rank of close in 60-period window
    close_pos20: float  # percentile rank of close in 20-period window
    low_pos60: float    # percentile rank of low in 60-period window
    change5: float      # 5-day % change
    direction_1d: str   # "UP" or "DOWN"
    change_1d: float    # 1-day % change
    change_5d: float    # 5-day % change (same as change5)
    polarity: str       # "HIGH", "MID", or "LOW"


def _percentile_rank(series: pd.Series, window: int) -> pd.Series:
    """Compute rolling percentile rank: fraction of values in window <= current value."""
    def _rank_in_window(s: pd.Series) -> float:
        if len(s) < 2:
            return 50.0
        val = s.iloc[-1]
        count_le = (s <= val).sum()
        return float((count_le - 1) / (len(s) - 1) * 100.0)

    return series.rolling(window=window, min_periods=2).apply(_rank_in_window, raw=False)


def classify_polarity(close_pos60: float) -> str:
    """Classify polarity based on 60-period percentile."""
    if close_pos60 > 75.0:
        return "HIGH"
    elif close_pos60 < 25.0:
        return "LOW"
    return "MID"


def load_prices(csv_path: str) -> pd.DataFrame:
    """Load OHLCV CSV and return DataFrame."""
    df = pd.read_csv(csv_path, parse_dates=["date"])
    df = df.sort_values("date").reset_index(drop=True)
    return df


def compute_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Compute all price metrics on the DataFrame."""
    result = df.copy()
    result["close_pos60"] = _percentile_rank(result["close"], 60)
    result["close_pos20"] = _percentile_rank(result["close"], 20)
    result["low_pos60"] = _percentile_rank(result["low"], 60)
    result["change_1d"] = result["close"].pct_change() * 100.0
    result["change5"] = result["close"].pct_change(periods=5) * 100.0
    result["change_5d"] = result["change5"]
    result["direction_1d"] = result["change_1d"].apply(
        lambda x: "UP" if x >= 0 else "DOWN" if pd.notna(x) else "N/A"
    )
    result["polarity"] = result["close_pos60"].apply(
        lambda x: classify_polarity(x) if pd.notna(x) else "N/A"
    )
    return result


def get_metrics_for_date(df: pd.DataFrame, date_str: str) -> Optional[PriceMetrics]:
    """Get PriceMetrics for a specific date from a computed DataFrame."""
    enriched = compute_metrics(df)
    mask = enriched["date"] == pd.Timestamp(date_str)
    rows = enriched[mask]
    if rows.empty:
        return None
    row = rows.iloc[0]
    if pd.isna(row.get("close_pos60")):
        return None
    return PriceMetrics(
        date=date_str,
        close=float(row["close"]),
        close_pos60=float(row["close_pos60"]),
        close_pos20=float(row["close_pos20"]) if pd.notna(row.get("close_pos20")) else 0.0,
        low_pos60=float(row["low_pos60"]) if pd.notna(row.get("low_pos60")) else 0.0,
        change5=float(row["change5"]) if pd.notna(row.get("change5")) else 0.0,
        direction_1d=str(row["direction_1d"]),
        change_1d=float(row["change_1d"]) if pd.notna(row.get("change_1d")) else 0.0,
        change_5d=float(row["change_5d"]) if pd.notna(row.get("change_5d")) else 0.0,
        polarity=str(row["polarity"]),
    )
