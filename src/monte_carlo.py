"""
Monte Carlo simulation for portfolio value projection and backtesting.

price_data expected format: {ticker: pd.DataFrame with a 'Close' column, DatetimeIndex}

For the backtest, pass 5-year history (period="5y") so there is enough training
data before the 1-year test window. Fetch with a separate cached function in app.py:

    @st.cache_data(ttl=86400)
    def fetch_simulation_history(ticker: str) -> pd.DataFrame:
        hist = yf.Ticker(ticker).history(period="5y")
        hist.index = hist.index.tz_localize(None)
        return hist
"""

import numpy as np
import pandas as pd


# ── Helpers ───────────────────────────────────────────────────────────────────

def _total_shares(portfolio: dict) -> dict:
    """Sum shares across all lots per ticker."""
    return {
        ticker: sum(lot["shares"] for lot in lots)
        for ticker, lots in portfolio.items()
    }


def _build_log_returns(price_data: dict, tickers: list) -> pd.DataFrame:
    """
    Build an aligned log-return DataFrame for the given tickers.
    Uses inner join — only dates where all tickers have prices are kept.
    """
    closes = {}
    for t in tickers:
        hist = price_data.get(t)
        if hist is not None and not hist.empty and "Close" in hist.columns:
            closes[t] = hist["Close"].dropna()
    if not closes:
        return pd.DataFrame()
    prices = pd.DataFrame(closes).dropna()
    return np.log(prices / prices.shift(1)).dropna()


