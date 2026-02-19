"""Integration tests - full pipeline end-to-end."""

import os
from datetime import date

import pytest

from xau_astro_forecast.main import run_pipeline, parse_args, main


def _csv_path() -> str:
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "data", "xau_prices.csv")


class TestParseArgs:
    def test_defaults(self) -> None:
        args = parse_args([])
        assert args.date is None
        assert args.csv is None

    def test_date_flag(self) -> None:
        args = parse_args(["--date", "2025-01-15"])
        assert args.date == "2025-01-15"

    def test_csv_flag(self) -> None:
        args = parse_args(["--csv", "/tmp/test.csv"])
        assert args.csv == "/tmp/test.csv"

    def test_both_flags(self) -> None:
        args = parse_args(["--date", "2025-06-01", "--csv", "/tmp/x.csv"])
        assert args.date == "2025-06-01"
        assert args.csv == "/tmp/x.csv"


class TestRunPipeline:
    def test_pipeline_without_price_data(self) -> None:
        """Run full pipeline for a date with no CSV."""
        report = run_pipeline(date(2025, 1, 15), csv_path=None)
        assert isinstance(report, str)
        assert len(report) > 100
        # Should contain key report sections
        assert "2025-01-15" in report

    def test_pipeline_with_price_data(self) -> None:
        """Run full pipeline with sample CSV."""
        csv = _csv_path()
        if not os.path.exists(csv):
            pytest.skip("Sample CSV not found")
        report = run_pipeline(date(2025, 1, 15), csv_path=csv)
        assert isinstance(report, str)
        assert len(report) > 100

    def test_pipeline_returns_string(self) -> None:
        report = run_pipeline(date(2024, 6, 15))
        assert isinstance(report, str)

    def test_pipeline_different_dates(self) -> None:
        """Pipeline works for different dates."""
        r1 = run_pipeline(date(2025, 3, 1))
        r2 = run_pipeline(date(2025, 6, 1))
        assert isinstance(r1, str)
        assert isinstance(r2, str)
        # Different dates should produce different reports
        assert "2025-03-01" in r1
        assert "2025-06-01" in r2


class TestMainCLI:
    def test_main_runs(self, capsys: pytest.CaptureFixture[str]) -> None:
        """main() runs without error."""
        main(["--date", "2025-01-15"])
        captured = capsys.readouterr()
        assert len(captured.out) > 50

    def test_main_invalid_date(self) -> None:
        """main() exits on invalid date."""
        with pytest.raises(SystemExit):
            main(["--date", "not-a-date"])
