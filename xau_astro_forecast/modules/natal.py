"""Natal chart module - loads fixed natal chart from JSON and computes positions."""

import json
import os
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional

import swisseph as swe

from .ephemeris import BODY_NAMES, PLANETS, BodyPosition


@dataclass
class NatalChart:
    """Complete natal chart with planet positions and angles."""
    name: str
    date_str: str
    time_str: str
    timezone: str
    latitude: float
    longitude: float
    planets: Dict[str, BodyPosition] = field(default_factory=dict)
    asc: float = 0.0
    mc: float = 0.0


# Module-level cache
_cached_chart: Optional[NatalChart] = None


def _get_config_path() -> str:
    """Get path to natal_chart.json."""
    module_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(module_dir, "..", "config", "natal_chart.json")


def load_natal_config(config_path: Optional[str] = None) -> dict:
    """Load natal chart configuration from JSON file."""
    if config_path is None:
        config_path = _get_config_path()
    with open(config_path, "r") as f:
        return json.load(f)  # type: ignore[no-any-return]


def compute_natal_chart(config_path: Optional[str] = None, use_cache: bool = True) -> NatalChart:
    """Compute natal chart positions from config.

    Args:
        config_path: Path to natal_chart.json. Uses default if None.
        use_cache: If True, return cached chart after first computation.

    Returns:
        NatalChart with all planet positions, ASC, and MC.
    """
    global _cached_chart

    if use_cache and _cached_chart is not None:
        return _cached_chart

    config = load_natal_config(config_path)

    # Parse date and time
    date_parts = config["date"].split("-")
    year = int(date_parts[0])
    month = int(date_parts[1])
    day = int(date_parts[2])

    time_parts = config["time"].split(":")
    hour = int(time_parts[0])
    minute = int(time_parts[1])

    lat = config["location"]["latitude"]
    lon = config["location"]["longitude"]

    # Use pre-computed UT hour if available (handles historical chart discrepancies)
    # Otherwise convert local time to UTC using offset
    if "ut_hour" in config:
        hour_utc = float(config["ut_hour"])
    else:
        utc_offset = config["utc_offset"]
        hour_utc = hour + minute / 60.0 - utc_offset

    # Compute Julian Day
    jd = float(swe.julday(year, month, day, hour_utc))

    # Compute houses and angles
    # swe.houses returns (cusps_tuple, ascmc_tuple)
    # ascmc: [0]=ASC, [1]=MC, [2]=ARMC, [3]=Vertex, etc.
    cusps, ascmc = swe.houses(jd, lat, lon, b'P')  # Placidus
    asc = float(ascmc[0])
    mc = float(ascmc[1])

    # Compute planet positions
    flags = swe.FLG_SWIEPH | swe.FLG_SPEED
    planets: Dict[str, BodyPosition] = {}

    for name in BODY_NAMES:
        planet_id = PLANETS[name]
        pos, _ = swe.calc_ut(jd, planet_id, flags)
        eq_pos, _ = swe.calc_ut(jd, planet_id, flags | swe.FLG_EQUATORIAL)

        planets[name] = BodyPosition(
            name=name,
            longitude=pos[0],
            speed=pos[3],
            declination=eq_pos[1],
        )

    chart = NatalChart(
        name=config["name"],
        date_str=config["date"],
        time_str=config["time"],
        timezone=config["timezone"],
        latitude=lat,
        longitude=lon,
        planets=planets,
        asc=asc,
        mc=mc,
    )

    if use_cache:
        _cached_chart = chart

    return chart


def clear_cache() -> None:
    """Clear the cached natal chart."""
    global _cached_chart
    _cached_chart = None


def get_natal_position(body_name: str, config_path: Optional[str] = None) -> BodyPosition:
    """Get natal position for a single body."""
    chart = compute_natal_chart(config_path)
    return chart.planets[body_name]
