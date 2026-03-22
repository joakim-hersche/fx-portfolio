"""Fetch historical 10-year government bond yields by currency.

Sources:
- USD: FRED API (DGS10) — requires FRED_API_KEY env var
- EUR: Riksbank API (DEGVB10Y, German Bund)
- GBP: Riksbank API (GBGVB10Y, UK Gilt)
- SEK: Riksbank API (SEGVB10YC)
- CHF: SNB API (rendoblid 10Y Confederation bond)
"""

import logging
import os

import pandas as pd
import requests
from cachetools import cached

from src.cache import long_cache_risk_free

_log = logging.getLogger(__name__)

# ── Currency → fetcher dispatch ──────────────────────────────────────

_RISK_FREE_LABEL = {
    "USD": "10Y Treasury",
    "EUR": "10Y Bund",
    "GBP": "10Y Gilt",
    "CHF": "10Y Confed.",
    "SEK": "10Y Gov. Bond",
}

_RIKSBANK_SERIES = {
    "EUR": "DEGVB10Y",
    "GBP": "GBGVB10Y",
    "SEK": "SEGVB10YC",
}


def risk_free_label(currency: str) -> str:
    """Human-readable label for the risk-free instrument."""
    return _RISK_FREE_LABEL.get(currency, "10Y Bond")


@cached(long_cache_risk_free)
def fetch_risk_free_yields(currency: str, start: str, end: str) -> pd.Series:
    """Return daily 10Y government bond yields (annualized %) for currency.

    Returns empty Series if the API is unavailable or the currency is
    unsupported. Values are forward-filled across weekends/holidays.
    """
    try:
        if currency == "USD":
            raw = _fetch_fred(start, end)
        elif currency in _RIKSBANK_SERIES:
            raw = _fetch_riksbank(currency, start, end)
        elif currency == "CHF":
            raw = _fetch_snb(start, end)
        else:
            return pd.Series(dtype=float)

        if raw.empty:
            return raw

        # Forward-fill weekends/holidays, then drop leading NaNs
        full_range = pd.date_range(start=raw.index.min(), end=raw.index.max(), freq="D")
        filled = raw.reindex(full_range).ffill().dropna()
        filled.index.name = "Date"
        return filled

    except Exception as exc:
        _log.warning("Risk-free fetch failed for %s: %s", currency, exc)
        return pd.Series(dtype=float)


# ── FRED (USD) ───────────────────────────────────────────────────────

def _fetch_fred(start: str, end: str) -> pd.Series:
    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        _log.debug("FRED_API_KEY not set — risk-free rate unavailable for USD")
        return pd.Series(dtype=float)

    resp = requests.get(
        "https://api.fred.stlouisfed.org/series/observations",
        params={
            "series_id": "DGS10",
            "api_key": api_key,
            "file_type": "json",
            "observation_start": start,
            "observation_end": end,
        },
        timeout=15,
    )
    resp.raise_for_status()

    rows = resp.json().get("observations", [])
    data = [(r["date"], float(r["value"])) for r in rows if r["value"] != "."]
    if not data:
        return pd.Series(dtype=float)

    dates, values = zip(*data)
    return pd.Series(values, index=pd.to_datetime(dates), dtype=float)


# ── Riksbank (EUR, GBP, SEK) ────────────────────────────────────────

def _fetch_riksbank(currency: str, start: str, end: str) -> pd.Series:
    series_id = _RIKSBANK_SERIES.get(currency)
    if not series_id:
        return pd.Series(dtype=float)

    try:
        resp = requests.get(
            f"https://api.riksbank.se/swea/v1/Observations/{series_id}/{start}/{end}",
            timeout=15,
        )
        resp.raise_for_status()

        rows = resp.json()
        if not rows:
            return pd.Series(dtype=float)

        data = [(r["date"], float(r["value"])) for r in rows if r.get("value") is not None]
        if not data:
            return pd.Series(dtype=float)

        dates, values = zip(*data)
        return pd.Series(values, index=pd.to_datetime(dates), dtype=float)

    except Exception as exc:
        _log.warning("Riksbank fetch failed for %s: %s", currency, exc)
        return pd.Series(dtype=float)


# ── SNB (CHF) ────────────────────────────────────────────────────────

def _fetch_snb(start: str, end: str) -> pd.Series:
    try:
        resp = requests.get(
            "https://data.snb.ch/api/cube/rendoblid/data/csv/en",
            params={"dimSel": "D0(10J0)", "fromDate": start, "toDate": end},
            timeout=15,
        )
        resp.raise_for_status()

        from io import StringIO
        # Skip the 2-line header + blank line; actual data starts at line 4
        lines = resp.text.strip().split("\n")
        # Find the header row with "Date"
        header_idx = next(i for i, line in enumerate(lines) if '"Date"' in line)
        csv_data = "\n".join(lines[header_idx:])

        df = pd.read_csv(StringIO(csv_data), sep=";", quotechar='"')
        # Drop rows with empty/missing Value
        df = df.dropna(subset=["Value"])
        df = df[df["Value"].astype(str).str.strip() != ""]

        dates = pd.to_datetime(df["Date"])
        values = pd.to_numeric(df["Value"], errors="coerce")
        series = pd.Series(values.values, index=dates, dtype=float).dropna()
        return series

    except Exception as exc:
        _log.warning("SNB fetch failed: %s", exc)
        return pd.Series(dtype=float)
