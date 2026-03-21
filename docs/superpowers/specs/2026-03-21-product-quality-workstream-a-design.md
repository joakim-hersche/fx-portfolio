# Workstream A — Product Quality (No Server Changes)

**Date:** 2026-03-21
**Goal:** Move the dashboard from "recommend with caveats" to "definitely recommend" for both experienced traders and passive investors, without requiring server-side infrastructure changes.

**Context:** User testing (experienced trader persona, 2-week usage) identified four gaps preventing an unconditional recommendation: data reliability risk (yfinance), European coverage gaps, limited chart interactivity, and no proactive alerting. This spec addresses all four within the current local-storage architecture.

---

## Scope

Two parallel tracks, no dependencies between them:

- **Track 1:** Data layer abstraction + European coverage expansion
- **Track 2:** Comparison chart ticker toggles + in-app alerts

---

## Track 1: Data Layer Abstraction + European Coverage

### 1.1 Provider Interface

**New file: `src/providers.py`**

A `DataProvider` protocol (Python `Protocol` class) defining the standard interface for all data sources. Methods map directly to the existing caching tiers in `data_fetch.py`:

```python
class DataProvider(Protocol):
    def get_current_prices(self, tickers: list[str]) -> dict[str, float]: ...
    def get_price_history_short(self, ticker: str) -> pd.DataFrame: ...   # 6mo, maps to fetch_price_history_short
    def get_price_history_long(self, ticker: str) -> pd.DataFrame: ...    # max, maps to fetch_price_history_long
    def get_price_history_range(self, ticker: str, period: str) -> pd.DataFrame: ...  # arbitrary period
    def get_simulation_history(self, ticker: str) -> pd.DataFrame: ...    # 5y, maps to fetch_simulation_history
    def get_analytics_history(self, ticker: str) -> pd.DataFrame: ...     # 1y, maps to fetch_analytics_history
    def get_fundamentals(self, ticker: str) -> dict: ...
    def get_news(self, ticker: str) -> list[dict]: ...
    def get_sector_peers(self, sector: str, candidates: list[str], target: str, max_peers: int) -> list[dict]: ...
    def get_sector_medians(self, sector: str, candidates: list[str], max_samples: int) -> dict: ...
    def get_company_name(self, ticker: str) -> str: ...
```

**Not in the protocol:** FX rates. Currency conversion is orthogonal to stock data — `src/fx.py` remains unchanged and independent of the provider selection. This allows mixing providers (e.g., EOD for stocks, yfinance for FX) without coupling.

### 1.2 Provider Implementations

**`YFinanceProvider`** — wraps the existing `data_fetch.py` logic. This is the default and only active provider. Preserves all current behavior including:
- Batch download via `yf.download()` for `get_current_prices` (currently called directly in `portfolio.py` — moves behind provider)
- `ThreadPoolExecutor` fan-out for history/fundamentals
- GBX-to-GBP conversion
- Individual `yf.Ticker()` calls for sector peers/medians with early-exit logic
- `get_company_name` wraps existing `fetch_company_name`

No `EODProvider` stub. When subscribers arrive and EOD Historical Data is integrated, the provider class is added then. A comment in `providers.py` documents the planned migration path.

### 1.3 Provider Selection

Environment variable `DATA_PROVIDER` controls which implementation is used:
- `DATA_PROVIDER=yfinance` (default if unset)
- Future: `DATA_PROVIDER=eod` (requires `EOD_API_KEY` env var)

`data_fetch.py` becomes a thin routing layer: a `get_provider()` function reads the config and returns the correct implementation. All existing call sites in `portfolio.py`, `monte_carlo.py`, and UI modules continue calling `data_fetch.py` functions — the provider swap is invisible to them.

### 1.4 Caching

No changes to `cache.py`. TTL caching wraps the provider calls at the `data_fetch.py` level, same as today. Each `data_fetch.py` function applies the appropriate TTL (5 min for short/range, 24h for long/simulation/analytics/fundamentals). Provider implementations are cache-unaware.

### 1.5 European Coverage Expansion

**Add to `src/stocks.py`:**

- **SMIM (Swiss Mid-Cap Index)** — 30 constituents. Wikipedia has a maintained list. Scrape using the same pattern as existing indices. Verify that Wikipedia's SMIM table includes the `.SW` suffix (the SMI scraper uses `suffix=""` because Wikipedia already includes it — confirm SMIM follows the same format before implementing). **Fallback:** if the Wikipedia page doesn't exist or has an incompatible table structure, use a static list of SMIM constituents (sourced from SIX Group) with a code comment noting the quarterly rebalance cadence.

**Not included:** SPI Extra (broader Swiss Performance Index). The Wikipedia source is unreliable and a static fallback list goes stale quarterly. SMIM covers the most important gap (Swiss mid-caps). Broader SPI coverage comes naturally when EOD Historical Data is integrated.

**Improve freeform ticker entry:**

The sidebar search already allows typing arbitrary tickers, but there's no validation feedback. Add an async validation on submit via `run.io_bound`: attempt a quick price fetch through the provider. If it fails, show a warning "Ticker not found — check the symbol and try again" with a brief loading spinner during the check. This runs asynchronously to avoid blocking the UI.

### 1.6 What This Does NOT Include

- Switching to a paid provider (deferred until subscribers exist)
- Batch historical data fetching (provider-specific optimization, done when EODProvider is implemented)
- Removing yfinance as a dependency (it remains the default)
- Changes to `src/fx.py` (FX is independent of stock data providers)

---

## Track 2: Comparison Chart Ticker Toggles + In-App Alerts

