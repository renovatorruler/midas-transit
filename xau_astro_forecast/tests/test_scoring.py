"""Tests for the scoring module."""

import json
import os
import pytest
from xau_astro_forecast.modules.aspects import AspectInfo
from xau_astro_forecast.modules.scoring import (
    score_aspects,
    classify_phase,
    classify_state,
    classify_context,
    compute_pressure_score,
    load_config,
    _normalize_score,
)


def _make_aspect(
    body1: str = "Jupiter",
    body2: str = "Saturn",
    aspect_name: str = "conjunction",
    orb: float = 0.5,
    applying: bool = True,
    regime: str = "STRUCTURAL",
    pair_type: str = "transit-transit",
) -> AspectInfo:
    return AspectInfo(
        body1=body1,
        body2=body2,
        aspect_name=aspect_name,
        aspect_angle=0.0,
        orb=orb,
        applying=applying,
        regime=regime,
        pair_type=pair_type,
    )


class TestScoringConfig:
    def test_config_loads(self):
        config = load_config()
        assert "planet_weights" in config
        assert "aspect_type_multipliers" in config

    def test_outer_planets_heavier(self):
        config = load_config()
        pw = config["planet_weights"]
        assert pw["Pluto"] > pw["Mercury"]
        assert pw["Neptune"] > pw["Venus"]
        assert pw["Uranus"] > pw["Mars"]
        assert pw["Saturn"] > pw["Mercury"]


class TestPressureScore:
    def test_empty_aspects_returns_zero(self):
        assert compute_pressure_score([]) == 0.0

    def test_single_tight_aspect_scores_positive(self):
        aspects = [_make_aspect(orb=0.1)]
        score = compute_pressure_score(aspects)
        assert score > 0

    def test_tighter_orb_scores_higher(self):
        tight = compute_pressure_score([_make_aspect(orb=0.1)])
        wide = compute_pressure_score([_make_aspect(orb=0.9)])
        assert tight > wide

    def test_outer_planets_score_higher(self):
        outer = compute_pressure_score([_make_aspect(body1="Pluto", body2="Neptune", orb=0.3)])
        inner = compute_pressure_score([_make_aspect(body1="Mercury", body2="Venus", orb=0.3)])
        assert outer > inner

    def test_conjunction_scores_higher_than_sextile(self):
        conj = compute_pressure_score([_make_aspect(aspect_name="conjunction", orb=0.3)])
        sext = compute_pressure_score([_make_aspect(aspect_name="sextile", orb=0.3)])
        assert conj > sext

    def test_more_aspects_higher_score(self):
        one = compute_pressure_score([_make_aspect()])
        three = compute_pressure_score([_make_aspect(), _make_aspect(), _make_aspect()])
        assert three > one


class TestNormalizeScore:
    def test_zero_aspects_returns_one(self):
        assert _normalize_score(0.0, 0) == 1.0

    def test_score_in_range(self):
        for raw in [0, 5, 15, 50, 100]:
            s = _normalize_score(raw, 3)
            assert 1.0 <= s <= 10.0


class TestClassifyPhase:
    def test_extreme_pressure(self):
        assert classify_phase(9.0) == "EXTREME PRESSURE"

    def test_high_pressure(self):
        assert classify_phase(7.0) == "HIGH PRESSURE"

    def test_moderate(self):
        assert classify_phase(5.0) == "MODERATE"

    def test_low(self):
        assert classify_phase(3.0) == "LOW"

    def test_minimal(self):
        assert classify_phase(1.5) == "MINIMAL"


class TestClassifyState:
    def test_empty_returns_easing(self):
        assert classify_state([]) == "EASING"

    def test_all_applying_returns_building(self):
        aspects = [_make_aspect(applying=True) for _ in range(5)]
        assert classify_state(aspects) == "BUILDING"

    def test_mostly_separating_returns_peak(self):
        aspects = [_make_aspect(applying=False) for _ in range(5)]
        assert classify_state(aspects) == "PEAK"

    def test_mixed_near_peak(self):
        aspects = [_make_aspect(applying=True), _make_aspect(applying=False), _make_aspect(applying=False)]
        state = classify_state(aspects)
        assert state == "PEAK"


class TestClassifyContext:
    def test_empty_quiet_period(self):
        assert classify_context([], "EASING") == "QUIET PERIOD"

    def test_peak_tight_activation_window(self):
        aspects = [_make_aspect(orb=0.1)]
        assert classify_context(aspects, "PEAK") == "ACTIVATION WINDOW"

    def test_building_many_pre_event(self):
        aspects = [_make_aspect() for _ in range(6)]
        assert classify_context(aspects, "BUILDING") == "PRE-EVENT TENSION"

    def test_peak_no_tight_post_event(self):
        aspects = [_make_aspect(orb=0.8)]
        assert classify_context(aspects, "PEAK") == "POST-EVENT REBALANCE"

    def test_few_aspects_quiet(self):
        aspects = [_make_aspect()]
        assert classify_context(aspects, "BUILDING") == "QUIET PERIOD"


class TestScoreAspects:
    def test_returns_scoring_result(self):
        aspects = [_make_aspect()]
        result = score_aspects(aspects)
        assert 1.0 <= result.score <= 10.0
        assert result.phase in ["EXTREME PRESSURE", "HIGH PRESSURE", "MODERATE", "LOW", "MINIMAL"]
        assert result.state in ["EASING", "BUILDING", "PEAK"]
        assert result.context in ["POST-EVENT REBALANCE", "PRE-EVENT TENSION", "ACTIVATION WINDOW", "QUIET PERIOD"]
        assert result.aspect_count == 1
        assert result.raw_score >= 0

    def test_many_tight_outer_aspects_high_score(self):
        aspects = [
            _make_aspect(body1="Pluto", body2="N.ASC", orb=0.1, applying=False),
            _make_aspect(body1="Neptune", body2="N.MC", orb=0.2, applying=False),
            _make_aspect(body1="Uranus", body2="Saturn", orb=0.1, applying=False),
            _make_aspect(body1="Jupiter", body2="Pluto", orb=0.3, applying=True),
            _make_aspect(body1="Saturn", body2="Neptune", orb=0.15, applying=False),
        ]
        result = score_aspects(aspects)
        assert result.score >= 6.0
        assert result.phase in ["EXTREME PRESSURE", "HIGH PRESSURE"]

    def test_single_wide_inner_aspect_low_score(self):
        aspects = [_make_aspect(body1="Mercury", body2="Venus", aspect_name="semi-sextile", orb=0.9)]
        result = score_aspects(aspects)
        assert result.score <= 4.0

    def test_no_aspects(self):
        result = score_aspects([])
        assert result.score == 1.0
        assert result.phase == "MINIMAL"
        assert result.aspect_count == 0
