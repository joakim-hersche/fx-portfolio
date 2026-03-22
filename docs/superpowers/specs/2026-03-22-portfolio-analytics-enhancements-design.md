# Portfolio Analytics Enhancements

Four features inspired by NVIDIA's quantitative-portfolio-optimization blueprint, adapted for a personal portfolio tracker.

## Feature 1: Sortino Ratio

**Goal:** Add downside-risk-adjusted return metric alongside existing Sharpe ratio.

**File:** `src/portfolio.py` — `compute_analytics()`

Add to the per-ticker loop after Sharpe calculation:

```python
downside = excess[excess < 0]
sortino = float((excess.mean() / downside.std()) * (252 ** 0.5)) if len(downside) > 5 else None
```

New column `"Sortino Ratio"` in the returned DataFrame, rounded to 2 decimal places.

**UI changes:**
- `src/ui/health.py` — add Sortino column to the risk metrics table
- `src/ui/guide.py` — add explanation: "Like Sharpe but only penalizes downside volatility. A stock that swings up a lot but rarely down will have a higher Sortino than Sharpe."

## Feature 2: KDE-based Monte Carlo

**Goal:** Improve simulation realism by capturing fat tails and skewness from historical data, instead of assuming normal distributions.

**Dependency:** Add `scikit-learn` to `requirements.txt`.

**File:** `src/monte_carlo.py` — `_simulate_paths()`

Add a `method` parameter (`"normal"` or `"kde"`, default `"kde"`):

- **Normal (existing):** `np.random.multivariate_normal(mean, cov, n_sims)` then Cholesky
- **KDE (new):** `KernelDensity(bandwidth='silverman').fit(historical_log_returns).sample(n_sims)`

KDE preserves the joint distribution shape including fat tails, skewness, and non-linear correlations. Falls back to normal if KDE fails (e.g., too few data points <30).

**Propagation:**
- `run_monte_carlo_portfolio()` and `run_monte_carlo_ticker()` pass `method` through
- `src/ui/forecast.py` — add a toggle switch ("Normal" / "KDE") above the fan chart. Default: KDE.
- Cache keys must include the method parameter so switching doesn't serve stale results.

**No changes to:**
- `compute_var_cvar()` — works on simulation output regardless of generation method
- `compute_model_diagnostics()` — still tests the raw historical returns
- Backtesting — uses the selected method for its simulations

## Feature 3: Smarter Rebalancing

**Goal:** Add turnover awareness to the rebalancing calculator.

**File:** `src/ui/health.py` — `_render_rebalancing_calculator()`

### Turnover constraint
Add a slider: "Max trade budget" (0–100% of deposit, default 100%). When set below 100%, the allocator caps total buy value at `deposit * pct` and prioritizes positions with the largest drift from target.

Changes to the greedy algorithm (lines ~830-881):
1. Calculate deficits as before
2. Set `trade_budget = deposit * (turnover_pct / 100)`
3. Allocate in order of largest deficit first, stopping when budget exhausted
4. Remaining cash shown as "Unallocated"

### Drift alert
After computing current vs target weights, show a warning badge on the rebalancing section header when any position drifts >5 percentage points from its target. Uses existing amber badge styling.

## Feature 4: Efficient Frontier

**Goal:** Show whether the user's portfolio is efficiently allocated by plotting it against the Mean-CVaR efficient frontier.

**Dependency:** Add `cvxpy` to `requirements.txt`.

### New module: `src/frontier.py`

```python
def compute_efficient_frontier(
    returns: pd.DataFrame,   # daily returns, columns = tickers
    n_points: int = 20,
    confidence: float = 0.95,
) -> dict:
    """Compute the Mean-CVaR efficient frontier.

    Returns {
        "frontier": [(cvar, expected_return), ...],  # n_points on the curve
        "stocks": {ticker: (cvar, expected_return)},  # individual stock positions
    }
    """
```

Algorithm (from NVIDIA blueprint, simplified for CPU):
1. Generate scenarios: use historical daily returns directly (no simulation needed)
2. For each of 20 log-spaced risk-aversion levels (lambda 0.001 to 10):
   - Solve LP: `minimize: lambda * CVaR - expected_portfolio_return`
   - Subject to: weights sum to 1, weights >= 0 (long-only)
   - CVaR formulated as: `CVaR = VaR + (1/(n*(1-alpha))) * sum(max(loss - VaR, 0))`
3. Collect (CVaR, return) for each solution
4. Compute each individual stock's (CVaR, return) for reference

```python
def portfolio_position(
    returns: pd.DataFrame,
    weights: dict[str, float],  # {ticker: weight}
    confidence: float = 0.95,
) -> tuple[float, float]:
    """Return (cvar, expected_return) for the current portfolio."""
```

### UI: New chart in Portfolio Health tab

**File:** `src/ui/health.py` — add after correlation heatmap, inside the "Detailed Metrics" collapsible.

Chart (Plotly scatter):
- **Frontier curve:** line connecting the 20 optimal points (color: `ACCENT`)
- **Current portfolio:** large dot with label (color: amber `#F59E0B`)
- **Individual stocks:** smaller dots with ticker labels (color: muted)
- X-axis: CVaR (%) — "Tail Risk"
- Y-axis: Expected Return (%) — "Expected Return"
- Title: "Efficient Frontier — is your portfolio optimally allocated?"

If current portfolio dot is on or near the frontier: efficient. If below: room to improve return for same risk, or reduce risk for same return.

### Data flow
1. Fetch 1-year daily returns for all portfolio tickers (reuse `price_data_1y` already fetched in `_fetch_health_data`)
2. Compute daily returns from close prices
3. Pass to `compute_efficient_frontier()` + `portfolio_position()`
4. Render chart

### Performance
For <30 stocks with 252 daily observations, each LP solves in <10ms on CPU. Total: <200ms for 20 points. No GPU needed.

### Graceful degradation
- `cvxpy` not installed: skip frontier chart, no error
- Portfolio has <3 stocks: skip (frontier meaningless with 1-2 assets)
- Solver fails: log warning, skip chart

## Files Changed

| File | Change |
|------|--------|
| `requirements.txt` | Add `cvxpy`, `scikit-learn` |
| `src/portfolio.py` | Add Sortino ratio to `compute_analytics()` |
| `src/monte_carlo.py` | Add KDE method to `_simulate_paths()` |
| `src/frontier.py` | **New** — efficient frontier computation |
| `src/ui/health.py` | Sortino column, rebalancing turnover slider, drift alert, frontier chart |
| `src/ui/forecast.py` | Normal/KDE toggle for Monte Carlo |
| `src/ui/guide.py` | Explain Sortino, KDE, frontier |

## Not in Scope

- GPU acceleration (irrelevant for <50 stocks)
- Short selling (long-only constraint matches personal investing)
- Transaction cost modeling (overcomplicates the rebalancing UX)
- Multi-period optimization (single-period sufficient for personal use)
