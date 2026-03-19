# Day 2 — The Data Layer: `stocks.py`, `data_fetch.py`, `fx.py`

*~10 minute read · Session 2 of 10*

---

Yesterday we mapped the app's overall architecture. Today we go one layer deeper: **how does the dashboard actually get data?** Three files are responsible — one for knowing *which* stocks exist, one for *fetching* their prices and fundamentals, and one for handling *currencies*. Together they form the foundation everything else sits on.

---

## 1. `stocks.py` — The Catalogue

Before a user can add a position, the app needs to offer them a list of tickers to choose from. `stocks.py` builds that list, and it does so from a rather clever source: **Wikipedia**.

### Scraping index tables from Wikipedia

```python
def fetch_wikipedia_table(url, ticker_col, name_col, suffix=""):
    try:
        response = requests.get(url, headers=HEADERS)
        tables = pd.read_html(io.StringIO(response.text))
        for table in tables:
            if ticker_col in table.columns and name_col in table.columns:
                stocks = {}
                for _, row in table.iterrows():
                    ticker = str(row[ticker_col]).strip()
                    name   = str(row[name_col]).strip()
                    if ticker and name and ticker != "nan":
                        full_ticker = f"{ticker}{suffix}"
                        stocks[f"{name} ({full_ticker})"] = full_ticker
                return stocks
    except Exception as e:
        print(f"Failed to fetch {url}: {e}")
    return {}
```

`pd.read_html()` is the workhorse here. It parses all HTML `<table>` elements on a page and returns a list of DataFrames — no manual HTML scraping required. The function then loops through those tables until it finds one that has the expected column names (`ticker_col`, `name_col`).

The output is a plain Python dict with a human-readable key and a ticker string as the value:

```python
{
    "Apple Inc. (AAPL)": "AAPL",
    "Microsoft Corp. (MSFT)": "MSFT",
    ...
}
```

This structure is perfect for Streamlit's `st.selectbox`, which can display the human-readable name while the app uses the ticker internally.

### The `suffix` parameter and exchange routing

Different exchanges require different ticker suffixes on Yahoo Finance:

```python
def get_ftse100_stocks():
    return fetch_wikipedia_table(
        url="https://en.wikipedia.org/wiki/FTSE_100_Index",
        ticker_col="Ticker",
        name_col="Company",
        suffix=".L"       # ← ".L" = London Stock Exchange
    )

def get_dax_stocks():
    return fetch_wikipedia_table(
        url="https://en.wikipedia.org/wiki/DAX",
        ticker_col="Ticker",
        name_col="Company",
        suffix=".DE"      # ← ".DE" = Deutsche Börse (Frankfurt)
    )
```

| Suffix | Exchange |
|--------|----------|
| *(none)* | US (NYSE / NASDAQ) |
| `.L` | London |
| `.DE` | Frankfurt |
| `.PA` | Paris |
| `.AS` | Amsterdam |
| `.MC` | Madrid |
| `.SW` | Swiss Exchange |

Crypto, ETFs, REITs, bonds, and emerging-market funds are defined as static dicts — no scraping needed because their tickers rarely change.

### `TICKER_COLORS` — brand colours for charts

At the bottom of `stocks.py` sits a large dict mapping tickers to hex colour codes. Each colour is chosen to be legible on **both light and dark backgrounds** — hence why you'll see comments like:

```python
"DIS":    "#3b5ce6",  # Disney (brightened from brand #113ccf for dark-mode visibility)
```

These colours are used later in the allocation bar chart and the comparison chart to give each ticker a consistent, recognisable identity across the UI.

**Key takeaways:**
- Wikipedia is used as a live, free source of index constituent lists.
- `pd.read_html()` converts HTML tables into DataFrames in one call.
- The `suffix` parameter adapts a single scraping function to every supported exchange.
- Static dicts handle assets with stable, well-known tickers (crypto, ETFs, etc.).

---

## 2. `data_fetch.py` — Prices, Fundamentals, and Caching

This file is the main interface to `yfinance`. Every piece of market data the dashboard displays passes through one of these functions. The defining characteristic of this file is the **caching strategy** — every single function is decorated with `@st.cache_data`.

### Why caching matters here

Streamlit reruns your script from top to bottom on every user interaction. Without caching, every click on a tab, every slider adjustment, would trigger a fresh HTTP request to Yahoo Finance — this would be unbearably slow and would hit rate limits quickly.

