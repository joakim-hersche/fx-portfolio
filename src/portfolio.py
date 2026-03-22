import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import yfinance as yf

_log = logging.getLogger(__name__)
import pandas as pd
from cachetools import cached

from src.cache import short_cache, long_cache, long_cache_splits, lenient_key
from src.fx import get_ticker_currency, get_fx_rate, get_historical_fx_rate


def compute_analytics(
    portfolio: dict,
    price_data: dict,
    bench_data: pd.DataFrame,
    base_currency: str = "USD",
) -> pd.DataFrame:
    """
    Compute per-ticker risk analytics from 1-year price history.
    price_data: {ticker: DataFrame with 'Close' column}
    bench_data: DataFrame with 'Close' column (currency-specific benchmark)
    base_currency: user's base currency (for risk-free rate + benchmark selection)
    Returns DataFrame with columns: Ticker, Volatility, Max Drawdown, Sharpe Ratio, Beta
    """
    from src.risk_free import fetch_risk_free_yields

    # Dynamic risk-free rate from 10Y government bonds
    try:
        end_date = str(pd.Timestamp.today().date())
        start_date = str((pd.Timestamp.today() - pd.DateOffset(years=1)).date())
        yields = fetch_risk_free_yields(base_currency, start_date, end_date)
        if not yields.empty:
            avg_annual_rf = yields.mean() / 100
        else:
            avg_annual_rf = 0.04  # fallback
    except Exception:
        avg_annual_rf = 0.04

    bench_returns = pd.Series(dtype=float)
    if not bench_data.empty and "Close" in bench_data.columns:
        bench_returns = bench_data["Close"].pct_change().dropna()

    rows = []
    for ticker in portfolio:
        hist = price_data.get(ticker)
        if hist is None or hist.empty or "Close" not in hist.columns:
            continue
        prices = hist["Close"].dropna()
        if len(prices) < 30:
            continue

        daily_returns = prices.pct_change().dropna()

        # Annualised volatility
        volatility = daily_returns.std() * (252 ** 0.5)

        # Max drawdown
        rolling_max = prices.cummax()
        drawdown = (prices - rolling_max) / rolling_max
        max_drawdown = float(drawdown.min())

        # Sharpe ratio (annualised, dynamic risk-free rate)
        daily_rf = avg_annual_rf / 252
        excess = daily_returns - daily_rf
        sharpe = float((excess.mean() / excess.std()) * (252 ** 0.5)) if excess.std() > 0 else None

        # Beta vs currency-specific benchmark
        beta = None
        if not bench_returns.empty:
            aligned = pd.concat([daily_returns, bench_returns], axis=1, join="inner").dropna()
            aligned.columns = ["stock", "bench"]
            if len(aligned) >= 30 and aligned["bench"].var() > 0:
                beta = float(aligned["stock"].cov(aligned["bench"]) / aligned["bench"].var())

        rows.append({
            "Ticker":       ticker,
            "Volatility":   round(volatility * 100, 1),
            "Max Drawdown": round(max_drawdown * 100, 1),
            "Sharpe Ratio": round(sharpe, 2) if sharpe is not None else None,
            "Beta":         round(beta, 2) if beta is not None else None,
        })

    return pd.DataFrame(rows) if rows else pd.DataFrame()

@cached(long_cache)
def _dividends_in_base_currency(
    ticker: str,
    purchase_date: str,
    from_currency: str,
    base_currency: str,
) -> float:
    """Sum dividends per share from purchase_date to today, converted at historical FX rates."""
    try:
        today = str(pd.Timestamp.today().date())
        ticker_obj = yf.Ticker(ticker)
        hist = ticker_obj.history(start=purchase_date, end=today)
        if hist.empty or "Dividends" not in hist.columns:
            return 0.0

        dividends = hist["Dividends"]
        dividends = dividends[dividends > 0]
        if dividends.empty:
            return 0.0

        if from_currency == base_currency:
            return float(dividends.sum())

        gbx = from_currency == "GBX"
        fx_from = "GBP" if gbx else from_currency
        fx_pair = f"{fx_from}{base_currency}=X"

        fx_hist = yf.Ticker(fx_pair).history(start=purchase_date, end=today)
        if fx_hist.empty:
            fallback, _ = get_fx_rate(from_currency, base_currency)
            return float(dividends.sum() * fallback)

        fx_series = fx_hist["Close"].reindex(dividends.index, method="ffill")
        # For dividends paid before FX history starts, use the earliest
        # available rate rather than bfill() which would pull a future rate.
        earliest_rate = fx_hist["Close"].iloc[0]
        fx_series = fx_series.fillna(earliest_rate)
        if gbx:
            fx_series = fx_series / 100

        return float((dividends * fx_series).sum())
    except Exception as exc:
        _log.warning("Dividend fetch failed for %s (from %s): %s", ticker, purchase_date, exc)
        return 0.0


