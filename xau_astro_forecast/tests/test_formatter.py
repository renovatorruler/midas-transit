"""Tests for the formatter module."""

import pytest
from typing import Dict, List

from xau_astro_forecast.modules.ephemeris import BodyPosition
from xau_astro_forecast.modules.aspects import AspectInfo
from xau_astro_forecast.modules.moon import MoonPhaseResult
from xau_astro_forecast.modules.price_analysis import PriceMetrics
from xau_astro_forecast.modules.scoring import ScoringResult
from xau_astro_forecast.modules.direction import DirectionResult
from xau_astro_forecast.modules.signal import SignalResult
from xau_astro_forecast.modules.formatter import render_report_to_string, _split_aspects


# --- Fixtures ---

BODIES = [
    "Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter",
    "Saturn", "Uranus", "Neptune", "Pluto", "True Node", "Mean Node", "Chiron"
]


def _make_positions() -> Dict[str, BodyPosition]:
    return {name: BodyPosition(name=name, longitude=i * 30.0, speed=1.0 - i * 0.1, declination=10.0 - i)
            for i, name in enumerate(BODIES)}


def _make_aspects() -> List[AspectInfo]:
    return [
        AspectInfo(body1="Saturn", body2="N.Pluto", aspect_name="conjunction",
                   aspect_angle=0.0, orb=0.3, applying=True, regime="STRUCTURAL", pair_type="transit-natal"),
        AspectInfo(body1="Jupiter", body2="N.Neptune", aspect_name="square",
                   aspect_angle=90.0, orb=0.8, applying=False, regime="STRUCTURAL", pair_type="transit-natal"),
        AspectInfo(body1="Mars", body2="N.ASC", aspect_name="trine",
                   aspect_angle=120.0, orb=0.5, applying=True, regime="ACTIVE", pair_type="transit-angle"),
        AspectInfo(body1="Sun", body2="Moon", aspect_name="sextile",
                   aspect_angle=60.0, orb=0.2, applying=True, regime="ACTIVE", pair_type="transit-transit"),
    ]


def _make_moon() -> MoonPhaseResult:
    return MoonPhaseResult(elongation=135.5, phase_name="Waxing Gibbous",
                           phase_number=3, trading_interpretation="Refinement - trend matures")


def _make_price() -> PriceMetrics:
    return PriceMetrics(date="2025-01-15", close=2650.50, close_pos60=75.0,
                        close_pos20=80.0, low_pos60=60.0, change5=2.5,
                        direction_1d="UP", change_1d=0.8, change_5d=2.5, polarity="HIGH")


def _make_scoring() -> ScoringResult:
    return ScoringResult(score=7.5, phase="HIGH PRESSURE", state="BUILDING",
                         context="PRE-EVENT TENSION", raw_score=15.3, aspect_count=4)


def _make_direction() -> DirectionResult:
    return DirectionResult(bias="UP", probability=72.5, confirmation=True,
                           astro_score=3.2, detail="Strong bullish pressure from outer aspects")


def _make_signal() -> SignalResult:
    return SignalResult(signal="LONG", risk_level="MEDIUM", position_size=65,
                        strategy="Buy on dips with trend confirmation",
                        invalidation="Close below 2600")


def _render_full() -> str:
    return render_report_to_string(
        report_date="2025-01-15",
        positions=_make_positions(),
        aspects=_make_aspects(),
        moon=_make_moon(),
        price=_make_price(),
        scoring=_make_scoring(),
        direction=_make_direction(),
        signal=_make_signal(),
    )


# --- Tests ---

