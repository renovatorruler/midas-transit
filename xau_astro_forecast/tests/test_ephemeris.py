"""Tests for the ephemeris module."""

from datetime import date

import pytest

from xau_astro_forecast.modules.ephemeris import (
    BODY_NAMES,
    BodyPosition,
    compute_positions,
    date_to_jd,
    get_position,
)


class TestDateToJd:
    def test_known_date(self) -> None:
        """J2000.0 epoch: 2000-01-01 12:00 UTC = JD 2451545.0"""
        jd = date_to_jd(date(2000, 1, 1), hour=12.0)
        assert abs(jd - 2451545.0) < 0.001

    def test_default_hour(self) -> None:
        """Default hour should be 6.0 UTC."""
        jd = date_to_jd(date(2000, 1, 1))
        expected = date_to_jd(date(2000, 1, 1), hour=6.0)
        assert jd == expected


class TestComputePositions:
    def test_returns_all_bodies(self) -> None:
        """Should return positions for all 12 bodies by default."""
        positions = compute_positions(date(2024, 1, 1))
        assert len(positions) == len(BODY_NAMES)
        names = [p.name for p in positions]
        for body in BODY_NAMES:
            assert body in names

    def test_position_fields(self) -> None:
        """Each position should have longitude, speed, and declination."""
        positions = compute_positions(date(2024, 1, 1))
        for pos in positions:
            assert isinstance(pos, BodyPosition)
            assert 0 <= pos.longitude < 360
            assert isinstance(pos.speed, float)
            assert -90 <= pos.declination <= 90

    def test_specific_body(self) -> None:
        """Should be able to get a single body."""
        pos = get_position(date(2024, 1, 1), "Sun")
        assert pos.name == "Sun"
        # Sun on Jan 1 2024 should be around 280° (Capricorn)
        assert 275 < pos.longitude < 285

    def test_sun_j2000(self) -> None:
        """Sun at J2000 epoch should be around 280° (Capricorn)."""
        pos = get_position(date(2000, 1, 1), "Sun", hour_utc=12.0)
        assert 279 < pos.longitude < 282

    def test_moon_speed_reasonable(self) -> None:
        """Moon speed should be roughly 11-15 deg/day."""
        pos = get_position(date(2024, 6, 15), "Moon")
        assert 10 < abs(pos.speed) < 16

    def test_subset_bodies(self) -> None:
        """Should compute only requested bodies."""
        positions = compute_positions(date(2024, 1, 1), bodies=["Sun", "Moon"])
        assert len(positions) == 2

    def test_defaults_to_0600_utc(self) -> None:
        """Positions at default should match positions at 06:00 UTC explicitly."""
        pos_default = compute_positions(date(2024, 3, 20))
        pos_explicit = compute_positions(date(2024, 3, 20), hour_utc=6.0)
        for p1, p2 in zip(pos_default, pos_explicit):
            assert p1.longitude == p2.longitude
            assert p1.speed == p2.speed

    def test_natal_date(self) -> None:
        """Compute positions for the natal chart date 1974-12-31."""
        positions = compute_positions(date(1974, 12, 31), hour_utc=13.333)  # 08:20 EST = 13:20 UTC
        sun = next(p for p in positions if p.name == "Sun")
        # Sun in late Capricorn ~279°
        assert 278 < sun.longitude < 282
