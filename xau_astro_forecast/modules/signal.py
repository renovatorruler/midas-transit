"""Signal module - generates trading signals from direction, scoring, and price data."""

from dataclasses import dataclass
from typing import Optional

from .direction import DirectionResult
from .scoring import ScoringResult
from .price_analysis import PriceMetrics


@dataclass
class SignalResult:
    """Trading signal output."""
    signal: str             # "LONG", "SHORT", or "NEUTRAL"
    risk_level: str         # "LOW", "MEDIUM", or "HIGH"
    position_size: int      # 0-100%
    strategy: str           # description of recommended strategy
    invalidation: str       # criteria that would invalidate the signal


def _compute_position_size(
    direction: DirectionResult,
    scoring: ScoringResult,
) -> int:
    """Compute position size 0-100% based on conviction."""
    # Base size from direction probability
    base = (direction.probability - 50.0) * 2.0  # 0-100 range

    # Boost if confirmed
    if direction.confirmation:
        base = min(100.0, base * 1.3)

    # Scale by pressure: high pressure = more conviction if direction is clear
    pressure_mult = 0.5 + (scoring.score / 10.0) * 0.5  # 0.5-1.0

    size = base * pressure_mult
    return max(0, min(100, int(round(size))))


def _compute_risk_level(scoring: ScoringResult, direction: DirectionResult) -> str:
    """Compute risk level."""
    if scoring.score >= 7.0 or scoring.phase in ("EXTREME PRESSURE", "HIGH PRESSURE"):
        return "HIGH"
    elif scoring.score >= 4.0 or direction.probability >= 65.0:
        return "MEDIUM"
    else:
        return "LOW"


def _build_strategy(
    signal: str,
    direction: DirectionResult,
    scoring: ScoringResult,
    price: Optional[PriceMetrics],
) -> str:
    """Build strategy description."""
    parts = []

    if signal == "NEUTRAL":
        parts.append("Stand aside - insufficient edge")
        if scoring.context == "QUIET PERIOD":
            parts.append("Wait for aspect activation")
        return ". ".join(parts)

    action = "Buy" if signal == "LONG" else "Sell"
    parts.append(f"{action} XAU/USD on {scoring.context.lower()} conditions")

    if direction.confirmation:
        parts.append("Price action confirms astro bias")
    else:
        parts.append("Astro-only signal, await price confirmation")

    if scoring.state == "BUILDING":
        parts.append("Scale in as aspects tighten")
    elif scoring.state == "PEAK":
        parts.append("Full position, watch for reversal signs")
    elif scoring.state == "EASING":
        parts.append("Reduce exposure as pressure dissipates")

    return ". ".join(parts)


def _build_invalidation(
    signal: str,
    direction: DirectionResult,
    price: Optional[PriceMetrics],
) -> str:
    """Build invalidation criteria."""
    parts = []

    if signal == "NEUTRAL":
        return "N/A - no active signal"

    if signal == "LONG":
        parts.append("Close below 20-period low")
        if price is not None:
            parts.append(f"Polarity shift to LOW (currently {price.polarity})")
    else:
        parts.append("Close above 20-period high")
        if price is not None:
            parts.append(f"Polarity shift to HIGH (currently {price.polarity})")

    parts.append(f"Direction probability drops below 55% (currently {direction.probability}%)")

    return "; ".join(parts)


def generate_signal(
    direction: DirectionResult,
    scoring: ScoringResult,
    price: Optional[PriceMetrics] = None,
) -> SignalResult:
    """Generate trading signal from direction, scoring, and price data.

    Args:
        direction: Direction bias result
        scoring: Scoring/pressure result
        price: Optional price metrics

    Returns:
        SignalResult with signal, risk, sizing, strategy, invalidation
    """
    # Determine signal
    min_probability = 55.0
    min_score = 2.0

    if direction.probability < min_probability or scoring.score < min_score:
        signal = "NEUTRAL"
    elif direction.bias == "UP":
        signal = "LONG"
    else:
        signal = "SHORT"

    # If price strongly contradicts direction without confirmation, go neutral
    if price is not None and not direction.confirmation:
        if signal == "LONG" and price.polarity == "LOW" and price.change_1d < -1.0:
            signal = "NEUTRAL"
        elif signal == "SHORT" and price.polarity == "HIGH" and price.change_1d > 1.0:
            signal = "NEUTRAL"

    risk_level = _compute_risk_level(scoring, direction)
    position_size = _compute_position_size(direction, scoring) if signal != "NEUTRAL" else 0
    strategy = _build_strategy(signal, direction, scoring, price)
    invalidation = _build_invalidation(signal, direction, price)

    return SignalResult(
        signal=signal,
        risk_level=risk_level,
        position_size=position_size,
        strategy=strategy,
        invalidation=invalidation,
    )