@cached(long_cache_splits)
def get_split_factor(ticker: str, purchase_date: str) -> float:
    """Cumulative stock-split ratio after *purchase_date* for *ticker*.

    Returns the product of all split factors that occurred after the purchase
    date.  E.g. a 5-for-1 split returns 5.0; a 5-for-1 followed by a 2-for-1
    returns 10.0.  Returns 1.0 when there are no splits, the purchase date is
    unknown, or on any fetch error.
    """
    if not purchase_date or purchase_date == "Manual":
        return 1.0
    try:
        splits = yf.Ticker(ticker).splits
        if splits.empty:
            return 1.0
        after = splits[splits.index.tz_localize(None) > pd.Timestamp(purchase_date)]
        if after.empty:
            return 1.0
        return float(after.prod())
    except Exception:
        return 1.0


@cached(short_cache, key=lenient_key)
def build_portfolio_df(portfolio: dict, base_currency: str) -> pd.DataFrame:
    """
    Convert raw portfolio session state into a display-ready DataFrame.
    All prices are converted to base_currency.
    """
    rows = []
    tickers = list(portfolio.keys())
    if not tickers:
        return pd.DataFrame()

    # Batch-fetch all ticker prices in a single HTTP request
    batch_data = yf.download(tickers, period="5d", group_by="ticker", progress=False, threads=True)

    # Fetch FX rates and dividends in parallel
    def _fetch_extras(ticker):
        ticker_ccy = get_ticker_currency(ticker)
        fx_rate, fx_ok = get_fx_rate(ticker_ccy, base_currency)
        div_cache = {}
        for lot in portfolio[ticker]:
            pd_date = lot.get("purchase_date")
            if pd_date and pd_date != "Manual" and pd_date not in div_cache:
                div_cache[pd_date] = _dividends_in_base_currency(ticker, pd_date, ticker_ccy, base_currency)
        return ticker, fx_rate, div_cache, fx_ok

    extras = {}
    with ThreadPoolExecutor(max_workers=min(10, len(tickers))) as executor:
        futures = {executor.submit(_fetch_extras, t): t for t in tickers}
        for future in as_completed(futures):
            try:
                ticker, fx_rate, div_cache, fx_ok = future.result()
                extras[ticker] = (fx_rate, div_cache, fx_ok)
            except Exception:
                continue

    for ticker, lots in portfolio.items():
        # Extract this ticker's data from the batch result
        if len(tickers) == 1:
            data = batch_data
        else:
            try:
                data = batch_data[ticker]
            except (KeyError, TypeError):
                continue
        if data.empty or "Close" not in data.columns:
            continue
        close = data["Close"].dropna()
        if len(close) < 2:
            continue

        extra = extras.get(ticker)
        if extra is None:
            continue
        fx_rate, div_cache, fx_ok = extra

        current_price = float(close.iloc[-1]) * fx_rate
        prev_price = float(close.iloc[-2]) * fx_rate

        for i, lot in enumerate(lots):
            shares = lot["shares"]
            # Use purchase-date FX rate if stored; fall back to current rate for
            # legacy lots that pre-date this field.
            lot_fx = lot.get("buy_fx_rate", fx_rate)
            buy_price = lot["buy_price"] * lot_fx
            purchase_date = lot["purchase_date"]

            split_factor = get_split_factor(ticker, purchase_date)
            adjusted_shares = shares * split_factor

            dividends_per_share = (
                div_cache.get(purchase_date, 0.0)
                if purchase_date and purchase_date != "Manual"
                else 0.0
            )
            total_dividends = round(dividends_per_share * shares, 2)
            cost_basis = buy_price * shares  # what you paid — independent of splits

            rows.append({
                "Ticker": ticker,
                "Purchase": i + 1,
                "Shares": adjusted_shares,
                "Buy Price": round(buy_price, 2),
                "Purchase Date": purchase_date or "Manual",
                "Current Price": round(current_price, 2),
                "Total Value": round(current_price * adjusted_shares, 2),
                "Dividends": total_dividends,
                "Daily P&L": round((current_price - prev_price) * adjusted_shares, 2),
                "Return (%)": round(
                    (current_price * adjusted_shares + total_dividends - cost_basis) / cost_basis * 100, 2
                ) if cost_basis else None,
            })

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df["Weight (%)"] = (df["Total Value"] / df["Total Value"].sum() * 100).round(2)
    df.attrs["fx_warnings"] = [t for t in extras if not extras[t][2]]
    return df


