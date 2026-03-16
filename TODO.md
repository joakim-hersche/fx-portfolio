# Market Dashboard — To Do List

A prioritised roadmap of improvements, fixes, and stretch goals. Updated March 2026.

-----

## P0 — Quick Wins (Do Before Sharing)

> High-visibility polish items a recruiter will notice in the first 30 seconds.

### ~~Embed Screenshot or GIF in README~~ ✅

- Replaced PDF with inline PNG screenshots in README (overview, KPI cards, positions table, allocation chart, normalised performance, price history)


### ~~Clean Up requirements.txt~~ ✅

- Trimmed to 7 direct dependencies: `streamlit`, `yfinance`, `pandas`, `plotly`, `requests`, `lxml`, `openpyxl`

### ~~Remove .DS_Store and Add to .gitignore~~ ✅

- `.DS_Store` removed from git tracking and added to `.gitignore`

### ~~Add Repo Description and Topics on GitHub~~ ✅

- Description and topic tags added to GitHub repo About section

### ~~Add Total Return KPI Cards~~ ✅

- Total Return KPI card added showing absolute amount and % alongside Total Value, Today's Change, and Positions

### ~~Add Development Notes to README~~ ✅

- Technical Notes section added to README covering GBX handling, dividend adjustment, tiered caching, multi-lot support, and error handling

### README GIF

- **What:** Replace static PNG screenshots with an animated GIF or short screen recording showing the dashboard in action
- **Why:** A GIF shows interactivity — hovering, toggling, expanding charts — in a way static screenshots can't; highest-ROI visual change remaining
- **How:** QuickTime screen recording → convert to GIF with ezgif.com → replace hero image in README

-----

## P1 — Investment Analytics

> Risk and fundamental metrics that add serious analytical depth.

### ~~Sharpe Ratio~~ ✅

- Implemented in `src/portfolio.py`; displayed in risk analytics table with colour coding

### ~~Volatility (Annualised)~~ ✅

- `daily_returns.std() * sqrt(252)` per ticker; shown in risk analytics table

### ~~Beta vs S&P 500~~ ✅

- SPY fetched via `fetch_analytics_history`; regression slope computed in `compute_analytics` and shown as "Market Sensitivity" in the risk table

### ~~Max Drawdown~~ ✅

- Worst peak-to-trough drop per ticker; shown in risk analytics table as "Worst Drop (%)"

### ~~Correlation Matrix~~ ✅

- Pairwise correlation heatmap using `px.imshow` in `app.py`, with "Correlation" legend label

### ~~Fundamental Snapshot (P/E, Div Yield, 52-week range)~~ ✅

- `fetch_fundamentals()` pulls `trailingPE`, `dividendYield`, `fiftyTwoWeekHigh/Low` from `ticker.info`; displayed in a fundamentals table per position

### Performance Attribution

- **What:** Table showing each position's contribution to total portfolio return (`weight × return` per ticker)
- **Why:** Standard in any professional portfolio view — immediately shows which positions drove or dragged performance; analytically strong and straightforward to implement
- **How:** For each ticker: `contribution = (position_value / total_value) * return_pct`; display sorted by contribution
- **Files:** `app.py` — summary or analytics section

### Monte Carlo Simulation

- **What:** Project portfolio value forward (e.g. 1 year) with confidence intervals using simulated return paths
- **Why:** Visually compelling and technically impressive — shows probabilistic thinking about portfolio outcomes
- **How:** Sample from historical daily return distribution (mean + std per ticker), simulate N paths, plot percentile bands
- **Files:** `app.py` — new simulation section

-----

## P2 — Medium Priority

> Meaningful improvements to analytical depth and UX.

### Split app.py into Modules

- **What:** Extract chart rendering, KPI cards, and portfolio display into separate modules
- **Why:** At 1013 lines `app.py` is a monolith — a recruiter targeting engineering roles will notice; the `src/` pattern is already established
- **How:** `src/charts.py` for Plotly figure builders, `src/ui.py` for KPI cards and styled table
- **Files:** `app.py`, new `src/` modules

### Analyst Target Price

- **What:** Add a column showing the analyst consensus target price and implied upside/downside % from current price
- **Why:** Valuation context beyond P/E — shows where the street thinks the stock is going; finance audiences expect this
- **How:** `ticker.info["targetMeanPrice"]`; upside = `(target - current) / current * 100`
- **Files:** `app.py` — fundamentals table

### Rebalancing Calculator

- **What:** Let the user set a target % per position; show deviation from target and how much to buy/sell to rebalance
- **Why:** Practical tool for real investors — differentiates from basic dashboards that only show current state
- **How:** Input target weights per ticker; compare to current weights; output required trades in shares and currency
- **Files:** `app.py` — new rebalancing section

### Dividend Income Chart

- **What:** Monthly bar chart of dividend income received across all positions
- **Why:** The dividend data is already fetched per lot — aggregating it by month adds a genuinely useful view for income investors and is visually distinct from everything else in the dashboard
- **How:** Group dividend records by ex-dividend month, sum in base currency, plot as `px.bar`
- **Files:** `app.py` — dividends section

### Weighted Average Cost Basis

- **What:** When a ticker has multiple lots, show the blended average buy price across all lots
- **Why:** Standard portfolio reporting — investors think in terms of average cost basis, not individual lot prices
- **How:** Calculate `sum(shares * buy_price) / sum(shares)` across all lots per ticker and display as a summary row
- **Files:** `app.py` — portfolio table

### ~~Total Return in Currency Terms~~ ✅

