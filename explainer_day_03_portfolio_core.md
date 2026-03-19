# Day 3 — Portfolio Core: `portfolio.py` & State Management

*~10 minute read · Session 3 of 10*

---

Yesterday we explored the data layer — how the app fetches stock lists, prices, and FX rates. Today we focus on the **portfolio engine**: how your positions are stored, how profit and loss is calculated, and how state is persisted across sessions. This is the heart of the dashboard.

> **Note on the codebase:** The original curriculum mentioned a dedicated `state.py` file. In the current NiceGUI-based version, state management has been folded directly into `main.py`, using NiceGUI's built-in `app.storage.user` instead of Streamlit's `st.session_state`. The portfolio calculation logic remains in `src/portfolio.py`.

---

## 1. How Positions Are Stored

The entire portfolio is a Python `dict` where each key is a ticker string and each value is a **list of lots** (individual purchase entries):

```python
{
    "AAPL": [
        {
            "shares": 10,
            "buy_price": 150.00,
            "buy_fx_rate": 1.0,
            "purchase_date": "2024-01-15",
            "manual_price": False,
        },
        {
            "shares": 5,
            "buy_price": 170.00,
            "buy_fx_rate": 1.0,
            "purchase_date": "2024-06-01",
            "manual_price": False,
        },
    ],
    "NESN.SW": [
        {
            "shares": 20,
            "buy_price": 105.50,
            "buy_fx_rate": 0.88,
            "purchase_date": "2023-11-20",
            "manual_price": False,
        },
    ],
}
```

Each lot records five things:

- **`shares`**: How many shares (or fractional units for crypto/commodities).
- **`buy_price`**: The price per share at purchase, in the stock's native currency.
- **`buy_fx_rate`**: The exchange rate from the stock's currency to your display currency on the day of purchase. For a US investor buying AAPL, this is simply `1.0`. For the same investor buying Nestle (`NESN.SW`, priced in CHF), it might be `0.88` (CHF → USD).
- **`purchase_date`**: An ISO date string like `"2024-01-15"`. Optional — if you enter a price manually, this can be `None`.
- **`manual_price`**: Whether the user typed the buy price instead of having the app look it up.

### Why a list of lots?

This is **multi-lot support**. Real investors rarely buy a stock once and stop. You might buy 10 shares of Apple in January and another 5 in June at a different price. Rather than averaging those into a single entry, the app keeps each purchase separate. This gives you:

1. Accurate cost basis per lot — you can see exactly which purchases are profitable.
2. Correct dividend tracking — dividends are counted from each lot's individual purchase date.
3. The ability to remove a specific lot without touching others (though the current UI removes all lots for a ticker at once, with an undo option).

---

## 2. State Persistence: Encrypted Storage

The dashboard needs to remember your portfolio between visits. In the NiceGUI version, this is handled by two functions in `main.py`:

```python
_LS_KEY = "market_dashboard_portfolio"

def _load_portfolio() -> dict:
    """Load and decrypt portfolio from user storage."""
    raw = app.storage.user.get(_LS_KEY, {})
    if isinstance(raw, dict):
        return raw  # Legacy unencrypted data
    if isinstance(raw, str):
        try:
            decrypted = _fernet.decrypt(raw.encode())
            parsed = json.loads(decrypted)
            return parsed if isinstance(parsed, dict) else {}
        except InvalidToken:
            pass
        # Fallback: legacy unencrypted JSON string
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def _save_portfolio(data: dict) -> None:
    """Encrypt and persist portfolio to user storage."""
    plaintext = json.dumps(data, default=str).encode()
    app.storage.user[_LS_KEY] = _fernet.encrypt(plaintext).decode()
```

There are several layers worth understanding here.

### What is `app.storage.user`?

NiceGUI provides a per-user storage dict backed by a server-side file. When you visit the dashboard, NiceGUI assigns you a cookie-based session and keeps a JSON file for your data. This replaces the browser-only `localStorage` approach from the Streamlit era.

### Why encryption?

The stored JSON file sits on the server's filesystem. Even though this is typically a personal deployment, the code takes a security-conscious approach: your portfolio data (ticker symbols, share counts, prices) is encrypted at rest using **Fernet symmetric encryption** (from the `cryptography` library).

The encryption key is derived from a secret via PBKDF2:

```python
_STORAGE_SECRET = os.environ.get("STORAGE_SECRET", "market-dashboard-dev-fallback")
_kdf = PBKDF2HMAC(
    algorithm=hashes.SHA256(),
    length=32,
    salt=b"market-dashboard-portfolio-salt",
    iterations=480_000,
)
_fernet = Fernet(base64.urlsafe_b64encode(_kdf.derive(_STORAGE_SECRET.encode())))
```

