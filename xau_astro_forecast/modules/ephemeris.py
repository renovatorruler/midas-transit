"""Ephemeris module - pyswisseph wrapper for celestial body positions."""

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Dict, List, Optional

import swisseph as swe


# Planet constants mapping name -> swisseph ID
PLANETS: Dict[str, int] = {
    "Sun": swe.SUN,
    "Moon": swe.MOON,
    "Mercury": swe.MERCURY,
    "Venus": swe.VENUS,
    "Mars": swe.MARS,
    "Jupiter": swe.JUPITER,
    "Saturn": swe.SATURN,
    "Uranus": swe.URANUS,
    "Neptune": swe.NEPTUNE,
    "Pluto": swe.PLUTO,
    "True Node": swe.TRUE_NODE,
    "Mean Node": swe.MEAN_NODE,
    "Chiron": swe.CHIRON,
}

# All 13 bodies requested by spec (excluding Chiron, using the 12 listed + Mean Node = 12)
# Spec says: Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto, True Node, Mean Node
# That's 12 bodies. We include all.
BODY_NAMES: List[str] = [
    "Sun", "Moon", "Mercury", "Venus", "Mars",
    "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto",
    "True Node", "Mean Node",
]

DEFAULT_HOUR_UTC = 6  # Default computation time: 06:00 UTC


@dataclass
class BodyPosition:
    """Position data for a celestial body."""
    name: str
    longitude: float       # degrees 0-360
    speed: float           # degrees per day
    declination: float     # degrees


def date_to_jd(d: date, hour: float = DEFAULT_HOUR_UTC) -> float:
    """Convert a date to Julian Day number at the given UTC hour."""
    return float(swe.julday(d.year, d.month, d.day, hour))


def compute_positions(
    target_date: date,
    hour_utc: float = DEFAULT_HOUR_UTC,
    bodies: Optional[List[str]] = None,
) -> List[BodyPosition]:
    """Compute positions for all requested bodies at the given date and time.

    Args:
        target_date: The date to compute positions for.
        hour_utc: Hour in UTC (default 6.0 for 06:00 UTC).
        bodies: List of body names to compute. Defaults to all BODY_NAMES.

    Returns:
        List of BodyPosition objects with longitude, speed, and declination.
    """
    if bodies is None:
        bodies = BODY_NAMES

    jd = date_to_jd(target_date, hour_utc)
    flags = swe.FLG_SWIEPH | swe.FLG_SPEED

    results: List[BodyPosition] = []
    for name in bodies:
        planet_id = PLANETS[name]

        # Get longitude and speed
        pos, ret_flags = swe.calc_ut(jd, planet_id, flags)
        lon = pos[0]
        speed = pos[3]

        # Get declination via equatorial flag
        eq_pos, _ = swe.calc_ut(jd, planet_id, flags | swe.FLG_EQUATORIAL)
        declination = eq_pos[1]  # declination is second element in equatorial

        results.append(BodyPosition(
            name=name,
            longitude=lon,
            speed=speed,
            declination=declination,
        ))

    return results


def get_position(target_date: date, body_name: str, hour_utc: float = DEFAULT_HOUR_UTC) -> BodyPosition:
    """Get position for a single body."""
    positions = compute_positions(target_date, hour_utc, [body_name])
    return positions[0]
