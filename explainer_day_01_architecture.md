# Day 1 — Architecture & `app.py`

*5–10 minute read · Session 1 of 10*

---

## How Streamlit Works: The Rerun Model

Before diving into any code, you need to understand Streamlit's execution model — because it's quite different from a normal Python script, and everything else in this codebase makes more sense once you've internalized it.

**Every user interaction reruns the entire script from top to bottom.**

When you click a button, select a currency, or add a stock, Streamlit discards the previous run and executes `app.py` again — line 1 through the last line. This sounds wasteful, but it's the design: Streamlit is a *reactive* framework. Your Python code describes *what to show* given the current state, and Streamlit figures out *what changed* and updates only those parts of the UI.

This has two major consequences you'll see throughout this codebase:

1. **State must be explicitly persisted.** Any variable you set during one run is gone on the next. That's why the app uses `st.session_state` — it's a dictionary that survives reruns.
2. **Expensive computations must be cached.** If fetching a stock price takes 2 seconds and the whole script reruns on every click, the app would be unusably slow. That's why you'll see `@st.cache_data` decorators everywhere.

---

## The First Line Is Special

```python
st.set_page_config(page_title="Market Dashboard", layout="wide")
```

This **must be the first Streamlit call** in the script — before any other `st.*` function. It sets browser-level properties (tab title, page layout). Streamlit enforces this; calling it anywhere else raises an error.

---

## Session State: Persisting Portfolio Data

```python
init_session_state()
sync_localstorage()
```

These two calls happen near the top of every run, before anything else touches data. `init_session_state()` (in `src/state.py`) ensures that `st.session_state.portfolio` exists — if it's the user's first visit, it initialises it as an empty dict. `sync_localstorage()` then checks the browser's localStorage for any previously saved portfolio data and loads it in.

The portfolio itself is stored as a nested dict:

```python
st.session_state.portfolio = {
    "AAPL": [
        {"shares": 10, "buy_price": 150.0, "purchase_date": "2023-06-01", ...},
        {"shares": 5,  "buy_price": 170.0, "purchase_date": "2024-01-15", ...},
    ],
    "TSLA": [
        {"shares": 8, "buy_price": 220.0, "purchase_date": "2023-09-10", ...},
    ]
}
```

The outer key is the ticker symbol. The value is a **list of lots** — you can hold multiple purchases of the same stock, each with its own price and date. This multi-lot design is important for accurate P&L and dividend calculations (covered on Day 3).

---

## The Sidebar

```python
with st.sidebar:
    base_currency = st.selectbox("Display Currency", ...)
    render_add_manage(all_stock_options, base_currency, ...)
```

The `with st.sidebar:` block collects everything that appears in the left panel. Two things live here:

- A **currency selector** — this drives every currency conversion in the rest of the app. The selected value is bound to `st.session_state["currency"]` via the `key=` parameter.
- The **Add / Manage Positions** form, delegated entirely to `sections/positions.py`.

A small but nice detail: after the currency selector, there's a conditional caption:

```python
if st.session_state.get("portfolio") and any(
    lot.get("buy_fx_rate") for lots in ... for lot in lots
):
    st.caption("Changing currency does not update historical buy FX rates...")
```

This only shows if you actually have a portfolio with FX data — a good example of using `st.session_state` to conditionally render UI.

---

## The Portfolio Guard

```python
if not st.session_state.portfolio:
    st.info("Add your first position using the sidebar on the left.")
    st.stop()
```

`st.stop()` is a Streamlit function that halts execution for the current run. Nothing below this line runs if the portfolio is empty. This is the primary guard — the entire data-fetching and rendering pipeline is skipped when there's nothing to show. A second guard follows:

```python
if df.empty:
    st.warning("Could not retrieve price data for any positions.")
    st.stop()
```

These two guards together ensure that all downstream code can assume a non-empty, valid DataFrame exists.

---

## Caching: Three TTL Tiers

The codebase uses three different cache lifetimes, each matching how frequently the underlying data changes:

| TTL | Used for | Rationale |
|-----|----------|-----------|
| **15 minutes** | Live prices (`fetch_price_history_short`) | Prices change tick-by-tick; 15 min is a reasonable balance between freshness and API rate limits |
| **24 hours** | Analytics history, fundamentals, company names | Volatility, Sharpe ratio, P/E — these barely move day-to-day |
| **No expiry** (session) | Stock lists from Wikipedia | The S&P 500 constituent list changes rarely; fetching it once per session is fine |

