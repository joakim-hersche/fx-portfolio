import pytest
from unittest.mock import patch, MagicMock
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


class TestResolveTicker:
    """Test ticker resolution against cached lists and yfinance fallback."""

    @patch("src.ui.bulk_add.load_stock_options")
    def test_exact_symbol_match(self, mock_options):
        from src.ui.bulk_add import resolve_ticker, TickerMatch
        mock_options.return_value = {
            "US — S&P 500": {"AAPL": "Apple Inc (AAPL)"},
        }
        result = resolve_ticker("AAPL")
        assert result.status == "resolved"
        assert result.ticker == "AAPL"
        assert result.label == "Apple Inc (AAPL)"
        assert result.is_alt is False

    @patch("src.ui.bulk_add.load_stock_options")
    def test_name_search_single_match(self, mock_options):
        from src.ui.bulk_add import resolve_ticker, TickerMatch
        mock_options.return_value = {
            "US — S&P 500": {"AAPL": "Apple Inc (AAPL)"},
        }
        result = resolve_ticker("apple")
        assert result.status == "resolved"
        assert result.ticker == "AAPL"

    @patch("src.ui.bulk_add.load_stock_options")
    def test_ambiguous_multiple_matches(self, mock_options):
        from src.ui.bulk_add import resolve_ticker, TickerMatch
        mock_options.return_value = {
            "UK — FTSE 100": {"SHEL.L": "Shell plc (SHEL.L)"},
            "Netherlands — AEX": {"SHELL.AS": "Shell plc (SHELL.AS)"},
        }
        result = resolve_ticker("shell")
        assert result.status == "ambiguous"
        assert len(result.matches) == 2

    @patch("src.ui.bulk_add.load_stock_options")
    def test_crypto_tagged_as_alt(self, mock_options):
        from src.ui.bulk_add import resolve_ticker, TickerMatch
        mock_options.return_value = {
            "Crypto": {"BTC-USD": "Bitcoin (BTC-USD)"},
        }
        result = resolve_ticker("BTC-USD")
        assert result.status == "resolved"
        assert result.is_alt is True

    @patch("src.ui.bulk_add.load_stock_options")
    @patch("src.ui.bulk_add._validate_via_yfinance")
    def test_yfinance_fallback(self, mock_validate, mock_options):
        from src.ui.bulk_add import resolve_ticker, TickerMatch
        mock_options.return_value = {"US — S&P 500": {}}
        mock_validate.return_value = "Custom Ticker Inc"
        result = resolve_ticker("CUSTOM")
        assert result.status == "resolved"
        assert result.ticker == "CUSTOM"

    @patch("src.ui.bulk_add.load_stock_options")
    @patch("src.ui.bulk_add._validate_via_yfinance")
    def test_not_found(self, mock_validate, mock_options):
        from src.ui.bulk_add import resolve_ticker, TickerMatch
        mock_options.return_value = {"US — S&P 500": {}}
        mock_validate.return_value = None
        result = resolve_ticker("XYZFAKE")
        assert result.status == "not_found"


from src.ui.bulk_add import BulkRow


class TestBulkRow:
    """Test per-row state management."""

    def test_new_row_is_empty(self):
        row = BulkRow(index=0)
        assert row.is_empty()
        assert not row.is_ready()

    def test_resolved_with_shares_and_price_is_ready(self):
        row = BulkRow(index=0)
        row.ticker_input = "AAPL"
        row.resolved_ticker = "AAPL"
        row.resolved_label = "Apple Inc (AAPL)"
        row.ticker_status = "resolved"
        row.shares = 10.0
        row.parsed_date = "2024-03-15"
        row.price = 171.48
        row.buy_fx_rate = 1.0
        assert row.is_ready()

    def test_resolved_without_price_not_ready(self):
        row = BulkRow(index=0)
        row.ticker_status = "resolved"
        row.resolved_ticker = "AAPL"
        row.shares = 10.0
        row.price = None
        assert not row.is_ready()

    def test_ambiguous_not_ready(self):
        row = BulkRow(index=0)
        row.ticker_input = "Shell"
        row.ticker_status = "ambiguous"
        row.shares = 10.0
        assert not row.is_ready()

    def test_not_found_not_ready(self):
        row = BulkRow(index=0)
        row.ticker_input = "XYZFAKE"
        row.ticker_status = "not_found"
        assert not row.is_ready()

    def test_missing_shares_not_ready(self):
        row = BulkRow(index=0)
        row.ticker_status = "resolved"
        row.resolved_ticker = "AAPL"
        row.shares = 0.0
        assert not row.is_ready()

    def test_to_lot(self):
        row = BulkRow(index=0)
        row.resolved_ticker = "AAPL"
        row.ticker_status = "resolved"
        row.shares = 10.0
        row.parsed_date = "2024-03-15"
        row.price = 171.48
        row.buy_fx_rate = 1.0
        row.manual_price = False
        lot = row.to_lot()
        assert lot == {
            "shares": 10.0,
            "buy_price": 171.48,
            "buy_fx_rate": 1.0,
            "purchase_date": "2024-03-15",
            "manual_price": False,
        }

    def test_alt_asset_to_lot_converts_amount(self):
        row = BulkRow(index=0)
        row.resolved_ticker = "BTC-USD"
        row.ticker_status = "resolved"
        row.is_alt = True
        row.shares = 500.0  # fiat amount
        row.price = 50000.0
        row.parsed_date = "2024-03-15"
        row.buy_fx_rate = 1.0
        row.manual_price = False
        lot = row.to_lot()
        assert lot["shares"] == round(500.0 / 50000.0, 6)  # 0.01

    def test_reset_clears_derived_state(self):
        row = BulkRow(index=0)
        row.resolved_ticker = "AAPL"
        row.ticker_status = "resolved"
        row.price = 171.48
        row.buy_fx_rate = 1.0
        row.reset_resolution()
        assert row.ticker_status == "pending"
        assert row.resolved_ticker is None
        assert row.price is None
        assert row.buy_fx_rate is None

    def test_reset_preserves_shares_and_date(self):
        row = BulkRow(index=0)
        row.shares = 10.0
        row.date_input = "2024-03-15"
        row.parsed_date = "2024-03-15"
        row.ticker_status = "resolved"
        row.resolved_ticker = "AAPL"
        row.price = 171.48
        row.reset_resolution()
        assert row.shares == 10.0
        assert row.date_input == "2024-03-15"
        assert row.parsed_date == "2024-03-15"
        assert row.ticker_status == "pending"
        assert row.price is None
