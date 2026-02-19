# Midas Transit System

A Python-based astro-trading forecast system for XAU (gold), combining astrological transit analysis with price action data.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r xau_astro_forecast/requirements.txt
```

## Usage

```bash
# Run the forecast
python -m xau_astro_forecast.main

# Run tests
pytest

# Type check
mypy xau_astro_forecast/
```

## Project Structure

```
xau_astro_forecast/
├── config/          # Configuration JSON files
├── data/            # Price data CSVs
├── modules/         # Core modules
│   └── ephemeris.py # Swiss Ephemeris wrapper
├── tests/           # Test suite
├── main.py          # Entry point
├── backtest.py      # Backtesting engine
└── requirements.txt # Dependencies
```
