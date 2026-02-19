"""Tests for signal module."""

import pytest
from xau_astro_forecast.modules.direction import DirectionResult
from xau_astro_forecast.modules.scoring import ScoringResult
from xau_astro_forecast.modules.price_analysis import PriceMetrics
from xau_astro_forecast.modules.signal import (
    SignalResult, generate_signal, _compute_position_size, _compute_risk_level,
)


def _make_direction(
    bias: str = "UP", probability: float = 70.0, confirmation: bool = False,
    astro_score: float = 5.0,
) -> DirectionResult:
    return DirectionResult(
        bias=bias, probability=probability, confirmation=confirmation,
        astro_score=astro_score, detail="test",
    )


def _make_scoring(
    score: float = 6.0, phase: str = "MODERATE", state: str = "BUILDING",
    context: str = "PRE-EVENT TENSION",
) -> ScoringResult:
    return ScoringResult(
        score=score, phase=phase, state=state, context=context,
        raw_score=15.0, aspect_count=5,
    )


def _make_price(polarity: str = "MID", change_1d: float = 0.3) -> PriceMetrics:
    return PriceMetrics(
        date="2025-01-15", close=2650.0, close_pos60=50.0,
        close_pos20=50.0, low_pos60=50.0, change5=1.0,
        direction_1d="UP", change_1d=change_1d, change_5d=1.0,
        polarity=polarity,
    )


class TestGenerateSignal:
    def test_long_signal_up_bias(self):
        d = _make_direction(bias="UP", probability=70.0)
        s = _make_scoring(score=6.0)
        result = generate_signal(d, s)
        assert result.signal == "LONG"

    def test_short_signal_down_bias(self):
        d = _make_direction(bias="DOWN", probability=70.0)
        s = _make_scoring(score=6.0)
        result = generate_signal(d, s)
        assert result.signal == "SHORT"

    def test_neutral_low_probability(self):
        d = _make_direction(bias="UP", probability=52.0)
        s = _make_scoring(score=6.0)
        result = generate_signal(d, s)
        assert result.signal == "NEUTRAL"

    def test_neutral_low_score(self):
        d = _make_direction(bias="UP", probability=70.0)
        s = _make_scoring(score=1.5)
        result = generate_signal(d, s)
        assert result.signal == "NEUTRAL"

    def test_neutral_contradicting_price(self):
        d = _make_direction(bias="UP", probability=70.0, confirmation=False)
        s = _make_scoring(score=6.0)
        p = _make_price(polarity="LOW", change_1d=-2.0)
        result = generate_signal(d, s, p)
        assert result.signal == "NEUTRAL"

    def test_long_with_confirming_price(self):
        d = _make_direction(bias="UP", probability=70.0, confirmation=True)
        s = _make_scoring(score=6.0)
        p = _make_price(polarity="HIGH", change_1d=1.5)
        result = generate_signal(d, s, p)
        assert result.signal == "LONG"

    def test_neutral_position_size_zero(self):
        d = _make_direction(probability=52.0)
        s = _make_scoring(score=1.5)
        result = generate_signal(d, s)
        assert result.position_size == 0

    def test_position_size_range(self):
        d = _make_direction(probability=80.0, confirmation=True)
        s = _make_scoring(score=8.0)
        result = generate_signal(d, s)
        assert 0 <= result.position_size <= 100

    def test_strategy_not_empty(self):
        d = _make_direction()
        s = _make_scoring()
        result = generate_signal(d, s)
        assert len(result.strategy) > 0

    def test_invalidation_not_empty(self):
        d = _make_direction()
        s = _make_scoring()
        result = generate_signal(d, s)
        assert len(result.invalidation) > 0

    def test_neutral_invalidation(self):
        d = _make_direction(probability=52.0)
        s = _make_scoring(score=1.5)
        result = generate_signal(d, s)
        assert "N/A" in result.invalidation


class TestRiskLevel:
    def test_high_risk_high_score(self):
        s = _make_scoring(score=8.0, phase="HIGH PRESSURE")
        d = _make_direction()
        assert _compute_risk_level(s, d) == "HIGH"

    def test_medium_risk(self):
        s = _make_scoring(score=5.0, phase="MODERATE")
        d = _make_direction(probability=66.0)
        assert _compute_risk_level(s, d) == "MEDIUM"

    def test_low_risk(self):
        s = _make_scoring(score=2.5, phase="LOW")
        d = _make_direction(probability=55.0)
        assert _compute_risk_level(s, d) == "LOW"


class TestPositionSize:
    def test_higher_probability_larger_size(self):
        s = _make_scoring(score=6.0)
        d_high = _make_direction(probability=85.0)
        d_low = _make_direction(probability=60.0)
        assert _compute_position_size(d_high, s) > _compute_position_size(d_low, s)

    def test_confirmation_boosts_size(self):
        s = _make_scoring(score=6.0)
        d_conf = _make_direction(probability=70.0, confirmation=True)
        d_no = _make_direction(probability=70.0, confirmation=False)
        assert _compute_position_size(d_conf, s) >= _compute_position_size(d_no, s)

    def test_size_capped_at_100(self):
        s = _make_scoring(score=10.0)
        d = _make_direction(probability=99.0, confirmation=True)
        assert _compute_position_size(d, s) <= 100


class TestSignalResultFields:
    def test_all_fields_present(self):
        result = generate_signal(_make_direction(), _make_scoring())
        assert hasattr(result, "signal")
        assert hasattr(result, "risk_level")
        assert hasattr(result, "position_size")
        assert hasattr(result, "strategy")
        assert hasattr(result, "invalidation")

    def test_signal_values(self):
        for bias, prob, score_val, expected in [
            ("UP", 70.0, 6.0, "LONG"),
            ("DOWN", 70.0, 6.0, "SHORT"),
            ("UP", 52.0, 6.0, "NEUTRAL"),
        ]:
            d = _make_direction(bias=bias, probability=prob)
            s = _make_scoring(score=score_val)
            assert generate_signal(d, s).signal == expected

    def test_risk_values_valid(self):
        d = _make_direction()
        s = _make_scoring()
        result = generate_signal(d, s)
        assert result.risk_level in ("LOW", "MEDIUM", "HIGH")