The decorator looks like this (you'll see this pattern throughout `src/data_fetch.py`):

```python
@st.cache_data(ttl=900)   # 900 seconds = 15 minutes
def fetch_price_history_short(ticker: str) -> pd.DataFrame:
    ...
```

`@st.cache_data` caches based on the function's **arguments**. Call `fetch_price_history_short("AAPL")` twice in the same run — or across separate reruns within the TTL window — and you get the cached result on the second call. The cache key is the function name + argument values.

---

## Pre-computation Block

After the guards, `app.py` pre-fetches everything before rendering any tab:

```python
_price_data_1y = {t: fetch_analytics_history(t) for t in _tickers}
_spy_data       = fetch_analytics_history("SPY")
analytics_df    = compute_analytics(st.session_state.portfolio, _price_data_1y, _spy_data)

_price_data_5y  = {t: fetch_simulation_history(t) for t in _tickers}
_bt             = cached_run_monte_carlo_backtest(...)
_ticker_mc_results = { ... }
_portfolio_mc   = cached_run_monte_carlo_portfolio(...)
```

This design choice matters: **all data is fetched once at the top**, then passed into the individual section renderers as arguments. The tabs don't fetch their own data — they receive it. This avoids duplicate network calls and makes the data flow explicit and traceable.

---

## KPI Cards

The four summary metrics at the top of the Overview tab are built as raw HTML strings via a helper function:

```python
def _kpi_card(label: str, value: str, border_color: str, ...) -> str:
    return f'<div style="...">...</div>'
```

The function returns an HTML string, not a Streamlit widget. The cards are then assembled into a CSS grid and rendered with:

```python
st.markdown(f"""
<div class="kpi-grid">
    {_card_1}{_card_2}{_card_3}{_card_4}
</div>
""", unsafe_allow_html=True)
```

`unsafe_allow_html=True` is required whenever you inject custom HTML into Streamlit. It's called "unsafe" because Streamlit can't sanitise arbitrary HTML, but in a local app you control, it's fine.

The color logic is simple and effective:

```python
pnl_color = C_POSITIVE if daily_pnl >= 0 else C_NEGATIVE
ret_color = C_POSITIVE if total_return >= 0 else C_NEGATIVE
```

`C_POSITIVE` and `C_NEGATIVE` are color constants imported from `src/charts.py` — a single source of truth for the green/red palette used throughout the app.

---

## The Tab Layout

```python
tab_overview, tab_positions, tab_risk, tab_forecast, tab_diagnostics, tab_guide = st.tabs([
    "Overview", "Positions", "Risk & Analytics", "Forecast", "Diagnostics", "Guide"
])
```

`st.tabs()` returns one context manager per tab. Each tab's content is written inside a `with tab_xxx:` block. Crucially, **all six `with` blocks execute on every rerun** — Streamlit doesn't skip inactive tabs. The content is just hidden by the UI. This is why the pre-computation block before the tabs makes sense: you don't want heavy fetches inside a tab block that runs even when the user is on a different tab.

---

## Module Dependency Diagram

Here's how the files relate to each other:

```
app.py  (entry point, orchestrator)
│
├── src/state.py               Session state init + localStorage sync
├── src/stocks.py              Ticker lists, market mappings, brand colors
├── src/fx.py                  FX rate fetching, currency detection
├── src/charts.py              Plotly helpers, color constants, layout defaults
├── src/ui.py                  Small Streamlit UI helpers (section_header, etc.)
│
├── src/data_fetch.py          All @st.cache_data fetchers
│   ├── uses → yfinance        Live prices, fundamentals, dividends
│   ├── uses → src/stocks.py   Ticker validation
│   ├── uses → src/fx.py       Currency conversion
│   └── uses → src/monte_carlo.py   Simulation engine (cached wrappers here)
│
├── src/portfolio.py           P&L computation, DataFrame builder
│   ├── uses → src/data_fetch.py
│   └── uses → src/fx.py
│
├── src/monte_carlo.py         Simulation engine (Cholesky, VaR, CVaR)
│   └── (pure numpy/pandas, no Streamlit)
│
├── src/excel_export.py        openpyxl report builder
│   └── uses → src/charts.py  (for chart data)
│
├── src/localstorage_component.py   HTML/JS bridge to browser localStorage
│
└── src/sections/              One file per rendered section
    ├── positions.py           Positions table + add/manage form
    ├── allocation.py          Bar chart of portfolio weights
    ├── comparison.py          Rebased multi-ticker comparison chart
    ├── price_history.py       Per-ticker price chart with buy overlays
    ├── risk.py                Volatility, Sharpe, Beta, correlation heatmap
    └── monte_carlo.py         Fan charts, backtest, QQ plots, diagnostics UI
```

**Key pattern:** `app.py` is a thin orchestrator. It fetches data at the top, computes KPIs inline, then delegates all rendering to `src/sections/`. The sections receive data as arguments — they don't fetch anything themselves.

---

## Key Takeaways

- Streamlit reruns the entire script on every user interaction. State must live in `st.session_state`; expensive work must be cached with `@st.cache_data`.
- `st.set_page_config()` must be the first Streamlit call — it's a hard constraint.
- `st.stop()` is used as a guard to bail out early if there's nothing to render.
- The three TTL tiers (15 min, 24 h, session) match the natural staleness of each data type.
- All data is pre-fetched before the tab layout so no tab duplicates a network call.
- `unsafe_allow_html=True` enables custom HTML/CSS in Streamlit — used here for the KPI cards and CSS design tokens.
- `app.py` itself is intentionally thin. Real logic lives in `src/`.

---

## What's Next

**Day 2** dives into the data layer: `stocks.py`, `data_fetch.py`, and `fx.py`. You'll see how the app scrapes S&P 500 and FTSE tickers from Wikipedia, how `yfinance` is used to fetch prices and fundamentals, why London-listed stocks need a special pence-to-pounds correction, and how every number on the dashboard gets converted to your chosen display currency.
