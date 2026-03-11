# Market Dashboard

A real-time stock portfolio tracker built with Streamlit. Add positions across major global exchanges, monitor performance in your home currency, and visualise portfolio allocation and price history. Built as a portfolio project for data/business analyst roles in Finance and FinTech.

## Features

- **Portfolio management** — add and remove positions across multiple lots per ticker
- **Multi-currency support** — live FX conversion across USD, EUR, GBP, and CHF
- **Performance metrics** — current value, daily P&L, return %, and portfolio weight per position
- **Interactive charts** — portfolio allocation pie chart, normalised 6-month performance comparison, and individual price history with buy price and purchase date overlays
- **Global stock coverage** — S&P 500, FTSE 100, DAX, CAC 40, SMI, AEX, IBEX 35, and 10 ETFs
- **Import / export** — save and load your portfolio as JSON

## Live Demo

[![Live Demo](https://img.shields.io/badge/Live%20Demo-Streamlit-red)](https://market-dashboardgit-p4ehquxxrncud3gzyvhbeq.streamlit.app)

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
├── app.py              # Streamlit application
├── src/
│   ├── stocks.py       # Stock list fetching (Wikipedia scraper)
│   ├── fx.py           # FX rate fetching and currency detection
│   └── portfolio.py    # Portfolio construction and P&L calculations
├── notebooks/          # Jupyter notebooks for data exploration
├── data/               # Local data files (gitignored)
├── requirements.txt
└── README.md
```

## Tech Stack

- Python 3.12
- [Streamlit](https://streamlit.io) — web UI
- [yfinance](https://github.com/ranaroussi/yfinance) — real-time stock data
- [pandas](https://pandas.pydata.org) — data processing
- [Plotly](https://plotly.com/python/) — interactive charts
