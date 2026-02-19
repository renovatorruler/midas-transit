"""Tests for direction module."""

import pytest
from xau_astro_forecast.modules.aspects import AspectInfo
from xau_astro_forecast.modules.price_analysis import PriceMetrics
from xau_astro_forecast.modules.direction import (
    DirectionResult, compute_direction, _aspect_direction_score,
    ASPECT_POLARITY, _get_weight,
)


def _make_aspect(
    body1: str = "Jupiter", body2: str = "Saturn",
    aspect_name: str = "trine", orb: float = 0.5,
    applying: bool = True, regime: str = "STRUCTURAL",
    pair_type: str = "transit-transit",
) -> AspectInfo:
    angle = {"conjunction": 0.0, "sextile": 60.0, "trine": 120.0,
             "square": 90.0, "opposition": 180.0, "semi-sextile": 30.0}
    return AspectInfo(
        body1=body1, body2=body2, aspect_name=aspect_name,
        aspect_angle=angle.get(aspect_name, 0.0), orb=orb,
        applying=applying, regime=regime, pair_type=pair_type,
    )


def _make_price(polarity: str = "HIGH", change_1d: float = 0.5) -> PriceMetrics:
    return PriceMetrics(
        date="2025-01-15", close=2650.0, close_pos60=80.0,
        close_pos20=75.0, low_pos60=70.0, change5=2.0,
        direction_1d="UP", change_1d=change_1d, change_5d=2.0,
        polarity=polarity,
    )


class TestDirectionScore:
    def test_trine_is_positive(self):
        a = _make_aspect(aspect_name="trine")
        assert _aspect_direction_score(a) > 0

    def test_square_is_negative(self):
        a = _make_aspect(aspect_name="square")
        assert _aspect_direction_score(a) < 0

    def test_opposition_is_negative(self):
        a = _make_aspect(aspect_name="opposition")
        assert _aspect_direction_score(a) < 0

    def test_sextile_is_positive(self):
        a = _make_aspect(aspect_name="sextile")
        assert _aspect_direction_score(a) > 0

    def test_conjunction_depends_on_planets(self):
        # Jupiter conjunction = bullish nature
        a = _make_aspect(body1="Jupiter", body2="Venus", aspect_name="conjunction")
        assert _aspect_direction_score(a) > 0
        # Saturn-Mars conjunction = bearish
        a2 = _make_aspect(body1="Saturn", body2="Mars", aspect_name="conjunction")
        assert _aspect_direction_score(a2) < 0

    def test_tighter_orb_stronger(self):
        tight = _make_aspect(orb=0.1)
        loose = _make_aspect(orb=0.9)
        assert abs(_aspect_direction_score(tight)) > abs(_aspect_direction_score(loose))

    def test_natal_prefix_stripped(self):
        w = _get_weight("N.Jupiter")
        assert w == _get_weight("Jupiter")


class TestComputeDirection:
    def test_no_aspects_neutral(self):
        result = compute_direction([])
        assert result.bias == "UP"
        assert result.probability == 50.0
        assert result.confirmation is False

    def test_bullish_aspects_up(self):
        aspects = [
            _make_aspect(aspect_name="trine", body1="Jupiter", body2="Venus"),
            _make_aspect(aspect_name="sextile", body1="Sun", body2="Moon"),
        ]
        result = compute_direction(aspects)
        assert result.bias == "UP"
        assert result.probability > 50.0

    def test_bearish_aspects_down(self):
        aspects = [
            _make_aspect(aspect_name="square", body1="Saturn", body2="Pluto"),
            _make_aspect(aspect_name="opposition", body1="Mars", body2="Saturn"),
            _make_aspect(aspect_name="square", body1="Uranus", body2="Pluto"),
        ]
        result = compute_direction(aspects)
        assert result.bias == "DOWN"
        assert result.probability > 50.0

    def test_probability_range(self):
        aspects = [_make_aspect(aspect_name="trine") for _ in range(10)]
        result = compute_direction(aspects)
        assert 50.0 <= result.probability <= 99.0

    def test_confirmation_when_aligned(self):
        aspects = [_make_aspect(aspect_name="trine", body1="Jupiter", body2="Venus")]
        price = _make_price(polarity="HIGH")
        result = compute_direction(aspects, price)
        assert result.bias == "UP"
        assert result.confirmation is True

    def test_no_confirmation_when_misaligned(self):
        aspects = [_make_aspect(aspect_name="trine", body1="Jupiter", body2="Venus")]
        price = _make_price(polarity="LOW")
        result = compute_direction(aspects, price)
        assert result.bias == "UP"
        assert result.confirmation is False

    def test_no_confirmation_mid_polarity(self):
        aspects = [_make_aspect(aspect_name="trine")]
        price = _make_price(polarity="MID")
        result = compute_direction(aspects, price)
        assert result.confirmation is False

    def test_detail_contains_counts(self):
        aspects = [
            _make_aspect(aspect_name="trine"),
            _make_aspect(aspect_name="square"),
        ]
        result = compute_direction(aspects)
        assert "bullish" in result.detail
        assert "bearish" in result.detail

    def test_result_dataclass_fields(self):
        result = compute_direction([])
        assert hasattr(result, "bias")
        assert hasattr(result, "probability")
        assert hasattr(result, "confirmation")
        assert hasattr(result, "astro_score")
        assert hasattr(result, "detail")