`@st.cache_data(ttl=N)` stores the function's return value in memory (keyed by the function name plus its arguments) and reuses it for `N` seconds. If the same ticker is requested again within the TTL window, the network call is skipped entirely.

### Two-tier price history

```python
@st.cache_data(ttl=900)   # 15 minutes — current price data
def fetch_price_history_short(ticker: str) -> pd.DataFrame:
    hist = yf.Ticker(ticker).history(period="6mo")
    hist.index = hist.index.tz_localize(None)
    return hist

@st.cache_data(ttl=86400)  # 24 hours — historical chart data
def fetch_price_history_long(ticker: str) -> pd.DataFrame:
    hist = yf.Ticker(ticker).history(period="max")
    hist.index = hist.index.tz_localize(None)
    return hist
```

Notice the TTL split:
- **Short history** (6 months) uses a **15-minute TTL** — you need it to be fresh because it drives the current price and today's gain/loss.
- **Long history** (full history, or 1-year analytics data) uses a **24-hour TTL** — this data is used for trend charts and risk calculations where a few hours' lag is acceptable.

The `.tz_localize(None)` call strips timezone information from the index. Yahoo Finance returns timezone-aware timestamps (`datetime64[ns, America/New_York]`), but Pandas comparisons with plain dates (e.g., `df.index > "2024-01-01"`) fail if one side is timezone-aware and the other isn't. Stripping the timezone makes the index a plain `datetime64[ns]` and keeps downstream code simple.

### Fundamentals: defensive parsing

```python
@st.cache_data(ttl=86400)
def fetch_fundamentals(ticker: str) -> dict:
    info = yf.Ticker(ticker).info
    current  = info.get("currentPrice") or info.get("regularMarketPrice")
    div_rate = info.get("dividendRate")

    if div_rate and current and current > 0:
        candidate = round(div_rate / current * 100, 4)
        div_pct = candidate if candidate <= 20.0 else None
    ...
```

`yf.Ticker.info` returns a large dict of metadata — P/E ratios, dividend rates, 52-week ranges, and more. But yfinance is not a polished API: fields are sometimes missing, sometimes in inconsistent units, and sometimes outright wrong.

Notice the guard `candidate <= 20.0`: if the computed yield is above 20%, the code assumes there's a **unit mismatch** (e.g., `dividendRate` was returned in cents instead of dollars for a London stock) and falls back to the `dividendYield` field instead. This kind of defensive coding is essential when working with third-party market data APIs.

### Monte Carlo wrappers

The bottom of `data_fetch.py` contains cached wrappers for the Monte Carlo simulation engine:

```python
@st.cache_data(ttl=86400)
def cached_run_monte_carlo_portfolio(portfolio, price_data, ...):
    return run_monte_carlo_portfolio(...)
```

These exist because simulations are computationally expensive (thousands of random paths). Wrapping them in `@st.cache_data` means the simulation only reruns when the portfolio or price data actually changes — not on every Streamlit rerun triggered by a UI event.

### `load_stock_options` — the master catalogue

```python
@st.cache_data(ttl=86400)
def load_stock_options() -> dict:
    return {
        "US — S&P 500":       get_sp500_stocks(),
        "UK — FTSE 100":      get_ftse100_stocks(),
        ...
        "Crypto":             get_crypto(),
        "Commodities":        get_commodities(),
    }
```

This single cached call aggregates all Wikipedia scrapes into one dict of dicts. Because it's cached for 24 hours, the Wikipedia scrapes happen **once per day**, not on every page load.

**Key takeaways:**
- `@st.cache_data(ttl=N)` is the primary performance tool in this codebase.
- Two TTL tiers: 15 minutes for live prices, 24 hours for historical and fundamental data.
- Defensive parsing handles yfinance's inconsistent field values (especially for dividends).
- `.tz_localize(None)` is a recurring pattern to keep timestamp comparisons clean.

---

## 3. `fx.py` — Currency Detection and Conversion

The dashboard supports portfolios that span multiple currencies (USD, GBP, EUR, CHF, crypto). `fx.py` handles all currency concerns in one place.

### Currency detection from ticker suffix

```python
def get_ticker_currency(ticker: str) -> str:
    if ticker.endswith(".L"):
        return "GBX"
    elif ticker.endswith((".DE", ".PA", ".AS", ".MC")):
        return "EUR"
    elif ticker.endswith(".SW"):
        return "CHF"
    return "USD"
```