def build_contribution_timeline(portfolio: dict, base_currency: str) -> pd.DataFrame:
    """Build a daily DataFrame with cumulative cost basis and portfolio market value.

    Returns DataFrame indexed by date with columns:
        - "Contributed": cumulative cost basis over time
        - "Portfolio Value": portfolio market value over time
    """
    from src.data_fetch import fetch_price_history_long

    if not portfolio:
        return pd.DataFrame()

    today_str = str(pd.Timestamp.today().date())

    # Collect all lots with their dates and cost info
    lots_info: list[dict] = []
    tickers_needed: set[str] = set()
    for ticker, lots in portfolio.items():
        for lot in lots:
            purchase_date = lot.get("purchase_date")
            if not purchase_date or purchase_date == "Manual":
                purchase_date = today_str
            shares = lot["shares"]
            buy_price = lot.get("buy_price", 0)
            ticker_ccy = get_ticker_currency(lot["ticker"] if "ticker" in lot else ticker)
            fallback_fx, _ = get_fx_rate(ticker_ccy, base_currency)
            buy_fx_rate = lot.get("buy_fx_rate", fallback_fx)
            cost = shares * buy_price * buy_fx_rate
            lots_info.append({
                "ticker": ticker,
                "date": purchase_date,
                "shares": shares,
                "cost": cost,
            })
            tickers_needed.add(ticker)

    if not lots_info:
        return pd.DataFrame()

    # Fetch price histories in parallel
    tickers_list = list(tickers_needed)
    with ThreadPoolExecutor(max_workers=min(10, len(tickers_list))) as ex:
        hist_results = dict(ex.map(
            lambda t: (t, fetch_price_history_long(t)), tickers_list
        ))

    # Determine date range
    all_dates = [lot["date"] for lot in lots_info]
    start_date = pd.Timestamp(min(all_dates))
    end_date = pd.Timestamp.today()

    # Build cumulative cost basis series
    cost_events = pd.Series(dtype=float)
    for lot in lots_info:
        dt = pd.Timestamp(lot["date"])
        if dt in cost_events.index:
            cost_events[dt] += lot["cost"]
        else:
            cost_events[dt] = lot["cost"]
    cost_events = cost_events.sort_index()

    # Build daily date range
    date_range = pd.date_range(start=start_date, end=end_date, freq="B")
    if date_range.empty:
        return pd.DataFrame()

    # Cumulative contributions
    contributed = cost_events.reindex(date_range, fill_value=0).cumsum()

    # Portfolio value: sum of (shares * price * fx_rate) for each lot active on that date
    # Group lots by ticker for efficiency
    from collections import defaultdict
    ticker_lots: dict[str, list[dict]] = defaultdict(list)
    for lot in lots_info:
        ticker_lots[lot["ticker"]].append(lot)

    portfolio_value = pd.Series(0.0, index=date_range)

    for ticker, lots in ticker_lots.items():
        hist = hist_results.get(ticker)
        if hist is None or hist.empty or "Close" not in hist.columns:
            continue

        prices = hist["Close"].dropna()
        prices = prices.reindex(date_range, method="ffill")

        # Get historical FX series for this ticker
        ticker_ccy = get_ticker_currency(ticker)
        if ticker_ccy == base_currency:
            fx_series = pd.Series(1.0, index=date_range)
        else:
            fx_from = "GBP" if ticker_ccy == "GBX" else ticker_ccy
            fx_pair = f"{fx_from}{base_currency}=X"
            fx_hist_data = fetch_price_history_long(fx_pair)
            if not fx_hist_data.empty and "Close" in fx_hist_data.columns:
                fx_series = fx_hist_data["Close"].reindex(date_range, method="ffill")
                if ticker_ccy == "GBX":
                    fx_series = fx_series / 100
                current_fx, _ = get_fx_rate(ticker_ccy, base_currency)
                fx_series = fx_series.fillna(current_fx)
            else:
                current_fx, _ = get_fx_rate(ticker_ccy, base_currency)
                fx_series = pd.Series(current_fx, index=date_range)

        for lot in lots:
            lot_date = pd.Timestamp(lot["date"])
            # Only count this lot's value from its purchase date onwards
            mask = date_range >= lot_date
            lot_value = prices * lot["shares"] * fx_series
            lot_value = lot_value.where(mask, 0)
            portfolio_value += lot_value.fillna(0)

    result = pd.DataFrame({
        "Contributed": contributed,
        "Portfolio Value": portfolio_value,
    })
    # Drop rows where both are zero (before first purchase)
    result = result.loc[(result != 0).any(axis=1)]
    return result


