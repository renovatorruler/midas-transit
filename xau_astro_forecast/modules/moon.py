"""Moon phase module - computes Sun-Moon elongation and classifies into 8 phases."""

from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional, Tuple

from .ephemeris import compute_positions


@dataclass
class MoonPhaseResult:
    """Result of moon phase computation."""
    elongation: float  # Sun-Moon elongation in degrees (0-360)
    phase_name: str  # e.g. "Waxing Crescent"
    phase_number: int  # 0-7
    trading_interpretation: str


# 8 moon phases with degree ranges and trading interpretations
MOON_PHASES: List[Tuple[str, float, float, str]] = [
    ("New Moon", 0.0, 45.0,
     "Initiation - new positions, fresh entries, seed phase for trends"),
    ("Waxing Crescent", 45.0, 90.0,
     "Building momentum - add to positions, early trend confirmation"),
    ("First Quarter", 90.0, 135.0,
     "Decision point - tension builds, breakout or reversal likely"),
    ("Waxing Gibbous", 135.0, 180.0,
     "Refinement - trend matures, tighten stops, prepare for climax"),
    ("Full Moon", 180.0, 225.0,
     "Culmination - peak volatility, take profits, reversal window"),
    ("Waning Gibbous", 225.0, 270.0,
     "Distribution - reduce exposure, lock in gains, fading momentum"),
    ("Last Quarter", 270.0, 315.0,
     "Reassessment - counter-trend setups, mean reversion plays"),
    ("Waning Crescent", 315.0, 360.0,
     "Release - close positions, prepare for next cycle, low activity"),
]


def compute_elongation(sun_lon: float, moon_lon: float) -> float:
    """Compute Sun-Moon elongation (0-360 degrees).

    Elongation is the Moon's angular distance ahead of the Sun,
    measured in the direction of increasing longitude.
    """
    elong = (moon_lon - sun_lon) % 360.0
    return elong


def classify_phase(elongation: float) -> Tuple[str, int, str]:
    """Classify moon phase from elongation angle.

    Returns (phase_name, phase_number, trading_interpretation).
    """
    elong = elongation % 360.0
    for i, (name, start, end, interp) in enumerate(MOON_PHASES):
        if start <= elong < end:
            return name, i, interp
    # Edge case: exactly 360 wraps to New Moon
    return MOON_PHASES[0][0], 0, MOON_PHASES[0][3]


def get_moon_phase(target_date: Optional[date] = None) -> MoonPhaseResult:
    """Compute moon phase for a given date.

    Uses ephemeris module to get Sun and Moon positions at 06:00 UTC.
    """
    if target_date is None:
        from datetime import date as date_cls
        target_date = date_cls.today()
    positions = compute_positions(target_date)
    pos_by_name = {p.name: p for p in positions}
    sun_lon = pos_by_name["Sun"].longitude
    moon_lon = pos_by_name["Moon"].longitude

    elongation = compute_elongation(sun_lon, moon_lon)
    phase_name, phase_number, interpretation = classify_phase(elongation)

    return MoonPhaseResult(
        elongation=elongation,
        phase_name=phase_name,
        phase_number=phase_number,
        trading_interpretation=interpretation,
    )


def get_all_phase_interpretations() -> Dict[str, str]:
    """Return all phase names mapped to their trading interpretations."""
    return {name: interp for name, _, _, interp in MOON_PHASES}
