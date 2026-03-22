# Portfolio Analytics Enhancements — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Sortino ratio, KDE Monte Carlo, turnover-aware rebalancing, and efficient frontier chart.

**Architecture:** Four independent features touching different modules. Sortino adds a column to existing analytics. KDE adds an alternative simulation method. Rebalancing gets a trade budget slider. Frontier is a new module + chart.

**Tech Stack:** cvxpy (LP solver), scikit-learn (KDE), existing numpy/pandas/plotly

**Spec:** `docs/superpowers/specs/2026-03-22-portfolio-analytics-enhancements-design.md`

---

### Task 1: Add dependencies

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add cvxpy and scikit-learn**

Add to `requirements.txt`:
```
cvxpy>=1.6
scikit-learn>=1.6
```

- [ ] **Step 2: Install**

Run: `pip3 install cvxpy scikit-learn`

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "deps: add cvxpy and scikit-learn"
```

---

### Task 2: Sortino Ratio

**Files:**
- Modify: `src/portfolio.py:64-82` — add Sortino calculation
- Modify: `src/ui/health.py:384-389,418-479,487-515` — add Sortino column to risk table
- Modify: `src/ui/guide.py` — add Sortino explanation
- Test: `tests/test_risk_free.py` or new `tests/test_analytics.py`

- [ ] **Step 1: Write test**

Create `tests/test_analytics.py`:

```python
import numpy as np
import pandas as pd
from unittest.mock import patch

from src.portfolio import compute_analytics


def test_sortino_ratio_computed():
    """Sortino ratio should appear in analytics output."""
    # Create synthetic price data with 60 days
    dates = pd.bdate_range("2024-01-01", periods=60)
    prices = pd.DataFrame({"Close": 100 + np.cumsum(np.random.randn(60) * 0.5)}, index=dates)

    portfolio = {"TEST": [{"shares": 10}]}
    price_data = {"TEST": prices}
    bench_data = prices.copy()  # use same as benchmark

    with patch("src.portfolio.fetch_risk_free_yields", return_value=pd.Series(dtype=float)):
        result = compute_analytics(portfolio, price_data, bench_data, "USD")

    assert "Sortino Ratio" in result.columns
    assert result.iloc[0]["Sortino Ratio"] is not None


def test_sortino_higher_than_sharpe_for_upside_volatility():
    """A stock with mostly upside moves should have Sortino > Sharpe."""
    dates = pd.bdate_range("2024-01-01", periods=252)
    # Biased upward: mostly positive returns with few negative
    returns = np.abs(np.random.randn(252) * 0.01) + 0.001
    returns[::20] = -0.005  # occasional small dips
    prices = pd.DataFrame({"Close": 100 * np.exp(np.cumsum(returns))}, index=dates)

    portfolio = {"TEST": [{"shares": 10}]}
    price_data = {"TEST": prices}
    bench_data = prices.copy()

    with patch("src.portfolio.fetch_risk_free_yields", return_value=pd.Series(dtype=float)):
        result = compute_analytics(portfolio, price_data, bench_data, "USD")

    sharpe = result.iloc[0]["Sharpe Ratio"]
    sortino = result.iloc[0]["Sortino Ratio"]
    assert sortino > sharpe  # less downside penalty → higher Sortino
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `python3 -m pytest tests/test_analytics.py -v`

- [ ] **Step 3: Add Sortino to `compute_analytics()`**

In `src/portfolio.py`, after the Sharpe calculation (line ~67), add:

```python
        # Sortino ratio (annualised, penalises only downside volatility)
        downside = excess[excess < 0]
        sortino = float((excess.mean() / downside.std()) * (252 ** 0.5)) if len(downside) > 5 and downside.std() > 0 else None
```

Update the `rows.append` dict to include:
```python
            "Sortino Ratio": round(sortino, 2) if sortino is not None else None,
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `python3 -m pytest tests/test_analytics.py -v`

- [ ] **Step 5: Add Sortino column to health tab risk table**

In `src/ui/health.py`:

1. In `analytics_map` building (~line 384-389), add:
```python
"Sortino Ratio": arow.get("Sortino Ratio"),
```

2. In the per-ticker row rendering (~line 418-422), add after `sharpe`:
```python
            sortino = a.get("Sortino Ratio")
