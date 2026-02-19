"""Tests for price analysis module."""

import os
import pandas as pd
import pytest

from xau_astro_forecast.modules.price_analysis import (
    PriceMetrics,
    classify_polarity,
    compute_metrics,
    get_metrics_for_date,
    load_prices,
)

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
CSV_PATH = os.path.join(DATA_DIR, "xau_prices.csv")


class TestLoadPrices:
    def test_loads_csv(self) -> None:
        df = load_prices(CSV_PATH)
        assert len(df) >= 100
        assert "date" in df.columns
        assert "open" in df.columns
        assert "high" in df.columns
        assert "low" in df.columns
        assert "close" in df.columns
        assert "volume" in df.columns

    def test_sorted_by_date(self) -> None:
        df = load_prices(CSV_PATH)
        dates = df["date"].tolist()
        assert dates == sorted(dates)


class TestComputeMetrics:
    def test_has_expected_columns(self) -> None:
        df = load_prices(CSV_PATH)
        result = compute_metrics(df)
        for col in ["close_pos60", "close_pos20", "low_pos60", "change5", "change_1d", "direction_1d", "polarity"]:
            assert col in result.columns

    def test_percentile_range(self) -> None:
        df = load_prices(CSV_PATH)
        result = compute_metrics(df)
        valid = result["close_pos60"].dropna()
        assert (valid >= 0).all()
        assert (valid <= 100).all()

    def test_change5_computed(self) -> None:
        df = load_prices(CSV_PATH)
        result = compute_metrics(df)
        # Row 5 should have a change5 value
        row5 = result.iloc[5]
        expected = (df.iloc[5]["close"] / df.iloc[0]["close"] - 1) * 100
        assert abs(row5["change5"] - expected) < 0.01

    def test_direction_1d(self) -> None:
        df = load_prices(CSV_PATH)
        result = compute_metrics(df)
        valid = result[result["direction_1d"].isin(["UP", "DOWN"])]
        assert len(valid) > 0

    def test_change_5d_equals_change5(self) -> None:
        df = load_prices(CSV_PATH)
        result = compute_metrics(df)
        valid = result.dropna(subset=["change5", "change_5d"])
        assert (valid["change5"] == valid["change_5d"]).all()


class TestClassifyPolarity:
    def test_high(self) -> None:
        assert classify_polarity(80.0) == "HIGH"

    def test_low(self) -> None:
        assert classify_polarity(20.0) == "LOW"

    def test_mid(self) -> None:
        assert classify_polarity(50.0) == "MID"

    def test_boundary_high(self) -> None:
        assert classify_polarity(75.0) == "MID"  # not strictly >75

    def test_boundary_low(self) -> None:
        assert classify_polarity(25.0) == "MID"  # not strictly <25


class TestGetMetricsForDate:
    def test_returns_metrics(self) -> None:
        df = load_prices(CSV_PATH)
        # Use a date well into the series (row 70+)
        date_str = df.iloc[70]["date"].strftime("%Y-%m-%d")
        metrics = get_metrics_for_date(df, date_str)
        assert metrics is not None
        assert isinstance(metrics, PriceMetrics)
        assert metrics.polarity in ("HIGH", "MID", "LOW")
        assert metrics.direction_1d in ("UP", "DOWN")

    def test_returns_none_for_missing_date(self) -> None:
        df = load_prices(CSV_PATH)
        assert get_metrics_for_date(df, "1999-01-01") is None

    def test_percentile_values_reasonable(self) -> None:
        df = load_prices(CSV_PATH)
        date_str = df.iloc[80]["date"].strftime("%Y-%m-%d")
        metrics = get_metrics_for_date(df, date_str)
        assert metrics is not None
        assert 0 <= metrics.close_pos60 <= 100
        assert 0 <= metrics.close_pos20 <= 100
        assert 0 <= metrics.low_pos60 <= 100
