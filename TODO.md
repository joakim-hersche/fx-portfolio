# Market Dashboard — To Do List

A prioritised roadmap of improvements, fixes, and stretch goals. Updated March 2026.

-----

## P0 — Critical

> Fixes that affect financial correctness or credibility. A finance recruiter will notice these.

### Dividend Adjustment

- **What:** Factor dividends into total return calculation
- **Why:** Return % currently ignores dividends received, significantly understating returns for dividend-paying stocks over long holding periods
- **How:** yfinance returns dividend data in `history()` — sum dividends received between purchase date and today and add to P&L
- **Files:** `app.py` — portfolio display loop

-----

## P1 — High Priority

> Significantly improves reliability, performance, and user experience.

### Performance: Data Caching

- **What:** Add `@st.cache_data` to all yfinance API calls
- **Why:** Currently refetches all price data on every single user interaction, causing multi-second lag with 5+ positions
- **How:** Wrap `yf.Ticker().history()` calls in cached functions with TTL of 15 minutes for current prices, 24 hours for historical data
- **Files:** `app.py`

### Performance: Lazy Chart Loading

- **What:** Only load price history charts when user expands them
- **Why:** `period="max"` fetches decades of data for every ticker on every rerun — the single heaviest operation in the app
- **How:** Wrap each chart in `st.expander(f"{ticker} Price History")` so they only render when opened
- **Files:** `app.py` — price history section

### Brand Colors

- **What:** Use brand colors for known tickers across all charts, with graceful fallback to Plotly palette
- **Why:** Visual polish — makes the dashboard feel intentional and professional
- **How:** Define `TICKER_COLORS` dictionary, apply via `color_discrete_map` in all `px.line()` and `px.pie()` calls
- **Status:** Color map drafted, needs implementing
- **Files:** `app.py`

### Rate Limiting Protection

- **What:** Wrap all yfinance calls in try/except with user-friendly error messages
- **Why:** Yahoo Finance rate limits requests without warning — currently causes unhandled exceptions that crash the app
- **How:** Catch `Exception` on all `yf.Ticker().history()` calls and display `st.warning()` instead of crashing
- **Files:** `app.py`

### JSON Import Validation

- **What:** Validate imported JSON structure before applying to session state
- **Why:** A malformed or incompatible JSON file currently crashes the app silently
- **How:** Check for expected keys (`shares`, `buy_price`, `purchase_date`) and display a clear error if invalid
- **Files:** `app.py` — import section

### Stock List Caching

- **What:** Cache the Wikipedia stock list fetches
- **Why:** Currently fetches from 7 Wikipedia pages on every cold start, adding 3–5 seconds to initial load
- **How:** Use `@st.cache_data(ttl=86400)` on all `get_*_stocks()` functions in `src/stocks.py`
- **Files:** `src/stocks.py`

-----

## P2 — Medium Priority

> Meaningful improvements to analytical depth and UX.

### Weighted Average Cost Basis

- **What:** When a ticker has multiple lots, show the blended average buy price across all lots
- **Why:** Standard portfolio reporting — investors think in terms of average cost basis, not individual lot prices
- **How:** Calculate `sum(shares * buy_price) / sum(shares)` across all lots per ticker and display as a summary row
- **Files:** `app.py` — portfolio table

### Total Return in Currency Terms

- **What:** Show absolute P&L in currency (e.g. +$1,240) alongside the percentage return
- **Why:** Both are expected in any professional portfolio view — % alone doesn’t convey scale
- **Files:** `app.py` — portfolio table and summary metrics

### Portfolio Benchmark Comparison

- **What:** Add an optional S&P 500 (SPY) or user-selected benchmark overlay to the normalised comparison chart
- **Why:** Showing performance relative to the market is the most analytically meaningful chart in the dashboard
- **How:** Fetch SPY data for the same period and add as an additional line to the normalised comparison chart
- **Files:** `app.py` — normalised comparison section

### Sector Breakdown Chart

- **What:** Add a pie chart showing portfolio allocation by sector (Technology, Healthcare, Finance, etc.)
- **Why:** Demonstrates analytical depth — sector concentration is a key portfolio risk concept
- **How:** Fetch `ticker.info["sector"]` from yfinance for each position and group by sector
- **Files:** `app.py`

### Market Status Indicator

- **What:** Show whether the US market is currently open and when prices were last updated
- **Why:** yfinance returns the last available price — users should know if they’re seeing today’s close or a stale quote
- **How:** Check current time against NYSE trading hours (09:30–16:00 ET, Mon–Fri) and display a status badge
- **Files:** `app.py` — header section

### Chart Period Presets

