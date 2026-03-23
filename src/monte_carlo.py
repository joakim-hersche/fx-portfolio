"""Monte Carlo simulation engine for portfolio projection and backtesting.

price_data expected format: {ticker: pd.DataFrame with a 'Close' column, DatetimeIndex}

Simulation engine: GARCH(1,1) with Student-t innovations (Gaussian copula for
cross-ticker correlation). Falls back to constant-volatility normal model when
GARCH does not converge or data is insufficient.
"""

import logging
import math
from concurrent.futures import ThreadPoolExecutor
from typing import cast

import numpy as np
import pandas as pd
import scipy.stats as scipy_stats
from scipy import stats
from statsmodels.stats.diagnostic import acorr_ljungbox

logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _total_shares(portfolio: dict) -> dict:
    """Sum split-adjusted shares across all lots per ticker."""
    from src.portfolio import get_split_factor
    return {
        ticker: sum(
            lot["shares"] * get_split_factor(ticker, lot.get("purchase_date"))
            for lot in lots
        )
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


# ── GARCH fitting ─────────────────────────────────────────────────────────────

def _fit_constant_vol(log_returns: pd.Series) -> dict:
    """
    Fit constant-volatility normal model (GARCH fallback and comparison baseline).

    Internally converts to percent for numerical consistency.
    Returns the same dict structure as _fit_garch_params.
    """
    vals = np.asarray(log_returns.values) * 100  # percent units
    n = len(vals)
    mu_raw = float(log_returns.mean())
    sigma2 = float(np.var(vals))  # percent^2
    sigma = math.sqrt(max(sigma2, 1e-14))

    # Log-likelihood for constant-vol normal (k=1 free parameter: sigma^2)
    ll = -0.5 * n * (math.log(2 * math.pi) + math.log(sigma2) + 1)
    aic = 2 * 1 - 2 * ll

    std_resid = vals / sigma
    cond_vol = np.full(n, sigma)

    return {
        "mu": mu_raw,
        "omega": sigma2,
        "alpha": 0.0,
        "beta": 0.0,
        "nu": np.inf,
        "long_run_var": sigma2,
        "half_life": None,
        "persistence": 0.0,
        "last_cond_var": sigma2,
        "standardized_residuals": std_resid,
        "conditional_vol": cond_vol,
        "converged": False,
        "model": "constant-vol",
        "log_likelihood": ll,
        "aic": aic,
        "low_confidence": n < 504,
    }


def _fit_garch_params(log_returns: pd.Series) -> dict:
    """
    Fit GARCH(1,1) with Student-t innovations per ticker using the arch library.

    Falls back to _fit_constant_vol on non-convergence or insufficient data.

    Returns
    -------
    dict with keys: mu, omega, alpha, beta, nu, long_run_var, half_life,
        persistence, last_cond_var, standardized_residuals, conditional_vol,
        converged, model, log_likelihood, aic, low_confidence
    """
    n = len(log_returns)
    if n < 252:
        return _fit_constant_vol(log_returns)

    try:
        from arch import arch_model

        returns_pct = np.asarray(log_returns.values) * 100  # percent units
        mu_raw = float(log_returns.mean())

        am = arch_model(
            returns_pct,
            mean="Zero",
            vol="GARCH",
            p=1,
            q=1,
            dist="t",
            rescale=False,
        )
        result = am.fit(
            disp="off",
            show_warning=False,
            options={"maxiter": 200, "ftol": 1e-8},
        )

        omega = float(result.params["omega"])
        alpha = float(result.params["alpha[1]"])
        beta = float(result.params["beta[1]"])
        nu = float(result.params["nu"])

        # Convergence and sanity checks
        if result.convergence_flag != 0:
            return _fit_constant_vol(log_returns)
        if omega <= 0 or alpha < 0 or beta < 0 or (alpha + beta) >= 0.9999:
            return _fit_constant_vol(log_returns)

        persistence = alpha + beta
        long_run_var = omega / (1.0 - persistence) if persistence < 1.0 else None
        if 0 < persistence < 1:
            half_life = math.log(2) / -math.log(persistence)
        else:
            half_life = None

        cond_vol_pct = result.conditional_volatility  # percent units
        std_resid = returns_pct / cond_vol_pct
        last_cond_var = float(cond_vol_pct[-1] ** 2)  # percent^2

        # Log-likelihood and AIC for GARCH-t (4 free params: omega, alpha, beta, nu)
        ll = float(result.loglikelihood)
        aic = float(result.aic)

        return {
            "mu": mu_raw,
            "omega": omega,
            "alpha": alpha,
            "beta": beta,
            "nu": nu,
            "long_run_var": long_run_var,
            "half_life": half_life,
            "persistence": persistence,
            "last_cond_var": last_cond_var,
            "standardized_residuals": std_resid,
            "conditional_vol": cond_vol_pct,
            "converged": True,
            "model": "garch-t",
            "log_likelihood": ll,
            "aic": aic,
            "low_confidence": n < 504,
        }

    except Exception:
        logger.debug("GARCH fit failed for ticker, falling back to constant-vol", exc_info=True)
        return _fit_constant_vol(log_returns)


# ── GARCH simulation ──────────────────────────────────────────────────────────

def _garch_returns(
    garch_params: list,
    corr_cholesky: np.ndarray,
    n_sims: int,
    horizon_days: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """
    Generate correlated GARCH(1,1) + Student-t log-returns via Gaussian copula.

    Steps the GARCH variance recursion per ticker:
        sigma2_t = omega + alpha * eps2_{t-1} + beta * sigma2_{t-1}
        eps_t    = sigma_t * z_t   (percent units)
        log_return_t = eps_t / 100 + mu   (raw units)

    Cross-ticker correlation is imposed via Gaussian copula:
    1. Draw Z ~ N(0,I), correlate via Cholesky
    2. Convert each marginal to uniform via normal CDF
    3. Invert each ticker's Student-t CDF at that quantile

    Parameters
    ----------
    garch_params : list of dicts (one per ticker, in ticker order)
    corr_cholesky : (N, N) lower-triangular Cholesky factor of residual correlation
    n_sims : int
    horizon_days : int
    rng : np.random.Generator

    Returns
    -------
    np.ndarray, shape (n_sims, horizon_days, N)  — raw log-returns
    """
    N = len(garch_params)
    L = corr_cholesky

    mus = np.array([p["mu"] for p in garch_params])
    omegas = np.array([p["omega"] for p in garch_params])
    alphas = np.array([p["alpha"] for p in garch_params])
    betas = np.array([p["beta"] for p in garch_params])
    nus = np.array([p["nu"] for p in garch_params])

    # Initialise conditional variance from last in-sample estimate
    sigma2 = np.tile(
        np.array([p["last_cond_var"] for p in garch_params]),
        (n_sims, 1),
    ).astype(np.float64)  # shape (n_sims, N)

    eps2 = np.zeros((n_sims, N))
    log_returns_out = np.empty((n_sims, horizon_days, N))

    for t in range(horizon_days):
        # 1. Independent standard normals
        Z = rng.standard_normal((n_sims, N))
        # 2. Correlate via Cholesky
        Z_corr = Z @ L.T
        # 3. Convert each marginal to uniform
        U = scipy_stats.norm.cdf(Z_corr)
        # 4. Invert each ticker's Student-t (or normal) CDF
        z_t = np.empty_like(Z_corr)
        for i in range(N):
            nu_i = nus[i]
            if np.isinf(nu_i) or nu_i > 100:
                z_t[:, i] = Z_corr[:, i]
            else:
                z_t[:, i] = scipy_stats.t.ppf(
                    np.clip(U[:, i], 1e-10, 1 - 1e-10), df=nu_i
                )
        # 5. GARCH step (percent units)
        sigma = np.sqrt(np.maximum(sigma2, 1e-14))
        eps = sigma * z_t  # percent units

        # 6. Store raw log-returns (divide by 100 to go from pct, add mean drift)
        log_returns_out[:, t, :] = eps / 100.0 + mus

        # 7. Update variance recursion
        eps2 = eps ** 2
        sigma2 = omegas + alphas * eps2 + betas * sigma2

    return log_returns_out


def _simulate_paths(
    garch_params: list,
    corr_cholesky: np.ndarray,
    start_prices: np.ndarray,
    shares: np.ndarray,
    n_sims: int,
    horizon_days: int,
    rng: np.random.Generator,
) -> tuple:
    """
    Simulate correlated GARCH price paths for N tickers.

    Returns
    -------
    portfolio_paths : ndarray, shape (n_sims, horizon_days)
    ticker_paths    : ndarray, shape (n_sims, horizon_days, N)
    """
    log_returns = _garch_returns(garch_params, corr_cholesky, n_sims, horizon_days, rng)

    # Cumulative log price change from start
    log_price_paths = np.log(start_prices) + np.cumsum(log_returns, axis=1)
    ticker_paths = np.exp(log_price_paths)  # (n_sims, horizon_days, N)

    portfolio_paths = (ticker_paths * shares).sum(axis=2)  # (n_sims, horizon_days)
    return portfolio_paths, ticker_paths


# ── Calibration ───────────────────────────────────────────────────────────────

def _calibrate(
    price_data: dict,
    tickers: list,
    lookback_days: int | None = None,
) -> tuple:
    """
    Fit GARCH per ticker and compute standardised-residual correlation.

    Each ticker is fitted on its individual (non-inner-joined) price history
    so that shorter-history tickers do not truncate the window for others.

    Parameters
    ----------
    price_data : dict  — {ticker: DataFrame with 'Close' column}
    tickers : list     — tickers to fit (must be in price_data)
    lookback_days : int or None — if set, truncate each ticker's history

    Returns
    -------
    garch_params : list[dict]   — one dict per ticker, in tickers order
    corr_cholesky : np.ndarray  — (N, N) Cholesky factor
    fitted_map : dict           — {ticker: garch_params_dict}
    model_comparison : dict     — {ticker: {garch_aic, constant_aic, delta_aic, preferred}}
    """
    N = len(tickers)

    _EMPTY_PARAMS = {
        "mu": 0.0, "omega": 1e-4, "alpha": 0.0, "beta": 0.0,
        "nu": np.inf, "long_run_var": 1e-4, "half_life": None,
        "persistence": 0.0, "last_cond_var": 1e-4,
        "standardized_residuals": np.array([]),
        "conditional_vol": np.array([]),
        "converged": False, "model": "constant-vol",
        "log_likelihood": -1e9, "aic": 1e9, "low_confidence": True,
    }

    def _fit_ticker(ticker: str) -> tuple:
        hist = price_data.get(ticker)
        if hist is None or hist.empty or "Close" not in hist.columns:
            empty = _EMPTY_PARAMS.copy()
            return ticker, empty, empty.copy()
        prices = hist["Close"].dropna()
        if lookback_days is not None:
            prices = prices.iloc[-lookback_days:]
        log_r = np.log(prices / prices.shift(1)).dropna()

        garch_p = _fit_garch_params(log_r)
        const_p = _fit_constant_vol(log_r)

        # Attach the index so we can align residuals later
        garch_p["_index"] = log_r.index
        const_p["_index"] = log_r.index

        return ticker, garch_p, const_p

    max_workers = min(N, 8)
    fitted_results = {}
    const_results = {}

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(_fit_ticker, t): t for t in tickers}
        for future in futures:
            try:
                ticker, garch_p, const_p = future.result()
                fitted_results[ticker] = garch_p
                const_results[ticker] = const_p
            except Exception:
                logger.warning("Failed to fit GARCH for ticker", exc_info=True)

    # Build model_comparison
    model_comparison = {}
    for t in tickers:
        gp = fitted_results.get(t, {})
        cp = const_results.get(t, {})
        g_aic = gp.get("aic", 1e9)
        c_aic = cp.get("aic", 1e9)
        delta_aic = c_aic - g_aic  # positive = GARCH better
        if delta_aic > 4:
            preferred = "garch-t"
        elif delta_aic < -4:
            preferred = "constant-vol"
        else:
            preferred = "comparable"
        model_comparison[t] = {
            "garch_aic": g_aic,
            "garch_ll": gp.get("log_likelihood", -1e9),
            "constant_aic": c_aic,
            "constant_ll": cp.get("log_likelihood", -1e9),
            "delta_aic": delta_aic,
            "preferred": preferred,
        }

    # Correlation from standardised residuals (inner join)
    std_resid_series = {}
    for t in tickers:
        gp = fitted_results.get(t, {})
        idx = gp.get("_index")
        sr = gp.get("standardized_residuals")
        if idx is not None and sr is not None and len(sr) > 0:
            std_resid_series[t] = pd.Series(sr, index=idx)

    corr_cholesky = np.eye(N)
    if N == 1:
        corr_cholesky = np.array([[1.0]])
    elif len(std_resid_series) >= 2:
        sr_df = pd.DataFrame(std_resid_series).dropna()
        if len(sr_df) >= 126:
            try:
                corr_mat = sr_df.corr().values
                corr_mat = corr_mat + np.eye(N) * 1e-8
                corr_cholesky = np.linalg.cholesky(corr_mat)
            except np.linalg.LinAlgError:
                logger.warning("Cholesky failed on residual correlation; using identity")
                corr_cholesky = np.eye(N)

    # Build ordered list and strip the private _index key
    garch_params_list = []
    for t in tickers:
        gp = fitted_results.get(t, {}).copy()
        gp.pop("_index", None)
        garch_params_list.append(gp)

    fitted_map = {t: fitted_results[t].copy() for t in tickers}
    for t in fitted_map:
        fitted_map[t].pop("_index", None)

    # Compute correlation matrix from standardised residuals for export
    correlation_matrix = None
    if len(std_resid_series) >= 2:
        sr_df = pd.DataFrame(std_resid_series).dropna()
        if len(sr_df) >= 2:
            correlation_matrix = sr_df.corr()

    return garch_params_list, corr_cholesky, fitted_map, model_comparison, correlation_matrix


# ── Distribution flags ────────────────────────────────────────────────────────

def compute_distribution_flags(price_data: dict) -> dict:
    """
    Compute excess kurtosis and skewness of GARCH standardised residuals per ticker.

    fat_tailed flag: nu < 10 (heavy Student-t tails) rather than raw kurtosis.
    kurtosis/skewness are computed on standardised residuals for compatibility.

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
        gp = _fit_garch_params(log_r)
        sr = gp.get("standardized_residuals")
        if sr is None or len(sr) == 0:
            sr = log_r.values

        sr_series = pd.Series(sr)
        kurt = float(sr_series.kurt())
        skew = float(sr_series.skew())
        nu = gp.get("nu", np.inf)
        fat_tailed = (not np.isinf(nu)) and (nu < 10)

        flags[ticker] = {
            "kurtosis":  round(kurt, 2),
            "skewness":  round(skew, 2),
            "fat_tailed": fat_tailed,
        }
    return flags


# ── Model diagnostics ─────────────────────────────────────────────────────────

def compute_model_diagnostics(price_data: dict) -> dict:
    """
    Run statistical tests on GARCH standardised residuals per ticker.

    Tests:
      1. Jarque-Bera       — are standardised residuals normally distributed?
      2. Ljung-Box (resid) — are residuals independent (no autocorrelation)?
      3. Ljung-Box (resid²)— did GARCH capture volatility dynamics?

    QQ plot uses Student-t(nu) reference when nu < 30, else normal.

    Returns
    -------
    {ticker: {
        jb_stat, jb_pvalue, jb_normal,
        lb_stat, lb_pvalue, lb_independent,
        lb_sq_stat, lb_sq_pvalue, lb_sq_pass,
        qq_theoretical, qq_observed,
        verdict, garch_params, nu,
    }}
    """
    results = {}
    for ticker, hist in price_data.items():
        if hist is None or hist.empty or "Close" not in hist.columns:
            continue
        log_r = np.log(hist["Close"].dropna() / hist["Close"].dropna().shift(1)).dropna()
        if len(log_r) < 60:
            continue

        gp = _fit_garch_params(log_r)
        sr = gp.get("standardized_residuals")
        if sr is None or len(sr) == 0:
            sr = log_r.values
        nu = gp.get("nu", np.inf)

        std_resid_vals = sr

        # Jarque-Bera on standardised residuals
        _jb = stats.jarque_bera(std_resid_vals)
        jb_stat: float = cast(float, _jb[0])
        jb_p: float = cast(float, _jb[1])
        jb_normal = jb_p >= 0.05

        # Ljung-Box on residuals (serial correlation)
        lb_result = acorr_ljungbox(std_resid_vals, lags=[10], return_df=True)
        lb_stat = float(lb_result["lb_stat"].iloc[0])
        lb_p = float(lb_result["lb_pvalue"].iloc[0])
        lb_independent = lb_p >= 0.01

        # Ljung-Box on squared residuals (volatility clustering)
        lb_sq_result = acorr_ljungbox(std_resid_vals ** 2, lags=[10], return_df=True)
        lb_sq_stat = float(lb_sq_result["lb_stat"].iloc[0])
        lb_sq_p = float(lb_sq_result["lb_pvalue"].iloc[0])
        lb_sq_pass = lb_sq_p >= 0.05

        # QQ data — use Student-t reference when nu is finite and < 30
        if np.isfinite(nu) and nu < 30:
            (qq_theoretical, qq_observed), _ = stats.probplot(
                std_resid_vals, dist="t", sparams=(nu,)
            )
        else:
            (qq_theoretical, qq_observed), _ = stats.probplot(std_resid_vals, dist="norm")

        # Plain-English verdict (based on squared residual LB and JB)
        if lb_sq_pass and jb_normal and lb_independent:
            verdict = (
                "GARCH model captured volatility dynamics well. "
                "Model assumptions are reasonable for this position."
            )
        elif lb_sq_pass and not jb_normal:
            verdict = (
                "GARCH model captured volatility dynamics well. "
                "Standardised residuals deviate from normality — Student-t fit handles fat tails."
            )
        elif not lb_sq_pass:
            verdict = (
                "Residual volatility clustering detected — model may understate risk "
                "during turbulent periods."
            )
        elif not lb_independent:
            verdict = (
                "Standardised residuals show autocorrelation. The model treats each day as "
                "independent, which may miss momentum or mean-reversion patterns."
            )
        else:
            verdict = (
                "Standardised residuals are non-normal and autocorrelated. "
                "Treat the simulation output with extra caution."
            )

        # Remove private keys before storing
        gp_clean = {k: v for k, v in gp.items() if not k.startswith("_")}
        # Remove non-serialisable arrays to keep the result dict lightweight
        gp_clean.pop("standardized_residuals", None)
        gp_clean.pop("conditional_vol", None)

        results[ticker] = {
            "jb_stat": round(float(jb_stat), 2),
            "jb_pvalue": round(float(jb_p), 4),
            "jb_normal": jb_normal,
            "lb_stat": round(lb_stat, 2),
            "lb_pvalue": round(lb_p, 4),
            "lb_independent": lb_independent,
            "lb_sq_stat": round(lb_sq_stat, 2),
            "lb_sq_pvalue": round(lb_sq_p, 4),
            "lb_sq_pass": lb_sq_pass,
            "qq_theoretical": qq_theoretical,
            "qq_observed": qq_observed,
            "verdict": verdict,
            "garch_params": gp_clean,
            "nu": nu,
        }
    return results


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
      - Training window: everything before 1 year ago (calibrate GARCH params)
      - Test window:     last 252 trading days (simulate then compare to actual)

    GARCH is fitted on training data only — no look-ahead bias.

    Parameters
    ----------
    portfolio : dict
    price_data : dict
    n_sims : int
    seed : int

    Returns
    -------
    dict with keys:
        sim_dates, percentiles, actual, start_value,
        hit_rate_80, hit_rate_50, ticker_hit_rates, ticker_flags,
        tickers_used, split_date, train_days, garch_params, model_comparison

    Returns empty dict if there is insufficient data.
    """
    shares_by_ticker = _total_shares(portfolio)
    candidate_tickers = [t for t in shares_by_ticker if t in price_data]

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
    if log_returns_all.empty or len(log_returns_all) < MIN_TOTAL:
        return {}

    # ── Split ──────────────────────────────────────────────────────────────
    split_idx = len(log_returns_all) - 252
    train_log_r = log_returns_all.iloc[:split_idx]
    test_log_r = log_returns_all.iloc[split_idx:]
    split_date = train_log_r.index[-1]
    train_days = len(train_log_r)

    # ── Build training-only price data (no look-ahead) ─────────────────────
    training_price_data = {}
    for t in valid_tickers:
        hist = price_data[t]
        hist_train = hist[hist.index <= split_date]
        if not hist_train.empty:
            training_price_data[t] = hist_train

    # ── Calibrate GARCH on training data only ─────────────────────────────
    garch_params_list, corr_cholesky, fitted_map, model_comparison, correlation_matrix = _calibrate(
        training_price_data, valid_tickers
    )

    # ── Starting prices at the split date ─────────────────────────────────
    price_df = pd.DataFrame({
        t: price_data[t]["Close"].dropna() for t in valid_tickers
    }).dropna()

    split_prices = price_df.loc[:split_date].iloc[-1].values
    shares = np.array([shares_by_ticker[t] for t in valid_tickers])
    start_value = float((split_prices * shares).sum())

    # ── Simulate ───────────────────────────────────────────────────────────
    rng = np.random.default_rng(seed)
    portfolio_paths, ticker_paths = _simulate_paths(
        garch_params_list, corr_cholesky, split_prices, shares, n_sims, 252, rng,
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
        columns=["p10", "p25", "p50", "p75", "p90"],  # type: ignore[arg-type]
        index=actual.index,
    )

    # ── Hit rates ─────────────────────────────────────────────────────────
    within_80 = ((actual >= percentiles["p10"]) & (actual <= percentiles["p90"])).mean()
    within_50 = ((actual >= percentiles["p25"]) & (actual <= percentiles["p75"])).mean()

    ticker_hit_rates = {}
    for i, ticker in enumerate(valid_tickers):
        t_paths = ticker_paths[:, :n_actual, i]
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
        "sim_dates":          actual.index,
        "percentiles":        percentiles,
        "actual":             actual,
        "start_value":        start_value,
        "hit_rate_80":        round(float(within_80) * 100, 1),
        "hit_rate_50":        round(float(within_50) * 100, 1),
        "ticker_hit_rates":   ticker_hit_rates,
        "ticker_flags":       compute_distribution_flags({t: price_data[t] for t in valid_tickers}),
        "tickers_used":       valid_tickers,
        "split_date":         split_date.date(),
        "train_days":         train_days,
        "garch_params":       fitted_map,
        "model_comparison":   model_comparison,
        "correlation_matrix": correlation_matrix,
    }