In production you'd set the `STORAGE_SECRET` environment variable to something strong. During development, a deterministic fallback is used (and a warning is logged).

### The load fallback chain

`_load_portfolio` handles three data formats for backwards compatibility:

1. **Plain dict** — old data that was never encrypted. Just return it.
2. **Fernet-encrypted string** — the current format. Decrypt, parse JSON, return.
3. **Plain JSON string** — old data stored as a string but not encrypted. Parse and return.

This graceful migration means users upgrading from the Streamlit version don't lose their portfolios.

### What's inside the stored dict?

The stored object wraps the portfolio with a top-level dict:

```python
{
    "portfolio": { "AAPL": [...], "NESN.SW": [...] },
    "currency": "USD"
}
```

The portfolio data and the user's chosen display currency travel together. When you change currencies in the top bar, the app calls `_save_portfolio` with the updated currency key.

---

## 3. Adding a Position: The Full Flow

When you fill in the sidebar form and click "Add Position", here's what happens inside `_on_add_position_inner()`:

**Step 1: Validation**

```python
if not ticker:
    ui.notify("Please select a stock.", type="warning")
    return
if shares_input.value is None or shares_input.value <= 0:
    ui.notify("Please enter the number of shares.", type="warning")
    return
```

Standard guard clauses. The function bails early with a notification if anything is missing.

**Step 2: Determine the buy price**

There are two paths. If `manual_price` is checked, the user typed a price directly and no API call is needed. Otherwise, the app calls `fetch_buy_price`:

```python
result = await run.io_bound(fetch_buy_price, ticker, str(purchase_date))
if result is None:
    ui.notify("No price data found for that date.", type="negative")
    return
buy_price, actual_date = result
```

`fetch_buy_price` (in `portfolio.py`) looks up the closing price on or just after the given date. If the purchase date was a weekend or holiday, it returns the next trading day's price and tells you. For example, if you say you bought on Saturday January 13, the app uses Monday January 15's close and shows an info message.

The `await run.io_bound(...)` pattern is NiceGUI's way of running blocking I/O (the Yahoo Finance API call) without freezing the UI. It's essentially `asyncio.to_thread()` under the hood.

**Step 3: Capture the FX rate**

```python
buy_fx_rate = await run.io_bound(
    get_historical_fx_rate, ticker_currency, base_currency, str(purchase_date)
)
```

If you're tracking your portfolio in USD but bought a Swiss stock priced in CHF, the app records what CHF/USD was on that day. This matters for accurate cost basis in your display currency.

**Step 4: Build the lot and save**

```python
lot = {
    "shares": shares,
    "buy_price": buy_price,
    "buy_fx_rate": buy_fx_rate,
    "purchase_date": str(purchase_date) if purchase_date else None,
    "manual_price": manual,
}
portfolio.setdefault(ticker, []).append(lot)
stored = _load_portfolio()
stored["portfolio"] = portfolio
_save_portfolio(stored)
```

`dict.setdefault(ticker, [])` is a clean Python pattern: if the ticker key doesn't exist yet, create it with an empty list, then append the new lot to that list. The portfolio is then re-saved to encrypted storage.

**Step 5: Refresh the UI**

```python
positions_list.refresh()
if on_mutation and on_mutation.get("fn"):
    on_mutation["fn"]()
```

NiceGUI's `@ui.refreshable` decorator lets you re-render a specific section without reloading the entire page. The mutation callback triggers a rebuild of the active tab so the KPI cards and charts update with the new position.

---

## 4. Building the Portfolio DataFrame: `build_portfolio_df`

This is the core calculation function in `portfolio.py`. It takes the raw portfolio dict and currency string, and returns a pandas DataFrame with one row per lot, containing everything the UI needs to display.

Here's the conceptual flow (reconstructed from the codebase):

```
For each ticker in portfolio:
    For each lot under that ticker:
        1. Get current price from Yahoo Finance
        2. Get yesterday's closing price (for daily change)
        3. Convert to display currency using current FX rate
        4. Calculate dividends received since purchase date
        5. Compute cost basis, current value, return %, daily P&L
        → One row in the DataFrame
```

The resulting DataFrame has columns like:

| Column | What it contains |
|--------|-----------------|
| `Ticker` | Stock symbol |
| `Shares` | Number of shares in this lot |
| `Buy Price` | Original purchase price (in display currency) |
| `Current Price` | Live price (in display currency) |
| `Total Value` | `Shares × Current Price` |
| `Dividends` | Total dividends received since purchase, FX-adjusted |
| `Daily P&L` | Change in value since yesterday's close |
| `Return (%)` | Total return as a percentage of cost basis |
| `Weight (%)` | This lot's share of the total portfolio value |
| `Purchase Date` | When the lot was bought |