- **What:** Add preset buttons (1M, 3M, 6M, 1Y, 3Y, Max) to price history charts
- **Why:** More intuitive than a date picker — this is the standard UX pattern on Bloomberg, Yahoo Finance, Google Finance
- **How:** Replace or supplement the date picker with `st.radio` or `st.button` presets that calculate the date range
- **Files:** `app.py` — price history section

### Volume Chart

- **What:** Add trading volume as a bar chart below each price history chart
- **Why:** Standard in financial charting — volume confirms price moves and signals conviction
- **How:** Use Plotly’s secondary y-axis (`make_subplots`) to add volume bars below the price line
- **Files:** `app.py` — price history section

### Mobile Responsiveness

- **What:** Fix the 4-column input layout on mobile screens
- **Why:** The columns collapse poorly on small screens — tested and confirmed on iPhone
- **How:** Stack input fields vertically on mobile using `st.columns([1])` or conditional column counts
- **Files:** `app.py` — portfolio input section

-----

## P3 — Polish & Stretch Goals

> Final layer of quality and presentation.

### Dark Mode Chart Theming

- **What:** Set `template="plotly_dark"` on all Plotly charts
- **Why:** Plotly charts use a light background by default which clashes with Streamlit’s dark mode
- **Files:** `app.py` — all `px.line()` and `px.pie()` calls

### CSV Export

- **What:** Add a CSV export option alongside JSON
- **Why:** More universally useful — non-technical users can open it directly in Excel
- **How:** Use `df.to_csv()` with `st.download_button()`
- **Files:** `app.py` — export section

### Loading Spinners

- **What:** Wrap all data fetching in `st.spinner("Fetching data...")`
- **Why:** Currently the app freezes silently during API calls — users don’t know if something is loading or broken
- **Files:** `app.py`

### Error State for Delisted Stocks

- **What:** Handle tickers that have been delisted or changed since a portfolio was saved
- **Why:** A user importing an old portfolio could have stale tickers that crash the app
- **How:** Check if `data.empty` after fetching and display a warning row in the table instead of crashing
- **Files:** `app.py` — portfolio display loop

### Custom Streamlit Subdomain

- **What:** Change the deployed URL to something clean (e.g. `market-dashboard.streamlit.app`)
- **Why:** The current auto-generated URL is ugly and hard to share
- **How:** Streamlit app settings → Custom subdomain — takes 2 minutes
- **Status:** Do this before sharing with recruiters

### README Screenshot / GIF

- **What:** Add a GIF or short screen recording showing the dashboard in action
- **Why:** A GIF is far more compelling than a static screenshot for a portfolio piece — shows the interactivity
- **How:** Use a screen recorder (QuickTime on Mac), convert to GIF with ezgif.com, add to `screenshots/` folder and README

### LinkedIn Post

- **What:** Write and publish a LinkedIn post about the project
- **Why:** Highest-ROI action for recruiter visibility — a post with a live demo link will outperform a static profile update
- **Content:** What you built, what problem it solves, tech stack, link to live app and GitHub

-----

## Known Limitations (Document in README)

|Limitation                      |Impact                                                           |Fix Priority             |
|--------------------------------|-----------------------------------------------------------------|-------------------------|
|Dividends not included in return|Understates returns for income stocks                            |P0                       |
|No real-time quotes             |Prices reflect last market close, not live intraday              |Low — yfinance limitation|
|App sleeps after inactivity     |30 second wake-up delay on Streamlit Community Cloud             |Low — platform limitation|
|~15 position practical limit    |Performance degrades significantly beyond this                   |P1 (caching)             |
|yfinance unofficial API         |Yahoo Finance can block requests without warning                 |P1 (error handling)      |

-----

## Completed ✅

- Project structure and GitHub repo
- yfinance API integration
- pandas data cleaning (timezone stripping, column dropping)
- Daily returns and 20-day rolling average calculations
- Price history chart with rolling average overlay (matplotlib)
- Normalised multi-ticker comparison chart
- Streamlit dashboard with portfolio input UI
- Portfolio overview table (value, P&L, return %, weight)
- Summary metric cards (total value, daily P&L, positions)
- Remove position functionality
- Portfolio weights pie chart
- Interactive Plotly charts (zoomable, hoverable)
- S&P 500, FTSE 100, DAX, CAC 40, SMI, AEX, IBEX 35 stock lists
- ETF support
- Multiple lots per ticker
- Purchase date lookup via yfinance historical data
- Manual price entry option
- Buy price horizontal line on charts
- Purchase date vertical line on charts
- Chart default view starts 2 months before earliest purchase date
- JSON export and import
- Deployed to Streamlit Community Cloud
- README with live demo badge
- FX conversion — live rates via yfinance, all positions normalised to a single base currency
- GBX/GBP handling — `.L` ticker prices divided by 100 to correct pence-to-pounds conversion