```

Add color class for Sortino (same thresholds as Sharpe):
```python
            sortino_cls = _color_class(sortino, [
                (lambda v: v >= 1, "td-pos"),
                (lambda v: v >= 0, "td-amb"),
                (lambda v: True, "td-neg"),
            ])
```

3. In the `rows_html` string (~line 478), add after the Sharpe `<td>`:
```python
f'<td class="{sortino_cls} right">{_fmt(sortino, "{:.1f}")}</td>'
```

4. In the table header (~line 504), add after "Return/Risk" `<th>`:
```html
<th class="right th-tip" title="Like Sharpe but only penalises downside swings. A stock that rises a lot but rarely falls will score higher here than on Sharpe.">Downside R/R</th>
```

Update the Risk colspan from 4 to 5.

- [ ] **Step 6: Update guide tab**

In `src/ui/guide.py`, in the Risk Metrics section, add after Sharpe explanation:

```
- **Downside Return/Risk (Sortino Ratio)** — like the Sharpe ratio but only penalises downside volatility. \
A stock that swings up a lot but rarely drops will have a higher Sortino than Sharpe. Above 1 is good, above 2 is excellent.
```

- [ ] **Step 7: Run full tests**

Run: `python3 -m pytest tests/ -v`

- [ ] **Step 8: Commit**

```bash
git add src/portfolio.py src/ui/health.py src/ui/guide.py tests/test_analytics.py
git commit -m "feat: add Sortino ratio to risk analytics"
```

---

### Task 3: KDE-based Monte Carlo

**Files:**
- Modify: `src/monte_carlo.py:38-80` — add `method` parameter to `_simulate_paths`
- Modify: `src/monte_carlo.py:349-461` — pass `method` through `run_monte_carlo_portfolio`
- Modify: `src/monte_carlo.py:490+` — pass `method` through `run_monte_carlo_ticker`
- Modify: `src/data_fetch.py` — update cached wrappers
- Test: `tests/test_monte_carlo_kde.py`

**Note:** KDE is the default. No UI toggle — falls back to normal silently when insufficient data.

- [ ] **Step 1: Write test**

Create `tests/test_monte_carlo_kde.py`:

```python
import numpy as np
import pandas as pd
import pytest

from src.monte_carlo import _simulate_paths


def test_kde_simulation_produces_valid_paths():
    """KDE simulation should produce portfolio paths with correct shape."""
    np.random.seed(42)
    N = 3
    mean_log = np.array([0.0005, 0.0003, 0.0004])
    cov_log = np.eye(N) * 0.0001
    start_prices = np.array([100.0, 50.0, 200.0])
    shares = np.array([10, 20, 5])
    rng = np.random.default_rng(42)

    # Need historical returns for KDE
    hist_returns = np.random.multivariate_normal(mean_log, cov_log, size=252)

    portfolio_paths, ticker_paths = _simulate_paths(
        mean_log, cov_log, start_prices, shares,
        n_sims=100, horizon_days=10, rng=rng,
        method="kde", hist_log_returns=hist_returns,
    )

    assert portfolio_paths.shape == (100, 10)
    assert ticker_paths.shape == (100, 10, 3)
    assert np.all(portfolio_paths > 0)


def test_normal_simulation_still_works():
    """Normal (default) simulation should still work."""
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

    # Only 5 rows — too few for KDE
    hist_returns = np.random.multivariate_normal(mean_log, cov_log, size=5)

    portfolio_paths, ticker_paths = _simulate_paths(
        mean_log, cov_log, start_prices, shares,
        n_sims=50, horizon_days=5, rng=rng,
        method="kde", hist_log_returns=hist_returns,
    )

    assert portfolio_paths.shape == (50, 5)
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `python3 -m pytest tests/test_monte_carlo_kde.py -v`

- [ ] **Step 3: Add KDE method to `_simulate_paths()`**

In `src/monte_carlo.py`, update the function signature and add KDE path:

```python
def _simulate_paths(
    mean_log: np.ndarray,
    cov_log: np.ndarray,
    start_prices: np.ndarray,
    shares: np.ndarray,
    n_sims: int,
    horizon_days: int,
    rng: np.random.Generator,
    method: str = "normal",
    hist_log_returns: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
```

After the existing Cholesky block, add the KDE path. The full simulation logic becomes:

