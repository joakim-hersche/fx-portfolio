import pytest
from src.ui.bulk_add import parse_date


class TestParseDate:
    """Test the multi-format date parser."""

    def test_iso_format(self):
        assert parse_date("2024-03-15") == "2024-03-15"

    def test_european_dot(self):
        assert parse_date("15.03.2024") == "2024-03-15"

    def test_european_slash(self):
        assert parse_date("15/03/2024") == "2024-03-15"

    def test_european_dash(self):
        assert parse_date("15-03-2024") == "2024-03-15"

    def test_unambiguous_day_gt_12(self):
        # Day > 12 means DD/MM regardless of separator
        assert parse_date("25/01/2024") == "2024-01-25"

    def test_ambiguous_defaults_european(self):
        # Both <= 12: default to DD/MM (European)
        assert parse_date("01/02/2024") == "2024-02-01"

    def test_us_format_when_month_gt_12_impossible(self):
        # 13/01/2024 can only be DD/MM (13 is not a valid month)
        assert parse_date("13/01/2024") == "2024-01-13"

    def test_invalid_returns_none(self):
        assert parse_date("asdf") is None
        assert parse_date("99/99/9999") is None
        assert parse_date("") is None

    def test_two_digit_year(self):
        assert parse_date("15.03.24") == "2024-03-15"

    def test_format_confirmation(self):
        # Test the human-readable confirmation string
        from src.ui.bulk_add import format_date_confirm
        assert format_date_confirm("2024-03-15") == "15-Mar-2024"
        assert format_date_confirm("2024-12-01") == "1-Dec-2024"
