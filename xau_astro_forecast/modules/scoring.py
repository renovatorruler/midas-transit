"""Scoring module - rates astrological pressure from aspects."""

import json
import os
from dataclasses import dataclass
from typing import Dict, List, Optional

from .aspects import AspectInfo


@dataclass
class ScoringResult:
    """Result of scoring astrological pressure."""
    score: float            # 1-10 pressure rating
    phase: str              # EXTREME PRESSURE, HIGH PRESSURE, MODERATE, LOW, MINIMAL
    state: str              # EASING, BUILDING, PEAK
    context: str            # POST-EVENT REBALANCE, PRE-EVENT TENSION, ACTIVATION WINDOW, QUIET PERIOD
    raw_score: float        # unnormalized weighted score
    aspect_count: int       # number of aspects scored


# Module-level config cache
_config: Optional[dict] = None


def _get_config_path() -> str:
    module_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(module_dir, "..", "config", "scoring_weights.json")


def load_config(config_path: Optional[str] = None) -> dict:
    """Load scoring weights configuration."""
    global _config
    if _config is not None and config_path is None:
        return _config
    path = config_path or _get_config_path()
    with open(path, "r") as f:
        cfg = json.load(f)
    if config_path is None:
        _config = cfg
    return dict(cfg)


def _get_body_weight(body: str, config: dict) -> float:
    """Get weight for a body (planet or angle)."""
    angle_weights = config.get("angle_weights", {})  # type: Dict[str, float]
    if body in angle_weights:
        return float(angle_weights[body])
    planet_weights = config.get("planet_weights", {})  # type: Dict[str, float]
    # Strip N. prefix for natal bodies
    clean = body.replace("N.", "")
    if clean in planet_weights:
        return float(planet_weights[clean])
    return 3.0  # default


def _compute_aspect_score(aspect: AspectInfo, config: dict) -> float:
    """Compute weighted score for a single aspect."""
    w1 = _get_body_weight(aspect.body1, config)
    w2 = _get_body_weight(aspect.body2, config)
    body_weight = (w1 + w2) / 2.0

    aspect_multipliers = config.get("aspect_type_multipliers", {})  # type: Dict[str, float]
    aspect_mult: float = float(aspect_multipliers.get(aspect.aspect_name, 1.0))

    # Tighter orb = higher score (exponential decay)
    decay = float(config.get("orb_decay_factor", 2.0))
    orb_factor = max(0.0, 1.0 - (aspect.orb ** 1.5) / decay)

    return float(body_weight * aspect_mult * orb_factor)


def compute_pressure_score(aspects: List[AspectInfo], config: Optional[dict] = None) -> float:
    """Compute raw pressure score from aspects."""
    if config is None:
        config = load_config()
    if not aspects:
        return 0.0
    total = sum(_compute_aspect_score(a, config) for a in aspects)
    return total


def _normalize_score(raw: float, aspect_count: int) -> float:
    """Normalize raw score to 1-10 range."""
    if aspect_count == 0:
        return 1.0
    # Scale: each aspect contributes ~3-8 raw points on average
    # With 1-2 aspects: low, 5+: high
    normalized = 1.0 + 9.0 * (1.0 - 1.0 / (1.0 + raw / 15.0))
    return max(1.0, min(10.0, round(normalized * 10) / 10))


def classify_phase(score: float, config: Optional[dict] = None) -> str:
    """Classify pressure phase based on score."""
    if config is None:
        config = load_config()
    thresholds = config.get("phase_thresholds", {})
    for phase in ["EXTREME PRESSURE", "HIGH PRESSURE", "MODERATE", "LOW", "MINIMAL"]:
        threshold = float(thresholds.get(phase, 0.0))
        if score >= threshold:
            return phase
    return "MINIMAL"


def classify_state(aspects: List[AspectInfo], config: Optional[dict] = None) -> str:
    """Classify state based on applying vs separating ratio."""
    if config is None:
        config = load_config()
    if not aspects:
        return "EASING"
    applying_count = sum(1 for a in aspects if a.applying)
    total = len(aspects)
    applying_ratio = applying_count / total

    thresholds = config.get("state_thresholds", {})
    # PEAK: most aspects near exact (low applying ratio = near exact or separating)
    peak_thresh = float(thresholds.get("PEAK", 0.3))
    building_thresh = float(thresholds.get("BUILDING", 0.55))

    if applying_ratio <= peak_thresh:
        return "PEAK"
    elif applying_ratio <= building_thresh:
        # Mix of applying and separating = near peak
        return "PEAK"
    else:
        # Mostly applying = still building
        return "BUILDING"


def classify_context(aspects: List[AspectInfo], state: str, config: Optional[dict] = None) -> str:
    """Classify context based on aspect patterns."""
    if config is None:
        config = load_config()
    rules = config.get("context_rules", {})
    tight_threshold = float(rules.get("tight_orb_threshold", 0.3))
    many_threshold = int(rules.get("many_aspects_threshold", 5))
    few_threshold = int(rules.get("few_aspects_threshold", 2))

    if not aspects:
        return "QUIET PERIOD"

    tight_count = sum(1 for a in aspects if a.orb <= tight_threshold)
    total = len(aspects)

    if state == "PEAK" and tight_count > 0:
        return "ACTIVATION WINDOW"
    elif state == "BUILDING" and total >= many_threshold:
        return "PRE-EVENT TENSION"
    elif state == "PEAK" and tight_count == 0:
        return "POST-EVENT REBALANCE"
    elif total <= few_threshold:
        return "QUIET PERIOD"
    else:
        return "PRE-EVENT TENSION"


def score_aspects(aspects: List[AspectInfo], config: Optional[dict] = None) -> ScoringResult:
    """Main scoring function: compute pressure score and classifications."""
    if config is None:
        config = load_config()

    raw = compute_pressure_score(aspects, config)
    score = _normalize_score(raw, len(aspects))
    phase = classify_phase(score, config)
    state = classify_state(aspects, config)
    context = classify_context(aspects, state, config)

    return ScoringResult(
        score=score,
        phase=phase,
        state=state,
        context=context,
        raw_score=round(raw, 4),
        aspect_count=len(aspects)
    )
