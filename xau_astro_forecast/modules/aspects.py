"""Aspect engine - calculates aspects between transit-transit, transit-natal, and transit-angle pairs."""

import json
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .ephemeris import BodyPosition


@dataclass
class AspectInfo:
    """Information about a detected aspect."""
    body1: str
    body2: str
    aspect_name: str
    aspect_angle: float
    orb: float              # actual orb (absolute difference from exact)
    applying: bool          # True if aspect is tightening
    regime: str             # STRUCTURAL or ACTIVE
    pair_type: str          # transit-transit, transit-natal, transit-angle


# Module-level config cache
_config: Optional[dict] = None


def _get_config_path() -> str:
    module_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(module_dir, "..", "config", "aspect_orbs.json")


def load_config(config_path: Optional[str] = None) -> dict:
    global _config
    if _config is not None and config_path is None:
        return _config
    if config_path is None:
        config_path = _get_config_path()
    with open(config_path, "r") as f:
        cfg = json.load(f)
    if config_path is None or config_path == _get_config_path():
        _config = cfg
    return cfg  # type: ignore[no-any-return]


def clear_config_cache() -> None:
    global _config
    _config = None


def angular_separation(lon1: float, lon2: float) -> float:
    """Compute minimum angular separation between two longitudes (0-180)."""
    diff = abs(lon1 - lon2) % 360
    if diff > 180:
        diff = 360 - diff
    return diff


def _is_outer(name: str, outer_planets: List[str]) -> bool:
    return name in outer_planets


def _get_max_orb(body1: str, body2: str, base_orb: float, outer_orb: float, outer_planets: List[str]) -> float:
    """Get max orb for a pair. Outer-outer pairs use reduced orb."""
    if _is_outer(body1, outer_planets) and _is_outer(body2, outer_planets):
        return min(base_orb, outer_orb)
    return base_orb


def _classify_applying(lon1: float, speed1: float, lon2: float, speed2: float, aspect_angle: float) -> bool:
    """Determine if aspect is applying (tightening) or separating.
    
    An aspect is applying if the angular distance to exact aspect is decreasing.
    """
    sep = angular_separation(lon1, lon2)
    # Small time step to check direction
    dt = 0.01  # days
    future_lon1 = (lon1 + speed1 * dt) % 360
    future_lon2 = (lon2 + speed2 * dt) % 360
    future_sep = angular_separation(future_lon1, future_lon2)
    
    # Check distance to exact aspect angle
    current_dist = abs(sep - aspect_angle)
    future_dist = abs(future_sep - aspect_angle)
    
    return future_dist < current_dist


def _classify_regime(body1: str, body2: str, pair_type: str, outer_planets: List[str]) -> str:
    """Classify regime: STRUCTURAL for outer planet aspects, ACTIVE for angle activations."""
    if pair_type == "transit-angle":
        return "ACTIVE"
    if _is_outer(body1, outer_planets) and _is_outer(body2, outer_planets):
        return "STRUCTURAL"
    if pair_type == "transit-natal" and _is_outer(body1, outer_planets):
        return "STRUCTURAL"
    # Mixed pairs default based on whether any outer planet involved
    if _is_outer(body1, outer_planets) or _is_outer(body2, outer_planets):
        return "STRUCTURAL"
    return "ACTIVE"


def find_aspects_between(
    body1: BodyPosition,
    body2_name: str,
    body2_lon: float,
    body2_speed: float,
    pair_type: str,
    config: Optional[dict] = None,
) -> List[AspectInfo]:
    """Find all aspects between two bodies/points."""
    if config is None:
        config = load_config()
    
    aspects_cfg = config["aspects"]
    outer_planets = config["outer_planets"]
    outer_orb = config["outer_outer_orb"]
    
    results: List[AspectInfo] = []
    sep = angular_separation(body1.longitude, body2_lon)
    
    for aspect_name, aspect_data in aspects_cfg.items():
        angle = aspect_data["angle"]
        base_orb = aspect_data["orb"]
        max_orb = _get_max_orb(body1.name, body2_name, base_orb, outer_orb, outer_planets)
        
        orb = abs(sep - angle)
        if orb <= max_orb:
            applying = _classify_applying(
                body1.longitude, body1.speed, body2_lon, body2_speed, angle
            )
            regime = _classify_regime(body1.name, body2_name, pair_type, outer_planets)
            
            results.append(AspectInfo(
                body1=body1.name,
                body2=body2_name,
                aspect_name=aspect_name,
                aspect_angle=angle,
                orb=round(orb, 4),
                applying=applying,
                regime=regime,
                pair_type=pair_type,
            ))
    
    return results


def compute_transit_transit_aspects(
    positions: List[BodyPosition],
    config: Optional[dict] = None,
) -> List[AspectInfo]:
    """Find all aspects between transit bodies (no duplicates)."""
    if config is None:
        config = load_config()
    
    results: List[AspectInfo] = []
    for i in range(len(positions)):
        for j in range(i + 1, len(positions)):
            aspects = find_aspects_between(
                positions[i],
                positions[j].name,
                positions[j].longitude,
                positions[j].speed,
                "transit-transit",
                config,
            )
            results.extend(aspects)
    return results


def compute_transit_natal_aspects(
    transit_positions: List[BodyPosition],
    natal_planets: Dict[str, BodyPosition],
    config: Optional[dict] = None,
) -> List[AspectInfo]:
    """Find all aspects between transit bodies and natal bodies."""
    if config is None:
        config = load_config()
    
    results: List[AspectInfo] = []
    for transit in transit_positions:
        for natal_name, natal_pos in natal_planets.items():
            aspects = find_aspects_between(
                transit,
                f"N.{natal_name}",
                natal_pos.longitude,
                0.0,  # natal positions don't move
                "transit-natal",
                config,
            )
            results.extend(aspects)
    return results


def compute_transit_angle_aspects(
    transit_positions: List[BodyPosition],
    asc: float,
    mc: float,
    config: Optional[dict] = None,
) -> List[AspectInfo]:
    """Find all aspects between transit bodies and natal angles (ASC/MC)."""
    if config is None:
        config = load_config()
    
    results: List[AspectInfo] = []
    angles = {"ASC": asc, "MC": mc}
    
    for transit in transit_positions:
        for angle_name, angle_lon in angles.items():
            aspects = find_aspects_between(
                transit,
                f"N.{angle_name}",
                angle_lon,
                0.0,  # angles don't move
                "transit-angle",
                config,
            )
            results.extend(aspects)
    return results


def compute_all_aspects(
    transit_positions: List[BodyPosition],
    natal_planets: Dict[str, BodyPosition],
    asc: float,
    mc: float,
    config: Optional[dict] = None,
) -> List[AspectInfo]:
    """Compute all aspects: transit-transit, transit-natal, and transit-angle."""
    if config is None:
        config = load_config()
    
    results: List[AspectInfo] = []
    results.extend(compute_transit_transit_aspects(transit_positions, config))
    results.extend(compute_transit_natal_aspects(transit_positions, natal_planets, config))
    results.extend(compute_transit_angle_aspects(transit_positions, asc, mc, config))
    return results
