"""Bulk Add Positions dialog — add multiple positions at once."""

import re
from dataclasses import dataclass, field
from datetime import datetime

from src.data_fetch import load_stock_options


def parse_date(raw: str) -> str | None:
    """Parse a date string in various formats, return YYYY-MM-DD or None.

    Priority: ISO > European (DD.MM, DD/MM, DD-MM) > US (MM/DD).
    Disambiguation: if both values <= 12, defaults to European (DD/MM)
    since the app targets European investors.
    """
    if not raw or not raw.strip():
        return None
    raw = raw.strip()

    # ISO format: YYYY-MM-DD
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", raw)
    if m:
        y, mo, d = int(m[1]), int(m[2]), int(m[3])
        return _validate_and_format(y, mo, d)

    # Separated format: A.B.C or A/B/C or A-B-C (non-ISO)
    m = re.match(r"^(\d{1,2})[./\-](\d{1,2})[./\-](\d{2,4})$", raw)
    if m:
        a, b, c = int(m[1]), int(m[2]), int(m[3])
        year = c if c > 99 else 2000 + c

        # If first value > 12, it must be a day (European: DD/MM/YYYY)
        if a > 12:
            return _validate_and_format(year, b, a)
        # If second value > 12, it must be a day — so first is month (US: MM/DD/YYYY)
        if b > 12:
            return _validate_and_format(year, a, b)
        # Both <= 12: default European (DD/MM/YYYY)
        return _validate_and_format(year, b, a)

    return None


def _validate_and_format(year: int, month: int, day: int) -> str | None:
    """Validate date components and return YYYY-MM-DD string or None."""
    try:
        dt = datetime(year, month, day)
        return dt.strftime("%Y-%m-%d")
    except (ValueError, OverflowError):
        return None


def format_date_confirm(iso_date: str) -> str:
    """Convert YYYY-MM-DD to human-readable 'D-Mon-YYYY' for confirmation."""
    try:
        dt = datetime.strptime(iso_date, "%Y-%m-%d")
        return f"{dt.day}-{dt.strftime('%b')}-{dt.year}"
    except (ValueError, TypeError):
        return "Invalid"


# ---------------------------------------------------------------------------
# Ticker resolution
# ---------------------------------------------------------------------------

_ALT_ASSET_LISTS = {"Crypto", "Commodities"}


@dataclass
class TickerMatch:
    status: str  # "resolved" | "ambiguous" | "not_found"
    ticker: str | None = None
    label: str | None = None
    is_alt: bool = False
    market: str | None = None
    matches: list[dict] = field(default_factory=list)


def resolve_ticker(query: str) -> TickerMatch:
    """Resolve a user query to a ticker symbol.

    Checks cached stock option lists first (exact symbol, then fuzzy name).
    Falls back to yfinance validation if no cached match.
    """
    query = query.strip()
    if not query:
        return TickerMatch(status="not_found")

    options = load_stock_options()
    query_upper = query.upper()
    query_lower = query.lower()

    # Pass 1: exact symbol match
    for market, tickers in options.items():
        if query_upper in tickers:
            return TickerMatch(
                status="resolved",
                ticker=query_upper,
                label=tickers[query_upper],
                is_alt=market in _ALT_ASSET_LISTS,
                market=market,
            )

    # Pass 2: fuzzy name search
    matches = []
    for market, tickers in options.items():
        for symbol, label in tickers.items():
            if query_lower in label.lower() or query_lower in symbol.lower():
                matches.append({
                    "ticker": symbol,
                    "label": label,
                    "market": market,
                    "is_alt": market in _ALT_ASSET_LISTS,
                })

    if len(matches) == 1:
        m = matches[0]
        return TickerMatch(
            status="resolved",
            ticker=m["ticker"],
            label=m["label"],
            is_alt=m["is_alt"],
            market=m["market"],
        )
    if len(matches) > 1:
        return TickerMatch(status="ambiguous", matches=matches)

    # Pass 3: yfinance fallback
    name = _validate_via_yfinance(query_upper)
    if name:
        return TickerMatch(
            status="resolved",
            ticker=query_upper,
            label=f"{name} ({query_upper})",
            is_alt=False,
        )

    return TickerMatch(status="not_found")


def _validate_via_yfinance(ticker: str) -> str | None:
    """Check if a ticker exists on Yahoo Finance. Returns company name or None."""
    from src.data_fetch import get_provider

    try:
        hist = get_provider().get_price_history_short(ticker)
        if hist.empty:
            return None
        info = get_provider().get_fundamentals(ticker)
        return info.get("shortName") or ticker
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Row state model
# ---------------------------------------------------------------------------


@dataclass
class BulkRow:
    """State model for one row in the bulk-add table."""

    index: int
    ticker_input: str = ""
    resolved_ticker: str | None = None
    resolved_label: str | None = None
    ticker_status: str = "pending"  # pending | resolved | ambiguous | not_found
    is_alt: bool = False
    market: str | None = None
    ambiguous_matches: list[dict] = field(default_factory=list)

    shares: float = 0.0
    date_input: str = ""
    parsed_date: str | None = None
    price: float | None = None
    price_status: str = "idle"  # idle | loading | fetched | failed
    buy_fx_rate: float | None = None
    manual_price: bool = False
    _cancelled: bool = False  # for cancelling in-flight fetches

    def is_empty(self) -> bool:
        return not self.ticker_input.strip()

    def is_ready(self) -> bool:
        """True if this row can be submitted."""
        if self.ticker_status != "resolved":
            return False
        if self.is_alt:
            return self.shares > 0 and self.price is not None and self.price > 0
        return self.shares > 0 and self.price is not None

    def to_lot(self) -> dict:
        """Convert to the portfolio lot structure."""
        shares = self.shares
        if self.is_alt and self.price and self.price > 0:
            shares = round(self.shares / self.price, 6)
        return {
            "shares": shares,
            "buy_price": self.price or 0.0,
            "buy_fx_rate": self.buy_fx_rate or 1.0,
            "purchase_date": self.parsed_date,
            "manual_price": self.manual_price,
        }

    def reset_resolution(self):
        """Clear derived state when ticker input changes. Preserves shares and date."""
        self.resolved_ticker = None
        self.resolved_label = None
        self.ticker_status = "pending"
        self.is_alt = False
        self.market = None
        self.ambiguous_matches = []
        self.price = None
        self.price_status = "idle"
        self.buy_fx_rate = None
        self.manual_price = False
        self._cancelled = True  # cancel any in-flight fetches
