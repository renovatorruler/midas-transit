"""Formatter module - Rich terminal output for V3.5 forecast report."""

from typing import Dict, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

from .ephemeris import BodyPosition
from .aspects import AspectInfo
from .moon import MoonPhaseResult
from .price_analysis import PriceMetrics
from .scoring import ScoringResult
from .direction import DirectionResult
from .signal import SignalResult


def _make_ephemeris_table(positions: Dict[str, BodyPosition]) -> Table:
    """Create ephemeris table showing all bodies."""
    table = Table(title="Ephemeris Positions (06:00 UTC)", box=box.ROUNDED)
    table.add_column("Body", style="cyan")
    table.add_column("Longitude", justify="right", style="yellow")
    table.add_column("Speed (°/day)", justify="right")
    table.add_column("Declination", justify="right")
    for name, pos in positions.items():
        speed_style = "green" if pos.speed >= 0 else "red"
        table.add_row(
            name,
            f"{pos.longitude:.4f}°",
            f"[{speed_style}]{pos.speed:.4f}[/{speed_style}]",
            f"{pos.declination:.4f}°",
        )
    return table


def _make_aspect_table(aspects: List[AspectInfo], title: str) -> Table:
    """Create aspect table for a group."""
    table = Table(title=title, box=box.SIMPLE)
    table.add_column("Body 1", style="cyan")
    table.add_column("Aspect", style="magenta")
    table.add_column("Body 2", style="cyan")
    table.add_column("Orb", justify="right")
    table.add_column("State", style="yellow")
    table.add_column("Regime", style="blue")
    for a in aspects:
        orb_style = "green" if a.orb < 0.3 else ("yellow" if a.orb < 0.7 else "red")
        state = "applying" if a.applying else "separating"
        table.add_row(
            a.body1,
            a.aspect_name,
            a.body2,
            f"[{orb_style}]{a.orb:.4f}°[/{orb_style}]",
            state,
            a.regime,
        )
    return table


def _split_aspects(aspects: List[AspectInfo]) -> tuple:
    """Split aspects into Outer Pressure Drivers and Angle Activations."""
    outer = []
    angles = []
    for a in aspects:
        if a.regime == "STRUCTURAL":
            outer.append(a)
        else:
            angles.append(a)
    return outer, angles