# ── Portfolio forward simulation ──────────────────────────────────────────────

def run_monte_carlo_portfolio(
    portfolio: dict,
    price_data: dict,
    start_prices_base: dict,
    n_sims: int = 1000,
    horizon_days: int = 252,
    lookback_days: int | None = None,
    seed: int = 42,
) -> dict:
    """
    Forward-looking correlated GARCH Monte Carlo simulation for the full portfolio.

    Uses all available price data for calibration (no train/test split).
    Runs two simulations — correlated (Cholesky) and independent (diagonal
    covariance) — so the diversification benefit can be measured directly.

    Parameters
    ----------
    portfolio : dict
    price_data : dict
    start_prices_base : dict — {ticker: current price in base currency}
    n_sims : int
    horizon_days : int
    lookback_days : int or None
    seed : int

    Returns
    -------
    dict with keys:
        dates, percentiles, portfolio_paths, portfolio_paths_i,
        start_value, tickers_used, ticker_flags, train_days,
        garch_params, model_comparison, correlation_matrix

    Returns empty dict if insufficient data.
    """
    shares_by_ticker = _total_shares(portfolio)

    MIN_DAYS = 252
    valid_tickers = [
        t for t in shares_by_ticker
        if (
            t in price_data
            and t in start_prices_base
            and price_data[t] is not None
            and not price_data[t].empty
            and "Close" in price_data[t].columns
            and price_data[t]["Close"].dropna().shape[0] >= MIN_DAYS
        )
    ]
    if not valid_tickers:
        return {}

    # Validate that inner-joined history is long enough
    log_returns_check = _build_log_returns(price_data, valid_tickers)
    if lookback_days is not None:
        log_returns_check = log_returns_check.iloc[-lookback_days:]
    if len(log_returns_check) < MIN_DAYS:
        return {}

    train_days = len(log_returns_check)
    last_date = log_returns_check.index[-1]

    # ── Calibrate GARCH ───────────────────────────────────────────────────
    garch_params_list, corr_cholesky, fitted_map, model_comparison, correlation_matrix = _calibrate(
        price_data, valid_tickers, lookback_days=lookback_days
    )

    N = len(valid_tickers)
    start_prices = np.array([start_prices_base[t] for t in valid_tickers])
    shares = np.array([shares_by_ticker[t] for t in valid_tickers])
    start_value = float((start_prices * shares).sum())

    # ── Correlated paths ──────────────────────────────────────────────────
    rng = np.random.default_rng(seed)
    portfolio_paths, _ = _simulate_paths(
        garch_params_list, corr_cholesky, start_prices, shares, n_sims, horizon_days, rng,
    )

    # ── Independent paths (identity correlation) ──────────────────────────
    rng_i = np.random.default_rng(seed)
    portfolio_paths_i, _ = _simulate_paths(
        garch_params_list, np.eye(N), start_prices, shares, n_sims, horizon_days, rng_i,
    )

    future_dates = pd.bdate_range(start=last_date, periods=horizon_days + 1)[1:]

    pcts = np.percentile(portfolio_paths, [10, 25, 50, 75, 90], axis=0)
    percentiles = pd.DataFrame(
        pcts.T,
        columns=["p10", "p25", "p50", "p75", "p90"],  # type: ignore[arg-type]
        index=future_dates,
    )

    return {
        "dates":              future_dates,
        "percentiles":        percentiles,
        "portfolio_paths":    portfolio_paths,
        "portfolio_paths_i":  portfolio_paths_i,
        "start_value":        start_value,
        "tickers_used":       valid_tickers,
        "ticker_flags":       compute_distribution_flags({t: price_data[t] for t in valid_tickers}),
        "train_days":         train_days,
        "garch_params":       fitted_map,
        "model_comparison":   model_comparison,
        "correlation_matrix": correlation_matrix,
    }


