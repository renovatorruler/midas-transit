"""Tests for the aspect engine module."""

import json
import os
import pytest
from typing import Dict

from xau_astro_forecast.modules.ephemeris import BodyPosition
from xau_astro_forecast.modules.aspects import (
    angular_separation,
    find_aspects_between,
    compute_transit_transit_aspects,
    compute_transit_natal_aspects,
    compute_transit_angle_aspects,
    compute_all_aspects,
    load_config,
    clear_config_cache,
    AspectInfo,
)


@pytest.fixture(autouse=True)
def reset_cache() -> None:
    clear_config_cache()


class TestAngularSeparation:
    def test_same_position(self) -> None:
        assert angular_separation(100.0, 100.0) == 0.0

    def test_opposition(self) -> None:
        assert angular_separation(0.0, 180.0) == 180.0

    def test_wrap_around(self) -> None:
        assert abs(angular_separation(350.0, 10.0) - 20.0) < 0.0001

    def test_square(self) -> None:
        assert angular_separation(0.0, 90.0) == 90.0

    def test_symmetric(self) -> None:
        assert angular_separation(30.0, 150.0) == angular_separation(150.0, 30.0)


class TestAspectDetection:
    def _make_body(self, name: str, lon: float, speed: float = 1.0) -> BodyPosition:
        return BodyPosition(name=name, longitude=lon, speed=speed, declination=0.0)

    def test_exact_conjunction(self) -> None:
        body1 = self._make_body("Sun", 100.0, speed=1.0)
        aspects = find_aspects_between(body1, "Moon", 100.0, 13.0, "transit-transit")
        names = [a.aspect_name for a in aspects]
        assert "conjunction" in names
        conj = [a for a in aspects if a.aspect_name == "conjunction"][0]
        assert conj.orb == 0.0

    def test_conjunction_within_orb(self) -> None:
        body1 = self._make_body("Sun", 100.0)
        aspects = find_aspects_between(body1, "Moon", 100.8, 13.0, "transit-transit")
        names = [a.aspect_name for a in aspects]
        assert "conjunction" in names

    def test_conjunction_outside_orb(self) -> None:
        body1 = self._make_body("Sun", 100.0)
        aspects = find_aspects_between(body1, "Moon", 101.5, 13.0, "transit-transit")
        names = [a.aspect_name for a in aspects]
        assert "conjunction" not in names

    def test_opposition_detected(self) -> None:
        body1 = self._make_body("Mars", 10.0, speed=0.5)
        aspects = find_aspects_between(body1, "Jupiter", 190.3, 0.08, "transit-transit")
        names = [a.aspect_name for a in aspects]
        assert "opposition" in names

    def test_square_detected(self) -> None:
        body1 = self._make_body("Venus", 45.0, speed=1.2)
        aspects = find_aspects_between(body1, "Saturn", 135.5, 0.03, "transit-transit")
        names = [a.aspect_name for a in aspects]
        assert "square" in names

    def test_trine_detected(self) -> None:
        body1 = self._make_body("Sun", 0.0, speed=1.0)
        aspects = find_aspects_between(body1, "Jupiter", 120.5, 0.08, "transit-transit")
        names = [a.aspect_name for a in aspects]
        assert "trine" in names

    def test_sextile_detected(self) -> None:
        body1 = self._make_body("Mercury", 30.0, speed=1.5)
        aspects = find_aspects_between(body1, "Venus", 90.7, 1.2, "transit-transit")
        names = [a.aspect_name for a in aspects]
        assert "sextile" in names

    def test_semi_sextile_detected(self) -> None:
        body1 = self._make_body("Sun", 0.0, speed=1.0)
        aspects = find_aspects_between(body1, "Mercury", 30.4, 1.5, "transit-transit")
        names = [a.aspect_name for a in aspects]
        assert "semi-sextile" in names


class TestOuterOuterOrb:
    def _make_body(self, name: str, lon: float, speed: float = 0.05) -> BodyPosition:
        return BodyPosition(name=name, longitude=lon, speed=speed, declination=0.0)

    def test_outer_outer_uses_reduced_orb(self) -> None:
        """Outer-outer pairs should use 0.5° orb, not 1.0°."""
        body1 = self._make_body("Jupiter", 100.0)
        # 0.7° orb - within 1.0 but outside 0.5
        aspects = find_aspects_between(body1, "Saturn", 100.7, 0.03, "transit-transit")
        names = [a.aspect_name for a in aspects]
        assert "conjunction" not in names

    def test_outer_outer_within_reduced_orb(self) -> None:
        body1 = self._make_body("Jupiter", 100.0)
        aspects = find_aspects_between(body1, "Saturn", 100.4, 0.03, "transit-transit")
        names = [a.aspect_name for a in aspects]
        assert "conjunction" in names

    def test_inner_outer_uses_full_orb(self) -> None:
        body1 = self._make_body("Sun", 100.0, speed=1.0)
        aspects = find_aspects_between(body1, "Jupiter", 100.8, 0.08, "transit-transit")
        names = [a.aspect_name for a in aspects]
        assert "conjunction" in names