- Total Return KPI card shows absolute amount in base currency alongside the percentage

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

### ~~Chart Period Presets~~ ✅

- Added to both price history (3M / 6M / 1Y / 2Y / Since purchase / Custom) and normalised comparison chart (3M / 6M / 1Y / All time)

### Portfolio Table Summary View

- **What:** Group multiple lots per ticker into a single summary row with total shares, weighted average cost, combined value, and expandable lot detail
- **Why:** With 11 columns the table already requires horizontal scrolling — adding lots per ticker makes it worse; investors think in positions not lots
- **How:** Aggregate by ticker in `build_portfolio_df`, show lot detail in an expander or sub-table
- **Files:** `src/portfolio.py`, `app.py` — portfolio table

### ~~Weight Bar Chart (Replace or Supplement Pie)~~ ✅

- Replaced pie chart with horizontal bar chart sorted by weight %; brand colors preserved

### Manage Positions Compact Layout

- **What:** Group lots by ticker in the Manage Positions section to reduce vertical space
- **Why:** Eight individual lot rows push all content far down the page — one row per ticker with lot count is sufficient
- **Files:** `app.py` — manage positions section

### Unit Tests

- **What:** Add `tests/test_portfolio.py` with unit tests for core calculation logic
- **Why:** `portfolio.py` has non-trivial logic (dividend FX conversion, return %, cost basis) — tests show correctness and engineering discipline
- **How:** pytest test cases for: dividend calculation, GBX conversion, return formula with dividends, multiple lots, empty portfolio
- **Files:** `tests/test_portfolio.py` (new)

### ~~Remove scratch notebooks~~ ✅

- Removed `notebooks/test.ipynb` and `notebooks/01_data_exploration.ipynb` — both were scratch/exploration work with no value in the repo

### Mobile Responsiveness

- **What:** Fix the 4-column input layout on mobile screens
- **Why:** The columns collapse poorly on small screens — tested and confirmed on iPhone
- **How:** Stack input fields vertically on mobile using `st.columns([1])` or conditional column counts
- **Files:** `app.py` — portfolio input section

-----

## P3 — Polish & Stretch Goals

> Final layer of quality and presentation.

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

### ~~Custom Streamlit Subdomain~~ ✅

- Live at `market-dashboard-open-source-project.streamlit.app`

### LinkedIn Post

- **What:** Write and publish a LinkedIn post about the project
- **Why:** Highest-ROI action for recruiter visibility — a post with a live demo link will outperform a static profile update
- **Content:** What you built, what problem it solves, tech stack, link to live app and GitHub

-----

## Known Limitations (Document in README)

|Limitation                      |Impact                                                           |Fix Priority             |
|--------------------------------|-----------------------------------------------------------------|-------------------------|
|Dividends not included in return|Understates returns for income stocks                            |Done ✅                  |
|No real-time quotes             |Prices reflect last market close, not live intraday              |Low — yfinance limitation|
|App sleeps after inactivity     |30 second wake-up delay on Streamlit Community Cloud             |Low — platform limitation|
|~15 position practical limit    |Performance degrades significantly beyond this                   |Low — caching now in place|
|yfinance unofficial API         |Yahoo Finance can block requests without warning                 |Low — error handling in place|

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
- Data caching — `fetch_price_history_short` (15 min TTL) and `fetch_price_history_long` (24 hr TTL); stock list cached for 24 hours
- Lazy chart loading — price history charts wrapped in `st.expander`, only render when opened
- Rate limiting protection — all yfinance calls wrapped in try/except, graceful fallback to `st.warning` instead of crash
- JSON import validation — structure checked for expected keys before applying to session state; clear error on invalid or unreadable file
- Chart color differentiation — `px.colors.qualitative.Plotly` applied consistently across pie and line charts
- Conditional table formatting — Return and Daily P&L columns colour-coded green/red via Pandas Styler
- Index-filtered stock selector — two-step dropdown (index → stock) replaces flat 500+ item list
- KPI cards — custom HTML metric cards with green/red border on Daily P&L based on sign
- Brand colors — `TICKER_COLORS` dict in `src/stocks.py` maps known tickers to brand hex; fallback palette is a neutral set of blues, purples, and teals (no red/green to avoid misleading gain/loss signals)
- Dividend adjustment — dividends received per lot summed from purchase date via yfinance `history()`, factored into Return (%) and shown as a separate column
- UX improvements from investor usability review — confirmation dialogs for Clear All and × remove, div yield bug fix (European tickers), combined Total Return KPI card, "last updated" timestamp, "Buy #" column label, "Advanced" removed from Risk section title
- Chart period presets — 3M / 6M / 1Y / All time on comparison chart; 3M / 6M / 1Y / 2Y / Since purchase / Custom on price history
- Price history From/To date range — configurable start date per chart
- Correlation heatmap "Correlation" legend label added
- Stock Market field — tooltip replaced with always-visible caption
- Scratch notebooks removed from repo
- README inline screenshots (PNG) replacing PDF
- requirements.txt trimmed to 7 direct dependencies
- .DS_Store removed from git tracking and added to .gitignore
- Technical Notes section added to README (GBX handling, dividend FX, caching, multi-lot, error handling)
- Total Return KPI card — absolute amount and % in base currency
- Sharpe Ratio, Volatility, Beta, Max Drawdown — computed in `src/portfolio.py`, displayed in risk analytics table
- Correlation heatmap — pairwise daily returns heatmap via `px.imshow`
- Fundamental Snapshot — P/E, dividend yield, 52-week range fetched from `ticker.info`