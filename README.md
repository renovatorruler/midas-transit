# Midas Transit System

A Python-based astro-trading forecast system for XAU (gold). Generates trading signals by combining astrological transit analysis against a fixed natal chart (COMEX gold futures first trade date) with price action data.

## Setup

### Requirements

- Python 3.9+
- Swiss Ephemeris data files (bundled with pyswisseph)

### Installation

```bash
git clone https://github.com/renovatorruler/midas-transit.git
cd midas-transit
pip install -r requirements.txt
```

### Dependencies

- `pyswisseph` — Swiss Ephemeris bindings for planetary calculations
- `pandas` — Price data analysis
- `rich` — Terminal report formatting
- `pytest` — Testing
- `mypy` — Type checking

## Usage

### Generate a Forecast

```bash
# Today's forecast (default)
python -m xau_astro_forecast.main

# Specific date
python -m xau_astro_forecast.main --date 2025-01-15

# Custom price CSV
python -m xau_astro_forecast.main --date 2025-01-15 --csv path/to/xau_prices.csv
```

### CLI Arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `--date` | Forecast date (YYYY-MM-DD) | Today |
| `--csv`  | Path to XAU OHLCV CSV file | `data/xau_prices.csv` |

### Output

The system produces a V3.5 formatted terminal report with:

- **Ephemeris Table** — Planetary positions (longitude, speed, declination)
- **Aspect Groups** — Outer Pressure Drivers, Angle Activations, other aspects
- **Moon Phase** — Current phase and trading interpretation
- **Price Metrics** — Percentile rankings, momentum, polarity
- **Scoring** — Astrological pressure rating (1-10) with phase/state/context
- **Direction** — UP/DOWN bias with probability and confirmation flag
- **Signal** — LONG/SHORT/NEUTRAL with risk level, position size, strategy

## Architecture

### Pipeline

```
Date Input → Ephemeris → Natal Chart → Aspects → Moon Phase
                                          ↓
                               Price Analysis (CSV)
                                          ↓
                               Scoring → Direction → Signal → Report
```

### Modules

| Module | Description |
|--------|-------------|
| `ephemeris.py` | pyswisseph wrapper for planetary positions |
| `natal.py` | Fixed natal chart (1974-12-31, COMEX gold) |
| `aspects.py` | Aspect detection with orb configuration |
| `moon.py` | Moon phase classification |
| `price_analysis.py` | OHLCV price metrics |
| `scoring.py` | Astrological pressure scoring |
| `direction.py` | Directional bias computation |
| `signal.py` | Trading signal generation |
| `formatter.py` | Rich terminal report output |

### Configuration

All configs are in `xau_astro_forecast/config/`:

- `natal_chart.json` — Natal chart parameters
- `aspect_orbs.json` — Aspect types and orb limits
- `scoring_weights.json` — Planet weights and scoring thresholds

## Natal Chart

The system uses the COMEX gold futures first trade date as its fixed natal anchor:

- **Date:** 1974-12-31
- **Time:** 08:20 EST
- **Location:** NYC (40.7128°N, 74.0047°W)
- **ASC:** ~241.35°
- **MC:** ~166.87°

## Testing

```bash
# Run all tests
python -m pytest xau_astro_forecast/tests/ -v

# Type checking
python -m mypy xau_astro_forecast/
```

## Price Data

Place your XAU/USD OHLCV CSV in `xau_astro_forecast/data/xau_prices.csv` with columns:

```
Date,Open,High,Low,Close,Volume
2025-01-02,2635.00,2665.00,2630.00,2655.00,150000
```

A sample dataset is included for testing.

## License

Private — All rights reserved.
