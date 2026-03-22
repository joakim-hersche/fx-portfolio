"""Bulk Add Positions dialog — add multiple positions at once."""

import re
from datetime import datetime


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
