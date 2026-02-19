"""Tests for moon phase module."""

from datetime import date

import pytest

from xau_astro_forecast.modules.moon import (
    MoonPhaseResult,
    classify_phase,
    compute_elongation,
    get_all_phase_interpretations,
    get_moon_phase,
    MOON_PHASES,
)


class TestComputeElongation:
    """Tests for Sun-Moon elongation computation."""

    def test_same_position(self) -> None:
        assert compute_elongation(100.0, 100.0) == 0.0

    def test_moon_ahead(self) -> None:
        assert compute_elongation(100.0, 190.0) == 90.0

    def test_moon_behind_wraps(self) -> None:
        # Moon at 10°, Sun at 350° -> elongation = 20°
        result = compute_elongation(350.0, 10.0)
        assert abs(result - 20.0) < 0.001

    def test_full_moon_elongation(self) -> None:
        assert compute_elongation(0.0, 180.0) == 180.0

    def test_negative_wrap(self) -> None:
        # Moon at 5°, Sun at 10° -> 355°
        result = compute_elongation(10.0, 5.0)
        assert abs(result - 355.0) < 0.001


class TestClassifyPhase:
    """Tests for phase classification from elongation."""

    def test_new_moon(self) -> None:
        name, num, interp = classify_phase(0.0)
        assert name == "New Moon"
        assert num == 0

    def test_first_quarter(self) -> None:
        name, num, _ = classify_phase(90.0)
        assert name == "First Quarter"
        assert num == 2

    def test_full_moon(self) -> None:
        name, num, _ = classify_phase(180.0)
        assert name == "Full Moon"
        assert num == 4

    def test_last_quarter(self) -> None:
        name, num, _ = classify_phase(270.0)
        assert name == "Last Quarter"
        assert num == 6

    def test_waxing_crescent(self) -> None:
        name, num, _ = classify_phase(60.0)
        assert name == "Waxing Crescent"
        assert num == 1

    def test_waning_crescent(self) -> None:
        name, num, _ = classify_phase(330.0)
        assert name == "Waning Crescent"
        assert num == 7

    def test_all_phases_have_interpretations(self) -> None:
        for elong in [10, 60, 100, 150, 200, 250, 280, 330]:
            _, _, interp = classify_phase(float(elong))
            assert len(interp) > 0

    def test_exact_360_wraps(self) -> None:
        name, num, _ = classify_phase(360.0)
        assert name == "New Moon"


class TestGetMoonPhase:
    """Tests using actual ephemeris for known dates."""

    def test_returns_moon_phase_result(self) -> None:
        result = get_moon_phase(date(2024, 1, 11))
        assert isinstance(result, MoonPhaseResult)
        assert 0.0 <= result.elongation < 360.0
        assert result.phase_name in [p[0] for p in MOON_PHASES]

    def test_new_moon_jan_2024(self) -> None:
        # New Moon was Jan 11 evening UTC; at 06:00 UTC Jan 12 elongation ~10°
        result = get_moon_phase(date(2024, 1, 12))
        assert result.phase_name == "New Moon"

    def test_full_moon_jan_2024(self) -> None:
        # Full Moon was Jan 25 evening UTC; at 06:00 UTC Jan 26 elongation ~186°
        result = get_moon_phase(date(2024, 1, 26))
        assert result.phase_name == "Full Moon"

    def test_first_quarter_jan_2024(self) -> None:
        # Jan 18, 2024 was First Quarter
        result = get_moon_phase(date(2024, 1, 18))
        assert result.phase_name in ("First Quarter", "Waxing Gibbous")

    def test_last_quarter_feb_2024(self) -> None:
        # Feb 2, 2024 was Last Quarter
        result = get_moon_phase(date(2024, 2, 2))
        assert result.phase_name in ("Last Quarter", "Waning Gibbous", "Waning Crescent")


class TestGetAllPhaseInterpretations:
    """Tests for phase interpretation lookup."""

    def test_returns_8_phases(self) -> None:
        interps = get_all_phase_interpretations()
        assert len(interps) == 8

    def test_all_phases_present(self) -> None:
        interps = get_all_phase_interpretations()
        expected = ["New Moon", "Waxing Crescent", "First Quarter", "Waxing Gibbous",
                    "Full Moon", "Waning Gibbous", "Last Quarter", "Waning Crescent"]
        for name in expected:
            assert name in interps
