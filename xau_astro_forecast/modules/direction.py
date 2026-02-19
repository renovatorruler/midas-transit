"""Direction module - computes UP/DOWN bias from aspect polarities and price action."""

from dataclasses import dataclass
from typing import Dict, List, Optional

from .aspects import AspectInfo
from .price_analysis import PriceMetrics


@dataclass
class DirectionResult:
    """Result of direction bias analysis."""
    bias: str               # "UP" or "DOWN"
    probability: float      # 50-100% confidence
    confirmation: bool      # True if astro bias aligns with price action
    astro_score: float      # raw weighted polarity score (positive=UP, negative=DOWN)
    detail: str             # human-readable explanation


# Aspect polarity: positive = bullish, negative = bearish
ASPECT_POLARITY: Dict[str, float] = {
    "conjunction": 0.0,     # neutral - depends on planets
    "sextile": 1.0,        # harmonious = bullish
    "trine": 1.0,          # harmonious = bullish
    "square": -1.0,        # tension = bearish
    "opposition": -1.0,    # tension = bearish
    "semi-sextile": 0.3,   # mildly harmonious
}

# Planet weights for direction scoring
PLANET_DIRECTION_WEIGHT: Dict[str, float] = {
    "Sun": 3.0, "Moon": 2.0, "Mercury": 1.5, "Venus": 2.5,
    "Mars": 2.0, "Jupiter": 4.0, "Saturn": 3.5,
    "Uranus": 3.0, "Neptune": 2.5, "Pluto": 4.0,
    "True Node": 1.0, "Mean Node": 1.0,
}

# Conjunction polarity depends on planet nature
PLANET_NATURE: Dict[str, float] = {
    "Sun": 0.3, "Moon": 0.1, "Mercury": 0.0, "Venus": 0.5,
    "Mars": -0.5, "Jupiter": 0.8, "Saturn": -0.6,
    "Uranus": -0.3, "Neptune": -0.2, "Pluto": -0.4,
    "True Node": 0.2, "Mean Node": 0.2,
    "ASC": 0.1, "MC": 0.2,
}


def _get_weight(body: str) -> float:
    """Get direction weight for a body."""
    clean = body.replace("N.", "")
    return PLANET_DIRECTION_WEIGHT.get(clean, 1.0)


def _get_nature(body: str) -> float:
    """Get nature value for a body (for conjunction polarity)."""
    clean = body.replace("N.", "")
    return PLANET_NATURE.get(clean, 0.0)


def _aspect_direction_score(aspect: AspectInfo) -> float:
    """Compute directional score for a single aspect."""
    polarity = ASPECT_POLARITY.get(aspect.aspect_name, 0.0)

    # For conjunctions, polarity depends on the planets involved
    if aspect.aspect_name == "conjunction":
        n1 = _get_nature(aspect.body1)
        n2 = _get_nature(aspect.body2)
        polarity = (n1 + n2) / 2.0

    w1 = _get_weight(aspect.body1)
    w2 = _get_weight(aspect.body2)
    weight = (w1 + w2) / 2.0

    # Tighter orb = stronger signal
    orb_factor = max(0.1, 1.0 - aspect.orb)

    return float(polarity * weight * orb_factor)


def compute_direction(
    aspects: List[AspectInfo],
    price_metrics: Optional[PriceMetrics] = None,
) -> DirectionResult:
    """Compute direction bias from aspects and optionally price data.

    Args:
        aspects: List of detected aspects
        price_metrics: Optional price metrics for confirmation check

    Returns:
        DirectionResult with bias, probability, and confirmation flag
    """
    if not aspects:
        return DirectionResult(
            bias="UP",
            probability=50.0,
            confirmation=False,
            astro_score=0.0,
            detail="No aspects - neutral bias",
        )

    astro_score = sum(_aspect_direction_score(a) for a in aspects)

    bias = "UP" if astro_score >= 0 else "DOWN"

    # Convert raw score to probability (50-100% range)
    # Use sigmoid-like mapping
    magnitude = abs(astro_score)
    probability = 50.0 + 50.0 * (1.0 - 1.0 / (1.0 + magnitude / 5.0))
    probability = round(min(99.0, probability), 1)

    # Confirmation: check if astro bias aligns with price action
    confirmation = False
    if price_metrics is not None:
        price_bias = "UP" if price_metrics.polarity == "HIGH" else (
            "DOWN" if price_metrics.polarity == "LOW" else None
        )
        if price_bias is not None and price_bias == bias:
            confirmation = True

    detail_parts = []
    up_count = sum(1 for a in aspects if _aspect_direction_score(a) > 0)
    down_count = sum(1 for a in aspects if _aspect_direction_score(a) < 0)
    detail_parts.append(f"{up_count} bullish, {down_count} bearish aspects")
    if confirmation:
        detail_parts.append("CONFIRMED by price action")
    detail = "; ".join(detail_parts)

    return DirectionResult(
        bias=bias,
        probability=probability,
        confirmation=confirmation,
        astro_score=round(astro_score, 4),
        detail=detail,
    )