def format_report(
    report_date: str,
    positions: Dict[str, BodyPosition],
    aspects: List[AspectInfo],
    moon: MoonPhaseResult,
    price: Optional[PriceMetrics],
    scoring: ScoringResult,
    direction: DirectionResult,
    signal: SignalResult,
    console: Optional[Console] = None,
) -> Console:
    """Render the full V3.5 forecast report to a Rich console.

    Args:
        report_date: Date string for the report header.
        positions: Dict of body name -> BodyPosition from ephemeris.
        aspects: List of AspectInfo from aspect engine.
        moon: MoonPhaseResult from moon module.
        price: PriceMetrics from price analysis (None if unavailable).
        scoring: ScoringResult from scoring module.
        direction: DirectionResult from direction module.
        signal: SignalResult from signal module.
        console: Optional Console instance (created if not provided).

    Returns:
        The Console instance used for rendering.
    """
    if console is None:
        console = Console()

    # Header
    console.print()
    console.print(Panel(
        f"[bold white]MIDAS TRANSIT SYSTEM — XAU/USD Astro Forecast[/bold white]\n"
        f"[dim]Report Date: {report_date} | V3.5 Format[/dim]",
        style="bold blue",
    ))

    # Ephemeris
    console.print(_make_ephemeris_table(positions))

    # Aspects
    outer_aspects, angle_aspects = _split_aspects(aspects)
    if outer_aspects:
        console.print(_make_aspect_table(outer_aspects, "Outer Pressure Drivers"))
    else:
        console.print(Panel("[dim]No outer pressure aspects active[/dim]", title="Outer Pressure Drivers"))
    if angle_aspects:
        console.print(_make_aspect_table(angle_aspects, "Angle Activations"))
    else:
        console.print(Panel("[dim]No angle activations active[/dim]", title="Angle Activations"))

    # Moon Phase
    console.print(Panel(
        f"[bold]{moon.phase_name}[/bold] — Elongation: {moon.elongation:.2f}°\n"
        f"[dim]{moon.trading_interpretation}[/dim]",
        title="Moon Phase",
        style="yellow",
    ))

    # Price Metrics
    if price is not None:
        price_table = Table(title="Price Metrics", box=box.ROUNDED)
        price_table.add_column("Metric", style="cyan")
        price_table.add_column("Value", justify="right")
        price_table.add_row("Close", f"${price.close:.2f}")
        price_table.add_row("Close Pos60", f"{price.close_pos60:.1f}%")
        price_table.add_row("Close Pos20", f"{price.close_pos20:.1f}%")
        price_table.add_row("Low Pos60", f"{price.low_pos60:.1f}%")
        price_table.add_row("Change 5D", f"{price.change5:.2f}%")
        price_table.add_row("Direction 1D", price.direction_1d)
        price_table.add_row("Change 1D", f"{price.change_1d:.2f}%")
        price_table.add_row("Polarity", f"[bold]{price.polarity}[/bold]")
        console.print(price_table)
    else:
        console.print(Panel("[dim]Price data unavailable[/dim]", title="Price Metrics"))

    # Scoring
    score_color = "red" if scoring.score >= 7 else ("yellow" if scoring.score >= 4 else "green")
    console.print(Panel(
        f"Pressure Score: [{score_color}][bold]{scoring.score:.1f}/10[/bold][/{score_color}]\n"
        f"Phase: {scoring.phase} | State: {scoring.state}\n"
        f"Context: {scoring.context}\n"
        f"[dim]Raw score: {scoring.raw_score:.2f} | Aspects scored: {scoring.aspect_count}[/dim]",
        title="Scoring Summary",
        style="magenta",
    ))

    # Direction
    bias_color = "green" if direction.bias == "UP" else "red"
    confirm_text = "✓ CONFIRMED" if direction.confirmation else "✗ Unconfirmed"
    confirm_color = "green" if direction.confirmation else "yellow"
    console.print(Panel(
        f"Bias: [{bias_color}][bold]{direction.bias}[/bold][/{bias_color}] "
        f"({direction.probability:.1f}%)\n"
        f"Confirmation: [{confirm_color}]{confirm_text}[/{confirm_color}]\n"
        f"[dim]{direction.detail}[/dim]",
        title="Direction Bias",
        style="blue",
    ))

    # Signal
    signal_colors = {"LONG": "green", "SHORT": "red", "NEUTRAL": "yellow"}
    sig_color = signal_colors.get(signal.signal, "white")
    risk_colors = {"LOW": "green", "MEDIUM": "yellow", "HIGH": "red"}
    risk_color = risk_colors.get(signal.risk_level, "white")
    console.print(Panel(
        f"Signal: [{sig_color}][bold]{signal.signal}[/bold][/{sig_color}] | "
        f"Risk: [{risk_color}]{signal.risk_level}[/{risk_color}] | "
        f"Size: {signal.position_size}%\n"
        f"Strategy: {signal.strategy}\n"
        f"Invalidation: {signal.invalidation}",
        title="Trading Signal",
        style="bold green" if signal.signal == "LONG" else (
            "bold red" if signal.signal == "SHORT" else "bold yellow"
        ),
    ))

    console.print()
    return console


def render_report_to_string(
    report_date: str,
    positions: Dict[str, BodyPosition],
    aspects: List[AspectInfo],
    moon: MoonPhaseResult,
    price: Optional[PriceMetrics],
    scoring: ScoringResult,
    direction: DirectionResult,
    signal: SignalResult,
) -> str:
    """Render report and return as a string (for testing/capture)."""
    from io import StringIO
    string_io = StringIO()
    console = Console(file=string_io, force_terminal=True, width=120)
    format_report(
        report_date=report_date,
        positions=positions,
        aspects=aspects,
        moon=moon,
        price=price,
        scoring=scoring,
        direction=direction,
        signal=signal,
        console=console,
    )
    return string_io.getvalue()
