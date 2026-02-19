"""Midas Transit System - XAU Astro-Trading Forecast.

Main entry point that wires all modules together into a full pipeline:
ephemeris → natal → aspects → moon → price → scoring → direction → signal → formatter
"""

import argparse
import os
import sys
from datetime import date, datetime
from typing import Optional

from xau_astro_forecast.modules.ephemeris import BodyPosition, compute_positions
from xau_astro_forecast.modules.natal import compute_natal_chart, NatalChart
from xau_astro_forecast.modules.aspects import compute_all_aspects, AspectInfo
from xau_astro_forecast.modules.moon import get_moon_phase, MoonPhaseResult
from xau_astro_forecast.modules.price_analysis import (
    load_prices,
    compute_metrics,
    get_metrics_for_date,
    PriceMetrics,
)
from xau_astro_forecast.modules.scoring import score_aspects, ScoringResult
from xau_astro_forecast.modules.direction import compute_direction, DirectionResult
from xau_astro_forecast.modules.signal import generate_signal, SignalResult
from xau_astro_forecast.modules.formatter import format_report, render_report_to_string

from typing import Dict, List


def _default_csv_path() -> str:
    """Return default path to xau_prices.csv relative to project root."""
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "xau_astro_forecast", "data", "xau_prices.csv")


def run_pipeline(
    target_date: date,
    csv_path: Optional[str] = None,
) -> str:
    """Run the full forecast pipeline and return the report as a string.

    Args:
        target_date: Date to generate forecast for.
        csv_path: Path to XAU OHLCV CSV. None to skip price analysis.

    Returns:
        Formatted report string.
    """
    # 1. Ephemeris
    position_list: List[BodyPosition] = compute_positions(target_date)
    positions: Dict[str, BodyPosition] = {p.name: p for p in position_list}

    # 2. Natal
    natal: NatalChart = compute_natal_chart()

    # 3. Aspects
    aspects: List[AspectInfo] = compute_all_aspects(
        transit_positions=position_list,
        natal_planets=natal.planets,
        asc=natal.asc,
        mc=natal.mc,
    )

    # 4. Moon phase
    moon: MoonPhaseResult = get_moon_phase(target_date)

    # 5. Price analysis
    price: Optional[PriceMetrics] = None
    if csv_path and os.path.exists(csv_path):
        try:
            df = load_prices(csv_path)
            df = compute_metrics(df)
            date_str = target_date.strftime("%Y-%m-%d")
            price = get_metrics_for_date(df, date_str)
        except Exception as e:
            print(f"Warning: Could not load price data: {e}", file=sys.stderr)

    # 6. Scoring
    scoring: ScoringResult = score_aspects(aspects)

    # 7. Direction
    direction: DirectionResult = compute_direction(aspects, price)

    # 8. Signal
    signal: SignalResult = generate_signal(direction, scoring, price)

    # 9. Format report
    report_date = target_date.strftime("%Y-%m-%d")
    report = render_report_to_string(
        report_date=report_date,
        positions=positions,
        aspects=aspects,
        moon=moon,
        price=price,
        scoring=scoring,
        direction=direction,
        signal=signal,
    )

    return report


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        prog="midas-transit",
        description="Midas Transit System - XAU Astro-Trading Forecast",
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Forecast date in YYYY-MM-DD format (default: today)",
    )
    parser.add_argument(
        "--csv",
        type=str,
        default=None,
        help="Path to XAU OHLCV CSV file (default: data/xau_prices.csv)",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> None:
    """Entry point for the forecast system."""
    args = parse_args(argv)

    # Parse date
    if args.date:
        try:
            target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
        except ValueError:
            print(f"Error: Invalid date format '{args.date}'. Use YYYY-MM-DD.", file=sys.stderr)
            sys.exit(1)
    else:
        target_date = date.today()

    # CSV path
    csv_path: Optional[str] = args.csv if args.csv else _default_csv_path()

    report = run_pipeline(target_date, csv_path)
    print(report)


if __name__ == "__main__":
    main()
