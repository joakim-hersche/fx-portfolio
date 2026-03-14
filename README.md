# Market Dashboard

A real-time stock portfolio tracker built with Streamlit. Add positions across major global exchanges, monitor performance in your home currency, and visualise portfolio allocation and price history. Built as a portfolio project for data/business analyst roles in Finance and FinTech.

![Dashboard Overview](Screenshots/01_overview.png)

[![Live Demo](https://img.shields.io/badge/Live%20Demo-Streamlit-red)](https://market-dashboard-open-source-project.streamlit.app)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)

## Features

- **Portfolio management** — add and remove positions across multiple lots per ticker
- **Multi-currency support** — live FX conversion across USD, EUR, GBP, and CHF
- **Performance metrics** — current value, daily P&L, return %, and portfolio weight per position; colour-coded green/red in the positions table
- **Dividend tracking** — dividends fetched from purchase date with historical FX conversion, factored into total return
- **Interactive charts** — portfolio allocation bar chart, normalised performance comparison with configurable time range (3M / 6M / 1Y / All time), and individual price history with buy price and purchase date overlays; click legend items to show/hide individual lines
- **Global stock coverage** — S&P 500, FTSE 100, DAX, CAC 40, SMI, AEX, IBEX 35, ETFs, crypto, and commodities; searchable via index-filtered dropdown
- **Import / export** — save and load your portfolio as JSON, with validated parsing on import
- **Performance** — all price data and stock lists are cached; price history charts lazy-load on demand

## Screenshots

### Positions Table
Colour-coded returns and P&L, with dividends, weight, and per-lot tracking across multiple exchanges.

![Positions Table](Screenshots/03_positions_table.png)

### Portfolio Allocation
Horizontal bar chart sorted by weight, with brand colours for known tickers.

![Portfolio Allocation](Screenshots/04_portfolio_allocation.png)

### Normalised Performance
Comparison chart with all positions rebased to 100. Configurable time range (3M / 6M / 1Y / All time). Toggle currency-adjusted mode. Click legend to show/hide individual stocks.

![Normalised Performance](Screenshots/05_normalised_performance.png)

### Price History
Per-ticker price chart with buy price overlays (yellow) and purchase date markers for each lot. Configurable date range with presets (3M / 6M / 1Y / 2Y / Since purchase) or custom from/to dates.

![Price History](Screenshots/06_price_history.png)

## Setup

1. Clone the repository
```
git clone https://github.com/joakim-hersche/market-dashboard.git
cd market-dashboard
```

2. Install dependencies
```
pip install -r requirements.txt
```

3. Run the app
```
streamlit run app.py
```

## Project Structure

```
market-dashboard/
├── app.py                # Streamlit application
├── src/
│   ├── portfolio.py      # Portfolio construction and P&L calculations
│   ├── stocks.py         # Stock list fetching (Wikipedia scraper)
│   └── fx.py             # FX rate fetching and currency detection
├── data/
│   └── sample_portfolio.json
├── Screenshots/
├── requirements.txt
└── README.md
```

## Tech Stack

- Python 3.12
- [Streamlit](https://streamlit.io) — web UI
- [yfinance](https://github.com/ranaroussi/yfinance) — real-time stock, FX, and dividend data
- [pandas](https://pandas.pydata.org) — data processing
- [Plotly](https://plotly.com/python/) — interactive charts

## Technical Notes

- **GBX/GBP handling** — London Stock Exchange tickers (`.L`) are quoted in pence by yfinance. All `.L` prices are divided by 100 before P&L or FX calculations to correct for this.
- **Dividend adjustment** — dividends are fetched per lot from the purchase date using `yfinance.Ticker.history()`. Historical FX rates are applied at each ex-dividend date so cross-currency income positions are converted accurately, not at today's rate.
- **Tiered caching** — two `@st.cache_data` TTLs: 15 minutes for current quotes (acceptable staleness for intraday use) and 24 hours for full price history and stock lists (expensive fetches that rarely change).
- **Multi-lot support** — each ticker can hold multiple lots with independent purchase dates and prices. The normalised chart groups by ticker using the earliest lot's start date.
- **Error handling** — all yfinance calls are wrapped in try/except with graceful `st.warning` fallbacks, so a single failed ticker doesn't crash the dashboard.
