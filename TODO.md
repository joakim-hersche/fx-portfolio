# Market Dashboard — To Do List

A prioritised roadmap of improvements, fixes, and stretch goals. Updated March 2026.

-----

## P0 — Quick Wins (Do Before Sharing)

> High-visibility polish items a recruiter will notice in the first 30 seconds.

### Embed Screenshot or GIF in README

- **What:** Add an embedded screenshot or animated GIF showing the live dashboard
- **Why:** Recruiters spend 5–10 seconds on the README before deciding whether to click the live demo — a visual is the highest-ROI change possible
- **How:** QuickTime screen recording → convert to GIF with ezgif.com → embed with `![Dashboard](screenshots/demo.gif)`
- **Status:** PDF exists in `screenshots/` but doesn't render inline on GitHub — replace with PNG or GIF

### Dark Mode Charts

- **What:** Apply `template="plotly_dark"` to all Plotly charts
- **Why:** Charts currently have a light background that clashes visibly with Streamlit's dark theme — noticeable on the live dashboard
- **How:** Add `.update_layout(template="plotly_dark")` to every `px.line()`, `px.pie()`, and `px.imshow()` call
- **Files:** `app.py`

### Clean Up requirements.txt

- **What:** Trim requirements.txt to only direct dependencies
- **Why:** Current file is a full pip freeze (~130 packages) including FastAPI, uvicorn, Jupyter, pytest — none of which are used by this app; a recruiter will wonder why a Streamlit dashboard needs FastAPI
- **How:** Replace with a minimal list: `streamlit`, `yfinance`, `pandas`, `plotly`, `requests`, `lxml`; keep full freeze as `requirements-lock.txt` if needed

### Remove .DS_Store and Add to .gitignore

- **What:** Delete the committed `.DS_Store` file and prevent future commits
- **Why:** macOS metadata file has no place in a repo — small thing but engineers notice it
- **How:** `git rm --cached .DS_Store`, add `.DS_Store` to `.gitignore`

### Add Repo Description and Topics on GitHub

- **What:** Add a one-line description, live app URL, and topic tags to the GitHub repo's About section
- **Why:** Currently shows "No description, website, or topics provided" — this is the first thing a recruiter sees on the repo page
- **How:** GitHub repo → About (gear icon) → add description, website URL, and tags: `python`, `streamlit`, `finance`, `portfolio-tracker`, `yfinance`, `plotly`

### Add Total Return KPI Cards

- **What:** Add total portfolio return ($ and %) as additional KPI cards alongside the existing three
- **Why:** Total Value, Daily P&L, and Positions count is sparse — total return is the most important metric and it's already computed in the DataFrame
- **How:** Sum `(Total Value - Cost Basis + Dividends)` across all rows; display as two additional KPI cards

### Add Development Notes to README

- **What:** Add a brief section explaining key technical decisions (GBX handling, historical FX dividends, tiered caching, etc.)
- **Why:** With all 26 commits from a two-day burst, a recruiter may wonder about AI involvement — explaining your decisions demonstrates genuine understanding
- **How:** 3–5 bullet points under a "Technical notes" section in the README

-----

## P1 — Investment Analytics

> Risk and fundamental metrics that add serious analytical depth.

### Sharpe Ratio

- **What:** Risk-adjusted return for each position and the overall portfolio
- **Why:** The single most recognised metric for comparing returns on a risk-adjusted basis — any quant or portfolio manager will look for this
- **How:** Use daily returns history (already fetched) — `(mean_daily_return / std_daily_return) * sqrt(252)` with a risk-free rate assumption (e.g. 4%)
- **Files:** `src/portfolio.py`, `app.py` — summary metrics section

### Volatility (Annualised)

- **What:** Annualised standard deviation of daily returns per position
- **Why:** Core risk metric — shows how much a stock swings relative to its return
- **How:** `daily_returns.std() * sqrt(252)` from price history
- **Files:** `src/portfolio.py`, `app.py` — positions table or risk panel

### Beta vs S&P 500

- **What:** Sensitivity of each position to S&P 500 moves
- **Why:** Standard risk measure — beta > 1 means more volatile than the market, < 1 means defensive
- **How:** Regress stock daily returns against SPY daily returns over the same period; slope = beta
- **Files:** `src/portfolio.py`, `app.py` — positions table

### Max Drawdown

- **What:** Largest peak-to-trough decline for each position over the holding period
- **Why:** Key downside risk metric used by fund managers — shows worst-case loss from a peak
- **How:** `(rolling_max - price) / rolling_max` — take the minimum over the period
- **Files:** `src/portfolio.py`, `app.py` — risk panel or positions table

### Correlation Matrix

- **What:** Heatmap showing how positions move relative to each other
- **Why:** Demonstrates diversification quality — low correlation between positions reduces portfolio risk
- **How:** Compute pairwise correlation of daily returns across all tickers; display as `px.imshow` heatmap
- **Files:** `app.py` — new analytics section

### Fundamental Snapshot (P/E, Div Yield, 52-week range)

- **What:** Per-stock panel showing P/E ratio, dividend yield, and 52-week high/low with current price position
- **Why:** Valuation context alongside price performance — rounds out the picture for any fundamental investor
- **How:** Pull from `ticker.info` — keys: `trailingPE`, `dividendYield`, `fiftyTwoWeekHigh`, `fiftyTwoWeekLow`
- **Files:** `app.py` — per-stock expander or new fundamentals table

### Monte Carlo Simulation

- **What:** Project portfolio value forward (e.g. 1 year) with confidence intervals using simulated return paths
- **Why:** Visually compelling and technically impressive — shows probabilistic thinking about portfolio outcomes
- **How:** Sample from historical daily return distribution (mean + std per ticker), simulate N paths, plot percentile bands
- **Files:** `app.py` — new simulation section

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

### ~~Chart Period Presets~~ ✅

- Added to both price history (3M / 6M / 1Y / 2Y / Since purchase / Custom) and normalised comparison chart (3M / 6M / 1Y / All time)

### Volume Chart

- **What:** Add trading volume as a bar chart below each price history chart
- **Why:** Standard in financial charting — volume confirms price moves and signals conviction
- **How:** Use Plotly’s secondary y-axis (`make_subplots`) to add volume bars below the price line
- **Files:** `app.py` — price history section

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

### Split app.py into Modules

- **What:** Extract form logic, chart rendering, and portfolio display into separate modules or helper functions
- **Why:** At ~400 lines `app.py` handles page config, CSS, session state, import/export, form, KPI cards, table, three chart sections — a recruiter targeting FinTech roles will notice the monolith
- **How:** Extend `src/` pattern: `src/charts.py` for Plotly figure builders, `src/ui.py` for KPI cards and styled table
- **Files:** `app.py`, new `src/` modules

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