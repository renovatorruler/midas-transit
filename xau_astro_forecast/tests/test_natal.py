"""Tests for natal chart module."""

import pytest
from xau_astro_forecast.modules.natal import (
    compute_natal_chart,
    clear_cache,
    load_natal_config,
    NatalChart,
)
from xau_astro_forecast.modules.ephemeris import BODY_NAMES


@pytest.fixture(autouse=True)
def _clear():
    clear_cache()
    yield
    clear_cache()


class TestNatalConfig:
    def test_load_config(self):
        config = load_natal_config()
        assert config["date"] == "1974-12-31"
        assert config["time"] == "08:20"
        assert config["timezone"] == "EST"
        assert config["utc_offset"] == -5
        assert config["location"]["latitude"] == 40.7128
        assert config["location"]["longitude"] == -74.0047

    def test_config_name(self):
        config = load_natal_config()
        assert "COMEX" in config["name"]


class TestNatalChart:
    def test_asc_within_tolerance(self):
        chart = compute_natal_chart()
        assert abs(chart.asc - 241.35) < 1.0, f"ASC {chart.asc} not within 1° of 241.35°"

    def test_mc_within_tolerance(self):
        chart = compute_natal_chart()
        assert abs(chart.mc - 166.87) < 1.0, f"MC {chart.mc} not within 1° of 166.87°"

    def test_all_planets_present(self):
        chart = compute_natal_chart()
        for name in BODY_NAMES:
            assert name in chart.planets, f"Missing planet: {name}"

    def test_planet_longitudes_valid(self):
        chart = compute_natal_chart()
        for name, pos in chart.planets.items():
            assert 0 <= pos.longitude < 360, f"{name} longitude {pos.longitude} out of range"

    def test_sun_in_capricorn(self):
        """1974-12-31 Sun should be in Capricorn (270-300°)."""
        chart = compute_natal_chart()
        sun = chart.planets["Sun"]
        assert 270 <= sun.longitude < 300, f"Sun at {sun.longitude}°, expected Capricorn"

    def test_chart_metadata(self):
        chart = compute_natal_chart()
        assert chart.date_str == "1974-12-31"
        assert chart.time_str == "08:20"
        assert chart.timezone == "EST"


class TestCaching:
    def test_cache_returns_same_object(self):
        chart1 = compute_natal_chart()
        chart2 = compute_natal_chart()
        assert chart1 is chart2

    def test_clear_cache_recomputes(self):
        chart1 = compute_natal_chart()
        clear_cache()
        chart2 = compute_natal_chart()
        assert chart1 is not chart2
        assert abs(chart1.asc - chart2.asc) < 0.001

    def test_no_cache_mode(self):
        chart1 = compute_natal_chart(use_cache=False)
        chart2 = compute_natal_chart(use_cache=False)
        assert chart1 is not chart2