def compute_var_cvar(
    end_paths: np.ndarray,
    start_value: float,
    confidence: float = 0.95,
) -> dict:
    """
    Compute Value at Risk and Conditional VaR (Expected Shortfall) from
    a 1-D array of simulated end-values.

    VaR(95%)  — the loss threshold such that only 5% of simulations are worse.
    CVaR(95%) — the average loss in those worst 5% of simulations.

    Both are returned as fractions (e.g. 0.15 = 15%) and absolute amounts.
    """
    returns = (end_paths - start_value) / start_value
    var = float(-np.percentile(returns, (1 - confidence) * 100))
    tail_mask = returns <= -var
    cvar = float(-returns[tail_mask].mean()) if tail_mask.any() else var
    return {
        "var":      var,
        "cvar":     cvar,
        "var_abs":  var * start_value,
        "cvar_abs": cvar * start_value,
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
    Forward-looking GARCH Monte Carlo simulation for a single ticker.

    Parameters
    ----------
    hist : pd.DataFrame
    current_price : float
    n_sims : int
    horizon_days : int
    lookback_days : int or None
    seed : int

    Returns
    -------
    dict with keys:
        dates, percentiles, end_paths, start_price,
        mu_annual, sigma_annual, flag, train_days,
        garch_params, model_comparison

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

    gp = _fit_garch_params(log_r)
    corr_cholesky = np.array([[1.0]])
    garch_params_list = [gp]

    # For display: annualised vol from long-run variance or sigma^2
    lr_var = gp.get("long_run_var")
    if lr_var is not None:
        sigma_annual = math.sqrt(lr_var) * math.sqrt(252) / 100.0 * 100
    else:
        sigma_annual = float(log_r.std()) * (252 ** 0.5) * 100
    mu_annual = round((gp["mu"] + 0.5 * (gp["omega"] / 1e4)) * 252 * 100, 2)

    start_arr = np.array([current_price])
    shares_arr = np.array([1.0])

    rng = np.random.default_rng(seed)
    _, ticker_paths = _simulate_paths(
        garch_params_list, corr_cholesky, start_arr, shares_arr,
        n_sims, horizon_days, rng,
    )
    paths = ticker_paths[:, :, 0]  # (n_sims, horizon_days)

    last_date = prices.index[-1]
    future_dates = pd.bdate_range(start=last_date, periods=horizon_days + 1)[1:]

    pcts = np.percentile(paths, [10, 25, 50, 75, 90], axis=0)
    percentiles = pd.DataFrame(
        pcts.T,
        columns=["p10", "p25", "p50", "p75", "p90"],  # type: ignore[arg-type]
        index=future_dates,
    )

    flag = compute_distribution_flags({"_": hist}).get("_", {})

    # Constant-vol fallback for model_comparison: fit once more
    cv_p = _fit_constant_vol(log_r)
    delta_aic = cv_p["aic"] - gp["aic"]
    if delta_aic > 4:
        preferred = "garch-t"
    elif delta_aic < -4:
        preferred = "constant-vol"
    else:
        preferred = "comparable"

    model_comparison = {
        "_": {
            "garch_aic": gp["aic"],
            "garch_ll": gp["log_likelihood"],
            "constant_aic": cv_p["aic"],
            "constant_ll": cv_p["log_likelihood"],
            "delta_aic": delta_aic,
            "preferred": preferred,
        }
    }

    # Compute sigma_annual from raw log_r std for display consistency
    sigma_annual_display = round(float(log_r.std()) * (252 ** 0.5) * 100, 2)
    mu_annual_display = round((gp["mu"] + 0.5 * float(log_r.std()) ** 2) * 252 * 100, 2)

    gp_clean = {k: v for k, v in gp.items() if not k.startswith("_")}
    gp_clean.pop("standardized_residuals", None)
    gp_clean.pop("conditional_vol", None)

    return {
        "dates":           future_dates,
        "percentiles":     percentiles,
        "end_paths":       paths[:, -1],
        "start_price":     current_price,
        "mu_annual":       mu_annual_display,
        "sigma_annual":    sigma_annual_display,
        "flag":            flag,
        "train_days":      len(log_r),
        "garch_params":    {"_": gp_clean},
        "model_comparison": model_comparison,
    }