### A concrete example

Say you bought 10 shares of AAPL at $150 on January 15, then 5 more at $170 on June 1. AAPL is currently at $185 and yesterday it was $183.

**Lot 1** (10 shares at $150):
- Cost basis: 10 × $150 = $1,500
- Current value: 10 × $185 = $1,850
- Daily P&L: 10 × ($185 - $183) = $20
- Return: ($1,850 - $1,500) / $1,500 = 23.3%

**Lot 2** (5 shares at $170):
- Cost basis: 5 × $170 = $850
- Current value: 5 × $185 = $925
- Daily P&L: 5 × ($185 - $183) = $10
- Return: ($925 - $850) / $850 = 8.8%

The KPI cards in the overview then aggregate across all lots: total value = $2,775, total cost basis = $2,350, total return = $425 (18.1%), today's change = $30.

---

## 5. Dividend Tracking: `_dividends_in_base_currency`

Dividends are tracked per lot, starting from that lot's purchase date. The function (internal to `portfolio.py`) does the following:

1. Fetch the ticker's full dividend history via `yfinance`.
2. Filter to only dividends paid **after** the lot's purchase date.
3. Sum those dividends (per share).
4. If the stock trades in a different currency from your display currency, fetch historical FX rates and convert each dividend at the rate on its payment date.

This means if you bought 20 shares of a UK stock on March 1, 2024, and it paid a 10p dividend in June and a 12p dividend in December, the function sums those two payments, converts each from GBP to your base currency using the FX rate on that specific day, and multiplies by your 20 shares.

The GBX/GBP correction from Day 2 applies here too — London-listed dividends come in pence (GBX), and the function converts them to pounds (GBP) before doing the FX lookup.

---

## 6. Risk Analytics: `compute_analytics`

`portfolio.py` also contains `compute_analytics`, which calculates per-ticker risk metrics from one year of price history. We'll cover these metrics in detail on Day 7 (Risk Analytics), but here's the high-level structure:

```python
def compute_analytics(portfolio, price_data, spy_data) -> pd.DataFrame:
    """
    price_data: {ticker: DataFrame with 'Close' column}
    spy_data:   DataFrame with 'Close' column (SPY benchmark)
    Returns: Ticker, Volatility, Max Drawdown, Sharpe Ratio, Beta
    """
```

For each ticker it computes daily returns, then derives:
- **Volatility** — annualized standard deviation
- **Max Drawdown** — worst peak-to-trough decline
- **Sharpe Ratio** — excess return per unit of risk
- **Beta** — sensitivity relative to the S&P 500

The SPY benchmark data is passed in separately so the function doesn't need to fetch it — keeping calculation and data-fetching cleanly separated.

---

## 7. Fetching Buy Prices: `fetch_buy_price`

```python
def fetch_buy_price(ticker, purchase_date) -> tuple | None:
    """
    Fetch closing price on or just after a given purchase date.
    Returns (price, actual_date_str) or None if no data within 7 days.
    """
```

This function handles the common edge case where your purchase date falls on a non-trading day. It requests price data for a 7-day window starting from the given date and returns the first available close. If nothing is found within that window, it returns `None` and the UI shows an error message.

The return value is a tuple `(price, actual_date_string)` — the actual date is included so the caller can detect and report date adjustments (e.g., "Saturday → Monday").

---

## Key Takeaways

- **The portfolio is a `dict[str, list[dict]]`** — ticker keys, each mapping to a list of lot dicts with shares, buy price, FX rate, date, and a manual-price flag.
- **Multi-lot support** keeps each purchase separate for accurate per-lot P&L and dividend tracking.
- **State is encrypted at rest** using Fernet symmetric encryption, with a PBKDF2-derived key. The load function handles three historical formats for backwards compatibility.
- **`build_portfolio_df`** is the central calculation engine — it takes raw lots and produces a display-ready DataFrame with current values, returns, dividends, and daily changes, all in your chosen currency.
- **Dividend tracking is date-aware and FX-aware** — dividends are only counted from each lot's purchase date, and converted at historical rates.
- **`fetch_buy_price` handles non-trading-day purchases** gracefully by sliding forward up to 7 days.

---

## What's Next

**Day 4** dives into the Positions Table and Allocation sections — how the raw DataFrame from `build_portfolio_df` gets transformed into the styled positions table you see in the UI, how color coding works for gains and losses, and how the allocation bar chart is built and sorted.