```python
    N = len(mean_log)

    if method == "kde" and hist_log_returns is not None and len(hist_log_returns) >= 30:
        try:
            from sklearn.neighbors import KernelDensity
            kde = KernelDensity(bandwidth="silverman", kernel="gaussian")
            kde.fit(hist_log_returns)
            samples = kde.sample(n_sims * horizon_days, random_state=rng.integers(2**31))
            log_returns = samples.reshape(n_sims, horizon_days, N)
        except Exception:
            # Fall back to normal
            log_returns = _normal_returns(mean_log, cov_log, n_sims, horizon_days, N, rng)
    else:
        log_returns = _normal_returns(mean_log, cov_log, n_sims, horizon_days, N, rng)

    # Cumulative log price change from start
    log_price_paths = np.log(start_prices) + np.cumsum(log_returns, axis=1)
    ticker_paths = np.exp(log_price_paths)
    portfolio_paths = (ticker_paths * shares).sum(axis=2)
    return portfolio_paths, ticker_paths
```

Extract the existing Cholesky logic into a helper:

```python
def _normal_returns(mean_log, cov_log, n_sims, horizon_days, N, rng):
    cov_stable = cov_log + np.eye(N) * 1e-8
    try:
        L = np.linalg.cholesky(cov_stable)
    except np.linalg.LinAlgError:
        L = np.diag(np.sqrt(np.maximum(np.diag(cov_stable), 0)))
    Z = rng.standard_normal((n_sims, horizon_days, N))
    return Z @ L.T + mean_log
```

- [ ] **Step 4: Pass `method` and `hist_log_returns` through `run_monte_carlo_portfolio()`**

Update function signature to accept `method: str = "kde"`. Pass `log_returns.values` as `hist_log_returns` to `_simulate_paths()`. Do the same for the independent simulation call.

- [ ] **Step 5: Pass `method` through `run_monte_carlo_ticker()`**

Same pattern — add `method` parameter, pass through to `_simulate_paths`.

- [ ] **Step 6: Run all tests**

Run: `python3 -m pytest tests/ -v`

- [ ] **Step 7: Commit**

```bash
git add src/monte_carlo.py tests/test_monte_carlo_kde.py
git commit -m "feat: use KDE for Monte Carlo simulation (captures fat tails)"
```

---

### Task 4: Smarter Rebalancing

**Files:**
- Modify: `src/ui/health.py:830-881` — add turnover constraint to greedy allocator
- Modify: `src/ui/health.py:978` — add trade budget slider

- [ ] **Step 1: Add trade budget slider**

In `src/ui/health.py`, in `_render_rebalancing_calculator()`, after the deposit amount input (~line 978), add:

```python
trade_pct = ui.slider(min=10, max=100, value=100, step=10).props("label-always").style("width:100%;")
ui.html(f'<div style="font-size:10px;color:{TEXT_DIM};margin-top:-4px;">Trade budget: use up to this % of deposit</div>')
```

- [ ] **Step 2: Modify greedy allocator to respect trade budget**

In the buy suggestion logic (~line 830-881), after computing deficits, add:

```python
trade_budget = deposit * (trade_pct.value / 100)
```

Replace the existing allocation loop to cap at `trade_budget` instead of `deposit`. Track allocated amount and stop when budget exhausted. Show remaining as "Unallocated" in the footer.

- [ ] **Step 3: Add drift alert**

After computing current vs target weights, check if any position drifts more than 5 percentage points. If so, add a warning badge to the rebalancing section header:

```python
max_drift = max(abs(current_weight - target_weight) for ...) if targets else 0
if max_drift > 5:
    ui.badge(f"Drift: {max_drift:.0f}pp", color="amber").props("floating")
```

- [ ] **Step 4: Manual test**

Start app, go to Portfolio Health → Rebalancing Calculator. Set targets, adjust the trade budget slider, verify buy suggestions change. Verify drift badge appears when weights diverge >5pp.

- [ ] **Step 5: Commit**

```bash
git add src/ui/health.py
git commit -m "feat: add trade budget slider and drift alert to rebalancing"
```

---

### Task 5: Efficient Frontier

**Files:**
- Create: `src/frontier.py`
- Create: `tests/test_frontier.py`
- Modify: `src/ui/health.py` — add frontier chart after correlation heatmap

- [ ] **Step 1: Write tests**