class TestApplyingSeparating:
    def _make_body(self, name: str, lon: float, speed: float) -> BodyPosition:
        return BodyPosition(name=name, longitude=lon, speed=speed, declination=0.0)

    def test_applying_conjunction(self) -> None:
        """Faster body approaching slower body = applying."""
        body1 = self._make_body("Moon", 99.0, speed=13.0)
        aspects = find_aspects_between(body1, "Sun", 99.5, 1.0, "transit-transit")
        conj = [a for a in aspects if a.aspect_name == "conjunction"]
        assert len(conj) == 1
        assert conj[0].applying is True

    def test_separating_conjunction(self) -> None:
        """Faster body moving away = separating."""
        body1 = self._make_body("Moon", 100.5, speed=13.0)
        aspects = find_aspects_between(body1, "Sun", 100.0, 1.0, "transit-transit")
        conj = [a for a in aspects if a.aspect_name == "conjunction"]
        assert len(conj) == 1
        assert conj[0].applying is False


class TestRegimeClassification:
    def _make_body(self, name: str, lon: float, speed: float = 1.0) -> BodyPosition:
        return BodyPosition(name=name, longitude=lon, speed=speed, declination=0.0)

    def test_angle_aspect_is_active(self) -> None:
        body1 = self._make_body("Mars", 241.0, speed=0.5)
        aspects = find_aspects_between(body1, "N.ASC", 241.35, 0.0, "transit-angle")
        assert len(aspects) > 0
        assert all(a.regime == "ACTIVE" for a in aspects)

    def test_outer_outer_is_structural(self) -> None:
        body1 = self._make_body("Jupiter", 100.0, speed=0.08)
        aspects = find_aspects_between(body1, "Saturn", 100.3, 0.03, "transit-transit")
        assert len(aspects) > 0
        assert all(a.regime == "STRUCTURAL" for a in aspects)

    def test_outer_to_natal_is_structural(self) -> None:
        body1 = self._make_body("Pluto", 300.0, speed=0.01)
        aspects = find_aspects_between(body1, "N.Sun", 300.2, 0.0, "transit-natal")
        assert len(aspects) > 0
        assert all(a.regime == "STRUCTURAL" for a in aspects)

    def test_inner_inner_is_active(self) -> None:
        body1 = self._make_body("Sun", 100.0, speed=1.0)
        aspects = find_aspects_between(body1, "Mercury", 100.3, 1.5, "transit-transit")
        assert len(aspects) > 0
        assert all(a.regime == "ACTIVE" for a in aspects)


class TestTransitTransitAspects:
    def test_finds_multiple_aspects(self) -> None:
        positions = [
            BodyPosition("Sun", 100.0, 1.0, 0.0),
            BodyPosition("Moon", 100.5, 13.0, 0.0),
            BodyPosition("Mars", 280.3, 0.5, 0.0),
        ]
        aspects = compute_transit_transit_aspects(positions)
        # Sun-Moon conjunction, Sun-Mars opposition
        assert len(aspects) >= 2

    def test_no_duplicate_pairs(self) -> None:
        positions = [
            BodyPosition("Sun", 100.0, 1.0, 0.0),
            BodyPosition("Moon", 100.5, 13.0, 0.0),
        ]
        aspects = compute_transit_transit_aspects(positions)
        # Should only have Sun-Moon, not Moon-Sun
        pairs = [(a.body1, a.body2) for a in aspects]
        assert ("Moon", "Sun") not in pairs


class TestTransitNatalAspects:
    def test_finds_transit_natal(self) -> None:
        transits = [BodyPosition("Mars", 100.3, 0.5, 0.0)]
        natals = {"Sun": BodyPosition("Sun", 100.0, 1.0, 0.0)}
        aspects = compute_transit_natal_aspects(transits, natals)
        assert len(aspects) >= 1
        assert aspects[0].pair_type == "transit-natal"
        assert aspects[0].body2.startswith("N.")


class TestTransitAngleAspects:
    def test_finds_transit_to_asc(self) -> None:
        transits = [BodyPosition("Mars", 241.0, 0.5, 0.0)]
        aspects = compute_transit_angle_aspects(transits, asc=241.35, mc=166.87)
        asc_aspects = [a for a in aspects if a.body2 == "N.ASC"]
        assert len(asc_aspects) >= 1
        assert asc_aspects[0].regime == "ACTIVE"

    def test_finds_transit_to_mc(self) -> None:
        transits = [BodyPosition("Jupiter", 166.5, 0.08, 0.0)]
        aspects = compute_transit_angle_aspects(transits, asc=241.35, mc=166.87)
        mc_aspects = [a for a in aspects if a.body2 == "N.MC"]
        assert len(mc_aspects) >= 1


class TestComputeAllAspects:
    def test_combines_all_types(self) -> None:
        transits = [
            BodyPosition("Sun", 100.0, 1.0, 0.0),
            BodyPosition("Mars", 241.0, 0.5, 0.0),
        ]
        natals = {"Sun": BodyPosition("Sun", 100.3, 1.0, 0.0)}
        aspects = compute_all_aspects(transits, natals, asc=241.35, mc=166.87)
        pair_types = set(a.pair_type for a in aspects)
        # Should have at least transit-natal and transit-angle
        assert "transit-natal" in pair_types or "transit-angle" in pair_types


class TestConfigLoading:
    def test_config_has_six_aspects(self) -> None:
        config = load_config()
        assert len(config["aspects"]) == 6

    def test_config_has_correct_angles(self) -> None:
        config = load_config()
        expected = {"conjunction": 0, "semi-sextile": 30, "sextile": 60,
                    "square": 90, "trine": 120, "opposition": 180}
        for name, angle in expected.items():
            assert config["aspects"][name]["angle"] == angle

    def test_config_has_outer_planets(self) -> None:
        config = load_config()
        assert "Jupiter" in config["outer_planets"]
        assert "Pluto" in config["outer_planets"]

    def test_outer_outer_orb_is_half(self) -> None:
        config = load_config()
        assert config["outer_outer_orb"] == 0.5