### 2.1 Ticker Toggle Pills

**Location:** `src/ui/overview.py`, within the comparison chart section.

**UI design (validated via interactive mockup at `/tmp/comparison_toggle_mockup.html`):**
- Row of pill-shaped buttons between the existing controls (range toggle, FX switch, benchmark switch) and the chart
- One pill per portfolio ticker
- Each pill has a small colored dot matching the Plotly trace color, plus the ticker name
- Active state: full opacity, subtle colored border/background
- Inactive state: opacity 0.35, strikethrough text
- "Select All / None" text links at the end of the pill row
- Smooth CSS transitions on hover and toggle
- Pill row in a horizontal scrollable container with `overflow-x: auto` to handle large portfolios without pushing the chart down

**Implementation:**
- State: `dict[str, bool]` in the `update_chart()` closure, tracking visibility per ticker
- On pill click: toggle the boolean, match traces by `.name` property (not by index — the benchmark overlay shifts indices when enabled), update `.visible` accordingly, re-render the `ui.plotly` element
- No changes to `charts.py` — toggle logic is purely UI state in `overview.py`
- Pill colors sourced from `portfolio_color_map` (same dict that colors the Plotly traces)

### 2.2 In-App Alerts

**New file: `src/alerts.py`** — alert rule engine (no UI dependency)

Alert rules scoped to metrics that are cheap to compute from portfolio weights and cached price data (no heavy computation on Overview tab load):

| Rule | Trigger | Default Threshold | Data needed |
|------|---------|-------------------|-------------|
| `concentration_warning` | Single position above X% of portfolio | 30% | Portfolio weights (already computed) |
| `correlation_spike` | Any ticker pair correlation above threshold | 0.85 | 1y price history (24h cached, warm cache only) |

**Cold-start behavior:** `concentration_warning` always evaluates (uses portfolio weights, zero fetch cost). `correlation_spike` only evaluates if 1y price history is already in the 24h cache (i.e., the user has visited the Health or Forecast tab at least once). If the cache is cold, the correlation alert is silently skipped — no fetch is triggered from Overview. This avoids a 10-20 second cold-start penalty on first visit.

Each rule function takes current portfolio metrics and returns `list[Alert]` where `Alert` is a dataclass with `severity` (info/warning/critical), `title`, `message`, and `rule_id`.

**Not included as default alerts:** `health_score_drop` and `drawdown_alert`. These require full health score computation (correlation matrix, volatility, sector data) which is expensive and already happens on the Health tab. They surface there naturally. If users want them on Overview, they can be added later when the Health tab caches its results in storage for cross-tab access.

**New file: `src/ui/alerts.py`** — alert UI component

- On Overview tab load, runs all alert rules against current portfolio metrics
- Compares current metric values against last-seen values stored in the portfolio dict (nested under an `"_alerts"` key — a dict with sub-keys `"snapshots"`, `"dismissed"`, and `"settings"` — inside the encrypted portfolio blob, inheriting existing Fernet encryption)
- Writes the current metric snapshot immediately after evaluation (not on page close — browser close events are unreliable)
- Renders a notification banner at the top of the Overview tab:
  - Header: "Since your last visit:" (or "Portfolio alerts:" on first visit)
  - List of triggered alerts, color-coded by severity (amber=warning, red=critical)
  - Dismissible per-alert (X button) — dismissed state stored in the portfolio dict under `"_alerts.dismissed"`
- Small gear icon on the banner opens a threshold settings panel (inline, not a modal)
  - Number inputs for each threshold
  - Settings persisted in the portfolio dict under `"_alerts.settings"`

### 2.3 What This Does NOT Include

- Push notifications or email alerts (requires server infrastructure — Workstream B)
- Alerts on tabs other than Overview (alerts surface portfolio-level concerns; tab-specific detail stays in those tabs)
- Historical alert log (dismissed alerts are gone — no value in storing them locally)
- Health score or drawdown alerts (too expensive for Overview tab load; surface on Health tab instead)

---

## Future Workstreams (Out of Scope)

**Workstream B — Server Infrastructure:**
- Fly.io Postgres (free tier)
- Always-on machine (`min_machines_running = 1`, ~$5/month)
- Email/password authentication
- End-to-end encrypted portfolio sync (client-side Fernet encryption, server stores ciphertext)
- Background alert jobs + email notifications

**Workstream C — Monetisation:**
- Stripe integration
- Feature gating (position limits, Monte Carlo run caps, export restrictions)
- Free/Starter/Pro/Lifetime tier enforcement
- Onboarding flow for non-technical hosted users

B depends on nothing. C depends on B. Both are separate spec/plan/implementation cycles.

---

## File Changes Summary

| File | Change |
|------|--------|
| `src/providers.py` | **New** — DataProvider protocol + YFinanceProvider implementation |
| `src/data_fetch.py` | Refactor — becomes routing layer calling provider interface |
| `src/portfolio.py` | Refactor — `yf.download()` call in `build_portfolio_df` moves behind provider's `get_current_prices` |
| `src/stocks.py` | Add SMIM scraping |
| `src/alerts.py` | **New** — alert rule engine (concentration, correlation) |
| `src/ui/alerts.py` | **New** — alert UI component (banner, settings, snapshot) |
| `src/ui/overview.py` | Add ticker toggle pills to comparison chart section |
| `src/ui/sidebar.py` | Add async ticker validation feedback on freeform entry |

**Unchanged:** `src/fx.py`, `src/cache.py`, `src/charts.py`, `src/ui/shared.py`