Create `tests/test_frontier.py`:

```python
import numpy as np
import pandas as pd
import pytest

from src.frontier import compute_efficient_frontier, portfolio_position


def test_frontier_returns_expected_structure():
    """Frontier should return frontier points and stock positions."""
    np.random.seed(42)
    dates = pd.bdate_range("2024-01-01", periods=252)
    returns = pd.DataFrame({
        "A": np.random.randn(252) * 0.02 + 0.001,
        "B": np.random.randn(252) * 0.01 + 0.0005,
        "C": np.random.randn(252) * 0.015 + 0.0008,
    }, index=dates)

    result = compute_efficient_frontier(returns, n_points=10)

    assert "frontier" in result
    assert "stocks" in result
    assert len(result["frontier"]) > 0
    assert len(result["stocks"]) == 3
    # Frontier points should be (cvar, return) tuples
    for cvar, ret in result["frontier"]:
        assert isinstance(cvar, float)
        assert isinstance(ret, float)


def test_portfolio_position():
    """Should return (cvar, return) for given weights."""
    np.random.seed(42)
    dates = pd.bdate_range("2024-01-01", periods=252)
    returns = pd.DataFrame({
        "A": np.random.randn(252) * 0.02 + 0.001,
        "B": np.random.randn(252) * 0.01 + 0.0005,
    }, index=dates)

    weights = {"A": 0.6, "B": 0.4}
    cvar, ret = portfolio_position(returns, weights)

    assert isinstance(cvar, float)
    assert isinstance(ret, float)
    assert cvar > 0  # CVaR should be positive (it's a loss measure)


def test_frontier_with_too_few_stocks():
    """Should return empty result with fewer than 3 stocks."""
    dates = pd.bdate_range("2024-01-01", periods=252)
    returns = pd.DataFrame({
        "A": np.random.randn(252) * 0.02,
    }, index=dates)

    result = compute_efficient_frontier(returns)
    assert result["frontier"] == []
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `python3 -m pytest tests/test_frontier.py -v`

- [ ] **Step 3: Implement `src/frontier.py`**

```python
"""Mean-CVaR efficient frontier computation.

Uses cvxpy to solve a series of linear programs at different risk-aversion
levels, producing the Pareto-optimal curve of (tail risk, expected return).
"""

import logging

import numpy as np
import pandas as pd

_log = logging.getLogger(__name__)


def compute_efficient_frontier(
    returns: pd.DataFrame,
    n_points: int = 20,
    confidence: float = 0.95,
) -> dict:
    """Compute the Mean-CVaR efficient frontier.

    Parameters
    ----------
    returns : DataFrame
        Daily returns with columns = tickers.
    n_points : int
        Number of points along the frontier.
    confidence : float
        Confidence level for CVaR (e.g. 0.95).

    Returns
    -------
    dict with:
        frontier: list of (cvar, expected_return) tuples
        stocks: {ticker: (cvar, expected_return)}
    """
    if returns.shape[1] < 3:
        return {"frontier": [], "stocks": {}}

    try:
        import cvxpy as cp
    except ImportError:
        _log.warning("cvxpy not installed — efficient frontier unavailable")
        return {"frontier": [], "stocks": {}}

    R = returns.values  # (T, N)
    T, N = R.shape
    alpha = 1 - confidence  # tail probability

    # Individual stock positions
    stocks = {}
    for i, ticker in enumerate(returns.columns):
        stock_returns = R[:, i]
        var = float(-np.percentile(stock_returns, alpha * 100))
        tail = stock_returns[stock_returns <= -var]
        cvar = float(-tail.mean()) if len(tail) > 0 else var
        exp_ret = float(stock_returns.mean() * 252)  # annualised
        stocks[ticker] = (cvar * np.sqrt(252), exp_ret)

    # Sweep risk-aversion levels
    lambdas = np.logspace(-3, 1, n_points)
    frontier = []

    w = cp.Variable(N)
    z = cp.Variable(T)  # auxiliary for CVaR
    gamma = cp.Variable()  # VaR threshold

    portfolio_returns = R @ w
    expected_return = cp.sum(portfolio_returns) / T

    # CVaR constraints: z_t >= -r_t - gamma, z_t >= 0
    constraints = [
        w >= 0,
        cp.sum(w) == 1,
        z >= 0,
        z >= -portfolio_returns - gamma,
    ]
    cvar_expr = gamma + cp.sum(z) / (T * alpha)

    for lam in lambdas:
        objective = cp.Minimize(lam * cvar_expr - expected_return)
        prob = cp.Problem(objective, constraints)
        try:
            prob.solve(solver=cp.CLARABEL, warm_start=True)
            if prob.status in ("optimal", "optimal_inaccurate"):
                cvar_val = float(cvar_expr.value) * np.sqrt(252)  # annualise
                ret_val = float(expected_return.value) * 252
                frontier.append((cvar_val, ret_val))
        except Exception:
            continue

    # Deduplicate and sort by CVaR
    seen = set()
    unique = []
    for cvar_val, ret_val in frontier:
        key = (round(cvar_val, 6), round(ret_val, 6))
        if key not in seen:
            seen.add(key)
            unique.append((cvar_val, ret_val))
    frontier = sorted(unique, key=lambda x: x[0])

    return {"frontier": frontier, "stocks": stocks}