class TestFormatterSections:
    """Verify all V3.5 report sections are present."""

    def test_header_present(self) -> None:
        output = _render_full()
        assert "MIDAS TRANSIT SYSTEM" in output
        assert "2025-01-15" in output

    def test_ephemeris_table_present(self) -> None:
        output = _render_full()
        assert "Ephemeris Positions" in output
        for body in BODIES:
            assert body in output

    def test_ephemeris_shows_lon_speed_decl(self) -> None:
        output = _render_full()
        # Sun at 0.0°
        assert "0.0000" in output
        # Speed and declination columns exist
        assert "Speed" in output
        assert "Declination" in output

    def test_outer_pressure_drivers_present(self) -> None:
        output = _render_full()
        assert "Outer Pressure Drivers" in output
        assert "Saturn" in output
        assert "N.Pluto" in output

    def test_angle_activations_present(self) -> None:
        output = _render_full()
        assert "Angle Activations" in output
        assert "N.ASC" in output

    def test_moon_phase_present(self) -> None:
        output = _render_full()
        assert "Moon Phase" in output
        assert "Waxing Gibbous" in output
        assert "135.50" in output

    def test_price_metrics_present(self) -> None:
        output = _render_full()
        assert "Price Metrics" in output
        assert "2650.50" in output
        assert "75.0" in output

    def test_scoring_summary_present(self) -> None:
        output = _render_full()
        assert "Scoring Summary" in output
        assert "7.5" in output
        assert "HIGH PRESSURE" in output
        assert "BUILDING" in output

    def test_direction_bias_present(self) -> None:
        output = _render_full()
        assert "Direction Bias" in output
        assert "UP" in output
        assert "72.5" in output
        assert "CONFIRMED" in output

    def test_trading_signal_present(self) -> None:
        output = _render_full()
        assert "Trading Signal" in output
        assert "LONG" in output
        assert "MEDIUM" in output
        assert "65%" in output

    def test_price_none_handled(self) -> None:
        output = render_report_to_string(
            report_date="2025-01-15",
            positions=_make_positions(),
            aspects=_make_aspects(),
            moon=_make_moon(),
            price=None,
            scoring=_make_scoring(),
            direction=_make_direction(),
            signal=_make_signal(),
        )
        assert "Price data unavailable" in output

    def test_empty_aspects(self) -> None:
        output = render_report_to_string(
            report_date="2025-01-15",
            positions=_make_positions(),
            aspects=[],
            moon=_make_moon(),
            price=_make_price(),
            scoring=_make_scoring(),
            direction=_make_direction(),
            signal=_make_signal(),
        )
        assert "No outer pressure aspects" in output
        assert "No angle activations" in output


class TestSplitAspects:
    """Test aspect splitting logic."""

    def test_splits_by_regime(self) -> None:
        aspects = _make_aspects()
        outer, angles = _split_aspects(aspects)
        assert len(outer) == 2
        assert len(angles) == 2
        assert all(a.regime == "STRUCTURAL" for a in outer)
        assert all(a.regime == "ACTIVE" for a in angles)

    def test_empty_list(self) -> None:
        outer, angles = _split_aspects([])
        assert outer == []
        assert angles == []


class TestSignalVariants:
    """Test different signal types render correctly."""

    def test_short_signal(self) -> None:
        sig = SignalResult(signal="SHORT", risk_level="HIGH", position_size=30,
                           strategy="Sell rallies", invalidation="Close above 2700")
        output = render_report_to_string(
            report_date="2025-01-15",
            positions=_make_positions(),
            aspects=_make_aspects(),
            moon=_make_moon(),
            price=_make_price(),
            scoring=_make_scoring(),
            direction=DirectionResult(bias="DOWN", probability=68.0, confirmation=False,
                                      astro_score=-2.0, detail="Bearish pressure"),
            signal=sig,
        )
        assert "SHORT" in output
        assert "DOWN" in output
        assert "Unconfirmed" in output

    def test_neutral_signal(self) -> None:
        sig = SignalResult(signal="NEUTRAL", risk_level="LOW", position_size=0,
                           strategy="Stay flat", invalidation="N/A")
        output = render_report_to_string(
            report_date="2025-01-15",
            positions=_make_positions(),
            aspects=[],
            moon=_make_moon(),
            price=None,
            scoring=ScoringResult(score=2.0, phase="MINIMAL", state="EASING",
                                  context="QUIET PERIOD", raw_score=1.0, aspect_count=0),
            direction=DirectionResult(bias="UP", probability=51.0, confirmation=False,
                                      astro_score=0.1, detail="No clear signal"),
            signal=sig,
        )
        assert "NEUTRAL" in output