def fetch_buy_price(ticker: str, purchase_date: str) -> tuple[float, str] | None:
    """
    Fetch closing price on or just after a given purchase date.

    Returns (price, actual_date_str) so callers can detect when the market
    was closed on the requested date and the next trading day was used instead.
    Returns None if no price data is found within 7 days.
    """
    try:
        end = str((pd.Timestamp(purchase_date) + pd.DateOffset(days=7)).date())
        hist = yf.Ticker(ticker).history(start=purchase_date, end=end)
        if hist.empty:
            return None
        actual_date = str(hist.index[0].date())
        return round(hist["Close"].iloc[0], 2), actual_date
    except Exception:
        return None


def build_dividend_timeline(
    portfolio: dict,
    base_currency: str,
    months_back: int = 24,
) -> list[dict]:
    """Return monthly dividend payments bucketed by ticker, converted to base currency.

    Each entry: {"month": "2025-01", "ticker": "AAPL", "amount": 12.34}
    Only includes months where a dividend was actually paid.
    """
    cutoff = pd.Timestamp.today() - pd.DateOffset(months=months_back)
    cutoff_str = str(cutoff.date())
    today_str = str(pd.Timestamp.today().date())
    rows: list[dict] = []

    for ticker, lots in portfolio.items():
        ticker_ccy = get_ticker_currency(ticker)
        gbx = ticker_ccy == "GBX"

        try:
            hist = yf.Ticker(ticker).history(start=cutoff_str, end=today_str)
            if hist.empty or "Dividends" not in hist.columns:
                continue
            divs = hist["Dividends"]
            divs = divs[divs > 0]
            if divs.empty:
                continue

            for date, amount in divs.items():
                date_str = str(date.date()) if hasattr(date, "date") else str(date)[:10]
                month_key = date_str[:7]  # "YYYY-MM"

                # Only count shares from lots purchased on or before this dividend date
                shares_held = sum(
                    lot["shares"] for lot in lots
                    if lot.get("purchase_date") and lot["purchase_date"] <= date_str
                )
                if shares_held <= 0:
                    continue

                if ticker_ccy == base_currency:
                    fx = 1.0
                else:
                    fx = get_historical_fx_rate(ticker_ccy, base_currency, date_str)

                converted = amount * fx * shares_held
                rows.append({"month": month_key, "ticker": ticker, "amount": round(converted, 2)})
        except Exception:
            continue

    return rows