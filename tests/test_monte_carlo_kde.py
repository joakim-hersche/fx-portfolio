import numpy as np
import pytest

from src.monte_carlo import _simulate_paths


def test_kde_simulation_produces_valid_paths():
    """KDE simulation should produce portfolio paths with correct shape."""
    N = 3
    mean_log = np.array([0.0005, 0.0003, 0.0004])
    cov_log = np.eye(N) * 0.0001
    start_prices = np.array([100.0, 50.0, 200.0])
    shares = np.array([10, 20, 5])
    rng = np.random.default_rng(42)
    hist_returns = np.random.default_rng(0).multivariate_normal(mean_log, cov_log, size=252)

    portfolio_paths, ticker_paths = _simulate_paths(
        mean_log, cov_log, start_prices, shares,
        n_sims=100, horizon_days=10, rng=rng,
        method="kde", hist_log_returns=hist_returns,
    )

    assert portfolio_paths.shape == (100, 10)
    assert ticker_paths.shape == (100, 10, 3)
    assert np.all(portfolio_paths > 0)


def test_normal_simulation_still_works():
    """Normal method should still work when explicitly requested."""
    N = 2
    mean_log = np.array([0.0005, 0.0003])
    cov_log = np.eye(N) * 0.0001
    start_prices = np.array([100.0, 50.0])
    shares = np.array([10, 20])
    rng = np.random.default_rng(42)

    portfolio_paths, ticker_paths = _simulate_paths(
        mean_log, cov_log, start_prices, shares,
        n_sims=50, horizon_days=5, rng=rng,
        method="normal",
    )

    assert portfolio_paths.shape == (50, 5)
    assert np.all(portfolio_paths > 0)


def test_kde_fallback_on_insufficient_data():
    """KDE with too few samples should fall back to normal without error."""
    N = 2
    mean_log = np.array([0.0005, 0.0003])
    cov_log = np.eye(N) * 0.0001
    start_prices = np.array([100.0, 50.0])
    shares = np.array([10, 20])
    rng = np.random.default_rng(42)
    hist_returns = np.random.default_rng(0).multivariate_normal(mean_log, cov_log, size=5)

    portfolio_paths, ticker_paths = _simulate_paths(
        mean_log, cov_log, start_prices, shares,
        n_sims=50, horizon_days=5, rng=rng,
        method="kde", hist_log_returns=hist_returns,
    )

    assert portfolio_paths.shape == (50, 5)