def portfolio_position(
    returns: pd.DataFrame,
    weights: dict[str, float],
    confidence: float = 0.95,
) -> tuple[float, float]:
    """Compute (cvar, expected_return) for a portfolio with given weights.

    Returns annualised values.
    """
    tickers = [t for t in returns.columns if t in weights]
    if not tickers:
        return (0.0, 0.0)

    w = np.array([weights[t] for t in tickers])
    w = w / w.sum()  # normalise

    R = returns[tickers].values
    port_returns = R @ w

    alpha = 1 - confidence
    var = float(-np.percentile(port_returns, alpha * 100))
    tail = port_returns[port_returns <= -var]
    cvar = float(-tail.mean()) if len(tail) > 0 else var

    return (cvar * np.sqrt(252), float(port_returns.mean() * 252))
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `python3 -m pytest tests/test_frontier.py -v`

- [ ] **Step 5: Add frontier chart to health tab**

In `src/ui/health.py`, after the correlation heatmap section (inside the "Detailed Metrics" collapsible), add a new function `_render_frontier_chart()` that:

1. Computes daily returns from `price_data_1y`
2. Calls `compute_efficient_frontier(returns)`
3. Computes current portfolio weights from `portfolio_df`
4. Calls `portfolio_position(returns, weights)`
5. Renders a Plotly scatter chart:
   - Frontier line: `ACCENT` color
   - Current portfolio: large amber dot `#F59E0B`
   - Individual stocks: small muted dots with ticker labels
   - X-axis: "Tail Risk (CVaR %)"
   - Y-axis: "Expected Return (%)"
   - Title: "Efficient Frontier"

Call this function from `_render_detailed_metrics()` after the correlation heatmap, guarded by:
```python
try:
    from src.frontier import compute_efficient_frontier
    # ... render
except ImportError:
    pass  # cvxpy not installed
```

- [ ] **Step 6: Update guide tab**

In `src/ui/guide.py`, add after the Risk-Free Rate section:

```
"Efficient Frontier" — shows the optimal trade-off between risk and return for your portfolio's stocks.
The curve represents the best possible portfolios: maximum return for each level of tail risk (CVaR).
If your portfolio dot is on the curve, your allocation is optimal. If it's below, you could get more
return for the same risk, or less risk for the same return, by adjusting weights.
```

- [ ] **Step 7: Run full tests**

Run: `python3 -m pytest tests/ -v`

- [ ] **Step 8: Commit**

```bash
git add src/frontier.py tests/test_frontier.py src/ui/health.py src/ui/guide.py
git commit -m "feat: add efficient frontier chart to portfolio health"
```

---

### Task 6: End-to-end verification

- [ ] **Step 1: Run full test suite**

Run: `python3 -m pytest tests/ -v`

- [ ] **Step 2: Manual verification**

Start the app and verify:

1. **Health tab → Detailed Metrics table**: Sortino column visible with color coding
2. **Health tab → Efficient Frontier chart**: frontier curve + portfolio dot + stock dots
3. **Health tab → Rebalancing**: trade budget slider works, drift badge appears
4. **Forecast tab**: KDE/Normal toggle visible, fan chart changes when switched
5. **Guide tab**: new explanations for Sortino, frontier

- [ ] **Step 3: Commit any fixes**