def _simulate_paths(
    mean_log: np.ndarray,
    cov_log: np.ndarray,
    start_prices: np.ndarray,
    shares: np.ndarray,
    n_sims: int,
    horizon_days: int,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Simulate correlated log-normal price paths for N tickers.

    Uses Cholesky decomposition to preserve the historical correlation structure.
    Falls back to diagonal (independent) simulation if the covariance matrix is
    not positive definite (can happen with very short history or near-constant assets).

    Returns
    -------
    portfolio_paths : ndarray, shape (n_sims, horizon_days)
        Combined portfolio value per simulation per day.
    ticker_paths : ndarray, shape (n_sims, horizon_days, N)
        Individual ticker price per simulation per day.
    """
    N = len(mean_log)
    cov_stable = cov_log + np.eye(N) * 1e-8  # nudge diagonal for numerical stability

    try:
        L = np.linalg.cholesky(cov_stable)
    except np.linalg.LinAlgError:
        # Correlation structure is degenerate — simulate independently
        L = np.diag(np.sqrt(np.maximum(np.diag(cov_stable), 0)))

    # Z: (n_sims, horizon_days, N) — standard normal shocks
    Z = rng.standard_normal((n_sims, horizon_days, N))
    # Correlated daily log returns: (n_sims, horizon_days, N)
    log_returns = Z @ L.T + mean_log  # mean broadcast across sims and days

    # Cumulative log price change from start
    log_price_paths = np.log(start_prices) + np.cumsum(log_returns, axis=1)
    ticker_paths = np.exp(log_price_paths)  # (n_sims, horizon_days, N)

    portfolio_paths = (ticker_paths * shares).sum(axis=2)  # (n_sims, horizon_days)
    return portfolio_paths, ticker_paths


# ── Distribution flags ────────────────────────────────────────────────────────

def compute_distribution_flags(price_data: dict) -> dict:
    """
    Compute excess kurtosis and skewness of log-returns per ticker.

    Excess kurtosis > 3 indicates fat-tailed returns — the core assumption
    the Gaussian Monte Carlo model violates. When fat tails are present,
    the confidence bands will underestimate tail risk.

    Returns
    -------
    {ticker: {"kurtosis": float, "skewness": float, "fat_tailed": bool}}
    """
    flags = {}
    for ticker, hist in price_data.items():
        if hist is None or hist.empty or "Close" not in hist.columns:
            continue
        log_r = np.log(hist["Close"].dropna() / hist["Close"].dropna().shift(1)).dropna()
        if len(log_r) < 60:
            continue
        kurt = float(log_r.kurt())   # pandas .kurt() returns excess kurtosis (normal = 0)
        skew = float(log_r.skew())
        flags[ticker] = {
            "kurtosis":  round(kurt, 2),
            "skewness":  round(skew, 2),
            "fat_tailed": kurt > 3,
        }
    return flags


# ── Backtest ──────────────────────────────────────────────────────────────────

def run_monte_carlo_backtest(
    portfolio: dict,
    price_data: dict,
    n_sims: int = 1000,
    seed: int = 42,
) -> dict:
    """
    Validate the Monte Carlo model against the past year of actual data.

    Splits the available price history at the 1-year mark:
      - Training window: everything before 1 year ago (calibrate μ and Σ)
      - Test window:     last 252 trading days (simulate then compare to actual)

    This avoids look-ahead bias — the simulation only sees data that would
    have been available at the split date.

    Parameters
    ----------
    portfolio : dict
        Session-state portfolio {ticker: [{"shares": N, ...}, ...]}.
    price_data : dict
        {ticker: DataFrame with 'Close' column}. Should be 5-year history
        so there is a meaningful training window before the 1-year test.
    n_sims : int
        Number of simulation paths.
    seed : int
        Random seed for reproducibility.

    Returns
    -------
    dict with keys:
        sim_dates        — DatetimeIndex, the 252-day test window
        percentiles      — DataFrame(p10, p25, p50, p75, p90), portfolio value
        actual           — Series, actual portfolio value over the test window
        start_value      — float, portfolio value at the split date
        hit_rate_80      — float (0–100), % of days actual fell within p10–p90
        hit_rate_50      — float (0–100), % of days actual fell within p25–p75
        ticker_hit_rates — {ticker: {"hit_rate_80": float, "hit_rate_50": float}}
        ticker_flags     — {ticker: {"kurtosis": float, "skewness": float, "fat_tailed": bool}}
        tickers_used     — list[str], tickers included (those with sufficient history)
        split_date       — date, where training ended and simulation started
        train_days       — int, number of trading days in the training window

    Returns empty dict if there is insufficient data.
    """
    shares_by_ticker = _total_shares(portfolio)
    candidate_tickers = [t for t in shares_by_ticker if t in price_data]

    # Need at least 252 training days + 252 test days.
    # Pre-filter by INDIVIDUAL ticker history length before building the joint
    # matrix. Without this, a recently-listed ticker would silently truncate the
    # inner-join window for every other ticker — the post-join count check is a
    # no-op because .dropna() makes all columns the same length.
    MIN_TOTAL = 504
    valid_tickers = [
        t for t in candidate_tickers
        if (
            price_data.get(t) is not None
            and not price_data[t].empty
            and "Close" in price_data[t].columns
            and price_data[t]["Close"].dropna().shape[0] >= MIN_TOTAL
        )
    ]
    if not valid_tickers:
        return {}

    log_returns_all = _build_log_returns(price_data, valid_tickers)

    # Final guard: the inner join may still shorten the window if trading
    # calendars differ (e.g. crypto vs equities). Bail if that happens.
    if log_returns_all.empty or len(log_returns_all) < MIN_TOTAL:
        return {}

    # ── Split ──────────────────────────────────────────────────────────────
    split_idx   = len(log_returns_all) - 252
    train_log_r = log_returns_all.iloc[:split_idx]
    test_log_r  = log_returns_all.iloc[split_idx:]     # 252 rows
    split_date  = train_log_r.index[-1]

    # ── Training statistics ────────────────────────────────────────────────
    mean_log   = train_log_r.mean().values
    cov_log    = train_log_r.cov().values

    # ── Starting prices at the split date ─────────────────────────────────
    # Build aligned price DataFrame
    price_df = pd.DataFrame({
        t: price_data[t]["Close"].dropna() for t in valid_tickers
    }).dropna()

    split_prices = price_df.loc[:split_date].iloc[-1].values
    shares       = np.array([shares_by_ticker[t] for t in valid_tickers])
    start_value  = float((split_prices * shares).sum())

    # ── Simulate ───────────────────────────────────────────────────────────
    rng = np.random.default_rng(seed)
    portfolio_paths, ticker_paths = _simulate_paths(
        mean_log, cov_log, split_prices, shares, n_sims, 252, rng
    )

    # ── Actual portfolio value during the test window ──────────────────────
    test_prices = price_df.loc[price_df.index.isin(test_log_r.index)].iloc[:252]
    actual_values = (test_prices[valid_tickers].values * shares).sum(axis=1)
    actual = pd.Series(actual_values, index=test_prices.index)
    n_actual = len(actual)

    # ── Portfolio-level percentile bands ──────────────────────────────────
    pcts = np.percentile(portfolio_paths[:, :n_actual], [10, 25, 50, 75, 90], axis=0)
    percentiles = pd.DataFrame(
        pcts.T,
        columns=["p10", "p25", "p50", "p75", "p90"],
        index=actual.index,
    )

    # ── Portfolio-level hit rates ──────────────────────────────────────────
    within_80 = ((actual >= percentiles["p10"]) & (actual <= percentiles["p90"])).mean()
    within_50 = ((actual >= percentiles["p25"]) & (actual <= percentiles["p75"])).mean()

    # ── Per-ticker hit rates ───────────────────────────────────────────────
    ticker_hit_rates = {}
    for i, ticker in enumerate(valid_tickers):
        t_paths  = ticker_paths[:, :n_actual, i]   # (n_sims, n_actual)
        t_actual = test_prices[ticker].values

        t_p10 = np.percentile(t_paths, 10, axis=0)
        t_p90 = np.percentile(t_paths, 90, axis=0)
        t_p25 = np.percentile(t_paths, 25, axis=0)
        t_p75 = np.percentile(t_paths, 75, axis=0)

        ticker_hit_rates[ticker] = {
            "hit_rate_80": round(float(((t_actual >= t_p10) & (t_actual <= t_p90)).mean()) * 100, 1),
            "hit_rate_50": round(float(((t_actual >= t_p25) & (t_actual <= t_p75)).mean()) * 100, 1),
        }

    return {
        "sim_dates":        actual.index,
        "percentiles":      percentiles,
        "actual":           actual,
        "start_value":      start_value,
        "hit_rate_80":      round(float(within_80) * 100, 1),
        "hit_rate_50":      round(float(within_50) * 100, 1),
        "ticker_hit_rates": ticker_hit_rates,
        "ticker_flags":     compute_distribution_flags({t: price_data[t] for t in valid_tickers}),
        "tickers_used":     valid_tickers,
        "split_date":       split_date.date(),
        "train_days":       len(train_log_r),
    }


# ── Per-ticker forward simulation ─────────────────────────────────────────────

def run_monte_carlo_ticker(
    hist: pd.DataFrame,
    current_price: float,
    n_sims: int = 1000,
    horizon_days: int = 252,
    lookback_days: int | None = None,
    seed: int = 42,
) -> dict:
    """
    Forward-looking Monte Carlo simulation for a single ticker.

    Log-returns are estimated from `hist` (up to `lookback_days` of history),
    then projected forward from `current_price` — which should already be
    FX-converted to the user's base currency. Because returns are ratios,
    the distribution calibration is currency-agnostic; only the starting
    price needs to be in the display currency.

    Parameters
    ----------
    hist : pd.DataFrame
        Price history with a 'Close' column (from fetch_simulation_history).
    current_price : float
        Current price in base currency (FX-adjusted). Used as simulation start.
    n_sims : int
        Number of simulation paths.
    horizon_days : int
        Number of trading days to simulate forward.
    lookback_days : int or None
        If set, only the last N days of history are used for calibration.
        None uses all available history.
    seed : int
        Random seed.

    Returns
    -------
    dict with keys:
        dates         — DatetimeIndex, future trading dates
        percentiles   — DataFrame(p10, p25, p50, p75, p90), price levels
        end_paths     — ndarray (n_sims,), simulated end prices
        start_price   — float, current_price used as starting point
        mu_annual     — float, annualised expected return used (%)
        sigma_annual  — float, annualised volatility used (%)
        flag          — dict from compute_distribution_flags (kurtosis, skewness, fat_tailed)
        train_days    — int, number of days used for calibration

    Returns empty dict if insufficient data.
    """
    if hist is None or hist.empty or "Close" not in hist.columns:
        return {}

    prices = hist["Close"].dropna()
    if lookback_days is not None:
        prices = prices.iloc[-lookback_days:]
    if len(prices) < 60:
        return {}

    log_r = np.log(prices / prices.shift(1)).dropna()
    mu    = float(log_r.mean())
    sigma = float(log_r.std())

    rng  = np.random.default_rng(seed)
    Z    = rng.standard_normal((n_sims, horizon_days))
    # Daily log-return paths: μ + σ·Z
    daily = mu + sigma * Z                                      # (n_sims, horizon_days)
    paths = current_price * np.exp(np.cumsum(daily, axis=1))   # (n_sims, horizon_days)

    last_date   = prices.index[-1]
    future_dates = pd.bdate_range(start=last_date, periods=horizon_days + 1)[1:]

    pcts = np.percentile(paths, [10, 25, 50, 75, 90], axis=0)
    percentiles = pd.DataFrame(
        pcts.T,
        columns=["p10", "p25", "p50", "p75", "p90"],
        index=future_dates,
    )

    flag = compute_distribution_flags({"_": hist}).get("_", {})

    return {
        "dates":        future_dates,
        "percentiles":  percentiles,
        "end_paths":    paths[:, -1],
        "start_price":  current_price,
        "mu_annual":    round(mu * 252 * 100, 2),
        "sigma_annual": round(sigma * (252 ** 0.5) * 100, 2),
        "flag":         flag,
        "train_days":   len(log_r),
    }