Currency is inferred purely from the ticker string — no API call needed. The `.L` (London) case returns `"GBX"` rather than `"GBP"`. This is important:

> **The GBX/GBP distinction:** London-listed stocks trade in **pence** (GBX), not pounds (GBP). One pound = 100 pence. Yahoo Finance returns London stock prices in pence but other metadata (like `currentPrice` in `info`) sometimes in pounds — an inconsistency that causes significant confusion if not handled explicitly.

### The `normalize_gbx` helper

```python
def normalize_gbx(value, currency: str):
    if currency == "GBX":
        return value / 100
    return value
```

Wherever a price value is retrieved for a London ticker, it passes through this function to convert from pence to pounds before any further calculations. For example, if HSBA.L (HSBC) trades at 7,500p, `normalize_gbx(7500, "GBX")` returns `75.0` (£75).

### Live FX rates via yfinance

```python
@st.cache_data(ttl=900)
def get_fx_rate(from_currency: str, to_currency: str) -> float:
    if from_currency == to_currency:
        return 1.0
    if from_currency == "GBX":
        return get_fx_rate("GBP", to_currency) / 100  # pence: divide GBP rate by 100
    pair = f"{from_currency}{to_currency}=X"
    rate = yf.Ticker(pair).history(period="1d")["Close"].iloc[-1]
    return float(rate)
```

Yahoo Finance exposes FX rates under ticker symbols like `"USDCHF=X"` (USD → CHF) or `"EURGBP=X"`. The function builds this pair string dynamically and fetches the latest closing price.

The GBX case is handled recursively: get the GBP rate first, then divide by 100.

If the lookup fails (network error, unsupported pair), the function falls back to `1.0` — meaning no conversion is applied rather than crashing. This is a pragmatic safety valve; the user sees numbers in their base currency rather than an error page.

### Historical FX for dividend calculation

```python
@st.cache_data(ttl=86400)
def get_historical_fx_rate(from_currency: str, to_currency: str, date_str: str) -> float:
    end = str((pd.Timestamp(date_str) + pd.DateOffset(days=7)).date())
    pair = f"{from_currency}{to_currency}=X"
    hist = yf.Ticker(pair).history(start=date_str, end=end)
    if not hist.empty:
        return float(hist["Close"].iloc[0])
    return get_fx_rate(from_currency, to_currency)  # live rate as fallback
```

This matters for **dividend tracking**: if you bought a FTSE 100 stock in 2022 when GBP/CHF was 1.15, the dividend received at that time should be converted at the 2022 rate, not today's rate. The 7-day window (`DateOffset(days=7)`) accounts for weekends and bank holidays when FX markets are closed — it fetches the first available trading day on or after the target date.

**Key takeaways:**
- Currency is detected from the ticker suffix — fast, no API needed.
- `"GBX"` (pence) is a distinct internal code that requires a `/100` correction everywhere.
- Live FX rates are fetched from Yahoo Finance using `"{CCY1}{CCY2}=X"` ticker pairs.
- Historical FX rates are used for accurate dividend P&L calculations per lot.
- All FX functions fall back gracefully rather than raising exceptions.

---

## Putting It All Together

Here's how these three modules interact at startup:

```
app.py calls load_stock_options()
    └─ data_fetch.py calls get_sp500_stocks(), get_ftse100_stocks(), ...
        └─ stocks.py scrapes Wikipedia → returns {name: ticker} dicts

User adds HSBA.L to portfolio
    └─ data_fetch.py calls fetch_price_history_short("HSBA.L")
        └─ yfinance returns price in GBX (pence)
    └─ fx.py: get_ticker_currency("HSBA.L") → "GBX"
    └─ fx.py: normalize_gbx(price, "GBX") → price / 100 → GBP
    └─ fx.py: get_fx_rate("GBX", "CHF") → GBP/CHF / 100 → CHF value
```

---

## What's Next — Day 3: Portfolio Core (`portfolio.py`, `state.py`)

Tomorrow we look at how the app **stores and computes** your portfolio. You'll learn how positions are represented as lists of dicts, how the app handles buying the same ticker multiple times at different prices (multi-lot support), and how P&L and dividends are actually calculated — including a concrete walkthrough with real numbers.
